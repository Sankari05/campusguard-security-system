"""
routers/session.py
==================
Camera Session Management & Live MJPEG Video Stream Router.
Endpoints:
  POST /api/session/start   → Start background camera recognition thread
  POST /api/session/stop    → Stop background camera thread
  GET  /api/session/status  → Live session stats & marked student count
  GET  /video_feed          → MJPEG video streaming for frontend <img>
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.database import database as db
from app.services.vision import attendance_session as _sess
from app.core.auth_utils import get_current_user, teacher_required, uname as _uname

log = logging.getLogger(__name__)
router = APIRouter(tags=["Camera Session"])


class StartSessionReq(BaseModel):
    period: str = "Period_1"


@router.get("/video_feed")
def video_feed():
    """Live MJPEG video stream with bounding boxes and confidence overlays."""
    return StreamingResponse(
        _sess.generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma":        "no-cache",
            "Expires":       "0",
        }
    )


@router.post("/api/session/start")
def start_session(req: StartSessionReq, user: dict = Depends(teacher_required)):
    """Start face recognition background thread for a given period."""
    state = _sess.get_status()
    if state.get("running"):
        return {"ok": False, "error": f"Session already running for {state.get('period')}"}

    period = req.period or db.get_current_period() or "Manual_Session"
    result = _sess.start_session(period)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to start camera session"))

    db.log_audit(_uname(user), "api_session_start", period)
    return {"ok": True, "period": period}


@router.post("/api/session/stop")
def stop_session(user: dict = Depends(teacher_required)):
    """Stop running camera recognition session."""
    period = _sess.get_status().get("period", "")
    _sess.stop_session()
    db.log_audit(_uname(user), "api_session_stop", period)
    return {"ok": True}


@router.get("/api/session/status")
def session_status(_: dict = Depends(get_current_user)):
    """Poll live session state, marked count, and active period info."""
    state = _sess.get_status()
    period = state.get("period") or ""
    today_records = db.get_today_attendance(period) if period else []
    total_students = len(db.get_all_students())

    return {
        "running":        state.get("running", False),
        "period":         period,
        "started_at":     state.get("started_at"),
        "marked_count":   len(today_records),
        "total_students": total_students,
        "absent_count":   max(0, total_students - len(today_records)),
        "error":          state.get("error") or "",
    }
