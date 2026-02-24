"""
Vector store service for managing embeddings in Qdrant.
"""
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from app.config import settings
from loguru import logger

class VectorStoreService:
    """
    Service for interacting with Qdrant vector database.
    """
    
    def __init__(self):
        # Handle cloud URL (https) vs local host
        if settings.QDRANT_HOST.startswith("http"):
            self.client = QdrantClient(
                url=settings.QDRANT_HOST, 
                api_key=settings.QDRANT_API_KEY
            )
        else:
            self.client = QdrantClient(
                host=settings.QDRANT_HOST, 
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY
            )
        # 384 dimensions for all-MiniLM-L6-v2
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        self.collection_name = settings.QDRANT_COLLECTION_GAMES
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            logger.info(f"Creating Qdrant collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=384, 
                    distance=models.Distance.COSINE
                )
            )

    def upsert_game_scenario(self, game_id: str, description: str, metadata: Dict[str, Any]):
        """
        Embed and store a game scenario.
        
        Args:
            game_id: Unique identifier for the game.
            description: Qualitative description of the scenario.
            metadata: Additional quantitative data (splits, moves, outcome).
        """
        vector = self.encoder.encode(description).tolist()
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=hash(game_id) % (2**63 - 1),  # Simple deterministic int ID
                    vector=vector,
                    payload={
                        "game_id": game_id,
                        "description": description,
                        **metadata
                    }
                )
            ]
        )
        logger.debug(f"Upserted vector for game {game_id}")

    def search_similar_scenarios(self, description: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar historical game scenarios.
        """
        vector = self.encoder.encode(description).tolist()
        
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit
        )
        
        return [hit.payload for hit in results.points]
