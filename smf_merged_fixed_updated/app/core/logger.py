"""
app.core.logger
Enterprise structured logging with contextual request correlation.
Supports both human-readable console output and machine-readable JSON logs for observability.
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict

# Context variable to track the current request ID across async coroutines
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="system")


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records into structured JSON with context fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_ctx.get()),
            "source": f"{record.filename}:{record.lineno}",
        }

        # Include custom extra fields if provided
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_obj["data"] = record.extra_data

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logger(name: str = "edutrack", level: int = logging.INFO) -> logging.Logger:
    """Creates and configures an enterprise logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        # Standard clean human-readable formatter for local development
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | [%(filename)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Global app logger
logger = setup_logger()
get_logger = setup_logger

