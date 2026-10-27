# =============================================================
# api_gatepass.py — Student Gate Pass API Routes
#
# Module providing:
#   1. Student Gate Pass Application & Active OTP Retrieval
#   2. Faculty & HOD 2-Stage Approval Pipeline
#   3. Watchman Portal Integration API (CORS enabled, Port 5173 friendly)
# =============================================================
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field

from app.database import database_gatepass as gpdb
from app.core.auth_utils import get_current_user, teacher_required, admin_required, decode_token

log = logging.getLogger(__name__)

router = APIRouter(tags=["Gate Pass System"])


# ── Pydantic Request Schemas ─────────────────────────────────
class GatePassApplyReq(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)
    event_date: str = Field(..., min_length=1)
    out_time: str = Field(..., min_length=1)
    expected_in_time: str = Field(default="")
    pass_type: str = Field(default="Gate Pass")
    qr_payload: str = Field(default="")


class DecisionReq(BaseModel):
    remarks: str = Field(default="", max_length=500)


class VerifyOtpReq(BaseModel):
    otp: str = Field(..., min_length=1, max_length=16)


class MarkExitReq(BaseModel):
    pass_id: int
    guard_id: str = Field(default="Main Gate Guard")
    remarks: str = Field(default="")


class VoiceCommandReq(BaseModel):
    transcript: str = Field(..., min_length=1)
    guard_id: str = Field(default="Main Gate Guard")
    active_pass_id: int | None = Field(default=None)


class IncidentLogReq(BaseModel):
    description: str = Field(..., min_length=2)
    category: str = Field(default="General")
    student_id: str = Field(default="")
    severity: str = Field(default="Medium")
    guard_id: str = Field(default="Main Gate Guard")
    voice_transcript: str = Field(default="")


# ── Student Auth Dependency ──────────────────────────────────
def _get_student_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token provided")
    token = auth[7:].strip()
    try:
        user = decode_token(token)
        if user.get("role") != "student":
            raise HTTPException(status_code=403, detail="Student access required")
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


# ── Faculty Scope & Incharge Helpers ─────────────────────────
def _resolve_scope(user: dict) -> dict:
    role = (user.get("role") or "").lower()
    if role == "admin":
        return {"department": None, "year": None, "section": None}
    if role == "hod":
        dept = user.get("dept") or user.get("department") or ""
        return {"department": dept or None, "year": None, "section": None}
    fac_id = user.get("sub") or user.get("fac_id") or ""
    try:
        from app.database import database_faculty_requests as freq
        return freq.get_faculty_scope(fac_id)
    except Exception:
        return {"department": None, "year": None, "section": None}


def _is_class_incharge(user: dict) -> bool:
    role = (user.get("role") or "").lower()
    if role in ("admin", "hod"):
        return True
    fac_id = user.get("sub") or user.get("fac_id") or ""
    try:
        from app.database import database as db
        return bool(db.get_faculty_incharge_class(fac_id))
    except Exception:
        return True


# =============================================================
# 1. STUDENT GATE PASS ROUTES
# =============================================================
@router.post("/api/student/gatepass")
def student_apply_gatepass(payload: GatePassApplyReq, user: dict = Depends(_get_student_user)):
    """Student submits a gate pass request."""
    try:
        record = gpdb.apply_gatepass(
            student_id=user["sub"],
            reason=payload.reason,
            event_date=payload.event_date,
            out_time=payload.out_time,
            expected_in_time=payload.expected_in_time,
            pass_type=payload.pass_type,
            qr_payload=payload.qr_payload,
        )
        return {"success": True, "record": record}
    except Exception as e:
        log.exception("student_apply_gatepass failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/student/gatepass")
def student_list_gatepasses(user: dict = Depends(_get_student_user)):
    """List all previous and active gate passes for logged in student."""
    return {"requests": gpdb.list_student_gatepasses(user["sub"])}


@router.get("/api/student/gatepass/active")
def student_get_active_gatepass(user: dict = Depends(_get_student_user)):
    """Get active approved pass with OTP for the student."""
    active = gpdb.get_active_gatepass(user["sub"])
    return {"has_active": active is not None, "pass": active}


# =============================================================
# 2. FACULTY & HOD APPROVAL ROUTES
# =============================================================
@router.get("/api/faculty/requests/gatepass")
def list_faculty_gatepasses(status: str = None, user: dict = Depends(teacher_required)):
    """List gate pass requests. Faculty sees 'Pending', HOD sees 'Forwarded'."""
    role = (user.get("role") or "").lower()
    if role == "admin":
        return {"requests": []}

    effective_status = status
    if role == "hod" and status in ("Pending", None):
        effective_status = "Forwarded"
    elif role not in ("hod", "admin") and status is None:
        effective_status = "Pending"

    scope = _resolve_scope(user)
    requests = gpdb.list_faculty_gatepasses(scope, effective_status)
    return {"requests": requests}


@router.get("/api/faculty/requests/gatepass/{pass_id}")
def get_faculty_gatepass_detail(pass_id: int, user: dict = Depends(teacher_required)):
    """Get full details of a specific gate pass request."""
    rec = gpdb.get_gatepass_by_id(pass_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Gate pass not found")
    return rec


@router.post("/api/faculty/requests/gatepass/{pass_id}/approve")
def approve_gatepass(pass_id: int, payload: DecisionReq = DecisionReq(), user: dict = Depends(teacher_required)):
    """Class Incharge approves -> Forwarded. HOD approves -> Approved + OTP Generated!"""
    role = (user.get("role") or "").lower()
    if role == "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin is not permitted to decide gate passes. Gate pass workflow is handled strictly by Class Incharge and HOD.",
        )
    actor = user.get("sub") or user.get("name") or "Faculty"

    if role == "hod":
        rec = gpdb.hod_decide_gatepass(pass_id, "Approved", actor, payload.remarks)
        if not rec:
            raise HTTPException(
                status_code=409,
                detail="Request is not awaiting HOD approval (must be Forwarded by Class Incharge first).",
            )
        return {"success": True, "status": "Approved", "record": rec}
    else:
        rec = gpdb.faculty_decide_gatepass(pass_id, "Approved", actor, payload.remarks)
        if not rec:
            raise HTTPException(status_code=404, detail="Gate pass not found or not in Pending state.")
        return {"success": True, "status": "Forwarded", "record": rec}


@router.post("/api/faculty/requests/gatepass/{pass_id}/reject")
def reject_gatepass(pass_id: int, payload: DecisionReq = DecisionReq(), user: dict = Depends(teacher_required)):
    """Reject gate pass request at either Faculty or HOD level."""
    role = (user.get("role") or "").lower()
    if role == "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin is not permitted to decide gate passes. Gate pass workflow is handled strictly by Class Incharge and HOD.",
        )
    actor = user.get("sub") or user.get("name") or "Faculty"

    if role == "hod":
        rec = gpdb.hod_decide_gatepass(pass_id, "Rejected", actor, payload.remarks)
    else:
        rec = gpdb.faculty_decide_gatepass(pass_id, "Rejected", actor, payload.remarks)

    if not rec:
        raise HTTPException(status_code=404, detail="Gate pass not found or already decided.")
    return {"success": True, "status": "Rejected", "record": rec}


# =============================================================
# 3. WATCHMAN PROJECT INTEGRATION ROUTES
# =============================================================
@router.post("/api/v1/gatepass/verify")
def watchman_verify_otp(payload: VerifyOtpReq):
    """
    Called by Watchman Portal (Port 5173 / Main Gate App).
    Takes entered OTP -> verifies approval status -> returns student photo & profile.
    """
    result = gpdb.verify_gatepass_otp(payload.otp)
    return result


@router.post("/api/v1/gatepass/mark-exit")
def watchman_mark_exit(payload: MarkExitReq):
    """Watchman confirms student exit. Marks gate pass as used."""
    rec = gpdb.mark_gatepass_exit(payload.pass_id, payload.guard_id, payload.remarks)
    return {
        "success": True,
        "message": "Student exit recorded successfully.",
        "record": rec,
    }


@router.get("/api/v1/gatepass/recent-exits")
def watchman_recent_exits():
    """Recent exit logs for watchman portal table."""
    return {"exits": gpdb.list_recent_gatepass_exits(limit=25)}


@router.post("/api/v1/gatepass/voice-command")
def watchman_voice_command(payload: VoiceCommandReq):
    """
    AI Natural Language & Voice Gateway for Watchman.
    Processes spoken transcript, recognizes intent (OTP verify, exit confirm, incident report),
    executes actions, and returns both structured payload and synthesized voice feedback string.
    """
    res = gpdb.process_voice_command(
        transcript=payload.transcript,
        guard_id=payload.guard_id,
        active_pass_id=payload.active_pass_id,
    )
    return res


@router.post("/api/v1/gatepass/incidents")
def log_gate_incident_api(payload: IncidentLogReq):
    """Log an incident or spoken situation at the gate."""
    rec = gpdb.log_gate_incident(
        guard_id=payload.guard_id,
        description=payload.description,
        category=payload.category,
        student_id=payload.student_id,
        severity=payload.severity,
        voice_transcript=payload.voice_transcript,
    )
    return {"success": True, "record": rec}


@router.get("/api/v1/gatepass/incidents")
def get_gate_incidents():
    """List recent gate incidents and voice situation logs."""
    return {"incidents": gpdb.list_gate_incidents(limit=30)}
