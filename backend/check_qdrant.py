from app.services.vector_store import VectorStoreService
from app.config import settings
from loguru import logger

def check():
    vs = VectorStoreService()
    try:
        count = vs.client.count(collection_name=settings.QDRANT_COLLECTION_GAMES).count
        print(f"Games Collection ('{settings.QDRANT_COLLECTION_GAMES}') Count: {count}")
    except Exception as e:
        print(f"Error counting games: {e}")

    try:
        count = vs.client.count(collection_name=settings.QDRANT_COLLECTION_PLAYERS).count
        print(f"Players Collection ('{settings.QDRANT_COLLECTION_PLAYERS}') Count: {count}")
    except Exception as e:
        print(f"Error counting players: {e}")

if __name__ == "__main__":
    check()
