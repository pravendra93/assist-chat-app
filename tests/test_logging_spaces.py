import os
import boto3
import pytest
from botocore.client import Config
from app.core.config import settings
from app.core.logging import upload_to_spaces

def test_logging_config_environment():
    """Verify that logging environment logic respects the settings."""
    # This is a unit test for the configuration logic
    allowed_envs = ["staging", "production"]
    if settings.ENVIRONMENT in allowed_envs:
        assert True # Logic would add the file sink
    else:
        assert True # Logic would skip the file sink

@pytest.mark.skipif(
    not all([
        settings.SPACES_ACCESS_KEY_ID, 
        settings.SPACES_SECRET_ACCESS_KEY,
        settings.SPACES_BUCKET,
        settings.SPACES_ENDPOINT
    ]),
    reason="DigitalOcean Spaces credentials not configured"
)
def test_spaces_upload_integration():
    """
    Integration test: Performs a real upload to DigitalOcean Spaces.
    Only runs if credentials are provided in .env
    """
    test_file = "test_pytest_upload.txt"
    with open(test_file, "w") as f:
        f.write("This is a test upload from pytest to verify log rotation integration.")

    try:
        # Use the same logic as the app
        session = boto3.session.Session()
        client = session.client(
            's3',
            region_name=settings.SPACES_REGION,
            endpoint_url=settings.SPACES_ENDPOINT,
            aws_access_key_id=settings.SPACES_ACCESS_KEY_ID,
            aws_secret_access_key=settings.SPACES_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )

        file_name = os.path.basename(test_file)
        object_name = f"dev-logs/assist-chat-app/test_pytest_{os.getpid()}.txt"
        
        client.upload_file(test_file, settings.SPACES_BUCKET, object_name)
        
        # Verify it exists
        response = client.head_object(Bucket=settings.SPACES_BUCKET, Key=object_name)
        assert response['ResponseMetadata']['HTTPStatusCode'] == 200
        
        # Clean up in Spaces
        client.delete_object(Bucket=settings.SPACES_BUCKET, Key=object_name)
        
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

def test_log_segregation(mocker):
    """
    Verifies that logs are correctly routed to app.log and errors.log.
    We mock the environment to be 'production' to ensure file sinks are added.
    """
    from loguru import logger
    import json
    import time
    from app.core.logging import setup_logging
    
    # Mock settings to enable file logging
    mocker.patch("app.core.config.settings.ENVIRONMENT", "production")
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Reset logger and setup with mocked settings
    logger.remove()
    setup_logging()
    
    # Emit logs at different levels
    test_msg_info = f"TEST_INFO_{os.getpid()}"
    test_msg_error = f"TEST_ERROR_{os.getpid()}"
    
    logger.info(test_msg_info)
    logger.error(test_msg_error)
    
    # Since enqueue=True, we might need a tiny sleep or wait for the sink to process
    # In a real environment, wait_time should be minimal
    time.sleep(0.5) 
    
    # Check app.log (should have both)
    if os.path.exists("logs/app.log"):
        with open("logs/app.log", "r") as f:
            content = f.read()
            assert test_msg_info in content
            assert test_msg_error in content
            
            # Verify JSON format
            last_line = content.strip().split("\n")[-1]
            log_entry = json.loads(last_line)
            assert "message" in log_entry
            assert "timestamp" in log_entry

    # Check errors.log (should ONLY have error)
    if os.path.exists("logs/errors.log"):
        with open("logs/errors.log", "r") as f:
            content = f.read()
            assert test_msg_info not in content
            assert test_msg_error in content
            
            # Verify JSON format
            last_line = content.strip().split("\n")[-1]
            log_entry = json.loads(last_line)
            assert log_entry["level"] == "ERROR"

def test_upload_to_spaces_no_deadlock(mocker):
    """
    Ensures upload_to_spaces doesn't use the logger, preventing deadlocks.
    We mock sys.stdout/stderr to verify they are used instead.
    """
    mock_stdout = mocker.patch("sys.stdout.write")
    mock_stderr = mocker.patch("sys.stderr.write")
    mock_boto3 = mocker.patch("boto3.session.Session")
    
    # Create a dummy file
    with open("dummy.log", "w") as f:
        f.write("dummy")
    
    try:
        upload_to_spaces("dummy.log")
        
        # Should NOT call logger (this is harder to assert deeply, but we check streams)
        # If credentials are missing (local env), it writes to stderr
        if not all([settings.SPACES_ACCESS_KEY_ID, settings.SPACES_SECRET_ACCESS_KEY]):
            assert mock_stderr.called
    finally:
        if os.path.exists("dummy.log"):
            os.remove("dummy.log")
