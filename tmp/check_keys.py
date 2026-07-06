import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import ApiKey, Tenant

async def list_keys():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiKey))
        keys = result.scalars().all()
        print(f"Total keys found: {len(keys)}")
        for k in keys:
            print(f"ID: {k.id}, Prefix: {k.key_prefix}, Active: {k.is_active}, Tenant: {k.tenant_id}")
        
        tenant_result = await session.execute(select(Tenant))
        tenants = tenant_result.scalars().all()
        print(f"Total tenants found: {len(tenants)}")
        for t in tenants:
            print(f"Tenant ID: {t.id}, Name: {t.name}")

if __name__ == "__main__":
    asyncio.run(list_keys())
