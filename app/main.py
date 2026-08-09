# Asha Shop API

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import os

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.config.settings import settings
from app.api.v1.auth import router as auth_router
from app.api.v1.products import router as products_router
from app.api.v1.categories import router as categories_router
from app.api.v1.brands import router as brands_router
from app.api.v1.cart import router as cart_router
from app.api.v1.orders import router as orders_router
from app.api.v1.admin import router as admin_api_router
from app.api.v1.admin_pages import router as admin_pages_router
from app.api.v1.payments import router as payments_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.invoices import router as invoices_router
from app.api.v1.purchase_orders import router as purchase_orders_router
from app.api.v1.tickets import router as tickets_router
from app.api.v1.chats import router as chats_router
from app.api.v1.wallet import router as wallet_router
from app.api.v1.finance import router as finance_router
from app.api.v1.warehouse import router as warehouse_router
from app.api.v1.seo import router as seo_router
from app.api.v1.export import router as export_router
from app.routes.shop_pages import router as shop_pages_router
from app.routes.shop_auth import router as shop_auth_router
from app.api.v1.notify import router as notify_router
from app.middleware import register_middleware
from app.utils.common_works import TimedHostedService

background_service: TimedHostedService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_service
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode")
    # Start background service for back-in-stock notifications
    background_service = TimedHostedService(interval_seconds=3600)
    await background_service.start()
    yield
    if background_service:
        await background_service.stop()
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Serve uploaded product/media files under /media.
# Preference order:
#   1. external volume /app/media (mounted from the old .NET wwwroot/Media)
#   2. bundled copy app/static/Media (shipped with the repo/image)
# If the file exists in neither and MEDIA_BASE_URL is set (old site still
# hosting the files), redirect to the given origin so images keep working on a
# fresh VPS before the full Media folder is copied over.
@app.get("/media/{file_path:path}")
async def media_files(file_path: str):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import RedirectResponse, FileResponse, JSONResponse

    normalized = file_path.replace("\\", "/").lstrip("/")
    for root in ("/app/media", "app/static/Media"):
        candidate = os.path.join(root, normalized)
        if os.path.isfile(candidate):
            return FileResponse(candidate)

    base = (settings.MEDIA_BASE_URL or "").rstrip("/")
    if base:
        return RedirectResponse(url=f"{base}/Media/{normalized}", status_code=301)
    return JSONResponse({"detail": "File not found"}, status_code=404)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(brands_router, prefix="/api/v1")
app.include_router(cart_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(admin_api_router, prefix="/api/v1")
app.include_router(admin_pages_router)
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(chats_router, prefix="/api/v1")
app.include_router(invoices_router, prefix="/api/v1")
app.include_router(purchase_orders_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(shop_pages_router)
app.include_router(shop_auth_router)
app.include_router(seo_router)
app.include_router(export_router, prefix="/api/v1")
app.include_router(warehouse_router, prefix="/api/v1")
app.include_router(wallet_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(notify_router, prefix="/api/v1")

# Custom error pages
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    try:
        with open("app/templates/errors/404.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), status_code=404)
    except Exception:
        return HTMLResponse("<h1>404 - Not Found</h1>", status_code=404)


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    try:
        with open("app/templates/errors/500.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read(), status_code=500)
    except Exception:
        return HTMLResponse("<h1>500 - Server Error</h1>", status_code=500)


# Register middleware
register_middleware(app)


@app.get("/", tags=["System"])
async def root_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/home")


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}