import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_cors_headers(client):
    """
    Test that CORS headers are present in the response.
    """
    response = client.options(
        "/v1/chat/",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-API-KEY",
        },
    )
    assert response.status_code == 200
    # Starlette returns the request origin if allow_origins is "*"
    allow_origin = response.headers.get("access-control-allow-origin")
    assert allow_origin == "*" or allow_origin == "http://example.com"
    assert "POST" in response.headers.get("access-control-allow-methods")


@pytest.mark.anyio
async def test_rate_limiter(client):
    """
    Test that the rate limiter blocks requests after the limit is reached.
    Note: This test assumes the rate limit is set to something low for testing or 
    we hit it quickly. In main.py it is 10 per minute.
    """
    # We need to provide valid auth for the chat endpoint unless we test a public endpoint
    # Let's test the root endpoint if it had a rate limiter, but main.py adds it to chat_router.
    # So we'll hit /v1/chat/ multiple times.
    
    # Actually, to make this test robust in a CI/unit test environment without a real Redis 
    # that persists state between tests, we might want to mock the limiter OR 
    # run this in the docker environment where Redis is fresh.
    
    # Let's try to hit it 11 times. The 11th should fail with 429.
    # We don't care about the actual auth here because the RateLimiter dependency 
    # is checked BEFORE the require_tenant_api_key dependency (since it's in the router dependencies list).
    
    for i in range(10):
        response = client.post("/v1/chat/", json={"query": "test"})
        # It might be 422 if we don't provide JSON or 401 if auth fails, 
        # but it should NOT be 429 yet.
        assert response.status_code != 429

    response = client.post("/v1/chat/", json={"query": "test"})
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"
