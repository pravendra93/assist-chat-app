import redis.asyncio as redis
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

redis_client = RedisClient()
