from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pyrate_limiter import Duration, Limiter, Rate
from fastapi_limiter.depends import RateLimiter
from app.auth.api_key import require_tenant_api_key
from app.db.session import get_db
from app.db.models import KnowledgeBaseChunk, KnowledgeBaseEmbedding, Conversation, Message, LLMUsage, AnalyticsEvent
from app.core.llm import get_embedding, get_chat_completion
from app.core.plan_limits import get_plan_limits, PlanLimits
from app.usage.throttler import enforce_plan_limits
from app.prompt.builder import PromptBuilder
from app.tasks.background import persist_chat_response
from typing import Tuple
import uuid

from app.services.chat_service import chat_service
from app.db.models import Tenant, ApiKey

router = APIRouter()

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000, description="User query")
    session_id: str | None = None
    
    @validator('query')
    def validate_query(cls, v):
        if len(v.strip()) == 0:
            raise ValueError("Query cannot be empty")
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        estimated_tokens = len(v) / 4
        if estimated_tokens > 1000:
            raise ValueError("Query too long (max 1000 tokens)")
        return v.strip()

class ChatResponse(BaseModel):
    answer: str
    confidence: float | None = None
    session_id: str

async def check_usage(
    tenant_data: Tuple[Tenant, ApiKey] = Depends(require_tenant_api_key),
    db: AsyncSession = Depends(get_db),
) -> Tuple[Tenant, ApiKey, PlanLimits]:
    """
    Dependency that:
    1. Loads plan limits from Plan.features for this tenant
    2. Enforces trial expiry, daily/monthly spend, and daily request limits
    3. Returns (tenant, api_key, plan_limits) for downstream use
    """
    tenant, api_key = tenant_data

    # Load plan limits
    plan_limits = await get_plan_limits(tenant, db)

    # Enforce all plan-level gates
    await enforce_plan_limits(tenant, plan_limits, db)

    return tenant, api_key, plan_limits

# Apply rate limiting: 10 requests per 60 seconds
@router.post(
    "/",
    response_model=ChatResponse,
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(10, Duration.SECOND * 60))))],
)
async def chat(
    payload: ChatRequest,
    response: Response,
    tenant_data: Tuple[Tenant, ApiKey, PlanLimits] = Depends(check_usage),
    db: AsyncSession = Depends(get_db),
):
    tenant, api_key, plan_limits = tenant_data

    answer, session_id, persistence_data = await chat_service.get_response(
        db=db,
        tenant=tenant,
        query=payload.query,
        session_id=payload.session_id,
        plan_limits=plan_limits,
    )

    # Schedule persistence in the background via Celery
    persist_chat_response.delay(
        tenant_id_str=str(tenant.id),
        session_id=session_id,
        data=persistence_data,
    )

    # Expose cost to logging middleware
    response.headers["X-Total-Cost"] = "{:.6f}".format(persistence_data["cost_usd"])

    return ChatResponse(
        answer=answer,
        confidence=1.0,  # Placeholder
        session_id=session_id,
    )
