"""
communication_router.py
------------------------
Authoritative multi-channel failover router and dispatch orchestrator for RidgeWatch.
Implements deterministic channel selection, idempotency enforcement, and non-blocking queueing.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable

from .models import (
    EmergencyMessage,
    DeliveryResult,
    DeliveryStatus,
    ChannelType,
    MessagePriority,
)
from .config import CommunicationConfig, get_config
from .adapters.base import BaseCommunicationAdapter
from .adapters import get_default_adapters
from .channel_health import ChannelHealthMonitor
from .message_queue import MessageQueueManager
from .delivery_tracker import DeliveryTracker
from .retry_manager import RetryManager

logger = logging.getLogger("ridgewatch.communication.router")


class CommunicationRouter:
    """
    Central multi-channel emergency routing coordinator.
    Evaluates bearer health, routes over optimal channel, manages failover,
    and maintains the persistent delivery ledger.
    """

    def __init__(
        self,
        config: Optional[CommunicationConfig] = None,
        db_path: Optional[str] = None,
        adapters: Optional[Dict[ChannelType, BaseCommunicationAdapter]] = None,
    ):
        self.config = config or get_config()
        self.db_path = db_path
        self.adapters = adapters or get_default_adapters()
        self.health_monitor = ChannelHealthMonitor(self.adapters)
        self.queue_manager = MessageQueueManager()
        self.delivery_tracker = DeliveryTracker(db_path=self.db_path)
        self.retry_manager = RetryManager(
            max_retries=self.config.max_retries,
            backoff_schedule=self.config.backoff_schedule,
        )
        self._executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="CommRouter")
        self._background_running = False

    def select_optimal_channel(self, message: EmergencyMessage) -> ChannelType:
        """
        Deterministic channel selection decision tree:
        1. Internet (WhatsApp) if available & enabled
        2. Cellular (SMSGate / Native SMS) if available & enabled
        3. Offline Sub-GHz LoRa if available & enabled
        4. Fallback: Local Delay-Tolerant Queue
        """
        # Tier 1: Internet (WhatsApp)
        if self.config.whatsapp_enabled:
            wa_health = self.health_monitor.check_channel(ChannelType.WHATSAPP)
            if wa_health.get("available", False):
                return ChannelType.WHATSAPP

        # Tier 2: Cellular (SMSGate / Native SMS)
        if self.config.smsgate_enabled:
            sms_health = self.health_monitor.check_channel(ChannelType.SMS_GATEWAY)
            if sms_health.get("available", False):
                return ChannelType.SMS_GATEWAY

        if self.config.native_sms_enabled:
            nat_health = self.health_monitor.check_channel(ChannelType.NATIVE_SMS)
            if nat_health.get("available", False):
                return ChannelType.NATIVE_SMS

        # Tier 3: Offline RF (Sub-GHz LoRa)
        if self.config.lora_enabled:
            lora_health = self.health_monitor.check_channel(ChannelType.LORA)
            if lora_health.get("available", False):
                return ChannelType.LORA

        # Tier 4: Total Blackout -> Local Offline Queue
        return ChannelType.OFFLINE_QUEUE

    def dispatch_alert(
        self,
        recipient: str,
        payload: str,
        priority: MessagePriority = MessagePriority.HIGH,
        alert_id: Optional[str] = None,
        rescue_command_id: Optional[str] = None,
        mission_id: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        sps: Optional[float] = None,
        preferred_channel: Optional[ChannelType] = None,
        async_dispatch: bool = False,
    ) -> EmergencyMessage:
        """
        Main routing entrypoint for emergency alerts.
        Enforces idempotency, selects optimal bearer, and executes dispatch.
        """
        # 1. Instantiate Canonical EmergencyMessage
        msg = EmergencyMessage(
            message_id="",  # Auto-generated in __post_init__
            recipient=recipient,
            payload=payload,
            priority=priority,
            alert_id=alert_id,
            rescue_command_id=rescue_command_id,
            mission_id=mission_id,
            latitude=latitude,
            longitude=longitude,
            sps=sps,
        )

        # 2. Idempotency check: prevent duplicate deliveries across channels
        existing = self.delivery_tracker.check_idempotency(msg.idempotency_key, check_db=not async_dispatch)
        if existing and existing.status in (
            DeliveryStatus.SENT,
            DeliveryStatus.DELIVERED,
            DeliveryStatus.ACKNOWLEDGED,
            DeliveryStatus.QUEUED,
            DeliveryStatus.SENDING,
        ):
            logger.info(
                f"[ROUTER] Idempotent hit: Message {existing.message_id} already exists "
                f"with status={existing.status.value}. Skipping duplicate send."
            )
            return existing

        if async_dispatch:
            msg.status = DeliveryStatus.QUEUED
            self.delivery_tracker.record_new_message(msg, persist_db=False)
            self._executor.submit(self._async_route_and_dispatch, msg, preferred_channel)
            return msg

        # 3. Synchronous Channel Selection
        if preferred_channel and preferred_channel != ChannelType.OFFLINE_QUEUE:
            h = self.health_monitor.check_channel(preferred_channel)
            if h.get("available", False):
                selected_channel = preferred_channel
            else:
                selected_channel = self.select_optimal_channel(msg)
        else:
            selected_channel = self.select_optimal_channel(msg)

        msg.channel = selected_channel
        self.delivery_tracker.record_new_message(msg, persist_db=True)
        return self._execute_dispatch_with_failover(msg)

    def _async_route_and_dispatch(self, msg: EmergencyMessage, preferred_channel: Optional[ChannelType] = None) -> None:
        """Executes asynchronous background channel evaluation and transmission."""
        try:
            self.delivery_tracker.persist_to_db(msg)
            if preferred_channel and preferred_channel != ChannelType.OFFLINE_QUEUE:
                h = self.health_monitor.check_channel(preferred_channel)
                if h.get("available", False):
                    selected_channel = preferred_channel
                else:
                    selected_channel = self.select_optimal_channel(msg)
            else:
                selected_channel = self.select_optimal_channel(msg)
            msg.channel = selected_channel
            self._execute_dispatch_with_failover(msg)
        except Exception as ex:
            logger.error(f"[ROUTER] Async dispatch error for {msg.message_id}: {ex}")

    def _execute_dispatch_with_failover(self, msg: EmergencyMessage) -> EmergencyMessage:
        """Executes transmission with immediate bearer failover if primary selected channel fails."""
        # Tiered failover list starting from selected channel
        all_channels = [
            ChannelType.WHATSAPP,
            ChannelType.SMS_GATEWAY,
            ChannelType.NATIVE_SMS,
            ChannelType.LORA,
            ChannelType.OFFLINE_QUEUE,
        ]

        start_idx = all_channels.index(msg.channel) if msg.channel in all_channels else 0
        failover_chain = all_channels[start_idx:]

        for attempt_channel in failover_chain:
            msg.channel = attempt_channel

            if attempt_channel == ChannelType.OFFLINE_QUEUE:
                # All physical channels failed or none available
                msg.status = DeliveryStatus.OFFLINE_QUEUED
                self.queue_manager.enqueue(msg)
                res = DeliveryResult(
                    message_id=msg.message_id,
                    channel=ChannelType.OFFLINE_QUEUE,
                    status=DeliveryStatus.OFFLINE_QUEUED,
                    error="All physical bearers unavailable. Saved to local delay-tolerant queue.",
                )
                self.delivery_tracker.update_result(res)
                logger.warning(
                    f"[ROUTER] Message {msg.message_id} routed to OFFLINE_QUEUE "
                    f"for recipient {msg.recipient_masked}"
                )
                return msg

            adapter = self.adapters.get(attempt_channel)
            if not adapter or not adapter.is_available():
                continue

            msg.status = DeliveryStatus.SENDING
            res = adapter.send(msg)

            # Record outcome for circuit breaker
            self.health_monitor.record_dispatch_outcome(attempt_channel, res.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED))

            if res.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED):
                self.delivery_tracker.update_result(res)
                logger.info(
                    f"[ROUTER] Successfully dispatched {msg.message_id} via "
                    f"{attempt_channel.value} to {msg.recipient_masked}"
                )
                return msg
            else:
                logger.warning(
                    f"[ROUTER] Channel {attempt_channel.value} failed for {msg.message_id}: "
                    f"{res.error}. Attempting next bearer in failover chain..."
                )
                msg.delivery_trace.append({
                    "channel": attempt_channel.value,
                    "status": "FAILED",
                    "error": res.error,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        # If everything fell through
        msg.status = DeliveryStatus.OFFLINE_QUEUED
        self.queue_manager.enqueue(msg)
        return msg

    def acknowledge_message(self, message_id: str, rescuer_id: Optional[str] = None) -> bool:
        """Records two-way delivery acknowledgement."""
        return self.delivery_tracker.record_acknowledgement(message_id, rescuer_id=rescuer_id)

    def dispatch_bulk(
        self,
        recipients: List[str],
        payload: str,
        priority: MessagePriority = MessagePriority.HIGH,
        alert_id: Optional[str] = None,
        async_dispatch: bool = True,
    ) -> List[EmergencyMessage]:
        """
        Dispatches emergency broadcast to bulk recipient list (e.g. 90 rescuers).
        Uses non-blocking worker pool to prevent freezing the server.
        """
        messages = []
        for r in recipients:
            msg = self.dispatch_alert(
                recipient=r,
                payload=payload,
                priority=priority,
                alert_id=alert_id,
                async_dispatch=async_dispatch,
            )
            messages.append(msg)
        return messages

    def drain_offline_queue(self) -> int:
        """Attempts to flush queued offline messages when network connectivity returns."""
        drained_count = 0
        while self.queue_manager.size() > 0:
            msg = self.queue_manager.dequeue()
            if not msg:
                break
            if msg.is_expired():
                continue
            # Re-evaluate best available channel
            optimal = self.select_optimal_channel(msg)
            if optimal == ChannelType.OFFLINE_QUEUE:
                # Still offline, put it back
                self.queue_manager.enqueue(msg)
                break
            msg.channel = optimal
            self._execute_dispatch_with_failover(msg)
            drained_count += 1
        return drained_count

    def get_status(self) -> Dict[str, Any]:
        """Observability telemetry payload."""
        return {
            "health": self.health_monitor.get_all_channel_status(),
            "queue_depth": self.queue_manager.size(),
            "config": {
                "failover_enabled": self.config.failover_enabled,
                "retry_enabled": self.config.retry_enabled,
                "whatsapp_enabled": self.config.whatsapp_enabled,
                "smsgate_enabled": self.config.smsgate_enabled,
                "lora_enabled": self.config.lora_enabled,
                "max_retries": self.config.max_retries,
            },
        }


# Global Router Singleton
_ROUTER: Optional[CommunicationRouter] = None


def get_communication_router(db_path: Optional[str] = None) -> CommunicationRouter:
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = CommunicationRouter(db_path=db_path)
    return _ROUTER


def reset_communication_router() -> None:
    """Resets global singleton for testing."""
    global _ROUTER
    _ROUTER = None
