"""
offline_message_queue.py
-------------------------
SQLite-backed persistent offline emergency message queue for RidgeWatch.
Stores, prioritizes, deduplicates, and manages the lifecycle of offline alerts
when internet connectivity is degraded or absent.
"""

from __future__ import annotations

import os
import json
import sqlite3
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from .offline_models import OfflineMessage, MessageType, MessagePriority, MessageStatus

logger = logging.getLogger("ridgewatch.offline.queue")

DEFAULT_OFFLINE_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "offline_messages.db"
)


class OfflineMessageQueue:
    """Thread-safe SQLite persistent offline emergency message queue."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("OFFLINE_DB_PATH", DEFAULT_OFFLINE_DB_PATH)
        self._lock = threading.RLock()
        self._ensure_dir()
        self.init_db()

    def _ensure_dir(self) -> None:
        """Ensures parent directory for SQLite database exists."""
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as ex:
                logger.warning(f"[OFFLINE-QUEUE] Could not create directory {db_dir}: {ex}")

    @contextmanager
    def _connect(self):
        """Context manager for SQLite connection with busy_timeout and foreign keys."""
        with self._lock:
            conn = sqlite3.connect(self.db_path, timeout=15.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()

    def init_db(self) -> None:
        """Initializes the offline_messages SQLite table and indexes."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS offline_messages (
                    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id              TEXT UNIQUE NOT NULL,
                    alert_id                TEXT,
                    source_device_id        TEXT NOT NULL,
                    destination_device_id   TEXT NOT NULL,
                    message_type            TEXT NOT NULL,
                    payload_json            TEXT NOT NULL,
                    priority                TEXT NOT NULL DEFAULT 'HIGH',
                    created_at              TEXT NOT NULL,
                    expires_at              TEXT,
                    hop_count               INTEGER NOT NULL DEFAULT 0,
                    max_hops                INTEGER NOT NULL DEFAULT 5,
                    status                  TEXT NOT NULL DEFAULT 'PENDING',
                    retry_count             INTEGER NOT NULL DEFAULT 0,
                    last_error              TEXT,
                    checksum                TEXT NOT NULL,
                    last_attempt_at         TEXT
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_offline_msg_id ON offline_messages(message_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_offline_status ON offline_messages(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_offline_priority ON offline_messages(priority);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_offline_created ON offline_messages(created_at);")

    def enqueue_message(self, message: OfflineMessage) -> bool:
        """
        Enqueues an offline emergency alert into the SQLite ledger.
        Deduplicates by message_id.
        """
        if message.is_expired():
            logger.info(f"[OFFLINE-QUEUE] Refusing to enqueue expired message {message.message_id}")
            return False

        if not message.verify_checksum():
            # Recompute if missing or invalid on initial creation
            message.checksum = message.calculate_checksum()

        payload_json_str = json.dumps(message.payload, sort_keys=True)
        type_str = message.message_type.value if hasattr(message.message_type, "value") else str(message.message_type)
        prio_str = message.priority.value if hasattr(message.priority, "value") else str(message.priority)
        status_str = message.status.value if hasattr(message.status, "value") else str(message.status)

        with self._connect() as conn:
            # Check existing message to prevent duplicate enqueue
            existing = conn.execute(
                "SELECT id, status FROM offline_messages WHERE message_id = ?",
                (message.message_id,),
            ).fetchone()

            if existing:
                logger.info(
                    f"[OFFLINE-QUEUE] Idempotent hit: Message {message.message_id} "
                    f"already in queue (status={existing['status']}). Skipping."
                )
                return False

            conn.execute(
                """
                INSERT INTO offline_messages (
                    message_id, alert_id, source_device_id, destination_device_id,
                    message_type, payload_json, priority, created_at, expires_at,
                    hop_count, max_hops, status, retry_count, last_error,
                    checksum, last_attempt_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.alert_id,
                    message.source_device_id,
                    message.destination_device_id,
                    type_str,
                    payload_json_str,
                    prio_str,
                    message.created_at,
                    message.expires_at,
                    message.hop_count,
                    message.max_hops,
                    status_str,
                    message.retry_count,
                    message.last_error,
                    message.checksum,
                    message.last_attempt_at,
                ),
            )

        logger.info(
            f"[OFFLINE-QUEUE] Enqueued {prio_str} {type_str} message {message.message_id} "
            f"from {message.source_device_id} -> {message.destination_device_id}"
        )
        return True

    def dequeue_pending_messages(self, limit: int = 10, include_retries: bool = True) -> List[OfflineMessage]:
        """
        Retrieves pending messages ordered by Priority (CRITICAL first) and Creation Time (FIFO).
        Automatically drops expired messages.
        """
        self.purge_expired_messages()

        status_filter = "('PENDING')"
        if include_retries:
            status_filter = "('PENDING', 'FAILED')"

        # Priority sort: CRITICAL (0), HIGH (1), MEDIUM (2), LOW (3)
        query = f"""
            SELECT * FROM offline_messages
            WHERE status IN {status_filter}
            ORDER BY
                CASE priority
                    WHEN 'CRITICAL' THEN 0
                    WHEN 'HIGH' THEN 1
                    WHEN 'MEDIUM' THEN 2
                    WHEN 'LOW' THEN 3
                    ELSE 4
                END ASC,
                created_at ASC
            LIMIT ?
        """

        messages: List[OfflineMessage] = []
        with self._connect() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
            for r in rows:
                msg = self._row_to_message(r)
                if not msg.is_expired():
                    messages.append(msg)
                else:
                    # Mark expired in DB
                    conn.execute(
                        "UPDATE offline_messages SET status = 'EXPIRED' WHERE id = ?",
                        (r["id"],),
                    )

        return messages

    def mark_sent(self, message_id: str, destination_device_id: Optional[str] = None) -> bool:
        """Marks message as SENT over local transport (e.g. LoRa mesh hop)."""
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            updates = ["status = 'SENT'", "last_attempt_at = ?"]
            params = [now_ts]
            if destination_device_id:
                updates.append("destination_device_id = ?")
                params.append(destination_device_id)
            params.append(message_id)
            cur = conn.execute(
                f"UPDATE offline_messages SET {', '.join(updates)} WHERE message_id = ?",
                params,
            )
            return cur.rowcount > 0

    def mark_synced(self, message_id: str, sync_metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Marks message as SYNCED to central cloud / external internet gateway."""
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE offline_messages
                SET status = 'SYNCED', last_attempt_at = ?, last_error = NULL
                WHERE message_id = ?
                """,
                (now_ts, message_id),
            )
            logger.info(f"[OFFLINE-QUEUE] Marked message {message_id} as SYNCED")
            return cur.rowcount > 0

    def mark_failed(self, message_id: str, error_message: str, increment_retry: bool = True) -> bool:
        """Records a failed transmission attempt and updates error log."""
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            if increment_retry:
                cur = conn.execute(
                    """
                    UPDATE offline_messages
                    SET status = 'FAILED', retry_count = retry_count + 1,
                        last_error = ?, last_attempt_at = ?
                    WHERE message_id = ?
                    """,
                    (error_message, now_ts, message_id),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE offline_messages
                    SET status = 'FAILED', last_error = ?, last_attempt_at = ?
                    WHERE message_id = ?
                    """,
                    (error_message, now_ts, message_id),
                )
            return cur.rowcount > 0

    def retry_failed_messages(self, max_retries: int = 5) -> int:
        """Resets status of FAILED messages below retry threshold back to PENDING."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE offline_messages
                SET status = 'PENDING'
                WHERE status = 'FAILED' AND retry_count < ?
                """,
                (max_retries,),
            )
            reset_count = cur.rowcount
            if reset_count > 0:
                logger.info(f"[OFFLINE-QUEUE] Reset {reset_count} failed messages to PENDING for retry")
            return reset_count

    def purge_expired_messages(self) -> int:
        """Updates status of all expired messages to EXPIRED."""
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE offline_messages
                SET status = 'EXPIRED'
                WHERE expires_at IS NOT NULL AND expires_at < ? AND status NOT IN ('SYNCED', 'EXPIRED')
                """,
                (now_ts,),
            )
            purged = cur.rowcount
            if purged > 0:
                logger.info(f"[OFFLINE-QUEUE] Purged {purged} expired messages")
            return purged

    def get_message(self, message_id: str) -> Optional[OfflineMessage]:
        """Fetches an offline message by message_id."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM offline_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            return self._row_to_message(row) if row else None

    def get_message_by_id(self, message_id: str) -> Optional[OfflineMessage]:
        """Alias for get_message(message_id)."""
        return self.get_message(message_id)

    def list_messages(self, status: Optional[Union[str, MessageStatus]] = None, limit: int = 50) -> List[OfflineMessage]:
        """Lists offline messages with optional status filter."""
        status_val = status.value if hasattr(status, "value") else (str(status).upper() if status else None)
        with self._connect() as conn:
            if status_val:
                rows = conn.execute(
                    "SELECT * FROM offline_messages WHERE status = ? ORDER BY id DESC LIMIT ?",
                    (status_val, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM offline_messages ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_message(r) for r in rows]

    def get_messages(self, status: Optional[Union[str, MessageStatus]] = None, limit: int = 50) -> List[OfflineMessage]:
        """Alias for list_messages(status, limit)."""
        return self.list_messages(status=status, limit=limit)

    def update_message_status(self, message_id: str, status: Union[str, MessageStatus], last_error: Optional[str] = None) -> bool:
        """Updates the status of a message in the offline queue."""
        status_val = status.value if hasattr(status, "value") else str(status).upper()
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            if last_error:
                cur = conn.execute(
                    "UPDATE offline_messages SET status = ?, last_attempt_at = ?, last_error = ? WHERE message_id = ?",
                    (status_val, now_ts, last_error, message_id),
                )
            else:
                cur = conn.execute(
                    "UPDATE offline_messages SET status = ?, last_attempt_at = ? WHERE message_id = ?",
                    (status_val, now_ts, message_id),
                )
            return cur.rowcount > 0

    def get_queue_stats(self) -> Dict[str, Any]:
        """Returns summary metrics for the offline message queue."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) as c FROM offline_messages").fetchone()["c"]
            pending = conn.execute("SELECT COUNT(*) as c FROM offline_messages WHERE status = 'PENDING'").fetchone()["c"]
            synced = conn.execute("SELECT COUNT(*) as c FROM offline_messages WHERE status = 'SYNCED'").fetchone()["c"]
            failed = conn.execute("SELECT COUNT(*) as c FROM offline_messages WHERE status = 'FAILED'").fetchone()["c"]
            expired = conn.execute("SELECT COUNT(*) as c FROM offline_messages WHERE status = 'EXPIRED'").fetchone()["c"]
            
            prio_rows = conn.execute(
                "SELECT priority, COUNT(*) as c FROM offline_messages WHERE status = 'PENDING' GROUP BY priority"
            ).fetchall()
            prio_counts = {r["priority"]: r["c"] for r in prio_rows}

            return {
                "total": total,
                "pending": pending,
                "synced": synced,
                "failed": failed,
                "expired": expired,
                "total_messages": total,
                "pending_count": pending,
                "synced_count": synced,
                "failed_count": failed,
                "expired_count": expired,
                "by_priority": {
                    "CRITICAL": prio_counts.get("CRITICAL", 0),
                    "HIGH": prio_counts.get("HIGH", 0),
                    "MEDIUM": prio_counts.get("MEDIUM", 0),
                    "LOW": prio_counts.get("LOW", 0),
                },
                "pending_by_priority": {
                    "CRITICAL": prio_counts.get("CRITICAL", 0),
                    "HIGH": prio_counts.get("HIGH", 0),
                    "MEDIUM": prio_counts.get("MEDIUM", 0),
                    "LOW": prio_counts.get("LOW", 0),
                },
            }

    def clear(self) -> None:
        """Clears all records in the queue (primarily for tests)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM offline_messages")

    def close(self) -> None:
        """Closes queue handles and releases lock."""
        pass

    def _row_to_message(self, row: sqlite3.Row) -> OfflineMessage:
        """Converts an SQLite row to an OfflineMessage object."""
        try:
            payload_data = json.loads(row["payload_json"])
        except Exception:
            payload_data = {"raw_text": row["payload_json"]}

        return OfflineMessage(
            message_id=row["message_id"],
            alert_id=row["alert_id"],
            source_device_id=row["source_device_id"],
            destination_device_id=row["destination_device_id"],
            message_type=MessageType(row["message_type"]) if row["message_type"] in MessageType.__members__ else MessageType.SURVIVOR_DETECTED,
            payload=payload_data,
            priority=MessagePriority(row["priority"]) if row["priority"] in MessagePriority.__members__ else MessagePriority.HIGH,
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            hop_count=int(row["hop_count"]),
            max_hops=int(row["max_hops"]),
            status=MessageStatus(row["status"]) if row["status"] in MessageStatus.__members__ else MessageStatus.PENDING,
            retry_count=int(row["retry_count"]),
            last_error=row["last_error"],
            checksum=row["checksum"],
            last_attempt_at=row["last_attempt_at"],
        )


# Singleton instance
_QUEUE_INSTANCE: Optional[OfflineMessageQueue] = None


def get_offline_queue(db_path: Optional[str] = None) -> OfflineMessageQueue:
    """Returns global singleton instance of OfflineMessageQueue."""
    global _QUEUE_INSTANCE
    if _QUEUE_INSTANCE is None or (db_path and _QUEUE_INSTANCE.db_path != db_path):
        _QUEUE_INSTANCE = OfflineMessageQueue(db_path=db_path)
    return _QUEUE_INSTANCE


def reset_offline_queue() -> None:
    """Resets global singleton instance for testing."""
    global _QUEUE_INSTANCE
    _QUEUE_INSTANCE = None
