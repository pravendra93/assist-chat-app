"""
app/core/plan_limits.py

Parses Plan.features JSONB into a typed PlanLimits dataclass and
provides a helper to load it for a given tenant.

Expected Plan.features structure:
{
    "usage": {
        "max_requests_per_day": 15000,
        "max_requests_per_minute": 60,
        "max_conversations_per_month": 30000
    },
    "billing": {
        "monthly_spend_limit_usd": 180,
        "daily_spend_limit_usd": 25,
        "overage_allowed": true
    },
    "model_limits": {
        "max_tokens_per_request": 3000,
        "max_chunks_per_query": 12,
        "allowed_models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1"]
    },
    "knowledge_base": {
        "max_files": 150,
        "max_storage_mb": 5000,
        "max_chunks_total": 150000
    },
    "team": {
        "max_users": 10
    },
    "analytics": {
        "retention_days": 180
    },
    "support": {
        "priority_support": true,
        "sla": "24h"
    }
}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.models import Tenant


# ---------------------------------------------------------------------------
# Sub-limit dataclasses
# ---------------------------------------------------------------------------

@dataclass
class UsageLimits:
    max_requests_per_day: int = 2000
    max_requests_per_minute: int = 30
    max_conversations_per_month: int = 10000


@dataclass
class BillingLimits:
    monthly_spend_limit_usd: float = 50.0
    daily_spend_limit_usd: float = 5.0
    overage_allowed: bool = False


@dataclass
class ModelLimits:
    max_tokens_per_request: int = 500
    max_chunks_per_query: int = 5
    allowed_models: List[str] = field(default_factory=lambda: ["gpt-4o-mini"])

    @property
    def default_model(self) -> str:
        """Return the primary (first) allowed model."""
        return self.allowed_models[0] if self.allowed_models else "gpt-4o-mini"


@dataclass
class KnowledgeBaseLimits:
    max_files: int = 50
    max_storage_mb: int = 500
    max_chunks_total: int = 50000


@dataclass
class TeamLimits:
    max_users: int = 5


# ---------------------------------------------------------------------------
# Root dataclass
# ---------------------------------------------------------------------------

@dataclass
class PlanLimits:
    usage: UsageLimits = field(default_factory=UsageLimits)
    billing: BillingLimits = field(default_factory=BillingLimits)
    model_limits: ModelLimits = field(default_factory=ModelLimits)
    knowledge_base: KnowledgeBaseLimits = field(default_factory=KnowledgeBaseLimits)
    team: TeamLimits = field(default_factory=TeamLimits)

    @classmethod
    def from_features(cls, features: dict) -> "PlanLimits":
        """
        Parse the Plan.features JSONB dict into a PlanLimits object.
        Unknown / missing keys fall back to safe defaults.
        """
        if not features:
            return cls()

        usage_raw = features.get("usage", {})
        billing_raw = features.get("billing", {})
        model_raw = features.get("model_limits", {})
        kb_raw = features.get("knowledge_base", {})
        team_raw = features.get("team", {})

        return cls(
            usage=UsageLimits(
                max_requests_per_day=int(usage_raw.get("max_requests_per_day", 2000)),
                max_requests_per_minute=int(usage_raw.get("max_requests_per_minute", 30)),
                max_conversations_per_month=int(usage_raw.get("max_conversations_per_month", 10000)),
            ),
            billing=BillingLimits(
                monthly_spend_limit_usd=float(billing_raw.get("monthly_spend_limit_usd", 50.0)),
                daily_spend_limit_usd=float(billing_raw.get("daily_spend_limit_usd", 5.0)),
                overage_allowed=bool(billing_raw.get("overage_allowed", False)),
            ),
            model_limits=ModelLimits(
                max_tokens_per_request=int(model_raw.get("max_tokens_per_request", 500)),
                max_chunks_per_query=int(model_raw.get("max_chunks_per_query", 5)),
                allowed_models=list(model_raw.get("allowed_models", ["gpt-4o-mini"])),
            ),
            knowledge_base=KnowledgeBaseLimits(
                max_files=int(kb_raw.get("max_files", 50)),
                max_storage_mb=int(kb_raw.get("max_storage_mb", 500)),
                max_chunks_total=int(kb_raw.get("max_chunks_total", 50000)),
            ),
            team=TeamLimits(
                max_users=int(team_raw.get("max_users", 5)),
            ),
        )


# ---------------------------------------------------------------------------
# Helper: load plan limits for a given tenant
# ---------------------------------------------------------------------------

async def get_plan_limits(tenant: "Tenant", db: "AsyncSession") -> PlanLimits:
    """
    Load the Plan associated with this tenant and return its PlanLimits.
    Falls back to safe defaults if no plan is assigned or features are empty.
    """
    if tenant.plan_id is None:
        return PlanLimits()

    from sqlalchemy import select
    from app.db.models import Plan

    result = await db.execute(select(Plan).where(Plan.id == tenant.plan_id))
    plan: Optional[Plan] = result.scalars().first()

    if plan is None or not plan.features:
        return PlanLimits()

    return PlanLimits.from_features(plan.features)
