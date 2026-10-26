# =============================================================
# api_workload.py — NEW FILE (additive only)
# Follows the exact register_<feature>_routes(app, ...) pattern
# used by api_hod.py / api_extras.py / api_override.py.
# =============================================================
import logging

from fastapi import Depends, HTTPException
from pydantic import BaseModel

import database_workload as workload_db

log = logging.getLogger(__name__)


class WorkloadOverrideReq(BaseModel):
    lab_duty_hours: int = None
    admin_duty_hours: int = None


def register_workload_routes(app, get_current_user, admin_required):

    try:
        workload_db.init_workload_table()
    except Exception as exc:
        log.warning("workload table init skipped: %s", exc)

    @app.get("/api/faculty/workload")
    def api_faculty_workload(dept: str = None, user: dict = Depends(get_current_user)):
        """Weekly teaching-hour balance, auto-computed from faculty_timetable."""
        try:
            role = (user.get("role") or "").lower()
            eff_dept = dept
            if role not in ("admin",) and not dept:
                eff_dept = user.get("dept")
            return workload_db.get_all_workload(eff_dept)
        except Exception as exc:
            log.exception("workload fetch failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/faculty/workload/{fac_id}")
    def api_faculty_workload_one(fac_id: str, user: dict = Depends(get_current_user)):
        try:
            return workload_db.get_faculty_workload(fac_id)
        except Exception as exc:
            log.exception("workload fetch (single) failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.put("/api/faculty/workload/{fac_id}")
    def api_faculty_workload_update(
        fac_id: str, body: WorkloadOverrideReq, user: dict = Depends(admin_required)
    ):
        """Manual override for lab/admin duty hours only — admin only."""
        try:
            return workload_db.set_workload_override(
                fac_id, body.lab_duty_hours, body.admin_duty_hours
            )
        except Exception as exc:
            log.exception("workload override failed")
            raise HTTPException(status_code=500, detail=str(exc))
