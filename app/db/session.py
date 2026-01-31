# app/db/session.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL")

engine = None
AsyncSessionLocal = None

def get_engine():
    global engine
    if engine is not None:
        return engine
    
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL env var is required (point to Supabase Postgres)")

    # If someone provided a sync URL like "postgresql://...", convert it to asyncpg dialect:
    url = DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace(
            "postgresql://", "postgresql+asyncpg://", 1)

    # create async engine (tune pool_size / max_overflow if necessary)
    engine = create_async_engine(
        url, future=True, echo=False, pool_size=20, max_overflow=10)
    return engine

def get_session_factory():
    global AsyncSessionLocal
    if AsyncSessionLocal is not None:
        return AsyncSessionLocal
    
    eng = get_engine()
    AsyncSessionLocal = sessionmaker(
        eng, class_=AsyncSession, expire_on_commit=False)
    return AsyncSessionLocal


async def init_db():
    # lightweight connectivity check only
    eng = get_engine()
    async with eng.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def get_db():
    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        yield session

