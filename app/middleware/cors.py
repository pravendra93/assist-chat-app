from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings

class DynamicCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """
        Custom CORS middleware that allows:
        1. PORTAL_DOMAINS (localhost:3000, stage.assistra.app, assistra.app)
        2. null origin (for srcdoc iframes)
        3. Requests with a valid ASST-API-KEY header
        """
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        asst_api_key = request.headers.get("asst-api-key") or request.headers.get("ASST-API-KEY")
        
        # Consider origin null (srcdoc) or portal domains as trusted
        is_trusted_origin = False
        if origin == "null":
            is_trusted_origin = True
        elif origin:
            for domain in settings.PORTAL_DOMAINS:
                if domain in origin:
                    is_trusted_origin = True
                    break
        elif referer:
            for domain in settings.PORTAL_DOMAINS:
                if domain in referer:
                    is_trusted_origin = True
                    break

        # Check if the ASST-API-KEY is being requested or present
        requested_headers = request.headers.get("access-control-request-headers", "").lower()
        has_api_key_header = "asst-api-key" in requested_headers or bool(asst_api_key)
        
        # Allowed if trusted origin OR has API key
        is_allowed = is_trusted_origin or has_api_key_header

        if request.method == "OPTIONS":
            if is_allowed:
                response = Response(status_code=200)
                # If origin is null, we must return "null" or "*"
                allowed_origin = origin if origin else "*"
                response.headers["Access-Control-Allow-Origin"] = allowed_origin
                response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "ASST-API-KEY, Content-Type, Authorization, Internal-Cache-Header"
                response.headers["Access-Control-Max-Age"] = "86400"
                return response

        response = await call_next(request)
        
        if is_allowed and origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        elif is_allowed and not origin:
            # For non-browser requests that might still need CORS headers for some reason
            response.headers["Access-Control-Allow-Origin"] = "*"

        return response
