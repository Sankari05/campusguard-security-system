"""
adapters/__init__.py
--------------------
Adapter registry and factory for RidgeWatch communication channels.
"""

from __future__ import annotations

from typing import Dict, Optional
from ..models import ChannelType
from .base import BaseCommunicationAdapter
from .whatsapp_adapter import WhatsAppAdapter
from .sms_gateway_adapter import SMSGatewayAdapter
from .native_sms_adapter import NativeSMSAdapter
from .lora_adapter import LoRaAdapter

__all__ = [
    "BaseCommunicationAdapter",
    "WhatsAppAdapter",
    "SMSGatewayAdapter",
    "NativeSMSAdapter",
    "LoRaAdapter",
    "get_default_adapters",
]


def get_default_adapters() -> Dict[ChannelType, BaseCommunicationAdapter]:
    """Instantiates default suite of communication adapters."""
    return {
        ChannelType.WHATSAPP: WhatsAppAdapter(),
        ChannelType.SMS_GATEWAY: SMSGatewayAdapter(),
        ChannelType.NATIVE_SMS: NativeSMSAdapter(),
        ChannelType.LORA: LoRaAdapter(),
    }
