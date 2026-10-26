"""
base.py
-------
Abstract Base Class for all Communication Channel Adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..models import EmergencyMessage, DeliveryResult, ChannelType


class BaseCommunicationAdapter(ABC):
    """Abstract interface governing physical communication channel drivers."""

    def __init__(self, channel_type: ChannelType, name: str):
        self.channel_type = channel_type
        self.name = name

    @abstractmethod
    def send(self, message: EmergencyMessage) -> DeliveryResult:
        """
        Dispatches the emergency message through this physical channel.
        Must return a structured DeliveryResult.
        Must NOT throw uncaught exceptions (must catch and return status=FAILED).
        """
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Proactively evaluates channel health and connectivity.
        Returns dict with:
          - available: bool
          - latency_ms: Optional[float]
          - error: Optional[str]
          - details: Dict[str, Any]
        """
        pass

    def is_available(self) -> bool:
        """Helper checking boolean availability."""
        try:
            return bool(self.health_check().get("available", False))
        except Exception:
            return False
