# =============================================================
# api_clash.py — NEW FILE (additive only)
# Read-only pre-check endpoint so the frontend can warn the user
# BEFORE submitting a timetable entry, without blocking the save.
# =============================================================
import logging

from fastapi import Depends, HTTPException

from database import db
from timetable_clash import check_clash

log = logging.getLogger(__name__)


def register_clash_routes(app, get_current_user):

    @app.get("/api/timetable/clash-check")
    def api_clash_check(
        faculty_id: str = None,
        section: str = None,
        dept: str = None,
        year: int = None,
        semester: int = None,
        day_of_week: str = None,
        period_no: int = None,
        room: str = None,
        _: dict = Depends(get_current_user),
    ):
        try:
            with db() as conn:
                conflicts = check_clash(
                    conn,
                    faculty_id=faculty_id,
                    section=section,
                    dept=dept,
                    year=year,
                    semester=semester,
                    day=day_of_week,
                    period=period_no,
                    room=room,
                )
            return {"has_conflict": bool(conflicts), "conflicts": conflicts}
        except Exception as exc:
            log.exception("clash-check failed")
            raise HTTPException(status_code=500, detail=str(exc))
