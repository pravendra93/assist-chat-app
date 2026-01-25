from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.auth.api_key import require_tenant_api_key

router = APIRouter()

class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None

class ChatResponse(BaseModel):
    answer: str
    confidence: float | None = None

@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    tenant=Depends(require_tenant_api_key)
):
    """
    Step-by-step pipeline (later):
    1. Retrieve chunks
    2. Build prompt
    3. Call LLM
    4. Track usage
    """

    # placeholder
    return ChatResponse(
        answer="RAG response placeholder",
        confidence=0.0
    )
