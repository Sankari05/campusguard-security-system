# =============================================================
# routers/students.py
# Students Router — Complete Student Profile & Lifecycle Management
# =============================================================
import re
import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel

from app.core import config
from app.database import database as db
from app.core.auth_utils import get_current_user, admin_required, teacher_required

log = logging.getLogger(__name__)

router = APIRouter(tags=["Students"])


# ── Schemas ───────────────────────────────────────────────────
class AddStudentReq(BaseModel):
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    register_number: str
    roll_number: str = ""
    gender: str = ""
    date_of_birth: str = ""
    department: str
    course: str = ""
    year: str = "1"
    section: str = "A"
    student_email: str = ""
    parent_email: str = ""
    student_mobile: str = ""
    parent_mobile: str = ""
    twin_of: Optional[str] = None


class UpdateStudentReq(BaseModel):
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    department: Optional[str] = None
    course: Optional[str] = None
    year: Optional[str] = None
    section: Optional[str] = None
    student_email: Optional[str] = None
    parent_email: Optional[str] = None
    student_mobile: Optional[str] = None
    parent_mobile: Optional[str] = None
    active: Optional[int] = None
    status: Optional[str] = None
    twin_of: Optional[str] = None


# ── Validation Helpers ────────────────────────────────────────
_NAME_RE = re.compile(r'^[A-Za-z]+( [A-Za-z]+)*$')

def _validate_name_field(val: str, label: str) -> str:
    v = (val or "").strip()
    if not v:
        raise HTTPException(status_code=422, detail=f"{label} is required.")
    if len(v) < 2 or len(v) > 50:
        raise HTTPException(status_code=422, detail=f"{label} must be between 2 and 50 characters.")
    if not _NAME_RE.match(v):
        raise HTTPException(status_code=422, detail=f"{label} must contain letters and single spaces only.")
    return v


# ── Routes ────────────────────────────────────────────────────
@router.get("/api/students")
def api_list_students(_: dict = Depends(get_current_user)):
    """Fetch all students ordered by register number."""
    rows = db.get_all_students()
    return [dict(r) for r in rows]


@router.get("/api/students/check/{register_number}")
def api_check_student(register_number: str, _: dict = Depends(get_current_user)):
    """Check if a student with this register number already exists."""
    sid = f"STU_{register_number.upper()}"
    s = db.get_student(sid)
    if s:
        return {"exists": True, "student": dict(s)}
    return {"exists": False}


@router.get("/api/students/departments")
def api_students_departments(current_user: dict = Depends(get_current_user)):
    """Distinct department codes enrolled in database."""
    role = (current_user.get("role") or "").lower()
    own_dept = (current_user.get("dept") or "").upper()
    try:
        if role == "admin":
            depts = db.get_distinct_departments()
        else:
            depts = [own_dept] if own_dept else []
        return {"departments": depts}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


from app.services.student_service import StudentService
_student_service = StudentService()


@router.get("/api/students/stats")
def api_students_stats(current_user: dict = Depends(get_current_user)):
    """Aggregate statistics for Student Management portal."""
    role = (current_user.get("role") or "").lower()
    dept = (current_user.get("dept") or "").upper()
    try:
        stats = _student_service.get_students_stats(role=role, dept=dept)
        return stats.model_dump() if hasattr(stats, "model_dump") else stats.dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/students/list")
def api_students_list(
    year: str = None,
    section: str = None,
    dept: str = None,
    semester: str = None,
    search: str = None,
    status: str = None,
    page: int = 1,
    per_page: int = 6,
    _: dict = Depends(get_current_user),
):
    """Paginated, filterable student list for Student Management."""
    role = (_.get("role") or "").lower()
    own_dept = (_.get("dept") or "").upper()
    if role not in ("admin", "hod", "faculty"):
        raise HTTPException(status_code=403, detail="Access denied: admin, hod, or faculty only.")
    try:
        return _student_service.get_students_list(
            role=role,
            own_dept=own_dept,
            year=year,
            section=section,
            dept=dept,
            semester=semester,
            search=search,
            status=status,
            page=page,
            per_page=per_page,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/api/students/{student_id}/deactivate")
def api_deactivate_student(student_id: str, user: dict = Depends(admin_required)):
    """Deactivate student and mark inactive in database."""
    sid = student_id.strip().upper()
    try:
        with db.db(write=True) as conn:
            row = conn.execute("SELECT student_id, name FROM students WHERE student_id = ?", (sid,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Student '{sid}' not found")
            conn.execute("UPDATE students SET active = 0, status = 'Inactive' WHERE student_id = ?", (sid,))
        db.log_audit(user.get("sub", "admin"), "deactivate_student", sid, row["name"])
        return {"ok": True, "student_id": sid, "status": "Inactive"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/students/{student_id}/reactivate")
def api_reactivate_student(student_id: str, user: dict = Depends(admin_required)):
    """Reactivate previously deactivated student."""
    sid = student_id.strip().upper()
    try:
        with db.db(write=True) as conn:
            row = conn.execute("SELECT student_id, name FROM students WHERE student_id = ?", (sid,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Student '{sid}' not found")
            conn.execute("UPDATE students SET active = 1, status = 'Active' WHERE student_id = ?", (sid,))
        db.log_audit(user.get("sub", "admin"), "reactivate_student", sid, row["name"])
        return {"ok": True, "student_id": sid, "status": "Active"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/students/{student_id}")
def api_get_student(student_id: str, _: dict = Depends(get_current_user)):
    """Retrieve full student record by ID."""
    s = db.get_student(student_id.strip().upper())
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    return dict(s)


@router.post("/api/students")
def api_add_student(req: AddStudentReq, request: Request, user: dict = Depends(admin_required)):
    """Add and register a new student record."""
    if req.first_name:
        req.first_name = _validate_name_field(req.first_name, "First Name")
    if req.last_name:
        req.last_name = _validate_name_field(req.last_name, "Last Name")

    full_name = req.name or f"{req.first_name} {req.last_name}".strip()
    if not full_name:
        raise HTTPException(status_code=422, detail="Name or First/Last name is required")

    sid = f"STU_{req.register_number.upper()}"
    ok = db.add_student(
        student_id=sid,
        name=full_name,
        register_number=req.register_number,
        roll_number=req.roll_number.lower(),
        first_name=req.first_name,
        last_name=req.last_name,
        gender=req.gender,
        date_of_birth=req.date_of_birth,
        department=req.department,
        course=req.course or req.department,
        year=req.year,
        section=req.section,
        student_email=req.student_email,
        parent_email=req.parent_email,
        student_mobile=req.student_mobile,
        parent_mobile=req.parent_mobile,
        status="Active",
        twin_of=req.twin_of,
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to add student to database.")

    db.log_audit(user.get("sub", "admin"), "add_student", sid, full_name, request.client.host if request.client else "?")
    return {"ok": True, "student_id": sid, "name": full_name}


@router.put("/api/students/{student_id}")
def api_update_student(student_id: str, req: UpdateStudentReq, user: dict = Depends(admin_required)):
    """Update student record fields."""
    sid = student_id.strip().upper()
    existing = db.get_student(sid)
    if not existing:
        raise HTTPException(status_code=404, detail="Student not found")

    upd_dict = {k: v for k, v in req.dict().items() if v is not None}
    if not upd_dict:
        return {"ok": True, "message": "No fields to update."}

    fields = ", ".join(f"{k} = ?" for k in upd_dict.keys())
    values = list(upd_dict.values()) + [sid]

    try:
        with db.db(write=True) as conn:
            conn.execute(f"UPDATE students SET {fields} WHERE student_id = ?", values)
        db.log_audit(user.get("sub", "admin"), "update_student", sid, str(list(upd_dict.keys())))
        return {"ok": True, "student_id": sid, "updated": list(upd_dict.keys())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/students/{student_id}")
def api_delete_student(student_id: str, user: dict = Depends(admin_required)):
    """Delete student and corresponding biometric samples."""
    sid = student_id.strip().upper()
    existing = db.get_student(sid)
    if not existing:
        raise HTTPException(status_code=404, detail="Student not found")

    try:
        db.delete_student_data(sid)
        db.log_audit(user.get("sub", "admin"), "delete_student", sid, existing.get("name", ""))
        return {"ok": True, "deleted": sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/students/{student_id}/attendance-trend")
def api_student_attendance_trend(student_id: str, months: int = Query(6, ge=1, le=12), _: dict = Depends(get_current_user)):
    """Compute monthly attendance percentages over the past N months."""
    sid = student_id.strip().upper()
    try:
        today = datetime.now()
        months_out = []
        for i in range(months - 1, -1, -1):
            m_date = today - timedelta(days=i * 30)
            months_out.append(m_date)

        month_labels = [m.strftime("%b") for m in months_out]
        cutoff = (today - timedelta(days=months * 30)).strftime("%Y-%m-%d")

        with db.db(write=False) as conn:
            rows = conn.execute(
                "SELECT date, status FROM student_attendance WHERE student_id = ? AND date >= ?",
                (sid, cutoff)
            ).fetchall()

        by_month = {m.strftime("%Y-%m"): {"present": 0, "total": 0} for m in months_out}
        for r in rows:
            m_key = str(r["date"])[:7]
            if m_key in by_month:
                by_month[m_key]["total"] += 1
                if r["status"] == "Present":
                    by_month[m_key]["present"] += 1

        series = []
        for m in months_out:
            k = m.strftime("%Y-%m")
            entry = by_month.get(k, {"present": 0, "total": 0})
            pct = round((entry["present"] / entry["total"]) * 100, 1) if entry["total"] > 0 else 0.0
            series.append(pct)

        return {"labels": month_labels, "data": series, "student_id": sid}
    except Exception as e:
        log.error("[STUDENTS] Attendance trend error: %s", e)
        return {"labels": [], "data": [], "student_id": sid}
