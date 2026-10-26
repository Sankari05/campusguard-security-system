"""
offline_models.py
-----------------
Data models, enumerations, checksum generation, and serialization logic for the
RidgeWatch Offline Emergency Communication Subsystem.
"""

from __future__ import annotations

import json
import uuid
import hashlib
import binascii
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Union


class MessageType(str, Enum):
    SURVIVOR_DETECTED = "SURVIVOR_DETECTED"
    MEDICAL_EMERGENCY = "MEDICAL_EMERGENCY"
    EARTHQUAKE_ALERT = "EARTHQUAKE_ALERT"
    FLOOD_ALERT = "FLOOD_ALERT"
    FIRE_ALERT = "FIRE_ALERT"
    LANDSLIDE_ALERT = "LANDSLIDE_ALERT"
    AVALANCHE_ALERT = "AVALANCHE_ALERT"
    RESCUE_ACK = "RESCUE_ACK"
    RESCUE_STATUS = "RESCUE_STATUS"
    GATEWAY_SYNC = "GATEWAY_SYNC"


class MessagePriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def weight(self) -> int:
        """Integer weight for priority sorting (0 = most urgent)."""
        weights = {
            MessagePriority.CRITICAL: 0,
            MessagePriority.HIGH: 1,
            MessagePriority.MEDIUM: 2,
            MessagePriority.LOW: 3,
        }
        return weights.get(self, 2)


class MessageStatus(str, Enum):
    PENDING = "PENDING"
    TRANSMITTING = "TRANSMITTING"
    SENT = "SENT"
    RECEIVED = "RECEIVED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


def compute_message_checksum(
    message_id: str,
    source_device_id: str,
    destination_device_id: str,
    message_type: str,
    payload_json: str,
) -> str:
    """Computes an 8-character CRC32 / SHA-256 hex checksum for packet integrity validation."""
    raw = f"{message_id}:{source_device_id}:{destination_device_id}:{message_type}:{payload_json}"
    crc = binascii.crc32(raw.encode("utf-8")) & 0xFFFFFFFF
    return f"{crc:08X}"


@dataclass
class OfflineMessage:
    """Canonical offline emergency message stored locally and routed over LoRa mesh."""
    message_id: str = ""
    alert_id: Optional[str] = None
    source_device_id: str = "NODE-ORIGIN"
    destination_device_id: str = "GATEWAY-01"
    message_type: MessageType = MessageType.SURVIVOR_DETECTED
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.HIGH
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    hop_count: int = 0
    max_hops: int = 5
    status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    last_error: Optional[str] = None
    checksum: str = ""
    last_attempt_at: Optional[str] = None

    def __post_init__(self):
        if not self.message_id:
            now = datetime.now(timezone.utc)
            self.message_id = f"OFF-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"

        if not self.expires_at:
            # Default TTL: 24 hours (86400 seconds)
            now_dt = datetime.now(timezone.utc)
            self.expires_at = (now_dt + timedelta(seconds=86400)).isoformat()

        if isinstance(self.message_type, str) and not isinstance(self.message_type, MessageType):
            try:
                self.message_type = MessageType(self.message_type)
            except Exception:
                self.message_type = MessageType.SURVIVOR_DETECTED

        if isinstance(self.priority, str) and not isinstance(self.priority, MessagePriority):
            try:
                self.priority = MessagePriority(self.priority.upper())
            except Exception:
                self.priority = MessagePriority.HIGH

        if isinstance(self.status, str) and not isinstance(self.status, MessageStatus):
            try:
                self.status = MessageStatus(self.status.upper())
            except Exception:
                self.status = MessageStatus.PENDING

        if not self.checksum:
            self.checksum = self.calculate_checksum()

    def calculate_checksum(self) -> str:
        """Calculates checksum over immutable fields."""
        payload_str = json.dumps(self.payload, sort_keys=True)
        type_str = self.message_type.value if hasattr(self.message_type, "value") else str(self.message_type)
        return compute_message_checksum(
            self.message_id,
            self.source_device_id,
            self.destination_device_id,
            type_str,
            payload_str,
        )

    def verify_checksum(self) -> bool:
        """Verifies packet integrity against corrupted payloads."""
        return self.checksum == self.calculate_checksum()

    def is_expired(self) -> bool:
        """Checks if message TTL has elapsed."""
        if not self.expires_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Serializes message to dictionary."""
        return {
            "message_id": self.message_id,
            "alert_id": self.alert_id,
            "source_device_id": self.source_device_id,
            "destination_device_id": self.destination_device_id,
            "message_type": self.message_type.value if hasattr(self.message_type, "value") else str(self.message_type),
            "payload": self.payload,
            "priority": self.priority.value if hasattr(self.priority, "value") else str(self.priority),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hop_count": self.hop_count,
            "max_hops": self.max_hops,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "retry_count": self.retry_count,
            "last_error": self.last_error,
            "checksum": self.checksum,
            "last_attempt_at": self.last_attempt_at,
        }

    def to_json(self) -> str:
        """Serializes message to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OfflineMessage:
        """Constructs an OfflineMessage from a dictionary."""
        payload_val = data.get("payload")
        if isinstance(payload_val, str):
            try:
                payload_val = json.loads(payload_val)
            except Exception:
                payload_val = {"raw_text": payload_val}

        return cls(
            message_id=data.get("message_id", ""),
            alert_id=data.get("alert_id"),
            source_device_id=data.get("source_device_id", "UNKNOWN"),
            destination_device_id=data.get("destination_device_id", "BROADCAST"),
            message_type=data.get("message_type", MessageType.SURVIVOR_DETECTED),
            payload=payload_val or {},
            priority=data.get("priority", MessagePriority.HIGH),
            created_at=data.get("created_at") or datetime.now(timezone.utc).isoformat(),
            expires_at=data.get("expires_at"),
            hop_count=int(data.get("hop_count", 0)),
            max_hops=int(data.get("max_hops", 5)),
            status=data.get("status", MessageStatus.PENDING),
            retry_count=int(data.get("retry_count", 0)),
            last_error=data.get("last_error"),
            checksum=data.get("checksum", ""),
            last_attempt_at=data.get("last_attempt_at"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> OfflineMessage:
        """Constructs an OfflineMessage from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class LoRaPacket:
    """Compact frame for over-the-air RF LoRa simulation and hardware serialization."""
    packet_id: str = ""
    source_id: str = "NODE-01"
    destination_id: str = "BROADCAST"
    message_type: str = "SURVIVOR_DETECTED"
    payload_raw: str = "{}"
    priority: str = "HIGH"
    hop_count: int = 0
    max_hops: int = 5
    rssi_dbm: float = -75.0
    snr_db: float = 9.0
    frequency_mhz: float = 868.0
    spreading_factor: int = 8
    bandwidth_khz: float = 125.0
    tx_power_dbm: float = 14.0
    checksum: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Backward compatibility properties
    @property
    def sender_node_id(self) -> str:
        return self.source_id

    @sender_node_id.setter
    def sender_node_id(self, val: str) -> None:
        self.source_id = val

    @property
    def receiver_node_id(self) -> str:
        return self.destination_id

    @receiver_node_id.setter
    def receiver_node_id(self, val: str) -> None:
        self.destination_id = val

    @property
    def raw_payload(self) -> str:
        return self.payload_raw

    @raw_payload.setter
    def raw_payload(self, val: str) -> None:
        self.payload_raw = val

    def __post_init__(self):
        if not self.packet_id:
            self.packet_id = f"PKT-{uuid.uuid4().hex[:8].upper()}"
        if not self.checksum:
            self.checksum = self.calculate_checksum()

    def calculate_checksum(self) -> str:
        """Calculates CRC32 checksum for packet payload."""
        raw = f"{self.packet_id}:{self.source_id}:{self.destination_id}:{self.message_type}:{self.payload_raw}"
        crc = binascii.crc32(raw.encode("utf-8")) & 0xFFFFFFFF
        return f"{crc:08X}"

    def verify_checksum(self) -> bool:
        """Verifies packet integrity."""
        return self.checksum == self.calculate_checksum()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "source_id": self.source_id,
            "destination_id": self.destination_id,
            "message_type": self.message_type,
            "payload_raw": self.payload_raw,
            "priority": self.priority,
            "hop_count": self.hop_count,
            "max_hops": self.max_hops,
            "rssi_dbm": self.rssi_dbm,
            "snr_db": self.snr_db,
            "frequency_mhz": self.frequency_mhz,
            "spreading_factor": self.spreading_factor,
            "bandwidth_khz": self.bandwidth_khz,
            "tx_power_dbm": self.tx_power_dbm,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "sender_node_id": self.source_id,
            "receiver_node_id": self.destination_id,
            "raw_payload": self.payload_raw,
        }

    @classmethod
    def from_offline_message(cls, message: OfflineMessage) -> LoRaPacket:
        """Constructs a LoRaPacket from an OfflineMessage."""
        type_str = message.message_type.value if hasattr(message.message_type, "value") else str(message.message_type)
        prio_str = message.priority.value if hasattr(message.priority, "value") else str(message.priority)
        payload_str = json.dumps(message.payload, sort_keys=True)
        return cls(
            packet_id=f"PKT-{message.message_id}",
            source_id=message.source_device_id,
            destination_id=message.destination_device_id,
            message_type=type_str,
            payload_raw=payload_str,
            priority=prio_str,
            hop_count=message.hop_count,
            max_hops=message.max_hops,
        )

    def to_offline_message(self) -> OfflineMessage:
        """Reconstructs an OfflineMessage from this LoRaPacket."""
        msg_id = self.packet_id.replace("PKT-", "") if self.packet_id.startswith("PKT-") else self.packet_id
        payload_dict = {}
        if self.payload_raw:
            try:
                payload_dict = json.loads(self.payload_raw)
            except Exception:
                payload_dict = {"raw_text": self.payload_raw}

        return OfflineMessage(
            message_id=msg_id,
            source_device_id=self.source_id,
            destination_device_id=self.destination_id,
            message_type=self.message_type,
            payload=payload_dict,
            priority=self.priority,
            hop_count=self.hop_count,
            max_hops=self.max_hops,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LoRaPacket:
        return cls(
            packet_id=data.get("packet_id", ""),
            source_id=data.get("source_id") or data.get("sender_node_id", "NODE-01"),
            destination_id=data.get("destination_id") or data.get("receiver_node_id", "BROADCAST"),
            message_type=data.get("message_type", "SURVIVOR_DETECTED"),
            payload_raw=data.get("payload_raw") or data.get("raw_payload", "{}"),
            priority=data.get("priority", "HIGH"),
            hop_count=int(data.get("hop_count", 0)),
            max_hops=int(data.get("max_hops", 5)),
            rssi_dbm=float(data.get("rssi_dbm", -75.0)),
            snr_db=float(data.get("snr_db", 9.0)),
            frequency_mhz=float(data.get("frequency_mhz", 868.0)),
            spreading_factor=int(data.get("spreading_factor", 8)),
            bandwidth_khz=float(data.get("bandwidth_khz", 125.0)),
            tx_power_dbm=float(data.get("tx_power_dbm", 14.0)),
            checksum=data.get("checksum", ""),
            created_at=data.get("created_at") or datetime.now(timezone.utc).isoformat(),
        )

