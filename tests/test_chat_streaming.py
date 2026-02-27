import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.auth.api_key import require_tenant_api_key
from app.db.models import Tenant, ApiKey
from app.db.session import get_db
import uuid
import json

# Mock objects
mock_tenant_id = uuid.uuid4()

def create_mock_tenant():
    return Tenant(id=mock_tenant_id, name="Test Tenant", plan_id=uuid.uuid4())

def create_mock_api_key():
    return ApiKey(id=uuid.uuid4(), tenant_id=mock_tenant_id, is_active=True)

async def mock_auth():
    return create_mock_tenant(), create_mock_api_key()

app.dependency_overrides[require_tenant_api_key] = mock_auth

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@patch("app.utils.redis_client.redis_client", new_callable=AsyncMock)
@patch("app.services.chat_service.get_chat_completion_stream", new_callable=AsyncMock)
@patch("app.services.chat_service.get_embedding", new_callable=AsyncMock)
@patch("app.api.chat.get_plan_limits")
def test_chat_streaming(mock_get_limits, mock_embedding, mock_stream, mock_redis, client):
    # Mock plan limits
    from app.core.plan_limits import PlanLimits
    limits = PlanLimits.from_features({
        "model_limits": {
            "max_tokens_per_request": 100,
            "max_chunks_per_query": 5,
            "allowed_models": ["gpt-4o-mini"]
        }
    })
    mock_get_limits.return_value = limits
    
    # Mock DB
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [] # No chunks for simplicity
    mock_session.execute.return_value = mock_result
    
    async def override_get_db():
        yield mock_session
    app.dependency_overrides[get_db] = override_get_db
    
    # Mock Embedding
    mock_embedding.return_value = [0.1] * 1536
    
    # Mock Streaming Response
    async def mock_stream_generator():
        chunks = ["Hello", " world", "!"]
        for c in chunks:
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content=c))]
            yield mock_chunk
        
        # Final usage chunk
        usage_chunk = MagicMock()
        usage_chunk.choices = []
        usage_chunk.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        yield usage_chunk

    mock_stream.return_value = mock_stream_generator()
    
    # Mock Celery
    with patch("app.tasks.background.persist_chat_response.delay") as mock_delay:
        response = client.post(
            "/v1/chat/",
            json={"query": "Hi", "stream": True}
        )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    
    # Collect streamed content
    content = ""
    for chunk in response.iter_bytes():
        content += chunk.decode()
    
    assert content == "Hello world!"
    
    # Check if persistence was scheduled (might be async in the background task)
    mock_delay.assert_called_once()
    
    # Cleanup
    app.dependency_overrides.pop(get_db, None)
