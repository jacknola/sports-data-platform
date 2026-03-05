"""
NCAAB Machine Learning Predictor Service

Uses ESPN BPI efficiency stats (AdjOE, AdjDE, BPI) to predict NCAAB game outcomes.
Loads a trained XGBoost moneyline model from models/ncaab_ml/ if available;
falls back to Pythagorean expectation (exponent 11.5, +3% home court) otherwise.

Game discovery: ESPN scoreboard (free, no API key required).
"""

import os
import pickle
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from loguru import logger

from app.services.sports_api import SportsAPIService
from app.services.ncaab_stats_service import NCAABStatsService

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = bool(xgb)  # verifies installation
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not installed — NCAAB will use Pythagorean fallback")

# League-average constants used in Pythagorean calculation
_LEAGUE_AVG = 106.0
_PYTH_EXP = 11.5
_HOME_COURT = 0.03
_MAX_KELLY = 0.10

FEATURE_COLS = [
    "home_adj_oe",
    "home_adj_de",
    "away_adj_oe",
    "away_adj_de",
    "home_bpi",
    "away_bpi",
    "spread",
]


class NCAABMLPredictor:
    """NCAAB game predictions using XGBoost (or Pythagorean fallback)."""

    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.sports_api = SportsAPIService()
        self.stats_service = NCAABStatsService()
        self._team_stats: Dict[str, Dict[str, float]] = {}
        self._load_models()

    # ── Model loading ────────────────────────────────────────────────────────

    def _load_models(self) -> None:
        _raw_path = os.getenv("NCAAB_MODEL_PATH", "./models/ncaab_ml")
        model_path = os.path.normpath(os.path.abspath(_raw_path))
        if not XGBOOST_AVAILABLE or not os.path.isdir(model_path):
            logger.info("NCAAB: no model directory — using Pythagorean fallback")
            return
        try:
            pkl = os.path.join(model_path, "moneyline_model.pkl")
            if os.path.exists(pkl):
                with open(pkl, "rb") as f:
                    self.models["moneyline"] = pickle.load(f)
                logger.info("NCAAB ML moneyline model loaded")
        except Exception as e:
            logger.warning(f"NCAAB: could not load model ({e}) — using Pythagorean")

    # ── Public API ───────────────────────────────────────────────────────────

    async def predict_today_games(self) -> List[Dict[str, Any]]:
        """
        Discover today's NCAAB games via ESPN and return ML predictions.

        Returns:
            List of prediction dicts (one per game).
        """
        logger.info("NCAAB ML: discovering today's games via ESPN")

        # 1. Fetch team stats (cached 24 h)
        self._team_stats = await self.stats_service.fetch_all_team_stats()
        if not self._team_stats:
            logger.warning("NCAAB ML: no team stats available from ESPN BPI")

        # 2. Discover games
        discovery = await self.sports_api.discover_games("basketball_ncaab")
        games = discovery.data or []
        if not games:
            logger.warning("NCAAB ML: no games found via ESPN scoreboard")
            return []

        logger.info(f"NCAAB ML: {len(games)} games via {discovery.source}")

        # 3. Try to get any available odds for EV calculation
        odds_lookup: Dict[str, Dict[str, Any]] = {}
        try:
            odds_raw = await self.sports_api.get_odds("basketball_ncaab")
            for g in (odds_raw or []):
                key = f"{g.get('home_team', '')}|{g.get('away_team', '')}"
                odds_lookup[key] = g
        except Exception as e:
            logger.warning(f"NCAAB ML: odds fetch failed ({e}) — EV skipped")

        # 4. Predict each game
        predictions: List[Dict[str, Any]] = []
        for game in games:
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            if not home or not away:
                continue

            odds_key = f"{home}|{away}"
            game_odds = odds_lookup.get(odds_key, {})
            pred = self._predict_game(home, away, game_odds)
            predictions.append(pred)

        logger.info(f"NCAAB ML: {len(predictions)} predictions generated")
        return predictions

    def _predict_game(
        self,
        home_team: str,
        away_team: str,
        odds_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Predict a single NCAAB game."""
        h_stats = self._get_team_stats(home_team)
        a_stats = self._get_team_stats(away_team)

        features = self._build_features(h_stats, a_stats, odds_data)
        home_prob = self._predict_moneyline(features)

        ev = self._calculate_ev(home_prob, odds_data)
        kelly = self._kelly(ev)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_win_probability": round(home_prob, 4),
            "away_win_probability": round(1.0 - home_prob, 4),
            "expected_value": ev,
            "kelly_criterion": kelly,
            "confidence": round(abs(home_prob - 0.5) * 2, 3),
            "method": "ml_xgboost" if "moneyline" in self.models else "pythagorean_fallback",
            "home_stats": h_stats or {},
            "away_stats": a_stats or {},
        }

    # ── Feature building ─────────────────────────────────────────────────────

    def _get_team_stats(self, team_name: str) -> Optional[Dict[str, float]]:
        return self.stats_service.get_team_stats(team_name)

    def _build_features(
        self,
        h: Optional[Dict[str, float]],
        a: Optional[Dict[str, float]],
        odds_data: Dict[str, Any],
    ) -> pd.DataFrame:
        # Default to league-average if stats unavailable
        h = h or {"AdjOE": _LEAGUE_AVG, "AdjDE": _LEAGUE_AVG, "BPI": 0.0}
        a = a or {"AdjOE": _LEAGUE_AVG, "AdjDE": _LEAGUE_AVG, "BPI": 0.0}

        spread = self._extract_spread(odds_data)

        row = {
            "home_adj_oe": h.get("AdjOE", _LEAGUE_AVG),
            "home_adj_de": h.get("AdjDE", _LEAGUE_AVG),
            "away_adj_oe": a.get("AdjOE", _LEAGUE_AVG),
            "away_adj_de": a.get("AdjDE", _LEAGUE_AVG),
            "home_bpi": h.get("BPI", 0.0),
            "away_bpi": a.get("BPI", 0.0),
            "spread": spread,
        }
        return pd.DataFrame([row])

    @staticmethod
    def _extract_spread(odds_data: Dict[str, Any]) -> float:
        """Pull the home-team spread from any bookmaker, or return 0."""
        for bm in odds_data.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "spreads":
                    for out in mkt.get("outcomes", []):
                        point = out.get("point")
                        if point is not None:
                            return float(point)
        return 0.0

    # ── Probability models ────────────────────────────────────────────────────

    def _predict_moneyline(self, features: pd.DataFrame) -> float:
        """Return P(home wins). Uses XGBoost if loaded, else Pythagorean."""
        if "moneyline" in self.models:
            try:
                prob = self.models["moneyline"].predict_proba(features[FEATURE_COLS])[0][1]
                return float(np.clip(prob, 0.05, 0.95))
            except Exception as e:
                logger.warning(f"NCAAB XGBoost predict failed ({e}), using Pythagorean")

        return self._pythagorean(features)

    @staticmethod
    def _pythagorean(features: pd.DataFrame) -> float:
        """Pythagorean win probability for college basketball (exponent 11.5)."""
        row = features.iloc[0]
        h_oe = max(row["home_adj_oe"], 50.0)
        h_de = max(row["home_adj_de"], 50.0)
        a_oe = max(row["away_adj_oe"], 50.0)
        a_de = max(row["away_adj_de"], 50.0)

        # Projected points per 100 possessions for each team in this matchup
        try:
            h_pts = (h_oe * a_de) / _LEAGUE_AVG
            a_pts = (a_oe * h_de) / _LEAGUE_AVG
            prob = (h_pts ** _PYTH_EXP) / (h_pts ** _PYTH_EXP + a_pts ** _PYTH_EXP)
        except (OverflowError, ZeroDivisionError):
            prob = 0.5

        return float(np.clip(prob + _HOME_COURT, 0.05, 0.95))

    # ── EV / Kelly ────────────────────────────────────────────────────────────

    def _calculate_ev(
        self, home_prob: float, odds_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        home_odds, away_odds = self._extract_ml_odds(odds_data)

        def _ev(prob: float, american: int) -> float:
            dec = (american / 100 + 1) if american > 0 else (100 / abs(american) + 1)
            return prob * (dec - 1) - (1 - prob)

        h_ev = _ev(home_prob, home_odds)
        a_ev = _ev(1 - home_prob, away_odds)

        return {
            "home_ev": round(h_ev, 4),
            "away_ev": round(a_ev, 4),
            "best_bet": "home" if h_ev >= a_ev else "away",
            "home_odds": home_odds,
            "away_odds": away_odds,
        }

    @staticmethod
    def _extract_ml_odds(odds_data: Dict[str, Any]) -> tuple:
        """Extract moneyline odds from h2h or spreads markets."""
        home_odds, away_odds = -110, -110
        for bm in odds_data.get("bookmakers", []):
            for mkt in bm.get("markets", []):
                if mkt.get("key") == "h2h":
                    outcomes = mkt.get("outcomes", [])
                    if len(outcomes) >= 2:
                        home_odds = round(outcomes[0].get("price", -110))
                        away_odds = round(outcomes[1].get("price", -110))
                    return home_odds, away_odds
        return home_odds, away_odds

    @staticmethod
    def _kelly(ev: Dict[str, Any]) -> float:
        """Quarter-Kelly on the best bet, capped at MAX_KELLY."""
        best = ev["best_bet"]
        prob = ev["home_ev"] if best == "home" else ev["away_ev"]
        if prob <= 0:
            return 0.0
        # Simple approximation: kelly ≈ edge / (decimal_odds - 1)
        odds = ev["home_odds"] if best == "home" else ev["away_odds"]
        dec_minus_1 = (odds / 100) if odds > 0 else (100 / abs(odds))
        full_kelly = prob / dec_minus_1 if dec_minus_1 > 0 else 0.0
        return round(min(full_kelly * 0.25, _MAX_KELLY), 4)
