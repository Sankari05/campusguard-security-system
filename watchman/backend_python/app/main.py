# =============================================================
# app/main.py
# Purpose : FastAPI Application Factory & Lifespan Entry Point
# Pattern : Enterprise Application Factory (Amazon, Qualcomm standard)
# Replaces: CampusGuardApplication.java (Spring Boot main class)
# =============================================================

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging_config import setup_logging
from app.db.init_db import init_db
from app.db.session import SessionLocal

settings = get_settings()
setup_logging(debug=settings.app_debug)
logger = logging.getLogger("campusguard")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application Lifespan Event Handler.
    Runs DB initialization / table creation on startup.
    Runs cleanup on shutdown.
    """
    logger.info(f"Starting CampusGuard in {settings.app_env.upper()} mode...")
    try:
        db = SessionLocal()
        try:
            init_db(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not auto-initialize DB on startup: {e}")
        logger.warning("The application will proceed and connect once DB is available.")

    yield
    logger.info("CampusGuard shutting down gracefully...")


def create_application() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    Equivalent to SpringApplication.run(CampusGuardApplication.class, args).
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "CampusGuard - Next-Generation Gate Security & Campus Safety Management System. "
            "Enterprise Python backend replacing legacy Spring Boot architecture."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS Middleware Configuration ───────────────────────────────
    # Allows React frontend (localhost:3000 / localhost:5173 / production) to communicate
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Custom Application Exception Handler ────────────────────────
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": exc.detail, "status_code": exc.status_code},
        )

    # ── Root & Health Check Endpoints ───────────────────────────────
    @app.get("/", include_in_schema=False)
    def root_redirect():
        """Redirect root URL to interactive Swagger documentation."""
        return RedirectResponse(url="/api/docs")

    @app.get("/health", tags=["Monitoring"])
    def health_check():
        """Liveness probe used by Docker, Kubernetes, and load balancers."""
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
        }

    # ── Include API v1 Router under /api/v1, /api, and root ──────────
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(api_router, prefix="/api")
    app.include_router(api_router, prefix="/v1")
    app.include_router(api_router)

    return app


app = create_application()
