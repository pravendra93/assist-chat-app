from fastapi import FastAPI
from app.api.chat import router as chat_router

app = FastAPI(
    title="RAG Chat Service",
    version="0.1.0"
)

app.include_router(chat_router, prefix="/v1/chat")
@app.get("/")
async def root():
    return {"status": "ok", "message": "Welcome to RAG Chat Service"}

@app.get("/health")
async def health():
    return {"status": "ok"}
