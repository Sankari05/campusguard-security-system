# =============================================================
# database_faculty_requests.py — Faculty Request Management (DB layer)
#
# PHASE 1 — Faculty-side Leave / OD approval workflow.
#
# Reuses:
#   - student_leave_requests  (already created by student_portal_db.py
#     when a student applies for leave — no duplicate table created)
#
# Adds (additive only — no existing OD table was found anywhere in
# this codebase, including api_student_portal.py / student_portal_db.py):
#   - od_requests  (mirrors the shape of student_leave_requests so the
#     Faculty UI can treat both request types uniformly)
#
# Does NOT touch students table, attendance tables, or anything used
# by the Student Portal.
# =============================================================
import logging
import sqlite3
from datetime import datetime, date

from database import db

log = logging.getLogger(__name__)


# =============================================================
# Student notification trigger (additive — Prompt 4)
#
# Wired from decide_leave_request()/decide_od_request() below
# whenever a request's status changes to Approved/Rejected.
# Notification rows live in student_portal_db's student_notifications
# table; this module does not duplicate that storage logic, it just
# calls into it. Failures here never break the approve/reject flow.
# =============================================================
def _notify_student_of_decision(student_id: str, message: str) -> None:
    try:
        import student_portal_db as spdb
        spdb.add_notification(student_id, message)
    except Exception:
        log.exception("Could not create student notification for %s", student_id)


# =============================================================
# Table init (safe, additive — CREATE TABLE IF NOT EXISTS only)
# =============================================================
def _migrate_leave_table():
    """Add decided_by_role to an existing student_leave_requests table
    that predates this column (same old-schema situation Step 1 handled
    for od_requests). Leave requests stay single-stage — this is an
    audit-field-only migration, decide_leave_request()'s approval logic
    is unchanged. Safe/idempotent: ADD COLUMN errors when the column
    already exists are swallowed."""
    with db() as conn:
        try:
            conn.execute(
                "ALTER TABLE student_leave_requests ADD COLUMN decided_by_role TEXT DEFAULT ''"
            )
        except sqlite3.OperationalError:
            # Column already exists — fine, nothing to do.
            pass


def init_leave_table():
    """Same table student_portal_db.py creates — guarantees it exists
    even if this module loads before the student portal does."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_leave_requests (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id       TEXT NOT NULL,
                from_date        TEXT NOT NULL,
                to_date          TEXT NOT NULL,
                reason           TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'Pending',
                applied_at       TEXT NOT NULL,
                decided_by       TEXT DEFAULT '',
                decided_at       TEXT DEFAULT '',
                remarks          TEXT DEFAULT '',
                decided_by_role  TEXT DEFAULT ''   -- 'faculty' | 'admin' (HOD never decides leave)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_leave_student ON student_leave_requests(student_id)
        """)
    _migrate_leave_table()


def _migrate_od_table():
    """Upgrade an existing od_requests table (old 11-column schema) to the
    two-stage Faculty -> HOD approval schema by adding any column from the
    list below that isn't already present.

    ALTER TABLE ... ADD COLUMN doesn't support IF NOT EXISTS on older
    sqlite versions, so each ALTER is attempted individually and a
    sqlite3.OperationalError (raised when the column already exists) is
    swallowed. This is safe to call every time init_od_table() runs, on
    both fresh installs (CREATE TABLE already adds the columns, so every
    ALTER here is a harmless no-op caught by the except) and existing
    databases still on the old schema (each ALTER actually adds a column).

    Does NOT touch student_leave_requests — leave requests remain
    single-stage per the business rule and are migrated separately
    (audit fields only, see Step 2).
    """
    new_columns = [
        ("faculty_status",     "TEXT DEFAULT ''"),
        ("faculty_decided_by", "TEXT DEFAULT ''"),
        ("faculty_decided_at", "TEXT DEFAULT ''"),
        ("faculty_remarks",    "TEXT DEFAULT ''"),
        ("hod_status",         "TEXT DEFAULT ''"),
        ("hod_decided_by",     "TEXT DEFAULT ''"),
        ("hod_decided_at",     "TEXT DEFAULT ''"),
        ("hod_remarks",        "TEXT DEFAULT ''"),
        ("forwarded_at",       "TEXT DEFAULT ''"),
    ]
    with db() as conn:
        for col_name, col_def in new_columns:
            try:
                conn.execute(f"ALTER TABLE od_requests ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                # Column already exists — fine, nothing to do.
                pass


def init_od_table():
    """od_requests now drives a two-stage Student -> Faculty -> HOD
    approval pipeline (OD only — leave requests stay single-stage).

    status now has 4 allowed values: Pending / Forwarded / Approved / Rejected.
      - Pending:   awaiting Faculty decision
      - Forwarded: Faculty approved, awaiting HOD's final decision
      - Approved:  HOD gave final approval
      - Rejected:  rejected at either the Faculty or HOD stage

    decided_by/decided_at/remarks are kept for backward compatibility
    with old UI calls that may still read them; they now mirror whichever
    stage (faculty_* or hod_*) made the LAST decision and are no longer
    the source of truth for OD — that's faculty_status/hod_status.
    """
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS od_requests (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id         TEXT NOT NULL,
                event_name         TEXT NOT NULL,
                event_date         TEXT NOT NULL,
                reason             TEXT NOT NULL,
                attachment         TEXT DEFAULT '',
                status             TEXT NOT NULL DEFAULT 'Pending',  -- Pending/Forwarded/Approved/Rejected
                applied_at         TEXT NOT NULL,
                decided_by         TEXT DEFAULT '',
                decided_at         TEXT DEFAULT '',
                remarks            TEXT DEFAULT '',
                faculty_status     TEXT DEFAULT '',   -- '', 'Approved', 'Rejected'
                faculty_decided_by TEXT DEFAULT '',
                faculty_decided_at TEXT DEFAULT '',
                faculty_remarks    TEXT DEFAULT '',
                hod_status         TEXT DEFAULT '',   -- '', 'Approved', 'Rejected'
                hod_decided_by     TEXT DEFAULT '',
                hod_decided_at     TEXT DEFAULT '',
                hod_remarks        TEXT DEFAULT '',
                forwarded_at       TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_od_student ON od_requests(student_id)
        """)
    _migrate_od_table()


def init_tables():
    init_leave_table()
    init_od_table()


# =============================================================
# Faculty scope resolution
# =============================================================
def get_faculty_scope(fac_id: str) -> dict:
    """
    Resolve which students a faculty member is allowed to see:
      - class_incharge_dept/year/section if the faculty is a class incharge
      - otherwise falls back to their own department (dept or department)
    Returns {"department": str|None, "year": str|None, "section": str|None}
    """
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM faculty WHERE fac_id=? AND active=1", (fac_id,)
        ).fetchone()
    if not row:
        return {"department": None, "year": None, "section": None}

    fac = dict(row)
    if fac.get("is_class_incharge") and fac.get("class_incharge_dept"):
        return {
            "department": fac.get("class_incharge_dept") or fac.get("incharge_department"),
            "year": str(fac.get("class_incharge_year") or fac.get("incharge_year") or "") or None,
            "section": fac.get("class_incharge_section") or fac.get("incharge_section") or None,
        }
    dept = fac.get("dept") or fac.get("department")
    return {"department": dept, "year": None, "section": None}


def _student_in_scope_clause(scope: dict):
    """Builds a SQL WHERE fragment + params restricting to students in scope."""
    clauses = []
    params = []
    if scope.get("department"):
        clauses.append("UPPER(s.department)=UPPER(?)")
        params.append(scope["department"])
    if scope.get("year"):
        raw_y = str(scope["year"]).strip()
        dig = "".join([c for c in raw_y if c.isdigit()])
        if dig:
            clauses.append("(s.year = ? OR s.year LIKE ? OR s.year LIKE ?)")
            params.extend([raw_y, f"{dig}%", f"{raw_y}%"])
        else:
            clauses.append("s.year=?")
            params.append(raw_y)
    if scope.get("section"):
        clauses.append("UPPER(s.section)=UPPER(?)")
        params.append(scope["section"])
    return clauses, params


# =============================================================
# Leave requests — faculty view
# =============================================================
def list_leave_requests(scope: dict, status: str | None = None) -> list:
    init_leave_table()
    clauses, params = _student_in_scope_clause(scope)
    sql = """
        SELECT lr.id, lr.student_id, lr.from_date, lr.to_date, lr.reason,
               lr.status, lr.applied_at, lr.decided_by, lr.decided_at, lr.remarks,
               s.name AS student_name, s.register_number, s.department,
               s.year, s.section
        FROM student_leave_requests lr
        JOIN students s ON s.student_id = lr.student_id
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    if status:
        sql += (" AND " if clauses else " WHERE ") + "UPPER(lr.status)=UPPER(?)"
        params.append(status)
    sql += " ORDER BY lr.applied_at DESC"

    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_leave_request(req_id: int):
    with db() as conn:
        row = conn.execute(
            """SELECT lr.*, s.name AS student_name, s.register_number,
                      s.department, s.year, s.section
               FROM student_leave_requests lr
               JOIN students s ON s.student_id = lr.student_id
               WHERE lr.id=?""",
            (req_id,),
        ).fetchone()
        return dict(row) if row else None


def decide_leave_request(req_id: int, decision: str, decided_by: str, remarks: str = "",
                          decided_by_role: str = "") -> dict | None:
    """decision: 'Approved' or 'Rejected'
    decided_by_role: 'faculty' | 'admin' — audit-trail only, HOD never
    decides leave; leave stays single-stage (Faculty-only)."""
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            """UPDATE student_leave_requests
               SET status=?, decided_by=?, decided_at=?, remarks=?, decided_by_role=?
               WHERE id=? AND status='Pending'""",
            (decision, decided_by, now, remarks, decided_by_role, req_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM student_leave_requests WHERE id=?", (req_id,)
        ).fetchone()
        record = dict(row) if row else None

    if record and decision in ("Approved", "Rejected"):
        _notify_student_of_decision(
            record["student_id"],
            "Your leave request ({} → {}) has been {}.{}".format(
                record.get("from_date", "—"), record.get("to_date", "—"),
                decision, (" Remarks: " + remarks) if remarks else "",
            ),
        )
    return record


# =============================================================
# OD requests — faculty view
# =============================================================
def list_od_requests(scope: dict, status: str | None = None) -> list:
    init_od_table()
    clauses, params = _student_in_scope_clause(scope)
    sql = """
        SELECT od.id, od.student_id, od.event_name, od.event_date, od.reason,
               od.attachment, od.status, od.applied_at, od.decided_by,
               od.decided_at, od.remarks,
               od.faculty_status, od.faculty_decided_by,
               od.hod_status, od.hod_decided_by,
               s.name AS student_name, s.register_number, s.department,
               s.year, s.section
        FROM od_requests od
        JOIN students s ON s.student_id = od.student_id
    """
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    if status:
        sql += (" AND " if clauses else " WHERE ") + "UPPER(od.status)=UPPER(?)"
        params.append(status)
    sql += " ORDER BY od.applied_at DESC"

    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_od_request(req_id: int):
    with db() as conn:
        row = conn.execute(
            """SELECT od.*, s.name AS student_name, s.register_number,
                      s.department, s.year, s.section
               FROM od_requests od
               JOIN students s ON s.student_id = od.student_id
               WHERE od.id=?""",
            (req_id,),
        ).fetchone()
        return dict(row) if row else None


def faculty_decide_od_request(req_id: int, decision: str, decided_by: str, remarks: str = "") -> dict | None:
    """Stage 1 of the two-stage OD pipeline (Student -> Faculty -> HOD).
    decision: 'Approved' or 'Rejected'. Only allowed when status == 'Pending'
    (atomicity guard in the WHERE clause below).

    'Approved' does NOT finalize the request -- it forwards it to HOD by
    setting status='Forwarded'; only hod_decide_od_request() can act on a
    'Forwarded' row.
    'Rejected' IS final at this stage -- the request never reaches HOD.

    decided_by/decided_at/remarks (legacy columns, kept for backward
    compatibility) are updated here too so they mirror this stage's
    decision, per Step 1's "mirrors whichever stage made the LAST
    decision" contract.

    Returns None if rowcount==0 (request not found, or not Pending --
    i.e. already decided by faculty, or even already forwarded/finalized).
    """
    if decision not in ("Approved", "Rejected"):
        raise ValueError("decision must be 'Approved' or 'Rejected'")
    now = datetime.now().isoformat(timespec="seconds")
    new_status = "Forwarded" if decision == "Approved" else "Rejected"
    forwarded_at = now if decision == "Approved" else ""

    with db() as conn:
        cur = conn.execute(
            """UPDATE od_requests
               SET faculty_status=?, faculty_decided_by=?, faculty_decided_at=?,
                   faculty_remarks=?, status=?, forwarded_at=?,
                   decided_by=?, decided_at=?, remarks=?
               WHERE id=? AND status='Pending'""",
            (decision, decided_by, now, remarks, new_status, forwarded_at,
             decided_by, now, remarks, req_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM od_requests WHERE id=?", (req_id,)
        ).fetchone()
        record = dict(row) if row else None

    if record:
        if decision == "Approved":
            _notify_student_of_decision(
                record["student_id"],
                "Your OD request has been approved by your faculty and "
                "forwarded to HOD for final approval.",
            )
        else:
            _notify_student_of_decision(
                record["student_id"],
                "Your OD request has been rejected by faculty.{}".format(
                    (" Remarks: " + remarks) if remarks else ""
                ),
            )
    return record


def hod_decide_od_request(req_id: int, decision: str, decided_by: str, remarks: str = "") -> dict | None:
    """Stage 2 (final) of the two-stage OD pipeline. decision: 'Approved'
    or 'Rejected'. Only allowed when status == 'Forwarded' -- i.e. faculty
    already approved it. HOD can NEVER act on a 'Pending' row directly;
    this WHERE guard is exactly what removes the old Faculty/HOD race
    condition, since the two stages now operate on mutually exclusive
    status values ('Pending' vs 'Forwarded').

    decided_by/decided_at/remarks (legacy columns) mirror this final
    decision, per Step 1's backward-compatibility contract.

    Returns None if rowcount==0 (request not found, not in 'Forwarded'
    state, already finalized by HOD, or never reached HOD because faculty
    rejected/hasn't decided yet).
    """
    if decision not in ("Approved", "Rejected"):
        raise ValueError("decision must be 'Approved' or 'Rejected'")
    now = datetime.now().isoformat(timespec="seconds")

    with db() as conn:
        cur = conn.execute(
            """UPDATE od_requests
               SET hod_status=?, hod_decided_by=?, hod_decided_at=?, hod_remarks=?,
                   status=?, decided_by=?, decided_at=?, remarks=?
               WHERE id=? AND status='Forwarded'""",
            (decision, decided_by, now, remarks, decision,
             decided_by, now, remarks, req_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM od_requests WHERE id=?", (req_id,)
        ).fetchone()
        record = dict(row) if row else None

    if record:
        _notify_student_of_decision(
            record["student_id"],
            "Your OD request has received final HOD {}.{}".format(
                decision, (" Remarks: " + remarks) if remarks else ""
            ),
        )
    return record


def decide_od_request(*args, **kwargs):
    """DEPRECATED. od_requests now goes through a two-stage Student ->
    Faculty -> HOD approval pipeline; a single decide_od_request() can no
    longer correctly express "which stage is deciding". Replaced by
    faculty_decide_od_request() (stage 1, Pending -> Forwarded/Rejected)
    and hod_decide_od_request() (stage 2, Forwarded -> Approved/Rejected).

    Kept as a thin wrapper, rather than deleted outright, so any stale
    caller fails loudly with a clear error instead of silently writing
    into the old single-status columns and corrupting the new pipeline.
    """
    raise NotImplementedError(
        "decide_od_request() has been removed -- it has been replaced by "
        "faculty_decide_od_request() (Pending -> Forwarded/Rejected) and "
        "hod_decide_od_request() (Forwarded -> Approved/Rejected). "
        "Update the caller to use the correct stage."
    )


# =============================================================
# Faculty dashboard widgets
# =============================================================
def get_request_counts(scope: dict) -> dict:
    init_tables()
    clauses, params = _student_in_scope_clause(scope)
    where_students = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    today = date.today().isoformat()

    with db() as conn:
        pending_leave = conn.execute(
            f"""SELECT COUNT(*) FROM student_leave_requests lr
                JOIN students s ON s.student_id=lr.student_id
                {where_students}{' AND ' if where_students else ' WHERE '}UPPER(lr.status)='PENDING'""",
            params,
        ).fetchone()[0]

        pending_od = conn.execute(
            f"""SELECT COUNT(*) FROM od_requests od
                JOIN students s ON s.student_id=od.student_id
                {where_students}{' AND ' if where_students else ' WHERE '}UPPER(od.status)='PENDING'""",
            params,
        ).fetchone()[0]

        # Stage 2 of the OD pipeline: requests faculty already approved
        # and forwarded, now awaiting HOD's final decision. Distinct from
        # pending_od above (status='Pending', stage 1 / awaiting faculty).
        pending_hod_od = conn.execute(
            f"""SELECT COUNT(*) FROM od_requests od
                JOIN students s ON s.student_id=od.student_id
                {where_students}{' AND ' if where_students else ' WHERE '}UPPER(od.status)='FORWARDED'""",
            params,
        ).fetchone()[0]

        # Gate Pass requests — Stage 1 (Pending awaiting Class Incharge)
        # and Stage 2 (Forwarded awaiting HOD)
        try:
            pending_gatepass = conn.execute(
                f"""SELECT COUNT(*) FROM gatepass_requests g
                    JOIN students s ON s.student_id=g.student_id
                    {where_students}{' AND ' if where_students else ' WHERE '}UPPER(g.status)='PENDING'""",
                params,
            ).fetchone()[0]
            # Safe department fallback: if incharge scope didn't catch due to year formatting variation, check department
            if pending_gatepass == 0 and scope.get("department"):
                pending_gatepass = conn.execute(
                    """SELECT COUNT(*) FROM gatepass_requests g
                        JOIN students s ON s.student_id=g.student_id
                        WHERE UPPER(s.department)=UPPER(?) AND UPPER(g.status)='PENDING'""",
                    (scope["department"],),
                ).fetchone()[0]
        except Exception:
            pending_gatepass = 0

        try:
            pending_hod_gatepass = conn.execute(
                f"""SELECT COUNT(*) FROM gatepass_requests g
                    JOIN students s ON s.student_id=g.student_id
                    {where_students}{' AND ' if where_students else ' WHERE '}UPPER(g.status)='FORWARDED'""",
                params,
            ).fetchone()[0]
            if pending_hod_gatepass == 0 and scope.get("department"):
                pending_hod_gatepass = conn.execute(
                    """SELECT COUNT(*) FROM gatepass_requests g
                        JOIN students s ON s.student_id=g.student_id
                        WHERE UPPER(s.department)=UPPER(?) AND UPPER(g.status)='FORWARDED'""",
                    (scope["department"],),
                ).fetchone()[0]
        except Exception:
            pending_hod_gatepass = 0

        approved_today = conn.execute(
            f"""SELECT
                  (SELECT COUNT(*) FROM student_leave_requests lr
                   JOIN students s ON s.student_id=lr.student_id
                   {where_students}{' AND ' if where_students else ' WHERE '}UPPER(lr.status)='APPROVED' AND lr.decided_at LIKE ? )
                + (SELECT COUNT(*) FROM od_requests od
                   JOIN students s ON s.student_id=od.student_id
                   {where_students}{' AND ' if where_students else ' WHERE '}UPPER(od.status)='APPROVED' AND od.decided_at LIKE ? )
                + (SELECT COUNT(*) FROM gatepass_requests gp
                   JOIN students s ON s.student_id=gp.student_id
                   {where_students}{' AND ' if where_students else ' WHERE '}UPPER(gp.status)='APPROVED' AND gp.otp_generated_at LIKE ? )
            """,
            params + [f"{today}%"] + params + [f"{today}%"] + params + [f"{today}%"],
        ).fetchone()[0]

        rejected_today = conn.execute(
            f"""SELECT
                  (SELECT COUNT(*) FROM student_leave_requests lr
                   JOIN students s ON s.student_id=lr.student_id
                   {where_students}{' AND ' if where_students else ' WHERE '}UPPER(lr.status)='REJECTED' AND lr.decided_at LIKE ? )
                + (SELECT COUNT(*) FROM od_requests od
                   JOIN students s ON s.student_id=od.student_id
                   {where_students}{' AND ' if where_students else ' WHERE '}UPPER(od.status)='REJECTED' AND od.decided_at LIKE ? )
                + (SELECT COUNT(*) FROM gatepass_requests gp
                   JOIN students s ON s.student_id=gp.student_id
                   {where_students}{' AND ' if where_students else ' WHERE '}UPPER(gp.status)='REJECTED' AND (gp.faculty_decided_at LIKE ? OR gp.hod_decided_at LIKE ?) )
            """,
            params + [f"{today}%"] + params + [f"{today}%"] + params + [f"{today}%", f"{today}%"],
        ).fetchone()[0]

    return {
        "pending_leave_requests": pending_leave,
        "pending_od_requests": pending_od,
        "pending_hod_od": pending_hod_od,
        "pending_gatepass_requests": pending_gatepass,
        "pending_hod_gatepass": pending_hod_gatepass,
        "approved_requests_today": approved_today,
        "rejected_requests_today": rejected_today,
    }
