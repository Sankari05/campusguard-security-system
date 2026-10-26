"""
models.py
---------
Domain models, Data Transfer Objects (DTOs), and Enumerations for the
RidgeWatch Multi-Channel Emergency Communication Subsystem.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional


class ChannelType(str, Enum):
    WHATSAPP = "WHATSAPP"
    SMS_GATEWAY = "SMS_GATEWAY"
    NATIVE_SMS = "NATIVE_SMS"
    LORA = "LORA"
    OFFLINE_QUEUE = "OFFLINE_QUEUE"


class MessagePriority(str, Enum):
    CRITICAL = "CRITICAL"  # Life-safety urgent, immediate dam breach / avalanche / burial
    HIGH = "HIGH"          # Urgent rescue mission dispatch
    MEDIUM = "MEDIUM"      # Work assignment / secondary hazard alert
    LOW = "LOW"            # Routine status update / telemetry heartbeat


class DeliveryStatus(str, Enum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RETRYING = "RETRYING"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    OFFLINE_QUEUED = "OFFLINE_QUEUED"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Channel healthy, operating normally
    OPEN = "OPEN"          # Channel failed, traffic bypassed/diverted
    HALF_OPEN = "HALF_OPEN"# Probing channel recovery with trial traffic


@dataclass
class DeliveryResult:
    """Standard result returned by all communication channel adapters."""
    message_id: str
    channel: ChannelType
    status: DeliveryStatus
    provider_message_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "channel": self.channel.value if hasattr(self.channel, "value") else str(self.channel),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "provider_message_id": self.provider_message_id,
            "error": self.error,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }


@dataclass
class EmergencyMessage:
    """Canonical emergency message routed through the failover layer."""
    message_id: str
    recipient: str
    payload: str
    priority: MessagePriority = MessagePriority.HIGH
    alert_id: Optional[str] = None
    rescue_command_id: Optional[str] = None
    mission_id: Optional[str] = None
    channel: ChannelType = ChannelType.SMS_GATEWAY
    compact_payload: Optional[str] = None
    status: DeliveryStatus = DeliveryStatus.QUEUED
    retry_count: int = 0
    max_retries: int = 3
    recipient_masked: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    dispatched_at: Optional[str] = None
    delivered_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    provider_message_id: Optional[str] = None
    last_error: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    sps: Optional[float] = None
    delivery_trace: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.message_id:
            now = datetime.now(timezone.utc)
            self.message_id = f"RW-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        if not self.expires_at:
            # Default TTL: 2 hours (120 min) for tactical messages
            now_dt = datetime.now(timezone.utc)
            self.expires_at = (now_dt + timedelta(minutes=120)).isoformat()

        if not self.idempotency_key:
            # Deterministic SHA-256 hash
            raw_key = f"{self.recipient}:{self.alert_id or ''}:{self.rescue_command_id or ''}:{self.payload}"
            self.idempotency_key = f"IDEM-{hashlib.sha256(raw_key.encode('utf-8')).hexdigest()[:16]}"

        if not self.recipient_masked and self.recipient:
            self.recipient_masked = self._mask_recipient(self.recipient)

        if not self.compact_payload:
            self.compact_payload = self._generate_compact_payload()

    def _mask_recipient(self, rec: str) -> str:
        clean = rec.strip()
        if len(clean) > 8:
            return clean[:4] + "****" + clean[-2:]
        return clean

    def _generate_compact_payload(self) -> str:
        """Generates compact <=64-byte ASCII packet for sub-GHz LoRa transmission."""
        prio_short = self.priority.value[:4].upper()
        lat_str = f"{self.latitude:.4f}" if self.latitude is not None else "0.0000"
        lon_str = f"{self.longitude:.4f}" if self.longitude is not None else "0.0000"
        sps_str = f"{int(self.sps)}" if self.sps is not None else "0"
        alt_id_short = (self.alert_id or self.rescue_command_id or "GEN")[:8]
        msg_short = self.message_id[-8:]
        
        raw_body = f"RW|{msg_short}|{prio_short}|{alt_id_short}|{lat_str}|{lon_str}|{sps_str}"
        # 2-byte hex checksum
        chk = sum(raw_body.encode("ascii")) % 256
        return f"{raw_body}|{chk:02X}"

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) >= exp
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["channel"] = self.channel.value if hasattr(self.channel, "value") else str(self.channel)
        res["priority"] = self.priority.value if hasattr(self.priority, "value") else str(self.priority)
        res["status"] = self.status.value if hasattr(self.status, "value") else str(self.status)
        return res
