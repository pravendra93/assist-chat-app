from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.usage.throttler import enforce_cost_limit

class Tenant:
    def __init__(self, id: str, daily_cost_limit: float):
        self.id = id
        self.daily_cost_limit = daily_cost_limit

async def require_tenant_api_key(
    x_api_key: str = Header(..., alias="x-api-key"),
    db: AsyncSession = Depends(get_db)
) -> Tenant:
    """
    Validate tenant API key, check subscription, and enforce limits.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Missing API key"
        )

    # 1. Lookup tenant and subscription
    # We assume tables: tenant_api_keys, tenants, subscriptions
    # And columns: key, tenant_id, id, daily_cost_limit, status
    query = text("""
        SELECT t.id, t.daily_cost_limit, s.status
        FROM tenant_api_keys k
        JOIN tenants t ON k.tenant_id = t.id
        LEFT JOIN subscriptions s ON t.id = s.tenant_id
        WHERE k.key = :api_key
    """)
    
    result = await db.execute(query, {"api_key": x_api_key})
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid API key"
        )
    
    tenant_id, daily_limit, sub_status = row

    # 2. Check subscription status (if required)
    # Assuming 'active' or 'trialing' are valid. Adjust as needed.
    valid_statuses = ["active", "trialing"]
    if sub_status not in valid_statuses:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Subscription inactive (status: {sub_status})"
        )

    tenant = Tenant(id=str(tenant_id), daily_cost_limit=float(daily_limit or 0.0))

    # 3. Check limits
    # enforce_cost_limit expects tenant dict currently, we need to fix that or pass dict
    # We will update enforce_cost_limit to accept Tenant object.
    await enforce_cost_limit(tenant, db)

    return tenant
