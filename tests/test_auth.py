"""Tests for Bearer token auth middleware."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def _make_app(token: str = "") -> TestClient:
    """Create a test Starlette app with TokenAuthMiddleware."""

    async def homepage(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", homepage)])

    with patch.dict(os.environ, {"MCP_AUTH_TOKEN": token}):
        # Re-import to pick up patched env
        import importlib

        import src.auth as auth_mod

        importlib.reload(auth_mod)
        app.add_middleware(auth_mod.TokenAuthMiddleware)

    return TestClient(app)


class TestAuthDisabled:
    """When MCP_AUTH_TOKEN is empty, all requests pass through."""

    def test_no_token_required(self) -> None:
        client = _make_app("")
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.text == "ok"


class TestAuthEnabled:
    """When MCP_AUTH_TOKEN is set, Bearer token is required."""

    def test_missing_header_returns_401(self) -> None:
        client = _make_app("secret-token-123")
        resp = client.get("/")
        assert resp.status_code == 401

    def test_wrong_token_returns_403(self) -> None:
        client = _make_app("secret-token-123")
        resp = client.get("/", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 403

    def test_valid_token_passes(self) -> None:
        client = _make_app("secret-token-123")
        resp = client.get("/", headers={"Authorization": "Bearer secret-token-123"})
        assert resp.status_code == 200
        assert resp.text == "ok"

    def test_malformed_header_returns_401(self) -> None:
        client = _make_app("secret-token-123")
        resp = client.get("/", headers={"Authorization": "Basic abc123"})
        assert resp.status_code == 401
