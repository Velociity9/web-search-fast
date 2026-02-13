"""API Key authentication middleware — validates Bearer tokens against database."""
from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that skip API key auth
_SKIP_PREFIXES = ("/admin/", "/health")


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Validate API key from Bearer token.

    Priority:
    1. Database API key lookup (if DB is available)
    2. Fallback to MCP_AUTH_TOKEN env var for backward compatibility
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path

        # Skip auth for admin routes and health checks
        for prefix in _SKIP_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        env_token = os.environ.get("MCP_AUTH_TOKEN", "")

        # If no auth configured at all, pass through
        if not env_token:
            try:
                from src.admin.repository import list_api_keys
                keys = await list_api_keys()
                if not keys:
                    return await call_next(request)
            except Exception:
                return await call_next(request)

        if not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "Missing Bearer token"}, status_code=401)

        token = auth_header[7:]

        # 1. Check env token (backward compat)
        if env_token and token == env_token:
            request.state.api_key_id = None
            return await call_next(request)

        # 2. Check database
        try:
            from src.admin.repository import increment_call_count, verify_api_key
            key = await verify_api_key(token)
            if key:
                # Check call limit
                if key.call_limit > 0 and key.call_count >= key.call_limit:
                    return JSONResponse({"error": "API key call limit exceeded"}, status_code=429)
                await increment_call_count(key.id)
                request.state.api_key_id = key.id
                return await call_next(request)
        except Exception:
            pass

        return JSONResponse({"error": "Invalid token"}, status_code=403)
