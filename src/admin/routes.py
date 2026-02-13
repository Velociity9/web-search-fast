"""Admin REST API routes — /admin/api/* endpoints."""
from __future__ import annotations

import logging
import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.admin import models, repository

logger = logging.getLogger(__name__)


def _get_admin_token() -> str:
    return os.environ.get("ADMIN_TOKEN", "")


async def _check_admin_auth(request: Request) -> JSONResponse | None:
    """Verify admin token. Returns error response or None if OK."""
    admin_token = _get_admin_token()
    if not admin_token:
        return None  # No admin token set — open access
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"error": "Missing admin token"}, status_code=401)
    if auth[7:] != admin_token:
        return JSONResponse({"error": "Invalid admin token"}, status_code=403)
    return None


# --- Stats ---

async def get_stats(request: Request) -> JSONResponse:
    if err := await _check_admin_auth(request):
        return err
    stats = await repository.get_stats()
    return JSONResponse(stats.model_dump())


# --- Search Logs ---

async def list_search_logs(request: Request) -> JSONResponse:
    if err := await _check_admin_auth(request):
        return err
    page = int(request.query_params.get("page", "1"))
    page_size = int(request.query_params.get("page_size", "20"))
    result = await repository.list_search_logs(
        page=page, page_size=page_size,
        query_filter=request.query_params.get("query"),
        ip_filter=request.query_params.get("ip"),
        key_filter=request.query_params.get("key_id"),
    )
    return JSONResponse({
        "items": [item.model_dump() for item in result.items],
        "total": result.total, "page": result.page, "page_size": result.page_size,
    })


# --- API Keys ---

async def list_keys(request: Request) -> JSONResponse:
    if err := await _check_admin_auth(request):
        return err
    keys = await repository.list_api_keys()
    return JSONResponse([k.model_dump() for k in keys])


async def create_key(request: Request) -> JSONResponse:
    if err := await _check_admin_auth(request):
        return err
    try:
        body = await request.json()
        data = models.APIKeyCreate(**body)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    key = await repository.create_api_key(
        name=data.name, call_limit=data.call_limit, expires_at=data.expires_at,
    )
    return JSONResponse(key.model_dump(), status_code=201)


async def delete_key(request: Request) -> JSONResponse:
    if err := await _check_admin_auth(request):
        return err
    key_id = request.path_params["key_id"]
    ok = await repository.revoke_api_key(key_id)
    if not ok:
        return JSONResponse({"error": "Key not found"}, status_code=404)
    return JSONResponse({"ok": True})


# --- IP Bans ---

async def list_ip_bans(request: Request) -> JSONResponse:
    if err := await _check_admin_auth(request):
        return err
    bans = await repository.list_bans()
    return JSONResponse([b.model_dump() for b in bans])


async def create_ip_ban(request: Request) -> JSONResponse:
    if err := await _check_admin_auth(request):
        return err
    try:
        body = await request.json()
        data = models.IPBanCreate(**body)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    ban = await repository.ban_ip(ip=data.ip, reason=data.reason)
    return JSONResponse(ban.model_dump(), status_code=201)


async def delete_ip_ban(request: Request) -> JSONResponse:
    if err := await _check_admin_auth(request):
        return err
    ip = request.path_params["ip"]
    ok = await repository.unban_ip(ip)
    if not ok:
        return JSONResponse({"error": "IP not found in ban list"}, status_code=404)
    return JSONResponse({"ok": True})


# --- Starlette sub-app ---

admin_routes = [
    Route("/admin/api/stats", get_stats, methods=["GET"]),
    Route("/admin/api/search-logs", list_search_logs, methods=["GET"]),
    Route("/admin/api/keys", list_keys, methods=["GET"]),
    Route("/admin/api/keys", create_key, methods=["POST"]),
    Route("/admin/api/keys/{key_id}", delete_key, methods=["DELETE"]),
    Route("/admin/api/ip-bans", list_ip_bans, methods=["GET"]),
    Route("/admin/api/ip-bans", create_ip_ban, methods=["POST"]),
    Route("/admin/api/ip-bans/{ip:path}", delete_ip_ban, methods=["DELETE"]),
]


def create_admin_app() -> Starlette:
    """Create the admin API Starlette sub-application."""
    return Starlette(routes=admin_routes)
