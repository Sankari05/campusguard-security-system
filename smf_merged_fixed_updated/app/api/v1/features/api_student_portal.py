# =============================================================
# api_student_portal.py — Student Portal routes
#
#   POST /student/login            register_number + date_of_birth ONLY
#   GET  /student/profile          view own profile
#   PUT  /student/profile          edit own profile (whitelisted fields)
#   POST /student/profile/photo    upload avatar
#
# Mounted with prefix "/student" in main.py / api.py create_app().
#
# LOGIN POLICY (do not change without product sign-off):
#   Students authenticate using ONLY their Register Number + Date of
#   Birth, every time. There is no student password. Students have no
#   way to set, change, or reset a password or their login ID
#   (register_number) from this portal — register_number and
#   date_of_birth are institution-controlled, read-only credentials.
#   This applies ONLY to the student portal ("/student/*") and does
#   NOT affect the separate EduTrack Pro login system used by
#   faculty/HOD/admin (api.py "/auth/*", auth_routes.py).
# =============================================================
import os
import logging
import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from pydantic import BaseModel, Field

import config
import student_portal_db as spdb
from auth_utils import create_access_token, decode_token

log = logging.getLogger(__name__)
router = APIRouter()

AVATAR_DIR = os.path.join(config.STATIC_DIR, "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)
ALLOWED_AVATAR_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB


# ── Schemas ──────────────────────────────────────────────────
class StudentLoginReq(BaseModel):
    """
    Students log in with ONLY their Register Number + Date of Birth —
    every time, not just on first login. There is no student password.
    """
    register_number: str = Field(..., min_length=1, max_length=64)
    date_of_birth: str = Field(
        ..., min_length=1,
        description="Date of birth as on record, format YYYY-MM-DD.",
    )


class ProfileUpdateReq(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    student_email: str | None = None
    student_mobile: str | None = None
    parent_email: str | None = None
    parent_mobile: str | None = None


class LeaveApplyReq(BaseModel):
    from_date: str = Field(..., min_length=1)
    to_date: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1, max_length=500)


class OdApplyReq(BaseModel):
    event_name: str = Field(..., min_length=1, max_length=200)
    event_date: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1, max_length=500)


# ── Auth dependency (student-only) ──────────────────────────
def _get_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token provided")
    return decode_token(auth[7:])


def student_required(user: dict = Depends(_get_user)) -> dict:
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    return user


# ── Routes ───────────────────────────────────────────────────
@router.post("/login")
def student_login(req: StudentLoginReq):
    """
    Student login — Register Number + Date of Birth, ALWAYS.

    There is no student password and no separate "first login" flow:
    every login (first time and every time after) is verified the same
    way, directly against the institution's record of the student's
    date of birth. Students cannot set/change a password or their
    register number from the portal.
    """
    student = spdb.verify_register_and_dob(req.register_number, req.date_of_birth)
    if not student:
        raise HTTPException(status_code=401, detail="Invalid register number or date of birth")

    token = create_access_token({
        "sub": student["student_id"],
        "role": "student",
        "register_number": student["register_number"],
        "name": student["name"],
    })
    spdb.touch_last_login(student["student_id"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "student": {
            "student_id": student["student_id"],
            "name": student["name"],
            "register_number": student["register_number"],
            "department": student.get("department"),
        },
    }


@router.get("/profile")
def get_my_profile(user: dict = Depends(student_required)):
    profile = spdb.get_profile(user["sub"])
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    return profile


@router.get("/dashboard-summary")
def get_dashboard_summary(user: dict = Depends(student_required)):
    """
    Aggregated stats for the Dashboard Home panel:
      - attendance_percent, current_semester  (pulled from existing tables)
      - pending_leave_requests, upcoming_events, assignment_deadlines
        (placeholder 0/empty until those modules are added)
    """
    summary = spdb.get_dashboard_summary(user["sub"])
    if not summary:
        raise HTTPException(status_code=404, detail="Student not found")
    return summary


@router.get("/attendance")
def get_attendance(user: dict = Depends(student_required)):
    """Overall + subject-wise attendance % for the logged-in student,
    computed from the existing student_attendance table."""
    return spdb.get_attendance_summary(user["sub"])


@router.get("/attendance/detail")
def get_attendance_detail(user: dict = Depends(student_required)):
    """Date-wise, period-wise full attendance log for the logged-in student.
    Read-only view over the existing student_attendance table — no new
    table or column is touched."""
    return spdb.get_attendance_detail(user["sub"])


@router.get("/marks")
def get_marks(user: dict = Depends(student_required)):
    """CIA 1 / CIA 2 / CIA 3 / Model Exam + Total per subject for the
    logged-in student (student_internal_marks table)."""
    return spdb.get_marks_summary(user["sub"])


@router.get("/results")
def get_results(user: dict = Depends(student_required)):
    """Semester-wise SGPA/CGPA + backlog info for the logged-in student,
    reusing the existing student_academics table (database_academic.py)."""
    return spdb.get_results_summary(user["sub"])


@router.get("/timetable")
def get_timetable(user: dict = Depends(student_required)):
    """Weekly timetable for the logged-in student, wrapping the existing
    database_extras.get_student_timetable() used by faculty/HOD features."""
    return spdb.get_timetable_summary(user["sub"])


@router.post("/leave")
def apply_leave(payload: LeaveApplyReq, user: dict = Depends(student_required)):
    """Apply for leave (date range + reason). Status starts as Pending.
    Rejects past dates / invalid ranges with a 400."""
    try:
        record = spdb.apply_leave(
            user["sub"], payload.from_date, payload.to_date, payload.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return record


@router.get("/leave")
def get_leave_history(user: dict = Depends(student_required)):
    """Leave history for the logged-in student, most recent first."""
    return {"requests": spdb.get_leave_history(user["sub"])}


@router.post("/od")
def apply_od(payload: OdApplyReq, user: dict = Depends(student_required)):
    """Apply for OD (event name/date + reason). Status starts as Pending.
    Reuses the existing od_requests table (Phase 1 Faculty Request
    Management) so it appears directly in the Faculty approval queue."""
    try:
        record = spdb.apply_od(
            user["sub"], payload.event_name, payload.event_date, payload.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return record


@router.get("/od")
def get_od_history(user: dict = Depends(student_required)):
    """OD history for the logged-in student, most recent first."""
    return {"requests": spdb.get_od_history(user["sub"])}


@router.get("/requests/tracker")
def get_request_tracker(user: dict = Depends(student_required)):
    """
    Prompt 5 — Student Request Tracker (Step 7 update).

    Combines student_leave_requests + od_requests for the logged-in
    student into one merged, chronologically-sorted timeline. Each
    request carries a `stages` list so the frontend can render a
    stepper/timeline UI without re-deriving the logic:
      - Leave requests (single-stage, Faculty-only): 3 stages —
        Submitted → Reviewed → Approved/Rejected.
      - OD requests (two-stage Faculty → HOD pipeline): 4 stages —
        Submitted → Faculty Review → HOD Review → Approved/Rejected.
    """
    return {"requests": spdb.get_request_tracker(user["sub"])}


@router.get("/notifications")
def get_notifications(user: dict = Depends(student_required)):
    """Notification list for the logged-in student (most recent first),
    plus an unread_count for the bell badge. Populated automatically
    when a faculty/HOD approves or rejects this student's leave/OD
    requests (see database_faculty_requests.py)."""
    return {
        "notifications": spdb.get_notifications(user["sub"]),
        "unread_count": spdb.get_unread_notification_count(user["sub"]),
    }


@router.post("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int, user: dict = Depends(student_required)):
    """Mark a single notification as read. Scoped to the logged-in
    student — cannot mark another student's notification."""
    record = spdb.mark_notification_read(user["sub"], notif_id)
    if not record:
        raise HTTPException(status_code=404, detail="Notification not found")
    return record


@router.put("/profile")
def update_my_profile(payload: ProfileUpdateReq, user: dict = Depends(student_required)):
    updated = spdb.update_profile(user["sub"], payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Profile updated successfully.", "profile": updated}


@router.post("/profile/photo")
async def upload_avatar(
    file: UploadFile = File(...),
    user: dict = Depends(student_required),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_AVATAR_EXT:
        raise HTTPException(status_code=400, detail="Only jpg/jpeg/png/webp images are allowed")

    contents = await file.read()
    if len(contents) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Image must be under 5 MB")

    student_id = user["sub"]
    filename = f"{student_id}_{int(datetime.now().timestamp())}{ext}"
    dest_path = os.path.join(AVATAR_DIR, filename)
    with open(dest_path, "wb") as f:
        f.write(contents)

    rel_path = f"/static/avatars/{filename}"
    spdb.update_avatar(student_id, rel_path)
    return {"message": "Profile photo updated.", "avatar_path": rel_path}
