import pytest
from httpx import AsyncClient
from app.main import app
from app.core.config import settings
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_invalidate_cache_success():
    """Test successful cache invalidation with correct header."""
    # Mock settings to have a known header value
    with patch.object(settings, "INTERNAL_CACHE_HEADER", "test-secret"):
        with patch("app.services.widget_service.widget_service.invalidate_cache", new_callable=AsyncMock) as mock_invalidate:
            async with AsyncClient(app=app, base_url="http://test") as ac:
                response = await ac.post(
                    "/v1/internal/cache-invalidate?tenant_id=test-tenant",
                    headers={"INTERNAL_CACHE_HEADER": "test-secret"}
                )
            
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            mock_invalidate.assert_called_once_with("test-tenant")

@pytest.mark.asyncio
async def test_invalidate_cache_unauthorized_missing_header():
    """Test 401 when header is missing."""
    with patch.object(settings, "INTERNAL_CACHE_HEADER", "test-secret"):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/v1/internal/cache-invalidate?tenant_id=test-tenant")
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"

@pytest.mark.asyncio
async def test_invalidate_cache_unauthorized_wrong_header():
    """Test 401 when header value is incorrect."""
    with patch.object(settings, "INTERNAL_CACHE_HEADER", "test-secret"):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/v1/internal/cache-invalidate?tenant_id=test-tenant",
                headers={"INTERNAL_CACHE_HEADER": "wrong-secret"}
            )
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"

@pytest.mark.asyncio
async def test_invalidate_cache_unauthorized_no_env_configured():
    """Test 401 when INTERNAL_CACHE_HEADER is not set in env."""
    with patch.object(settings, "INTERNAL_CACHE_HEADER", None):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/v1/internal/cache-invalidate?tenant_id=test-tenant",
                headers={"INTERNAL_CACHE_HEADER": "any-value"}
            )
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"
