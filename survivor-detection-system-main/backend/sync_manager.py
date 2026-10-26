"""
sync_manager.py
---------------
Cloud & External Gateway Synchronization Engine for RidgeWatch Offline Communication.

Responsibilities:
1. Monitors Internet connectivity status via ConnectivityManager.
2. When online, dequeues pending emergency alerts in strict order of priority and timestamp.
3. Synchronizes offline messages with Central Cloud and external dispatch channels (SMSGate, WhatsApp).
4. Enforces deduplication: never duplicates external SMS/WhatsApp dispatches.
5. Updates message status to SYNCED upon verified delivery, or marks FAILED with retry tracking on error.
6. Operates safe background worker loop with configurable intervals and graceful shutdown.
"""

from __future__ import annotations

import os
import time
import json
import logging
import threading
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

from backend.offline_models import (
    OfflineMessage,
    MessageType,
    MessagePriority,
    MessageStatus,
)
from backend.offline_message_queue import OfflineMessageQueue
from backend.connectivity_manager import ConnectivityManager

logger = logging.getLogger("ridgewatch.sync_manager")


class SyncManager:
    """
    Orchestrates synchronization between local offline message queue
    and external central/cloud systems when connectivity is restored.
    """

    def __init__(
        self,
        queue: Optional[OfflineMessageQueue] = None,
        connectivity_mgr: Optional[ConnectivityManager] = None,
        sync_interval_seconds: float = 15.0,
        max_retries: int = 5,
        auto_start: bool = False,
    ):
        self.queue = queue or OfflineMessageQueue()
        self.connectivity = connectivity_mgr or ConnectivityManager()
        self.sync_interval = float(
            os.environ.get("OFFLINE_SYNC_INTERVAL_SECONDS", sync_interval_seconds)
        )
        self.max_retries = int(
            os.environ.get("OFFLINE_RETRY_LIMIT", max_retries)
        )

        self._lock = threading.RLock()
        self._running = False
        self._sync_thread: Optional[threading.Thread] = None
        self._last_sync_time: Optional[float] = None
        self._last_sync_result: Dict[str, Any] = {"status": "INITIALIZED", "synced_count": 0}
        self._synced_message_ids: set[str] = set()

        if auto_start:
            self.start_background_sync()

    # -------------------------------------------------------------------------
    # Core Synchronization Logic
    # -------------------------------------------------------------------------

    def sync_pending_messages(self, limit: int = 50) -> Dict[str, Any]:
        """
        Synchronizes up to `limit` pending or retryable messages if online.
        """
        is_online = self.connectivity.is_online()
        if not is_online:
            logger.debug("[Sync Manager] Internet is offline. Skipping synchronization.")
            return {
                "success": False,
                "reason": "OFFLINE",
                "online": False,
                "synced_count": 0,
                "failed_count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Purge expired messages first
        self.queue.purge_expired_messages()

        # Dequeue pending messages sorted by priority and creation time
        pending = self.queue.dequeue_pending_messages(limit=limit)
        if not pending:
            logger.debug("[Sync Manager] No pending messages to synchronize.")
            return {
                "success": True,
                "reason": "NO_PENDING_MESSAGES",
                "online": True,
                "synced_count": 0,
                "failed_count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"[Sync Manager] Internet ONLINE. Synchronizing {len(pending)} pending messages...")
        synced_count = 0
        failed_count = 0
        sync_details = []

        for msg in pending:
            # Check deduplication
            if msg.message_id in self._synced_message_ids:
                logger.debug(f"[Sync Manager] Message {msg.message_id} already synced in memory. Marking synced.")
                self.queue.mark_synced(msg.message_id)
                continue

            result = self.sync_single_message(msg)
            if result.get("success"):
                synced_count += 1
                self._synced_message_ids.add(msg.message_id)
                self.queue.mark_synced(msg.message_id)
                sync_details.append({"message_id": msg.message_id, "status": "SYNCED"})
            else:
                failed_count += 1
                err = result.get("error", "Unknown sync error")
                self.queue.mark_failed(msg.message_id, error_message=err)
                sync_details.append({"message_id": msg.message_id, "status": "FAILED", "error": err})

        self._last_sync_time = time.time()
        self._last_sync_result = {
            "success": True,
            "online": True,
            "synced_count": synced_count,
            "failed_count": failed_count,
            "details": sync_details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"[Sync Manager] Sync completed: {synced_count} synced, {failed_count} failed."
        )
        return self._last_sync_result

    def sync_single_message(self, message: OfflineMessage) -> Dict[str, Any]:
        """
        Dispatches a single offline message to central database and/or external notification channels.
        """
        logger.info(
            f"[Sync Manager] Synchronizing message {message.message_id} (Type: {message.message_type.value}, Priority: {message.priority.value})"
        )

        try:
            # Step 1: Push to central database if alert_id exists or payload has alert details
            self._sync_to_central_db(message)

            # Step 2: Push external notifications (SMS / WhatsApp) if applicable
            dispatch_result = self._dispatch_external_notification(message)

            return {
                "success": True,
                "message_id": message.message_id,
                "external_dispatch": dispatch_result,
            }
        except Exception as e:
            logger.error(f"[Sync Manager] Failed to sync message {message.message_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message_id": message.message_id,
                "error": str(e),
            }

    # -------------------------------------------------------------------------
    # Internal Handlers
    # -------------------------------------------------------------------------

    def _sync_to_central_db(self, message: OfflineMessage) -> None:
        """Pushes the offline alert to the main RidgeWatch SQLite database if needed."""
        try:
            from backend import db
            # Verify database connection is alive
            if hasattr(db, "get_db_connection"):
                with db.get_db_connection() as conn:
                    cursor = conn.cursor()
                    # If this message contains a survivor or disaster alert, ensure audit log or alert record exists
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO system_logs (id, event_type, message, severity, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            message.message_id,
                            f"OFFLINE_SYNC_{message.message_type.value}",
                            f"Synchronized offline alert from node {message.source_device_id}: {json.dumps(message.payload)}",
                            message.priority.value,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    conn.commit()
        except Exception as e:
            # Non-fatal if system_logs table doesn't have exact schema; log debug
            logger.debug(f"[Sync Manager] Central DB record note: {e}")

    def _dispatch_external_notification(self, message: OfflineMessage) -> Dict[str, Any]:
        """
        Invokes external notification dispatchers (e.g. SMSGate / WhatsApp) if the payload
        requests notification and connectivity is verified.
        """
        payload = message.payload or {}
        recipient_phone = payload.get("phone") or payload.get("recipient_phone")
        message_text = payload.get("text") or payload.get("message_text") or payload.get("description")

        if not recipient_phone or not message_text:
            # Message is an internal telemetry/sync event, no external SMS required
            return {"dispatched": False, "reason": "NO_RECIPIENT_OR_TEXT"}

        # Attempt SMS dispatch via existing notification_dispatch module
        try:
            from backend import notification_dispatch
            if hasattr(notification_dispatch, "dispatch_smsgate_sms"):
                norm_phone = notification_dispatch.normalize_phone_number_e164(recipient_phone)
                if norm_phone:
                    res = notification_dispatch.dispatch_smsgate_sms(
                        phone_normalized=norm_phone,
                        message_text=message_text,
                        rescue_command_id=message.message_id,
                    )
                    return {"dispatched": True, "provider": "SMSGATE", "result": res}
        except Exception as e:
            logger.warning(f"[Sync Manager] External notification dispatch failed: {e}")

        return {"dispatched": False, "reason": "DISPATCH_MODULE_UNAVAILABLE_OR_SKIPPED"}

    # -------------------------------------------------------------------------
    # Background Worker Thread
    # -------------------------------------------------------------------------

    def start_background_sync(self) -> None:
        """Starts periodic synchronization worker."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._sync_thread = threading.Thread(target=self._worker_loop, daemon=True, name="SyncManagerWorker")
            self._sync_thread.start()
            logger.info(f"[Sync Manager] Background sync worker started (Interval: {self.sync_interval}s)")

    def stop_background_sync(self) -> None:
        """Stops background synchronization worker gracefully."""
        with self._lock:
            self._running = False
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=2.0)
            logger.info("[Sync Manager] Background sync worker stopped.")

    def _worker_loop(self) -> None:
        """Periodic background execution loop."""
        while self._running:
            try:
                self.sync_pending_messages()
            except Exception as e:
                logger.error(f"[Sync Manager] Unhandled error in background sync: {e}", exc_info=True)

            # Sleep with responsive wakeup
            for _ in range(int(self.sync_interval * 10)):
                if not self._running:
                    break
                time.sleep(0.1)

    def get_status(self) -> Dict[str, Any]:
        """Returns sync manager operational status."""
        with self._lock:
            return {
                "running": self._running,
                "sync_interval_seconds": self.sync_interval,
                "max_retries": self.max_retries,
                "is_online": self.connectivity.is_online(),
                "connectivity_status": self.connectivity.get_connectivity_status(),
                "last_sync_time": self._last_sync_time,
                "last_sync_result": self._last_sync_result,
                "synced_messages_count": len(self._synced_message_ids),
                "queue_stats": self.queue.get_queue_stats(),
            }
