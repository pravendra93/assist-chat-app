
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.auth.api_key import require_tenant_api_key
from app.db.models import Tenant, ApiKey, Plan
from app.db.session import get_db
import uuid
from datetime import datetime, timezone, timedelta

# Create reusable mock objects
mock_tenant_id = uuid.uuid4()
mock_plan_id = uuid.uuid4()

def create_mock_tenant(is_trial=False, trial_ends_at=None):
    return Tenant(
        id=mock_tenant_id,
        name="Test Tenant",
        plan_id=mock_plan_id,
        is_trial=is_trial,
        trial_ends_at=trial_ends_at
    )

def create_mock_api_key():
    return ApiKey(
        id=uuid.uuid4(),
        tenant_id=mock_tenant_id,
        is_active=True
    )

async def mock_auth_pro():
    """Mock auth for a healthy Pro tenant."""
    return create_mock_tenant(), create_mock_api_key()

# Default override for auth
app.dependency_overrides[require_tenant_api_key] = mock_auth_pro

# Create a shared mock session that conftest already partially sets up
# but we want more control in individual tests
@patch("app.api.chat.get_plan_limits")
@patch("app.usage.throttler.datetime")
def test_trial_expired_returns_403(mock_dt, mock_get_limits, client: TestClient):
    # Setup trial expired tenant
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    mock_tenant = create_mock_tenant(is_trial=True, trial_ends_at=yesterday)
    
    # Mock current time to be today
    # Note: we must mock the class method 'now'
    mock_now = datetime.now(timezone.utc)
    mock_dt.now.return_value = mock_now
    
    async def override_auth():
        return mock_tenant, create_mock_api_key()
    
    app.dependency_overrides[require_tenant_api_key] = override_auth
    
    response = client.post(
        "/v1/chat/",
        json={"query": "Hello"}
    )
    
    assert response.status_code == 403
    assert "Trial period has expired" in response.json()["detail"]["error"]
    
    # Cleanup
    app.dependency_overrides[require_tenant_api_key] = mock_auth_pro

@patch("app.api.chat.get_plan_limits")
def test_daily_spend_limit_enforced(mock_get_limits, client: TestClient):
    # Mock plan limits
    from app.core.plan_limits import PlanLimits
    limits = PlanLimits.from_features({
        "billing": {"daily_spend_limit_usd": 5.0}
    })
    mock_get_limits.return_value = limits
    
    # We need to control the mock session returned by get_db
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 5.0 # limit hit
    mock_session.execute.return_value = mock_result
    
    async def override_get_db():
        yield mock_session
        
    app.dependency_overrides[get_db] = override_get_db
    
    response = client.post(
        "/v1/chat/",
        json={"query": "Hello"}
    )
    
    assert response.status_code == 429
    assert "Daily LLM spend limit reached" in response.json()["detail"]["error"]
    
    # Cleanup
    app.dependency_overrides.pop(get_db, None)

@patch("app.api.chat.get_plan_limits")
def test_daily_request_limit_enforced(mock_get_limits, client: TestClient):
    # Mock plan limits
    from app.core.plan_limits import PlanLimits
    limits = PlanLimits.from_features({
        "usage": {"max_requests_per_day": 10}
    })
    mock_get_limits.return_value = limits
    
    # Mock DB results:
    # 1. Daily spend = 0
    # 2. Monthly spend = 0
    # 3. Request count = 10 (limit hit)
    mock_session = AsyncMock()
    
    mock_result_0 = MagicMock()
    mock_result_0.scalar.return_value = 0
    
    mock_result_limit = MagicMock()
    mock_result_limit.scalar.return_value = 10
    
    mock_session.execute.side_effect = [mock_result_0, mock_result_0, mock_result_limit]
    
    async def override_get_db():
        yield mock_session
        
    app.dependency_overrides[get_db] = override_get_db
    
    response = client.post(
        "/v1/chat/",
        json={"query": "Hello"}
    )
    
    assert response.status_code == 429
    assert "Daily request limit reached" in response.json()["detail"]["error"]
    
    # Cleanup
    app.dependency_overrides.pop(get_db, None)

@patch("app.utils.redis_client.redis_client", new_callable=AsyncMock)
@patch("app.services.chat_service.get_chat_completion", new_callable=AsyncMock)
@patch("app.services.chat_service.get_embedding", new_callable=AsyncMock)
@patch("app.api.chat.get_plan_limits")
def test_plan_limits_applied_to_chat(mock_get_limits, mock_embedding, mock_completion, mock_redis, client: TestClient):
    # Mock plan limits
    from app.core.plan_limits import PlanLimits
    limits = PlanLimits.from_features({
        "model_limits": {
            "max_tokens_per_request": 123,
            "max_chunks_per_query": 3,
            "allowed_models": ["gpt-4o"]
        }
    })
    mock_get_limits.return_value = limits
    
    # Bypass redis
    mock_redis.get_cache.return_value = None
    
    # Mock DB for throttler (pass all checks)
    mock_session = AsyncMock()
    mock_result_ok = MagicMock()
    mock_result_ok.scalar.return_value = 0
    mock_session.execute.return_value = mock_result_ok
    
    async def override_get_db():
        yield mock_session
    app.dependency_overrides[get_db] = override_get_db
    
    # Mock LLM calls
    mock_embedding.return_value = [0.1] * 1536
    
    mock_resp = AsyncMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Answer"))]
    mock_resp.usage.prompt_tokens = 1
    mock_resp.usage.completion_tokens = 1
    mock_resp.usage.total_tokens = 2
    mock_completion.return_value = mock_resp
    
    # Mock Celery delay to avoid actual task submission
    with patch("app.api.chat.persist_chat_response.delay") as mock_delay:
        response = client.post(
            "/v1/chat/",
            json={"query": "Hello"}
        )
    
    assert response.status_code == 200
    
    # Verify LLM was called with correct plan limits
    mock_completion.assert_called_once()
    args, kwargs = mock_completion.call_args
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["max_tokens"] == 123
    
    # Cleanup
    app.dependency_overrides.pop(get_db, None)
