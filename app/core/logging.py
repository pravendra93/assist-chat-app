import logging
import sys
from loguru import logger
import json
import os
import boto3
from botocore.client import Config
from app.core.config import settings

def serialize(record):
    exception = record["exception"]
    if exception:
        exception = {
            "type": exception.type.__name__,
            "value": str(exception.value),
            "traceback": bool(exception.traceback),
        }

    subset = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "extra": record["extra"],
        "exception": exception,
    }
    return json.dumps(subset)

def json_formatter(record):
    record["extra"]["serialized"] = serialize(record)
    return "{extra[serialized]}\n"

def health_filter(record):
    """
    Filters out logs related to the /health endpoint to reduce noise.
    """
    return "/health" not in record["message"]

def dynamic_console_formatter(record):
    """
    Dynamic formatter for console that gracefully handles missing request_id.
    """
    # Use 'SYSTEM' if request_id is not present
    req_id = record["extra"].get("request_id", "SYSTEM")
    
    # Custom format string
    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        f"<cyan>{req_id}</cyan> - "
        "<level>{message}</level>"
    )
    
    # Add extra fields if they exist (excluding serialized and request_id which we already handled)
    extra_items = {k: v for k, v in record["extra"].items() if k not in ["serialized", "request_id"]}
    if extra_items:
        # Escape curly braces because Loguru will try to format the returned string again
        extra_str = str(extra_items).replace("{", "{{").replace("}", "}}")
        fmt += f" <magenta>{extra_str}</magenta>"
    
    return fmt + "\n"

# Shared Boto3 client for DigitalOcean Spaces
_spaces_client = None

def get_spaces_client():
    global _spaces_client
    if _spaces_client is None:
        if all([
            settings.SPACES_ACCESS_KEY_ID, 
            settings.SPACES_SECRET_ACCESS_KEY,
            settings.SPACES_BUCKET,
            settings.SPACES_ENDPOINT
        ]):
            try:
                session = boto3.session.Session()
                _spaces_client = session.client(
                    's3',
                    region_name=settings.SPACES_REGION,
                    endpoint_url=settings.SPACES_ENDPOINT,
                    aws_access_key_id=settings.SPACES_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.SPACES_SECRET_ACCESS_KEY,
                    config=Config(signature_version='s3v4')
                )
            except Exception as e:
                sys.stderr.write(f"Failed to initialize DigitalOcean Spaces client: {e}\n")
    return _spaces_client

def upload_to_spaces(file_path):
    """
    Uploads a file to DigitalOcean Spaces using a shared client.
    Used as an after-rotation hook for loguru.
    """
    client = get_spaces_client()
    if not client:
        return

    try:
        file_name = os.path.basename(file_path)
        # Bucket route: dev-assistra/dev-logs/assist-chat-app
        object_name = f"dev-logs/assist-chat-app/{file_name}"
        
        client.upload_file(file_path, settings.SPACES_BUCKET, object_name)
        sys.stdout.write(f"Successfully uploaded {file_name} to DigitalOcean Spaces: {object_name}\n")
    except Exception as e:
        sys.stderr.write(f"Failed to upload {file_path} to DigitalOcean Spaces: {e}\n")

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def setup_logging():
    # Remove default handlers
    logger.remove()
    
    # Sink 1: Human-readable console for development (DEBUG+)
    logger.add(
        sys.stdout,
        format=dynamic_console_formatter,
        filter=health_filter,
        level="DEBUG",
        backtrace=True,
        diagnose=True,
        enqueue=True
    )

    # File-based Sinks (Only enabled for staging and production)
    if settings.ENVIRONMENT in ["staging", "production"]:
        os.makedirs("logs", exist_ok=True)
        
        # Sink 2: JSON file for production monitoring (INFO+)
        logger.add(
            "logs/app.log",
            format=json_formatter,
            filter=health_filter,
            level="INFO",
            rotation="10 MB",
            compression=upload_to_spaces,
            backtrace=True,
            diagnose=True,
            enqueue=True
        )

        # Sink 3: Error-only JSON file for alerts (ERROR+)
        logger.add(
            "logs/errors.log",
            format=json_formatter,
            filter=health_filter,
            level="ERROR",
            rotation="10 MB",
            compression=upload_to_spaces,
            backtrace=True,
            diagnose=True,
            enqueue=True
        )
    else:
        sys.stdout.write(f"File logging and Spaces upload disabled for current environment: {settings.ENVIRONMENT}\n")

    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Specific interceptors for common libraries
    for name in ["uvicorn", "uvicorn.access", "fastapi", "openai", "httpx"]:
        _logger = logging.getLogger(name)
        _logger.handlers = [InterceptHandler()]
        _logger.propagate = False
        # Prevent noisy debug logs (like full prompts in Request options)
        _logger.setLevel(logging.INFO)

    return logger
