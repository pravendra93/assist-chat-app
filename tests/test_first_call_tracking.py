import asyncio
import uuid
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import Tenant, ApiKey
from app.auth.api_key import require_tenant_api_key
from unittest.mock import MagicMock

async def test_first_call_tracking():
    async with AsyncSessionLocal() as db:
        # 1. Create a dummy tenant and API key
        tenant_id = uuid.uuid4()
        tenant = Tenant(
            id=tenant_id, 
            name="Test Tracking Tenant",
            is_installed=False
        )
        db.add(tenant)
        
        api_key_str = f"sk_live_{uuid.uuid4().hex[:20]}"
        # Normally we'd hash the key, but for this test we'll just mock the verification
        # or use the real hashing if possible. Let's just create the record.
        api_key = ApiKey(
            tenant_id=tenant_id,
            api_key_hash="dummy_hash", # Not verifying in this test, just checking tracking
            key_prefix=api_key_str[:12],
            is_active=True
        )
        db.add(api_key)
        await db.commit()
        
        print(f"Created Test Tenant: {tenant_id}")
        
        # 2. Mock Request
        mock_request = MagicMock()
        mock_request.headers = {"origin": "http://test-site.com"}
        
        # 3. Call require_tenant_api_key (simulating the API call)
        # We need to mock verify_api_key to return True
        import app.auth.api_key as api_key_module
        original_verify = api_key_module.verify_api_key
        api_key_module.verify_api_key = lambda key, hash: True
        
        try:
            returned_tenant, returned_api_key = await require_tenant_api_key(
                request=mock_request,
                asst_api_key=api_key_str,
                db=db
            )
            
            # Since require_tenant_api_key calls db.flush(), we should see changes in returned objects
            print(f"Tracking check: is_installed={returned_tenant.is_installed}")
            print(f"Tracking check: first_api_call_at={returned_tenant.first_api_call_at}")
            print(f"Tracking check: installation_url={returned_tenant.installation_url}")
            print(f"Tracking check: last_used_at={returned_api_key.last_used_at}")
            
            assert returned_tenant.is_installed == True
            assert returned_tenant.installation_url == "http://test-site.com"
            assert returned_tenant.first_api_call_at is not None
            assert returned_api_key.last_used_at is not None
            
            print("Verification successful!")
            
        finally:
            api_key_module.verify_api_key = original_verify
            # Cleanup
            await db.execute(select(Tenant).where(Tenant.id == tenant_id)) # refresh
            await db.delete(api_key)
            await db.delete(tenant)
            await db.commit()

if __name__ == "__main__":
    asyncio.run(test_first_call_tracking())
