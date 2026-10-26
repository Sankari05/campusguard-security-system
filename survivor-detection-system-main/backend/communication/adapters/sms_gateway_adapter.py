"""
sms_gateway_adapter.py
----------------------
Cellular-tier communication adapter wrapping SMSGate Android Local Server.
"""

from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .base import BaseCommunicationAdapter
from ..models import EmergencyMessage, DeliveryResult, DeliveryStatus, ChannelType

logger = logging.getLogger("ridgewatch.communication.smsgate")


class SMSGatewayAdapter(BaseCommunicationAdapter):
    """Dispatches emergency messages through local SMSGate server via physical SIM."""

    def __init__(self):
        super().__init__(ChannelType.SMS_GATEWAY, "SMSGate-Cellular-Adapter")
        self._forced_availability: Optional[bool] = None

    def set_simulated_availability(self, available: Optional[bool]) -> None:
        """Allows testing to toggle Cellular channel availability dynamically."""
        self._forced_availability = available

    def health_check(self) -> Dict[str, Any]:
        """Evaluates health of the SMSGate Android Local Server."""
        if self._forced_availability is not None:
            return {
                "available": self._forced_availability,
                "latency_ms": 120.0 if self._forced_availability else None,
                "error": None if self._forced_availability else "Cellular / SMSGate gateway unreachable",
                "details": {"tier": "CELLULAR", "simulated": True},
            }

        try:
            try:
                from notification_dispatch import check_smsgate_health
            except ImportError:
                from backend.notification_dispatch import check_smsgate_health
            return check_smsgate_health()
        except Exception as ex:
            return {
                "available": False,
                "latency_ms": None,
                "error": str(ex),
                "details": {},
            }

    def send(self, message: EmergencyMessage) -> DeliveryResult:
        """Dispatches SMS alert through SMSGate gateway."""
        start = time.time()
        now_ts = datetime.now(timezone.utc).isoformat()

        # Check health prior to send
        health = self.health_check()
        if not health.get("available", False):
            return DeliveryResult(
                message_id=message.message_id,
                channel=ChannelType.SMS_GATEWAY,
                status=DeliveryStatus.FAILED,
                error=health.get("error") or "SMSGate cellular gateway unavailable",
                timestamp=now_ts,
                latency_ms=(time.time() - start) * 1000,
            )

        try:
            try:
                from notification_dispatch import dispatch_smsgate_sms
            except ImportError:
                from backend.notification_dispatch import dispatch_smsgate_sms

            res = dispatch_smsgate_sms(
                phone_normalized=message.recipient,
                message_text=message.payload,
                rescue_command_id=message.rescue_command_id or message.alert_id or message.message_id,
            )

            status_str = res.get("status", "FAILED")
            deliv_status = DeliveryStatus.SENT if status_str == "SENT" else DeliveryStatus.FAILED

            return DeliveryResult(
                message_id=message.message_id,
                channel=ChannelType.SMS_GATEWAY,
                status=deliv_status,
                provider_message_id=res.get("message_id"),
                error=res.get("error"),
                timestamp=now_ts,
                latency_ms=(time.time() - start) * 1000,
                metadata={"provider": "SMSGATE", "sim_response": res},
            )
        except Exception as ex:
            return DeliveryResult(
                message_id=message.message_id,
                channel=ChannelType.SMS_GATEWAY,
                status=DeliveryStatus.FAILED,
                error=f"SMSGate dispatch exception: {ex}",
                timestamp=now_ts,
                latency_ms=(time.time() - start) * 1000,
            )
