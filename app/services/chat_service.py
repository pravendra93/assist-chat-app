"""
app/services/chat_service.py

Core RAG pipeline: retrieve → prompt → LLM.
Now accepts PlanLimits so per-plan model, token, and chunk constraints
are applied at call time.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import (
    KnowledgeBaseChunk,
    KnowledgeBaseEmbedding,
    Conversation,
    Message,
    LLMUsage,
    AnalyticsEvent,
    Tenant,
    ApiKey,
)
from app.core.llm import get_embedding, get_chat_completion, get_chat_completion_stream
from app.prompt.builder import PromptBuilder
import uuid
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.plan_limits import PlanLimits


# Pricing table (USD per token)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {"prompt": 0.15 / 1_000_000, "completion": 0.60 / 1_000_000},
    "gpt-4o":      {"prompt": 2.50 / 1_000_000, "completion": 10.00 / 1_000_000},
    "gpt-4.1":     {"prompt": 2.00 / 1_000_000, "completion": 8.00 / 1_000_000},
    # Legacy fallback
    "gpt-3.5-turbo": {"prompt": 0.50 / 1_000_000, "completion": 1.50 / 1_000_000},
}


def _calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
    return (prompt_tokens * pricing["prompt"]) + (completion_tokens * pricing["completion"])


class ChatService:
    def __init__(self):
        self.prompt_builder = PromptBuilder()

    async def get_response(
        self,
        db: AsyncSession,
        tenant: Tenant,
        query: str,
        session_id: Optional[str] = None,
        plan_limits: Optional["PlanLimits"] = None,
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Core RAG logic: Retrieve → Prompt → LLM.

        Applies plan limits when provided:
          - max_chunks_per_query  → limits vector search results
          - max_tokens_per_request → limits LLM output tokens
          - allowed_models (first entry) → which model to call

        Returns: (answer, session_id, metadata_for_persistence)
        """
        from app.utils.redis_client import redis_client
        import hashlib

        # Resolve plan-aware settings (or safe defaults)
        if plan_limits is not None:
            max_chunks = plan_limits.model_limits.max_chunks_per_query
            max_tokens = plan_limits.model_limits.max_tokens_per_request
            model = plan_limits.model_limits.default_model
        else:
            max_chunks = 5
            max_tokens = 500
            model = "gpt-4o-mini"

        if not session_id:
            session_id = str(uuid.uuid4())

        # 0. Check Circuit Breaker
        if await redis_client.is_circuit_broken():
            from app.core.logging import logger
            logger.warning(f"Circuit Breaker active for tenant {tenant.id}. Skipping LLM.")
            fallback_answer = "Our AI service is temporarily unavailable due to capacity limits. Please try again later."
            return fallback_answer, session_id, {
                "query": query,
                "answer": fallback_answer,
                "model": model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "cached": False,
                "error": "circuit_breaker_active"
            }

        # 1. Check Cache (Full Response)
        query_hash = hashlib.md5(query.strip().lower().encode()).hexdigest()
        cache_key = f"cache:chat:{tenant.id}:{query_hash}"

        cached_res = await redis_client.get_cache(cache_key)
        if cached_res:
            persistence_data = {
                "query": query,
                "answer": cached_res["answer"],
                "model": model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "cached": True,
            }
            return cached_res["answer"], session_id, persistence_data

        try:
            from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception, retry_if_exception_type
            import openai

            def is_retryable_openai_error(e):
                """Predicate to skip retries for non-transient OpenAI errors."""
                if isinstance(e, (openai.APIConnectionError, openai.APITimeoutError)):
                    return True
                if isinstance(e, openai.RateLimitError):
                    # Do NOT retry if it's a quota issue
                    return "insufficient_quota" not in str(e).lower()
                if isinstance(e, openai.APIStatusError):
                    # Retry on 500+ errors, but not on 400s (invalid_request, auth, etc)
                    return e.status_code >= 500
                return False

            # 2. Retrieve chunks (plan-limited)
            try:
                # 2a. Check Embedding Cache
                emb_cache_key = f"cache:embedding:{query_hash}"
                cached_emb_data = await redis_client.get_cache(emb_cache_key)
                
                if cached_emb_data and "embedding" in cached_emb_data:
                    from app.core.logging import logger
                    logger.info(f"Using cached embedding for query {query_hash}")
                    embedding = cached_emb_data["embedding"]
                else:
                    @retry(
                        wait=wait_exponential(multiplier=1, min=1, max=5),
                        stop=stop_after_attempt(2),
                        retry=retry_if_exception(is_retryable_openai_error)
                    )
                    async def fetch_embedding_with_retry():
                        return await get_embedding(query)
                    
                    embedding = await fetch_embedding_with_retry()
                    # Cache embedding for 7 days
                    await redis_client.set_cache(emb_cache_key, {"embedding": embedding}, ttl=604800)

                query_stmt = (
                    select(KnowledgeBaseChunk)
                    .join(
                        KnowledgeBaseEmbedding,
                        KnowledgeBaseChunk.id == KnowledgeBaseEmbedding.chunk_id,
                    )
                    .where(
                        KnowledgeBaseEmbedding.tenant_id == tenant.id,
                        KnowledgeBaseEmbedding.model == "text-embedding-3-small",
                    )
                    .order_by(
                        KnowledgeBaseEmbedding.embedding.cosine_distance(embedding)
                    )
                    .limit(max_chunks)   # ← plan-limited
                )

                result = await db.execute(query_stmt)
                chunks = result.scalars().all()
            except Exception as e:
                from app.core.logging import logger
                logger.error(f"Retrieval Error for tenant {tenant.id}: {e}")
                
                # Check for quota error in retrieval (embeddings call)
                if "insufficient_quota" in str(e).lower():
                    await redis_client.set_str("cb:openai:quota_exceeded", "1", ttl=3600) # Break for 1 hour
                
                chunks = [] # Fallback to no context if DB fails

            # Early release: We've finished all DB reads for the RAG context.
            # Closing the session now returns the connection to the pool early
            # so it can be reused while we wait for the (relatively slow) LLM.
            await db.close()

            # --- RETRIEVAL-FIRST FLOW ---
            if not chunks:
                from app.core.logging import logger
                logger.info(f"No relevant context found for tenant {tenant.id}. Returning fallback.")
                fallback_answer = "I'm sorry, I don't have enough information to answer that based on my knowledge base."
                return fallback_answer, session_id, {
                    "query": query,
                    "answer": fallback_answer,
                    "model": model,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "cached": False,
                    "no_context": True
                }

            # 3. Build prompt
            messages = self.prompt_builder.build(query, chunks)

            # 4. Call LLM (plan-limited model & max_tokens)
            try:
                @retry(
                    wait=wait_exponential(multiplier=1, min=1, max=5),
                    stop=stop_after_attempt(2),
                    retry=retry_if_exception(is_retryable_openai_error)
                )
                async def fetch_completion_with_retry():
                    return await get_chat_completion(
                        messages,
                        model=model,
                        max_tokens=max_tokens,
                    )

                llm_completion = await fetch_completion_with_retry()
                answer = llm_completion.choices[0].message.content

                # 5. Calculate cost
                prompt_tokens = llm_completion.usage.prompt_tokens
                completion_tokens = llm_completion.usage.completion_tokens
                total_tokens = llm_completion.usage.total_tokens
                cost_usd = _calc_cost(model, prompt_tokens, completion_tokens)

                persistence_data = {
                    "query": query,
                    "answer": answer,
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_usd,
                    "cached": False,
                }

                # 6. Cache (24 h TTL)
                await redis_client.set_cache(cache_key, {"answer": answer}, ttl=86400)

                return answer, session_id, persistence_data

            except Exception as e:
                from app.core.logging import logger
                logger.error(f"LLM Error for tenant {tenant.id}: {e}")
                
                # Check for quota error to trigger circuit breaker
                if "insufficient_quota" in str(e).lower():
                    await redis_client.set_str("cb:openai:quota_exceeded", "1", ttl=3600) # Break for 1 hour
                
                raise # Re-wrap in outer catch for fallback

        except Exception as e:
            from app.core.logging import logger
            logger.error(f"ChatService Global Error for tenant {tenant.id}: {e}")

            if await redis_client.is_circuit_broken():
                 fallback_answer = "Our AI service is temporarily unavailable due to capacity limits. Please try again later."
            else:
                 fallback_answer = "I'm having trouble thinking right now. Please try again."

            persistence_data = {
                "query": query,
                "answer": fallback_answer,
                "model": model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "cached": False,
                "error": True,
            }
            return fallback_answer, session_id, persistence_data

    async def persist_response(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        session_id: str,
        data: Dict[str, Any],
    ):
        """
        Save conversation history, usage, and analytics to the database.
        Designed to be run as a background task.
        """
        # 1. Handle Conversation
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.session_id == session_id,
                Conversation.tenant_id == tenant_id,
            )
        )
        conversation = conv_result.scalars().first()
        if not conversation:
            conversation = Conversation(tenant_id=tenant_id, session_id=session_id)
            db.add(conversation)
            await db.flush()

        # 2. Save Messages
        user_msg = Message(
            conversation_id=conversation.id,
            sender="user",
            text=data["query"],
        )
        db.add(user_msg)

        bot_msg = Message(
            conversation_id=conversation.id,
            sender="assistant",
            text=data["answer"],
        )
        db.add(bot_msg)
        await db.flush()

        # 3. Save Usage (record actual model used)
        llm_usage = LLMUsage(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            message_id=bot_msg.id,
            model=data.get("model", "gpt-4o-mini"),
            prompt_tokens=data["prompt_tokens"],
            completion_tokens=data["completion_tokens"],
            total_tokens=data["total_tokens"],
            cost_usd=data["cost_usd"],
        )
        db.add(llm_usage)

        # 4. Analytics
        event = AnalyticsEvent(
            tenant_id=tenant_id,
            event_type="chat_completion",
            payload={
                "conversation_id": str(conversation.id),
                "tokens": data["total_tokens"],
                "cost": float(data["cost_usd"]),
                "model": data.get("model", "gpt-4o-mini"),
            },
        )
        db.add(event)

        await db.commit()


    async def get_streaming_response(
        self,
        db: AsyncSession,
        tenant: Tenant,
        query: str,
        session_id: Optional[str] = None,
        plan_limits: Optional["PlanLimits"] = None,
    ):
        """
        Streaming version of the RAG pipeline.
        Yields tokens and handles background persistence.
        """
        from app.utils.redis_client import redis_client
        import hashlib
        import json

        if not session_id:
            session_id = str(uuid.uuid4())

        # 0. Check Circuit Breaker
        if await redis_client.is_circuit_broken():
            from app.core.logging import logger
            logger.warning(f"Circuit Breaker active for tenant {tenant.id}. Skipping Streaming LLM.")
            yield "Our AI service is temporarily unavailable due to capacity limits. Please try again later."
            return

        # 1. Retrieve chunks
        try:
            from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
            import openai

            def is_retryable_openai_error(e):
                """Predicate to skip retries for non-transient OpenAI errors."""
                if isinstance(e, (openai.APIConnectionError, openai.APITimeoutError)):
                    return True
                if isinstance(e, openai.RateLimitError):
                    return "insufficient_quota" not in str(e).lower()
                if isinstance(e, openai.APIStatusError):
                    return e.status_code >= 500
                return False

            query_hash = hashlib.md5(query.strip().lower().encode()).hexdigest()
            emb_cache_key = f"cache:embedding:{query_hash}"
            cached_emb_data = await redis_client.get_cache(emb_cache_key)

            if cached_emb_data and "embedding" in cached_emb_data:
                from app.core.logging import logger
                logger.info(f"Using cached embedding for streaming query {query_hash}")
                embedding = cached_emb_data["embedding"]
            else:
                @retry(
                    wait=wait_exponential(multiplier=1, min=1, max=5),
                    stop=stop_after_attempt(2),
                    retry=retry_if_exception(is_retryable_openai_error)
                )
                async def fetch_embedding_with_retry():
                    return await get_embedding(query)
                
                embedding = await fetch_embedding_with_retry()
                await redis_client.set_cache(emb_cache_key, {"embedding": embedding}, ttl=604800)

            query_stmt = (
                select(KnowledgeBaseChunk)
                .join(
                    KnowledgeBaseEmbedding,
                    KnowledgeBaseChunk.id == KnowledgeBaseEmbedding.chunk_id,
                )
                .where(
                    KnowledgeBaseEmbedding.tenant_id == tenant.id,
                    KnowledgeBaseEmbedding.model == "text-embedding-3-small",
                )
                .order_by(
                    KnowledgeBaseEmbedding.embedding.cosine_distance(embedding)
                )
                .limit(max_chunks)
            )
            result = await db.execute(query_stmt)
            chunks = result.scalars().all()
        except Exception as e:
            from app.core.logging import logger
            logger.error(f"Streaming Retrieval Error for tenant {tenant.id}: {e}")
            if "insufficient_quota" in str(e).lower():
                await redis_client.set_str("cb:openai:quota_exceeded", "1", ttl=3600)
            chunks = []
            
        await db.close()

        # --- RETRIEVAL-FIRST FLOW (Streaming) ---
        if not chunks:
            from app.core.logging import logger
            logger.info(f"No context found for tenant {tenant.id} in streaming request. Returning fallback.")
            yield "I'm sorry, I don't have enough information to answer that based on my knowledge base."
            return

        # 2. Build prompt
        messages = self.prompt_builder.build(query, chunks)

        # 3. Call Streaming LLM
        try:
            stream = await get_chat_completion_stream(
                messages,
                model=model,
                max_tokens=max_tokens,
            )
        except Exception as e:
            from app.core.logging import logger
            logger.error(f"Streaming LLM Error for tenant {tenant.id}: {e}")
            if "insufficient_quota" in str(e).lower():
                await redis_client.set_str("cb:openai:quota_exceeded", "1", ttl=3600)
            yield "I'm having trouble thinking right now. Please try again."
            return

        full_answer = []
        usage_data = None

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_answer.append(content)
                yield content
            
            if hasattr(chunk, 'usage') and chunk.usage:
                usage_data = chunk.usage

        # 4. Persistence & Cleanup (Post-stream)
        answer_str = "".join(full_answer)
        
        # Calculate cost if usage_data is available
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        cost_usd = 0.0
        
        if usage_data:
            prompt_tokens = usage_data.prompt_tokens
            completion_tokens = usage_data.completion_tokens
            total_tokens = usage_data.total_tokens
            cost_usd = _calc_cost(model, prompt_tokens, completion_tokens)

        persistence_data = {
            "query": query,
            "answer": answer_str,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "cached": False,
        }

        # Schedule background persistence
        from app.tasks.background import persist_chat_response
        persist_chat_response.delay(
            tenant_id_str=str(tenant.id),
            session_id=session_id,
            data=persistence_data,
        )

        # Cache the result
        query_hash = hashlib.md5(query.strip().lower().encode()).hexdigest()
        cache_key = f"cache:chat:{tenant.id}:{query_hash}"
        await redis_client.set_cache(cache_key, {"answer": answer_str}, ttl=86400)


chat_service = ChatService()
