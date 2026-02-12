"""Bearer token authentication middleware for MCP HTTP transport."""
from __future__ import annotations

import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Read token from environment — if empty/unset, auth is disabled
MCP_AUTH_TOKEN: str = os.environ.get("MCP_AUTH_TOKEN", "")


def is_auth_enabled() -> bool:
    return bool(MCP_AUTH_TOKEN)


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Validate Bearer token on every request when MCP_AUTH_TOKEN is set."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not is_auth_enabled():
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Missing or malformed Authorization header from %s", request.client)
            return JSONResponse({"error": "Missing Bearer token"}, status_code=401)

        token = auth_header[7:]  # strip "Bearer "
        if token != MCP_AUTH_TOKEN:
            logger.warning("Invalid token from %s", request.client)
            return JSONResponse({"error": "Invalid token"}, status_code=403)

        return await call_next(request)
