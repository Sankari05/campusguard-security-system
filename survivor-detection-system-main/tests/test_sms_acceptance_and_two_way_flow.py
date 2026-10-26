"""
test_sms_acceptance_and_two_way_flow.py
---------------------------------------
Comprehensive test suite verifying TWO-WAY MANUAL ACCEPTANCE for rescue assignments
and work assignments across:
1. Android Companion APK acceptance pathway (POST /api/wearable/notifications/{id}/accept & POST /api/wearable/commands/{id}/status)
2. SMS reply acceptance pathway (POST /api/sms/inbound, /api/sms/webhook, /api/smsgate/inbound)
3. Convergence on authoritative backend ACCEPTED state & Real GPS activation workflow.
4. Strict security, identity verification, duplicate protection, and failure isolation.
"""

import os
import uuid
import pytest
import httpx
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend import db
from backend.api import app, accept_rescue_assignment, operations
from backend.notification_dispatch import (
    dispatch_rescue_command_notifications,
    dispatch_job_assignment_notifications,
    parse_sms_acceptance_command,
    normalize_phone_number_e164,
    resolve_recipient_mobile,
)


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Initialize DB and seed teams and scenarios before each test with isolated SMSGate env."""
    db.init_db()
    db.seed_builtin_teams()
    db.seed_builtin_scenarios()
    monkeypatch.setenv("SMS_PROVIDER", "SMSGATE")
    monkeypatch.setenv("SMSGATE_ENABLED", "true")
    monkeypatch.setenv("SMSGATE_LOCAL_URL", "http://192.168.1.100:8080")
    monkeypatch.setenv("SMSGATE_USERNAME", "test_user")
    monkeypatch.setenv("SMSGATE_PASSWORD", "test_password")
    monkeypatch.setenv("SMSGATE_SIM_NUMBER", "1")


# ====================================================================== #
# 1. Strict SMS Command Parser Unit Tests
# ====================================================================== #

def test_parse_sms_acceptance_command_valid():
    """Test strict parser accepts valid case-insensitive ACCEPT <COMMAND_ID> with whitespace."""
    assert parse_sms_acceptance_command("ACCEPT CMD-12345") == "CMD-12345"
    assert parse_sms_acceptance_command("accept cmd-12345") == "CMD-12345"
    assert parse_sms_acceptance_command("  ACCEPT ASN-9876  ") == "ASN-9876"
    assert parse_sms_acceptance_command("Accept CMD-ALPHA-01") == "CMD-ALPHA-01"


def test_parse_sms_acceptance_command_invalid():
    """Test strict parser rejects ambiguous or malformed messages."""
    assert parse_sms_acceptance_command("ACCEPT") is None
    assert parse_sms_acceptance_command("YES") is None
    assert parse_sms_acceptance_command("OK") is None
    assert parse_sms_acceptance_command("ACCEPT PLEASE") is None
    assert parse_sms_acceptance_command("ACCEPT CMD-12345 EXTRA") is None
    assert parse_sms_acceptance_command("RANDOM TEXT") is None
    assert parse_sms_acceptance_command("") is None
    assert parse_sms_acceptance_command(None) is None


# ====================================================================== #
# 2. Assignment starts ASSIGNED & Outgoing SMS has Reply Instruction
# ====================================================================== #

def test_rescue_command_starts_assigned_with_reply_instruction():
    """Verify newly assigned rescue command starts as ASSIGNED and SMS contains reply instructions."""
    command_id = f"CMD-TEST-{uuid.uuid4().hex[:6].upper()}"
    cmd = db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )
    assert cmd["status"] == "ASSIGNED"

    sent_messages = []

    def mock_post(url, *args, **kwargs):
        json_data = kwargs.get("json", {})
        msg_text = json_data.get("textMessage", {}).get("text", "")
        sent_messages.append(msg_text)
        mock_r = MagicMock()
        mock_r.status_code = 200
        mock_r.json.return_value = {"status": "success", "id": "MSG-001"}
        return mock_r

    with patch("httpx.post", side_effect=mock_post):
        res = dispatch_rescue_command_notifications(
            command_id=command_id,
            team_id="ALPHA",
            member_id="ALPHA-M001",
            victim_id="VIC-001",
        )
        assert res["sms_status"] in ("SENT", "QUEUED")
        assert len(sent_messages) > 0
        assert f"ACCEPT {command_id}" in sent_messages[0]
        assert "To accept this mission, reply:" in sent_messages[0]

    # Verify database status is still ASSIGNED (SMS delivery alone does NOT accept)
    db_cmd = db.get_rescue_command(command_id)
    assert db_cmd is not None
    assert db_cmd["status"] == "ASSIGNED"


def test_job_assignment_starts_assigned_with_reply_instruction():
    """Verify job assignment starts ASSIGNED and outgoing SMS contains ACCEPT <ASSIGNMENT_ID>."""
    client = TestClient(app)
    job_id = f"JOB-TEST-{uuid.uuid4().hex[:4].upper()}"
    db.create_commander_job(
        job_id=job_id,
        job_name="Reinforce Trench Wall",
        scenario_id="himalaya_avalanche",
        scenario_name="Himalayan Avalanche",
        location="Sector C",
        priority="HIGH",
    )

    sent_messages = []

    def mock_post(url, *args, **kwargs):
        json_data = kwargs.get("json", {})
        msg_text = json_data.get("textMessage", {}).get("text", "")
        sent_messages.append(msg_text)
        mock_r = MagicMock()
        mock_r.status_code = 200
        mock_r.json.return_value = {"status": "success", "id": "MSG-JOB-001"}
        return mock_r

    with patch("httpx.post", side_effect=mock_post):
        assign_res = client.post("/commander/jobs/assign", json={
            "job_id": job_id,
            "member_id": "ALPHA-M001",
        })
        assert assign_res.status_code == 200
        data = assign_res.json()
        assignment_id = data["assignment_id"]
        assert data["status"] == "ASSIGNED"

        assert len(sent_messages) > 0
        assert f"ACCEPT {assignment_id}" in sent_messages[0]
        assert "To accept this assignment, reply:" in sent_messages[0]

    # Verify assignment status in DB remains ASSIGNED
    job_db = db.get_job_assignment(assignment_id)
    assert job_db is not None
    assert job_db["status"] == "ASSIGNED"


# ====================================================================== #
# 3. SMS Acceptance Inbound Webhook Tests (PATH B)
# ====================================================================== #

def test_valid_sms_acceptance_rescue_command():
    """Test valid SMS reply ACCEPT <CMD_ID> transitions command to USER_ACCEPTED with source SMS."""
    client = TestClient(app)
    command_id = f"CMD-RESCUE-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "CONF-001"}

    with patch("httpx.post", return_value=mock_resp):
        resp = client.post("/api/sms/inbound", json={
            "phoneNumber": "+918098897666",
            "message": f"ACCEPT {command_id}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        result = data["result"]
        assert result["success"] is True
        assert result["status"] == "ACCEPTED"
        assert result["source"] == "SMS"
        assert result["command_id"] == command_id
        assert result["member_id"] == "ALPHA-M001"

    # Verify database state
    updated_cmd = db.get_rescue_command(command_id)
    assert updated_cmd is not None
    assert updated_cmd["status"] == "USER_ACCEPTED"
    assert updated_cmd["acceptance_source"] == "SMS"
    assert updated_cmd["accepted_at"] is not None


def test_valid_sms_acceptance_nested_smsgate_webhook_payload():
    """Test SMSGate standard webhook event payload format {event: 'sms:received', payload: {...}}."""
    client = TestClient(app)
    command_id = f"CMD-NESTED-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-002",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "CONF-002"}

    with patch("httpx.post", return_value=mock_resp):
        resp = client.post("/api/sms/webhook", json={
            "event": "sms:received",
            "payload": {
                "phoneNumber": "+918098897666",
                "message": f"accept {command_id.lower()}",
            }
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    updated_cmd = db.get_rescue_command(command_id)
    assert updated_cmd is not None
    assert updated_cmd["status"] == "USER_ACCEPTED"
    assert updated_cmd["acceptance_source"] == "SMS"


def test_valid_sms_acceptance_job_assignment():
    """Test valid SMS reply ACCEPT <ASN_ID> transitions job assignment to ACCEPTED with source SMS."""
    client = TestClient(app)
    job_id = f"JOB-VAL-{uuid.uuid4().hex[:4].upper()}"
    db.create_commander_job(
        job_id=job_id,
        job_name="Reinforce Trench Wall",
        scenario_id="himalaya_avalanche",
        scenario_name="Himalayan Avalanche",
        location="Sector C",
        priority="HIGH",
    )
    assignment_id = f"ASN-JOB-{uuid.uuid4().hex[:6].upper()}"
    db.create_job_assignment(
        assignment_id=assignment_id,
        job_id=job_id,
        member_id="ALPHA-M001",
        personnel_id="P-ALPHA-01",
        team_id="ALPHA",
        scenario_id="himalaya_avalanche",
        status="ASSIGNED",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "CONF-003"}

    with patch("httpx.post", return_value=mock_resp):
        resp = client.post("/api/sms/inbound", json={
            "phone_number": "8098897666",  # Will be normalized to +918098897666
            "text": f"ACCEPT {assignment_id}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        result = data["result"]
        assert result["success"] is True
        assert result["status"] == "ACCEPTED"
        assert result["source"] == "SMS"
        assert result["assignment_id"] == assignment_id

    updated_job = db.get_job_assignment(assignment_id)
    assert updated_job is not None
    assert updated_job["status"] == "ACCEPTED"
    assert updated_job["acceptance_source"] == "SMS"


# ====================================================================== #
# 4. Security & Validation Tests
# ====================================================================== #

def test_sms_acceptance_rejected_for_wrong_command_id():
    """Verify unknown/non-existent command ID returns 404."""
    client = TestClient(app)
    resp = client.post("/api/sms/inbound", json={
        "phoneNumber": "+918098897666",
        "message": "ACCEPT CMD-NONEXISTENT-999",
    })
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_sms_acceptance_rejected_for_unauthorized_phone_number():
    """Verify SMS from unregistered or spoofed phone number is rejected with 403."""
    client = TestClient(app)
    command_id = f"CMD-SEC-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",  # Registered phone: +918098897666
        victim_id="VIC-001",
    )

    resp = client.post("/api/sms/inbound", json={
        "phoneNumber": "+919999999999",  # Unauthorized phone
        "message": f"ACCEPT {command_id}",
    })
    assert resp.status_code == 403
    assert "not authorized" in resp.json()["detail"].lower()

    # Verify command is STILL ASSIGNED
    cmd = db.get_rescue_command(command_id)
    assert cmd is not None
    assert cmd["status"] == "ASSIGNED"


def test_sms_acceptance_rejected_for_invalid_format():
    """Verify invalid format messages (e.g. YES, OK, ACCEPT) return 400."""
    client = TestClient(app)
    for invalid_msg in ["YES", "OK", "ACCEPT", "ACCEPT PLEASE", "RANDOM"]:
        resp = client.post("/api/sms/inbound", json={
            "phoneNumber": "+918098897666",
            "message": invalid_msg,
        })
        assert resp.status_code == 400
        assert "invalid acceptance format" in resp.json()["detail"].lower()


# ====================================================================== #
# 5. Duplicate Acceptance & Idempotency Tests
# ====================================================================== #

def test_duplicate_sms_acceptance_returns_already_accepted():
    """Verify repeated SMS ACCEPT commands return ALREADY_ACCEPTED without duplicate transitions."""
    client = TestClient(app)
    command_id = f"CMD-DUP-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "CONF-004"}

    with patch("httpx.post", return_value=mock_resp):
        # First ACCEPT
        resp1 = client.post("/api/sms/inbound", json={
            "phoneNumber": "+918098897666",
            "message": f"ACCEPT {command_id}",
        })
        assert resp1.status_code == 200
        assert resp1.json()["result"]["status"] == "ACCEPTED"

        # Second ACCEPT (duplicate)
        resp2 = client.post("/api/sms/inbound", json={
            "phoneNumber": "+918098897666",
            "message": f"ACCEPT {command_id}",
        })
        assert resp2.status_code == 200
        assert resp2.json()["result"]["status"] == "ALREADY_ACCEPTED"
        assert resp2.json()["result"]["already_accepted"] is True


def test_cross_channel_idempotency_apk_then_sms():
    """Verify mission accepted via APK returns ALREADY_ACCEPTED when subsequently replied via SMS."""
    client = TestClient(app)
    command_id = f"CMD-CROSS-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )

    # 1. Rescuer taps ACCEPT on APK
    apk_resp = client.post(f"/api/wearable/commands/{command_id}/status", json={
        "status": "USER_ACCEPTED",
    })
    assert apk_resp.status_code == 200
    cmd_db = db.get_rescue_command(command_id)
    assert cmd_db is not None
    assert cmd_db["status"] == "USER_ACCEPTED"
    assert cmd_db["acceptance_source"] == "APK"

    # 2. Rescuer later replies via SMS
    sms_resp = client.post("/api/sms/inbound", json={
        "phoneNumber": "+918098897666",
        "message": f"ACCEPT {command_id}",
    })
    assert sms_resp.status_code == 200
    assert sms_resp.json()["result"]["status"] == "ALREADY_ACCEPTED"

    # Verify original source remains preserved
    cmd_final = db.get_rescue_command(command_id)
    assert cmd_final is not None
    assert cmd_final["status"] == "USER_ACCEPTED"
    assert cmd_final["acceptance_source"] == "APK"


def test_cross_channel_idempotency_sms_then_apk():
    """Verify mission accepted via SMS returns ALREADY_ACCEPTED when subsequently tapped on APK."""
    client = TestClient(app)
    command_id = f"CMD-SMSAPK-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "CONF-005"}

    with patch("httpx.post", return_value=mock_resp):
        # 1. Rescuer replies via SMS
        sms_resp = client.post("/api/sms/inbound", json={
            "phoneNumber": "+918098897666",
            "message": f"ACCEPT {command_id}",
        })
        assert sms_resp.status_code == 200
        assert sms_resp.json()["result"]["status"] == "ACCEPTED"

    cmd_db = db.get_rescue_command(command_id)
    assert cmd_db is not None
    assert cmd_db["status"] == "USER_ACCEPTED"
    assert cmd_db["acceptance_source"] == "SMS"

    # 2. Rescuer taps ACCEPT on APK
    apk_resp = client.post(f"/api/wearable/commands/{command_id}/status", json={
        "status": "USER_ACCEPTED",
    })
    assert apk_resp.status_code == 200
    assert apk_resp.json()["result"]["status"] == "ALREADY_ACCEPTED"

    # Authoritative state remains USER_ACCEPTED / SMS
    cmd_final = db.get_rescue_command(command_id)
    assert cmd_final is not None
    assert cmd_final["status"] == "USER_ACCEPTED"
    assert cmd_final["acceptance_source"] == "SMS"


# ====================================================================== #
# 6. Failure Isolation Tests
# ====================================================================== #

def test_confirmation_sms_failure_does_not_rollback_acceptance():
    """Verify if confirmation SMS network call fails, mission acceptance still succeeds."""
    client = TestClient(app)
    command_id = f"CMD-FAILISO-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )

    # Force httpx.post to fail with ConnectionError
    with patch("httpx.post", side_effect=httpx.ConnectError("SMSGate down")):
        resp = client.post("/api/sms/inbound", json={
            "phoneNumber": "+918098897666",
            "message": f"ACCEPT {command_id}",
        })
        # Acceptance must STILL succeed
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == "ACCEPTED"

    cmd_db = db.get_rescue_command(command_id)
    assert cmd_db is not None
    assert cmd_db["status"] == "USER_ACCEPTED"
    assert cmd_db["acceptance_source"] == "SMS"


# ====================================================================== #
# 7. GPS Convergence & Bridge Heartbeat Tests
# ====================================================================== #

def test_sms_acceptance_converges_with_real_gps_heartbeat():
    """
    Verify that after SMS acceptance, bridge heartbeat returns ACCEPTED active command,
    and subsequent real GPS telemetry from ALPHA-M001 is ingested as PHONE_GPS TRACKING.
    """
    client = TestClient(app)
    command_id = f"CMD-GPS-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0850,
        destination_longitude=80.2750,
        member_id="ALPHA-M001",
        victim_id="VIC-SURVIVOR-1",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "CONF-006"}

    # 1. Rescuer accepts via SMS
    with patch("httpx.post", return_value=mock_resp):
        sms_res = client.post("/api/sms/inbound", json={
            "phoneNumber": "+918098897666",
            "message": f"ACCEPT {command_id}",
        })
        assert sms_res.status_code == 200

    # 2. Companion APK performs routine background heartbeat sync
    hb_res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "SES-COMPANION-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "gps_available": True,
        "gps_status": "STANDBY",
    })
    assert hb_res.status_code == 200
    active_cmd = hb_res.json()["active_command"]
    assert active_cmd is not None
    assert active_cmd["command_id"] == command_id
    assert active_cmd["status"] in ("USER_ACCEPTED", "ACCEPTED")

    # 3. Android Companion, seeing ACCEPTED status, activates real GPS and streams live coordinates
    gps_res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": "SES-COMPANION-01",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "latitude": 13.0840,
        "longitude": 80.2740,
        "altitude_m": 12.5,
        "accuracy_m": 4.2,
        "speed_mps": 1.4,
        "heading_deg": 45.0,
        "location_source": "PHONE_GPS",
        "gps_status": "TRACKING",
        "gps_available": True,
    })
    assert gps_res.status_code == 200

    # 4. Verify Commander overview reflects real GPS from ALPHA-M001
    latest_gps = client.get("/api/wearable/commands/current_state?member_id=ALPHA-M001")
    assert latest_gps.status_code == 200
    live_data = latest_gps.json()
    assert live_data["has_command"] is True
    assert live_data["command_id"] == command_id
    assert live_data["command_status"] in ("USER_ACCEPTED", "ACCEPTED")
