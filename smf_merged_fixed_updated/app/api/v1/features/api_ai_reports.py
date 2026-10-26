# =============================================================
# api_ai_reports.py — NEW FILE (additive, follows the exact same
# register_xxx_routes(app, ...) pattern as api_hod.py / api_extras.py
# / api_override.py so it plugs into create_app() with ONE
# try/except block and touches nothing else.
# =============================================================
import logging
from datetime import datetime

from fastapi import Depends, HTTPException

import database as db
from ai_summary import generate_ai_summary

log = logging.getLogger(__name__)


def register_ai_report_routes(app, get_current_user):

    @app.get("/api/reports/ai-summary")
    def api_reports_ai_summary(
        days: int = 180,
        dept: str = None,
        threshold: float = 75.0,
        current_user: dict = Depends(get_current_user),
    ):
        """
        Natural-language summary of attendance health for the Reports page.
        Reuses existing db helper functions (get_low_attendance_students,
        get_attendance_summary / get_attendance_summary_by_dept) — does
        NOT duplicate any SQL already in api.py's /api/reports/analytics.

        Access control: Admin/HOD get the full/department picture. Every
        other role (faculty/teacher/classincharge) only sees insight for
        the single class they are the registered Class In-Charge of — they
        can no longer pass a different `dept` to peek at other classes.
        Faculty who are not a class in-charge get a neutral "no class
        assigned" message instead of department-wide data.
        """
        try:
            role = (current_user.get("role") or "").lower()
            sec_lock = None
            year_lock = None
            if role not in ("admin", "hod"):
                fac_id = current_user.get("sub") or current_user.get("username") or ""
                cls = db.get_faculty_incharge_class(fac_id)
                if cls:
                    eff_dept = cls["dept"]
                    sec_lock = cls["section"]
                    year_lock = str(cls["year"])
                else:
                    return {
                        "summary": "You are not assigned as a Class In-Charge, so there is no class for you to view a report for.",
                        "stats": {},
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                    }
            else:
                eff_dept = (dept or "").upper()

            low_students = db.get_low_attendance_students(threshold, days)
            if eff_dept:
                low_students = [
                    s for s in low_students
                    if (s.get("department") or "").upper() == eff_dept
                ]
            if sec_lock:
                low_students = [
                    s for s in low_students
                    if (s.get("section") or "").upper() == sec_lock
                    and str(s.get("year") or "") == year_lock
                ]

            if eff_dept:
                summary_rows = db.get_attendance_summary_by_dept(eff_dept, days=min(days, 30))
            else:
                summary_rows = db.get_attendance_summary(days=min(days, 30))
            if sec_lock:
                summary_rows = [
                    r for r in summary_rows
                    if ((r.get("section") if isinstance(r, dict) else r["section"]) or "").upper() == sec_lock
                ]

            # ── Build lightweight stats dict for the summary generator ──
            total_students = len(set(s["student_id"] for s in low_students)) \
                if low_students else 0
            # total_students above only counts low-attendance ones; get a
            # true total via dashboard stats helper (role-aware, existing fn)
            try:
                dash = db.get_dashboard_stats_by_role(
                    "admin" if not eff_dept else "hod", dept=eff_dept)
                total_students = dash.get("total_students", total_students)
            except Exception:
                pass

            critical = [s for s in low_students if (s.get("pct") or 0) < 60]
            warning  = [s for s in low_students if 60 <= (s.get("pct") or 0) < 75]

            # average attendance from the recent summary window
            pcts = []
            for r in summary_rows:
                pc = r.get("present_count", 0) if isinstance(r, dict) else r["present_count"]
                td = (r.get("total_days", 1) if isinstance(r, dict) else r["total_days"]) or 1
                pcts.append(pc / td * 100)
            avg_attendance = round(sum(pcts) / len(pcts), 1) if pcts else 0.0

            # weakest section among the low-attendance list
            sec_map = {}
            for s in low_students:
                key = s.get("section") or "—"
                sec_map.setdefault(key, []).append(s.get("pct") or 0)
            lowest_section = None
            if sec_map:
                worst_key = min(sec_map, key=lambda k: sum(sec_map[k]) / len(sec_map[k]))
                lowest_section = {
                    "section": worst_key,
                    "avg_pct": round(sum(sec_map[worst_key]) / len(sec_map[worst_key]), 1),
                }

            # weakest year among the low-attendance list
            yr_map = {}
            for s in low_students:
                key = s.get("year") or "—"
                yr_map.setdefault(key, []).append(s.get("pct") or 0)
            lowest_year = None
            if yr_map:
                worst_yr = min(yr_map, key=lambda k: sum(yr_map[k]) / len(yr_map[k]))
                lowest_year = {
                    "year": worst_yr,
                    "avg_pct": round(sum(yr_map[worst_yr]) / len(yr_map[worst_yr]), 1),
                }

            # simple trend: compare first half vs second half of summary window
            trend_direction = "flat"
            if len(pcts) >= 4:
                mid = len(pcts) // 2
                first_avg, second_avg = sum(pcts[:mid]) / mid, sum(pcts[mid:]) / (len(pcts) - mid)
                if second_avg - first_avg > 2:
                    trend_direction = "up"
                elif first_avg - second_avg > 2:
                    trend_direction = "down"

            stats = {
                "dept": eff_dept or "the college",
                "total_students": total_students,
                "avg_attendance": avg_attendance,
                "critical_count": len(critical),
                "warning_count": len(warning),
                "below_75_count": len(low_students),
                "lowest_section": lowest_section,
                "lowest_year": lowest_year,
                "trend_direction": trend_direction,
            }

            summary_text = generate_ai_summary(stats)

            return {
                "summary": summary_text,
                "stats": stats,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }

        except Exception as exc:
            log.exception("AI summary generation failed")
            raise HTTPException(status_code=500, detail=str(exc))
