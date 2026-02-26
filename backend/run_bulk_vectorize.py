"""
Bulk Vectorization Script
Optimized for processing large volumes of historical games and player logs into Qdrant.
"""

import sys
import os
import argparse
import asyncio
from typing import List, Dict, Any
from loguru import logger
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.game import Game
from app.models.player_game_log import PlayerGameLog
from app.models.player import Player
from app.config import settings

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from sentence_transformers import SentenceTransformer
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("Qdrant/SentenceTransformers not installed.")


class BulkVectorizer:
    def __init__(self):
        if not QDRANT_AVAILABLE:
            return
            
        if settings.QDRANT_HOST.startswith("http"):
            self.client = QdrantClient(url=settings.QDRANT_HOST, api_key=settings.QDRANT_API_KEY, timeout=60.0)
        else:
            self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, api_key=settings.QDRANT_API_KEY, timeout=60.0)
            
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        self._ensure_collections()

    def _ensure_collections(self):
        collections = self.client.get_collections().collections
        
        for name in [settings.QDRANT_COLLECTION_GAMES, settings.QDRANT_COLLECTION_PLAYERS]:
            if not any(c.name == name for c in collections):
                logger.info(f"Creating collection {name}...")
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
                )

    def vectorize_games(self, batch_size=100, limit=None):
        logger.info("Vectorizing Games...")
        db = SessionLocal()
        total = 0
        try:
            query = select(Game).order_by(Game.id.desc())
            if limit:
                query = query.limit(limit)
                
            games = db.execute(query).scalars().all()
            
            for i in range(0, len(games), batch_size):
                batch = games[i:i+batch_size]
                texts = []
                payloads = []
                ids = []
                
                for game in batch:
                    # Skip if no score
                    if game.home_score is None:
                        continue
                    
                    desc = f"{game.sport.upper()} Game: {game.away_team} ({game.away_score}) @ {game.home_team} ({game.home_score}). Date: {game.game_date.strftime('%Y-%m-%d') if game.game_date else 'Unknown'}."
                    texts.append(desc)
                    ids.append(game.id)
                    payloads.append({
                        "game_id": game.external_game_id,
                        "sport": game.sport,
                        "home_team": game.home_team,
                        "away_team": game.away_team,
                        "home_score": game.home_score,
                        "away_score": game.away_score,
                        "date": game.game_date.strftime('%Y-%m-%d') if game.game_date else None,
                        "description": desc
                    })

                if not texts:
                    continue
                    
                vectors = self.encoder.encode(texts, batch_size=batch_size, show_progress_bar=False).tolist()
                
                points = [
                    models.PointStruct(id=ids[j], vector=vectors[j], payload=payloads[j])
                    for j in range(len(ids))
                ]
                
                self.client.upsert(collection_name=settings.QDRANT_COLLECTION_GAMES, points=points)
                total += len(points)
                logger.info(f"Vectorized {total} games...")
                
        finally:
            db.close()
        return total

    def vectorize_player_logs(self, batch_size=100, limit=None):
        logger.info("Vectorizing Player Game Logs...")
        db = SessionLocal()
        total = 0
        try:
            # Join Player to get the name
            query = select(PlayerGameLog, Player.name).join(Player, PlayerGameLog.player_id == Player.id).order_by(PlayerGameLog.id.desc())
            if limit:
                query = query.limit(limit)
                
            results = db.execute(query).all()
            
            for i in range(0, len(results), batch_size):
                batch = results[i:i+batch_size]
                texts = []
                payloads = []
                ids = []
                
                for log, player_name in batch:
                    # A concise description combining player and stats
                    desc = f"Player {player_name} scored {log.pts} points, {log.reb} rebounds, {log.ast} assists (PRA: {log.pra}) on {log.game_date.strftime('%Y-%m-%d') if log.game_date else 'Unknown'}."
                    texts.append(desc)
                    ids.append(log.id)
                    payloads.append({
                        "log_id": log.external_log_id,
                        "player_name": player_name,
                        "pts": log.pts,
                        "reb": log.reb,
                        "ast": log.ast,
                        "pra": log.pra,
                        "date": log.game_date.strftime('%Y-%m-%d') if log.game_date else None,
                        "description": desc
                    })

                if not texts:
                    continue
                    
                vectors = self.encoder.encode(texts, batch_size=batch_size, show_progress_bar=False).tolist()
                
                points = [
                    models.PointStruct(id=ids[j], vector=vectors[j], payload=payloads[j])
                    for j in range(len(ids))
                ]
                
                self.client.upsert(collection_name=settings.QDRANT_COLLECTION_PLAYERS, points=points)
                total += len(points)
                logger.info(f"Vectorized {total} player logs...")
                
        finally:
            db.close()
        return total

def main():
    if not QDRANT_AVAILABLE:
        logger.error("Qdrant not installed. Cannot vectorize.")
        return
        
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2000, help="Max records to vectorize (default: 2000 for recent context)")
    args = parser.parse_args()

    vectorizer = BulkVectorizer()
    vectorizer.vectorize_games(limit=args.limit)
    vectorizer.vectorize_player_logs(limit=args.limit)
    logger.info("✅ Bulk vectorization complete!")

if __name__ == "__main__":
    main()
