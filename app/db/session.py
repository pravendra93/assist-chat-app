# app/db/session.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL env var is required (point to Supabase Postgres)")

# If someone provided a sync URL like "postgresql://...", convert it to asyncpg dialect:
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://", 1)

# create async engine (tune pool_size / max_overflow if necessary)
engine = create_async_engine(
    DATABASE_URL, future=True, echo=False, pool_size=20, max_overflow=10)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    # lightweight connectivity check only
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
