from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict

VECTOR_SEARCH_SQL = """
SELECT
  id,
  content,
  chunk_index,
  1 - (embedding <=> :query_embedding) AS score
FROM knowledge_base_chunks
WHERE tenant_id = :tenant_id
ORDER BY embedding <=> :query_embedding
LIMIT :top_k;
"""

async def vector_search(
    db: AsyncSession,
    *,
    tenant_id: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> List[Dict]:
    result = await db.execute(
        text(VECTOR_SEARCH_SQL),
        {
            "tenant_id": tenant_id,
            "query_embedding": query_embedding,
            "top_k": top_k,
        },
    )

    rows = result.fetchall()

    return [
        {
            "chunk_id": row.id,
            "content": row.content,
            "chunk_index": row.chunk_index,
            "score": float(row.score),
            "source": "vector",
        }
        for row in rows
    ]
