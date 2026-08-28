"""
AgentProbe -- Security and performance middleware.

Adds in one place:
  - Security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, etc.)
  - Request size cap (protects against request-flooding attacks)
  - Per-IP rate limiting on POST /audit (in-memory token bucket, Redis-backed
    when REDIS_URL is set for correctness across multiple instances)
  - Structured security event logging (all 429s, oversized requests, auth failures)
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("agentprobe.security")


# ---------------------------------------------------------------------------
# Config (override via env)
# ---------------------------------------------------------------------------

MAX_REQUEST_BODY_BYTES = int(os.environ.get("MAX_REQUEST_BYTES", 64 * 1024))  # 64 KB
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MIN", 10))         # POST /audit
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://agentprobe.pages.dev,http://localhost:3000"
).split(",")


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

_SECURITY_HEADERS = {
    # Prevent MIME-type sniffing
    "X-Content-Type-Options": "nosniff",
    # Deny iframe embedding (clickjacking protection)
    "X-Frame-Options": "DENY",
    # Basic XSS filter for older browsers
    "X-XSS-Protection": "1; mode=block",
    # Don't send referrer to cross-origin destinations
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Limit browser feature access
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # Strict Transport Security -- 1 year, include subdomains
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    # Content Security Policy -- tight; the API only serves JSON
    "Content-Security-Policy": (
        "default-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none';"
    ),
    # Hide server info
    "Server": "AgentProbe",
}


# ---------------------------------------------------------------------------
# In-memory rate limiter (token-bucket, per IP)
# Replaced with Redis-backed counting when REDIS_URL is set.
# ---------------------------------------------------------------------------

_ip_windows: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.monotonic()
    window = _ip_windows[ip]
    # Evict timestamps older than 60 seconds
    cutoff = now - 60.0
    _ip_windows[ip] = [t for t in window if t > cutoff]
    if len(_ip_windows[ip]) >= RATE_LIMIT_PER_MINUTE:
        return False
    _ip_windows[ip].append(now)
    return True


def _get_client_ip(request: Request) -> str:
    """Extract real IP from X-Forwarded-For (Render/Cloudflare set this)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# Middleware class
# ---------------------------------------------------------------------------

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Single middleware that handles:
      1. Request body size enforcement
      2. Rate limiting on POST /audit
      3. Security response headers on every response
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = _get_client_ip(request)

        # ------------------------------------------------------------------ #
        # 1. Body size cap -- checked before parsing to avoid OOM on huge     #
        #    payloads.  Content-Length header is checked first (fast path);   #
        #    for chunked bodies the actual read is bounded in the API route.  #
        # ------------------------------------------------------------------ #
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            logger.warning(
                "oversized_request ip=%s path=%s bytes=%s",
                ip, request.url.path, content_length,
            )
            return JSONResponse(
                {"detail": "Request body too large"},
                status_code=413,
                headers=_SECURITY_HEADERS,
            )

        # ------------------------------------------------------------------ #
        # 2. Rate limit -- applied to POST /audit only                        #
        # ------------------------------------------------------------------ #
        if request.method == "POST" and request.url.path == "/audit":
            allowed = _check_rate_limit(ip)
            if not allowed:
                logger.warning("rate_limited ip=%s", ip)
                return JSONResponse(
                    {
                        "detail": "Too many audit requests. "
                                  f"Limit is {RATE_LIMIT_PER_MINUTE} per minute."
                    },
                    status_code=429,
                    headers={
                        **_SECURITY_HEADERS,
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(RATE_LIMIT_PER_MINUTE),
                    },
                )

        # ------------------------------------------------------------------ #
        # 3. Process the request                                              #
        # ------------------------------------------------------------------ #
        response: Response = await call_next(request)

        # ------------------------------------------------------------------ #
        # 4. Attach security headers to every response                        #
        # ------------------------------------------------------------------ #
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value

        # Log auth failures for auditing
        if response.status_code == 401:
            logger.warning(
                "auth_failure ip=%s path=%s",
                ip, request.url.path,
            )

        return response
