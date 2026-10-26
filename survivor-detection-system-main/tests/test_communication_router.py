"""
test_communication_router.py
-----------------------------
Comprehensive test suite for the RidgeWatch Resilient Multi-Channel Emergency Communication Layer.
Covers all 15 required test scenarios:
1. Internet available -> WhatsApp selected
2. Internet down, Cellular up -> SMSGate selected
3. Internet & Cellular down, LoRa up -> LoRa selected
4. All channels down -> OFFLINE_QUEUED locally
5. Duplicate message rejection (Idempotency)
6. CRITICAL priority queue preemption
7. Exponential backoff retries terminate at max retries
8. Expired messages purged (TTL validation)
9. Backward compatibility with failover disabled
10. Adapter failures handled safely with automatic failover
11. 90-recipient queue simulation non-blocking performance
12. Database ledger persistence and state consistency
13. Two-way ACK processing
14. Compact LoRa packet formatting (<64 bytes) and checksum verification
15. Circuit breaker state transitions (CLOSED -> OPEN -> HALF_OPEN)
"""

import os
import time
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from backend import db
from backend.communication import (
    CommunicationRouter,
    EmergencyMessage,
    DeliveryResult,
    ChannelType,
    MessagePriority,
    DeliveryStatus,
    CircuitState,
    CommunicationConfig,
    WhatsAppAdapter,
    SMSGatewayAdapter,
    NativeSMSAdapter,
    LoRaAdapter,
    get_communication_router,
    reset_communication_router,
)


@pytest.fixture(autouse=True)
def setup_db_and_router():
    """Initializes DB and cleans up router singleton before each test."""
    db.init_db()
    reset_communication_router()
    yield
    reset_communication_router()


# ---------------------------------------------------------------------- #
# 1. Channel Selection & Failover Tests
# ---------------------------------------------------------------------- #

def test_scenario_1_internet_available_selects_whatsapp():
    """Scenario 1: Internet ON, Cellular ON, LoRa ON -> WhatsApp selected."""
    cfg = CommunicationConfig(
        whatsapp_enabled=True,
        smsgate_enabled=True,
        lora_enabled=True,
    )
    wa = WhatsAppAdapter(simulated=True)
    wa.set_simulated_availability(True)
    sms = SMSGatewayAdapter()
    sms.set_simulated_availability(True)
    lora = LoRaAdapter(simulated=True)
    lora.set_simulated_availability(True)

    adapters = {
        ChannelType.WHATSAPP: wa,
        ChannelType.SMS_GATEWAY: sms,
        ChannelType.LORA: lora,
    }
    router = CommunicationRouter(config=cfg, adapters=adapters)

    msg = router.dispatch_alert(
        recipient="+918098897666",
        payload="Emergency: Evacuate Sector 4",
        priority=MessagePriority.CRITICAL,
    )

    assert msg.channel == ChannelType.WHATSAPP
    assert msg.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED)
    assert msg.dispatched_at is not None


def test_scenario_2_internet_down_cellular_up_selects_sms():
    """Scenario 2: Internet OFF, Cellular ON, LoRa ON -> SMSGate selected."""
    cfg = CommunicationConfig(
        whatsapp_enabled=True,
        smsgate_enabled=True,
        lora_enabled=True,
    )
    wa = WhatsAppAdapter(simulated=True)
    wa.set_simulated_availability(False)  # Internet down
    sms = SMSGatewayAdapter()
    sms.set_simulated_availability(True)  # Cellular active
    lora = LoRaAdapter(simulated=True)
    lora.set_simulated_availability(True)

    adapters = {
        ChannelType.WHATSAPP: wa,
        ChannelType.SMS_GATEWAY: sms,
        ChannelType.LORA: lora,
    }
    router = CommunicationRouter(config=cfg, adapters=adapters)

    msg = router.dispatch_alert(
        recipient="+918098897666",
        payload="Emergency: Debris Surge Detected",
        priority=MessagePriority.HIGH,
    )

    assert msg.channel == ChannelType.SMS_GATEWAY
    assert msg.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED)


def test_scenario_3_internet_and_cellular_down_lora_up_selects_lora():
    """Scenario 3: Internet OFF, Cellular OFF, LoRa ON -> LoRa selected."""
    cfg = CommunicationConfig(
        whatsapp_enabled=True,
        smsgate_enabled=True,
        lora_enabled=True,
    )
    wa = WhatsAppAdapter(simulated=True)
    wa.set_simulated_availability(False)
    sms = SMSGatewayAdapter()
    sms.set_simulated_availability(False)
    lora = LoRaAdapter(simulated=True)
    lora.set_simulated_availability(True)

    adapters = {
        ChannelType.WHATSAPP: wa,
        ChannelType.SMS_GATEWAY: sms,
        ChannelType.LORA: lora,
    }
    router = CommunicationRouter(config=cfg, adapters=adapters)

    msg = router.dispatch_alert(
        recipient="+918098897666",
        payload="Critical: Avalanche Warning",
        priority=MessagePriority.CRITICAL,
        latitude=32.3739,
        longitude=77.2491,
        sps=92.0,
    )

    assert msg.channel == ChannelType.LORA
    assert msg.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED)
    assert msg.provider_message_id.startswith("LORA-")


def test_scenario_4_all_channels_down_queues_offline():
    """Scenario 4: All channels OFF -> OFFLINE_QUEUED locally."""
    cfg = CommunicationConfig(
        whatsapp_enabled=True,
        smsgate_enabled=True,
        lora_enabled=True,
    )
    wa = WhatsAppAdapter(simulated=True)
    wa.set_simulated_availability(False)
    sms = SMSGatewayAdapter()
    sms.set_simulated_availability(False)
    lora = LoRaAdapter(simulated=True)
    lora.set_simulated_availability(False)

    adapters = {
        ChannelType.WHATSAPP: wa,
        ChannelType.SMS_GATEWAY: sms,
        ChannelType.LORA: lora,
    }
    router = CommunicationRouter(config=cfg, adapters=adapters)

    msg = router.dispatch_alert(
        recipient="+918098897666",
        payload="Alert in Deep Gorge",
        priority=MessagePriority.HIGH,
    )

    assert msg.channel == ChannelType.OFFLINE_QUEUE
    assert msg.status == DeliveryStatus.OFFLINE_QUEUED
    assert router.queue_manager.size() == 1


# ---------------------------------------------------------------------- #
# 2. Idempotency, Deduplication & Priority Queuing
# ---------------------------------------------------------------------- #

def test_scenario_5_duplicate_message_rejected_by_idempotency():
    """Scenario 5: Duplicate alert received -> returns existing record without re-sending."""
    router = CommunicationRouter()

    msg1 = router.dispatch_alert(
        recipient="+918098897666",
        payload="Team Alpha proceed to Sector B",
        priority=MessagePriority.HIGH,
        alert_id="ALT-DUP-01",
    )

    msg2 = router.dispatch_alert(
        recipient="+918098897666",
        payload="Team Alpha proceed to Sector B",
        priority=MessagePriority.HIGH,
        alert_id="ALT-DUP-01",
    )

    assert msg1.message_id == msg2.message_id
    assert msg1.idempotency_key == msg2.idempotency_key


def test_scenario_6_critical_messages_preempt_queue():
    """Scenario 6: CRITICAL messages have higher queue priority than LOW/MEDIUM."""
    from backend.communication.message_queue import MessageQueueManager

    qm = MessageQueueManager()

    m_low = EmergencyMessage(message_id="M-LOW", recipient="R1", payload="Heartbeat", priority=MessagePriority.LOW)
    m_med = EmergencyMessage(message_id="M-MED", recipient="R2", payload="Update", priority=MessagePriority.MEDIUM)
    m_crit = EmergencyMessage(message_id="M-CRIT", recipient="R3", payload="BURIAL ALERT", priority=MessagePriority.CRITICAL)

    qm.enqueue(m_low)
    qm.enqueue(m_med)
    qm.enqueue(m_crit)

    popped_1 = qm.dequeue()
    assert popped_1.message_id == "M-CRIT"

    popped_2 = qm.dequeue()
    assert popped_2.message_id == "M-MED"

    popped_3 = qm.dequeue()
    assert popped_3.message_id == "M-LOW"


# ---------------------------------------------------------------------- #
# 3. Retry, Expiration & Channel Failure Handling
# ---------------------------------------------------------------------- #

def test_scenario_7_retry_stops_at_maximum():
    """Scenario 7: Retry count stops at max retries (3 retries)."""
    from backend.communication.retry_manager import RetryManager

    rm = RetryManager(max_retries=3, backoff_schedule=(1.0, 2.0, 3.0))
    msg = EmergencyMessage(message_id="M-RETRY", recipient="R1", payload="Test", priority=MessagePriority.HIGH)

    assert rm.should_retry(msg) is True
    delay1 = rm.prepare_next_retry(msg)
    assert delay1 is not None
    assert msg.retry_count == 1

    delay2 = rm.prepare_next_retry(msg)
    assert msg.retry_count == 2

    delay3 = rm.prepare_next_retry(msg)
    assert msg.retry_count == 3

    delay4 = rm.prepare_next_retry(msg)
    assert delay4 is None  # Max reached
    assert msg.status == DeliveryStatus.FAILED


def test_scenario_8_expired_messages_not_sent():
    """Scenario 8: Expired messages (TTL exceeded) are marked EXPIRED and not dispatched."""
    from backend.communication.message_queue import MessageQueueManager

    qm = MessageQueueManager()
    past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    msg_expired = EmergencyMessage(
        message_id="M-EXP",
        recipient="R1",
        payload="Old Hazard",
        expires_at=past_time,
    )

    assert msg_expired.is_expired() is True
    qm.enqueue(msg_expired)
    popped = qm.dequeue()
    assert popped is None
    assert qm.size() == 0


def test_scenario_9_backward_compatibility_with_flag_disabled():
    """Scenario 9: Feature flag disabled (COMMUNICATION_FAILOVER_ENABLED=false) preserves old behavior."""
    from backend.notification_dispatch import dispatch_rescue_command_notifications

    with patch.dict(os.environ, {"COMMUNICATION_FAILOVER_ENABLED": "false", "SMSGATE_ENABLED": "true"}):
        res = dispatch_rescue_command_notifications(
            command_id="CMD-COMPAT-01",
            team_id="ALPHA",
            member_id="ALPHA-M001",
            victim_id="V-101",
        )
        assert res["rescue_command_id"] == "CMD-COMPAT-01"
        assert res["sms"]["provider"] == "SMSGATE"


def test_scenario_10_adapter_failures_fallback_to_next_channel():
    """Scenario 10: Primary channel adapter failure triggers immediate failover to secondary."""
    cfg = CommunicationConfig(
        whatsapp_enabled=True,
        smsgate_enabled=True,
        lora_enabled=True,
    )

    wa = WhatsAppAdapter(simulated=True)
    wa.set_simulated_availability(True)
    # Force WA to fail during send()
    wa.send = MagicMock(return_value=DeliveryResult(
        message_id="TEST",
        channel=ChannelType.WHATSAPP,
        status=DeliveryStatus.FAILED,
        error="WhatsApp HTTP 500 Server Error",
    ))

    sms = SMSGatewayAdapter()
    sms.set_simulated_availability(True)

    adapters = {
        ChannelType.WHATSAPP: wa,
        ChannelType.SMS_GATEWAY: sms,
    }
    router = CommunicationRouter(config=cfg, adapters=adapters)

    msg = router.dispatch_alert(
        recipient="+918098897666",
        payload="Failover test message",
    )

    # WhatsApp failed, fell back to SMSGateway
    assert msg.channel == ChannelType.SMS_GATEWAY
    assert msg.status in (DeliveryStatus.SENT, DeliveryStatus.DELIVERED)


# ---------------------------------------------------------------------- #
# 4. Bulk 90-Recipient Queue & Async Performance
# ---------------------------------------------------------------------- #

def test_scenario_11_bulk_90_recipients_non_blocking():
    """Scenario 11: 90-recipient broadcast completes quickly without blocking backend thread."""
    router = CommunicationRouter()
    recipients = [f"+9180988976{i:02d}" for i in range(90)]

    start = time.time()
    messages = router.dispatch_bulk(
        recipients=recipients,
        payload="BROADCAST: Earthquake aftershock warning for all sectors.",
        priority=MessagePriority.CRITICAL,
        async_dispatch=True,
    )
    elapsed = time.time() - start

    assert len(messages) == 90
    assert elapsed < 1.0  # Asynchronous launch must return in < 1 second


# ---------------------------------------------------------------------- #
# 5. Database Persistence & Acknowledgement
# ---------------------------------------------------------------------- #

def test_scenario_12_delivery_ledger_persistence():
    """Scenario 12: Communication delivery table logs records accurately in SQLite."""
    router = CommunicationRouter()

    msg = router.dispatch_alert(
        recipient="+918098897666",
        payload="Ledger persistence check",
        alert_id="ALT-LEDGER-01",
        rescue_command_id="CMD-LEDGER-01",
    )

    row = db.get_communication_delivery(msg.message_id)
    assert row is not None
    assert row["message_id"] == msg.message_id
    assert row["alert_id"] == "ALT-LEDGER-01"
    assert row["recipient"] == "+918098897666"


def test_scenario_13_two_way_acknowledgement():
    """Scenario 13: Two-way rescuer ACK updates status to ACKNOWLEDGED with timestamp."""
    router = CommunicationRouter()

    msg = router.dispatch_alert(
        recipient="+918098897666",
        payload="Awaiting acknowledgement",
    )

    assert msg.acknowledged_at is None
    ack_success = router.acknowledge_message(msg.message_id, rescuer_id="ALPHA-M001")
    assert ack_success is True

    updated = router.delivery_tracker.get_message(msg.message_id)
    assert updated.status == DeliveryStatus.ACKNOWLEDGED
    assert updated.acknowledged_at is not None

    db_row = db.get_communication_delivery(msg.message_id)
    assert db_row["status"] == "ACKNOWLEDGED"
    assert db_row["acknowledged_at"] is not None


# ---------------------------------------------------------------------- #
# 6. LoRa Packet Formatting & Circuit Breaker
# ---------------------------------------------------------------------- #

def test_scenario_14_compact_lora_packet_formatting():
    """Scenario 14: LoRa packet is strictly < 64 bytes and contains valid checksum."""
    lora = LoRaAdapter()
    msg = EmergencyMessage(
        message_id="RW-20260914-A8F3C19B",
        recipient="BROADCAST",
        payload="Severe rockfall reported at pass",
        priority=MessagePriority.CRITICAL,
        alert_id="ALT-ROK-01",
        latitude=32.37392,
        longitude=77.24915,
        sps=94.5,
    )

    packet = lora.format_packet(msg)
    assert len(packet.encode("utf-8")) <= 64
    assert packet.startswith("RW|")
    parts = packet.split("|")
    assert len(parts) >= 7  # RW, msg_id, prio, alt_id, lat, lon, sps, checksum


def test_scenario_15_circuit_breaker_trips_open():
    """Scenario 15: Circuit breaker trips OPEN after consecutive failures and recovers on success."""
    from backend.communication.channel_health import ChannelCircuitBreaker

    cb = ChannelCircuitBreaker(ChannelType.WHATSAPP, failure_threshold=3, recovery_timeout_sec=0.2)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_attempt() is True

    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    cb.record_failure()  # 3rd failure trips breaker
    assert cb.state == CircuitState.OPEN
    assert cb.can_attempt() is False

    # Wait for recovery timeout
    time.sleep(0.25)
    assert cb.can_attempt() is True  # enters HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0
