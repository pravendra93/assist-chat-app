from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.core.config import settings

app = FastAPI(
    title="RAG Chat Service",
    version="0.1.0"
)

# CORS Configuration
# Allow all origins since the chat widget is embedded on third-party client websites.
# Security is handled via the ASST-API-Key header, not CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["ASST-API-Key", "Content-Type", "Authorization"],
)

# Note: Rate limiting will be implemented at the endpoint level
# using fastapi-limiter's RateLimiter dependency

app.include_router(chat_router, prefix="/v1/chat")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Welcome to RAG Chat Service"}

@app.get("/health")
async def health():
    return {"status": "ok"}
