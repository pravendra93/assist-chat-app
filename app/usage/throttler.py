"""
app/usage/throttler.py

Usage enforcement.
Checks trial expiry and credit balance before allowing a chat call.
"""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.services.credit_service import has_sufficient_credits

if TYPE_CHECKING:
    from app.db.models import Tenant
    from app.core.plan_limits import PlanLimits


async def enforce_plan_limits(
    tenant: "Tenant",
    plan_limits: "PlanLimits",
    db: AsyncSession,
) -> None:
    """
    Gate-check usage limits before serving a chat request.

    Checks:
    1. Trial expiry: Raises HTTP 403
    2. Credit balance: Raises HTTP 402 if exhausted
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

    # 2. Credit check
    # Throttling is now done primarily via credits instead of daily/monthly budget caps.
    sufficient = await has_sufficient_credits(db, tenant.id)
    if not sufficient:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "credits_exhausted",
                "message": "You have run out of credits. Please upgrade your plan to continue.",
            },
        )


# ---------------------------------------------------------------------------
# Legacy helper kept for backward compatibility (internal paths only)
# ---------------------------------------------------------------------------

async def enforce_cost_limit(
    tenant: dict,
    db: AsyncSession,
) -> dict:
    """
    Deprecated: use enforce_plan_limits instead.
    Enforces credit check for dict-based tenant data.
    """
    import uuid
    tenant_id = uuid.UUID(tenant["tenant_id"]) if isinstance(tenant["tenant_id"], str) else tenant["tenant_id"]
    
    sufficient = await has_sufficient_credits(db, tenant_id)
    if not sufficient:
        raise HTTPException(
            status_code=402,
            detail={"error": "Credits exhausted"},
        )
    return {"status": "ok"}
