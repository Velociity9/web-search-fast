"""Data access layer for admin operations."""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone

import aiosqlite

from src.admin.database import get_db
from src.admin.models import (
    APIKeyCreated,
    APIKeyOut,
    DashboardStats,
    IPBanOut,
    PaginatedResponse,
    SearchLogOut,
)

logger = logging.getLogger(__name__)

# Optional Redis — graceful fallback to SQLite
_redis = None


async def init_redis(url: str | None) -> None:
    """Try to connect to Redis. Non-fatal if unavailable."""
    global _redis
    if not url:
        return
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(url, decode_responses=True)
        await _redis.ping()
        logger.info("Redis connected at %s", url)
    except Exception as e:
        logger.warning("Redis unavailable (%s), falling back to SQLite", e)
        _redis = None


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


async def create_api_key(name: str, call_limit: int = 0, expires_at: str | None = None) -> APIKeyCreated:
    """Create a new API key. Returns the model WITH plaintext key (only time it's visible)."""
    db = await get_db()
    key_id = str(uuid.uuid4())
    plaintext = f"wsm_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(plaintext)
    key_prefix = plaintext[:12]
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        "INSERT INTO api_keys (id, name, key_hash, key_prefix, call_limit, call_count, is_active, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)",
        (key_id, name, key_hash, key_prefix, call_limit, now, expires_at),
    )
    await db.commit()
    return APIKeyCreated(
        id=key_id, name=name, key_prefix=key_prefix, key=plaintext,
        call_limit=call_limit, call_count=0, is_active=True,
        created_at=now, expires_at=expires_at,
    )


async def verify_api_key(token: str) -> APIKeyOut | None:
    """Verify a plaintext API key. Returns the key model if valid, None otherwise."""
    db = await get_db()
    key_hash = _hash_key(token)
    row = await db.execute_fetchall(
        "SELECT * FROM api_keys WHERE key_hash = ? AND is_active = 1", (key_hash,)
    )
    if not row:
        return None
    r = row[0]
    # Check expiration
    if r["expires_at"]:
        if datetime.fromisoformat(r["expires_at"]) < datetime.now(timezone.utc):
            return None
    return APIKeyOut(
        id=r["id"], name=r["name"], key_prefix=r["key_prefix"],
        call_limit=r["call_limit"], call_count=r["call_count"],
        is_active=bool(r["is_active"]), created_at=r["created_at"],
        expires_at=r["expires_at"],
    )


async def increment_call_count(key_id: str) -> None:
    db = await get_db()
    await db.execute("UPDATE api_keys SET call_count = call_count + 1 WHERE id = ?", (key_id,))
    await db.commit()


async def list_api_keys() -> list[APIKeyOut]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM api_keys ORDER BY created_at DESC")
    return [
        APIKeyOut(
            id=r["id"], name=r["name"], key_prefix=r["key_prefix"],
            call_limit=r["call_limit"], call_count=r["call_count"],
            is_active=bool(r["is_active"]), created_at=r["created_at"],
            expires_at=r["expires_at"],
        )
        for r in rows
    ]


async def revoke_api_key(key_id: str) -> bool:
    db = await get_db()
    cursor = await db.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
    await db.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Search Logs
# ---------------------------------------------------------------------------


async def log_search(
    query: str, ip_address: str, engine: str | None = None,
    api_key_id: str | None = None, user_agent: str | None = None,
    status_code: int | None = None, elapsed_ms: int | None = None,
    request_body: str | None = None, response_body: str | None = None,
    tool_name: str | None = None,
) -> None:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    # Truncate large bodies to 10KB to avoid bloating the DB
    if request_body and len(request_body) > 10240:
        request_body = request_body[:10240] + "...[truncated]"
    if response_body and len(response_body) > 10240:
        response_body = response_body[:10240] + "...[truncated]"
    await db.execute(
        "INSERT INTO search_logs (api_key_id, query, engine, ip_address, user_agent, "
        "status_code, elapsed_ms, request_body, response_body, tool_name, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (api_key_id, query, engine, ip_address, user_agent, status_code, elapsed_ms,
         request_body, response_body, tool_name, now),
    )
    await db.commit()


async def list_search_logs(
    page: int = 1, page_size: int = 20,
    query_filter: str | None = None, ip_filter: str | None = None,
    key_filter: str | None = None,
) -> PaginatedResponse:
    db = await get_db()
    conditions: list[str] = []
    params: list = []

    if query_filter:
        conditions.append("query LIKE ?")
        params.append(f"%{query_filter}%")
    if ip_filter:
        conditions.append("ip_address = ?")
        params.append(ip_filter)
    if key_filter:
        conditions.append("api_key_id = ?")
        params.append(key_filter)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_rows = await db.execute_fetchall(f"SELECT COUNT(*) as cnt FROM search_logs {where}", params)
    total = count_rows[0]["cnt"]

    offset = (page - 1) * page_size
    rows = await db.execute_fetchall(
        f"SELECT * FROM search_logs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    )
    items = [
        SearchLogOut(
            id=r["id"], api_key_id=r["api_key_id"], query=r["query"],
            engine=r["engine"], ip_address=r["ip_address"],
            user_agent=r["user_agent"], status_code=r["status_code"],
            elapsed_ms=r["elapsed_ms"],
            request_body=r["request_body"] if "request_body" in r.keys() else None,
            response_body=r["response_body"] if "response_body" in r.keys() else None,
            tool_name=r["tool_name"] if "tool_name" in r.keys() else None,
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# IP Bans
# ---------------------------------------------------------------------------

_REDIS_BAN_KEY = "wsm:ip:banned"


async def ban_ip(ip: str, reason: str = "") -> IPBanOut:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT OR IGNORE INTO ip_bans (ip_address, reason, created_at) VALUES (?, ?, ?)",
        (ip, reason, now),
    )
    await db.commit()
    if _redis:
        try:
            await _redis.sadd(_REDIS_BAN_KEY, ip)
        except Exception:
            pass
    rows = await db.execute_fetchall("SELECT * FROM ip_bans WHERE ip_address = ?", (ip,))
    r = rows[0]
    return IPBanOut(id=r["id"], ip_address=r["ip_address"], reason=r["reason"], created_at=r["created_at"])


async def unban_ip(ip: str) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM ip_bans WHERE ip_address = ?", (ip,))
    await db.commit()
    if _redis:
        try:
            await _redis.srem(_REDIS_BAN_KEY, ip)
        except Exception:
            pass
    return cursor.rowcount > 0


async def is_ip_banned(ip: str) -> bool:
    if _redis:
        try:
            return await _redis.sismember(_REDIS_BAN_KEY, ip)
        except Exception:
            pass
    db = await get_db()
    rows = await db.execute_fetchall("SELECT 1 FROM ip_bans WHERE ip_address = ? LIMIT 1", (ip,))
    return len(rows) > 0


async def list_bans() -> list[IPBanOut]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM ip_bans ORDER BY created_at DESC")
    return [
        IPBanOut(id=r["id"], ip_address=r["ip_address"], reason=r["reason"], created_at=r["created_at"])
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------


async def get_stats() -> DashboardStats:
    db = await get_db()
    total = (await db.execute_fetchall("SELECT COUNT(*) as cnt FROM search_logs"))[0]["cnt"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = (await db.execute_fetchall(
        "SELECT COUNT(*) as cnt FROM search_logs WHERE created_at >= ?", (today,)
    ))[0]["cnt"]
    active_keys = (await db.execute_fetchall(
        "SELECT COUNT(*) as cnt FROM api_keys WHERE is_active = 1"
    ))[0]["cnt"]
    banned = (await db.execute_fetchall("SELECT COUNT(*) as cnt FROM ip_bans"))[0]["cnt"]
    return DashboardStats(
        total_searches=total, searches_today=today_count,
        active_keys=active_keys, banned_ips=banned,
    )
