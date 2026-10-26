"""
backend/communication/__init__.py
---------------------------------
Public surface for the RidgeWatch Resilient Multi-Channel Emergency Communication Layer.
"""

from __future__ import annotations

from .models import (
    EmergencyMessage,
    DeliveryResult,
    ChannelType,
    MessagePriority,
    DeliveryStatus,
    CircuitState,
)
from .config import CommunicationConfig, get_config, reload_config
from .communication_router import (
    CommunicationRouter,
    get_communication_router,
    reset_communication_router,
)
from .channel_health import ChannelHealthMonitor, ChannelCircuitBreaker
from .message_queue import MessageQueueManager
from .delivery_tracker import DeliveryTracker
from .retry_manager import RetryManager
from .adapters import (
    BaseCommunicationAdapter,
    WhatsAppAdapter,
    SMSGatewayAdapter,
    NativeSMSAdapter,
    LoRaAdapter,
    get_default_adapters,
)

__all__ = [
    "EmergencyMessage",
    "DeliveryResult",
    "ChannelType",
    "MessagePriority",
    "DeliveryStatus",
    "CircuitState",
    "CommunicationConfig",
    "get_config",
    "reload_config",
    "CommunicationRouter",
    "get_communication_router",
    "reset_communication_router",
    "ChannelHealthMonitor",
    "ChannelCircuitBreaker",
    "MessageQueueManager",
    "DeliveryTracker",
    "RetryManager",
    "BaseCommunicationAdapter",
    "WhatsAppAdapter",
    "SMSGatewayAdapter",
    "NativeSMSAdapter",
    "LoRaAdapter",
    "get_default_adapters",
]
