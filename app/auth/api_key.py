from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import ApiKey, Tenant
from app.core.security import verify_api_key
from app.schema import TenantOut

async def require_tenant_api_key(
    asst_api_key: str = Header(..., alias="ASST-API-Key", description="The API Key"),
    db: AsyncSession = Depends(get_db)
) -> tuple[TenantOut, ApiKey]:
    """
    Validate tenant API key and return (Tenant, ApiKey)
    """
    if not asst_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    
    # Extract key prefix for efficient lookup (first 12 chars, e.g., "sk_live_abc1")
    # This allows us to use an indexed column instead of fetching all keys
    key_prefix = asst_api_key[:12] if len(asst_api_key) >= 12 else asst_api_key
    
    # Lookup API Keys by prefix (much more efficient than fetching all)
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix,
            ApiKey.is_active == True
        )
    )
    api_keys = result.scalars().all()
    
    # Verify hash for matching prefix keys
    api_key_record = None
    for key in api_keys:
        if verify_api_key(asst_api_key, key.api_key_hash):
            api_key_record = key
            break
    
    # Generic error message to prevent enumeration (FINDING-010)
    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
        
    # Get the Tenant (with eager loading to avoid N+1)
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == api_key_record.tenant_id)
    )
    tenant = tenant_result.scalars().first()
    
    if not tenant or not api_key_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

    return tenant, api_key_record
