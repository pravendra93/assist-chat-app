from fastapi import APIRouter, Depends, Request, Response, BackgroundTasks
from pyrate_limiter import Duration, Limiter, Rate
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.chat import require_tenant_api_key, check_usage
from app.db.session import get_db
from app.schemas.widget import WidgetConfigResponse, WidgetChatRequest, WidgetChatResponse
from app.services.chat_service import chat_service
from app.services.widget_service import widget_service
from app.middleware.anti_abuse import validate_domain_whitelist
from app.db.models import Tenant, ApiKey

router = APIRouter()

@router.get(
    "/config",
    response_model=WidgetConfigResponse,
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(20, Duration.SECOND * 60))))]
)
async def get_widget_config(
    request: Request,
    auth_data: tuple[Tenant, ApiKey] = Depends(require_tenant_api_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch widget configuration for the tenant associated with the API key.
    Includes domain whitelist validation and dynamic config fetching.
    """
    tenant, api_key = auth_data
    
    # Extract domain for specific configuration
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    target_url = origin or referer
    domain = None
    if target_url:
        from urllib.parse import urlparse
        domain = urlparse(target_url).netloc

    # Domain whitelist check
    whitelisted_domains = getattr(tenant, "whitelisted_domains", None)
    await validate_domain_whitelist(request, whitelisted_domains)
    
    config = await widget_service.get_config(db=db, tenant=tenant, domain=domain)
    return config

@router.post(
    "/chat",
    response_model=WidgetChatResponse,
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(10, Duration.SECOND * 60))))]
)
async def widget_chat(
    request: Request,
    response: Response,
    chat_req: WidgetChatRequest,
    background_tasks: BackgroundTasks,
    tenant_data: tuple[Tenant, ApiKey] = Depends(check_usage),
    db: AsyncSession = Depends(get_db)
):
    """
    Process a chat message from the widget using the shared RAG logic.
    Includes budget enforcement (via check_usage) and domain whitelist.
    """
    tenant, api_key = tenant_data
    
    # 1. Domain whitelist check
    whitelisted_domains = getattr(tenant, "whitelisted_domains", None)
    await validate_domain_whitelist(request, whitelisted_domains)
    
    # 2. Use the shared ChatService for communication
    answer, session_id, persistence_data = await chat_service.get_response(
        db=db,
        tenant=tenant,
        query=chat_req.message,
        session_id=chat_req.session_id
    )
    
    # 3. Schedule persistence in the background
    background_tasks.add_task(
        chat_service.persist_response,
        db=db,
        tenant_id=tenant.id,
        session_id=session_id,
        data=persistence_data
    )
    
    # 4. Expose cost to logging middleware
    response.headers["X-Total-Cost"] = "{:.6f}".format(persistence_data["cost_usd"])
    
    return WidgetChatResponse(
        answer=answer,
        session_id=session_id
    )
