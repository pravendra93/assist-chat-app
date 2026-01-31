import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException, status

# Set dummy env var to avoid RuntimeError on import
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/db"

from app.auth.api_key import require_tenant_api_key, Tenant

# We simulate the DB session
@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_require_tenant_api_key_success(mock_db):
    # Setup mock query result
    mock_result = MagicMock()
    # Return valid tenant: id, daily_limit, status
    mock_result.first.return_value = ("tenant-123", 50.0, "active")
    mock_db.execute.return_value = mock_result

    # Patch enforce_cost_limit to do nothing
    with patch("app.auth.api_key.enforce_cost_limit", new_callable=AsyncMock) as mock_cost:
        tenant = await require_tenant_api_key("valid-key", db=mock_db)
        
        assert isinstance(tenant, Tenant)
        assert tenant.id == "tenant-123"
        assert tenant.daily_cost_limit == 50.0
        
        # Verify SQL query was executed
        assert mock_db.execute.called
        
        # Verify cost limit was called
        mock_cost.assert_called_once()
        assert mock_cost.call_args[0][0] == tenant

@pytest.mark.anyio
async def test_require_tenant_api_key_invalid_key(mock_db):
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc:
        await require_tenant_api_key("bad-key", db=mock_db)
    
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc.value.detail == "Invalid API key"

@pytest.mark.anyio
async def test_require_tenant_api_key_inactive_subscription(mock_db):
    mock_result = MagicMock()
    mock_result.first.return_value = ("tenant-123", 50.0, "canceled")
    mock_db.execute.return_value = mock_result

    with pytest.raises(HTTPException) as exc:
        await require_tenant_api_key("valid-key", db=mock_db)
    
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Subscription inactive" in exc.value.detail
