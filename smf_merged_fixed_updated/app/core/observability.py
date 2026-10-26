"""
app.core.observability
Enterprise Production Observability, Crash Tracking, and Sentry Integration.

Provides dual-tier error tracking:
1. Cloud Sentry: Real-time stack traces, breadcrumbs, performance profiling when SENTRY_DSN is set.
2. Local Structured Audit Log: Fallback exception journaling into logs/exceptions.jsonl with correlation IDs.
"""

import os
import sys
import json
import uuid
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse

import config

log = logging.getLogger(__name__)

_SENTRY_ACTIVE = False
EXCEPTION_LOG_PATH = os.path.join(config.BASE_DIR, "logs", "exceptions.jsonl")


def init_observability():
    """Initialize Sentry SDK with automatic environment detection or local fallback."""
    global _SENTRY_ACTIVE
    dsn = os.getenv("SENTRY_DSN", getattr(config, "SENTRY_DSN", "")).strip()

    if dsn and dsn.startswith("http"):
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_sdk.init(
                dsn=dsn,
                environment=getattr(config, "APP_ENV", "production"),
                release="edutrack-pro@9.6.0",
                traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
                profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
                integrations=[FastApiIntegration()],
                send_default_pii=False,
            )
            _SENTRY_ACTIVE = True
            log.info("[OBSERVABILITY] Sentry SDK successfully initialized (Cloud Monitoring Active).")
            return True
        except Exception as err:
            log.warning("[OBSERVABILITY] Sentry init failed: %s. Using local fallback logger.", err)
            _SENTRY_ACTIVE = False
    else:
        log.info("[OBSERVABILITY] SENTRY_DSN not set. Local structured JSON exception logger active.")
        _SENTRY_ACTIVE = False
    return False


def capture_exception(err: Exception, context: Optional[Dict[str, Any]] = None) -> str:
    """Capture exception to Sentry or local structured JSON log, returning an Error Reference ID."""
    error_id = str(uuid.uuid4())[:12]

    if _SENTRY_ACTIVE:
        try:
            import sentry_sdk
            with sentry_sdk.push_scope() as scope:
                if context:
                    for k, v in context.items():
                        scope.set_extra(k, str(v)[:500])
                scope.set_tag("error_id", error_id)
                sentry_event_id = sentry_sdk.capture_exception(err)
                if sentry_event_id:
                    error_id = str(sentry_event_id)
        except Exception:
            pass

    # Always write to local structured JSON exception log for offline auditability
    _record_local_exception(error_id, err, context)
    return error_id


def _record_local_exception(error_id: str, err: Exception, context: Optional[Dict[str, Any]] = None):
    try:
        os.makedirs(os.path.dirname(EXCEPTION_LOG_PATH), exist_ok=True)
        entry = {
            "error_id": error_id,
            "timestamp": datetime.now().isoformat(),
            "exception_type": type(err).__name__,
            "message": str(err),
            "traceback": traceback.format_exc(),
            "context": context or {},
        }
        with open(EXCEPTION_LOG_PATH, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry) + "\n")
    except Exception as write_err:
        log.error("Failed writing to local exception journal: %s", write_err)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Enterprise global 500 handler returning a clean, traceable error envelope."""
    context = {
        "url": str(request.url),
        "method": request.method,
        "client": request.client.host if request.client else "?",
    }
    error_id = capture_exception(exc, context)

    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_id": error_id,
            "message": "Internal Server Error occurred. Our engineering observability team has been alerted.",
            "timestamp": datetime.now().isoformat()
        }
    )
