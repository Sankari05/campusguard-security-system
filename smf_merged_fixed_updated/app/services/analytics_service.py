"""
app/services/analytics_service.py
==================================
Enterprise Analytics & Attendance Reporting Service.
Extracts heavy SQL queries and aggregate calculations from api.py into a clean service.
"""

import re
import math
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import database as db

log = logging.getLogger(__name__)


class AnalyticsService:
    """Business logic for attendance trends, department/year distribution, and KPI analytics."""

    _ROMAN_MAP = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}

    @classmethod
    def year_num(cls, y: Optional[str]) -> Optional[int]:
        """Normalize Roman/string year into plain integer (1 to 4)."""
        if y is None:
            return None
        y_str = str(y).strip().upper()
        if not y_str:
            return None
        if y_str in cls._ROMAN_MAP:
            return cls._ROMAN_MAP[y_str]
        m = re.search(r"\d+", y_str)
        return int(m.group()) if m else None

    @classmethod
    def canonical_year_label(cls, y_raw: Any) -> str:
        """Return canonical label ('1st Year', '2nd Year', '3rd Year', '4th Year')."""
        n = cls.year_num(y_raw)
        if n == 1:
            return "1st Year"
        elif n == 2:
            return "2nd Year"
        elif n == 3:
            return "3rd Year"
        elif n == 4:
            return "4th Year"
        return (str(y_raw) if y_raw else "—").strip()

    def get_reports_analytics(
        self,
        current_user: Dict[str, Any],
        days: int = 180,
        year: Optional[str] = None,
        section: Optional[str] = None,
        dept: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate full analytics payload for Reports & Analytics dashboard.
        Handles class incharge locking and role-based filtering.
        """
        role = (current_user.get("role") or "").lower()
        no_incharge_class = False

        if role not in ("admin", "hod"):
            fac_id = current_user.get("sub") or current_user.get("username") or ""
            cls = db.get_faculty_incharge_class(fac_id)
            if cls:
                dept, year, section = cls["dept"], str(cls["year"]), cls["section"]
            else:
                no_incharge_class = True

        if no_incharge_class:
            return {
                "summary": {
                    "total_students": 0, "avg_attendance": 0.0,
                    "below_75_count": 0, "above_75_count": 0,
                    "warning_count": 0, "critical_count": 0, "days": days,
                },
                "year_wise": [], "section_wise": [], "trend": [],
                "below75_students": [],
                "insights": [
                    "You are not assigned as a Class In-Charge, so there is no class for you to view reports for."
                ],
            }

        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        with db.db() as conn:
            def _q(sql, params=()):
                try:
                    return conn.execute(sql, params).fetchall()
                except Exception:
                    return []

            def _pct(present, total):
                if not total:
                    return 0.0
                return round(present / total * 100, 1)

            dept_filter_sa = ""
            dept_filter_s = ""
            dept_params_sa = []
            dept_params_s = []
            if dept:
                dept_filter_sa = "AND UPPER(COALESCE(sa.department, s.department, '')) = ?"
                dept_filter_s = "AND UPPER(COALESCE(s.department,'')) = ?"
                dept_params_sa = [dept.upper()]
                dept_params_s = [dept.upper()]

            sec_filter_sa = "AND UPPER(COALESCE(NULLIF(sa.section,''), s.section, '')) = ?" if section else ""
            sec_val_sa = [section.upper()] if section else []

            # Actual school days in window
            actual_days_q = _q(
                "SELECT COUNT(DISTINCT date) FROM student_attendance "
                "WHERE date >= ? AND UPPER(status)='PRESENT'", (cutoff,)
            )
            actual_days = max(1, (actual_days_q[0][0] if actual_days_q and actual_days_q[0][0] else days))

            # Per-student summary
            sum_sql = f"""
                SELECT s.student_id,
                       COALESCE(s.name, sa.name, '') AS name,
                       COALESCE(s.roll_number, '')   AS roll_number,
                       COALESCE(NULLIF(sa.year,''), s.year, '') AS year,
                       COALESCE(NULLIF(sa.section,''), s.section, '') AS section,
                       COALESCE(NULLIF(sa.department,''), s.department, '') AS department,
                       COUNT(DISTINCT CASE WHEN UPPER(sa.status)='PRESENT' THEN sa.date END) AS present_count,
                       {actual_days} AS total_days
                FROM students s
                LEFT JOIN student_attendance sa
                    ON s.student_id = sa.student_id AND sa.date >= ?
                WHERE s.active=1
                {dept_filter_s}
                {sec_filter_sa}
                GROUP BY s.student_id
            """
            sum_rows = _q(sum_sql, [cutoff] + dept_params_s + sec_val_sa)
            target_year_num = self.year_num(year) if year else None

            students_data = []
            for r in sum_rows:
                sid, name, roll, yr, sec, dep, pc, td = r
                if target_year_num is not None and self.year_num(yr) != target_year_num:
                    continue
                pct = _pct(pc, td)
                status = "good" if pct >= 75 else ("warning" if pct >= 60 else "critical")
                canonical_yr = self.canonical_year_label(yr)
                students_data.append({
                    "student_id": sid, "name": name, "roll_number": roll,
                    "year": canonical_yr, "section": sec or "—", "department": dep,
                    "present_count": pc, "total_days": td,
                    "pct": pct, "status": status,
                })

            total_students = len(students_data)
            below75 = [s for s in students_data if s["pct"] < 75]
            above75 = [s for s in students_data if s["pct"] >= 75]
            avg_att = round(sum(s["pct"] for s in students_data) / total_students, 1) if total_students else 0.0

            warning_count = sum(1 for s in students_data if 60 <= s["pct"] < 75)
            critical_count = sum(1 for s in students_data if s["pct"] < 60)

            # Year-wise averages
            year_map: Dict[str, List] = {}
            for s in students_data:
                yr = s["year"]
                year_map.setdefault(yr, []).append(s["pct"])
            year_wise = [
                {"year": yr, "avg_pct": round(sum(v)/len(v), 1), "count": len(v)}
                for yr, v in sorted(year_map.items())
            ]

            # Section-wise averages
            sec_map: Dict[str, List] = {}
            for s in students_data:
                sec = (s["section"] or "—").strip()
                dep = (s["department"] or "").strip().upper()
                key = f"{dep}-{sec}" if dep and sec != "—" else sec
                sec_map.setdefault(key, []).append(s["pct"])
            section_wise = [
                {"section": sec, "avg_pct": round(sum(v)/len(v), 1), "count": len(v)}
                for sec, v in sorted(sec_map.items())
            ]

            # Attendance trend (last 30 days)
            trend_rows = _q("""
                SELECT sa.date,
                       COUNT(DISTINCT CASE WHEN UPPER(sa.status)='PRESENT' THEN sa.student_id END) AS present,
                       COUNT(DISTINCT sa.student_id) AS total
                FROM student_attendance sa
                LEFT JOIN students s ON s.student_id = sa.student_id
                WHERE sa.date >= date('now','-30 days') AND s.active=1
                GROUP BY sa.date
                ORDER BY sa.date ASC
            """)
            trend = [
                {"date": r[0], "pct": _pct(r[1], r[2]) if r[2] else 0}
                for r in trend_rows
            ]

            # Insights
            insights = []
            if year_wise:
                lowest_yr = min(year_wise, key=lambda x: x["avg_pct"])
                if lowest_yr["avg_pct"] < 75:
                    insights.append(f"{lowest_yr['year']} Year has the lowest attendance at {lowest_yr['avg_pct']}%.")
            if section_wise:
                lowest_sec = min(section_wise, key=lambda x: x["avg_pct"])
                if lowest_sec["avg_pct"] < avg_att:
                    insights.append(f"Section {lowest_sec['section']} attendance ({lowest_sec['avg_pct']}%) is below department average ({avg_att}%).")
            if len(below75):
                insights.append(f"{len(below75)} student{'s' if len(below75)!=1 else ''} require{'s' if len(below75)==1 else ''} immediate attendance improvement.")
            if critical_count:
                insights.append(f"{critical_count} student{'s are' if critical_count!=1 else ' is'} critically low (below 60%).")
            if avg_att >= 75:
                insights.append(f"Department average attendance is healthy at {avg_att}%.")
            else:
                insights.append(f"Department average attendance is {avg_att}% — below the 75% required threshold.")

            below75.sort(key=lambda s: s["pct"])

            return {
                "summary": {
                    "total_students": total_students,
                    "avg_attendance": avg_att,
                    "below_75_count": len(below75),
                    "above_75_count": len(above75),
                    "warning_count": warning_count,
                    "critical_count": critical_count,
                    "days": days,
                },
                "year_wise": year_wise,
                "section_wise": section_wise,
                "trend": trend,
                "below75_students": below75,
                "insights": insights,
            }
