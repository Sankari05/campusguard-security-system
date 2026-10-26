"""
test_offline_communication.py
------------------------------
Comprehensive Unit and Integration Test Suite for the RidgeWatch Resilient
Offline Emergency Communication Subsystem.

Tests:
1. Message models, checksum calculation, and corruption detection
2. Message TTL expiration handling
3. Offline queue persistence and priority-based ordering
4. Idempotency and duplicate message suppression
5. Retry count limits and failure state tracking
6. Non-blocking connectivity probing and simulation overrides
7. LoRa gateway RF propagation modeling (RSSI, SNR, Time-on-Air)
8. LoRa range boundary enforcement and packet loss
9. Multi-hop mesh routing and routing table resolution
10. Mesh loop prevention and seen-packet cache suppression
11. Max-hops / TTL expiry packet drop
12. End-to-end acknowledgement (ACK) processing
13. Sync manager offline message holding & online auto-synchronization
14. Deduplication: no duplicate external SMS/WhatsApp dispatches
15. Local edge backend orchestration and health status
16. FastAPI REST endpoints (/api/offline/*)
"""

import os
import time
import json
import pytest
from datetime import datetime, timezone, timedelta

from backend.offline_models import (
    OfflineMessage,
    LoRaPacket,
    MessageType,
    MessagePriority,
    MessageStatus,
    compute_message_checksum,
)
from backend.offline_message_queue import OfflineMessageQueue
from backend.connectivity_manager import ConnectivityManager
from backend.lora_gateway import LoRaGateway, LoRaNodeDescriptor
from backend.mesh_router import MeshRouter
from backend.sync_manager import SyncManager
from backend.local_edge_backend import LocalEdgeBackend


# =============================================================================
# 1. OFFLINE MESSAGE MODEL & CHECKSUM INTEGRITY TESTS
# =============================================================================

def test_offline_message_creation_and_checksum():
    """Verifies that OfflineMessage computes a valid CRC32 checksum upon creation."""
    msg = OfflineMessage(
        source_device_id="NODE-ALPHA",
        destination_device_id="GATEWAY-01",
        message_type=MessageType.SURVIVOR_DETECTED,
        payload={"victim_id": "V-101", "sps": 0.95},
        priority=MessagePriority.CRITICAL,
    )

    assert msg.message_id.startswith("OFF-")
    assert len(msg.checksum) == 8
    assert msg.verify_checksum() is True
    assert msg.is_expired() is False


def test_offline_message_corrupted_payload_detection():
    """Verifies that tampering with an immutable message payload fails checksum verification."""
    msg = OfflineMessage(
        source_device_id="NODE-ALPHA",
        destination_device_id="GATEWAY-01",
        message_type=MessageType.EARTHQUAKE_ALERT,
        payload={"magnitude": 6.8},
        priority=MessagePriority.CRITICAL,
    )

    assert msg.verify_checksum() is True

    # Tamper with payload
    msg.payload["magnitude"] = 7.9
    assert msg.verify_checksum() is False


def test_offline_message_ttl_expiration():
    """Verifies that expired messages are accurately identified."""
    past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    future_time = (datetime.now(timezone.utc) + timedelta(seconds=3600)).isoformat()

    expired_msg = OfflineMessage(
        message_type=MessageType.FLOOD_ALERT,
        payload={"level_m": 4.5},
        expires_at=past_time,
    )
    assert expired_msg.is_expired() is True

    valid_msg = OfflineMessage(
        message_type=MessageType.FLOOD_ALERT,
        payload={"level_m": 4.5},
        expires_at=future_time,
    )
    assert valid_msg.is_expired() is False


# =============================================================================
# 2. OFFLINE MESSAGE QUEUE PERSISTENCE & PRIORITY TESTS
# =============================================================================

def test_offline_queue_enqueue_and_retrieve(tmp_path):
    """Verifies storing and retrieving offline messages from isolated SQLite database."""
    db_file = tmp_path / "test_queue.db"
    queue = OfflineMessageQueue(db_path=str(db_file))

    msg = OfflineMessage(
        source_device_id="NODE-01",
        destination_device_id="GATEWAY-01",
        message_type=MessageType.SURVIVOR_DETECTED,
        payload={"victim_id": "V-202"},
        priority=MessagePriority.HIGH,
    )

    success = queue.enqueue_message(msg)
    assert success is True

    fetched = queue.get_message_by_id(msg.message_id)
    assert fetched is not None
    assert fetched.message_id == msg.message_id
    assert fetched.payload == {"victim_id": "V-202"}
    assert fetched.status == MessageStatus.PENDING


def test_offline_queue_duplicate_prevention(tmp_path):
    """Verifies that duplicate message_ids are ignored idempotently."""
    db_file = tmp_path / "test_dup.db"
    queue = OfflineMessageQueue(db_path=str(db_file))

    msg = OfflineMessage(
        message_id="OFF-FIXED-DUP-ID-01",
        source_device_id="NODE-01",
        destination_device_id="GATEWAY-01",
        message_type=MessageType.LANDSLIDE_ALERT,
        payload={"risk": "HIGH"},
    )

    first_enqueue = queue.enqueue_message(msg)
    second_enqueue = queue.enqueue_message(msg)

    assert first_enqueue is True
    assert second_enqueue is False

    stats = queue.get_queue_stats()
    assert stats["total"] == 1


def test_offline_queue_priority_ordering(tmp_path):
    """Verifies that dequeuing returns CRITICAL before HIGH before MEDIUM before LOW."""
    db_file = tmp_path / "test_prio.db"
    queue = OfflineMessageQueue(db_path=str(db_file))

    msg_low = OfflineMessage(message_id="M-LOW", priority=MessagePriority.LOW, payload={"k": "low"})
    msg_crit = OfflineMessage(message_id="M-CRIT", priority=MessagePriority.CRITICAL, payload={"k": "crit"})
    msg_high = OfflineMessage(message_id="M-HIGH", priority=MessagePriority.HIGH, payload={"k": "high"})
    msg_med = OfflineMessage(message_id="M-MED", priority=MessagePriority.MEDIUM, payload={"k": "med"})

    queue.enqueue_message(msg_low)
    queue.enqueue_message(msg_med)
    queue.enqueue_message(msg_crit)
    queue.enqueue_message(msg_high)

    dequeued = queue.dequeue_pending_messages(limit=10)
    assert len(dequeued) == 4
    assert dequeued[0].message_id == "M-CRIT"
    assert dequeued[1].message_id == "M-HIGH"
    assert dequeued[2].message_id == "M-MED"
    assert dequeued[3].message_id == "M-LOW"


def test_offline_queue_retry_and_failure_tracking(tmp_path):
    """Verifies mark_failed, retry increment, and retry reset logic."""
    db_file = tmp_path / "test_retry.db"
    queue = OfflineMessageQueue(db_path=str(db_file))

    msg = OfflineMessage(message_id="M-FAIL-01", priority=MessagePriority.HIGH)
    queue.enqueue_message(msg)

    # Mark failed
    queue.mark_failed("M-FAIL-01", error_message="Radio timeout", increment_retry=True)
    msg_after = queue.get_message_by_id("M-FAIL-01")
    assert msg_after.status == MessageStatus.FAILED
    assert msg_after.retry_count == 1
    assert msg_after.last_error == "Radio timeout"

    # Reset retryable messages
    reset_count = queue.retry_failed_messages(max_retries=5)
    assert reset_count == 1
    msg_reset = queue.get_message_by_id("M-FAIL-01")
    assert msg_reset.status == MessageStatus.PENDING


# =============================================================================
# 3. CONNECTIVITY MANAGER TESTS
# =============================================================================

def test_connectivity_manager_simulation_override():
    """Verifies forced offline and online simulation overrides."""
    conn = ConnectivityManager(cache_ttl_sec=0.1)

    # Force Offline
    conn.set_simulated_connectivity(False)
    assert conn.is_online() is False
    status_off = conn.get_connectivity_status()
    assert status_off["is_online"] is False
    assert status_off["forced_simulation"] is False

    # Force Online
    conn.set_simulated_connectivity(True)
    assert conn.is_online() is True
    status_on = conn.get_connectivity_status()
    assert status_on["is_online"] is True
    assert status_on["forced_simulation"] is True

    # Clear Override
    conn.clear_simulation_override()
    status_cleared = conn.get_connectivity_status()
    assert status_cleared["forced_simulation"] is None


# =============================================================================
# 4. LORA GATEWAY PROPAGATION & SIMULATOR TESTS
# =============================================================================

def test_lora_gateway_propagation_calculation():
    """Verifies simulated Log-Distance Path Loss, RSSI, SNR, and Time-on-Air modeling."""
    gw = LoRaGateway(device_id="GW-TEST-01", mode="simulator", max_range_meters=5000.0)

    packet = LoRaPacket(
        source_id="NODE-01",
        destination_id="GW-TEST-01",
        message_type="SURVIVOR_DETECTED",
        payload_raw='{"sps": 0.9}',
    )

    res = gw.send_packet(packet, target_node_id="GW-TEST-01", simulated_distance_m=500.0)
    assert res["success"] is True
    assert res["simulated"] is True
    assert res["distance_meters"] == 500.0
    assert -120.0 <= res["rssi_dbm"] <= -20.0
    assert res["time_on_air_ms"] > 0.0


def test_lora_gateway_out_of_range_handling():
    """Verifies that packets beyond max_range_meters fail with clear error."""
    gw = LoRaGateway(device_id="GW-TEST-01", mode="simulator", max_range_meters=2000.0)

    packet = LoRaPacket(
        source_id="NODE-01",
        destination_id="GW-TEST-01",
        message_type="AVALANCHE_ALERT",
        payload_raw="{}",
    )

    res = gw.send_packet(packet, target_node_id="GW-TEST-01", simulated_distance_m=3500.0)
    assert res["success"] is False
    assert "Out of range" in res["error"]


def test_lora_gateway_packet_deduplication():
    """Verifies that receiving the identical packet twice returns duplicate flag."""
    gw = LoRaGateway(device_id="GW-TEST-01", mode="simulator")

    packet = LoRaPacket(
        packet_id="PKT-UNIQUE-1234",
        source_id="NODE-01",
        destination_id="GW-TEST-01",
        message_type="SURVIVOR_DETECTED",
        payload_raw='{"test": true}',
    )

    rx1 = gw.receive_packet(packet)
    assert rx1["success"] is True
    assert rx1["duplicate"] is False

    rx2 = gw.receive_packet(packet)
    assert rx2["success"] is True
    assert rx2["duplicate"] is True


# =============================================================================
# 5. MESH ROUTER & MULTI-HOP TESTS
# =============================================================================

def test_mesh_router_forwarding_and_loop_prevention():
    """Verifies multi-hop routing, hop count increment, and loop suppression."""
    gw = LoRaGateway(device_id="RELAY-01", mode="simulator")
    router = MeshRouter(node_id="RELAY-01", gateway=gw, max_hops=5)

    router.add_route(destination_id="GATEWAY-BASE", next_hop_id="GATEWAY-BASE", metric=1)

    packet = LoRaPacket(
        packet_id="PKT-ROUTING-TEST-01",
        source_id="NODE-ORIGIN",
        destination_id="GATEWAY-BASE",
        message_type="SURVIVOR_DETECTED",
        payload_raw='{"victim_id": "V-55"}',
        hop_count=0,
        max_hops=5,
    )

    # First forward attempt
    fwd1 = router.forward_packet(packet, is_originator=False)
    assert fwd1["status"] == "FORWARDED"
    assert fwd1["next_hop"] == "GATEWAY-BASE"
    assert fwd1["hop_count"] == 1

    # Loop attack / duplicate arrival
    fwd_dup = router.forward_packet(packet, is_originator=False)
    assert fwd_dup["status"] == "DROPPED_DUPLICATE"


def test_mesh_router_max_hops_exceeded():
    """Verifies dropping packets when hop_count exceeds max_hops."""
    gw = LoRaGateway(device_id="RELAY-01", mode="simulator")
    router = MeshRouter(node_id="RELAY-01", gateway=gw, max_hops=3)

    packet = LoRaPacket(
        packet_id="PKT-EXPIRED-HOPS",
        source_id="NODE-ORIGIN",
        destination_id="GATEWAY-BASE",
        hop_count=3,
        max_hops=3,
    )

    res = router.forward_packet(packet, is_originator=False)
    assert res["status"] == "DROPPED_TTL_EXPIRED"


def test_mesh_router_acknowledgement():
    """Verifies sending end-to-end RESCUE_ACK packet back to origin."""
    gw = LoRaGateway(device_id="GATEWAY-01", mode="simulator")
    router = MeshRouter(node_id="GATEWAY-01", gateway=gw)

    ack_res = router.send_acknowledgement(
        original_message_id="OFF-ORIGIN-MSG-99",
        destination_node_id="NODE-ORIGIN",
        status="DELIVERED_TO_BASE",
    )

    assert ack_res["status"] in ("FORWARDED", "LOCAL_DELIVERED")


# =============================================================================
# 6. SYNC MANAGER & CLOUD RECOVERY TESTS
# =============================================================================

def test_sync_manager_offline_holding(tmp_path):
    """Verifies that while Internet is offline, messages remain safely stored locally."""
    db_file = tmp_path / "test_sync_off.db"
    queue = OfflineMessageQueue(db_path=str(db_file))
    conn = ConnectivityManager()
    conn.set_simulated_connectivity(False)

    sync_mgr = SyncManager(queue=queue, connectivity_mgr=conn, auto_start=False)

    msg = OfflineMessage(
        message_id="M-OFFLINE-HOLD",
        payload={"alert": "debris flow"},
        priority=MessagePriority.HIGH,
    )
    queue.enqueue_message(msg)

    res = sync_mgr.sync_pending_messages()
    assert res["success"] is False
    assert res["reason"] == "OFFLINE"

    # Verify message is still PENDING
    assert queue.get_message_by_id("M-OFFLINE-HOLD").status == MessageStatus.PENDING


def test_sync_manager_online_auto_sync_and_idempotency(tmp_path):
    """Verifies that when Internet returns, messages are synced without duplicates."""
    db_file = tmp_path / "test_sync_on.db"
    queue = OfflineMessageQueue(db_path=str(db_file))
    conn = ConnectivityManager()
    conn.set_simulated_connectivity(True)

    sync_mgr = SyncManager(queue=queue, connectivity_mgr=conn, auto_start=False)

    msg = OfflineMessage(
        message_id="M-ONLINE-SYNC",
        payload={"victim_id": "V-999", "phone": "+918098897666", "text": "Rescue needed"},
        priority=MessagePriority.CRITICAL,
    )
    queue.enqueue_message(msg)

    # First sync: should succeed
    res1 = sync_mgr.sync_pending_messages()
    assert res1["success"] is True
    assert res1["synced_count"] == 1

    msg_synced = queue.get_message_by_id("M-ONLINE-SYNC")
    assert msg_synced.status == MessageStatus.SYNCED

    # Second sync: idempotent, zero dequeued
    res2 = sync_mgr.sync_pending_messages()
    assert res2["success"] is True
    assert res2["synced_count"] == 0


# =============================================================================
# 7. LOCAL EDGE BACKEND ORCHESTRATION TESTS
# =============================================================================

def test_local_edge_backend_alert_ingestion(tmp_path):
    """Verifies full end-to-end edge backend ingestion and health check."""
    db_file = tmp_path / "test_edge.db"
    edge = LocalEdgeBackend(node_id="EDGE-01", db_path=str(db_file), auto_start_sync=False)
    edge.connectivity.set_simulated_connectivity(False)

    ingest_res = edge.ingest_emergency_alert(
        message_type="SURVIVOR_DETECTED",
        payload={"victim_id": "V-404", "sps": 0.88},
        priority="CRITICAL",
    )

    assert ingest_res["success"] is True
    assert ingest_res["status"] == "QUEUED_AND_ROUTED"

    health = edge.get_health_status()
    assert health["local_backend_status"] == "HEALTHY"
    assert health["queue_size"] == 1
    assert health["alerts_ingested_total"] == 1
    assert health["internet_available"] is False

    edge.shutdown()


# =============================================================================
# 8. FASTAPI REST API ENDPOINTS TESTS
# =============================================================================

def test_offline_api_endpoints(api_client):
    """Verifies /api/offline/* REST endpoints."""
    # 1. GET /api/offline/status
    resp_status = api_client.get("/api/offline/status")
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert "local_backend_status" in status_data
    assert "internet_available" in status_data

    # 2. GET /api/offline/queue
    resp_queue = api_client.get("/api/offline/queue")
    assert resp_queue.status_code == 200
    queue_data = resp_queue.json()
    assert "queue_stats" in queue_data
    assert "messages" in queue_data

    # 3. POST /api/offline/enqueue
    resp_enqueue = api_client.post(
        "/api/offline/enqueue",
        json={
            "message_type": "MEDICAL_EMERGENCY",
            "payload": {"triage": "CRITICAL", "bpm": 130},
            "priority": "CRITICAL",
            "destination_device_id": "GATEWAY-01",
        },
    )
    assert resp_enqueue.status_code == 200
    enqueue_data = resp_enqueue.json()
    assert enqueue_data["success"] is True
    assert "message_id" in enqueue_data

    # 4. POST /api/offline/simulator/send
    resp_sim = api_client.post(
        "/api/offline/simulator/send",
        json={
            "source_id": "NODE-FIELD-01",
            "destination_id": "GATEWAY-01",
            "message_type": "FLOOD_ALERT",
            "payload": {"water_level_m": 3.8},
            "simulated_distance_m": 600.0,
        },
    )
    assert resp_sim.status_code == 200
    sim_data = resp_sim.json()
    assert sim_data["success"] is True
    assert "tx_result" in sim_data

    # 5. GET /api/offline/nodes
    resp_nodes = api_client.get("/api/offline/nodes")
    assert resp_nodes.status_code == 200
    nodes_data = resp_nodes.json()
    assert "nodes" in nodes_data
    assert "routing_table" in nodes_data

    # 6. POST /api/offline/sync
    resp_sync = api_client.post("/api/offline/sync")
    assert resp_sync.status_code == 200
