import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.api.chat import router as chat_router
from app.api.widget import router as widget_router
from app.api.internal import router as internal_router
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.utils.redis_client import redis_client

# Setup structured logging
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await redis_client.connect()
    logger.info("Application startup: Redis connected")
    yield
    # Shutdown logic
    await redis_client.close()
    logger.info("Application shutdown: Redis closed")

app = FastAPI(
    title="RAG Chat Service",
    version="0.1.0",
    lifespan=lifespan
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

# Static Files (for Widget script)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routes
app.include_router(chat_router, prefix="/v1/chat")
app.include_router(widget_router, prefix="/v1/widget")
app.include_router(internal_router, prefix="/v1/internal", tags=["internal"])

@app.get("/")
async def root():
    return {"status": "ok", "message": "Welcome to RAG Chat Service"}

@app.get("/health")
async def health():
    return {"status": "ok"}
