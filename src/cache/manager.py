"""
Cache manager - Abstract interface for cache operations
Uses Redis for fast cache and MongoDB as backing store
"""

from abc import ABC, abstractmethod
from typing import Optional, Any
import hashlib
from src.config.settings import settings


class BaseCacheManager(ABC):
    """Abstract base class for cache managers"""

    def __init__(self, ttl_seconds: Optional[int] = None):
        self.ttl_seconds = ttl_seconds or settings.cache_ttl

    @staticmethod
    def generate_hash_key(query: str) -> str:
        """Generate a consistent hash key for a query"""
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Store value in cache with TTL"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """Clear entire cache"""
        pass


class CacheManager:
    """
    Two-layer cache manager:
    - Redis: primary low-latency cache with TTL
    - MongoDB: persistent backing store for recovery and history
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize Redis and MongoDB clients."""
        from src.cache.redis_cache import RedisCache
        from src.cache.mongodb_store import MongoStore

        self.redis = RedisCache()
        self.mongo = MongoStore()

    async def get(self, query: str) -> Optional[Any]:
        """Get result from Redis, then fall back to MongoDB if needed."""
        key = BaseCacheManager.generate_hash_key(query)

        redis_value = await self.redis.get(key)
        if redis_value is not None:
            return redis_value

        mongo_value = await self.mongo.get_recent(query, settings.cache_ttl)
        if mongo_value is not None:
            # Warm Redis after MongoDB recovery hit.
            await self.redis.set(key, mongo_value, settings.cache_ttl)
        return mongo_value

    async def set(self, query: str, result: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Write-through set to Redis cache and MongoDB store."""
        key = BaseCacheManager.generate_hash_key(query)
        ttl = ttl_seconds or settings.cache_ttl

        redis_ok = await self.redis.set(key, result, ttl)
        mongo_ok = await self.mongo.save(query, result)

        return redis_ok or mongo_ok

    async def delete(self, query: str) -> bool:
        """Delete cached result from Redis."""
        key = BaseCacheManager.generate_hash_key(query)
        return await self.redis.delete(key)

    async def exists(self, query: str) -> bool:
        """Check if query result exists in Redis or recent MongoDB records."""
        key = BaseCacheManager.generate_hash_key(query)
        if await self.redis.exists(key):
            return True
        return await self.mongo.get_recent(query, settings.cache_ttl) is not None

    async def clear(self) -> bool:
        """Clear Redis cache (does not delete historical MongoDB records)."""
        return await self.redis.clear()
