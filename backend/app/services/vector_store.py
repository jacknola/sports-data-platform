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
        self._ensure_collections()

    def _ensure_collections(self):
        """Create collections if they don't exist."""
        collections = self.client.get_collections().collections
        
        for name in [settings.QDRANT_COLLECTION_GAMES, settings.QDRANT_COLLECTION_PLAYERS]:
            exists = any(c.name == name for c in collections)
            if not exists:
                logger.info(f"Creating Qdrant collection: {name}")
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(
                        size=384, 
                        distance=models.Distance.COSINE
                    )
                )

    def upsert_game_scenario(self, game_id: str, description: str, metadata: Dict[str, Any], collection: Optional[str] = None):
        """
        Embed and store a game scenario.
        
        Args:
            game_id: Unique identifier for the game.
            description: Qualitative description of the scenario.
            metadata: Additional quantitative data.
            collection: Target collection name.
        """
        coll_name = collection or settings.QDRANT_COLLECTION_GAMES
        vector = self.encoder.encode(description).tolist()
        
        self.client.upsert(
            collection_name=coll_name,
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
        logger.debug(f"Upserted vector for {game_id} into {coll_name}")

    def search_similar_scenarios(self, description: str, limit: int = 5, collection: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar historical game scenarios.
        """
        coll_name = collection or settings.QDRANT_COLLECTION_GAMES
        vector = self.encoder.encode(description).tolist()
        
        results = self.client.query_points(
            collection_name=coll_name,
            query=vector,
            limit=limit
        )
        
        return [hit.payload for hit in results.points]
