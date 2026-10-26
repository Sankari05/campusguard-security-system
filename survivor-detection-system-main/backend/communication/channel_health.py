"""
channel_health.py
-----------------
Channel health monitoring, probe telemetry, and circuit breaker patterns for
heterogeneous disaster communication channels.
"""

from __future__ import annotations

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .models import ChannelType, CircuitState
from .adapters.base import BaseCommunicationAdapter

logger = logging.getLogger("ridgewatch.communication.health")


class ChannelCircuitBreaker:
    """Per-channel circuit breaker preventing cascading failures and latency spikes."""

    def __init__(
        self,
        channel: ChannelType,
        failure_threshold: int = 3,
        recovery_timeout_sec: float = 30.0,
    ):
        self.channel = channel
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_success_time = time.time()

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                logger.warning(
                    f"[CIRCUIT-BREAKER] Channel {self.channel.value} tripped OPEN "
                    f"after {self.failure_count} consecutive failures."
                )
            self.state = CircuitState.OPEN

    def can_attempt(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            now = time.time()
            if self.last_failure_time and (now - self.last_failure_time) > self.recovery_timeout_sec:
                logger.info(f"[CIRCUIT-BREAKER] Channel {self.channel.value} entering HALF_OPEN probe state.")
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        if self.state == CircuitState.HALF_OPEN:
            return True
        return True


class ChannelHealthMonitor:
    """Monitors real-time availability across all physical and logical bearers."""

    def __init__(self, adapters: Optional[Dict[ChannelType, BaseCommunicationAdapter]] = None):
        self.adapters = adapters or {}
        self.circuit_breakers: Dict[ChannelType, ChannelCircuitBreaker] = {
            c: ChannelCircuitBreaker(c) for c in ChannelType
        }
        self._last_health_cache: Dict[ChannelType, Dict[str, Any]] = {}
        self._last_check_time: float = 0.0
        self._cache_ttl_sec: float = 2.0  # short cache to avoid spamming health checks

    def register_adapter(self, channel: ChannelType, adapter: BaseCommunicationAdapter) -> None:
        self.adapters[channel] = adapter

    def record_dispatch_outcome(self, channel: ChannelType, success: bool) -> None:
        cb = self.circuit_breakers.get(channel)
        if cb:
            if success:
                cb.record_success()
            else:
                cb.record_failure()

    def check_channel(self, channel: ChannelType, force_fresh: bool = False) -> Dict[str, Any]:
        """Evaluates health of a specific channel taking circuit breaker state into account."""
        cb = self.circuit_breakers.get(channel)
        if cb and not cb.can_attempt() and not force_fresh:
            return {
                "available": False,
                "circuit_state": cb.state.value,
                "latency_ms": None,
                "error": f"Circuit breaker is {cb.state.value} (tripped)",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        adapter = self.adapters.get(channel)
        if not adapter:
            return {
                "available": False,
                "circuit_state": CircuitState.CLOSED.value,
                "latency_ms": None,
                "error": f"No adapter registered for {channel.value}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        res = adapter.health_check()
        avail = bool(res.get("available", False))
        if cb:
            if avail:
                cb.record_success()
            else:
                cb.record_failure()

        out = {
            "channel": channel.value,
            "available": avail,
            "circuit_state": cb.state.value if cb else CircuitState.CLOSED.value,
            "latency_ms": res.get("latency_ms"),
            "error": res.get("error"),
            "details": res.get("details", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._last_health_cache[channel] = out
        return out

    def get_all_channel_status(self) -> Dict[str, Any]:
        """Returns comprehensive health telemetry for all communication tiers."""
        statuses = {}
        for c in [ChannelType.WHATSAPP, ChannelType.SMS_GATEWAY, ChannelType.NATIVE_SMS, ChannelType.LORA]:
            statuses[c.value.lower()] = self.check_channel(c)

        # Offline queue is always available locally
        statuses["offline_queue"] = {
            "channel": ChannelType.OFFLINE_QUEUE.value,
            "available": True,
            "circuit_state": CircuitState.CLOSED.value,
            "latency_ms": 1.0,
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Resolve currently active highest priority bearer
        active_bearer = ChannelType.OFFLINE_QUEUE
        for c in [ChannelType.WHATSAPP, ChannelType.SMS_GATEWAY, ChannelType.NATIVE_SMS, ChannelType.LORA]:
            if statuses.get(c.value.lower(), {}).get("available"):
                active_bearer = c
                break

        return {
            "channels": statuses,
            "active_primary_bearer": active_bearer.value,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
