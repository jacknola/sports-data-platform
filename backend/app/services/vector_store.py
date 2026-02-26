"""
Vector store service for managing embeddings in Qdrant.
"""
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from app.config import settings
from loguru import logger

class VectorStoreService:
    def __init__(self):
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
        self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
        self._ensure_collections()

    def _ensure_collections(self):
        """Create collections and required payload indexes."""
        collections = self.client.get_collections().collections
        
        target_collections = [settings.QDRANT_COLLECTION_GAMES, settings.QDRANT_COLLECTION_PLAYERS]
        
        for name in target_collections:
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
                
                # FIX: Automatically create the index for player_name to avoid 400 errors
                if name == settings.QDRANT_COLLECTION_PLAYERS:
                    self.client.create_payload_index(
                        collection_name=name,
                        field_name="player_name",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    logger.success(f"Created 'player_name' index for {name}")

    def upsert_game_scenario(self, game_id: str, description: str, metadata: Dict[str, Any], collection: Optional[str] = None):
        """Stores a game scenario using a stable UUID based on game_id."""
        coll_name = collection or settings.QDRANT_COLLECTION_GAMES
        vector = self.encoder.encode(description).tolist()
        
        # FIX: Use a stable UUID to prevent duplicates across different script runs
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(game_id)))
        
        self.client.upsert(
            collection_name=coll_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "game_id": game_id,
                        "description": description,
                        **metadata
                    }
                )
            ]
        )