"""
app/services/student_service.py
Enterprise Service for student business logic, normalization, and analytics.
"""

from typing import Any, Dict, List, Optional
from app.repositories.student_repository import StudentRepository
from app.schemas.student import StudentResponse, StudentListResponse, StudentStatsResponse


class StudentService:
    """Business logic layer for student management and statistics."""

    _ROMAN_TO_NUM = {"I": "1", "II": "2", "III": "3", "IV": "4"}
    _SEM_TO_NUM = {
        "1": "1", "2": "1", "3": "2", "4": "2",
        "5": "3", "6": "3", "7": "4", "8": "4",
    }

    def __init__(self, repository: Optional[StudentRepository] = None):
        self.repo = repository or StudentRepository()

    @staticmethod
    def derive_year(student: Dict[str, Any]) -> str:
        """Derive academic year from explicit field or roll number batch prefix (e.g. 23 -> 4th Year)."""
        yr = (student.get("year") or "").strip()
        if yr:
            return yr
        roll = (student.get("roll_number") or "").strip()
        if roll and len(roll) >= 2 and roll[:2].isdigit():
            batch = int(roll[:2])
            calc_yr = max(1, min(4, 26 - batch + 1))
            suffix = "st" if calc_yr == 1 else "nd" if calc_yr == 2 else "rd" if calc_yr == 3 else "th"
            return f"{calc_yr}{suffix} Year"
        return ""

    @classmethod
    def norm_year(cls, val: str) -> str:
        """Normalize any year representation ('III', '3', '3rd Year', 'Year 3') down to digit '1'-'4'."""
        v = (val or "").strip().upper()
        if not v:
            return ""
        if v in cls._ROMAN_TO_NUM:
            return cls._ROMAN_TO_NUM[v]
        for rom, num in cls._ROMAN_TO_NUM.items():
            if rom in v:
                return num
        digits = [c for c in v if c.isdigit()]
        if digits:
            d = int(digits[0])
            if 1 <= d <= 4:
                return str(d)
        if len(v) >= 2 and v[:2].isdigit():
            b = int(v[:2])
            calc_yr = max(1, min(4, 26 - b + 1))
            return str(calc_yr)
        return ""

    @staticmethod
    def get_attendance_status(pct: float) -> str:
        """Determine attendance category: good (>=75%), warning (50-74%), critical (<50%)."""
        if pct >= 75.0:
            return "good"
        if pct >= 50.0:
            return "warning"
        return "critical"

    def get_students_stats(self, role: str, dept: str = "") -> StudentStatsResponse:
        """Calculate aggregate student counts and low-attendance alerts."""
        role_norm = (role or "").lower()
        dept_norm = (dept or "").upper()

        stats = self.repo.get_dashboard_stats("admin" if role_norm == "admin" else "hod", dept=dept_norm)
        total = stats.get("student_count", 0)
        present_today = min(stats.get("present_today", 0), total)
        absent_today = max(0, total - present_today)

        if role_norm == "admin":
            critical_count = len(self.repo.get_low_attendance_students(threshold=75.0))
        else:
            low = self.repo.get_low_attendance_students(threshold=75.0)
            critical_count = len([s for s in low if (s.get("department") or "").upper() == dept_norm])

        return StudentStatsResponse(
            total=total,
            present_today=present_today,
            absent_today=absent_today,
            critical_count=critical_count,
        )

    def get_students_list(
        self,
        role: str,
        own_dept: str = "",
        year: Optional[str] = None,
        section: Optional[str] = None,
        dept: Optional[str] = None,
        semester: Optional[str] = None,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 6,
    ) -> Dict[str, Any]:
        """Fetch, scope, enrich, filter, and paginate student list."""
        role_norm = (role or "").lower()
        own_dept_norm = (own_dept or "").upper()

        raw_students = self.repo.get_all_students()

        # Department scoping
        if role_norm != "admin" and own_dept_norm:
            students = [s for s in raw_students if (s.get("department") or "").upper() == own_dept_norm]
        elif role_norm == "admin" and dept:
            dept_q = dept.strip().upper()
            students = [s for s in raw_students if (s.get("department") or "").upper() == dept_q]
        else:
            students = list(raw_students)

        # Build attendance lookup
        att_map = {}
        try:
            summary_rows = self.repo.get_attendance_summary(days=180)
            for row in summary_rows:
                sid = row.get("student_id", "")
                present = row.get("present_count", 0) or 0
                total_d = row.get("total_days", 1) or 1
                att_map[sid] = round(present / total_d * 100, 1)
        except Exception:
            pass

        # Enrich records
        enriched = []
        for s in students:
            item = dict(s)
            sid = item.get("student_id", "")
            pct = att_map.get(sid, 0.0)
            item["attendance_pct"] = pct
            item["status"] = self.get_attendance_status(pct)
            item.setdefault("year", self.derive_year(item))
            enriched.append(item)

        # Year and Semester filter
        if year or semester:
            target_yr = self.norm_year(year) if year else self._SEM_TO_NUM.get(str(semester).strip(), "")
            if target_yr:
                enriched = [s for s in enriched if self.norm_year(s.get("year", "")) == target_yr]

        # Section filter
        if section:
            sec_q = section.strip().upper()
            enriched = [s for s in enriched if (s.get("section") or "").strip().upper() == sec_q]

        # Search filter
        if search:
            q = search.strip().lower()
            enriched = [
                s for s in enriched
                if q in (s.get("name") or "").lower()
                or q in (s.get("roll_number") or "").lower()
                or q in (s.get("reg_no") or "").lower()
                or q in (s.get("student_id") or "").lower()
            ]

        # Status filter
        if status:
            stat_q = status.strip().lower()
            enriched = [s for s in enriched if s.get("status") == stat_q]

        total = len(enriched)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = start + per_page
        page_items = enriched[start:end]

        return {
            "students": page_items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": total_pages,
            "total_pages": total_pages,
        }
