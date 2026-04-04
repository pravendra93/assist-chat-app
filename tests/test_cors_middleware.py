import asyncio
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import sys
import os

# Mock settings
class MockSettings:
    PORTAL_DOMAINS = ["localhost:3000", "stage.assistra.app", "assistra.app"]

settings = MockSettings()

# The Middleware logic (copied from app/middleware/cors.py)
class DynamicCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        asst_api_key = request.headers.get("asst-api-key") or request.headers.get("ASST-API-KEY")
        
        is_trusted_origin = False
        if origin == "null":
            is_trusted_origin = True
        elif origin:
            for domain in settings.PORTAL_DOMAINS:
                if domain in origin:
                    is_trusted_origin = True
                    break

        requested_headers = request.headers.get("access-control-request-headers", "").lower()
        has_api_key_header = "asst-api-key" in requested_headers or bool(asst_api_key)
        is_allowed = is_trusted_origin or has_api_key_header

        if request.method == "OPTIONS":
            if is_allowed:
                response = Response(status_code=200)
                response.headers["Access-Control-Allow-Origin"] = origin if origin else "*"
                response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "ASST-API-KEY, Content-Type, Authorization"
                return response

        response = await call_next(request)
        if is_allowed and origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        return response

async def test_cors():
    app = FastAPI()
    app.add_middleware(DynamicCORSMiddleware)
    
    @app.get("/")
    async def root():
        return {"ok": True}

    from httpx import AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Test 1: Portal domain (localhost:3000)
        resp = await ac.options("/", headers={"Origin": "http://localhost:3000"})
        print(f"Test 1 (Portal): {resp.status_code}, CORS: {resp.headers.get('Access-Control-Allow-Origin')}")
        assert resp.headers.get('Access-Control-Allow-Origin') == "http://localhost:3000"

        # Test 2: srcdoc (origin null)
        resp = await ac.options("/", headers={"Origin": "null"})
        print(f"Test 2 (null): {resp.status_code}, CORS: {resp.headers.get('Access-Control-Allow-Origin')}")
        assert resp.headers.get('Access-Control-Allow-Origin') == "null"

        # Test 3: Unauthorized domain (evil.com)
        resp = await ac.options("/", headers={"Origin": "http://evil.com"})
        print(f"Test 3 (Evil): {resp.status_code}, CORS: {resp.headers.get('Access-Control-Allow-Origin')}")
        assert resp.headers.get('Access-Control-Allow-Origin') is None

        # Test 4: Unauthorized domain WITH ASST-API-KEY in requested headers
        resp = await ac.options("/", headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Headers": "asst-api-key, content-type"
        })
        print(f"Test 4 (Evil + Key Header): {resp.status_code}, CORS: {resp.headers.get('Access-Control-Allow-Origin')}")
        assert resp.headers.get('Access-Control-Allow-Origin') == "http://evil.com"

        # Test 5: Actual request with ASST-API-KEY
        resp = await ac.get("/", headers={"Origin": "http://evil.com", "ASST-API-KEY": "sk_test_123"})
        print(f"Test 5 (Actual + Key): {resp.status_code}, CORS: {resp.headers.get('Access-Control-Allow-Origin')}")
        assert resp.headers.get('Access-Control-Allow-Origin') == "http://evil.com"

if __name__ == "__main__":
    asyncio.run(test_cors())
