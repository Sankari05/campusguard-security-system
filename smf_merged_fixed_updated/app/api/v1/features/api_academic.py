# =============================================================
# api_academic.py — NEW FILE (additive only)
# Follows the exact register_<feature>_routes(app, ...) pattern
# used by api_hod.py / api_extras.py / api_override.py.
# =============================================================
import logging

from fastapi import Depends, HTTPException
from pydantic import BaseModel

import database_academic as acad_db

log = logging.getLogger(__name__)


class AcademicRecordReq(BaseModel):
    student_id: str
    semester: int
    cgpa: float = None
    sgpa: float = None
    backlog_count: int = 0
    backlog_subjects: str = ""


def register_academic_routes(app, get_current_user, teacher_required):

    try:
        acad_db.init_academic_table()
    except Exception as exc:
        log.warning("academic table init skipped: %s", exc)

    @app.get("/api/academics/backlogs")
    def api_academics_backlogs(dept: str = None, user: dict = Depends(get_current_user)):
        """Students whose latest semester record has backlog_count > 0."""
        try:
            role = (user.get("role") or "").lower()
            eff_dept = dept
            if role not in ("admin",) and not dept:
                eff_dept = user.get("dept")
            return acad_db.get_backlogs(eff_dept)
        except Exception as exc:
            log.exception("backlogs fetch failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/academics/cgpa-summary")
    def api_academics_cgpa_summary(dept: str = None, user: dict = Depends(get_current_user)):
        try:
            role = (user.get("role") or "").lower()
            eff_dept = dept
            if role not in ("admin",) and not dept:
                eff_dept = user.get("dept")
            return acad_db.get_cgpa_summary(eff_dept)
        except Exception as exc:
            log.exception("cgpa summary failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/academics/all")
    def api_academics_all(dept: str = None, user: dict = Depends(get_current_user)):
        """Latest semester record for every student — backs the Academics page table."""
        try:
            role = (user.get("role") or "").lower()
            eff_dept = dept
            if role not in ("admin",) and not dept:
                eff_dept = user.get("dept")
            return acad_db.get_all_latest(eff_dept)
        except Exception as exc:
            log.exception("academics-all fetch failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/academics/{student_id}")
    def api_academics_one(student_id: str, user: dict = Depends(get_current_user)):
        try:
            return acad_db.get_for_student(student_id)
        except Exception as exc:
            log.exception("academics fetch (single) failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/academics")
    def api_academics_save(body: AcademicRecordReq, user: dict = Depends(teacher_required)):
        try:
            return acad_db.upsert_record(
                student_id=body.student_id, semester=body.semester,
                cgpa=body.cgpa, sgpa=body.sgpa,
                backlog_count=body.backlog_count, backlog_subjects=body.backlog_subjects,
                updated_by=user.get("username") or user.get("user_id") or "",
            )
        except Exception as exc:
            log.exception("academic record save failed")
            raise HTTPException(status_code=500, detail=str(exc))
