from fastapi import APIRouter, HTTPException, Query, Header, status
from app.services.widget_service import widget_service
from app.core.logging import logger
from app.core.config import settings

router = APIRouter()

@router.post("/cache-invalidate")
async def invalidate_widget_cache(
    tenant_id: str = Query(..., description="The UUID of the tenant whose cache should be invalidated"),
    internal_cache_header: str = Header(..., alias="INTERNAL_CACHE_HEADER")
):
    """
    Internal endpoint to clear the widget configuration cache for a tenant.
    This should be called by the management server when settings are updated.
    """
    if not settings.INTERNAL_CACHE_HEADER or internal_cache_header != settings.INTERNAL_CACHE_HEADER:
        logger.warning(f"Unauthorized cache invalidation attempt for tenant {tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )
    try:
        await widget_service.invalidate_cache(tenant_id)
        logger.info(f"Internal cache invalidation triggered for tenant {tenant_id}")
        return {"status": "success", "message": f"Cache invalidated for tenant {tenant_id}"}
    except Exception as e:
        logger.error(f"Failed to invalidate cache for tenant {tenant_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during cache invalidation")
