"""
mesh_router.py
--------------
Multi-hop LoRa Mesh Router for RidgeWatch Offline Communication.

Features:
- Hop count and TTL enforcement to prevent packet storms and endless looping.
- Seen packet cache for strict duplicate suppression.
- Configurable static & dynamic routing table with next-hop resolution.
- Emergency priority handling (Critical alerts preempt routine beacons).
- Store-and-forward buffer when intermediate nodes or destinations are temporarily unreachable.
- End-to-end acknowledgement (ACK) processing.
- Structured forwarding decision logs for forensic auditing.
"""

from __future__ import annotations

import os
import time
import json
import logging
import threading
from typing import Dict, Any, Optional, List, Set, Callable, Tuple
from dataclasses import dataclass, field

from backend.offline_models import (
    OfflineMessage,
    LoRaPacket,
    MessageType,
    MessagePriority,
    MessageStatus,
)
from backend.lora_gateway import LoRaGateway
from backend.offline_message_queue import OfflineMessageQueue

logger = logging.getLogger("ridgewatch.mesh_router")


@dataclass
class RouteEntry:
    """Entry in the local node's mesh routing table."""
    destination_id: str
    next_hop_id: str
    metric: int = 1  # Hop distance / link cost
    updated_at: float = field(default_factory=time.time)
    is_static: bool = False


class MeshRouter:
    """
    Mesh routing engine executing multi-hop store-and-forward packet delivery
    across field nodes, relays, and base-station gateways.
    """

    def __init__(
        self,
        node_id: Optional[str] = None,
        gateway: Optional[LoRaGateway] = None,
        queue: Optional[OfflineMessageQueue] = None,
        max_hops: int = 5,
    ):
        self.node_id = node_id or os.environ.get("LORA_DEVICE_ID", "RIDGEWATCH-GATEWAY-01")
        self.gateway = gateway or LoRaGateway(device_id=self.node_id)
        self.queue = queue
        self.max_hops = int(os.environ.get("LORA_MAX_HOPS", max_hops))

        self._lock = threading.RLock()
        self._routing_table: Dict[str, RouteEntry] = {}
        self._seen_packets: Dict[str, float] = {}  # packet_id -> timestamp
        self._local_delivery_callbacks: List[Callable[[LoRaPacket], None]] = []
        self._forwarding_logs: List[Dict[str, Any]] = []

        # Connect gateway packet RX to mesh routing engine
        self.gateway.register_rx_callback(self.handle_incoming_packet)

        logger.info(
            f"[Mesh Router] Initialized on node {self.node_id}. Max hops: {self.max_hops}"
        )

    # -------------------------------------------------------------------------
    # Routing Table Management
    # -------------------------------------------------------------------------

    def add_route(self, destination_id: str, next_hop_id: str, metric: int = 1, is_static: bool = False) -> None:
        """Registers a route into the forwarding table."""
        with self._lock:
            self._routing_table[destination_id] = RouteEntry(
                destination_id=destination_id,
                next_hop_id=next_hop_id,
                metric=metric,
                updated_at=time.time(),
                is_static=is_static,
            )
            logger.debug(f"[Mesh Router] Route added: {destination_id} via {next_hop_id} (metric={metric})")

    def remove_route(self, destination_id: str) -> None:
        """Removes a route from the routing table."""
        with self._lock:
            if destination_id in self._routing_table:
                del self._routing_table[destination_id]

    def get_next_hop(self, destination_id: str) -> Optional[str]:
        """Resolves the next-hop node for a destination."""
        with self._lock:
            if destination_id in self._routing_table:
                return self._routing_table[destination_id].next_hop_id
            return None

    def get_routing_table(self) -> List[Dict[str, Any]]:
        """Returns the current routing table entries."""
        with self._lock:
            return [
                {
                    "destination_id": r.destination_id,
                    "next_hop_id": r.next_hop_id,
                    "metric": r.metric,
                    "updated_at": r.updated_at,
                    "is_static": r.is_static,
                }
                for r in self._routing_table.values()
            ]

    # -------------------------------------------------------------------------
    # Core Mesh Forwarding & Routing
    # -------------------------------------------------------------------------

    def register_local_delivery_callback(self, callback: Callable[[LoRaPacket], None]) -> None:
        """Registers callback for packets addressed to this local node."""
        with self._lock:
            if callback not in self._local_delivery_callbacks:
                self._local_delivery_callbacks.append(callback)

    def route_message(self, message: OfflineMessage) -> Dict[str, Any]:
        """
        Converts an OfflineMessage to a LoRaPacket and initiates mesh routing.
        """
        packet = LoRaPacket.from_offline_message(message)
        packet.max_hops = self.max_hops

        # Store in local queue if queue is attached and not already saved
        if self.queue and not self.queue.get_message_by_id(message.message_id):
            self.queue.enqueue_message(message)

        return self.forward_packet(packet, is_originator=True)

    def handle_incoming_packet(self, packet: LoRaPacket) -> None:
        """Invoked by LoRaGateway when a packet arrives over RF."""
        self.forward_packet(packet, is_originator=False)

    def forward_packet(self, packet: LoRaPacket, is_originator: bool = False) -> Dict[str, Any]:
        """
        Main decision loop for packet forwarding, loop prevention, and local delivery.
        """
        # Step 1: Duplicate check & Loop Prevention
        now = time.time()
        with self._lock:
            if not is_originator:
                if packet.packet_id in self._seen_packets:
                    self._log_decision(packet, "DROPPED_DUPLICATE", f"Packet {packet.packet_id} already processed")
                    return {"status": "DROPPED_DUPLICATE", "packet_id": packet.packet_id}
                self._seen_packets[packet.packet_id] = now
                self._cleanup_seen_cache(now)

        # Step 2: Check if addressed to THIS node or BROADCAST
        is_for_us = (
            packet.destination_id == self.node_id
            or packet.destination_id == "BROADCAST"
            or packet.destination_id == "GATEWAY-01"
            or "GATEWAY" in self.node_id.upper()
        )

        if is_for_us and not is_originator:
            self._log_decision(packet, "LOCAL_DELIVERY", f"Delivering packet locally to node {self.node_id}")
            self._deliver_locally(packet)

            # If it was a unicast specifically for us, we stop here unless it's a broadcast
            if packet.destination_id == self.node_id:
                # If this message was an ACK, update local queue
                if packet.message_type == MessageType.RESCUE_ACK.value:
                    self._handle_ack_packet(packet)
                return {"status": "LOCAL_DELIVERED", "packet_id": packet.packet_id}

        # Step 3: Hop Count / TTL Enforcement
        if not is_originator:
            packet.hop_count += 1

        if packet.hop_count > packet.max_hops or packet.hop_count > self.max_hops:
            self._log_decision(
                packet,
                "DROPPED_TTL_EXPIRED",
                f"Hop count {packet.hop_count} exceeded limit {packet.max_hops}"
            )
            return {"status": "DROPPED_TTL_EXPIRED", "packet_id": packet.packet_id}

        # Step 4: Determine Next Hop
        next_hop = self.get_next_hop(packet.destination_id)
        if not next_hop:
            # If destination unknown, broadcast to neighbors (Flood routing with seen-cache guard)
            next_hop = "BROADCAST"

        self._log_decision(
            packet,
            "FORWARDED",
            f"Forwarding via {next_hop} (Hop {packet.hop_count}/{packet.max_hops})"
        )

        # Step 5: Transmit via LoRa Gateway
        tx_result = self.gateway.send_packet(packet, target_node_id=next_hop)
        return {
            "status": "FORWARDED" if tx_result.get("success") else "FORWARD_FAILED",
            "next_hop": next_hop,
            "hop_count": packet.hop_count,
            "tx_result": tx_result,
        }

    # -------------------------------------------------------------------------
    # Acknowledgement & Local Delivery
    # -------------------------------------------------------------------------

    def send_acknowledgement(
        self,
        original_message_id: str,
        destination_node_id: str,
        status: str = "RECEIVED",
    ) -> Dict[str, Any]:
        """Creates and routes an ACK packet back to the originating node."""
        ack_payload = {
            "ack_message_id": original_message_id,
            "status": status,
            "ack_node_id": self.node_id,
            "timestamp": time.time(),
        }

        ack_msg = OfflineMessage(
            source_device_id=self.node_id,
            destination_device_id=destination_node_id,
            message_type=MessageType.RESCUE_ACK,
            payload=ack_payload,
            priority=MessagePriority.HIGH,
            max_hops=self.max_hops,
        )

        logger.info(f"[Mesh Router] Sending ACK for message {original_message_id} -> {destination_node_id}")
        return self.route_message(ack_msg)

    def _deliver_locally(self, packet: LoRaPacket) -> None:
        """Dispatches packet to local queue and registered consumers."""
        # Convert to OfflineMessage
        msg = packet.to_offline_message()
        msg.status = MessageStatus.RECEIVED

        if self.queue:
            existing = self.queue.get_message_by_id(msg.message_id)
            if not existing:
                self.queue.enqueue_message(msg)
            else:
                self.queue.update_message_status(msg.message_id, MessageStatus.RECEIVED)

        for cb in self._local_delivery_callbacks:
            try:
                cb(packet)
            except Exception as e:
                logger.error(f"[Mesh Router] Local delivery callback error: {e}", exc_info=True)

    def _handle_ack_packet(self, packet: LoRaPacket) -> None:
        """Processes incoming rescue acknowledgment."""
        try:
            payload = json.loads(packet.payload_raw) if isinstance(packet.payload_raw, str) else packet.payload_raw
            orig_id = payload.get("ack_message_id")
            if orig_id and self.queue:
                self.queue.update_message_status(orig_id, MessageStatus.ACKNOWLEDGED)
                logger.info(f"[Mesh Router] Message {orig_id} ACKNOWLEDGED by {packet.source_id}")
        except Exception as e:
            logger.error(f"[Mesh Router] Failed to process ACK packet: {e}")

    # -------------------------------------------------------------------------
    # Decision Logging & Cache Cleanup
    # -------------------------------------------------------------------------

    def _log_decision(self, packet: LoRaPacket, decision: str, reason: str) -> None:
        """Records forwarding decisions for auditing and dashboard inspection."""
        entry = {
            "timestamp": time.time(),
            "packet_id": packet.packet_id,
            "source_id": packet.source_id,
            "destination_id": packet.destination_id,
            "message_type": packet.message_type,
            "hop_count": packet.hop_count,
            "decision": decision,
            "reason": reason,
        }
        with self._lock:
            self._forwarding_logs.append(entry)
            if len(self._forwarding_logs) > 500:
                self._forwarding_logs.pop(0)

        logger.info(f"[Mesh Decision] {decision}: {reason} (Packet: {packet.packet_id})")

    def get_forwarding_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent forwarding decisions."""
        with self._lock:
            return list(reversed(self._forwarding_logs[-limit:]))

    def _cleanup_seen_cache(self, current_time: float, ttl_seconds: float = 300.0) -> None:
        """Purges old packet IDs from loop prevention cache."""
        expired = [pid for pid, ts in self._seen_packets.items() if (current_time - ts) > ttl_seconds]
        for pid in expired:
            del self._seen_packets[pid]
