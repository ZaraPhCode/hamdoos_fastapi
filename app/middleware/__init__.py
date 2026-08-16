"""Middleware — error handling, logging, rate limiting, security, localization."""

from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
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

    def _forbidden_response(self) -> Response:
        try:
            with open("app/templates/errors/403.html", "r", encoding="utf-8") as f:
                return HTMLResponse(f.read(), status_code=403)
        except Exception:
            return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from starlette.responses import RedirectResponse
        try:
            response = await call_next(request)
            if request.url.path.startswith("/administration"):
                if response.status_code == 401 and request.url.path != "/administration/login":
                    login_url = f"/login?next={request.url.path}"
                    return RedirectResponse(url=login_url, status_code=302)
                if response.status_code == 403 and request.url.path != "/administration/login":
                    return self._forbidden_response()
            return response
        except HTTPException as e:
            if request.url.path.startswith("/administration") and request.url.path != "/administration/login":
                if e.status_code == 401:
                    login_url = f"/login?next={request.url.path}"
                    return RedirectResponse(url=login_url, status_code=302)
                if e.status_code == 403:
                    return self._forbidden_response()
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


class SiteSettingsMiddleware(BaseHTTPMiddleware):
    """Load the site settings / theme once per request so templates (footer,
    footer modals, sidebar) read from the DB instead of hard-coded text.

    ``request.state.site_settings`` is the admin-editable ``SiteSetting`` row
    (``None`` if the DB has none yet); ``request.state.site_config`` exposes the
    reusable theme/default info from ``app/config/site_config.py``.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from sqlalchemy import select

        from app.config.site_config import SITE_INFO, THEME
        from app.database import async_session_factory
        from app.models.common import SiteSetting

        path = request.url.path
        needs_settings = not any(
            path.startswith(prefix)
            for prefix in ("/static", "/media", "/api", "/docs", "/redoc", "/health")
        )
        site_settings = None
        if needs_settings:
            try:
                async with async_session_factory() as db:
                    result = await db.execute(
                        select(SiteSetting).where(SiteSetting.is_removed == False).limit(1)
                    )
                    site_settings = result.scalar_one_or_none()
            except Exception:
                site_settings = None

        request.state.site_settings = site_settings
        request.state.site_config = {"THEME": THEME, "SITE_INFO": SITE_INFO}
        response = await call_next(request)
        return response


def register_middleware(app: FastAPI):
    """Register all middleware in the correct order."""
    app.add_middleware(SiteSettingsMiddleware)
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