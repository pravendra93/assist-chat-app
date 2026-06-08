from fastapi import Request, HTTPException, status
from typing import List, Optional
from app.core.logging import logger

async def validate_domain_whitelist(request: Request, whitelisted_domains: Optional[List[str]]):
    """
    Validate that the request Origin or Referer is in the whitelisted domains.
    """
    if not whitelisted_domains:
        # If no whitelist is defined, allow all (or change to block all if preferred)
        return

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    
    # Simple check: extract host from origin or referer
    target = origin or referer
    if not target:
        # Might be a direct server-to-server call or non-browser request
        # For widget, we expect an origin/referer
        logger.warning(f"Request missing Origin/Referer header for domain validation")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Domain not whitelisted"
        )

    # Basic domain check logic
    from urllib.parse import urlparse
    target_host = urlparse(target).netloc or urlparse(target).path
    target_host = target_host.split(":")[0].lower()

    is_whitelisted = False
    for domain in whitelisted_domains:
        domain = domain.strip().lower()
        if target_host == domain or target_host.endswith("." + domain):
            is_whitelisted = True
            break
            
    if not is_whitelisted:
        logger.warning(f"Domain validation failed for target '{target}' (resolved host: '{target_host}')")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Domain not whitelisted"
        )
