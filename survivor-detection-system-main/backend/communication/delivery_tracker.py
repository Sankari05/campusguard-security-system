"""
delivery_tracker.py
-------------------
Delivery ledger persistence, status tracking, and idempotency verification.
Syncs with SQLite table `communication_delivery` in backend/db.py.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from .models import EmergencyMessage, DeliveryStatus, DeliveryResult

logger = logging.getLogger("ridgewatch.communication.tracker")


class DeliveryTracker:
    """Manages delivery status transitions and idempotency checks."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self._memory_ledger: Dict[str, EmergencyMessage] = {}
        self._idempotency_index: Dict[str, str] = {}  # idempotency_key -> message_id

    def check_idempotency(self, idempotency_key: str, check_db: bool = True) -> Optional[EmergencyMessage]:
        """Returns existing message if duplicate idempotency key is detected."""
        if not idempotency_key:
            return None

        # 1. In-memory check (instant)
        msg_id = self._idempotency_index.get(idempotency_key)
        if msg_id and msg_id in self._memory_ledger:
            return self._memory_ledger[msg_id]

        if not check_db:
            return None

        # 2. Database check
        try:
            try:
                import db
            except ImportError:
                from backend import db

            if hasattr(db, "get_communication_delivery_by_idempotency"):
                row = db.get_communication_delivery_by_idempotency(idempotency_key, db_path=self.db_path)
                if row:
                    msg = self._row_to_message(row)
                    self._memory_ledger[msg.message_id] = msg
                    self._idempotency_index[idempotency_key] = msg.message_id
                    return msg
        except Exception as ex:
            logger.debug(f"[TRACKER] Idempotency DB check exception: {ex}")

        return None

    def record_new_message(self, message: EmergencyMessage, persist_db: bool = True) -> None:
        """Records a newly queued or created message in ledger and database."""
        self._memory_ledger[message.message_id] = message
        if message.idempotency_key:
            self._idempotency_index[message.idempotency_key] = message.message_id

        if persist_db:
            self.persist_to_db(message)

    def persist_to_db(self, message: EmergencyMessage) -> None:
        """Persists message record to SQLite database."""
        try:
            try:
                import db
            except ImportError:
                from backend import db

            if hasattr(db, "log_communication_delivery"):
                db.log_communication_delivery(message.to_dict(), db_path=self.db_path)
        except Exception as ex:
            logger.warning(f"[TRACKER] Failed to persist communication delivery to DB: {ex}")

    def update_result(self, result: DeliveryResult) -> Optional[EmergencyMessage]:
        """Updates delivery ledger following adapter execution."""
        msg = self._memory_ledger.get(result.message_id)
        now_ts = datetime.now(timezone.utc).isoformat()

        if msg:
            msg.status = result.status
            msg.provider_message_id = result.provider_message_id or msg.provider_message_id
            msg.last_error = result.error
            if result.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED):
                msg.dispatched_at = now_ts
            if result.status == DeliveryStatus.DELIVERED:
                msg.delivered_at = now_ts

            msg.delivery_trace.append({
                "channel": result.channel.value if hasattr(result.channel, "value") else str(result.channel),
                "status": result.status.value if hasattr(result.status, "value") else str(result.status),
                "timestamp": now_ts,
                "latency_ms": result.latency_ms,
                "error": result.error,
                "provider_id": result.provider_message_id,
            })

        # Update DB
        try:
            try:
                import db
            except ImportError:
                from backend import db

            if hasattr(db, "update_communication_delivery_status"):
                db.update_communication_delivery_status(
                    message_id=result.message_id,
                    status=result.status.value if hasattr(result.status, "value") else str(result.status),
                    error=result.error,
                    provider_message_id=result.provider_message_id,
                    dispatched_at=now_ts if result.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED) else None,
                    delivered_at=now_ts if result.status == DeliveryStatus.DELIVERED else None,
                    db_path=self.db_path,
                )
        except Exception as ex:
            logger.warning(f"[TRACKER] Failed to update communication delivery in DB: {ex}")

        return msg

    def record_acknowledgement(self, message_id: str, rescuer_id: Optional[str] = None) -> bool:
        """Records explicit two-way rescuer confirmation."""
        now_ts = datetime.now(timezone.utc).isoformat()
        msg = self._memory_ledger.get(message_id)
        if msg:
            msg.status = DeliveryStatus.ACKNOWLEDGED
            msg.acknowledged_at = now_ts
            msg.delivery_trace.append({
                "event": "RESCUER_ACKNOWLEDGED",
                "rescuer_id": rescuer_id,
                "timestamp": now_ts,
            })

        try:
            try:
                import db
            except ImportError:
                from backend import db

            if hasattr(db, "update_communication_delivery_status"):
                db.update_communication_delivery_status(
                    message_id=message_id,
                    status=DeliveryStatus.ACKNOWLEDGED.value,
                    acknowledged_at=now_ts,
                    db_path=self.db_path,
                )
            return True
        except Exception as ex:
            logger.warning(f"[TRACKER] Failed to record ACK in DB: {ex}")
            return False

    def get_message(self, message_id: str) -> Optional[EmergencyMessage]:
        return self._memory_ledger.get(message_id)

    def list_deliveries(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            try:
                import db
            except ImportError:
                from backend import db

            if hasattr(db, "list_communication_deliveries"):
                rows = db.list_communication_deliveries(limit=limit, db_path=self.db_path)
                if rows:
                    return rows
        except Exception:
            pass

        return [m.to_dict() for m in list(self._memory_ledger.values())[-limit:]]

    def _row_to_message(self, row: Dict[str, Any]) -> EmergencyMessage:
        from .models import ChannelType, MessagePriority, DeliveryStatus
        return EmergencyMessage(
            message_id=row["message_id"],
            recipient=row["recipient"],
            payload=row["payload"],
            priority=MessagePriority(row.get("priority", "HIGH")),
            channel=ChannelType(row.get("channel", "SMS_GATEWAY")),
            status=DeliveryStatus(row.get("status", "QUEUED")),
            retry_count=int(row.get("retry_count", 0)),
            idempotency_key=row.get("idempotency_key"),
            created_at=row.get("created_at", datetime.now(timezone.utc).isoformat()),
            expires_at=row.get("expires_at"),
            provider_message_id=row.get("provider_message_id"),
            last_error=row.get("error"),
        )
