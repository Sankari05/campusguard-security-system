# =============================================================
# database_workload.py — NEW FILE (additive only)
#
# Computes faculty teaching-hour workload from the EXISTING
# faculty_timetable table (one row = one weekly period). Adds one
# new table (faculty_workload) purely for manual overrides of
# lab/admin duty hours — weekly_hours itself is always computed
# live from faculty_timetable, never stored stale.
# =============================================================
import logging
from datetime import datetime

from database import db

log = logging.getLogger(__name__)


def init_workload_table():
    """Safe to call on every startup — CREATE TABLE IF NOT EXISTS only."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS faculty_workload (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id      TEXT NOT NULL UNIQUE,
                dept            TEXT,
                lab_duty_hours  INTEGER DEFAULT 0,
                admin_duty_hours INTEGER DEFAULT 0,
                updated_at      TEXT
            )
        """)


def _overrides_map(conn):
    rows = conn.execute(
        "SELECT faculty_id, lab_duty_hours, admin_duty_hours FROM faculty_workload"
    ).fetchall()
    return {r[0]: {"lab_duty_hours": r[1] or 0, "admin_duty_hours": r[2] or 0} for r in rows}


def get_all_workload(dept: str = None) -> list:
    """
    Auto-calculates weekly_hours by counting faculty_timetable rows per
    faculty (each row = one period/week). Joins with the faculty table
    for name/dept, and with faculty_workload for any manual lab/admin
    duty overrides.
    """
    init_workload_table()
    with db() as conn:
        overrides = _overrides_map(conn)

        q = """
            SELECT f.fac_id AS faculty_id, f.name AS name, f.dept AS dept,
                   COALESCE(t.cnt, 0) AS weekly_hours
            FROM faculty f
            LEFT JOIN (
                SELECT faculty_id, COUNT(*) AS cnt
                FROM faculty_timetable
                GROUP BY faculty_id
            ) t ON t.faculty_id = f.fac_id
        """
        params = []
        if dept:
            q += " WHERE UPPER(f.dept) = ?"
            params.append(dept.upper())
        q += " ORDER BY weekly_hours DESC"

        rows = conn.execute(q, params).fetchall()
        result = []
        for r in rows:
            ov = overrides.get(r["faculty_id"], {})
            result.append({
                "faculty_id": r["faculty_id"],
                "name": r["name"],
                "dept": r["dept"],
                "weekly_hours": r["weekly_hours"] or 0,
                "lab_duty_hours": ov.get("lab_duty_hours", 0),
                "admin_duty_hours": ov.get("admin_duty_hours", 0),
                "total_load_hours": (r["weekly_hours"] or 0)
                                    + ov.get("lab_duty_hours", 0)
                                    + ov.get("admin_duty_hours", 0),
            })
        return result


def get_faculty_workload(fac_id: str) -> dict:
    rows = get_all_workload()
    for r in rows:
        if r["faculty_id"] == fac_id:
            return r
    return {"faculty_id": fac_id, "name": None, "dept": None,
            "weekly_hours": 0, "lab_duty_hours": 0, "admin_duty_hours": 0,
            "total_load_hours": 0}


def set_workload_override(fac_id: str, lab_duty_hours: int = None, admin_duty_hours: int = None) -> dict:
    """Manual override for lab/admin duty hours only — weekly_hours stays auto-computed."""
    init_workload_table()
    with db() as conn:
        existing = conn.execute(
            "SELECT * FROM faculty_workload WHERE faculty_id=?", (fac_id,)
        ).fetchone()
        dept_row = conn.execute("SELECT dept FROM faculty WHERE fac_id=?", (fac_id,)).fetchone()
        dept = dept_row[0] if dept_row else None

        if existing:
            new_lab = lab_duty_hours if lab_duty_hours is not None else existing["lab_duty_hours"]
            new_admin = admin_duty_hours if admin_duty_hours is not None else existing["admin_duty_hours"]
            conn.execute(
                "UPDATE faculty_workload SET lab_duty_hours=?, admin_duty_hours=?, updated_at=? WHERE faculty_id=?",
                (new_lab, new_admin, datetime.now().isoformat(timespec="seconds"), fac_id)
            )
        else:
            conn.execute(
                "INSERT INTO faculty_workload (faculty_id, dept, lab_duty_hours, admin_duty_hours, updated_at) "
                "VALUES (?,?,?,?,?)",
                (fac_id, dept, lab_duty_hours or 0, admin_duty_hours or 0,
                 datetime.now().isoformat(timespec="seconds"))
            )
    return get_faculty_workload(fac_id)
