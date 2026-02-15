from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Tenant, ApiKey
from app.rate_limit.redis_rate_limiter import rate_limiter # Might be used elsewhere or kept for utility

class WidgetService:
    async def get_config(self, db: AsyncSession, tenant: Tenant, domain: str = None) -> dict:
        """
        Fetch widget configuration for a tenant.
        Priority: tenant_configs > chatbot_configs > defaults.
        Caching: Uses Redis with a 1-hour TTL.
        """
        from app.utils.redis_client import redis_client
        
        # 1. Check Cache
        cache_key = f"cache:config:{tenant.id}:{domain or 'default'}"
        cached_config = await redis_client.get_cache(cache_key)
        if cached_config:
            return cached_config

        # (If cache miss) 2. Fetch from DB
        from sqlalchemy import select, or_
        from app.db.models import TenantConfig, ChatbotConfig
        
        # ... (rest of the DB fetching logic) ...
        # [Wait, I should replace the whole function block correctly]
        
        # 2a. Fetch ChatbotConfig
        chatbot_stmt = select(ChatbotConfig).where(ChatbotConfig.tenant_id == tenant.id)
        chatbot_result = await db.execute(chatbot_stmt)
        chatbot_config = chatbot_result.scalars().first()

        # 2b. Fetch TenantConfig (prioritize matching domain, then NULL domain)
        tenant_stmt = select(TenantConfig).where(
            TenantConfig.tenant_id == tenant.id
        ).order_by(
            TenantConfig.domain.desc() # Non-NULL domains first
        )
        if domain:
            tenant_stmt = tenant_stmt.where(or_(TenantConfig.domain == domain, TenantConfig.domain == None))
        
        tenant_result = await db.execute(tenant_stmt)
        tenant_configs = tenant_result.scalars().all()
        
        # Select the best matching tenant_config
        active_tenant_config = None
        if domain:
            for tc in tenant_configs:
                if tc.domain == domain:
                    active_tenant_config = tc
                    break
        
        if not active_tenant_config and tenant_configs:
            # Fallback to default (NULL domain) or the first one
            for tc in tenant_configs:
                if tc.domain is None:
                    active_tenant_config = tc
                    break
            if not active_tenant_config:
                active_tenant_config = tenant_configs[0]

        # 3. Merge Logic
        config = {
            "tenant_id": str(tenant.id), # UUID to string for JSON
            "chat_title": getattr(chatbot_config, "name", None) or getattr(active_tenant_config, "brand_name", None) or f"Chat with {tenant.name}",
            "primary_color": getattr(chatbot_config, "primary_color", None) or getattr(active_tenant_config, "primary_color", None) or "#0ea5e9",
            "welcome_message": getattr(chatbot_config, "welcome_message", None) or getattr(active_tenant_config, "welcome_message", None) or "Hello! How can I help you?",
            "bot_name": getattr(chatbot_config, "name", None) or getattr(active_tenant_config, "brand_name", None) or f"{tenant.name} Bot",
            "logo_url": getattr(chatbot_config, "logo_url", None) or getattr(active_tenant_config, "logo_url", None),
            "suggested_questions": ["How do I get started?", "What are your pricing plans?"]
        }

        if chatbot_config:
            config["background_color"] = chatbot_config.background_color
            config["position"] = chatbot_config.position

        # 4. Save to Cache (1 hour TTL)
        await redis_client.set_cache(cache_key, config, ttl=3600)

    async def invalidate_cache(self, tenant_id: str):
        """
        Invalidate all cached widget configurations for a specific tenant.
        """
        from app.utils.redis_client import redis_client
        pattern = f"cache:config:{tenant_id}:*"
        await redis_client.delete_by_pattern(pattern)

widget_service = WidgetService()
