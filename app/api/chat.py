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
from app.usage.throttler import enforce_cost_limit
from app.prompt.builder import PromptBuilder
import uuid

router = APIRouter()

prompt_builder = PromptBuilder()

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
    tenant_data=Depends(require_tenant_api_key),
    db: AsyncSession = Depends(get_db)
):
    tenant, api_key = tenant_data
    tenant_dict = {
        "tenant_id": tenant.id,
        "daily_cost_limit": float(api_key.daily_cost_limit_usd)
    }
    await enforce_cost_limit(tenant_dict, db)
    return tenant, api_key

# Apply rate limiting: 10 requests per 60 seconds (FINDING-005)
@router.post(
    "/",
    response_model=ChatResponse,
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(10, Duration.SECOND * 60))))]
)
async def chat(
    payload: ChatRequest,
    response: Response,
    tenant_data=Depends(check_usage),
    db: AsyncSession = Depends(get_db)
):
    tenant, api_key = tenant_data
    
    # 1. Retrieve chunks
    embedding = await get_embedding(payload.query)
    
    # Vector search using cosine distance (<=> operator in pgvector)
    # We join with chunks to get content
    query = select(KnowledgeBaseChunk).join(
        KnowledgeBaseEmbedding, KnowledgeBaseChunk.id == KnowledgeBaseEmbedding.chunk_id
    ).where(
        KnowledgeBaseEmbedding.tenant_id == tenant.id,
        KnowledgeBaseEmbedding.model == "text-embedding-3-small" # Match embedding model
    ).order_by(
        KnowledgeBaseEmbedding.embedding.cosine_distance(embedding)
    ).limit(3)
    
    result = await db.execute(query)
    chunks = result.scalars().all()
    
    # 2. Build prompt using PromptBuilder
    messages = prompt_builder.build(payload.query, chunks)

    # 3. Call LLM
    llm_completion = await get_chat_completion(messages, model="gpt-3.5-turbo")
    answer = llm_completion.choices[0].message.content
    
    # Calculate costs (approximate)
    prompt_tokens = llm_completion.usage.prompt_tokens
    completion_tokens = llm_completion.usage.completion_tokens
    total_tokens = llm_completion.usage.total_tokens
    
    # Pricing for gpt-3.5-turbo-0125: Input $0.50/1M, Output $1.50/1M
    cost_usd = (prompt_tokens * 0.50 / 1_000_000) + (completion_tokens * 1.50 / 1_000_000)
    
    # Expose cost to logging middleware
    response.headers["X-Total-Cost"] = "{:.6f}".format(cost_usd)

    # 4. Persistence
    if payload.session_id:
        session_id = payload.session_id
        # SECURITY: Verify conversation belongs to tenant (FINDING-002)
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.session_id == session_id,
                Conversation.tenant_id == tenant.id  # Prevent session hijacking
            )
        )
        conversation = conv_result.scalars().first()
        if not conversation:
             conversation = Conversation(
                tenant_id=tenant.id,
                session_id=session_id
            )
             db.add(conversation)
             await db.flush() # to get ID
    else:
        session_id = str(uuid.uuid4())
        conversation = Conversation(
            tenant_id=tenant.id,
            session_id=session_id
        )
        db.add(conversation)
        await db.flush()

    # Save Messages
    user_msg = Message(
        conversation_id=conversation.id,
        sender="user",
        text=payload.query
    )
    db.add(user_msg)
    
    bot_msg = Message(
        conversation_id=conversation.id,
        sender="assistant",
        text=answer
    )
    db.add(bot_msg)
    await db.flush()
    
    # Save Usage
    llm_usage = LLMUsage(
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        message_id=bot_msg.id,
        model="gpt-3.5-turbo",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )
    db.add(llm_usage)
    
    # Analytics
    event = AnalyticsEvent(
        tenant_id=tenant.id,
        event_type="chat_completion",
        payload={
            "conversation_id": str(conversation.id),
            "tokens": total_tokens,
            "cost": float(cost_usd)
        }
    )
    db.add(event)
    
    await db.commit()

    return ChatResponse(
        answer=answer,
        confidence=1.0, # Placeholder
        session_id=session_id
    )
