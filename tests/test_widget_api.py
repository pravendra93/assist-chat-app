
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.auth.api_key import require_tenant_api_key
from app.db.models import Tenant, ApiKey
from app.db.session import get_db
import uuid

# Create reusable mock objects
mock_tenant_id = uuid.uuid4()

def create_mock_tenant():
    return Tenant(
        id=mock_tenant_id,
        name="Test Tenant",
        is_trial=False
    )

def create_mock_api_key():
    return ApiKey(
        id=uuid.uuid4(),
        tenant_id=mock_tenant_id,
        is_active=True
    )

async def mock_auth():
    return create_mock_tenant(), create_mock_api_key()

# Override auth for all tests in this file
app.dependency_overrides[require_tenant_api_key] = mock_auth

@patch("app.api.chat.get_plan_limits")
@patch("app.utils.redis_client.redis_client", new_callable=AsyncMock)
def test_get_widget_config_success(mock_redis, mock_get_limits, client: TestClient):
    # Mock plan limits
    from app.core.plan_limits import PlanLimits
    mock_get_limits.return_value = PlanLimits.from_features({})
    
    # Mock redis (cache miss)
    mock_redis.get_cache.return_value = None
    
    # Mock DB
    mock_session = AsyncMock()
    
    # 2a. ChatbotConfig result (None)
    mock_chatbot_result = MagicMock()
    mock_chatbot_result.scalars().first.return_value = None
    
    # 2b. TenantConfig result (Empty)
    mock_tenant_result = MagicMock()
    mock_tenant_result.scalars().all.return_value = []
    
    # Side effects for DB executions
    mock_session.execute.side_effect = [mock_chatbot_result, mock_tenant_result]
    
    async def override_get_db():
        yield mock_session
    app.dependency_overrides[get_db] = override_get_db
    
    response = client.get(
        "/v1/widget/config",
        headers={"ASST-API-KEY": "sk_live_123456789012"}
    )
    
    # If the fix works, this should be 200.
    # If the fix is missing, FastAPI will throw ResponseValidationError (500 in TestClient)
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(mock_tenant_id)
    assert "chat_title" in data
    assert "primary_color" in data
    
    # Cleanup
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_tenant_api_key, None)
