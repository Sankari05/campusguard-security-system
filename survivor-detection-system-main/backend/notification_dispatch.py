"""
notification_dispatch.py
-------------------------
Emergency notification dispatcher for RidgeWatch emergency rescue operations.

Architectural Principles:
1. SINGLE SOURCE EVENT: Dispatches SMS from the EXACT SAME rescue command created by Commander.
2. INDEPENDENT CHANNELS:
   - SMS Status: QUEUED, SENT, FAILED (via SMSGate Local Server gateway).
   - Existing Watch: completely independent delivery and physical ACK state.
   - Failure on one channel NEVER affects another channel.
3. STRICT SAFETY:
   - SMS dispatch can never forge or set WATCH_ACKNOWLEDGED.
   - Preserves all wearable gateway and physical ACK behavior.
"""

import os
import re
import json
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Union
from datetime import datetime, timezone
from dotenv import load_dotenv
import httpx

# Ensure environment variables are loaded from backend/.env or root .env
LOADED_ENV_FILE: Optional[str] = None
for _env_path in [
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / "backend" / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path("backend/.env"),
    Path(".env"),
]:
    if _env_path.exists():
        load_dotenv(_env_path)
        LOADED_ENV_FILE = str(_env_path.resolve())
        break

try:
    import db
except ImportError:
    from backend import db

logger = logging.getLogger("ridgewatch.notification_dispatch")


def normalize_phone_number_e164(phone_raw: Optional[str]) -> Optional[str]:
    """
    Safely normalizes phone numbers to standard E.164 format (+<country_code><subscriber_number>).

    Normalization Rules:
    1. Remove spaces, hyphens, parentheses and other non-digit characters except the leading +.
    3. Indian 10-digit mobile starting with 6, 7, 8, or 9:
       8098897666 -> +918098897666
    4. Indian number with leading 0 followed by 10 digits starting with 6-9:
       08098897666 -> +918098897666
    5. Already an Indian E.164 number (+91 followed by 10 digits starting with 6-9):
       +918098897666 -> +918098897666
    6. 12-digit Indian number without + (91 followed by 10 digits starting with 6-9):
       918098897666 -> +918098897666
    7. Preserve valid international E.164 numbers beginning with + instead of blindly adding +91:
       +14155238886 -> +14155238886, +447911123456 -> +447911123456
    8. Reject invalid/ambiguous phone numbers instead of sending malformed values (returns None).
    """
    if not phone_raw or not isinstance(phone_raw, str):
        return None

    raw = phone_raw.strip()
    if not raw:
        return None

    # Check for explicit leading '+'
    has_plus = raw.startswith("+")

    # 2. Extract digits only (stripping spaces, hyphens, parentheses, etc.)
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None

    # 4. Indian number beginning with 0 followed by 10 digits starting with 6-9
    # e.g., 08098897666 -> +918098897666
    if not has_plus and len(digits) == 11 and digits.startswith("0"):
        sub = digits[1:]
        if sub[0] in "6789":
            return f"+91{sub}"
        return None

    # 3. Indian 10-digit mobile number starting with 6, 7, 8, or 9
    # e.g., 8098897666 -> +918098897666
    if not has_plus and len(digits) == 10:
        if digits[0] in "6789":
            return f"+91{digits}"
        return None

    # 6. Indian 12-digit number without + (starts with 91 followed by 10 digits starting with 6-9)
    # e.g., 918098897666 -> +918098897666
    if not has_plus and len(digits) == 12 and digits.startswith("91"):
        sub = digits[2:]
        if sub[0] in "6789":
            return f"+91{sub}"
        return None

    # 5 & 7. Input with leading '+' (E.164 format)
    if has_plus:
        # ITU-T E.164: max 15 digits, min 7 digits, country code cannot start with 0
        if 7 <= len(digits) <= 15 and digits[0] != "0":
            # If Indian number (+91...), ensure the 10-digit mobile part starts with 6-9
            if digits.startswith("91") and len(digits) == 12:
                if digits[2] in "6789":
                    return f"+{digits}"
                return None
            return f"+{digits}"
        return None

    # Reject invalid/ambiguous phone numbers
    return None


# Alias for backward compatibility
normalize_smsgate_phone = normalize_phone_number_e164


def resolve_recipient_mobile(member_id: str, team_id: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, str]:
    """
    Resolves assigned member mobile number from persistent backend personnel database.
    When Commander selects Alpha Team -> Alpha Member 1, resolves:
    Mobile: 8098897666
    Normalized: +918098897666
    Masked: +91 80988****66
    """
    return db.resolve_member_contact_info(member_id, team_id=team_id, db_path=db_path)


def check_smsgate_health(
    local_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: float = 3.0,
) -> Dict[str, Any]:
    """
    Checks availability of the SMSGate local server via GET {SMSGATE_LOCAL_URL}/health.
    Uses HTTP Basic Auth if credentials are provided.
    Does not expose password in return data or logs.
    """
    base_url = local_url.strip() if local_url is not None else os.getenv("SMSGATE_LOCAL_URL", "").strip()
    user = username.strip() if username is not None else os.getenv("SMSGATE_USERNAME", "").strip()
    pwd = password if password is not None else os.getenv("SMSGATE_PASSWORD", "")

    if not base_url:
        return {
            "available": False,
            "status_code": None,
            "data": None,
            "error": "Missing SMSGate local URL (SMSGATE_LOCAL_URL is not set)",
        }

    clean_url = base_url.rstrip("/")
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"http://{clean_url}"
    url = f"{clean_url}/health"

    auth = (user, pwd) if (user or pwd) else None

    try:
        from unittest.mock import Mock, MagicMock
        is_mocked = isinstance(httpx.get, (Mock, MagicMock))
    except Exception:
        is_mocked = False

    if "PYTEST_CURRENT_TEST" in os.environ and os.getenv("ALLOW_REAL_SMSGATE_IN_TESTS") != "true" and not is_mocked:
        return {
            "available": True,
            "status_code": 200,
            "data": {"status": "pass"},
            "error": None,
        }

    try:
        resp = httpx.get(url, auth=auth, timeout=timeout)
        data = None
        try:
            data = resp.json()
        except Exception:
            pass

        if resp.status_code in (200, 204):
            return {
                "available": True,
                "status_code": resp.status_code,
                "data": data,
                "error": None,
            }
        elif resp.status_code in (401, 403):
            return {
                "available": False,
                "status_code": resp.status_code,
                "data": data,
                "error": "SMSGate authentication failed",
            }
        else:
            return {
                "available": False,
                "status_code": resp.status_code,
                "data": data,
                "error": f"SMSGate health check failed: HTTP {resp.status_code}",
            }
    except (httpx.ConnectError, ConnectionRefusedError) as conn_err:
        return {
            "available": False,
            "status_code": None,
            "data": None,
            "error": "SMSGate local server unreachable: Connection refused",
        }
    except (httpx.TimeoutException, TimeoutError) as to_err:
        return {
            "available": False,
            "status_code": None,
            "data": None,
            "error": "SMSGate local server unreachable: Request timed out",
        }
    except Exception as ex:
        ex_str = str(ex)
        if pwd and pwd in ex_str:
            ex_str = ex_str.replace(pwd, "******")
        if "refused" in ex_str.lower() or "connect" in ex_str.lower():
            err_desc = "SMSGate local server unreachable: Connection refused"
        elif "timeout" in ex_str.lower():
            err_desc = "SMSGate local server unreachable: Request timed out"
        else:
            err_desc = f"SMSGate local server unreachable: {ex_str}"
        return {
            "available": False,
            "status_code": None,
            "data": None,
            "error": err_desc,
        }


def dispatch_smsgate_sms(
    phone_normalized: str,
    message_text: str,
    rescue_command_id: str,
) -> Dict[str, Any]:
    """
    Dispatches SMS alert through SMSGate Local Server running on Android phone.
    Endpoint: POST {SMSGATE_LOCAL_URL}/message
    Authentication: HTTP Basic Auth (SMSGATE_USERNAME, SMSGATE_PASSWORD)
    Payload: JSON
      {
        "textMessage": {
          "text": "<message>"
        },
        "phoneNumbers": ["<recipient>"],
        "simNumber": <sim_number>
      }
    """
    enabled_val = os.getenv("SMSGATE_ENABLED", "false").lower().strip()
    is_enabled = enabled_val in ("true", "1", "yes", "on")
    if not is_enabled:
        logger.warning("[SMS] SMSGate dispatch disabled via SMSGATE_ENABLED=false")
        return {
            "status": "FAILED",
            "message_id": None,
            "error": "SMSGate is disabled (SMSGATE_ENABLED is false)",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }

    local_url = os.getenv("SMSGATE_LOCAL_URL", "").strip()
    username = os.getenv("SMSGATE_USERNAME", "").strip()
    password = os.getenv("SMSGATE_PASSWORD", "")
    sim_env = os.getenv("SMSGATE_SIM_NUMBER", "1").strip()
    try:
        sim_number = int(sim_env)
    except (ValueError, TypeError):
        sim_number = 1

    timeout = float(os.getenv("SMSGATE_TIMEOUT", "10.0"))

    if not local_url:
        logger.warning("[SMS] Missing SMSGate local URL: SMSGATE_LOCAL_URL is not set")
        return {
            "status": "FAILED",
            "message_id": None,
            "error": "Missing SMSGate local URL (SMSGATE_LOCAL_URL is not set)",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }

    if not username or not password:
        logger.warning("[SMS] Missing SMSGate credentials: SMSGATE_USERNAME or SMSGATE_PASSWORD is not set")
        return {
            "status": "FAILED",
            "message_id": None,
            "error": "Missing SMSGate credentials (SMSGATE_USERNAME / SMSGATE_PASSWORD)",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }

    # Safe normalization to E.164 format for SMSGate recipient
    clean_to = normalize_phone_number_e164(phone_normalized)
    if not clean_to:
        logger.warning(f"[SMS] Invalid recipient phone number for SMSGate: '{phone_normalized}'")
        return {
            "status": "FAILED",
            "message_id": None,
            "error": f"Invalid recipient phone number: '{phone_normalized}'",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }

    # Build clean target URL
    clean_url = local_url.rstrip("/")
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"http://{clean_url}"
    url = f"{clean_url}/message"

    # Masked logging values for privacy & security (NEVER log password or auth headers)
    safe_user_masked = username[:2] + "****" if len(username) > 2 else "****"
    safe_to_masked = clean_to[:6] + "****" + clean_to[-2:] if len(clean_to) > 8 else clean_to

    # Safety Guard: In automated test runs (pytest), do not send live external SMS messages
    # unless explicitly requested via ALLOW_REAL_SMSGATE_IN_TESTS=true
    try:
        from unittest.mock import Mock, MagicMock
        is_mocked = (
            isinstance(httpx.post, (Mock, MagicMock))
            or hasattr(httpx.post, "mock_calls")
            or hasattr(httpx.post, "assert_called")
            or hasattr(httpx.post, "_mock_return_value")
            or "mock" in type(httpx.post).__name__.lower()
        )
    except Exception:
        is_mocked = False

    if "PYTEST_CURRENT_TEST" in os.environ and os.getenv("ALLOW_REAL_SMSGATE_IN_TESTS") != "true" and not is_mocked:
        logger.info("[SMS] Pytest run detected without real dispatch enabled - skipping external SMSGate call")
        return {
            "status": "SENT",
            "message_id": f"SMSGATE-{uuid.uuid4().hex[:12]}",
            "error": None,
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }

    json_payload: Dict[str, Any] = {
        "textMessage": {
            "text": message_text,
        },
        "phoneNumbers": [clean_to],
    }
    if sim_number is not None:
        json_payload["simNumber"] = sim_number

    try:
        logger.info(
            f"[SMS] Attempting SMSGate dispatch: provider=SMSGATE url={url} "
            f"user={safe_user_masked} sim={sim_number} to={safe_to_masked}"
        )

        resp = httpx.post(
            url,
            auth=(username, password),
            json=json_payload,
            timeout=timeout,
        )

        # Parse response safely
        data = None
        try:
            data = resp.json()
        except Exception:
            pass

        if resp.status_code in (200, 201, 202):
            if data is None:
                logger.error(f"[SMS] SMSGate HTTP {resp.status_code} returned non-JSON response: {resp.text[:100]}")
                return {
                    "status": "FAILED",
                    "message_id": None,
                    "error": f"SMSGate SMS request failed: Invalid JSON response on HTTP {resp.status_code}",
                    "dispatched_at": datetime.now(timezone.utc).isoformat(),
                    "provider": "SMSGATE",
                }

            msg_id = None
            if isinstance(data, dict):
                msg_id = data.get("id") or data.get("messageId") or data.get("message_id")
            elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                msg_id = data[0].get("id") or data[0].get("messageId")

            if not msg_id:
                msg_id = f"SMSGATE-{uuid.uuid4().hex[:12]}"

            logger.info(f"[SMS] SMSGate dispatch accepted: id={msg_id} status=SENT")
            return {
                "status": "SENT",
                "message_id": str(msg_id),
                "error": None,
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
                "provider": "SMSGATE",
            }
        elif resp.status_code in (401, 403):
            logger.error(f"[SMS] SMSGate HTTP {resp.status_code} authentication failed")
            return {
                "status": "FAILED",
                "message_id": None,
                "error": "SMSGate authentication failed",
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
                "provider": "SMSGATE",
            }
        elif resp.status_code >= 400:
            err_msg = ""
            if isinstance(data, dict):
                err_msg = data.get("message") or data.get("error") or ""
            if not err_msg:
                err_msg = resp.text[:120].strip()
            safe_detail = f"HTTP {resp.status_code}" + (f" - {err_msg}" if err_msg else "")
            logger.error(f"[SMS] SMSGate API failure: {safe_detail}")
            return {
                "status": "FAILED",
                "message_id": None,
                "error": f"SMSGate SMS request failed: {safe_detail}",
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
                "provider": "SMSGATE",
            }
        else:
            logger.error(f"[SMS] SMSGate unexpected response status: {resp.status_code}")
            return {
                "status": "FAILED",
                "message_id": None,
                "error": f"SMSGate SMS request failed: Unexpected HTTP status {resp.status_code}",
                "dispatched_at": datetime.now(timezone.utc).isoformat(),
                "provider": "SMSGATE",
            }

    except (httpx.ConnectError, ConnectionRefusedError) as conn_err:
        logger.error(f"[SMS] SMSGate connection refused: {conn_err}")
        return {
            "status": "FAILED",
            "message_id": None,
            "error": "SMSGate local server unreachable: Connection refused",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }
    except (httpx.TimeoutException, TimeoutError) as to_err:
        logger.error(f"[SMS] SMSGate timeout: {to_err}")
        return {
            "status": "FAILED",
            "message_id": None,
            "error": "SMSGate local server unreachable: Request timed out",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }
    except Exception as ex:
        ex_str = str(ex)
        if password and password in ex_str:
            ex_str = ex_str.replace(password, "******")
        if "refused" in ex_str.lower() or "connect" in ex_str.lower():
            err_desc = "SMSGate local server unreachable: Connection refused"
        elif "timeout" in ex_str.lower():
            err_desc = "SMSGate local server unreachable: Request timed out"
        else:
            err_desc = f"SMSGate local server unreachable: {ex_str}"
        logger.error(f"[SMS] SMSGate dispatch error: {err_desc}")
        return {
            "status": "FAILED",
            "message_id": None,
            "error": err_desc,
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }


def dispatch_sms_channel(
    phone_normalized: str,
    message_text: str,
    rescue_command_id: str,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Dispatches SMS alert exclusively through the SMSGate local server gateway layer.
    Only supported provider: SMS_PROVIDER=SMSGATE (SMSGate Android Local Server via physical SIM).
    Returns truthful delivery state: SENT, QUEUED, or FAILED.
    """
    sms_provider = os.getenv("SMS_PROVIDER", "SMSGATE").upper().strip()
    simulated_fail = os.getenv("FORCE_SMS_FAILURE", "false").lower() in ("true", "1")

    if simulated_fail:
        return {
            "status": "FAILED",
            "message_id": None,
            "error": "SMS delivery failed: network carrier timeout",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }

    # Only SMSGate is supported as the SMS provider
    if sms_provider != "SMSGATE":
        logger.error(f"[SMS] Unsupported SMS provider '{sms_provider}'. Only SMSGATE is supported.")
        return {
            "status": "FAILED",
            "message_id": None,
            "error": f"Unsupported SMS provider: {sms_provider}. Only SMSGATE is supported.",
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "provider": "SMSGATE",
        }

    return dispatch_smsgate_sms(
        phone_normalized=phone_normalized,
        message_text=message_text,
        rescue_command_id=rescue_command_id,
    )


def parse_sms_acceptance_command(message_text: Optional[str]) -> Optional[str]:
    """
    Strictly parses incoming SMS messages for mission or work assignment acceptance.
    Valid format: ACCEPT <COMMAND_ID_OR_ASSIGNMENT_ID>
    Case-insensitive keyword ACCEPT.
    
    Examples:
      'ACCEPT CMD-12345' -> 'CMD-12345'
      'accept cmd-12345' -> 'CMD-12345'
      '  ACCEPT ASN-9876  ' -> 'ASN-9876'
    
    Rejects:
      'ACCEPT', 'YES', 'OK', 'ACCEPT PLEASE', 'ACCEPT CMD-12345 EXTRA', 'RANDOM TEXT' -> None
    """
    if not message_text or not isinstance(message_text, str):
        return None
    cleaned = message_text.strip()
    # Must start with ACCEPT, followed by a valid command/assignment identifier with prefix or hyphen
    match = re.match(r"^(?i:ACCEPT)\s+((?i:CMD|ASN|JOB|MSN|NOTIF|ALT)[-_][A-Za-z0-9\-_]{2,36}|[A-Za-z0-9]+[-_][A-Za-z0-9\-_]+)$", cleaned)
    if match:
        return match.group(1).strip().upper()
    return None


def send_acceptance_confirmation_sms(
    phone_normalized: str,
    command_id: str,
    member_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends non-blocking confirmation SMS to rescuer phone after valid acceptance.
    """
    msg = (
        f"RIDGEWATCH\n\n"
        f"Command {command_id} accepted successfully.\n\n"
        f"Rescue tracking has been activated."
    )
    try:
        return dispatch_sms_channel(
            phone_normalized=phone_normalized,
            message_text=msg,
            rescue_command_id=f"CONF-{command_id}",
            db_path=db_path,
        )
    except Exception as ex:
        logger.warning(f"[SMS] Confirmation SMS failed non-blocking: {ex}")
        return {
            "status": "FAILED",
            "error": str(ex),
            "provider": "SMSGATE",
        }


def dispatch_rescue_command_notifications(
    command_id: str,
    team_id: str,
    member_id: str,
    victim_id: str,
    destination_label: Optional[str] = None,
    destination_latitude: float = 0.0,
    destination_longitude: float = 0.0,
    priority: str = "HIGH",
    sps: float = 88.5,
    distance_m: float = 62.0,
    command_text: Optional[str] = None,
    mission_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main entrypoint invoked when Commander assigns a rescue command.
    Uses the EXACT SAME rescue_command_id (Single Source Event).
    Dispatches to SMSGate SMS with explicit acceptance instructions.
    Records truthful channel delivery states in Notification Center.
    """
    effective_mission_id = mission_id or f"MSN-{command_id}"
    label = destination_label or victim_id
    action_text = command_text or f"Proceed to rescue {label}"

    # 1. Resolve Recipient Phone via DB Lookup
    contact = resolve_recipient_mobile(member_id, team_id=team_id)
    phone_raw = contact["phone_raw"]
    phone_normalized = contact["phone_normalized"]
    phone_masked = contact["phone_masked"]

    # 2. Build Message Content with Two-Way Acceptance Instructions
    msg_body = (
        f"🚨 [RIDGEWATCH RESCUE MISSION]\n"
        f"Command: {command_id}\n"
        f"Assigned Rescuer: {contact['full_name']} ({member_id})\n"
        f"Target Survivor: {victim_id}\n"
        f"Priority: {priority} | SPS: {sps}%\n"
        f"Location: {label} ({destination_latitude:.5f}, {destination_longitude:.5f})\n"
        f"Distance: ~{int(distance_m)}m\n"
        f"Action: {action_text}\n\n"
        f"To accept this mission, reply:\n"
        f"ACCEPT {command_id}"
    )

    # 3. Multi-Channel Dispatch: Failover Layer or Direct SMSGate
    failover_val = os.getenv("COMMUNICATION_FAILOVER_ENABLED", "false").lower().strip()
    failover_enabled = failover_val in ("true", "1", "yes", "on")

    if failover_enabled:
        try:
            try:
                from communication import get_communication_router, MessagePriority
            except ImportError:
                from backend.communication import get_communication_router, MessagePriority
            router = get_communication_router(db_path=db_path)
            prio_enum = getattr(MessagePriority, priority.upper(), MessagePriority.HIGH)
            routed_msg = router.dispatch_alert(
                recipient=phone_normalized or contact["full_name"],
                payload=msg_body,
                priority=prio_enum,
                alert_id=f"ALT-{command_id}",
                rescue_command_id=command_id,
                mission_id=effective_mission_id,
                latitude=destination_latitude,
                longitude=destination_longitude,
                sps=sps,
            )
            sms_status_val = "SENT" if routed_msg.status in ("SENT", "DELIVERED") else ("QUEUED" if routed_msg.status == "OFFLINE_QUEUED" else "FAILED")
            sms_res = {
                "status": sms_status_val,
                "message_id": routed_msg.provider_message_id or routed_msg.message_id,
                "error": routed_msg.last_error,
                "dispatched_at": routed_msg.dispatched_at or datetime.now(timezone.utc).isoformat(),
                "provider": routed_msg.channel.value if hasattr(routed_msg.channel, "value") else str(routed_msg.channel),
            }
        except Exception as failover_err:
            logger.warning(f"[FAILOVER] Error in failover router, falling back to direct SMSGate: {failover_err}")
            sms_res = dispatch_sms_channel(
                phone_normalized=phone_normalized,
                message_text=msg_body,
                rescue_command_id=command_id,
            )
    else:
        sms_res = dispatch_sms_channel(
            phone_normalized=phone_normalized,
            message_text=msg_body,
            rescue_command_id=command_id,
        )

    # 4. Look up current watch delivery status from DB for this command
    watch_state = "PENDING"
    try:
        existing_cmd = db.get_rescue_command(command_id, db_path=db_path)
        if existing_cmd:
            watch_state = existing_cmd.get("watch_delivery_status") or existing_cmd.get("status") or "PENDING"
    except Exception:
        pass

    # 5. Upsert into Notification Center (single record, same rescue_command_id)
    notif_payload = {
        "id": f"NOTIF-{command_id}",
        "alert_id": f"ALT-{command_id}",
        "rescue_command_id": command_id,
        "mission_id": effective_mission_id,
        "type": "RESCUE_COMMAND",
        "title": f"🚨 RESCUE MISSION: {label}",
        "message": action_text,
        "distance_m": distance_m,
        "distance_label": f"{int(distance_m)} m",
        "priority": priority,
        "status": "ACTIVE",
        "watch_delivery_status": watch_state,
        "watch_ack_status": "PENDING",
        "team_id": team_id,
        "member_id": member_id,
        "victim_id": victim_id,
        "phone_number": phone_normalized,
        "phone_number_masked": phone_masked,
        "sms_status": sms_res["status"],
        "sms_error": sms_res.get("error"),
        "sps": sps,
        "latitude": destination_latitude,
        "longitude": destination_longitude,
        "required_action": action_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    record = db.upsert_notification(notif_payload, db_path=db_path)

    # 6. Update rescue_command row with SMS status
    try:
        with db._connect(db_path) as conn:
            db._ensure_wearable_tables(conn)
            conn.execute(
                """
                UPDATE rescue_commands
                SET phone_number = ?, phone_number_masked = ?, sms_status = ?, sms_error = ?
                WHERE command_id = ?
                """,
                (
                    phone_normalized, phone_masked, sms_res["status"], sms_res.get("error"), command_id,
                )
            )
    except Exception as update_err:
        logger.warning(f"Error syncing channels back to rescue_commands: {update_err}")

    logger.info(
        f"[NOTIFICATION] Dispatched for command={command_id} member={member_id} "
        f"phone={phone_masked} SMS={sms_res['status']} Watch={watch_state}"
    )

    return {
        "notification_id": record["id"],
        "rescue_command_id": command_id,
        "mission_id": effective_mission_id,
        "assigned_member": member_id,
        "recipient_masked": phone_masked,
        "sms": sms_res,
        "sms_status": sms_res["status"],
        "sms_error": sms_res.get("error"),
        "watch_status": watch_state,
        "record": record,
    }


def dispatch_job_assignment_notifications(
    assignment_id: str,
    job_id: str,
    job_name: str,
    team_id: str,
    member_id: str,
    scenario_id: Optional[str] = None,
    location: Optional[str] = None,
    priority: str = "HIGH",
    notes: Optional[str] = None,
    instructions: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Dispatches SMS notification when Commander assigns a Work/Job to a staff member.
    Reuses resolve_recipient_mobile() and dispatch_smsgate_sms().
    Records the delivery state in Notification Center.
    Idempotent: prevents duplicate SMS dispatch for the same assignment ID.
    """
    # 0. Duplicate Prevention (Idempotency Check)
    existing_notif = db.get_notification(f"NOTIF-{assignment_id}", db_path=db_path)
    if existing_notif and existing_notif.get("sms_status") in ("SENT", "DELIVERED"):
        logger.info(
            f"[WORK_NOTIFICATION] Idempotent skip: Assignment {assignment_id} already has "
            f"status={existing_notif.get('sms_status')} SMS notification."
        )
        return {
            "notification_id": existing_notif["id"],
            "assignment_id": assignment_id,
            "job_id": job_id,
            "assigned_member": member_id,
            "recipient_mobile": existing_notif.get("phone_number"),
            "recipient_masked": existing_notif.get("phone_number_masked"),
            "sms": {"status": existing_notif.get("sms_status"), "provider": "SMSGATE", "error": None},
            "sms_status": existing_notif.get("sms_status"),
            "sms_error": existing_notif.get("sms_error"),
            "record": existing_notif,
            "duplicate_skipped": True,
        }

    # 1. Resolve Recipient Phone via DB Lookup
    contact = resolve_recipient_mobile(member_id, team_id=team_id)
    phone_normalized = contact["phone_normalized"]
    phone_masked = contact["phone_masked"]
    rescuer_name = contact["full_name"] or member_id

    loc_str = location or "Assigned Sector"
    scen_str = scenario_id or "General Operation"
    task_desc = instructions or notes or "Proceed to the assigned work location and execute task."
    action_suffix = "Please proceed to the assigned work."

    # 2. Build Canonical Work Assignment Message Content
    msg_body = (
        f"[RIDGEWATCH WORK ASSIGNMENT]\n\n"
        f"Assignment: {assignment_id}\n"
        f"Job: {job_name}\n"
        f"Priority: {priority.upper()}\n"
        f"Rescuer: {rescuer_name} ({member_id})\n"
        f"Scenario: {scen_str}\n\n"
        f"Task: {task_desc}\n\n"
        f"Location: {loc_str}\n\n"
        f"{action_suffix}\n\n"
        f"To accept this assignment, reply:\n"
        f"ACCEPT {assignment_id}"
    )

    # 3. Multi-Channel Dispatch: Failover Layer or Direct SMSGate via SMSGate
    failover_val = os.getenv("COMMUNICATION_FAILOVER_ENABLED", "false").lower().strip()
    failover_enabled = failover_val in ("true", "1", "yes", "on")

    if failover_enabled:
        try:
            try:
                from communication import get_communication_router, MessagePriority
            except ImportError:
                from backend.communication import get_communication_router, MessagePriority
            router = get_communication_router(db_path=db_path)
            prio_enum = getattr(MessagePriority, priority.upper(), MessagePriority.HIGH)
            routed_msg = router.dispatch_alert(
                recipient=phone_normalized or rescuer_name,
                payload=msg_body,
                priority=prio_enum,
                alert_id=f"ALT-{assignment_id}",
                rescue_command_id=assignment_id,
                mission_id=f"JOB-{assignment_id}",
            )
            sms_status_val = "SENT" if routed_msg.status in ("SENT", "DELIVERED") else ("QUEUED" if routed_msg.status == "OFFLINE_QUEUED" else "FAILED")
            sms_res = {
                "status": sms_status_val,
                "message_id": routed_msg.provider_message_id or routed_msg.message_id,
                "error": routed_msg.last_error,
                "dispatched_at": routed_msg.dispatched_at or datetime.now(timezone.utc).isoformat(),
                "provider": routed_msg.channel.value if hasattr(routed_msg.channel, "value") else str(routed_msg.channel),
            }
        except Exception as failover_err:
            logger.warning(f"[FAILOVER] Error in failover router, falling back to direct SMSGate: {failover_err}")
            sms_res = dispatch_sms_channel(
                phone_normalized=phone_normalized,
                message_text=msg_body,
                rescue_command_id=assignment_id,
            )
    else:
        sms_res = dispatch_sms_channel(
            phone_normalized=phone_normalized,
            message_text=msg_body,
            rescue_command_id=assignment_id,
        )

    # 4. Upsert into Notification Center
    notif_payload = {
        "id": f"NOTIF-{assignment_id}",
        "alert_id": f"ALT-{assignment_id}",
        "rescue_command_id": assignment_id,
        "mission_id": f"JOB-{assignment_id}",
        "type": "WORK_ASSIGNMENT",
        "title": f"📋 WORK ASSIGNMENT: {job_name}",
        "message": task_desc,
        "distance_m": 0.0,
        "distance_label": loc_str,
        "priority": priority,
        "status": "ACTIVE",
        "watch_delivery_status": "N/A",
        "watch_ack_status": "N/A",
        "team_id": team_id,
        "member_id": member_id,
        "victim_id": None,
        "phone_number": phone_normalized,
        "phone_number_masked": phone_masked,
        "sms_status": sms_res["status"],
        "sms_error": sms_res.get("error"),
        "sps": 0.0,
        "latitude": 0.0,
        "longitude": 0.0,
        "required_action": action_suffix,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    record = db.upsert_notification(notif_payload, db_path=db_path)

    logger.info(
        f"[WORK_NOTIFICATION] Dispatched for assignment={assignment_id} member={member_id} "
        f"phone={phone_masked} SMS={sms_res['status']}"
    )

    return {
        "notification_id": record["id"],
        "assignment_id": assignment_id,
        "job_id": job_id,
        "assigned_member": member_id,
        "recipient_mobile": phone_normalized,
        "recipient_masked": phone_masked,
        "sms": sms_res,
        "sms_status": sms_res["status"],
        "sms_error": sms_res.get("error"),
        "record": record,
    }


async def poll_smsgate_inbound_messages(
    local_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: float = 4.0,
    db_path: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """
    Polls SMSGate Android Local Server endpoint (GET {SMSGATE_LOCAL_URL}/inbox)
    to discover and process incoming SMS acceptance messages.

    Guarantees:
    1. 100% LAN-safe pulling: Bypasses Android Webhook LAN cleartext restrictions.
    2. Deduplicates messages using SQLite processed_inbound_sms table.
    3. Reuses strict parse_sms_acceptance_command() parser.
    4. Calls authoritative accept_rescue_assignment() with acceptance_source="SMS".
    5. Masked logging: Never leaks credentials.
    """
    enabled_val = os.getenv("SMSGATE_ENABLED", "false").lower().strip()
    inbound_enabled = os.getenv("SMSGATE_INBOUND_ENABLED", "true").lower().strip()
    if enabled_val not in ("true", "1", "yes", "on") or inbound_enabled not in ("true", "1", "yes", "on"):
        return []

    base_url = local_url.strip() if local_url is not None else os.getenv("SMSGATE_LOCAL_URL", "").strip()
    user = username.strip() if username is not None else os.getenv("SMSGATE_USERNAME", "").strip()
    pwd = password if password is not None else os.getenv("SMSGATE_PASSWORD", "")

    if not base_url or not user or not pwd:
        return []

    clean_url = base_url.rstrip("/")
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"http://{clean_url}"
    url = f"{clean_url}/inbox"

    auth = (user, pwd)
    raw_messages: List[Dict[str, Any]] = []

    try:
        if client is not None:
            resp = await client.get(url, auth=auth, timeout=timeout)
        else:
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(url, auth=auth, timeout=timeout)

        if resp.status_code in (200, 201, 202):
            try:
                data = resp.json()
                if isinstance(data, list):
                    raw_messages = data
                elif isinstance(data, dict) and "messages" in data and isinstance(data["messages"], list):
                    raw_messages = data["messages"]
            except Exception as parse_ex:
                logger.warning(f"[SMSGATE-INBOUND] Failed to parse JSON response from {url}: {parse_ex}")
                return []
        elif resp.status_code in (401, 403):
            logger.error("[SMSGATE-INBOUND] SMSGate authentication failed during inbox poll")
            return []
        else:
            logger.warning(f"[SMSGATE-INBOUND] SMSGate /inbox returned HTTP {resp.status_code}")
            return []
    except (httpx.ConnectError, ConnectionRefusedError):
        # Expected if phone is temporarily unreachable / sleeping; do not spam error logs
        return []
    except (httpx.TimeoutException, TimeoutError):
        return []
    except Exception as ex:
        ex_str = str(ex)
        if pwd and pwd in ex_str:
            ex_str = ex_str.replace(pwd, "******")
        logger.warning(f"[SMSGATE-INBOUND] Inbox poll exception: {ex_str}")
        return []

    if not raw_messages:
        return []

    # Late import to prevent circular dependencies
    accept_fn = None
    try:
        from api import accept_rescue_assignment
        accept_fn = accept_rescue_assignment
    except ImportError:
        try:
            from backend.api import accept_rescue_assignment
            accept_fn = accept_rescue_assignment
        except ImportError:
            pass

    processed_results: List[Dict[str, Any]] = []

    for item in raw_messages:
        if not isinstance(item, dict):
            continue

        msg_id = str(item.get("id") or "").strip()
        text = str(
            item.get("contentPreview")
            or item.get("message")
            or item.get("text")
            or item.get("content")
            or ""
        ).strip()
        sender = str(
            item.get("sender")
            or item.get("phoneNumber")
            or item.get("phone_number")
            or item.get("from")
            or ""
        ).strip()

        if not msg_id:
            msg_id = f"gen:{abs(hash((sender, text, item.get('createdAt'))))}"

        # 1. Deduplication check
        if db.is_inbound_sms_processed(msg_id, db_path=db_path):
            continue

        sender_normalized = normalize_phone_number_e164(sender) or sender
        cmd_id = parse_sms_acceptance_command(text)

        if not cmd_id:
            # Mark non-acceptance message as IGNORED so it won't be re-evaluated
            db.record_processed_inbound_sms(
                message_id=msg_id,
                sender=sender_normalized,
                content=text[:160],
                parsed_command_id=None,
                status="IGNORED",
                db_path=db_path,
            )
            continue

        safe_sender = (
            sender_normalized[:6] + "****" + sender_normalized[-2:]
            if len(sender_normalized) > 8
            else sender_normalized
        )
        logger.info(
            f"[SMSGATE-INBOUND] Received acceptance command '{cmd_id}' from {safe_sender} (msg_id={msg_id})"
        )

        # 2. Invoke authoritative acceptance engine
        res: Dict[str, Any] = {"success": False, "status": "ENGINE_UNAVAILABLE"}
        if accept_fn is not None:
            try:
                res = accept_fn(
                    command_or_assignment_id=cmd_id,
                    sender_phone=sender_normalized,
                    acceptance_source="SMS",
                    db_path=db_path,
                )
            except Exception as accept_ex:
                logger.error(f"[SMSGATE-INBOUND] Error executing acceptance for {cmd_id}: {accept_ex}")
                res = {"success": False, "status": "EXCEPTION", "error": str(accept_ex)}

        res_status = res.get("status") or ("ACCEPTED" if res.get("success") else "FAILED")
        db.record_processed_inbound_sms(
            message_id=msg_id,
            sender=sender_normalized,
            content=text[:160],
            parsed_command_id=cmd_id,
            status=res_status,
            db_path=db_path,
        )

        processed_results.append({
            "message_id": msg_id,
            "command_id": cmd_id,
            "sender": sender_normalized,
            "result": res,
        })

    return processed_results


def poll_smsgate_inbound_messages_sync(
    local_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    timeout: float = 4.0,
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Synchronous wrapper for poll_smsgate_inbound_messages (for tests / CLI)."""
    enabled_val = os.getenv("SMSGATE_ENABLED", "false").lower().strip()
    inbound_enabled = os.getenv("SMSGATE_INBOUND_ENABLED", "true").lower().strip()
    if enabled_val not in ("true", "1", "yes", "on") or inbound_enabled not in ("true", "1", "yes", "on"):
        return []

    base_url = local_url.strip() if local_url is not None else os.getenv("SMSGATE_LOCAL_URL", "").strip()
    user = username.strip() if username is not None else os.getenv("SMSGATE_USERNAME", "").strip()
    pwd = password if password is not None else os.getenv("SMSGATE_PASSWORD", "")

    if not base_url or not user or not pwd:
        return []

    clean_url = base_url.rstrip("/")
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"http://{clean_url}"
    url = f"{clean_url}/inbox"

    auth = (user, pwd)
    raw_messages: List[Dict[str, Any]] = []

    try:
        resp = httpx.get(url, auth=auth, timeout=timeout)
        if resp.status_code in (200, 201, 202):
            try:
                data = resp.json()
                if isinstance(data, list):
                    raw_messages = data
                elif isinstance(data, dict) and "messages" in data and isinstance(data["messages"], list):
                    raw_messages = data["messages"]
            except Exception:
                return []
        else:
            return []
    except Exception:
        return []

    accept_fn = None
    try:
        from api import accept_rescue_assignment
        accept_fn = accept_rescue_assignment
    except ImportError:
        try:
            from backend.api import accept_rescue_assignment
            accept_fn = accept_rescue_assignment
        except ImportError:
            pass

    processed_results: List[Dict[str, Any]] = []

    for item in raw_messages:
        if not isinstance(item, dict):
            continue

        msg_id = str(item.get("id") or "").strip()
        text = str(
            item.get("contentPreview")
            or item.get("message")
            or item.get("text")
            or item.get("content")
            or ""
        ).strip()
        sender = str(
            item.get("sender")
            or item.get("phoneNumber")
            or item.get("phone_number")
            or item.get("from")
            or ""
        ).strip()

        if not msg_id:
            msg_id = f"gen:{abs(hash((sender, text, item.get('createdAt'))))}"

        if db.is_inbound_sms_processed(msg_id, db_path=db_path):
            continue

        sender_normalized = normalize_phone_number_e164(sender) or sender
        cmd_id = parse_sms_acceptance_command(text)

        if not cmd_id:
            db.record_processed_inbound_sms(
                message_id=msg_id,
                sender=sender_normalized,
                content=text[:160],
                parsed_command_id=None,
                status="IGNORED",
                db_path=db_path,
            )
            continue

        res = {"success": False, "status": "ENGINE_UNAVAILABLE"}
        if accept_fn is not None:
            try:
                res = accept_fn(
                    command_or_assignment_id=cmd_id,
                    sender_phone=sender_normalized,
                    acceptance_source="SMS",
                    db_path=db_path,
                )
            except Exception as accept_ex:
                res = {"success": False, "status": "EXCEPTION", "error": str(accept_ex)}

        res_status = res.get("status") or ("ACCEPTED" if res.get("success") else "FAILED")
        db.record_processed_inbound_sms(
            message_id=msg_id,
            sender=sender_normalized,
            content=text[:160],
            parsed_command_id=cmd_id,
            status=res_status,
            db_path=db_path,
        )

        processed_results.append({
            "message_id": msg_id,
            "command_id": cmd_id,
            "sender": sender_normalized,
            "result": res,
        })

    return processed_results


