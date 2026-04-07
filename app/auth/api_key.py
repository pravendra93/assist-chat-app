from fastapi import Header, HTTPException, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import ApiKey, Tenant, TenantConfig
from app.core.security import verify_api_key
from urllib.parse import urlparse
from app.schema import TenantOut
from app.core.config import settings

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
            detail="Authentication failed",
            headers={"X-Auth-Error": "AUTH_01"}
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
            detail="Authentication failed",
            headers={"X-Auth-Error": "AUTH_02"}
        )
        
    # Get the Tenant (with eager loading to avoid N+1)
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == api_key_record.tenant_id)
    )
    tenant = tenant_result.scalars().first()
    
    if not tenant or not api_key_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"X-Auth-Error": "AUTH_03"}
        )

    # --- Domain Validation ---
    request_origin = request.headers.get("origin") or request.headers.get("referer")
    
    # Internal portal domains that bypass tenant-specific domain validation
    PORTAL_DOMAINS = settings.PORTAL_DOMAINS
    
    request_domain = None
    is_portal_request = False
    
    if request_origin:
        parsed = urlparse(request_origin)
        # Check if the request is coming from one of our portal domains
        netloc = (parsed.netloc or parsed.path).lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        
        if netloc in PORTAL_DOMAINS:
            is_portal_request = True
            
        # Extract hostname for tenant-specific configuration matching
        request_domain = parsed.hostname or request_origin
        if request_domain.startswith("www."):
            request_domain = request_domain[4:]
    
    # If it's a request from our portal, we skip the dynamic domain validation
    if not is_portal_request:
        # DETECT NON-BROWSER CLIENTS (Mitigation for FINDING-002)
        # Since the API key for the widget is public, any non-browser client 
        # (scripts/curl) can use it by spoofing the Origin header.
        # We add a basic check for common browser strings in the User-Agent.
        user_agent = request.headers.get("user-agent", "").lower()
        is_likely_browser = any(b in user_agent for b in ["mozilla", "chrome", "safari", "firefox", "edge"])
        
        # If the request domain is provided but isn't from a browser, 
        # it's a higher risk of intent to bypass whitelisting.
        # Note: Some real users might use obscure browsers, so we log but allow for now,
        # or we could be more strict if abuse is detected.
        if not is_likely_browser:
             from app.core.logging import logger
             logger.warning(
                 "potential_origin_spoofing",
                 tenant_id=str(tenant.id),
                 user_agent=user_agent,
                 origin=request_origin
             )
             # In a production environment with high abuse, we might block this:
             # raise HTTPException(status_code=403, detail="Access denied for non-browser clients")

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
                detail="Authentication failed",
                headers={"X-Auth-Error": "AUTH_04"}
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
                detail="Authentication failed",
                headers={"X-Auth-Error": "AUTH_05"}
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
        tenant.installation_url = request_origin
    
    # Use flush so the updates are sent to the DB but not committed yet.
    # The route handler (which uses this dependency) will handle the commit.
    await db.flush()

    return tenant, api_key_record
