"""
app/usage/throttler.py

Plan-aware request enforcement.
Checks trial expiry, daily/monthly spend limits, and daily request counts
sourced from Plan.features (via PlanLimits) before allowing a chat call.
"""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timezone, date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import Tenant
    from app.core.plan_limits import PlanLimits

# Safety buffer so we block just before the hard limit
COST_BUFFER_USD = 0.20


async def enforce_plan_limits(
    tenant: "Tenant",
    plan_limits: "PlanLimits",
    db: AsyncSession,
) -> None:
    """
    Gate-check all plan-level limits before serving a chat request.

    Raises HTTP 403 for trial expiry.
    Raises HTTP 429 for spend / request-count overruns.
    """

    # 1. Trial expiry check
    if tenant.is_trial:
        now = datetime.now(timezone.utc)
        if tenant.trial_ends_at is not None and tenant.trial_ends_at < now:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Trial period has expired",
                    "trial_ended_at": tenant.trial_ends_at.isoformat(),
                },
            )

    tenant_id = str(tenant.id)
    today: date = datetime.now(timezone.utc).date()

    # 2. Daily spend check
    daily_result = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM llm_usage
            WHERE tenant_id = :tenant_id
              AND created_at::date = :today
            """
        ),
        {"tenant_id": tenant_id, "today": today},
    )
    daily_spent = float(daily_result.scalar() or 0)
    daily_limit = plan_limits.billing.daily_spend_limit_usd

    if not plan_limits.billing.overage_allowed and daily_spent >= (daily_limit - COST_BUFFER_USD):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Daily LLM spend limit reached",
                "spent_today_usd": daily_spent,
                "daily_limit_usd": daily_limit,
            },
        )

    # 3. Monthly spend check
    monthly_result = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM llm_usage
            WHERE tenant_id = :tenant_id
              AND date_trunc('month', created_at) = date_trunc('month', CURRENT_DATE::timestamptz)
            """
        ),
        {"tenant_id": tenant_id},
    )
    monthly_spent = float(monthly_result.scalar() or 0)
    monthly_limit = plan_limits.billing.monthly_spend_limit_usd

    if not plan_limits.billing.overage_allowed and monthly_spent >= monthly_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Monthly LLM spend limit reached",
                "spent_this_month_usd": monthly_spent,
                "monthly_limit_usd": monthly_limit,
            },
        )

    # 4. Daily request count check
    requests_result = await db.execute(
        text(
            """
            SELECT COUNT(*)
            FROM llm_usage
            WHERE tenant_id = :tenant_id
              AND created_at::date = :today
            """
        ),
        {"tenant_id": tenant_id, "today": today},
    )
    requests_today = int(requests_result.scalar() or 0)
    max_requests = plan_limits.usage.max_requests_per_day

    if requests_today >= max_requests:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Daily request limit reached",
                "requests_today": requests_today,
                "max_requests_per_day": max_requests,
            },
        )


# ---------------------------------------------------------------------------
# Legacy helper kept for backward compatibility (not used on new paths)
# ---------------------------------------------------------------------------

async def enforce_cost_limit(
    tenant: dict,
    db: AsyncSession,
) -> dict:
    """
    Deprecated: use enforce_plan_limits instead.
    Kept to avoid breaking any direct callers that haven't been migrated yet.
    """
    tenant_id = tenant["tenant_id"]
    daily_limit = tenant["daily_cost_limit"]
    today = datetime.now(timezone.utc).date()

    result = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM llm_usage
            WHERE tenant_id = :tenant_id
              AND created_at::date = :today
            """
        ),
        {"tenant_id": tenant_id, "today": today},
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

    return {"spent_today": spent_today, "daily_limit": daily_limit}
