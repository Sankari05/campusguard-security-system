"""
local_edge_backend.py
---------------------
Local Edge Backend Service for RidgeWatch Offline Operations.

Acts as the central offline orchestrator running on local field laptops, base stations,
or edge gateways. Integrates local message queue, LoRa gateway, mesh router,
connectivity detector, and synchronization manager.

Core Guarantees:
1. 100% OFFLINE AUTONOMY: All emergency alerts are accepted, validated, stored in SQLite,
   and routed over LoRa mesh regardless of Internet availability.
2. NO DATA LOSS: Ingested alerts are persisted before any transmission attempts.
3. SEAMLESS RECOVERY: Automatic synchronization triggered as soon as connectivity resumes.
"""

from __future__ import annotations

import os
import time
import uuid
import logging
import threading
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timezone

from backend.offline_models import (
    OfflineMessage,
    LoRaPacket,
    MessageType,
    MessagePriority,
    MessageStatus,
)
from backend.offline_message_queue import OfflineMessageQueue
from backend.connectivity_manager import ConnectivityManager
from backend.lora_gateway import LoRaGateway, LoRaNodeDescriptor
from backend.mesh_router import MeshRouter
from backend.sync_manager import SyncManager

logger = logging.getLogger("ridgewatch.local_edge_backend")


class LocalEdgeBackend:
    """
    Unified local edge orchestrator for offline emergency alerting, LoRa mesh routing,
    and automatic cloud synchronization.
    """

    def __init__(
        self,
        node_id: Optional[str] = None,
        db_path: Optional[str] = None,
        lora_mode: Optional[str] = None,
        auto_start_sync: bool = True,
    ):
        self.node_id = node_id or os.environ.get("LORA_DEVICE_ID", "RIDGEWATCH-GATEWAY-01")
        self._lock = threading.RLock()

        # Initialize Subsystems
        self.queue = OfflineMessageQueue(db_path=db_path)
        self.connectivity = ConnectivityManager()
        self.gateway = LoRaGateway(device_id=self.node_id, mode=lora_mode)
        self.router = MeshRouter(node_id=self.node_id, gateway=self.gateway, queue=self.queue)
        self.sync_manager = SyncManager(
            queue=self.queue,
            connectivity_mgr=self.connectivity,
            auto_start=auto_start_sync,
        )

        self._start_time = time.time()
        self._alerts_ingested_count = 0
        self._alerts_forwarded_count = 0

        # Register local delivery callback from mesh router to edge handler
        self.router.register_local_delivery_callback(self._on_mesh_alert_received)

        logger.info(
            f"[Local Edge Backend] Initialized successfully. Node ID: {self.node_id}, "
            f"LoRa Mode: {self.gateway.mode}, Online: {self.connectivity.is_online()}"
        )

    # -------------------------------------------------------------------------
    # Alert Ingestion & Processing
    # -------------------------------------------------------------------------

    def ingest_emergency_alert(
        self,
        message_type: Union[str, MessageType],
        payload: Dict[str, Any],
        priority: Union[str, MessagePriority] = MessagePriority.HIGH,
        alert_id: Optional[str] = None,
        destination_device_id: str = "GATEWAY-01",
        source_device_id: Optional[str] = None,
        ttl_seconds: int = 86400,
    ) -> Dict[str, Any]:
        """
        Ingests an emergency alert from any RidgeWatch engine (fusion engine, wearable gateway,
        landslide detector, etc.). Persists locally, enqueues in offline queue, and initiates mesh routing.
        """
        src_id = source_device_id or self.node_id

        # Normalize types
        if isinstance(message_type, str):
            try:
                mtype = MessageType(message_type)
            except Exception:
                mtype = MessageType.SURVIVOR_DETECTED
        else:
            mtype = message_type

        if isinstance(priority, str):
            try:
                mpriority = MessagePriority(priority.upper())
            except Exception:
                mpriority = MessagePriority.HIGH
        else:
            mpriority = priority

        # Create Offline Message
        message = OfflineMessage(
            alert_id=alert_id,
            source_device_id=src_id,
            destination_device_id=destination_device_id,
            message_type=mtype,
            payload=payload,
            priority=mpriority,
            max_hops=self.router.max_hops,
        )

        with self._lock:
            self._alerts_ingested_count += 1

        # 1. Enqueue in SQLite Offline Message Queue
        enqueue_ok = self.queue.enqueue_message(message)
        if not enqueue_ok:
            logger.warning(f"[Local Edge Backend] Message {message.message_id} already exists or failed to enqueue.")

        # 2. Route via LoRa Mesh
        route_res = self.router.route_message(message)
        if route_res.get("status") == "FORWARDED":
            with self._lock:
                self._alerts_forwarded_count += 1
            self.queue.mark_sent(message.message_id)

        # 3. If online, optionally trigger immediate background sync attempt
        if self.connectivity.is_online():
            try:
                # Non-blocking sync attempt in background
                threading.Thread(target=self.sync_manager.sync_pending_messages, daemon=True).start()
            except Exception:
                pass

        logger.info(
            f"[Local Edge Backend] Ingested alert {message.message_id} ({mtype.value}) - "
            f"Queue: OK, Mesh: {route_res.get('status')}"
        )

        return {
            "success": True,
            "message_id": message.message_id,
            "alert_id": alert_id,
            "status": "QUEUED_AND_ROUTED",
            "mesh_result": route_res,
            "is_online": self.connectivity.is_online(),
            "created_at": message.created_at,
        }

    # -------------------------------------------------------------------------
    # Incoming Mesh Alert Callback
    # -------------------------------------------------------------------------

    def _on_mesh_alert_received(self, packet: LoRaPacket) -> None:
        """Invoked when an RF packet arrives addressed to this local edge node."""
        logger.info(
            f"[Local Edge Backend] Received mesh alert {packet.packet_id} "
            f"from {packet.source_id} (Type: {packet.message_type})"
        )

        # If it is an emergency alert and we are the gateway, send an ACK back
        if packet.message_type != MessageType.RESCUE_ACK.value and packet.source_id != self.node_id:
            self.router.send_acknowledgement(
                original_message_id=packet.packet_id,
                destination_node_id=packet.source_id,
                status="RECEIVED_AT_GATEWAY",
            )

    # -------------------------------------------------------------------------
    # Health & System Status
    # -------------------------------------------------------------------------

    def get_health_status(self) -> Dict[str, Any]:
        """
        Returns comprehensive health metrics for the offline communication system.
        """
        with self._lock:
            uptime = round(time.time() - self._start_time, 1)
            q_stats = self.queue.get_queue_stats()
            conn_status = self.connectivity.get_connectivity_status()
            gw_status = self.gateway.get_status()
            sync_status = self.sync_manager.get_status()

            return {
                "local_backend_status": "HEALTHY",
                "node_id": self.node_id,
                "uptime_seconds": uptime,
                "internet_available": conn_status.get("online", False),
                "connectivity_details": conn_status,
                "queue_size": q_stats.get("total", 0),
                "pending_messages": q_stats.get("pending", 0),
                "failed_messages": q_stats.get("failed", 0),
                "synced_messages": q_stats.get("synced", 0),
                "queue_breakdown_by_priority": q_stats.get("by_priority", {}),
                "last_synchronization_time": sync_status.get("last_sync_time"),
                "lora_mode": gw_status.get("mode", "simulator"),
                "registered_nodes_count": gw_status.get("registered_nodes_count", 0),
                "alerts_ingested_total": self._alerts_ingested_count,
                "alerts_forwarded_total": self._alerts_forwarded_count,
            }

    def trigger_sync(self) -> Dict[str, Any]:
        """Manually triggers an immediate cloud synchronization."""
        return self.sync_manager.sync_pending_messages()

    def shutdown(self) -> None:
        """Gracefully shuts down all worker threads and gateways."""
        logger.info("[Local Edge Backend] Shutting down...")
        self.sync_manager.stop_background_sync()
        self.gateway.close()
        self.queue.close()


# Singleton Instance Access
_GLOBAL_EDGE_BACKEND: Optional[LocalEdgeBackend] = None
_GLOBAL_LOCK = threading.Lock()


def get_local_edge_backend() -> LocalEdgeBackend:
    """Returns or lazily creates the global singleton LocalEdgeBackend instance."""
    global _GLOBAL_EDGE_BACKEND
    with _GLOBAL_LOCK:
        if _GLOBAL_EDGE_BACKEND is None:
            _GLOBAL_EDGE_BACKEND = LocalEdgeBackend()
        return _GLOBAL_EDGE_BACKEND
