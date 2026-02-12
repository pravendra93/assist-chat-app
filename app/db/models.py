# app/db/models.py
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


def gen_uuid():
    # return a Python uuid.UUID object
    return uuid.uuid4()


class Account(Base):
    __tablename__ = "accounts"
    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    email = sa.Column(sa.String, nullable=False, unique=True, index=True)
    hashed_password = sa.Column(sa.String, nullable=False)
    first_name = sa.Column(sa.String, nullable=True)
    last_name = sa.Column(sa.String, nullable=True)
    is_active = sa.Column(sa.Boolean, default=True)
    # Whether the account's email address has been verified.
    # This column exists in the migrations; expose it here so ORM matches DB.
    email_verified = sa.Column(sa.Boolean, nullable=False,
                               server_default=sa.sql.expression.false())
    role = sa.Column(sa.String, nullable=False,
                     server_default="platform_user", index=True)
    token_version = sa.Column(sa.Integer, nullable=False, default=0)
    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())


class Tenant(Base):
    __tablename__ = "tenants"
    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    name = sa.Column(sa.String, nullable=False)
    owner_account_id = sa.Column(postgresql.UUID(
        as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True)
    status = sa.Column(sa.String, default="pending")
    plan = sa.Column(sa.String, default="trial")
    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())


class TenantUser(Base):
    __tablename__ = "tenant_users"
    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    tenant_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "tenants.id"), nullable=False, index=True)
    email = sa.Column(sa.String, nullable=False)
    first_name = sa.Column(sa.String, nullable=True)
    last_name = sa.Column(sa.String, nullable=True)
    role = sa.Column(sa.String, default="viewer")
    hashed_password = sa.Column(sa.String, nullable=True)
    is_active = sa.Column(sa.Boolean, default=True)
    token_version = sa.Column(sa.Integer, nullable=False, default=0)
    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"
    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    tenant_id = sa.Column(postgresql.UUID(as_uuid=True),
                          sa.ForeignKey("tenants.id"), nullable=False)
    plan = sa.Column(sa.String, nullable=True)
    status = sa.Column(sa.String, nullable=True)
    started_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    provider_subscription_id = sa.Column(sa.String, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())


class EmailToken(Base):
    __tablename__ = "email_tokens"
    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    account_id = sa.Column(postgresql.UUID(as_uuid=True),
                           sa.ForeignKey("accounts.id"), nullable=True)
    tenant_user_id = sa.Column(postgresql.UUID(
        as_uuid=True), sa.ForeignKey("tenant_users.id"), nullable=True)
    token = sa.Column(sa.String, nullable=False, index=True)
    token_type = sa.Column(sa.String, nullable=False)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    used = sa.Column(sa.Boolean, default=False)
    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    tenant_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "tenants.id"), nullable=False, index=True)
    session_id = sa.Column(sa.String, nullable=True)
    user_id = sa.Column(sa.String, nullable=True)
    started_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())
    ended_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    resolved = sa.Column(sa.Boolean, default=False)
    escalated = sa.Column(sa.Boolean, default=False)


class Message(Base):
    __tablename__ = "messages"
    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    conversation_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "conversations.id"), nullable=False, index=True)
    sender = sa.Column(sa.String, nullable=False)
    text = sa.Column(sa.Text, nullable=True)
    meta = sa.Column("metadata", sa.JSON, default={})
    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    tenant_id = sa.Column(postgresql.UUID(as_uuid=True),
                          sa.ForeignKey("tenants.id"), nullable=True)
    event_type = sa.Column(sa.String, nullable=True)
    payload = sa.Column(sa.JSON, default={})
    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())


class Plan(Base):
    __tablename__ = "plans"

    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)

    slug = sa.Column(sa.String, nullable=False, unique=True)
    name = sa.Column(sa.String, nullable=False)
    description = sa.Column(sa.Text, nullable=True)

    price_cents = sa.Column(sa.Integer, nullable=False, default=0)
    currency = sa.Column(sa.String, nullable=False, default="usd")

    # month | year | one_time
    interval = sa.Column(sa.String, nullable=False, default="month")
    interval_count = sa.Column(sa.Integer, nullable=False, default=1)

    trial_days = sa.Column(sa.Integer, nullable=False, default=0)

    stripe_product_id = sa.Column(sa.String, nullable=True)
    stripe_price_id = sa.Column(sa.String, nullable=True)

    features = sa.Column(postgresql.JSONB, nullable=False, default=dict)
    meta = sa.Column("metadata", postgresql.JSONB,
                     nullable=False, server_default='{}')

    active = sa.Column(sa.Boolean, nullable=False, default=True)

    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())

    updated_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())

    prices = relationship("PlanPrice", back_populates="plan",
                          cascade="all, delete-orphan", order_by="PlanPrice.valid_from")


class PlanPrice(Base):
    __tablename__ = "plan_prices"

    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    plan_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "plans.id", ondelete="CASCADE"), nullable=False, index=True)

    price_cents = sa.Column(sa.Integer, nullable=False)
    currency = sa.Column(sa.String, nullable=False, default="usd")
    interval = sa.Column(sa.String, nullable=False)
    stripe_price_id = sa. Column(sa.String, nullable=True)

    valid_from = sa.Column(sa.TIMESTAMP(timezone=True),
                           nullable=False, server_default=func.now())
    valid_to = sa.Column(sa.TIMESTAMP(timezone=True), nullable=True)

    # relationship back to Plan
    plan = relationship("Plan", back_populates="prices")


class KnowledgeBaseFile(Base):
    __tablename__ = "knowledge_base_files"

    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    tenant_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "tenants.id"), nullable=False, index=True)
    uploaded_by = sa.Column(postgresql.UUID(as_uuid=True), nullable=True)

    file_name = sa.Column(sa.String, nullable=False)
    file_type = sa.Column(sa.String, nullable=False)
    file_size = sa.Column(sa.BigInteger, nullable=False)

    storage_key = sa.Column(sa.String, nullable=False)
    storage_provider = sa.Column(sa.String, default='do_spaces')

    status = sa.Column(sa.String, nullable=False, default='uploaded')
    
    chunk_count = sa.Column(sa.Integer, default=0)
    error_message = sa.Column(sa.Text, nullable=True)
    celery_task_id = sa.Column(sa.String, nullable=True)


    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now(), onupdate=func.now())



class KnowledgeBaseChunk(Base):
    __tablename__ = "knowledge_base_chunks"

    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    file_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "knowledge_base_files.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    chunk_index = sa.Column(sa.Integer, nullable=False)
    page_no = sa.Column(sa.Integer, nullable=True)  # for PDFs
    content = sa.Column(sa.Text, nullable=False)
    token_estimate = sa.Column(sa.Integer, nullable=False)

    status = sa.Column(sa.String, nullable=False, default='active')
    is_embedded = sa.Column(sa.Boolean, default=False)
    usage_count = sa.Column(sa.Integer, default=0)

    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now(), onupdate=func.now())


class ApiKey(Base):
    __tablename__ = "tenant_api_keys"

    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    tenant_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "tenants.id", ondelete="CASCADE"), nullable=False, index=True)

    name = sa.Column(sa.String, nullable=True)
    
    # Secure storage
    api_key_hash = sa.Column(sa.String, nullable=False, unique=True, index=True)
    # Store prefix to identify keys in UI and for efficient lookup (e.g. sk_live_1234...)
    key_prefix = sa.Column(sa.String, nullable=True, index=True)  # Indexed for fast lookup
    
    is_active = sa.Column(sa.Boolean, default=True)
    
    rate_limit_per_min = sa.Column(sa.Integer, default=60)
    daily_cost_limit_usd = sa.Column(sa.Numeric(10, 2), default=5.00)
    
    last_used_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now(), onupdate=func.now())


from pgvector.sqlalchemy import Vector

class KnowledgeBaseEmbedding(Base):
    __tablename__ = "knowledge_base_embeddings"

    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    tenant_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "knowledge_base_chunks.id", ondelete="CASCADE"), nullable=False, index=True)

    model = sa.Column(sa.String, nullable=False)
    embedding_version = sa.Column(sa.Integer, nullable=False, default=1)

    # Use pgvector's Vector type for the embedding column
    embedding = sa.Column(Vector(1536), nullable=False)
    
    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id = sa.Column(postgresql.UUID(as_uuid=True),
                   primary_key=True, default=gen_uuid)
    tenant_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    conversation_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    message_id = sa.Column(postgresql.UUID(as_uuid=True), sa.ForeignKey(
        "messages.id", ondelete="CASCADE"), nullable=True, index=True)

    model = sa.Column(sa.String, nullable=False)
    prompt_tokens = sa.Column(sa.Integer, nullable=False)
    completion_tokens = sa.Column(sa.Integer, nullable=False)
    total_tokens = sa.Column(sa.Integer, nullable=False)

    cost_usd = sa.Column(sa.Numeric(10, 6), nullable=False)
    latency_ms = sa.Column(sa.Integer, nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True),
                           server_default=func.now())
