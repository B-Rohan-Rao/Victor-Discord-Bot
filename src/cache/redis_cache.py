"""
Redis-based cache implementation for production
Provides ultra-fast in-memory caching with TTL
"""

import json
import asyncio
from typing import Optional, Any
import redis
from src.cache.manager import BaseCacheManager
from src.config.settings import settings

REDIS_AVAILABLE = True


class RedisCache(BaseCacheManager):
    """Redis cache backend"""

    def __init__(self):
        if not REDIS_AVAILABLE:
            raise ImportError("redis package not installed. Install with: uv pip install redis")

        super().__init__()
        self.redis_client: Optional[Any] = None
        self.connection_args = {
            "host": settings.redis_host,
            "port": settings.redis_port,
            "db": settings.redis_db,
            "password": settings.redis_password if settings.redis_password else None,
            "decode_responses": True,
        }

    async def _get_client(self) -> Any:
        """Get or create Redis client"""
        if self.redis_client is None:
            self.redis_client = redis.Redis(**self.connection_args)
            # Test connection
            try:
                await asyncio.to_thread(self.redis_client.ping)
            except Exception as e:
                print(f"Redis connection failed: {e}")
                raise

        return self.redis_client

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value from Redis"""
        try:
            client = await self._get_client()
            value = await asyncio.to_thread(client.get, key)

            if value is None:
                return None

            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        except Exception as e:
            print(f"Error getting from Redis: {e}")
            return None

    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Store value in Redis with TTL"""
        ttl = ttl_seconds or self.ttl_seconds

        try:
            client = await self._get_client()
            value_str = json.dumps(value) if not isinstance(value, str) else value
            await asyncio.to_thread(client.setex, key, ttl, value_str)
            return True

        except Exception as e:
            print(f"Error setting in Redis: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from Redis"""
        try:
            client = await self._get_client()
            await asyncio.to_thread(client.delete, key)
            return True

        except Exception as e:
            print(f"Error deleting from Redis: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        try:
            client = await self._get_client()
            result = await asyncio.to_thread(client.exists, key)
            return result > 0

        except Exception as e:
            print(f"Error checking Redis: {e}")
            return False

    async def clear(self) -> bool:
        """Clear entire Redis database"""
        try:
            client = await self._get_client()
            await asyncio.to_thread(client.flushdb)
            return True

        except Exception as e:
            print(f"Error clearing Redis: {e}")
            return False

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await asyncio.to_thread(self.redis_client.close)
