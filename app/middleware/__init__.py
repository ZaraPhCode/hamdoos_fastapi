"""Middleware — error handling, logging, rate limiting, security, localization."""

from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all incoming requests and their durations."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        logger.info(
            f"[{request_id}] {request.method} {request.url.path} "
            f"→ {response.status_code} ({duration:.3f}s)"
        )
        response.headers["X-Request-ID"] = request_id
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global error handler — catches unhandled exceptions and redirects admin auth errors."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from starlette.responses import RedirectResponse
        try:
            response = await call_next(request)
            if response.status_code in (401, 403) and request.url.path.startswith("/administration"):
                if request.url.path == "/administration/login":
                    return response
                login_url = f"/administration/login?next={request.url.path}"
                return RedirectResponse(url=login_url, status_code=302)
            return response
        except HTTPException as e:
            if e.status_code in (401, 403) and request.url.path.startswith("/administration") and request.url.path != "/administration/login":
                login_url = f"/administration/login?next={request.url.path}"
                return RedirectResponse(url=login_url, status_code=302)
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        except Exception as e:
            logger.exception(f"Unhandled error: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request.headers.get("X-Request-ID", ""),
                },
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY" if not request.url.path.startswith("/administration") else "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class LocalizationMiddleware(BaseHTTPMiddleware):
    """Detect user language from Accept-Language header or cookie."""

    SUPPORTED_LOCALES = ["fa", "en"]
    DEFAULT_LOCALE = "fa"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        locale = request.cookies.get("locale", "")
        if not locale or locale not in self.SUPPORTED_LOCALES:
            accept_lang = request.headers.get("Accept-Language", "")
            if accept_lang:
                for lang in self.SUPPORTED_LOCALES:
                    if lang in accept_lang:
                        locale = lang
                        break
            if not locale:
                locale = self.DEFAULT_LOCALE

        request.state.locale = locale
        response = await call_next(request)
        return response


def register_middleware(app: FastAPI):
    """Register all middleware in the correct order."""
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(LocalizationMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key="asha-shop-session-secret-change-in-production",
        session_cookie="asha_session",
        max_age=7200,
        same_site="lax",
    )