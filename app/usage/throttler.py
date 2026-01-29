from fastapi import HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timezone

from app.db.session import get_db

# safety buffer so we block BEFORE hard limit
COST_BUFFER_USD = 0.20  

async def enforce_cost_limit(
    tenant: dict,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = tenant["tenant_id"]
    daily_limit = tenant["daily_cost_limit"]

    today = datetime.now(timezone.utc).date()

    query = """
    SELECT COALESCE(SUM(cost_usd), 0)
    FROM llm_usage
    WHERE tenant_id = :tenant_id
      AND created_at::date = :today
    """

    result = await db.execute(
        text(query),
        {
            "tenant_id": tenant_id,
            "today": today,
        }
    )

    spent_today = float(result.scalar() or 0)

    if spent_today >= (daily_limit - COST_BUFFER_USD):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Daily LLM budget exceeded",
                "spent_today": spent_today,
                "daily_limit": daily_limit,
            },
        )

    return {
        "spent_today": spent_today,
        "daily_limit": daily_limit,
    }
