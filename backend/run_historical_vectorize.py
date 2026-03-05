"""
Historical Data Vectorization Service

Vectorizes historical game lines and player props for semantic search
using Qdrant (primary) and PostgreSQL pgvector (secondary).

Usage:
    python3 run_historical_vectorize.py --type games --limit 1000
    python3 run_historical_vectorize.py --type props --limit 5000
    python3 run_historical_vectorize.py --type all
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger

from app.database import SessionLocal
from app.models.historical_game_line import HistoricalGameLine
from app.models.historical_player_prop import HistoricalPlayerProp

from app.skills import firecrawl
# Vector store imports
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from sentence_transformers import SentenceTransformer
    from app.config import settings

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning(
        "Qdrant not available - install with: pip install qdrant-client sentence-transformers"
    )


class HistoricalVectorizer:
    """Vectorize historical data for semantic search."""

    # Qdrant collection names
    COLLECTION_GAMES = "historical_games"
    COLLECTION_PROPS = "historical_props"

    def __init__(self):
        if QDRANT_AVAILABLE:
            if settings.QDRANT_HOST.startswith("http"):
                self.client = QdrantClient(
                    url=settings.QDRANT_HOST, api_key=settings.QDRANT_API_KEY
                )
            else:
                self.client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    api_key=settings.QDRANT_API_KEY,
                )
            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
            self._ensure_collections()
        else:
            self.client = None
            self.encoder = None

    def _ensure_collections(self):
        """Create collections if they don't exist."""
        if not QDRANT_AVAILABLE:
            return

        collections = self.client.get_collections().collections

        for name in [self.COLLECTION_GAMES, self.COLLECTION_PROPS]:
            exists = any(c.name == name for c in collections)
            if not exists:
                logger.info(f"Creating Qdrant collection: {name}")
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(
                        size=384, distance=models.Distance.COSINE
                    ),
                )


    async def get_web_context_for_game(self, team1: str, team2: str) -> str:
        """Get web context for a game using Firecrawl."""
        if not team1 or not team2:
            return ""
        try:
            query = f"{team1} vs {team2} news and analysis"
            logger.info(f"Firecrawling for: {query}")
            # Note: Assuming firecrawl skill is available and returns a dict with 'summary'
            result = await firecrawl.scrape_and_summarize(query=query)
            return result.get("summary", "")
        except Exception as e:
            logger.error(f"Error getting web context with Firecrawl: {e}")
            return ""

    def generate_game_description(self, game: HistoricalGameLine) -> str:
        """Generate semantic description for a game."""
        parts = []

        if game.season:
            parts.append(f"{game.season}-{game.season + 1} season")

        if game.home_team and game.away_team:
            parts.append(f"{game.home_team} vs {game.away_team}")

        if game.home_score is not None and game.away_score is not None:
            result = f"Final score: {game.home_team} {game.home_score}, {game.away_team} {game.away_score}"
            parts.append(result)

            margin = game.home_score - game.away_score
            if margin > 0:
                parts.append(f"{game.home_team} won by {margin} points")
            elif margin < 0:
                parts.append(f"{game.away_team} won by {-margin} points")
            else:
                parts.append("Game went to overtime")

        if game.home_spread is not None:
            spread_line = f"Spread: {game.home_team} {game.home_spread}"
            parts.append(spread_line)

        if game.over_under is not None:
            parts.append(f"Total: {game.over_under}")

        if game.home_ml and game.away_ml:
            parts.append(
                f"Moneyline: {game.home_team} {game.home_ml}, {game.away_team} {game.away_ml}"
            )

        if game.clv_spread:
            parts.append(f"CLV spread: {game.clv_spread:.2f}")
        if game.clv_total:
            parts.append(f"CLV total: {game.clv_total:.2f}")


        # Get real-time web context
        web_context = asyncio.run(self.get_web_context_for_game(game.home_team, game.away_team))
        if web_context:
            parts.append(f"Context: {web_context}")

        return ". ".join(parts)

    def generate_prop_description(self, prop: HistoricalPlayerProp) -> str:
        """Generate semantic description for a player prop."""
        parts = []

        if prop.player_name:
            parts.append(f"{prop.player_name} prop")

        if prop.team and prop.opponent:
            parts.append(f"{prop.team} vs {prop.opponent}")

        if prop.game_date:
            parts.append(f"Date: {prop.game_date.strftime('%Y-%m-%d')}")

        if prop.prop_type and prop.line:
            parts.append(f"{prop.prop_type} over/under {prop.line}")

        if prop.over_odds and prop.under_odds:
            parts.append(f"Odds: over {prop.over_odds}, under {prop.under_odds}")

        if prop.actual is not None:
            parts.append(f"Result: {prop.actual} {prop.prop_type}")
            if prop.result:
                parts.append(f"Outcome: {prop.result}")

        if prop.clv is not None:
            parts.append(f"Closing line value: {prop.clv:.2f}")

        if prop.predicted is not None and prop.actual is not None:
            edge = prop.actual - prop.predicted
            parts.append(
                f"Model predicted {prop.predicted:.1f}, actual was {prop.actual:.1f}, edge: {edge:.1f}"
            )

        return ". ".join(parts)

    def vectorize_games(self, limit: int = 1000, batch_size: int = 100) -> int:
        """Vectorize historical game lines."""
        if not QDRANT_AVAILABLE or not self.client:
            logger.warning("Qdrant not available, skipping game vectorization")
            return 0

        db = SessionLocal()
        total = 0

        try:
            offset = 0
            while True:
                games = (
                    db.query(HistoricalGameLine).limit(batch_size).offset(offset).all()
                )

                if not games:
                    break

                points = []
                for game in games:
                    description = self.generate_game_description(game)
                    vector = self.encoder.encode(description).tolist()

                    points.append(
                        models.PointStruct(
                            id=game.id,
                            vector=vector,
                            payload={
                                "game_id": game.id,
                                "external_game_id": game.external_game_id,
                                "season": game.season,
                                "game_date": game.game_date.isoformat()
                                if game.game_date
                                else None,
                                "home_team": game.home_team,
                                "away_team": game.away_team,
                                "home_score": game.home_score,
                                "away_score": game.away_score,
                                "total_score": game.total_score,
                                "home_spread": game.home_spread,
                                "over_under": game.over_under,
                                "source": game.source,
                                "description": description,
                            },
                        )
                    )

                self.client.upsert(collection_name=self.COLLECTION_GAMES, points=points)

                total += len(points)
                offset += batch_size
                logger.info(f"Vectorized {total} games...")

                if total >= limit:
                    break

        finally:
            db.close()

        logger.info(f"Game vectorization complete. Total: {total}")
        return total

    def vectorize_props(self, limit: int = 5000, batch_size: int = 100) -> int:
        """Vectorize historical player props."""
        if not QDRANT_AVAILABLE or not self.client:
            logger.warning("Qdrant not available, skipping prop vectorization")
            return 0

        db = SessionLocal()
        total = 0

        try:
            offset = 0
            while True:
                props = (
                    db.query(HistoricalPlayerProp)
                    .limit(batch_size)
                    .offset(offset)
                    .all()
                )

                if not props:
                    break

                points = []
                for prop in props:
                    description = self.generate_prop_description(prop)
                    vector = self.encoder.encode(description).tolist()

                    points.append(
                        models.PointStruct(
                            id=prop.id,
                            vector=vector,
                            payload={
                                "prop_id": prop.id,
                                "external_prop_id": prop.external_prop_id,
                                "player_name": prop.player_name,
                                "team": prop.team,
                                "opponent": prop.opponent,
                                "game_date": prop.game_date.isoformat()
                                if prop.game_date
                                else None,
                                "season": prop.season,
                                "prop_type": prop.prop_type,
                                "line": prop.line,
                                "actual": prop.actual,
                                "result": prop.result,
                                "sportsbook": prop.sportsbook,
                                "source": prop.source,
                                "description": description,
                            },
                        )
                    )

                self.client.upsert(collection_name=self.COLLECTION_PROPS, points=points)

                total += len(points)
                offset += batch_size
                logger.info(f"Vectorized {total} props...")

                if total >= limit:
                    break

        finally:
            db.close()

        logger.info(f"Prop vectorization complete. Total: {total}")
        return total


async def run_vectorization(data_type: str = "all", limit: int = 1000):
    """Run vectorization."""
    vectorizer = HistoricalVectorizer()

    if data_type in ("games", "all"):
        logger.info("Vectorizing historical games...")
        vectorizer.vectorize_games(limit)

    if data_type in ("props", "all"):
        logger.info("Vectorizing historical player props...")
        # Props typically have more data, use higher limit
        prop_limit = limit * 5 if data_type == "all" else limit
        vectorizer.vectorize_props(prop_limit)


def main():
    parser = argparse.ArgumentParser(description="Historical data vectorization")
    parser.add_argument(
        "--type",
        choices=["games", "props", "all"],
        default="all",
        help="Data type to vectorize",
    )
    parser.add_argument(
        "--limit", type=int, default=1000, help="Max records to vectorize"
    )
    args = parser.parse_args()

    asyncio.run(run_vectorization(args.type, args.limit))


if __name__ == "__main__":
    main()
