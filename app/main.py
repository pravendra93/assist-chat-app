import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.core.config import settings
from app.core.logging import setup_logging, logger

# Setup structured logging
setup_logging()

app = FastAPI(
    title="RAG Chat Service",
    version="0.1.0"
)

# CORS Configuration (FINDING-009)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS if settings.BACKEND_CORS_ORIGINS else [
        "http://localhost:3000",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["ASST-API-Key", "Content-Type", "Authorization"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Skip logging for health checks to reduce noise
    if request.url.path == "/health":
        return await call_next(request)
        
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    with logger.contextualize(request_id=request_id, path=request.url.path, method=request.method):
        logger.info("request_started")
        
        try:
            response = await call_next(request)
            
            process_time = (time.time() - start_time) * 1000
            formatted_process_time = "{0:.2f}ms".format(process_time)
            
            # Log completion
            logger.info(
                "request_finished",
                status_code=response.status_code,
                latency=formatted_process_time,
                cost=response.headers.get("X-Total-Cost", "0.000000")
            )
            
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = formatted_process_time
            
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.exception(
                "request_failed",
                error=str(e),
                latency="{0:.2f}ms".format(process_time)
            )
            raise

app.include_router(chat_router, prefix="/v1/chat")

@app.get("/")
async def root():
    return {"status": "ok", "message": "Welcome to RAG Chat Service"}

@app.get("/health")
async def health():
    return {"status": "ok"}
