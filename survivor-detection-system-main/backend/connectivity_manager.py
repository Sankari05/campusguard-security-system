"""
connectivity_manager.py
-----------------------
Internet connectivity detection and monitoring for RidgeWatch.
Performs non-blocking, cached reachability probes to detect when external cloud,
SMS, and WhatsApp gateways can be reached.
"""

from __future__ import annotations

import os
import time
import socket
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("ridgewatch.offline.connectivity")


class ConnectivityManager:
    """Monitors and reports internet connectivity with non-blocking caching."""

    def __init__(
        self,
        probe_hosts: Optional[list[tuple[str, int]]] = None,
        cache_ttl_sec: float = 3.0,
        probe_timeout_sec: float = 1.2,
    ):
        self.probe_hosts = probe_hosts or [
            ("8.8.8.8", 53),        # Google Public DNS
            ("1.1.1.1", 53),        # Cloudflare DNS
            ("www.google.com", 80),  # HTTP Fallback
        ]
        self.cache_ttl_sec = cache_ttl_sec
        self.probe_timeout_sec = probe_timeout_sec
        self._is_online_cached: bool = True
        self._last_checked_time: float = 0.0
        self._last_latency_ms: Optional[float] = None
        self._consecutive_failures: int = 0
        self._forced_simulation_state: Optional[bool] = None
        self._lock = threading.Lock()

    def set_simulated_connectivity(self, online: Optional[bool]) -> None:
        """
        Allows tests and live simulator demos to override connectivity state.
        Pass None to resume automatic real network probing.
        """
        with self._lock:
            self._forced_simulation_state = online
            if online is not None:
                self._is_online_cached = online
                self._last_checked_time = time.time()
                logger.info(f"[CONNECTIVITY] Simulation override set: online={online}")
            else:
                logger.info("[CONNECTIVITY] Simulation override cleared. Automatic probing active.")

    def clear_simulation_override(self) -> None:
        """Clears any forced simulation state, resuming live network probing."""
        with self._lock:
            self._forced_simulation_state = None
            logger.info("[CONNECTIVITY] Simulation override cleared. Automatic probing active.")

    def is_online(self, force_fresh: bool = False) -> bool:
        """
        Returns True if Internet is available, False otherwise.
        Uses a short-lived cache (3s default) to avoid stalling caller threads.
        """
        with self._lock:
            if self._forced_simulation_state is not None:
                return self._forced_simulation_state

        now = time.time()
        if not force_fresh and (now - self._last_checked_time) < self.cache_ttl_sec:
            return self._is_online_cached

        return self.probe_now()

    def probe_now(self) -> bool:
        """Executes a synchronous low-latency network probe across candidate endpoints."""
        with self._lock:
            if self._forced_simulation_state is not None:
                return self._forced_simulation_state

        start = time.time()
        online = False
        lat_ms = None

        for host, port in self.probe_hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.probe_timeout_sec)
                sock.connect((host, port))
                sock.close()
                lat_ms = (time.time() - start) * 1000
                online = True
                break
            except Exception:
                continue

        with self._lock:
            self._is_online_cached = online
            self._last_checked_time = time.time()
            self._last_latency_ms = lat_ms
            if online:
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1

        return online

    def get_connectivity_status(self) -> Dict[str, Any]:
        """Returns structured connectivity metrics."""
        online = self.is_online()
        with self._lock:
            forced = self._forced_simulation_state
            lat = self._last_latency_ms
            fails = self._consecutive_failures
            last_check = datetime.fromtimestamp(self._last_checked_time, tz=timezone.utc).isoformat() if self._last_checked_time else None

        return {
            "is_online": online,
            "latency_ms": round(lat, 2) if lat is not None else None,
            "last_checked_at": last_check,
            "consecutive_failures": fails,
            "simulated_override": forced is not None,
            "simulated_value": forced,
            "forced_simulation": forced,
            "status_text": "ONLINE" if online else "OFFLINE",
        }


# Global singleton instance
_CONNECTIVITY_INSTANCE: Optional[ConnectivityManager] = None


def get_connectivity_manager() -> ConnectivityManager:
    """Returns global singleton instance of ConnectivityManager."""
    global _CONNECTIVITY_INSTANCE
    if _CONNECTIVITY_INSTANCE is None:
        _CONNECTIVITY_INSTANCE = ConnectivityManager()
    return _CONNECTIVITY_INSTANCE


def reset_connectivity_manager() -> None:
    """Resets global singleton instance for testing."""
    global _CONNECTIVITY_INSTANCE
    _CONNECTIVITY_INSTANCE = None
