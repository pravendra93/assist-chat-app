from fastapi import Header, HTTPException, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import ApiKey, Tenant, TenantConfig
from app.core.security import verify_api_key
from urllib.parse import urlparse
from app.schema import TenantOut

async def require_tenant_api_key(
    request: Request,
    asst_api_key: str = Header(..., alias="ASST-API-KEY", description="The API Key"),
    db: AsyncSession = Depends(get_db)
) -> tuple[Tenant, ApiKey]:
    """
    Validate tenant API key and return (Tenant, ApiKey).
    Also tracks first-time usage and updates last_used_at.
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

    # --- Domain Validation ---
    request_origin = request.headers.get("origin") or request.headers.get("referer")
    request_domain = None
    if request_origin:
        parsed = urlparse(request_origin)
        request_domain = parsed.hostname or request_origin
        # Strip 'www.' if present for more flexible matching
        if request_domain.startswith("www."):
            request_domain = request_domain[4:]
    
    
    # Fetch configured domains for this tenant
    config_result = await db.execute(
        select(TenantConfig).where(
            TenantConfig.tenant_id == tenant.id,
            TenantConfig.domain != None
        )
    )
    tenant_configs = config_result.scalars().all()
    configured_domains = [tc.domain.lower() for tc in tenant_configs if tc.domain]
    
    # Normalize configured domains (strip 'www.' if present)
    normalized_configured_domains = []
    for d in configured_domains:
        d_parsed = urlparse(d if "://" in d else f"https://{d}")
        d_hostname = d_parsed.hostname or d
        if d_hostname.startswith("www."):
            d_hostname = d_hostname[4:]
        normalized_configured_domains.append(d_hostname)
    
    # If no domains are configured, the user specified "allow request only to those ... which has domain"
    if not normalized_configured_domains:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

    # Check for match (case-insensitive)
    is_domain_allowed = False
    if request_domain:
        request_domain = request_domain.lower()
        if request_domain in normalized_configured_domains:
            is_domain_allowed = True
            
    if not is_domain_allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    # --- End Domain Validation ---

    # Tracking Logic
    # 1. Update last_used_at for the API Key
    api_key_record.last_used_at = func.now()

    # 2. Track first-time usage for the Tenant
    if not tenant.is_installed:
        tenant.is_installed = True
        tenant.first_api_call_at = func.now()
        # Capture the URL where the API/Widget was first called
        tenant.installation_url = request.headers.get("origin") or request.headers.get("referer")
    
    # Use flush so the updates are sent to the DB but not committed yet.
    # The route handler (which uses this dependency) will handle the commit.
    await db.flush()

    return tenant, api_key_record
