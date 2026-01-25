
from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_chat_endpoint_no_auth(client: TestClient):
    response = client.post("/v1/chat/", json={"query": "Hello"})
    assert response.status_code == 422 # Missing header

def test_chat_endpoint_success(client: TestClient):
    response = client.post(
        "/v1/chat/",
        headers={"X-API-KEY": "test-key"},
        json={"query": "Hello"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "confidence" in data
