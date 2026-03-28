"""
app/services/credit_service.py
──────────────────────────────
Handles all credit-related logic:
  - Token → Credit conversion
  - Credit balance lookup
  - Charging credits per request
  - Checking sufficiency before a request
  - Creating/seeding ledger entries
"""

from __future__ import annotations

import uuid
from typing import Optional, Tuple
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.db.models import CreditLedger, CreditUsageLog
from app.core.logging import logger

# ─── Conversion Constants ─────────────────────────────────────────────────────
# 1 credit = TOKENS_PER_CREDIT tokens
TOKENS_PER_CREDIT: int = 1000

# Minimum credits required to attempt a chat request
MIN_CREDITS_FOR_CHAT: int = 1

# Approximate tokens for an average chat turn (used for "estimated convos" calc)
AVG_TOKENS_PER_CONVERSATION: int = 800

# Default credits granted when a new tenant signs up (can be plan-driven later)
DEFAULT_PLAN_CREDITS: int = 5_000   # 5 million tokens equivalent


def get_plan_credits(plan) -> int:
    """
    Read the monthly_credits allocation from a Plan ORM model.
    Falls back to DEFAULT_PLAN_CREDITS if the plan or its features don't have credits.
    """
    if plan is None:
        return DEFAULT_PLAN_CREDITS
    features = getattr(plan, "features", None) or {}
    credits_cfg = features.get("credits", {}) if isinstance(features, dict) else {}
    monthly = credits_cfg.get("monthly_credits")
    if monthly and isinstance(monthly, int) and monthly > 0:
        return monthly
    return DEFAULT_PLAN_CREDITS


# ─── Helpers ─────────────────────────────────────────────────────────────────

def tokens_to_credits(tokens: int) -> int:
    """Convert a raw token count to whole credits (ceiling division)."""
    if tokens <= 0:
        return 0
    return max(1, (tokens + TOKENS_PER_CREDIT - 1) // TOKENS_PER_CREDIT)


def credits_to_estimated_convos(credits_remaining: int) -> int:
    """Estimate how many average conversations the remaining credits can cover."""
    avg_credits_per_convo = tokens_to_credits(AVG_TOKENS_PER_CONVERSATION)
    if avg_credits_per_convo <= 0:
        return 0
    return credits_remaining // avg_credits_per_convo


# ─── Ledger Management ────────────────────────────────────────────────────────

async def get_active_ledger(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> Optional[CreditLedger]:
    """
    Return the current active (non-expired, credits remaining) ledger for a tenant.
    Prefers the ledger with the most remaining credits.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(CreditLedger)
        .where(CreditLedger.tenant_id == tenant_id)
        .where(CreditLedger.credits_used < CreditLedger.credits_total)
        .where(
            (CreditLedger.valid_to == None) | (CreditLedger.valid_to > now)  # noqa: E711
        )
        .order_by((CreditLedger.credits_total - CreditLedger.credits_used).desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_credit_balance(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> dict:
    """
    Aggregate credit balance across ALL ledger entries for a tenant.
    """
    now = datetime.now(timezone.utc)

    # Sum across all valid ledger rows (not expired)
    stmt = (
        select(
            func.coalesce(func.sum(CreditLedger.credits_total), 0).label("total"),
            func.coalesce(func.sum(CreditLedger.credits_used), 0).label("used"),
        )
        .where(CreditLedger.tenant_id == tenant_id)
        .where(
            (CreditLedger.valid_to == None) | (CreditLedger.valid_to > now)  # noqa: E711
        )
    )
    row = (await db.execute(stmt)).first()

    total: int = int(row.total) if row else 0
    used: int = int(row.used) if row else 0
    remaining: int = max(0, total - used)

    usage_pct: float = (used / total * 100.0) if total > 0 else 0.0

    return {
        "credits_total": total,
        "credits_used": used,
        "credits_remaining": remaining,
        "usage_pct": round(usage_pct, 2),
        "estimated_convos_left": credits_to_estimated_convos(remaining),
        "is_exhausted": remaining <= 0 and total > 0,
        "warn_80": usage_pct >= 80.0,
        "warn_95": usage_pct >= 95.0,
    }


async def ensure_tenant_ledger(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    credits: int = DEFAULT_PLAN_CREDITS,
    source: str = "plan",
    description: str = "Initial plan credits",
) -> CreditLedger:
    """
    Create a credit ledger entry for a tenant if none exists.
    Idempotent — skips creation if an active ledger already exists.
    """
    existing = await get_active_ledger(db, tenant_id)
    if existing:
        return existing

    ledger = CreditLedger(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        credits_total=credits,
        credits_used=0,
        source=source,
        description=description,
    )
    db.add(ledger)
    await db.commit()
    await db.refresh(ledger)
    logger.info(f"[Credits] Created ledger for tenant {tenant_id}: {credits} credits ({source})")
    return ledger


# ─── Credit Charging ─────────────────────────────────────────────────────────

async def charge_credits(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    prompt_tokens: int,
    completion_tokens: int,
    conversation_id: Optional[uuid.UUID] = None,
    request_type: str = "chat",
    model: str = "gpt-4o",
) -> Tuple[int, bool]:
    """
    Deduct credits from the tenant's active ledger for a completed request.

    This is called AFTER a successful API round-trip to avoid charging on failure.
    Uses a raw UPDATE with WHERE credits_used + delta <= credits_total for atomicity.

    Returns:
        (credits_charged, success)
    """
    total_tokens = prompt_tokens + completion_tokens
    credits = tokens_to_credits(total_tokens)

    if credits <= 0:
        return 0, True

    ledger = await get_active_ledger(db, tenant_id)
    if not ledger:
        # No ledger → auto-provision a default one so first-time users aren't blocked
        logger.warning(f"[Credits] No ledger found for tenant {tenant_id}; provisioning default")
        ledger = await ensure_tenant_ledger(db, tenant_id)

    # Atomic increment using SQL to prevent race conditions
    result = await db.execute(
        text(
            """
            UPDATE credit_ledger
               SET credits_used = credits_used + :delta,
                   updated_at   = now()
             WHERE id = :ledger_id
               AND credits_used + :delta <= credits_total
            RETURNING credits_used, credits_total
            """
        ),
        {"delta": credits, "ledger_id": str(ledger.id)},
    )
    row = result.first()

    if not row:
        # Could not charge (would exceed total) – log as failed
        logger.warning(
            f"[Credits] Charge failed for tenant {tenant_id}: "
            f"attempted {credits} credits but ledger is near/at limit"
        )
        log_entry = CreditUsageLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            ledger_id=ledger.id,
            conversation_id=conversation_id,
            request_type=request_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            credits_charged=0,
            model=model,
            status="failed",
        )
        db.add(log_entry)
        await db.commit() # this might throw if caller has open transaction not ready to commit. Since it's run in background worker it's OK.
        return 0, False

    # Log the successful charge
    log_entry = CreditUsageLog(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        ledger_id=ledger.id,
        conversation_id=conversation_id,
        request_type=request_type,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        credits_charged=credits,
        model=model,
        status="charged",
    )
    db.add(log_entry)
    await db.commit()

    logger.info(
        f"[Credits] Charged {credits} credits for tenant {tenant_id} "
        f"({request_type}, {total_tokens} tokens)"
    )
    return credits, True


async def has_sufficient_credits(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    min_credits: int = MIN_CREDITS_FOR_CHAT,
) -> bool:
    """
    Quick check: does the tenant have enough credits to start a request?
    Returns True even when no ledger exists (auto-provision will happen at charge time).
    """
    balance = await get_credit_balance(db, tenant_id)
    # If there's NO ledger at all, credits_total == 0 and is_exhausted == False
    # (the `total > 0` guard in get_credit_balance). Allow through; ledger will be
    # seeded on first charge.
    if balance["credits_total"] == 0:
        return True
    return balance["credits_remaining"] >= min_credits
