"""
PropInferenceService — localized Random Forest + Bayesian inference for NBA player props.

Pipeline per request
────────────────────
  1. Scale the 10 incoming features with the persisted StandardScaler
     (fitted by sync_qdrant.py on the full historical dataset)
  2. Apply the same domain weights used during ingestion
  3. Query Qdrant for the `limit` most similar historical prop contexts
     — an optional `date_limit` timestamp filter prevents data leakage
       during walk-forward backtesting
  4. Binarize the neighbour payloads against the current `prop_line`:
       label = 1 if actual_points_scored > prop_line, else 0
  5. Train a localised RandomForestClassifier on those N outcomes
     → rf_prob (probability of going OVER)
  6. Bayesian Beta-Binomial update (exact conjugate posterior):
       Prior:     Beta(α₀, β₀)   where α₀ = rf_prob * K, β₀ = (1−rf_prob) * K
       Evidence:  n_over successes in n_total trials (the neighbour outcomes)
       Posterior: Beta(α₀ + n_over, β₀ + n_total − n_over)
     This is the analytical exact solution, equivalent to running:
         p  = pm.Beta('p', alpha=α₀, beta=β₀)
         pm.Binomial('obs', n=n_total, p=p, observed=n_over)
     Returns posterior mean and 95% HDI via scipy.stats.beta
  7. edge = posterior_mean − implied_prob
  8. Fractional Quarter-Kelly bet sizing

Usage
─────
  service = PropInferenceService()
  result  = service.predict(features, prop_line=24.5, implied_prob=0.524)
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from loguru import logger
from scipy import stats as scipy_stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

ROOT = Path(__file__).parent.parent.parent          # → backend/
sys.path.insert(0, str(ROOT))

from app.config import settings                      # noqa: E402

# ── constants (must match sync_qdrant.py exactly) ────────────────────────────
COLLECTION_NAME = settings.QDRANT_COLLECTION_NBA_PROPS
SCALER_PATH = ROOT.parent / "models" / "prop_scaler.joblib"

FEATURE_NAMES: list[str] = [
    "usage_rate_season",
    "l5_form_variance",
    "expected_mins",
    "opp_pace",
    "opp_def_rtg",
    "def_vs_position",
    "implied_team_total",
    "spread",
    "rest_advantage",
    "is_home",
]

DOMAIN_WEIGHTS = np.array(
    [2.0, 1.5, 2.0, 1.5, 1.5, 1.5, 1.2, 0.8, 0.8, 0.5],
    dtype=float,
)

# Bayesian prior pseudo-observation count.
# K = 10 → prior has the weight of 10 "virtual" past games.
# Lower K = posterior tracks the 50-neighbour evidence more aggressively.
_PRIOR_STRENGTH: int = 10

# Quarter-Kelly hard cap per bet (10% of bankroll maximum)
_BANKROLL_CAP: float = 0.10


class PropInferenceService:
    """
    Full inference pipeline: feature vectorisation → Qdrant kNN →
    localised Random Forest → Bayesian update → edge + Kelly sizing.
    """

    def __init__(self) -> None:
        self._scaler: Optional[StandardScaler] = self._load_scaler()
        self._qdrant: QdrantClient = self._init_qdrant()

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(
        self,
        features: dict[str, float],
        prop_line: float,
        implied_prob: float,
        date_limit: Optional[datetime] = None,
        n_neighbors: int = 50,
    ) -> dict:
        """
        Run the full inference pipeline for one NBA player points prop.

        Parameters
        ----------
        features : dict
            The 10 feature keys (see FEATURE_NAMES).  Missing keys default to 0.
        prop_line : float
            Sportsbook line (e.g. 24.5).  Neighbours are binarised against this.
        implied_prob : float
            Market implied probability of the OVER (0–1).
        date_limit : datetime, optional
            When set, Qdrant only returns neighbours whose game_date_ts < this
            timestamp.  Pass the current loop date during backtesting.
        n_neighbors : int
            Number of Qdrant neighbours to retrieve (default 50).

        Returns
        -------
        dict with keys:
            rf_prob, posterior_mean, edge, p05, p95,
            kelly_fraction, recommendation, n_neighbors_used, n_over
        """
        if self._scaler is None:
            raise RuntimeError(
                "StandardScaler not loaded. Run `python -m app.scripts.sync_qdrant` first."
            )

        # Step 1 — vectorise
        query_vec = self._vectorise(features)

        # Step 2 — retrieve nearest neighbours
        neighbours = self._query_qdrant(query_vec, date_limit, n_neighbors)
        if len(neighbours) < 5:
            raise ValueError(
                f"Only {len(neighbours)} Qdrant neighbours found (need ≥ 5). "
                "Populate the collection with sync_qdrant.py first."
            )

        # Step 3 — binarise against prop_line
        actuals = np.array(
            [float(p.payload["actual_points_scored"]) for p in neighbours]
        )
        labels = (actuals > prop_line).astype(int)
        n_total = len(labels)
        n_over = int(labels.sum())

        # Step 4 — localised Random Forest
        rf_prob = self._train_local_rf(neighbours, labels)

        # Step 5 — Bayesian Beta-Binomial update
        posterior_mean, p05, p95 = self._bayesian_update(rf_prob, n_over, n_total)

        # Step 6 — edge
        edge = posterior_mean - implied_prob

        # Step 7 — Quarter-Kelly sizing
        kelly_fraction = self._quarter_kelly(posterior_mean, implied_prob)

        if abs(edge) < 0.02:
            recommendation = "PASS"
        elif edge > 0:
            recommendation = "OVER"
        else:
            recommendation = "UNDER"

        return {
            "rf_prob":          round(rf_prob, 4),
            "posterior_mean":   round(posterior_mean, 4),
            "edge":             round(edge, 4),
            "p05":              round(p05, 4),
            "p95":              round(p95, 4),
            "kelly_fraction":   round(kelly_fraction, 4),
            "recommendation":   recommendation,
            "n_neighbors_used": n_total,
            "n_over":           n_over,
        }

    # ── Internal: vectorisation ───────────────────────────────────────────────

    def _vectorise(self, features: dict[str, float]) -> list[float]:
        """Scale and weight the feature dict into a Qdrant query vector."""
        raw = np.array([features.get(f, 0.0) for f in FEATURE_NAMES], dtype=float)
        scaled = self._scaler.transform(raw.reshape(1, -1))[0]
        weighted = scaled * DOMAIN_WEIGHTS
        return weighted.tolist()

    # ── Internal: Qdrant ─────────────────────────────────────────────────────

    def _query_qdrant(
        self,
        query_vec: list[float],
        date_limit: Optional[datetime],
        limit: int,
    ) -> list:
        """Query Qdrant, optionally restricting to data before date_limit."""
        flt: Optional[qmodels.Filter] = None
        if date_limit is not None:
            flt = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="game_date_ts",
                        range=qmodels.Range(lt=date_limit.timestamp()),
                    )
                ]
            )

        result = self._qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vec,
            query_filter=flt,
            limit=limit,
        )
        return result.points

    # ── Internal: localised Random Forest ────────────────────────────────────

    def _train_local_rf(self, neighbours: list, labels: np.ndarray) -> float:
        """
        Train a Random Forest on the raw features of the 50 neighbours.
        Returns the probability of going OVER the prop line.

        Uses OOB (out-of-bag) probability estimate for a more honest
        assessment with small-sample training sets.
        """
        if len(np.unique(labels)) < 2:
            # All neighbours are the same class — return the base rate directly
            return float(labels.mean())

        X = np.array(
            [
                [float(p.payload["features"].get(f, 0.0)) for f in FEATURE_NAMES]
                for p in neighbours
            ]
        )

        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=4,
            min_samples_leaf=3,
            oob_score=True,
            random_state=42,
            n_jobs=-1,
        )
        rf.fit(X, labels)

        # oob_decision_function_ shape: (n_samples, n_classes)
        # Column 1 = P(OVER); take the mean across all training samples
        return float(rf.oob_decision_function_[:, 1].mean())

    # ── Internal: Bayesian Beta-Binomial update ───────────────────────────────

    def _bayesian_update(
        self,
        rf_prob: float,
        n_over: int,
        n_total: int,
    ) -> tuple[float, float, float]:
        """
        Exact Beta-Binomial conjugate posterior update.

        Model
        ─────
          Prior:     p ~ Beta(α₀, β₀)
                         α₀ = rf_prob * K
                         β₀ = (1 − rf_prob) * K
          Likelihood: n_over | p ~ Binomial(n_total, p)
          Posterior:  p | data ~ Beta(α₀ + n_over, β₀ + n_total − n_over)

        This is the analytical closed-form solution to:
            with pm.Model():
                p   = pm.Beta('p', alpha=α₀, beta=β₀)
                obs = pm.Binomial('obs', n=n_total, p=p, observed=n_over)

        Returns
        ───────
        (posterior_mean, hdi_lower_95, hdi_upper_95)
        """
        alpha_0 = max(rf_prob * _PRIOR_STRENGTH, 1e-6)
        beta_0  = max((1.0 - rf_prob) * _PRIOR_STRENGTH, 1e-6)

        alpha_post = alpha_0 + n_over
        beta_post  = beta_0  + (n_total - n_over)

        posterior = scipy_stats.beta(alpha_post, beta_post)
        posterior_mean = float(posterior.mean())
        p05, p95 = map(float, posterior.interval(0.95))

        return posterior_mean, p05, p95

    # ── Internal: Kelly sizing ────────────────────────────────────────────────

    @staticmethod
    def _quarter_kelly(prob: float, implied_prob: float) -> float:
        """
        Fractional Quarter-Kelly criterion.

        Kelly formula:  f* = (b·p − q) / b
            b = (1 / implied_prob) − 1   (decimal odds minus 1)
            q = 1 − p

        Returns the Quarter-Kelly fraction (capped at _BANKROLL_CAP).
        Multiply by current bankroll to get the dollar bet size.
        """
        if implied_prob <= 0.0 or implied_prob >= 1.0:
            return 0.0

        b = (1.0 / implied_prob) - 1.0
        q = 1.0 - prob
        kelly = (b * prob - q) / b

        if kelly <= 0.0:
            return 0.0

        quarter_kelly = 0.25 * kelly
        return min(quarter_kelly, _BANKROLL_CAP)

    # ── Init helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _load_scaler() -> Optional[StandardScaler]:
        if SCALER_PATH.exists():
            scaler = joblib.load(SCALER_PATH)
            logger.info(f"Loaded StandardScaler from {SCALER_PATH}")
            return scaler
        logger.warning(
            f"Scaler not found at {SCALER_PATH}. "
            "Run `python -m app.scripts.sync_qdrant` to generate it."
        )
        return None

    @staticmethod
    def _init_qdrant() -> QdrantClient:
        if settings.QDRANT_HOST.startswith("http"):
            return QdrantClient(url=settings.QDRANT_HOST, api_key=settings.QDRANT_API_KEY)
        return QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY,
        )
