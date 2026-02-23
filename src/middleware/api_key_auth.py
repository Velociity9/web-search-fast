"""API Key authentication middleware — validates Bearer tokens against database."""
from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that skip API key auth (health/pool endpoints only)
_SKIP_PREFIXES = ("/health", "/pool/")

# Admin static assets don't need auth (JS/CSS/images)
_ADMIN_STATIC_PREFIXES = ("/admin/assets/",)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Validate API key from Bearer token.

    Priority:
    1. ADMIN_TOKEN env var (for admin panel access)
    2. MCP_AUTH_TOKEN env var (for MCP/search API backward compatibility)
    3. Database API key lookup
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path

        # Skip auth for health checks and pool stats
        for prefix in _SKIP_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Skip auth for admin static assets (JS, CSS, images)
        for prefix in _ADMIN_STATIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Admin SPA HTML pages (not /admin/api/*) — skip auth so the SPA can load,
        # the SPA itself will call /admin/api/* with the token
        if path.startswith("/admin") and not path.startswith("/admin/api/"):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        env_token = os.environ.get("MCP_AUTH_TOKEN", "")
        admin_token = os.environ.get("ADMIN_TOKEN", "")

        # If no auth configured at all (no env tokens and no DB keys), pass through
        if not env_token and not admin_token:
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

        # 1. Check ADMIN_TOKEN (admin panel access)
        if admin_token and token == admin_token:
            request.state.api_key_id = None
            return await call_next(request)

        # 2. Check MCP_AUTH_TOKEN (backward compat)
        if env_token and token == env_token:
            request.state.api_key_id = None
            return await call_next(request)

        # 3. Check database API keys
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
