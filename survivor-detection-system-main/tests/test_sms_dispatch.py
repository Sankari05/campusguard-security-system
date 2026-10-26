"""
test_sms_dispatch.py
--------------------
Unit and regression tests for RidgeWatch SMS Dispatch:
Exclusive SMS Provider: SMSGate Local Server via physical SIM (SMS_PROVIDER=SMSGATE).

Verifies:
1. SMSGate success with correct endpoint, Basic Auth, and JSON payload.
2. SMSGate failure and safe error reporting.
3. SMSGate HTTP 401/403 authentication failure handling.
4. SMSGate connection and timeout failures without password leak.
5. Dynamic recipient resolution without hardcoding (ALPHA vs BRAVO).
6. Configurable SIM slot parameter.
7. Correct SMS status and error persistence in DB.
8. Commander assignment integrity (exactly one rescue command).
9. Watch notification and watch ACK non-forgery safety.
10. Explicit rejection of unsupported SMS providers (Exotel, GSM_SIMULATED).
11. Automated tests NEVER send real SMS messages.
"""

import os
import httpx
import pytest
from unittest.mock import patch, MagicMock
from backend import db
from backend.notification_dispatch import (
    dispatch_sms_channel,
    dispatch_smsgate_sms,
    check_smsgate_health,
    dispatch_rescue_command_notifications,
    normalize_phone_number_e164,
    normalize_smsgate_phone,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    db.init_db()
    db.seed_builtin_teams()


# ---------------------------------------------------------------------- #
# 1. Provider Validation & Dynamic Resolution Tests
# ---------------------------------------------------------------------- #

def test_sms_unsupported_provider_fails():
    """Verify that unsupported providers or invalid ones fail explicitly."""
    for unsupported in ["EXOTEL", "GSM_SIMULATED", "INVALID_PROVIDER", "UNKNOWN"]:
        with patch.dict(os.environ, {"SMS_PROVIDER": unsupported}):
            res = dispatch_sms_channel("+918098897666", "Test Alert", "CMD-UNSUP-01")
            assert res["status"] == "FAILED"
            assert f"Unsupported SMS provider: {unsupported}" in res["error"]
            assert "Only SMSGATE is supported" in res["error"]


def test_sms_dynamic_recipient_resolution_contact_resolver():
    """Verify dynamic recipient mobile resolution for ALPHA and BRAVO members without hardcoding."""
    contact_alpha = db.resolve_member_contact_info("ALPHA-M001", team_id="ALPHA")
    assert contact_alpha["phone_normalized"] == "+918098897666"
    assert contact_alpha["phone_masked"] == "+91 80988****66"

    contact_bravo = db.resolve_member_contact_info("BRAVO-M001", team_id="BRAVO")
    assert contact_bravo["phone_normalized"] == "+919876502001"
    assert contact_bravo["phone_masked"] == "+91 98765****01"


# ---------------------------------------------------------------------- #
# 2. Watch Safety & Single Rescue Command
# ---------------------------------------------------------------------- #


def test_sms_cannot_modify_watch_ack_status():
    """Verify safety critical rule: SMS dispatch NEVER sets watch_ack_status to ACCEPTED or WATCH_ACKNOWLEDGED."""
    res = dispatch_rescue_command_notifications(
        command_id="CMD-ACK-SAFETY-01",
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-VICTIM-99",
        destination_label="North Ridge",
    )
    notif = db.get_notification(res["notification_id"])
    assert notif is not None
    assert notif["watch_ack_status"] != "ACCEPTED"
    assert notif["watch_ack_status"] != "WATCH_ACKNOWLEDGED"


def test_commander_single_rescue_command_integrity():
    """Verify that dispatching creates exactly one rescue command and notification in the database."""
    cmd_id = "CMD-SINGLE-INTEGRITY-01"
    res = dispatch_rescue_command_notifications(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-VICTIM-01",
        destination_label="Sector Alpha",
    )
    assert res["rescue_command_id"] == cmd_id

    # Verify single notification record created with matching ID
    notif = db.get_notification(res["notification_id"])
    assert notif is not None
    assert notif["rescue_command_id"] == cmd_id


# ---------------------------------------------------------------------- #
# 3. Watch Independence & Frontend UI Verification
# ---------------------------------------------------------------------- #

def test_watch_ack_status_independent_during_sms_failure():
    """Verify that watch ACK status remains completely independent when SMS dispatch fails."""
    cmd_id = "CMD-WATCH-ACK-INDEP-01"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-SURVIVOR-04",
        destination_label="Sector 5",
        watch_delivery_status="DELIVERED_TO_BRIDGE",
    )

    mock_sg_resp = MagicMock()
    mock_sg_resp.status_code = 500
    mock_sg_resp.json.return_value = {"message": "Internal Server Error"}

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "test_user",
        "SMSGATE_PASSWORD": "test_password",
    }):
        with patch("httpx.post", return_value=mock_sg_resp):
            dispatch_res = dispatch_rescue_command_notifications(
                command_id=cmd_id,
                team_id="ALPHA",
                member_id="ALPHA-M001",
                victim_id="V-SURVIVOR-04",
                destination_label="Sector 5",
            )
            assert dispatch_res["sms_status"] == "FAILED"

            # Check rescue_command row
            cmd = db.get_rescue_command(cmd_id)
            assert cmd["sms_status"] == "FAILED"
            # Watch ACK must NOT be accepted or acknowledged
            assert cmd.get("acknowledged_at") is None

            # Check notification
            notifs = db.list_notifications(team_id="ALPHA")
            target_notif = next((n for n in notifs if n.get("rescue_command_id") == cmd_id), None)
            assert target_notif is not None
            assert target_notif["watch_ack_status"] == "PENDING"
            assert target_notif["watch_ack_status"] != "ACCEPTED"


def test_frontend_notification_ui_never_displays_gsm_gateway_delivered():
    """Verify that 'GSM simulated gateway delivered' is completely removed and the UI uses dynamic status/error display."""
    js_path = "frontend/js/notification.js"
    html_path = "frontend/notification.html"

    assert os.path.exists(js_path), f"File {js_path} does not exist"
    with open(js_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    # Rule: Never display "GSM simulated gateway delivered"
    assert "GSM simulated gateway delivered" not in js_content, (
        "Found hardcoded 'GSM simulated gateway delivered' in frontend/js/notification.js"
    )

    # Verify dynamic error display and success message
    assert "Error: ${item.sms_error}" in js_content
    assert "SMS delivery failed" in js_content
    assert "SMSGate Android gateway delivered" in js_content

    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        assert "GSM simulated gateway delivered" not in html_content


# ---------------------------------------------------------------------- #
# 4. SMSGate Local Server Tests (Android Physical SIM Gateway)
# ---------------------------------------------------------------------- #

def test_smsgate_success_mocked():
    """Verify that SMS_PROVIDER=SMSGATE routes to SMSGate local server with correct endpoint, Basic Auth, and JSON payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "MSG_SMSGATE_SUCCESS_001",
        "state": "Pending",
    }

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "test_user",
        "SMSGATE_PASSWORD": "test_password",
        "SMSGATE_SIM_NUMBER": "1",
    }):
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            res = dispatch_sms_channel(
                phone_normalized="+918098897666",
                message_text="🚨 Emergency Dispatch: Alpha 1",
                rescue_command_id="CMD-SG-01",
            )
            assert res["status"] == "SENT"
            assert res["message_id"] == "MSG_SMSGATE_SUCCESS_001"
            assert res["error"] is None
            assert res.get("provider") == "SMSGATE"

            # Verify SMSGate API request parameters
            mock_post.assert_called_once()
            call_args, call_kwargs = mock_post.call_args
            assert call_args[0] == "http://192.168.1.100:8080/message"
            assert call_kwargs["auth"] == ("test_user", "test_password")

            json_payload = call_kwargs["json"]
            assert json_payload["textMessage"]["text"] == "🚨 Emergency Dispatch: Alpha 1"
            assert json_payload["phoneNumbers"] == ["+918098897666"]
            assert json_payload["simNumber"] == 1


def test_smsgate_configurable_sim_number():
    """Verify that SMSGATE_SIM_NUMBER is configurable and passed in the JSON payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "MSG_SIM_2"}

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "test_user",
        "SMSGATE_PASSWORD": "test_password",
        "SMSGATE_SIM_NUMBER": "2",
    }):
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            res = dispatch_sms_channel(
                phone_normalized="+918098897666",
                message_text="Testing SIM slot 2",
                rescue_command_id="CMD-SG-SIM2",
            )
            assert res["status"] == "SENT"
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["json"]["simNumber"] == 2


def test_smsgate_dynamic_recipient_routing_alpha_vs_bravo():
    """Verify that dynamic contact resolution routes to respective phone numbers without hardcoding."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "MSG_DYN_001"}

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "test_user",
        "SMSGATE_PASSWORD": "test_password",
    }):
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            # 1. Assign to Alpha Member 1
            cmd_alpha = "CMD-SG-ALPHA-01"
            db.create_rescue_command(
                command_id=cmd_alpha,
                team_id="ALPHA",
                member_id="ALPHA-M001",
                victim_id="V-ALPHA",
            )
            dispatch_rescue_command_notifications(
                command_id=cmd_alpha,
                team_id="ALPHA",
                member_id="ALPHA-M001",
                victim_id="V-ALPHA",
            )
            contact_alpha = db.resolve_member_contact_info("ALPHA-M001", team_id="ALPHA")
            alpha_payload = mock_post.call_args[1]["json"]
            assert alpha_payload["phoneNumbers"] == [contact_alpha["phone_normalized"]]

            # 2. Assign to Bravo Member 1
            mock_post.reset_mock()
            cmd_bravo = "CMD-SG-BRAVO-01"
            db.create_rescue_command(
                command_id=cmd_bravo,
                team_id="BRAVO",
                member_id="BRAVO-M001",
                victim_id="V-BRAVO",
            )
            dispatch_rescue_command_notifications(
                command_id=cmd_bravo,
                team_id="BRAVO",
                member_id="BRAVO-M001",
                victim_id="V-BRAVO",
            )
            contact_bravo = db.resolve_member_contact_info("BRAVO-M001", team_id="BRAVO")
            bravo_payload = mock_post.call_args[1]["json"]
            assert bravo_payload["phoneNumbers"] == [contact_bravo["phone_normalized"]]
            assert bravo_payload["phoneNumbers"] != [contact_alpha["phone_normalized"]]


def test_smsgate_disabled():
    """Verify that when SMSGATE_ENABLED=false, dispatch returns FAILED with a clear error."""
    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "false",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "user",
        "SMSGATE_PASSWORD": "pwd",
    }):
        res = dispatch_sms_channel(
            phone_normalized="+918098897666",
            message_text="Emergency",
            rescue_command_id="CMD-SG-DIS",
        )
        assert res["status"] == "FAILED"
        assert "disabled" in res["error"].lower()


def test_smsgate_missing_configuration():
    """Verify that missing SMSGATE_LOCAL_URL or credentials returns FAILED with clear error."""
    # Missing URL
    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "",
        "SMSGATE_USERNAME": "user",
        "SMSGATE_PASSWORD": "pwd",
    }):
        res = dispatch_sms_channel("+918098897666", "Test", "CMD-SG-NO-URL")
        assert res["status"] == "FAILED"
        assert "SMSGATE_LOCAL_URL" in res["error"]

    # Missing credentials
    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "",
        "SMSGATE_PASSWORD": "",
    }):
        res = dispatch_sms_channel("+918098897666", "Test", "CMD-SG-NO-CREDS")
        assert res["status"] == "FAILED"
        assert "credentials" in res["error"].lower()


def test_smsgate_connection_refused():
    """Verify that connection refused produces clear safe error without secrets."""
    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "super_secret_password_xyz",
    }):
        with patch("httpx.post", side_effect=httpx.ConnectError("Connection refused")):
            res = dispatch_sms_channel("+918098897666", "Test", "CMD-SG-CONN-ERR")
            assert res["status"] == "FAILED"
            assert "SMSGate local server unreachable" in res["error"]
            assert "Connection refused" in res["error"]
            assert "super_secret_password_xyz" not in res["error"]


def test_smsgate_timeout():
    """Verify that timeout produces clear safe error without secrets."""
    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "super_secret_password_xyz",
    }):
        with patch("httpx.post", side_effect=httpx.TimeoutException("Request timed out")):
            res = dispatch_sms_channel("+918098897666", "Test", "CMD-SG-TO-ERR")
            assert res["status"] == "FAILED"
            assert "SMSGate local server unreachable" in res["error"]
            assert "Request timed out" in res["error"]
            assert "super_secret_password_xyz" not in res["error"]


def test_smsgate_http_401_403_auth_failure():
    """Verify HTTP 401 and 403 authentication failures are handled safely."""
    # 401
    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_401.text = "Unauthorized"
    mock_401.json.side_effect = Exception("Not JSON")

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "wrong_password",
    }):
        with patch("httpx.post", return_value=mock_401):
            res = dispatch_sms_channel("+918098897666", "Test", "CMD-SG-401")
            assert res["status"] == "FAILED"
            assert res["error"] == "SMSGate authentication failed"
            assert "wrong_password" not in res["error"]

    # 403
    mock_403 = MagicMock()
    mock_403.status_code = 403
    mock_403.text = "Forbidden"
    mock_403.json.side_effect = Exception("Not JSON")

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "wrong_password",
    }):
        with patch("httpx.post", return_value=mock_403):
            res = dispatch_sms_channel("+918098897666", "Test", "CMD-SG-403")
            assert res["status"] == "FAILED"
            assert res["error"] == "SMSGate authentication failed"


def test_smsgate_http_4xx_5xx_failure():
    """Verify HTTP 4xx and 5xx API failures return safe error detail."""
    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_500.json.return_value = {"message": "SIM 1 device not ready"}

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "pwd",
    }):
        with patch("httpx.post", return_value=mock_500):
            res = dispatch_sms_channel("+918098897666", "Test", "CMD-SG-500")
            assert res["status"] == "FAILED"
            assert "SMSGate SMS request failed: HTTP 500 - SIM 1 device not ready" in res["error"]


def test_smsgate_invalid_json_response():
    """Verify non-JSON response on HTTP 200 is caught and reported as failure."""
    mock_bad_json = MagicMock()
    mock_bad_json.status_code = 200
    mock_bad_json.text = "<html><body>Not JSON</body></html>"
    mock_bad_json.json.side_effect = Exception("JSONDecodeError")

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "pwd",
    }):
        with patch("httpx.post", return_value=mock_bad_json):
            res = dispatch_sms_channel("+918098897666", "Test", "CMD-SG-BAD-JSON")
            assert res["status"] == "FAILED"
            assert "Invalid JSON response" in res["error"]


def test_smsgate_failure_persists_in_db():
    """Verify that SMSGate failure persists sms_status=FAILED and sms_error in database."""
    cmd_id = "CMD-SG-FAIL-DB-01"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-SG-FAIL",
    )

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "pwd",
    }):
        with patch("httpx.post", side_effect=httpx.ConnectError("Connection refused")):
            dispatch_res = dispatch_rescue_command_notifications(
                command_id=cmd_id,
                team_id="ALPHA",
                member_id="ALPHA-M001",
                victim_id="V-SG-FAIL",
            )
            assert dispatch_res["sms_status"] == "FAILED"
            assert "Connection refused" in dispatch_res["sms_error"]

            # Verify persisted in rescue_commands table
            cmd = db.get_rescue_command(cmd_id)
            assert cmd["sms_status"] == "FAILED"
            assert "Connection refused" in cmd["sms_error"]

            # Verify retrieved via list_notifications
            notifs = db.list_notifications(team_id="ALPHA")
            target_notif = next((n for n in notifs if n.get("rescue_command_id") == cmd_id), None)
            assert target_notif is not None
            assert target_notif["sms_status"] == "FAILED"
            assert "Connection refused" in target_notif["sms_error"]


def test_smsgate_success_persists_in_db():
    """Verify that SMSGate success persists sms_status=SENT and sms_error=None in database."""
    cmd_id = "CMD-SG-OK-DB-01"
    db.create_rescue_command(
        command_id=cmd_id,
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="V-SG-OK",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "MSG-SG-OK-999"}

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "pwd",
    }):
        with patch("httpx.post", return_value=mock_resp):
            dispatch_res = dispatch_rescue_command_notifications(
                command_id=cmd_id,
                team_id="ALPHA",
                member_id="ALPHA-M001",
                victim_id="V-SG-OK",
            )
            assert dispatch_res["sms_status"] == "SENT"
            assert dispatch_res["sms_error"] is None

            # Verify persisted in rescue_commands table
            cmd = db.get_rescue_command(cmd_id)
            assert cmd["sms_status"] == "SENT"
            assert cmd["sms_error"] is None

            # Verify retrieved via list_notifications
            notifs = db.list_notifications(team_id="ALPHA")
            target_notif = next((n for n in notifs if n.get("rescue_command_id") == cmd_id), None)
            assert target_notif is not None
            assert target_notif["sms_status"] == "SENT"
            assert target_notif["sms_error"] is None


def test_smsgate_health_check_helper():
    """Verify check_smsgate_health function behavior under success, auth failure, and connect error."""
    # 1. Success
    mock_h_resp = MagicMock()
    mock_h_resp.status_code = 200
    mock_h_resp.json.return_value = {"status": "pass"}
    with patch("httpx.get", return_value=mock_h_resp) as mock_get:
        h_res = check_smsgate_health(
            local_url="http://192.168.1.100:8080",
            username="admin",
            password="pwd",
        )
        assert h_res["available"] is True
        assert h_res["status_code"] == 200
        assert h_res["data"] == {"status": "pass"}
        assert h_res["error"] is None
        mock_get.assert_called_once_with(
            "http://192.168.1.100:8080/health",
            auth=("admin", "pwd"),
            timeout=3.0,
        )

    # 2. Auth failure (401)
    mock_401 = MagicMock()
    mock_401.status_code = 401
    mock_401.json.return_value = {"error": "unauthorized"}
    with patch("httpx.get", return_value=mock_401):
        h_res = check_smsgate_health(
            local_url="http://192.168.1.100:8080",
            username="admin",
            password="bad",
        )
        assert h_res["available"] is False
        assert h_res["status_code"] == 401
        assert "SMSGate authentication failed" in h_res["error"]

    # 3. Connection refused
    with patch("httpx.get", side_effect=httpx.ConnectError("Connection refused")):
        h_res = check_smsgate_health(
            local_url="http://192.168.1.100:8080",
            username="admin",
            password="pwd",
        )
        assert h_res["available"] is False
        assert "SMSGate local server unreachable: Connection refused" in h_res["error"]

    # 4. Missing URL
    with patch.dict(os.environ, {"SMSGATE_LOCAL_URL": ""}):
        h_res = check_smsgate_health(local_url="")
        assert h_res["available"] is False
        assert "Missing SMSGate local URL" in h_res["error"]


def test_smsgate_frontend_ui_provider_aware_text():
    """Verify frontend notification.js renders provider-aware text for SMSGate without GSM simulated text."""
    js_path = "frontend/js/notification.js"
    assert os.path.exists(js_path)
    with open(js_path, "r", encoding="utf-8") as f:
        js_content = f.read()

    assert "SMSGate Android gateway delivered" in js_content
    assert "GSM simulated gateway delivered" not in js_content


# ---------------------------------------------------------------------- #
# 5. SMSGate Recipient Phone-Number Normalization Tests (E.164 Standard)
# ---------------------------------------------------------------------- #

def test_phone_number_normalization_indian_numbers():
    """
    Verify phone normalization rules for Indian mobile numbers:
    1. 10-digit mobile starting with 6,7,8,9: 8098897666 -> +918098897666
    2. 11-digit starting with 0: 08098897666 -> +918098897666
    3. 12-digit without +: 918098897666 -> +918098897666
    4. Already Indian E.164: +918098897666 -> +918098897666
    """
    # 1. 10-digit mobile
    assert normalize_phone_number_e164("8098897666") == "+918098897666"
    assert normalize_phone_number_e164("8877665544") == "+918877665544"
    assert normalize_phone_number_e164("7766554433") == "+917766554433"
    assert normalize_phone_number_e164("6655443322") == "+916655443322"

    # 2. Leading 0 with 10 digits
    assert normalize_phone_number_e164("08098897666") == "+918098897666"
    assert normalize_phone_number_e164("08877665544") == "+918877665544"

    # 3. 12-digit without +
    assert normalize_phone_number_e164("918098897666") == "+918098897666"
    assert normalize_phone_number_e164("918877665544") == "+918877665544"

    # 4. Already Indian E.164
    assert normalize_phone_number_e164("+918098897666") == "+918098897666"
    assert normalize_phone_number_e164("+918877665544") == "+918877665544"

    # Backward compatibility alias
    assert normalize_smsgate_phone("8098897666") == "+918098897666"


def test_phone_number_normalization_whitespace_and_hyphens():
    """Verify phone normalization with various spacing, hyphens, and parentheses."""
    assert normalize_phone_number_e164(" 8098897666 ") == "+918098897666"
    assert normalize_phone_number_e164("+91 80988 97666") == "+918098897666"
    assert normalize_phone_number_e164("+91-80988-97666") == "+918098897666"
    assert normalize_phone_number_e164("80988-97666") == "+918098897666"
    assert normalize_phone_number_e164("0 80988 97666") == "+918098897666"
    assert normalize_phone_number_e164("0-80988-97666") == "+918098897666"
    assert normalize_phone_number_e164("91 80988 97666") == "+918098897666"
    assert normalize_phone_number_e164("91-80988-97666") == "+918098897666"
    assert normalize_phone_number_e164("+91 (809) 889-7666") == "+918098897666"
    assert normalize_phone_number_e164("(08098) 897666") == "+918098897666"


def test_phone_number_normalization_preserves_international_e164():
    """Verify that valid international E.164 numbers with '+' are preserved, not corrupted with +91."""
    assert normalize_phone_number_e164("+14155238886") == "+14155238886"
    assert normalize_phone_number_e164("+447911123456") == "+447911123456"
    assert normalize_phone_number_e164("+61412345678") == "+61412345678"
    assert normalize_phone_number_e164("+819012345678") == "+819012345678"
    assert normalize_phone_number_e164("+1 (415) 523-8886") == "+14155238886"


def test_phone_number_normalization_rejects_invalid_ambiguous():
    """Verify that invalid or ambiguous phone numbers are rejected (return None)."""
    assert normalize_phone_number_e164("") is None
    assert normalize_phone_number_e164("   ") is None
    assert normalize_phone_number_e164(None) is None
    assert normalize_phone_number_e164("12345") is None  # Too short
    assert normalize_phone_number_e164("abcdefg") is None  # Non-numeric
    assert normalize_phone_number_e164("+0123456789") is None  # Country code starts with 0
    assert normalize_phone_number_e164("5363879303") is None  # 10 digits starting with 5 (invalid Indian mobile)
    assert normalize_phone_number_e164("01234567890") is None  # 11 digits starting with 01
    assert normalize_phone_number_e164("+911234567890") is None  # Indian number starting with 1
    assert normalize_phone_number_e164("911234567890") is None  # Indian 12-digit starting with 911


def test_smsgate_dispatch_phone_number_normalization_in_payload():
    """
    Verify that SMSGate dispatch correctly normalizes all valid formats to E.164
    in the JSON payload sent to the SMSGate endpoint.
    """
    test_inputs = [
        ("8098897666", "+918098897666"),
        ("08098897666", "+918098897666"),
        ("918098897666", "+918098897666"),
        ("+918098897666", "+918098897666"),
        (" +91 80988-97666 ", "+918098897666"),
        ("+14155238886", "+14155238886"),
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": "MSG-NORM-OK"}

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "pwd",
        "SMSGATE_SIM_NUMBER": "1",
    }):
        for input_phone, expected_e164 in test_inputs:
            with patch("httpx.post", return_value=mock_resp) as mock_post:
                res = dispatch_smsgate_sms(
                    phone_normalized=input_phone,
                    message_text="Test Normalization",
                    rescue_command_id="CMD-NORM-01",
                )
                assert res["status"] == "SENT"
                assert res["error"] is None

                mock_post.assert_called_once()
                call_json = mock_post.call_args[1]["json"]

                # Requirement 9: JSON payload structure unchanged
                assert call_json["textMessage"] == {"text": "Test Normalization"}
                assert call_json["simNumber"] == 1

                # Requirement 12: final value sent is E.164 format
                assert call_json["phoneNumbers"] == [expected_e164]


def test_smsgate_dispatch_rejects_invalid_phone_number():
    """Verify that dispatch_smsgate_sms safely rejects invalid/ambiguous phone numbers without sending."""
    invalid_inputs = ["12345", "not_a_phone", "+0123456789", "5363879303"]

    with patch.dict(os.environ, {
        "SMS_PROVIDER": "SMSGATE",
        "SMSGATE_ENABLED": "true",
        "SMSGATE_LOCAL_URL": "http://192.168.1.100:8080",
        "SMSGATE_USERNAME": "admin",
        "SMSGATE_PASSWORD": "pwd",
    }):
        for invalid_phone in invalid_inputs:
            with patch("httpx.post") as mock_post:
                res = dispatch_smsgate_sms(
                    phone_normalized=invalid_phone,
                    message_text="Test",
                    rescue_command_id="CMD-INVALID-PHONE",
                )
                assert res["status"] == "FAILED"
                assert "Invalid recipient phone number" in res["error"]
                mock_post.assert_not_called()


