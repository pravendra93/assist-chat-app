from fastapi import APIRouter, Depends, Request, Response, HTTPException
from pyrate_limiter import Duration, Limiter, Rate
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.chat import check_usage
from app.db.session import get_db
from app.schemas.widget import WidgetConfigResponse, WidgetChatRequest, WidgetChatResponse
from app.services.chat_service import chat_service
from app.services.widget_service import widget_service
from app.middleware.anti_abuse import validate_domain_whitelist
from app.db.models import Tenant, ApiKey
from app.tasks.background import persist_chat_response
from app.core.plan_limits import PlanLimits
from typing import Tuple, Optional
import uuid

router = APIRouter()

@router.get(
    "/config",
    response_model=WidgetConfigResponse,
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(20, Duration.SECOND * 60))))],
)
async def get_widget_config(
    request: Request,
    auth_data: Tuple[Tenant, ApiKey, PlanLimits] = Depends(check_usage),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch widget configuration for the tenant associated with the API key.
    Includes domain whitelist validation and dynamic config fetching.
    """
    tenant, api_key, plan_limits = auth_data

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


@router.get("/init-by-key")
async def init_by_key(
    key: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Lookup tenant_id by API key (used by portal for initialization).
    This handles both full keys and masked keys (sk_live_... form).
    """
    if not key:
        raise HTTPException(status_code=400, detail="API key is required")
    
    # Try finding exact match first
    from app.core.security import verify_api_key
    
    # Prefix lookup
    key_prefix = key[:12] if len(key) >= 12 else key
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix,
            ApiKey.is_active == True
        )
    )
    keys = list(result.scalars().all())
    
    api_key_record = None
    if key.endswith("..."):
        # Masked key - if we found a match by prefix, it's enough for init
        if keys:
            api_key_record = keys[0]
    else:
        # Full key - verify hash
        for k in keys:
            if verify_api_key(key, k.api_key_hash):
                api_key_record = k
                break
                
    if not api_key_record:
        # Fallback to all keys if prefix didn't match (for older keys)
        if not key.endswith("..."):
            fallback_result = await db.execute(
                select(ApiKey).where(ApiKey.is_active == True)
            )
            all_keys = fallback_result.scalars().all()
            for k in all_keys:
                if verify_api_key(key, k.api_key_hash):
                    api_key_record = k
                    break

    if not api_key_record:
        raise HTTPException(status_code=401, detail="Invalid API key")
        
    return {"tenant_id": str(api_key_record.tenant_id)}


@router.post(
    "/chat",
    response_model=WidgetChatResponse,
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(10, Duration.SECOND * 60))))],
)
async def widget_chat(
    request: Request,
    response: Response,
    chat_req: WidgetChatRequest,
    tenant_data: Tuple[Tenant, ApiKey, PlanLimits] = Depends(check_usage),
    db: AsyncSession = Depends(get_db),
):
    """
    Process a chat message from the widget using the shared RAG logic.
    Includes plan limit enforcement (via check_usage) and domain whitelist.
    """
    tenant, api_key, plan_limits = tenant_data

    # 1. Domain whitelist check
    whitelisted_domains = getattr(tenant, "whitelisted_domains", None)
    await validate_domain_whitelist(request, whitelisted_domains)

    # 2. Use the shared ChatService for communication (plan limits applied)
    answer, session_id, persistence_data = await chat_service.get_response(
        db=db,
        tenant=tenant,
        query=chat_req.text,
        session_id=chat_req.session_id,
        plan_limits=plan_limits,
    )

    # 3. Schedule persistence in the background via Celery
    persist_chat_response.delay(
        tenant_id_str=str(tenant.id),
        session_id=session_id,
        data=persistence_data,
    )

    # 4. Expose cost to logging middleware
    response.headers["X-Total-Cost"] = "{:.6f}".format(persistence_data["cost_usd"])

    return WidgetChatResponse(
        answer=answer,
        session_id=session_id,
    )

@router.get("/test")
async def test_widget_router():
    return {"status": "active", "router": "widget"}


@router.post("/chat-stream")
async def widget_chat_stream(
    request: Request,
    chat_req: WidgetChatRequest,
    tenant_data: Tuple[Tenant, ApiKey, PlanLimits] = Depends(check_usage),
    db: AsyncSession = Depends(get_db),
):
    """
    Streaming version of the widget chat.
    Uses Server-Sent Events (SSE) but as a raw stream for the widget.js.
    """
    from fastapi.responses import StreamingResponse
    tenant, api_key, plan_limits = tenant_data

    # 1. Domain whitelist check
    whitelisted_domains = getattr(tenant, "whitelisted_domains", None)
    await validate_domain_whitelist(request, whitelisted_domains)

    # 2. Return StreamingResponse
    async def stream_generator():
        # First yield the session_id so the frontend can save it
        # We wrap it in a special marker [SESSION_ID:...]
        session_id = chat_req.session_id or str(uuid.uuid4())
        yield f"[SESSION_ID:{session_id}]"

        async for token in chat_service.get_streaming_response(
            db=db,
            tenant=tenant,
            query=chat_req.text,
            session_id=session_id,
            plan_limits=plan_limits,
        ):
            yield token

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
