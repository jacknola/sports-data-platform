"""
Redis cache service
"""
import redis
from typing import Optional, Any
from loguru import logger

from app.config import settings


class RedisCache:
    """Redis cache singleton"""
    
    _instance: Optional['RedisCache'] = None
    _redis_client: Optional[redis.Redis] = None
    
    def __init__(self):
        if RedisCache._instance is not None:
            raise Exception("RedisCache is a singleton, use get_instance()")
        
        RedisCache._instance = self
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self._redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
            # Test connection
            self._redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._redis_client = None
    
    @classmethod
    async def get_instance(cls) -> 'RedisCache':
        """Get or create RedisCache instance"""
        if cls._instance is None:
            cls()
        return cls._instance
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._redis_client:
            return None
        
        try:
            return self._redis_client.get(key)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache"""
        if not self._redis_client:
            return
        
        try:
            self._redis_client.setex(key, ttl, str(value))
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def delete(self, key: str):
        """Delete key from cache"""
        if not self._redis_client:
            return
        
        try:
            self._redis_client.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")

    # Convenience helpers
    def get_json(self, key: str) -> Optional[Any]:
        """Get a JSON-serialized value and decode it"""
        import json
        value = self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception as e:
            logger.error(f"Cache JSON decode error for {key}: {e}")
            return None

    def set_json(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Serialize value as JSON and store it"""
        import json
        try:
            payload = json.dumps(value)
            self.set(key, payload, ttl)
        except Exception as e:
            logger.error(f"Cache JSON encode error for {key}: {e}")

    @classmethod
    def get_sync(cls) -> 'RedisCache':
        """Synchronous accessor for code paths that aren't async"""
        if cls._instance is None:
            cls()
        return cls._instance  # type: ignore[return-value]

