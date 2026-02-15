import asyncio
from typing import Any, Dict
import uuid
from app.core.celery_app import celery_app
from app.services.chat_service import chat_service
from app.db.session import AsyncSessionLocal
from app.core.logging import logger

@celery_app.task(name="persist_chat_response")
def persist_chat_response(tenant_id_str: str, session_id: str, data: Dict[str, Any]):
    """
    Sync wrapper for the async chat_service.persist_response.
    """
    from app.db.session import engine, AsyncSessionLocal
    import uuid
    
    tenant_id = uuid.UUID(tenant_id_str)
    
    async def run_persistence():
        try:
            async with AsyncSessionLocal() as db:
                await chat_service.persist_response(
                    db=db,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    data=data
                )
                logger.info(f"Successfully persisted chat response for session {session_id}")
        except Exception as e:
            logger.error(f"Error persisting chat response for session {session_id}: {e}")
            raise e
        finally:
            # CRITICAL: Dispose the engine pool after each task when using asyncio.run()
            # to avoid "got Future attached to a different loop" errors on reuse.
            await engine.dispose()

    asyncio.run(run_persistence())
