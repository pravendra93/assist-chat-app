from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import KnowledgeBaseChunk, KnowledgeBaseEmbedding, Conversation, Message, LLMUsage, AnalyticsEvent, Tenant, ApiKey
from app.core.llm import get_embedding, get_chat_completion
from app.prompt.builder import PromptBuilder
import uuid
from typing import Optional, Tuple, Dict, Any

class ChatService:
    def __init__(self):
        self.prompt_builder = PromptBuilder()

    async def get_response(
        self,
        db: AsyncSession,
        tenant: Tenant,
        query: str,
        session_id: Optional[str] = None
    ) -> Tuple[str, str, float]:
        """
        Core RAG logic: Retrieve, Prompt, Call LLM, Persist.
        Returns: (answer, session_id, cost_usd)
        """
        
        # 1. Retrieve chunks
        embedding = await get_embedding(query)
        
        # Vector search using cosine distance
        query_stmt = select(KnowledgeBaseChunk).join(
            KnowledgeBaseEmbedding, KnowledgeBaseChunk.id == KnowledgeBaseEmbedding.chunk_id
        ).where(
            KnowledgeBaseEmbedding.tenant_id == tenant.id,
            KnowledgeBaseEmbedding.model == "text-embedding-3-small"
        ).order_by(
            KnowledgeBaseEmbedding.embedding.cosine_distance(embedding)
        ).limit(3)
        
        result = await db.execute(query_stmt)
        chunks = result.scalars().all()
        
        # 2. Build prompt
        messages = self.prompt_builder.build(query, chunks)

        # 3. Call LLM
        llm_completion = await get_chat_completion(messages, model="gpt-3.5-turbo")
        answer = llm_completion.choices[0].message.content
        
        # Calculate costs
        prompt_tokens = llm_completion.usage.prompt_tokens
        completion_tokens = llm_completion.usage.completion_tokens
        total_tokens = llm_completion.usage.total_tokens
        
        # Pricing for gpt-3.5-turbo-0125
        cost_usd = (prompt_tokens * 0.50 / 1_000_000) + (completion_tokens * 1.50 / 1_000_000)
        
        # 4. Persistence
        if session_id:
            # Verify conversation belongs to tenant
            conv_result = await db.execute(
                select(Conversation).where(
                    Conversation.session_id == session_id,
                    Conversation.tenant_id == tenant.id
                )
            )
            conversation = conv_result.scalars().first()
            if not conversation:
                 conversation = Conversation(
                    tenant_id=tenant.id,
                    session_id=session_id
                )
                 db.add(conversation)
                 await db.flush()
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
            text=query
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

        return answer, session_id, cost_usd

chat_service = ChatService()
