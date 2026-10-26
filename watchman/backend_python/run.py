#!/usr/bin/env python
# =============================================================
# CampusGuard - Server Runner
# Usage:
#   python run.py
# Or:
#   uvicorn app.main:app --reload --port 8080
# =============================================================

import sys
import uvicorn
from app.core.config import get_settings

settings = get_settings()

if __name__ == "__main__":
    print(f"Starting {settings.app_name} on port {settings.app_port}...")
    print(f"Swagger API Docs: http://localhost:{settings.app_port}/api/docs")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_debug,
    )
