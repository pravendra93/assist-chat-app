
import pytest
from fastapi import Request, HTTPException
from unittest.mock import AsyncMock, MagicMock
from app.auth.api_key import require_tenant_api_key
from app.db.models import Tenant, ApiKey, TenantConfig
import uuid
import anyio

# Helper functions to create mock models
def create_mock_tenant(tenant_id):
    return Tenant(
        id=tenant_id,
        name="Test Tenant",
        is_trial=False,
        is_installed=True
    )

def create_mock_api_key(tenant_id):
    return ApiKey(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        is_active=True,
        api_key_hash="hashed_key",
        key_prefix="sk_live_1234"
    )

def create_mock_tenant_config(tenant_id, domain):
    return TenantConfig(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        domain=domain
    )

def test_require_tenant_api_key_direct_success(mocker):
    tenant_id = uuid.uuid4()
    tenant = create_mock_tenant(tenant_id)
    api_key = create_mock_api_key(tenant_id)
    config = create_mock_tenant_config(tenant_id, "example.com")
    
    mocker.patch("app.auth.api_key.verify_api_key", return_value=True)
    mocker.patch("app.auth.api_key.func.now", return_value=None) # Avoid actual SQL func
    
    # Mock DB
    mock_db = AsyncMock()
    mock_result_api = MagicMock()
    mock_result_api.scalars.return_value.all.return_value = [api_key]
    mock_result_tenant = MagicMock()
    mock_result_tenant.scalars.return_value.first.return_value = tenant
    mock_result_config = MagicMock()
    mock_result_config.scalars.return_value.all.return_value = [config]
    
    mock_db.execute.side_effect = [mock_result_api, mock_result_tenant, mock_result_config]
    
    # Mock Request
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"origin": "https://example.com"}
    
    async def run():
        return await require_tenant_api_key(
            request=mock_request,
            asst_api_key="sk_live_123456789012",
            db=mock_db
        )
    
    result_tenant, result_api_key = anyio.run(run)
    
    assert result_tenant.id == tenant_id
    assert result_api_key.id == api_key.id

def test_require_tenant_api_key_direct_failure_mismatch(mocker):
    tenant_id = uuid.uuid4()
    tenant = create_mock_tenant(tenant_id)
    api_key = create_mock_api_key(tenant_id)
    config = create_mock_tenant_config(tenant_id, "example.com")
    
    mocker.patch("app.auth.api_key.verify_api_key", return_value=True)
    
    # Mock DB
    mock_db = AsyncMock()
    mock_result_api = MagicMock()
    mock_result_api.scalars.return_value.all.return_value = [api_key]
    mock_result_tenant = MagicMock()
    mock_result_tenant.scalars.return_value.first.return_value = tenant
    mock_result_config = MagicMock()
    mock_result_config.scalars.return_value.all.return_value = [config]
    
    mock_db.execute.side_effect = [mock_result_api, mock_result_tenant, mock_result_config]
    
    # Mock Request
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"origin": "https://wrong.com"}
    
    async def run():
        await require_tenant_api_key(
            request=mock_request,
            asst_api_key="sk_live_123456789012",
            db=mock_db
        )
        
    with pytest.raises(HTTPException) as exc:
        anyio.run(run)
    assert exc.value.status_code == 401

def test_require_tenant_api_key_direct_no_config(mocker):
    tenant_id = uuid.uuid4()
    tenant = create_mock_tenant(tenant_id)
    api_key = create_mock_api_key(tenant_id)
    
    mocker.patch("app.auth.api_key.verify_api_key", return_value=True)
    
    # Mock DB
    mock_db = AsyncMock()
    mock_result_api = MagicMock()
    mock_result_api.scalars.return_value.all.return_value = [api_key]
    mock_result_tenant = MagicMock()
    mock_result_tenant.scalars.return_value.first.return_value = tenant
    mock_result_config = MagicMock()
    mock_result_config.scalars.return_value.all.return_value = []
    
    mock_db.execute.side_effect = [mock_result_api, mock_result_tenant, mock_result_config]
    
    # Mock Request
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"origin": "https://example.com"}
    
    async def run():
        await require_tenant_api_key(
            request=mock_request,
            asst_api_key="sk_live_123456789012",
            db=mock_db
        )
        
    with pytest.raises(HTTPException) as exc:
        anyio.run(run)
    assert exc.value.status_code == 401

def test_require_tenant_api_key_direct_www_stripping(mocker):
    tenant_id = uuid.uuid4()
    tenant = create_mock_tenant(tenant_id)
    api_key = create_mock_api_key(tenant_id)
    config = create_mock_tenant_config(tenant_id, "example.com")
    
    mocker.patch("app.auth.api_key.verify_api_key", return_value=True)
    mocker.patch("app.auth.api_key.func.now", return_value=None)
    
    # Mock DB
    mock_db = AsyncMock()
    mock_result_api = MagicMock()
    mock_result_api.scalars.return_value.all.return_value = [api_key]
    mock_result_tenant = MagicMock()
    mock_result_tenant.scalars.return_value.first.return_value = tenant
    mock_result_config = MagicMock()
    mock_result_config.scalars.return_value.all.return_value = [config]
    
    mock_db.execute.side_effect = [mock_result_api, mock_result_tenant, mock_result_config]
    
    # Mock Request with www
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"origin": "https://www.example.com"}
    
    async def run():
        return await require_tenant_api_key(
            request=mock_request,
            asst_api_key="sk_live_123456789012",
            db=mock_db
        )
    
    result_tenant, result_api_key = anyio.run(run)
    
    assert result_tenant.id == tenant_id
    assert result_api_key.id == api_key.id
