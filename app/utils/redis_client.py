import redis.asyncio as redis
from typing import Optional
from app.core.config import settings
from app.core.logging import logger

class RedisClient:
    _instance = None
    _redis = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
        return cls._instance

    async def connect(self):
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self._redis.ping()
                logger.info("Successfully connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._redis = None
        return self._redis

    async def get_client(self) -> redis.Redis:
        if self._redis is None:
            await self.connect()
        return self._redis

    async def close(self):
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Redis connection closed")

    async def set_cache(self, key: str, value: dict, ttl: int = 3600):
        """
        Store a dictionary in Redis as a JSON string with a TTL.
        """
        client = await self.get_client()
        if client:
            try:
                import json
                await client.set(key, json.dumps(value), ex=ttl)
            except Exception as e:
                logger.error(f"Error setting Redis cache for key {key}: {e}")

    async def get_cache(self, key: str) -> Optional[dict]:
        """
        Retrieve a JSON string from Redis and return it as a dictionary.
        """
        client = await self.get_client()
        if client:
            try:
                import json
                data = await client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.error(f"Error getting Redis cache for key {key}: {e}")
        return None

    async def delete_by_pattern(self, pattern: str):
        """
        Delete all keys matching the given pattern.
        """
        client = await self.get_client()
        if client:
            try:
                # Use SCAN to find keys instead of KEYS (more performance-friendly for large DBs)
                cursor = 0
                while True:
                    cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
                    if keys:
                        await client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.error(f"Error deleting Redis keys with pattern {pattern}: {e}")

redis_client = RedisClient()
