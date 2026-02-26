"""
Ingest historical NBA player prop data into Qdrant.

For each row in player_game_logs the script computes 10 point-in-time
features using SQL window functions (ROWS BETWEEN UNBOUNDED PRECEDING AND
1 PRECEDING) — this guarantees zero data leakage: only information that
was available before a given game is used to describe that game.

The 10 features
───────────────
  1. usage_rate_season   — season pts/min * 36 (opportunity proxy)
  2. l5_form_variance    — VAR_SAMP of pts over last 5 games
  3. expected_mins       — season AVG(min) to date
  4. opp_pace            — from scenario JSON (default 100.0)
  5. opp_def_rtg         — from scenario JSON (default 112.0)
  6. def_vs_position     — from scenario JSON (default 0.0)
  7. implied_team_total  — from scenario JSON (default 112.5)
  8. spread              — from scenario JSON (default 0.0)
  9. rest_advantage      — days since player's previous game
 10. is_home             — 1 if player's team is the home team

Pipeline
────────
  1. Query PostgreSQL with the window-function SQL
  2. Fit a StandardScaler on all rows; persist to backend/models/prop_scaler.joblib
  3. Apply domain-specific feature weights (higher weight = more influence on
     nearest-neighbour retrieval)
  4. Upsert 10-dim weighted vectors into Qdrant collection `nba_historical_props`
     Payload stores raw features, game_date (ISO string), game_date_ts (Unix float
     for range filtering), player_name, and actual_points_scored

Requirements
────────────
  • PostgreSQL — SQLite does NOT support VAR_SAMP window functions or JSON operators
  • Qdrant running (local or cloud)
  • player_game_logs populated via run_backfill_pipeline.py

Usage
─────
  cd backend
  python -m app.scripts.sync_qdrant          # incremental upsert
  python -m app.scripts.sync_qdrant --wipe   # drop + recreate collection first
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

# ── path resolution (run as module or direct script) ─────────────────────────
ROOT = Path(__file__).parent.parent.parent          # → backend/
sys.path.insert(0, str(ROOT))

from app.config import settings                      # noqa: E402
from app.database import SessionLocal                # noqa: E402

# ── constants ─────────────────────────────────────────────────────────────────
COLLECTION_NAME = settings.QDRANT_COLLECTION_NBA_PROPS
VECTOR_DIM = 10
MODEL_DIR = ROOT.parent / "models"                   # → sports-data-platform/backend/../models
SCALER_PATH = MODEL_DIR / "prop_scaler.joblib"

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

# Domain weights — multiplied onto scaled features before Qdrant upsert.
# Higher weight = feature pulls neighbours closer together on that dimension.
DOMAIN_WEIGHTS = np.array(
    [
        2.0,   # usage_rate_season   — minutes/opportunity is the strongest signal
        1.5,   # l5_form_variance    — hot/cold streaks matter
        2.0,   # expected_mins       — minutes = scoring opportunity
        1.5,   # opp_pace            — up-tempo games inflate counting stats
        1.5,   # opp_def_rtg         — weak defences give up more
        1.5,   # def_vs_position     — positional matchup quality
        1.2,   # implied_team_total  — team scoring environment
        0.8,   # spread              — correlated with totals, secondary
        0.8,   # rest_advantage      — rest matters but less for individual props
        0.5,   # is_home             — home court effect minor for individual stats
    ],
    dtype=float,
)

# ── SQL (PostgreSQL only) ─────────────────────────────────────────────────────
# All window frames use ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING so
# that features for game N only include games 1 … N-1 (strict point-in-time).
_SQL = text("""
WITH pit AS (
    SELECT
        pgl.id                                                              AS log_id,
        pgl.player_id,
        pgl.game_id,
        pgl.game_date,
        pgl.pts                                                             AS actual_points_scored,
        p.name                                                              AS player_name,

        -- Feature 1: Usage Rate (Season) — pts/min * 36, prior games only
        COALESCE(
            AVG(pgl.pts)  OVER w_season
            / NULLIF(AVG(pgl.min) OVER w_season, 0)
            * 36.0,
            18.0
        )                                                                   AS usage_rate_season,

        -- Feature 2: L5 Form Variance
        COALESCE(VAR_SAMP(pgl.pts) OVER w_l5, 25.0)                        AS l5_form_variance,

        -- Feature 3: Expected Minutes
        COALESCE(AVG(pgl.min) OVER w_season, 24.0)                         AS expected_mins,

        -- Feature 9: Rest Advantage (days since previous game)
        COALESCE(
            EXTRACT(EPOCH FROM (
                pgl.game_date
                - LAG(pgl.game_date) OVER (
                    PARTITION BY pgl.player_id ORDER BY pgl.game_date
                )
            )) / 86400.0,
            2.0
        )                                                                   AS rest_advantage,

        -- Features 4-8 from scenario JSON (populated by backfill pipeline)
        COALESCE((pgl.scenario->>'opp_pace')::float,          100.0)       AS opp_pace,
        COALESCE((pgl.scenario->>'opp_def_rtg')::float,       112.0)       AS opp_def_rtg,
        COALESCE((pgl.scenario->>'def_vs_position')::float,     0.0)       AS def_vs_position,
        COALESCE((pgl.scenario->>'implied_team_total')::float, 112.5)      AS implied_team_total,
        COALESCE((pgl.scenario->>'spread')::float,              0.0)       AS spread,

        -- Feature 10: Home/Away
        CASE WHEN t.name = g.home_team THEN 1 ELSE 0 END                   AS is_home

    FROM  player_game_logs  pgl
    JOIN  players           p   ON p.id  = pgl.player_id
    JOIN  games             g   ON g.id  = pgl.game_id
    JOIN  teams             t   ON t.id  = pgl.team_id

    WHERE pgl.pts IS NOT NULL
      AND pgl.min IS NOT NULL
      AND pgl.min > 0

    WINDOW
        -- All prior games in the season (exclusive of current row)
        w_season AS (
            PARTITION BY pgl.player_id
            ORDER BY pgl.game_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
        ),
        -- Last 5 prior games
        w_l5 AS (
            PARTITION BY pgl.player_id
            ORDER BY pgl.game_date
            ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        )
)
SELECT *
FROM   pit
WHERE  usage_rate_season > 0   -- need at least one prior game
ORDER  BY game_date ASC
""")

_RESULT_COLUMNS = [
    "log_id", "player_id", "game_id", "game_date",
    "actual_points_scored", "player_name",
    *FEATURE_NAMES,
]


# ── Qdrant helpers ────────────────────────────────────────────────────────────

def _qdrant_client() -> QdrantClient:
    if settings.QDRANT_HOST.startswith("http"):
        return QdrantClient(url=settings.QDRANT_HOST, api_key=settings.QDRANT_API_KEY)
    return QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        api_key=settings.QDRANT_API_KEY,
    )


def _ensure_collection(client: QdrantClient, *, wipe: bool = False) -> None:
    existing = {c.name for c in client.get_collections().collections}

    if wipe and COLLECTION_NAME in existing:
        logger.info(f"Wiping collection '{COLLECTION_NAME}'")
        client.delete_collection(COLLECTION_NAME)
        existing.discard(COLLECTION_NAME)

    if COLLECTION_NAME not in existing:
        logger.info(f"Creating collection '{COLLECTION_NAME}' (dim={VECTOR_DIM}, cosine)")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(
                size=VECTOR_DIM,
                distance=qmodels.Distance.COSINE,
            ),
        )
        # Float payload index on game_date_ts enables fast range filtering
        # during backtesting (date_limit parameter in inference_service.py)
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="game_date_ts",
            field_schema=qmodels.PayloadSchemaType.FLOAT,
        )
        logger.info("Payload index created on 'game_date_ts'")


def _det_id(log_id: int) -> int:
    """Deterministic positive-integer Qdrant point ID derived from the DB primary key."""
    digest = hashlib.sha256(f"nba_prop_{log_id}".encode()).hexdigest()
    return int(digest, 16) % (2**63 - 1)


def _to_ts(game_date: Any) -> float:
    """Convert a game_date (datetime or ISO string) to a UTC Unix timestamp."""
    if isinstance(game_date, str):
        game_date = datetime.fromisoformat(game_date)
    if game_date.tzinfo is None:
        game_date = game_date.replace(tzinfo=timezone.utc)
    return game_date.timestamp()


# ── Main ──────────────────────────────────────────────────────────────────────

def main(*, wipe: bool = False) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Query PostgreSQL ───────────────────────────────────────────────────
    logger.info("Querying PostgreSQL with point-in-time window functions…")
    db = SessionLocal()
    try:
        rows = db.execute(_SQL).fetchall()
    finally:
        db.close()

    if not rows:
        logger.error(
            "No rows returned. Ensure player_game_logs is populated "
            "(run run_backfill_pipeline.py) and the DATABASE_URL points to PostgreSQL."
        )
        return

    df = pd.DataFrame(rows, columns=_RESULT_COLUMNS)
    logger.info(f"Loaded {len(df):,} player-game rows")

    # ── 2. Fit StandardScaler and persist ────────────────────────────────────
    X_raw = df[FEATURE_NAMES].astype(float).fillna(0.0)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)

    joblib.dump(scaler, SCALER_PATH)
    logger.info(f"StandardScaler saved → {SCALER_PATH}")

    # ── 3. Apply domain weights (post-scaling) ────────────────────────────────
    X_weighted = X_scaled * DOMAIN_WEIGHTS   # shape (N, 10)

    # ── 4. Upsert into Qdrant in batches ──────────────────────────────────────
    client = _qdrant_client()
    _ensure_collection(client, wipe=wipe)

    batch_size = 256
    total = len(df)
    upserted = 0

    for start in range(0, total, batch_size):
        chunk = df.iloc[start : start + batch_size]
        vectors = X_weighted[start : start + batch_size]

        points: list[qmodels.PointStruct] = []
        for i, (_, row) in enumerate(chunk.iterrows()):
            ts = _to_ts(row["game_date"])
            gd_str = (
                row["game_date"].isoformat()
                if hasattr(row["game_date"], "isoformat")
                else str(row["game_date"])
            )
            points.append(
                qmodels.PointStruct(
                    id=_det_id(int(row["log_id"])),
                    vector=vectors[i].tolist(),
                    payload={
                        "log_id":               int(row["log_id"]),
                        "player_id":            int(row["player_id"]),
                        "player_name":          str(row["player_name"]),
                        "game_date":            gd_str,
                        "game_date_ts":         ts,
                        "actual_points_scored": float(row["actual_points_scored"]),
                        # Raw (unscaled) features stored for RF training
                        "features": {
                            feat: float(row[feat]) for feat in FEATURE_NAMES
                        },
                    },
                )
            )

        client.upsert(collection_name=COLLECTION_NAME, points=points)
        upserted += len(points)
        logger.info(f"  Upserted {upserted:,} / {total:,}")

    logger.info(f"Sync complete — {upserted:,} vectors in '{COLLECTION_NAME}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync NBA prop data to Qdrant")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete and recreate the Qdrant collection before syncing",
    )
    args = parser.parse_args()
    main(wipe=args.wipe)
