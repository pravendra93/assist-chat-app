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

def upload_to_spaces(file_path):
    """
    Uploads a file to DigitalOcean Spaces.
    Used as an after-rotation hook for loguru.
    """
    if not all([
        settings.SPACES_ACCESS_KEY_ID, 
        settings.SPACES_SECRET_ACCESS_KEY,
        settings.SPACES_BUCKET,
        settings.SPACES_ENDPOINT
    ]):
        sys.stderr.write("DigitalOcean Spaces credentials not fully configured. Skipping log upload.\n")
        return

    try:
        session = boto3.session.Session()
        client = session.client(
            's3',
            region_name=settings.SPACES_REGION,
            endpoint_url=settings.SPACES_ENDPOINT,
            aws_access_key_id=settings.SPACES_ACCESS_KEY_ID,
            aws_secret_access_key=settings.SPACES_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )

        file_name = os.path.basename(file_path)
        # Bucket route: dev-assistra/dev-logs/assist-chat-app
        # Since SPACES_BUCKET is 'dev-assistra', the key should start with 'dev-logs/assist-chat-app/'
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
    
    # Add JSON handler to stdout
    logger.add(
        sys.stdout,
        format=json_formatter,
        level="INFO",
        backtrace=True,
        diagnose=True,
    )

    # Add file handler with rotation and upload to Spaces
    # Logs are stored locally in 'logs/' and uploaded after rotation
    # Only enabled for staging and production
    if settings.ENVIRONMENT in ["staging", "production"]:
        log_file_path = "logs/assist-chat-app.log"
        os.makedirs("logs", exist_ok=True)
        
        logger.add(
            log_file_path,
            format=json_formatter,
            level="INFO",
            rotation="10 KB",  # Rotate when file reaches 10MB
            compression=upload_to_spaces,  # Upload to Spaces after rotation
            backtrace=True,
            diagnose=True,
        )
    else:
        sys.stdout.write(f"Log uploading disabled for current environment: {settings.ENVIRONMENT}\n")

    # Intercept standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    
    # Specific interceptors for common libraries
    for name in ["uvicorn", "uvicorn.access", "fastapi"]:
        _logger = logging.getLogger(name)
        _logger.handlers = [InterceptHandler()]
        _logger.propagate = False

    return logger
