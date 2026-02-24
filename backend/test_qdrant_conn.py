"""
Connection test for Qdrant.
"""
from qdrant_client import QdrantClient
from app.config import settings

def test_qdrant_connection():
    try:
        client = QdrantClient(host="localhost", port=6333)
        # Simple health check
        version = client.get_collections()
        print("Successfully connected to Qdrant")
        return True
    except Exception as e:
        print(f"Failed to connect to Qdrant: {e}")
        return False

if __name__ == "__main__":
    test_qdrant_connection()
