"""
test_smsgate_inbound_polling.py
-------------------------------
Unit and integration tests for SMSGate Local Server /inbox polling:
1. Polling and processing valid ACCEPT <CMD_ID> SMS from /inbox.
2. Message-level persistent deduplication via processed_inbound_sms.
3. Strict sender authorization and validation.
4. Safe ignoring of non-acceptance messages (e.g. promo, carrier, or casual text).
5. Network error and timeout resiliency without crashing FastAPI.
6. Idempotent integration with existing accept_rescue_assignment() engine.
"""

import os
import uuid
import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from backend import db
from backend.api import app
from backend.notification_dispatch import (
    poll_smsgate_inbound_messages,
    poll_smsgate_inbound_messages_sync,
    parse_sms_acceptance_command,
)


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Initialize DB, seed builtins, and configure test SMSGate env."""
    db.init_db()
    db.seed_builtin_teams()
    db.seed_builtin_scenarios()
    monkeypatch.setenv("SMSGATE_ENABLED", "true")
    monkeypatch.setenv("SMSGATE_INBOUND_ENABLED", "true")
    monkeypatch.setenv("SMSGATE_LOCAL_URL", "http://192.168.43.93:8080")
    monkeypatch.setenv("SMSGATE_USERNAME", "sms_test")
    monkeypatch.setenv("SMSGATE_PASSWORD", "test_pass")
    monkeypatch.setenv("SMSGATE_SIM_NUMBER", "2")


def test_valid_inbound_sms_poll_accepts_command():
    """Verify that a valid ACCEPT <CMD_ID> from authorized phone transitions command to USER_ACCEPTED."""
    command_id = f"CMD-POLL-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )

    inbox_payload = [
        {
            "id": f"text:{uuid.uuid4().hex[:8]}",
            "contentPreview": f"ACCEPT {command_id}",
            "sender": "+918098897666",  # Authorized for ALPHA-M001
            "simNumber": 2,
            "type": "SMS",
            "createdAt": "2026-09-10T05:00:00.000Z",
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = inbox_payload

    with patch("httpx.get", return_value=mock_resp), patch("httpx.post", return_value=MagicMock(status_code=200, json=lambda: {"status": "success"})):
        results = poll_smsgate_inbound_messages_sync()

    assert len(results) == 1
    assert results[0]["command_id"] == command_id
    assert results[0]["result"]["success"] is True
    assert results[0]["result"]["status"] == "ACCEPTED"

    cmd = db.get_rescue_command(command_id)
    assert cmd is not None
    assert cmd["status"] == "USER_ACCEPTED"
    assert cmd["acceptance_source"] == "SMS"
    assert cmd["accepted_at"] is not None


def test_inbound_sms_message_deduplication():
    """Verify that repeated polling does not re-process already handled message IDs."""
    command_id = f"CMD-DEDUP-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )

    msg_id = f"text:dedup_{uuid.uuid4().hex[:6]}"
    inbox_payload = [
        {
            "id": msg_id,
            "contentPreview": f"ACCEPT {command_id}",
            "sender": "+918098897666",
            "simNumber": 2,
            "type": "SMS",
            "createdAt": "2026-09-10T05:00:00.000Z",
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = inbox_payload

    with patch("httpx.get", return_value=mock_resp), patch("httpx.post", return_value=MagicMock(status_code=200, json=lambda: {"status": "success"})):
        # First poll cycle
        res1 = poll_smsgate_inbound_messages_sync()
        assert len(res1) == 1

        # Second poll cycle (same inbox list returned by SMSGate)
        res2 = poll_smsgate_inbound_messages_sync()
        assert len(res2) == 0  # Deduplicated and skipped


def test_unauthorized_sender_rejected():
    """Verify inbound SMS from unauthorized sender does not accept the command."""
    command_id = f"CMD-UNAUTH-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )

    inbox_payload = [
        {
            "id": f"text:{uuid.uuid4().hex[:8]}",
            "contentPreview": f"ACCEPT {command_id}",
            "sender": "+919999999999",  # Unauthorized phone number
            "simNumber": 2,
            "type": "SMS",
            "createdAt": "2026-09-10T05:00:00.000Z",
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = inbox_payload

    with patch("httpx.get", return_value=mock_resp):
        results = poll_smsgate_inbound_messages_sync()

    assert len(results) == 1
    assert results[0]["result"]["success"] is False
    assert results[0]["result"]["status"] == "UNAUTHORIZED_SENDER"

    # Command in DB must still be ASSIGNED
    cmd = db.get_rescue_command(command_id)
    assert cmd is not None
    assert cmd["status"] == "ASSIGNED"


def test_malformed_and_promo_sms_ignored_safely():
    """Verify non-acceptance messages are safely recorded as IGNORED without triggering errors."""
    inbox_payload = [
        {
            "id": f"text:promo_{uuid.uuid4().hex[:6]}",
            "contentPreview": "Daily Free SMS Balance Left :99, Main-Bal:Rs0.00",
            "sender": "VT-ViCare",
            "simNumber": 2,
            "type": "SMS",
        },
        {
            "id": f"text:casual_{uuid.uuid4().hex[:6]}",
            "contentPreview": "HELLO RIDGEWATCH TEAM",
            "sender": "+918098897666",
            "simNumber": 2,
            "type": "SMS",
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = inbox_payload

    with patch("httpx.get", return_value=mock_resp):
        results = poll_smsgate_inbound_messages_sync()

    assert len(results) == 0  # No valid ACCEPT commands


def test_smsgate_network_unreachable_handled_gracefully():
    """Verify connection errors to SMSGate do not throw unhandled exceptions."""
    with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
        results = poll_smsgate_inbound_messages_sync()
        assert results == []


def test_manual_inbox_poll_endpoint():
    """Verify POST /api/sms/inbox/poll triggers an on-demand poll."""
    client = TestClient(app)
    command_id = f"CMD-API-POLL-{uuid.uuid4().hex[:6].upper()}"
    db.create_rescue_command(
        command_id=command_id,
        team_id="ALPHA",
        destination_latitude=13.0827,
        destination_longitude=80.2707,
        member_id="ALPHA-M001",
        victim_id="VIC-001",
    )

    inbox_payload = [
        {
            "id": f"text:{uuid.uuid4().hex[:8]}",
            "contentPreview": f"ACCEPT {command_id}",
            "sender": "+918098897666",
            "simNumber": 2,
            "type": "SMS",
            "createdAt": "2026-09-10T05:00:00.000Z",
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = inbox_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp), patch("httpx.post", return_value=MagicMock(status_code=200, json=lambda: {"status": "success"})):
        resp = client.post("/api/sms/inbox/poll")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["processed_count"] == 1
