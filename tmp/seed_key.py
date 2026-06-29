import asyncio
import os
from sqlalchemy import select
from app.db.session import AsyncSessionLocal, engine
from app.db.models import ApiKey, Tenant, TenantConfig, ChatbotConfig
from app.core.security import hash_api_key

async def seed_test_key():
    async with AsyncSessionLocal() as session:
        # Check if the key already exists
        full_key = "sk_live_0CB_E4vbs9mpCRsfA19lBctmuy8Aj2hD"
        prefix = full_key[:12]
        
        result = await session.execute(select(ApiKey).where(ApiKey.key_prefix == prefix))
        existing_key = result.scalars().first()
        
        if existing_key:
            print(f"Key with prefix {prefix} already exists for tenant {existing_key.tenant_id}")
            return

        # Create a test tenant
        tenant = Tenant(
            name="Test Local Tenant",
            is_active=True
        )
        session.add(tenant)
        await session.flush()
        
        # Create the API key
        new_key = ApiKey(
            tenant_id=tenant.id,
            key_prefix=prefix,
            api_key_hash=hash_api_key(full_key),
            is_active=True,
            name="Default Local Key"
        )
        session.add(new_key)
        
        # Create a default chatbot config
        bot_config = ChatbotConfig(
            tenant_id=tenant.id,
            name="RaKri AI Assistant",
            welcome_message="Hello! I am your test assistant. How can I help you today?",
            primary_color="#6366f1"
        )
        session.add(bot_config)
        
        await session.commit()
        print(f"Successfully seeded test tenant ({tenant.id}) and API key '{full_key}'")

if __name__ == "__main__":
    if not os.getenv("DATABASE_URL"):
        print("Error: DATABASE_URL not set")
    else:
        asyncio.run(seed_test_key())
