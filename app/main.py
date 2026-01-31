import os
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from app.api.chat import router as chat_router

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

async def custom_identifier(request: Depends):
    # Use client IP as identifier, fallback to "unknown" for tests/proxies
    if request.client:
        return request.client.host
    return request.headers.get("X-Forwarded-For", "unknown")

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Initialize Redis connection
    r = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(r, identifier=custom_identifier)
    yield
    # Close Redis connection
    await r.aclose()


app = FastAPI(
    title="RAG Chat Service",
    version="0.1.0",
    lifespan=lifespan
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include router with global rate limiting (e.g., 10 requests per minute per identifier)
# The identifier defaults to the client's IP address.
app.include_router(
    chat_router, 
    prefix="/v1/chat",
    dependencies=[Depends(RateLimiter(times=10, seconds=60))]
)

@app.get("/")
async def root():
    return {"status": "ok", "message": "Welcome to RAG Chat Service"}

@app.get("/health")
async def health():
    return {"status": "ok"}

