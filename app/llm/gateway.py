import voyageai
from app.core.config import settings

client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)

async def embed_text(text: str) -> list[float]:
    result = client.embed(
        texts=[text],
        model="voyage-3-lite"
    )
    return result.embeddings[0]