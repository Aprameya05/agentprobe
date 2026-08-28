"""
AgentProbe -- Redis caching layer (Upstash free tier).

Wraps redis.asyncio with a graceful no-op fallback so the API still
works when REDIS_URL is not set (dev mode or free tier without Redis).

Cache keys:
  leaderboard:<limit>            TTL 60s  -- top ARS list
  audit:<audit_id>               TTL 300s -- completed audit report
  audit:<audit_id>:events:<n>   TTL 120s -- event poll responses

Usage:
  from .cache import cache
  value = await cache.get("key")
  await cache.set("key", json.dumps(data), ttl=60)
  await cache.delete("key")
  await cache.invalidate_audit(audit_id)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_REDIS_URL = os.environ.get("REDIS_URL", "")


class _NoopCache:
    """Returned when Redis is not configured. All operations are no-ops."""

    async def get(self, key: str) -> Optional[str]:
        return None

    async def set(self, key: str, value: str, ttl: int = 60) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def invalidate_audit(self, audit_id: str) -> None:
        pass

    async def close(self) -> None:
        pass

    @property
    def available(self) -> bool:
        return False


class _RedisCache:
    def __init__(self, url: str) -> None:
        import redis.asyncio as aioredis  # type: ignore
        self._client = aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

    async def get(self, key: str) -> Optional[str]:
        try:
            return await self._client.get(key)
        except Exception as exc:
            logger.warning("cache get failed: %s", exc)
            return None

    async def set(self, key: str, value: str, ttl: int = 60) -> None:
        try:
            await self._client.setex(key, ttl, value)
        except Exception as exc:
            logger.warning("cache set failed: %s", exc)

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except Exception as exc:
            logger.warning("cache delete failed: %s", exc)

    async def invalidate_audit(self, audit_id: str) -> None:
        """Bust all cache keys for a given audit."""
        await self.delete(f"audit:{audit_id}")
        # events-poll keys have a variable suffix -- use SCAN to find them
        try:
            cursor = 0
            while True:
                cursor, keys = await self._client.scan(
                    cursor, match=f"audit:{audit_id}:*", count=50
                )
                if keys:
                    await self._client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.warning("cache invalidate_audit failed: %s", exc)

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:
            pass

    @property
    def available(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Module-level singleton -- import this everywhere
# ---------------------------------------------------------------------------

def _build_cache() -> _RedisCache | _NoopCache:
    if _REDIS_URL:
        try:
            c = _RedisCache(_REDIS_URL)
            logger.info("Redis cache initialised (%s)", _REDIS_URL.split("@")[-1])
            return c
        except Exception as exc:
            logger.warning("Redis init failed, using no-op cache: %s", exc)
    return _NoopCache()


cache: _RedisCache | _NoopCache = _build_cache()


# ---------------------------------------------------------------------------
# Convenience helpers used by routes
# ---------------------------------------------------------------------------

async def cached_json(key: str, ttl: int, factory) -> Any:
    """
    Return the cached JSON value for `key`, or call `factory()` to produce
    it, store it, and return it.

    factory must be an async callable returning a JSON-serialisable value.
    """
    raw = await cache.get(key)
    if raw is not None:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

    value = await factory()
    try:
        await cache.set(key, json.dumps(value), ttl=ttl)
    except Exception:
        pass
    return value
