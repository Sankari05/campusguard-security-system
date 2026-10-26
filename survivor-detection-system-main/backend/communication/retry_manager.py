"""
retry_manager.py
----------------
Exponential backoff retry scheduling, jitter calculations, and retry termination.
"""

from __future__ import annotations

import random
import time
import logging
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime, timezone

from .models import EmergencyMessage, DeliveryStatus, DeliveryResult
from .config import get_config

logger = logging.getLogger("ridgewatch.communication.retry")


class RetryManager:
    """Orchestrates exponential backoff retries with jitter and termination guards."""

    def __init__(
        self,
        max_retries: int = 3,
        backoff_schedule: tuple = (5.0, 15.0, 30.0),
        jitter_pct: float = 0.2,
    ):
        self.max_retries = max_retries
        self.backoff_schedule = backoff_schedule
        self.jitter_pct = jitter_pct

    def should_retry(self, message: EmergencyMessage) -> bool:
        """Determines if message is eligible for another transmission attempt."""
        if message.is_expired():
            logger.info(f"[RETRY] Message {message.message_id} is expired. Retries aborted.")
            return False

        if message.status in (DeliveryStatus.DELIVERED, DeliveryStatus.ACKNOWLEDGED, DeliveryStatus.SENT):
            return False

        if message.retry_count >= self.max_retries:
            logger.info(
                f"[RETRY] Message {message.message_id} reached maximum retries "
                f"({message.retry_count}/{self.max_retries})."
            )
            return False

        return True

    def calculate_backoff_delay(self, retry_attempt: int) -> float:
        """
        Calculates delay in seconds for the given retry attempt:
        Retry 1: 5s (+/- jitter)
        Retry 2: 15s (+/- jitter)
        Retry 3: 30s (+/- jitter)
        """
        idx = min(max(0, retry_attempt - 1), len(self.backoff_schedule) - 1)
        base_delay = self.backoff_schedule[idx]

        # Apply random jitter to prevent thundering herd / retry storms
        jitter_range = base_delay * self.jitter_pct
        jitter = random.uniform(-jitter_range, jitter_range)
        effective_delay = max(0.5, base_delay + jitter)
        return round(effective_delay, 2)

    def prepare_next_retry(self, message: EmergencyMessage) -> Optional[float]:
        """Increments retry counter and returns required backoff delay (or None if maxed out)."""
        if not self.should_retry(message):
            message.status = DeliveryStatus.FAILED
            return None

        message.retry_count += 1
        message.status = DeliveryStatus.RETRYING
        delay = self.calculate_backoff_delay(message.retry_count)

        logger.info(
            f"[RETRY] Scheduled Retry #{message.retry_count} for {message.message_id} "
            f"in {delay:.1f}s (Max retries: {self.max_retries})"
        )
        return delay
