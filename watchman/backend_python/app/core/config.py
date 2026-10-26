# =============================================================
# app/core/config.py
# Purpose : Application-wide settings loaded from .env
# Pattern : Singleton Settings (used by Netflix, Uber internally)
# Replaces: application.properties in Spring Boot
# =============================================================

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Central configuration class.
    All values are auto-loaded from .env file.
    Add a new config? Just add a field here.
    """

    # ── App ────────────────────────────────────────────────────
    app_name: str = "CampusGuard - Smart Watchman & Gate Management System"
    app_version: str = "2.0.0"
    app_env: str = "development"  # development | staging | production
    app_port: int = 8080
    app_debug: bool = True

    # ── Database ───────────────────────────────────────────────
    database_url: str = "postgresql://postgres:1972@localhost:5432/campusguard_db"

    # ── Security ───────────────────────────────────────────────
    jwt_secret: str = "404E635266556A586E3272357538782F413F4428472B4B6250645367566B5970"
    jwt_expiration_hours: int = 24
    jwt_algorithm: str = "HS256"

    # ── CORS ───────────────────────────────────────────────────
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached singleton Settings instance.
    Calling this multiple times always returns the SAME object (memory efficient).
    """
    return Settings()
