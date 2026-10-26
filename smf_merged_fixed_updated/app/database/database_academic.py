# =============================================================
# database_academic.py — NEW FILE (additive only)
#
# Tracks CGPA/SGPA and backlog (arrear) data per student per
# semester. Independent of the existing `students` /
# `student_extended` tables — only joined read-only for
# name/department display.
# =============================================================
import logging
from datetime import datetime

from database import db

log = logging.getLogger(__name__)


def init_academic_table():
    """Safe to call on every startup — CREATE TABLE IF NOT EXISTS only."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_academics (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id       TEXT NOT NULL,
                semester         INTEGER NOT NULL,
                cgpa             REAL,
                sgpa             REAL,
                backlog_count    INTEGER DEFAULT 0,
                backlog_subjects TEXT,
                updated_at       TEXT,
                updated_by       TEXT,
                UNIQUE(student_id, semester)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_acad_student ON student_academics(student_id)
        """)


def _latest_per_student_subquery():
    # picks the most recently updated semester record per student
    return """
        SELECT sa.*
        FROM student_academics sa
        INNER JOIN (
            SELECT student_id, MAX(semester) AS max_sem
            FROM student_academics
            GROUP BY student_id
        ) latest ON sa.student_id = latest.student_id AND sa.semester = latest.max_sem
    """


def upsert_record(student_id: str, semester: int, cgpa: float = None, sgpa: float = None,
                   backlog_count: int = 0, backlog_subjects: str = "", updated_by: str = "") -> dict:
    init_academic_table()
    with db() as conn:
        conn.execute("""
            INSERT INTO student_academics
              (student_id, semester, cgpa, sgpa, backlog_count, backlog_subjects, updated_at, updated_by)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(student_id, semester) DO UPDATE SET
              cgpa=excluded.cgpa, sgpa=excluded.sgpa,
              backlog_count=excluded.backlog_count,
              backlog_subjects=excluded.backlog_subjects,
              updated_at=excluded.updated_at, updated_by=excluded.updated_by
        """, (student_id, semester, cgpa, sgpa, backlog_count, backlog_subjects,
              datetime.now().isoformat(timespec="seconds"), updated_by))

    return get_for_student(student_id)


def get_for_student(student_id: str) -> list:
    init_academic_table()
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM student_academics WHERE student_id=? ORDER BY semester DESC",
            (student_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_latest(dept: str = None) -> list:
    """Latest semester record per student, joined with name/dept for display."""
    init_academic_table()
    with db() as conn:
        q = f"""
            SELECT s.student_id, s.name, COALESCE(s.department,'') AS dept,
                   la.semester, la.cgpa, la.sgpa, la.backlog_count, la.backlog_subjects, la.updated_at
            FROM ({_latest_per_student_subquery()}) la
            JOIN students s ON s.student_id = la.student_id
        """
        params = []
        if dept:
            q += " WHERE UPPER(COALESCE(s.department,'')) = ?"
            params.append(dept.upper())
        q += " ORDER BY la.cgpa DESC"
        rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


def get_backlogs(dept: str = None) -> list:
    """Students whose LATEST semester record has backlog_count > 0."""
    rows = get_all_latest(dept)
    return [r for r in rows if (r.get("backlog_count") or 0) > 0]


def get_cgpa_summary(dept: str = None) -> dict:
    rows = get_all_latest(dept)
    total = len(rows)
    cgpas = [r["cgpa"] for r in rows if r.get("cgpa") is not None]
    avg_cgpa = round(sum(cgpas) / len(cgpas), 2) if cgpas else None
    with_backlog = [r for r in rows if (r.get("backlog_count") or 0) > 0]
    total_backlogs = sum(r.get("backlog_count") or 0 for r in rows)
    return {
        "dept": dept or "All",
        "total_records": total,
        "avg_cgpa": avg_cgpa,
        "students_with_backlogs": len(with_backlog),
        "total_backlog_count": total_backlogs,
    }
