"""
test_work_assignment_sms_and_companion.py
-----------------------------------------
Comprehensive test suite verifying:
1. Commander Job Assignment DB Persistence (job_assignments table).
2. Automatic SMS dispatch via SMSGate Local Server + physical SIM pipeline.
3. Dynamic E.164 phone resolution for ALPHA and BRAVO teams (no hardcoded numbers).
4. SMS failure isolation: SMS failure does NOT block job assignment or backend response.
5. Android Companion heartbeat delivery: active_job_assignment returned in bridge heartbeat.
6. Member status updates and job status transitions (ASSIGNED -> ACCEPTED -> COMPLETED).
7. Zero regression on existing Rescue Assignments (POST /commander/assign and active_command).
"""

import os
import uuid
import pytest
import httpx
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend import db
from backend.api import app
from backend.notification_dispatch import (
    dispatch_job_assignment_notifications,
    dispatch_smsgate_sms,
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
# 1. DB Persistence & API Endpoint Tests
# ====================================================================== #

def test_commander_assign_job_db_persistence():
    """Verify POST /commander/jobs/assign creates job assignment in DB with correct initial state."""
    client = TestClient(app)

    # 1. Create a commander job in database
    job_id = f"JOB-SURVEY-{uuid.uuid4().hex[:4].upper()}"
    db.create_commander_job(
        job_id=job_id,
        job_name="Sector B Perimeter Survey",
        scenario_id="himalaya_avalanche",
        scenario_name="Himalayan Avalanche",
        location="Sector B",
        priority="HIGH",
        description="Scan perimeter for structural instability and hazards.",
    )

    payload = {
        "job_id": job_id,
        "member_id": "ALPHA-M001",
        "notes": "Scan perimeter for structural instability and hazards.",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "MSG-TEST-001"}

    with patch("httpx.post", return_value=mock_resp):
        res = client.post("/commander/jobs/assign", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ASSIGNED"
        assert data["assigned"] is True
        assignment_id = data["assignment_id"]
        assert assignment_id.startswith("ASN-")

        # Verify DB record in job_assignments table
        job_db = db.get_commander_job(job_id)
        assert job_db is not None
        assert len(job_db["assignments"]) > 0
        assign_rec = job_db["assignments"][0]
        assert assign_rec["assignment_id"] == assignment_id
        assert assign_rec["member_id"] == "ALPHA-M001"
        assert assign_rec["status"] == "ASSIGNED"


# ====================================================================== #
# 2. SMS Dispatch via SMSGate & Message Formatting
# ====================================================================== #

def test_commander_assign_job_triggers_smsgate_sms():
    """Verify assigning a job triggers SMSGate dispatch with canonical message format."""
    client = TestClient(app)

    job_id = f"JOB-CLEAR-{uuid.uuid4().hex[:4].upper()}"
    db.create_commander_job(
        job_id=job_id,
        job_name="Clear Debris at Grid C3",
        scenario_id="himalaya_avalanche",
        scenario_name="Himalayan Avalanche",
        location="Grid C3",
        priority="CRITICAL",
        description="Clear pathway to allow medical team access.",
    )

    payload = {
        "job_id": job_id,
        "member_id": "ALPHA-M001",
        "notes": "Clear pathway to allow medical team access.",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "MSG-TEST-002"}

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        res = client.post("/commander/jobs/assign", json=payload)
        assert res.status_code == 200
        assignment_id = res.json()["assignment_id"]

        # Verify HTTP call was made to SMSGate
        assert mock_post.called
        post_kwargs = mock_post.call_args[1]
        sent_payload = post_kwargs["json"]
        assert sent_payload["phoneNumbers"] == ["+918098897666"]
        msg_text = sent_payload["textMessage"]["text"]

        # Verify canonical SMS text content
        assert "[RIDGEWATCH WORK ASSIGNMENT]" in msg_text
        assert "Clear Debris at Grid C3" in msg_text
        assert "CRITICAL" in msg_text
        assert "ALPHA-M001" in msg_text


def test_dispatch_job_assignment_notifications_dynamic_phone_resolution():
    """Verify dispatch_job_assignment_notifications resolves dynamic phone numbers without hardcoding."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "MSG-DYN-001"}

    # Test for ALPHA member
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        res_alpha = dispatch_job_assignment_notifications(
            assignment_id="ASN-DYN-001",
            job_id="JOB-01",
            job_name="Sector Survey",
            team_id="ALPHA",
            member_id="ALPHA-M001",
            scenario_id="himalaya_avalanche",
            location="North Ridge",
            priority="MEDIUM",
        )
        assert res_alpha["sms_status"] == "SENT"
        assert res_alpha["recipient_mobile"] == "+918098897666"
        sent_alpha = mock_post.call_args[1]["json"]
        assert sent_alpha["phoneNumbers"] == ["+918098897666"]

    # Test for BRAVO member
    with patch("httpx.post", return_value=mock_resp) as mock_post:
        res_bravo = dispatch_job_assignment_notifications(
            assignment_id="ASN-DYN-002",
            job_id="JOB-02",
            job_name="Supply Transport",
            team_id="BRAVO",
            member_id="BRAVO-M001",
            scenario_id="himalaya_avalanche",
            location="South Ridge",
            priority="LOW",
        )
        assert res_bravo["sms_status"] == "SENT"
        assert res_bravo["recipient_mobile"] == "+919876502001"
        sent_bravo = mock_post.call_args[1]["json"]
        assert sent_bravo["phoneNumbers"] == ["+919876502001"]


# ====================================================================== #
# 3. SMS Failure Isolation Tests
# ====================================================================== #

def test_work_assignment_sms_failure_isolation():
    """Verify that if SMS dispatch fails, the job assignment STILL succeeds and returns 200 OK."""
    client = TestClient(app)

    job_id = f"JOB-ESCORT-{uuid.uuid4().hex[:4].upper()}"
    db.create_commander_job(
        job_id=job_id,
        job_name="Escort Medical Unit",
        scenario_id="himalaya_avalanche",
        scenario_name="Himalayan Avalanche",
        location="Sector D",
        priority="HIGH",
        description="Escort unit safely through designated route.",
    )

    payload = {
        "job_id": job_id,
        "member_id": "ALPHA-M001",
        "notes": "Escort unit safely through designated route.",
    }

    with patch("httpx.post", side_effect=httpx.ConnectError("SMSGate Local Server connection refused on port 8080")):
        res = client.post("/commander/jobs/assign", json=payload)
        # Assignment MUST still succeed
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ASSIGNED"
        assignment_id = data["assignment_id"]

        # Verify DB record is still created intact
        job_db = db.get_commander_job(job_id)
        assert job_db is not None
        assert len(job_db["assignments"]) > 0


# ====================================================================== #
# 4. Android Companion Bridge Sync Tests
# ====================================================================== #

def test_android_companion_heartbeat_receives_active_job_assignment():
    """Verify Android Companion receives active_job_assignment via /api/wearable/bridge/heartbeat."""
    client = TestClient(app)
    session_id = f"BRG-AND-{uuid.uuid4().hex[:6].upper()}"

    job_id = f"JOB-SEARCH-{uuid.uuid4().hex[:4].upper()}"
    db.create_commander_job(
        job_id=job_id,
        job_name="Search West Ridge Sector",
        scenario_id="himalaya_avalanche",
        scenario_name="Himalayan Avalanche",
        location="West Ridge",
        priority="HIGH",
        description="Conduct search along western ridge line.",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "MSG-TEST-003"}

    # 1. Assign job to ALPHA-M001
    with patch("httpx.post", return_value=mock_resp):
        assign_res = client.post("/commander/jobs/assign", json={
            "job_id": job_id,
            "member_id": "ALPHA-M001",
            "notes": "Conduct search along western ridge line."
        })
        assert assign_res.status_code == 200
        assigned_id = assign_res.json()["assignment_id"]

    # 2. Rescuer companion sends heartbeat for ALPHA-M001
    sync_res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": session_id,
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "device_name": "RidgeWatch Native Android Companion",
        "watch_device_id": "DEV-WEARABLE-CALLPLUS",
        "watch_mac": "CB:4E:FD:EE:7F:1B",
        "watch_model": "Wave Call Plus",
        "watch_connected": False,
        "bluetooth_state": "ENABLED",
        "gps_available": True,
        "status": "ONLINE"
    })
    assert sync_res.status_code == 200
    sync_data = sync_res.json()

    # 3. Verify active_job_assignment is present in sync response
    assert "active_job_assignment" in sync_data
    job = sync_data["active_job_assignment"]
    assert job is not None
    assert job["assignment_id"] == assigned_id
    assert job["title"] == "Search West Ridge Sector"
    assert job["job_type"] == "GENERAL"
    assert job["priority"] == "HIGH"
    assert job["sector"] == "West Ridge"
    assert job["status"] == "ASSIGNED"


def test_android_companion_heartbeat_member_isolation():
    """Verify job assignments for ALPHA-M001 are NOT returned in heartbeat for BRAVO-M001."""
    client = TestClient(app)

    job_id = f"JOB-EXCL-{uuid.uuid4().hex[:4].upper()}"
    db.create_commander_job(
        job_id=job_id,
        job_name="Alpha Exclusive Task",
        scenario_id="himalaya_avalanche",
        scenario_name="Himalayan Avalanche",
        location="Sector A",
        priority="MEDIUM",
        description="Alpha member exclusive mission.",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "MSG-TEST-004"}

    # 1. Assign job to ALPHA-M001
    with patch("httpx.post", return_value=mock_resp):
        client.post("/commander/jobs/assign", json={
            "job_id": job_id,
            "member_id": "ALPHA-M001",
            "notes": "Alpha member exclusive mission."
        })

    # 2. Rescuer companion sends heartbeat for BRAVO-M001 (who has no active jobs)
    sync_res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": f"BRG-BRAVO-{uuid.uuid4().hex[:6].upper()}",
        "team_id": "BRAVO",
        "member_id": "BRAVO-M001",
        "device_name": "RidgeWatch Native Android Companion",
        "status": "ONLINE"
    })
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data.get("active_job_assignment") is None


def test_job_assignment_status_update_and_heartbeat_lifecycle():
    """Verify job assignment status transition from ASSIGNED to ACCEPTED to COMPLETED."""
    # 1. Create commander job and assignment
    job = db.create_commander_job(
        job_id="JOB-TREE-01",
        job_name="Remove Fallen Tree",
        scenario_id="himalaya_avalanche",
        scenario_name="Himalayan Avalanche",
        location="North Access Road",
        priority="HIGH",
        description="Clear road obstruction."
    )
    assignment = db.create_job_assignment(
        assignment_id="ASN-TREE-01",
        job_id="JOB-TREE-01",
        member_id="ALPHA-M001",
        personnel_id="ALPHA-M001",
        team_id="ALPHA",
        scenario_id="himalaya_avalanche",
        assigned_by="Commander",
        status="ASSIGNED",
        result_notes="Clear road obstruction."
    )
    assignment_id = assignment["assignment_id"]

    # Verify active in DB
    active_job = db.get_active_job_assignment_for_member("ALPHA-M001")
    assert active_job is not None
    assert active_job["assignment_id"] == assignment_id
    assert active_job["status"] == "ASSIGNED"

    # 2. Update status to ACCEPTED
    db.update_job_assignment_status(assignment_id, "ACCEPTED", progress_pct=25, result_notes="En route with chainsaw")
    active_job_accepted = db.get_active_job_assignment_for_member("ALPHA-M001")
    assert active_job_accepted is not None
    assert active_job_accepted["status"] == "ACCEPTED"
    assert active_job_accepted["progress_pct"] == 25

    # 3. Update status to COMPLETED -> no longer active
    db.update_job_assignment_status(assignment_id, "COMPLETED", progress_pct=100, result_notes="Road cleared")
    active_job_done = db.get_active_job_assignment_for_member("ALPHA-M001")
    assert active_job_done is None


# ====================================================================== #
# 5. Non-Regression Tests (Rescue Assignment Compatibility)
# ====================================================================== #

def test_rescue_assignment_unbroken_regression():
    """Verify POST /commander/assign and active_command continue to work completely unaffected."""
    client = TestClient(app)

    # 1. Start scenario to populate victims and teams
    client.post("/scenario/reset")
    start_res = client.post("/scenario/start", json={"seed": 7, "enable_degradation": False})
    assert start_res.status_code == 200

    overview = client.get("/commander/overview").json()
    victim_id = overview["victims"][0]["victim_id"]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "MSG-RESCUE-001"}

    # 2. Assign rescue command
    with patch("httpx.post", return_value=mock_resp):
        assign_res = client.post("/commander/assign", json={
            "victim_id": victim_id,
            "team_id": "ALPHA",
            "member_id": "ALPHA-M001",
            "notes": "Emergency rescue assigned"
        })
        assert assign_res.status_code == 200
        cmd_data = assign_res.json()
        assert cmd_data["status"].upper() == "EN_ROUTE"

    # 3. Heartbeat receives rescue active_command
    sync_res = client.post("/api/wearable/bridge/heartbeat", json={
        "session_id": f"BRG-REG-{uuid.uuid4().hex[:6].upper()}",
        "team_id": "ALPHA",
        "member_id": "ALPHA-M001",
        "device_name": "RidgeWatch Native Android Companion",
        "status": "ONLINE"
    })
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data.get("active_command") is not None


def test_work_assignment_duplicate_sms_prevention():
    """Verify that retrying/calling dispatch for an existing assignment does not dispatch duplicate SMS."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "success", "id": "MSG-DEDUP-001"}

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        # 1. First dispatch -> triggers SMS
        res1 = dispatch_job_assignment_notifications(
            assignment_id="ASN-DEDUP-01",
            job_id="JOB-DEDUP",
            job_name="Reinforce Berm",
            team_id="ALPHA",
            member_id="ALPHA-M001",
            priority="HIGH",
        )
        assert res1["sms_status"] == "SENT"
        assert mock_post.call_count == 1

        # 2. Retry dispatch with same assignment ID -> skips duplicate SMS
        res2 = dispatch_job_assignment_notifications(
            assignment_id="ASN-DEDUP-01",
            job_id="JOB-DEDUP",
            job_name="Reinforce Berm",
            team_id="ALPHA",
            member_id="ALPHA-M001",
            priority="HIGH",
        )
        assert res2.get("duplicate_skipped") is True
        assert res2["sms_status"] == "SENT"
        assert mock_post.call_count == 1  # Still 1, no second SMS sent!
