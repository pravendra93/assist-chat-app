import time
from typing import Optional
from app.utils.redis_client import redis_client
from app.core.logging import logger

class WidgetRateLimiter:
    def __init__(self):
        pass

    async def is_rate_limited(self, tenant_id: str, limit: int = 60) -> bool:
        """
        Check if a tenant is rate limited (requests per minute).
        """
        redis = await redis_client.get_client()
        if not redis:
            return False  # Fail open if Redis is down, or handle accordingly
            
        key = f"rate_limit:{tenant_id}:{int(time.time() / 60)}"
        try:
            current_count = await redis.incr(key)
            if current_count == 1:
                await redis.expire(key, 60)
            
            return current_count > limit
        except Exception as e:
            logger.error(f"Error in rate limiter: {e}")
            return False

    async def is_cost_throttled(self, tenant_id: str, daily_limit: float) -> bool:
        """
        Check if a tenant has exceeded their daily cost limit.
        """
        redis = await redis_client.get_client()
        if not redis:
            return False
            
        today = time.strftime("%Y-%m-%d")
        key = f"cost_throttle:{tenant_id}:{today}"
        
        try:
            current_cost = await redis.get(key)
            if current_cost and float(current_cost) >= daily_limit:
                return True
            return False
        except Exception as e:
            logger.error(f"Error in cost throttler: {e}")
            return False

    async def track_cost(self, tenant_id: str, cost: float):
        """
        Increment the daily cost for a tenant.
        """
        redis = await redis_client.get_client()
        if not redis:
            return
            
        today = time.strftime("%Y-%m-%d")
        key = f"cost_throttle:{tenant_id}:{today}"
        
        try:
            await redis.incrbyfloat(key, cost)
            await redis.expire(key, 86400)  # 24 hours
        except Exception as e:
            logger.error(f"Error tracking cost: {e}")

rate_limiter = WidgetRateLimiter()
