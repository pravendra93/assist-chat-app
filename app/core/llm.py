from openai import AsyncOpenAI, APITimeoutError
from app.core.config import settings
from fastapi import HTTPException
import asyncio

client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    timeout=30.0,  # 30 second timeout (FINDING-006)
    max_retries=2
)

async def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """
    Generate an embedding for the given text using OpenAI.
    """
    text = text.replace("\n", " ")
    try:
        response = await asyncio.wait_for(
            client.embeddings.create(input=[text], model=model),
            timeout=30.0
        )
        return response.data[0].embedding
    except (APITimeoutError, asyncio.TimeoutError):
        raise HTTPException(status_code=504, detail="Embedding request timed out")

async def get_chat_completion(
    messages: list[dict], 
    model: str = "gpt-3.5-turbo", 
    temperature: float = 0.7,
    max_tokens: int = 500  # Reasonable limit (FINDING-007)
):
    """
    Get a chat completion from OpenAI with timeout and token limits.
    """
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            ),
            timeout=30.0  # 30 second timeout (FINDING-006)
        )
        return response
    except (APITimeoutError, asyncio.TimeoutError):
        raise HTTPException(status_code=504, detail="LLM request timed out")
