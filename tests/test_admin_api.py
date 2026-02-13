"""Tests for admin REST API endpoints."""
from __future__ import annotations

import os
import tempfile

import pytest
from starlette.testclient import TestClient

from src.admin.database import close_db, init_db
from src.admin.routes import admin_routes

ADMIN_TOKEN = "test-admin-token-123"


@pytest.fixture(autouse=True)
async def _setup_db():
    """Create a fresh in-memory-like temp DB for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    await init_db(db_path)
    yield
    await close_db()
    os.unlink(db_path)


@pytest.fixture()
def client():
    from starlette.applications import Starlette
    app = Starlette(routes=admin_routes)
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


class TestStatsEndpoint:
    def test_get_stats(self, client, auth_headers):
        with _patch_admin_token():
            resp = client.get("/admin/api/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_searches" in data
        assert "active_keys" in data
        assert "banned_ips" in data

    def test_stats_no_auth_when_no_token(self, client):
        with _patch_admin_token(""):
            resp = client.get("/admin/api/stats")
        assert resp.status_code == 200


class TestAPIKeysEndpoints:
    def test_create_and_list_keys(self, client, auth_headers):
        with _patch_admin_token():
            resp = client.post(
                "/admin/api/keys",
                json={"name": "test-key", "call_limit": 100},
                headers=auth_headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["name"] == "test-key"
            assert data["call_limit"] == 100
            assert "key" in data  # plaintext key returned on creation
            assert data["key"].startswith("wsm_")

            # List keys
            resp = client.get("/admin/api/keys", headers=auth_headers)
            assert resp.status_code == 200
            keys = resp.json()
            assert len(keys) == 1
            assert keys[0]["name"] == "test-key"
            assert "key" not in keys[0]  # plaintext NOT in list

    def test_revoke_key(self, client, auth_headers):
        with _patch_admin_token():
            resp = client.post(
                "/admin/api/keys",
                json={"name": "to-revoke"},
                headers=auth_headers,
            )
            key_id = resp.json()["id"]

            resp = client.delete(f"/admin/api/keys/{key_id}", headers=auth_headers)
            assert resp.status_code == 200

            # Verify it's revoked
            resp = client.get("/admin/api/keys", headers=auth_headers)
            keys = resp.json()
            assert keys[0]["is_active"] is False

    def test_revoke_nonexistent_key(self, client, auth_headers):
        with _patch_admin_token():
            resp = client.delete(
                "/admin/api/keys/nonexistent-id", headers=auth_headers
            )
            assert resp.status_code == 404

    def test_create_key_invalid_body(self, client, auth_headers):
        with _patch_admin_token():
            resp = client.post(
                "/admin/api/keys", json={}, headers=auth_headers
            )
            assert resp.status_code == 400


# PLACEHOLDER_MORE_TESTS


class TestIPBansEndpoints:
    def test_ban_and_list(self, client, auth_headers):
        with _patch_admin_token():
            resp = client.post(
                "/admin/api/ip-bans",
                json={"ip": "10.0.0.1", "reason": "spam"},
                headers=auth_headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["ip_address"] == "10.0.0.1"
            assert data["reason"] == "spam"

            resp = client.get("/admin/api/ip-bans", headers=auth_headers)
            assert resp.status_code == 200
            bans = resp.json()
            assert len(bans) == 1

    def test_unban(self, client, auth_headers):
        with _patch_admin_token():
            client.post(
                "/admin/api/ip-bans",
                json={"ip": "10.0.0.2"},
                headers=auth_headers,
            )
            resp = client.delete("/admin/api/ip-bans/10.0.0.2", headers=auth_headers)
            assert resp.status_code == 200

            resp = client.get("/admin/api/ip-bans", headers=auth_headers)
            assert len(resp.json()) == 0

    def test_unban_nonexistent(self, client, auth_headers):
        with _patch_admin_token():
            resp = client.delete("/admin/api/ip-bans/99.99.99.99", headers=auth_headers)
            assert resp.status_code == 404


class TestSearchLogsEndpoint:
    @pytest.mark.asyncio
    async def test_list_logs(self, client, auth_headers):
        from src.admin.repository import log_search
        await log_search(query="test query", ip_address="1.2.3.4", engine="google")

        with _patch_admin_token():
            resp = client.get("/admin/api/search-logs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["query"] == "test query"

    @pytest.mark.asyncio
    async def test_filter_by_ip(self, client, auth_headers):
        from src.admin.repository import log_search
        await log_search(query="q1", ip_address="1.1.1.1")
        await log_search(query="q2", ip_address="2.2.2.2")

        with _patch_admin_token():
            resp = client.get("/admin/api/search-logs?ip=1.1.1.1", headers=auth_headers)
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["ip_address"] == "1.1.1.1"


class TestAdminAuth:
    def test_wrong_admin_token_rejected(self, client):
        with _patch_admin_token():
            resp = client.get(
                "/admin/api/stats",
                headers={"Authorization": "Bearer wrong-token"},
            )
            assert resp.status_code == 403

    def test_missing_admin_token_rejected(self, client):
        with _patch_admin_token():
            resp = client.get("/admin/api/stats")
            assert resp.status_code == 401


# --- Helpers ---

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def _patch_admin_token(token: str = ADMIN_TOKEN):
    with patch.dict(os.environ, {"ADMIN_TOKEN": token}):
        yield
