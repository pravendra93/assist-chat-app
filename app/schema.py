# app/schemas.py
from pydantic import BaseModel, EmailStr
from decimal import Decimal
from typing import Optional, Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class RegisterOut(BaseModel):
    account_id: str
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AccountOut(BaseModel):
    id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    role: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class AccountUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class InviteIn(BaseModel):
    email: EmailStr
    role: Optional[str] = "admin"


class TenantUserSetup(BaseModel):
    token: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: str


class ValidateToken(BaseModel):
    token: str


class WidgetInitOut(BaseModel):
    tenant_id: str
    branding: dict
    widget_config: dict
    ephemeral_token: str


class ConversationOut(BaseModel):
    id: UUID
    tenant_id: UUID
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    resolved: bool
    escalated: bool

    class Config:
        orm_mode = True


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    sender: str
    text: str
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        orm_mode = True


class ChatIn(BaseModel):
    tenant_id: str
    session_id: Optional[str]
    user_id: Optional[str]
    query: str


class ChatOut(BaseModel):
    conversation_id: str
    reply: Optional[str] = None


# Coupon Schemas
class CouponCreate(BaseModel):
    coupon_code: str
    description: Optional[str] = None
    discount_amount: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    max_uses: Optional[int] = None


class CouponUpdate(BaseModel):
    description: Optional[str] = None
    discount_amount: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = None


class CouponOut(BaseModel):
    id: UUID
    coupon_code: str
    description: Optional[str] = None
    discount_amount: Optional[Decimal] = None
    discount_percentage: Optional[Decimal] = None
    max_uses: Optional[int] = None
    current_uses: int
    is_active: bool
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class CouponUsageOut(BaseModel):
    id: UUID
    coupon_id: UUID
    user_id: Optional[str] = None
    applied_at: datetime

    class Config:
        from_attributes = True

class TenantCreate(BaseModel):
    name: str
    domain: str
    owner_account_id: Optional[UUID] = None
    status: Optional[str] = "pending"  # allowed: pending, active, suspended
    plan: Optional[str] = "trial"
    plan_id: Optional[UUID] = None
    trial_ends_at: Optional[datetime] = None
    is_trial: Optional[bool] = True



class TenantOut(BaseModel):
    id: UUID
    name: str
    domain: str
    owner_account_id: Optional[UUID] = None
    status: str
    plan: str
    plan_id: Optional[UUID] = None
    trial_ends_at: Optional[datetime] = None
    is_trial: bool = True
    created_at: Optional[datetime] = None

    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    domain: str
    owner_account_id: Optional[UUID] = None
    status: Optional[str] = None
    plan: Optional[str] = None
    plan_id: Optional[UUID] = None
    trial_ends_at: Optional[datetime] = None
    is_trial: Optional[bool] = None


    class Config:
        orm_mode = True


class TenantUserOut(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class TenantConfigOut(BaseModel):
    id: UUID
    tenant_id: UUID
    domain: Optional[str] = None
    brand_name: Optional[str] = None
    primary_color: Optional[str] = "#0ea5e9"
    logo_url: Optional[str] = None
    welcome_message: Optional[str] = "Hello! How can I help you?"
    chat_icon: Optional[str] = "message"

    class Config:
        orm_mode = True


class PlanPriceOut(BaseModel):
    id: UUID
    plan_id: UUID
    price_cents: int
    currency: str
    interval: str
    stripe_price_id: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

    class Config:
        orm_mode = True


class PlanCreate(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    price_cents: int = 0
    currency: str = "usd"
    interval: str = "month"  # month | year | one_time
    interval_count: int = 1
    trial_days: int = 0
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    features: Optional[Dict[str, Any]] = {}
    meta: Optional[Dict[str, Any]] = {}
    active: bool = True


class PlanOut(BaseModel):
    id: UUID
    slug: str
    name: str
    description: Optional[str] = None
    price_cents: int
    currency: str
    interval: str
    interval_count: int
    trial_days: int
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    features: Optional[Dict[str, Any]] = {}
    meta: Optional[Dict[str, Any]] = {}
    active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # prices: List[PlanPriceOut] = []

    class Config:
        orm_mode = True


class PlanUpdate(BaseModel):
    # All fields optional for partial update
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = None
    currency: Optional[str] = None
    interval: Optional[str] = None
    interval_count: Optional[int] = None
    trial_days: Optional[int] = None
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None

    class Config:
        orm_mode = True


class PublicPlanOut(BaseModel):
    """Public-safe plan schema — no Stripe IDs or internal metadata."""
    id: UUID
    slug: str
    name: str
    description: Optional[str] = None
    price_cents: int
    currency: str
    interval: str
    interval_count: int
    trial_days: int
    features: Optional[Dict[str, Any]] = {}
    active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class LogEntry(BaseModel):
    level: str
    message: str
    context: Optional[Dict[str, Any]] = None

class ChatbotConfigOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str = "Support Assistant"
    welcome_message: Optional[str] = "Hi! How can I help you today?"
    is_active: bool = True
    primary_color: Optional[str] = "#000000"
    background_color: Optional[str] = "#ffffff"
    logo_url: Optional[str] = None
    position: Optional[str] = "bottom-right"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class ChatbotConfigUpdate(BaseModel):
    name: Optional[str] = None
    welcome_message: Optional[str] = None
    is_active: Optional[bool] = None
    primary_color: Optional[str] = None
    background_color: Optional[str] = None
    logo_url: Optional[str] = None
    position: Optional[str] = None


class KnowledgeBaseFileOut(BaseModel):
    id: UUID
    tenant_id: UUID
    file_name: str
    file_type: str
    file_size: int
    storage_key: str
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    estimated_time: Optional[int] = None  # in seconds
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class PresignedUrlRequest(BaseModel):
    tenant_id: UUID
    file_name: str
    file_type: str  # 'pdf' or 'csv'
    file_size: int
    content_type: str = "application/octet-stream"


class PresignedUrlResponse(BaseModel):
    file_id: UUID
    upload_url: str
    storage_key: str


class KnowledgeBaseChunkOut(BaseModel):
    id: UUID
    file_id: UUID
    tenant_id: UUID
    chunk_index: int
    page_no: Optional[int] = None
    content: str
    token_estimate: int
    status: str
    is_embedded: bool
    usage_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ApiKeyCreate(BaseModel):
    name: str
    tenant_id: UUID


class ApiKeyOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    key: Optional[str] = None  # The masked key (prefix + ***)
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

    # Helper for tenant name if joined
    tenant_name: Optional[str] = None

    class Config:
        orm_mode = True


class ApiKeyCreated(ApiKeyOut):
    full_key: str


class TenantLimitsOverrideBase(BaseModel):
    monthly_spend_limit_usd: Optional[Decimal] = Decimal("50.00")
    daily_spend_limit_usd: Optional[Decimal] = Decimal("5.00")
    max_requests_per_minute: Optional[int] = 30
    max_requests_per_day: Optional[int] = 2000
    max_concurrent_sessions: Optional[int] = 100
    max_tokens_per_request: Optional[int] = 1500
    max_chunks_per_query: Optional[int] = 5
    max_files: Optional[int] = 50
    max_total_storage_mb: Optional[int] = 500
    max_embeddings_per_month: Optional[int] = 50000
    auto_suspend_on_limit: Optional[bool] = True
    notify_on_80_percent: Optional[bool] = True


class TenantLimitsOverrideCreate(TenantLimitsOverrideBase):
    tenant_id: UUID


class TenantLimitsOverrideUpdate(BaseModel):
    monthly_spend_limit_usd: Optional[Decimal] = None
    daily_spend_limit_usd: Optional[Decimal] = None
    max_requests_per_minute: Optional[int] = None
    max_requests_per_day: Optional[int] = None
    max_concurrent_sessions: Optional[int] = None
    max_tokens_per_request: Optional[int] = None
    max_chunks_per_query: Optional[int] = None
    max_files: Optional[int] = None
    max_total_storage_mb: Optional[int] = None
    max_embeddings_per_month: Optional[int] = None
    auto_suspend_on_limit: Optional[bool] = None
    notify_on_80_percent: Optional[bool] = None


class TenantLimitsOverrideOut(TenantLimitsOverrideBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True



