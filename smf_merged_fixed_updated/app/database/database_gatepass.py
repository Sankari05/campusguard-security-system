# =============================================================
# database_gatepass.py — Gate Pass Management (Database Layer)
#
# Safe, isolated, and additive database module for Student Gate Pass.
# Zero impact on existing attendance or face recognition tables.
#
# Workflow:
#   1. Student applies for Gate Pass (Status: Pending)
#   2. Class Incharge (Faculty) reviews & approves (Status: Forwarded)
#   3. HOD gives final approval (Status: Approved) -> Generates 6-Digit OTP & QR
#   4. Watchman verifies OTP at Gate (POST /api/v1/gatepass/verify)
#   5. Watchman logs student exit (POST /api/v1/gatepass/mark-exit)
# =============================================================
import logging
import sqlite3
import random
from datetime import datetime, date, timedelta

from app.database.database import db

log = logging.getLogger(__name__)


# ── Student notification trigger ─────────────────────────────
def _notify_student(student_id: str, message: str) -> None:
    try:
        from app.database import student_portal_db as spdb
        spdb.add_notification(student_id, message)
    except Exception:
        try:
            import student_portal_db as spdb
            spdb.add_notification(student_id, message)
        except Exception:
            log.warning("Could not send gatepass notification to student %s", student_id)


# ── Schema Initialization ────────────────────────────────────
def init_gatepass_table():
    """Create gatepass_requests table safely if not exists."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gatepass_requests (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id          TEXT NOT NULL,
                pass_type           TEXT DEFAULT 'Gate Pass',
                reason              TEXT NOT NULL,
                event_date          TEXT NOT NULL,
                out_time            TEXT NOT NULL,
                expected_in_time    TEXT DEFAULT '',
                status              TEXT NOT NULL DEFAULT 'Pending',
                applied_at          TEXT NOT NULL,
                faculty_status      TEXT DEFAULT '',
                faculty_decided_by  TEXT DEFAULT '',
                faculty_decided_at  TEXT DEFAULT '',
                faculty_remarks     TEXT DEFAULT '',
                hod_status          TEXT DEFAULT '',
                hod_decided_by      TEXT DEFAULT '',
                hod_decided_at      TEXT DEFAULT '',
                hod_remarks         TEXT DEFAULT '',
                forwarded_at        TEXT DEFAULT '',
                otp                 TEXT DEFAULT '',
                otp_generated_at    TEXT DEFAULT '',
                otp_expires_at      TEXT DEFAULT '',
                qr_payload          TEXT DEFAULT '',
                is_used             INTEGER DEFAULT 0,
                exited_at           TEXT DEFAULT '',
                guard_id            TEXT DEFAULT '',
                guard_remarks       TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gp_student ON gatepass_requests(student_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gp_otp ON gatepass_requests(otp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gp_status ON gatepass_requests(status)
        """)


# ── Student Actions ──────────────────────────────────────────
def apply_gatepass(
    student_id: str,
    reason: str,
    event_date: str,
    out_time: str,
    expected_in_time: str = "",
    pass_type: str = "Gate Pass",
    qr_payload: str = "",
) -> dict:
    """Student submits a gate pass request."""
    init_gatepass_table()
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO gatepass_requests
               (student_id, pass_type, reason, event_date, out_time, expected_in_time,
                status, applied_at, qr_payload)
               VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, ?)""",
            (student_id, pass_type, reason, event_date, out_time, expected_in_time, now, qr_payload),
        )
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM gatepass_requests WHERE id = ?", (new_id,)
        ).fetchone()
        return dict(row)


def list_student_gatepasses(student_id: str) -> list[dict]:
    """Get all gate pass requests for a given student."""
    init_gatepass_table()
    with db() as conn:
        rows = conn.execute(
            """SELECT * FROM gatepass_requests
               WHERE student_id = ?
               ORDER BY id DESC""",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_active_gatepass(student_id: str) -> dict | None:
    """Get the currently approved, un-used gate pass for this student if any."""
    init_gatepass_table()
    with db() as conn:
        row = conn.execute(
            """SELECT * FROM gatepass_requests
               WHERE student_id = ? AND status = 'Approved' AND is_used = 0
               ORDER BY id DESC LIMIT 1""",
            (student_id,),
        ).fetchone()
        return dict(row) if row else None


def get_gatepass_by_id(pass_id: int) -> dict | None:
    """Fetch full gate pass details joined with student profile."""
    init_gatepass_table()
    with db() as conn:
        row = conn.execute(
            """SELECT g.*, s.name, s.register_number, s.roll_number, s.department,
                      s.course, s.year, s.section, s.student_mobile, s.parent_mobile
               FROM gatepass_requests g
               LEFT JOIN students s ON g.student_id = s.student_id
               WHERE g.id = ?""",
            (pass_id,),
        ).fetchone()
        return dict(row) if row else None


# ── Faculty & HOD Review Actions ─────────────────────────────
def list_faculty_gatepasses(scope: dict, status: str = None) -> list[dict]:
    """List gate passes filtered by faculty scope (department, year, section)
    and status ('Pending' for Faculty, 'Forwarded' for HOD)."""
    init_gatepass_table()
    query = """
        SELECT g.*, s.name, s.register_number, s.roll_number, s.department,
               s.year, s.section
        FROM gatepass_requests g
        LEFT JOIN students s ON g.student_id = s.student_id
        WHERE 1=1
    """
    params = []
    if scope.get("department"):
        query += " AND s.department = ?"
        params.append(scope["department"])
    if scope.get("year"):
        query += " AND s.year = ?"
        params.append(str(scope["year"]))
    if scope.get("section"):
        query += " AND s.section = ?"
        params.append(scope["section"])

    if status:
        query += " AND g.status = ?"
        params.append(status)

    query += " ORDER BY g.id DESC"

    with db() as conn:
        rows = conn.execute(query, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["student_name"] = d.get("name") or d["student_id"]
            out.append(d)
        return out


def faculty_decide_gatepass(pass_id: int, decision: str, decided_by: str, remarks: str = "") -> dict | None:
    """Stage 1: Faculty/Class Incharge review.
    If 'Approved' -> status becomes 'Forwarded' (sent to HOD).
    If 'Rejected' -> status becomes 'Rejected'.
    """
    if decision not in ("Approved", "Rejected"):
        raise ValueError("decision must be 'Approved' or 'Rejected'")
    now = datetime.now().isoformat(timespec="seconds")
    new_status = "Forwarded" if decision == "Approved" else "Rejected"

    with db() as conn:
        cur = conn.execute(
            """UPDATE gatepass_requests
               SET faculty_status=?, faculty_decided_by=?, faculty_decided_at=?,
                   faculty_remarks=?, status=?, forwarded_at=?
               WHERE id=? AND status='Pending'""",
            (decision, decided_by, now, remarks, new_status, now if decision == "Approved" else "", pass_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM gatepass_requests WHERE id=?", (pass_id,)).fetchone()
        record = dict(row) if row else None

    if record:
        msg = f"Your Gate Pass request has been approved by Class Incharge ({decided_by}) and forwarded to HOD." if decision == "Approved" \
              else f"Your Gate Pass request was rejected by Class Incharge. Remarks: {remarks}"
        _notify_student(record["student_id"], msg)

    return record


def hod_decide_gatepass(pass_id: int, decision: str, decided_by: str, remarks: str = "") -> dict | None:
    """Stage 2: Final HOD review.
    If 'Approved' -> Generates 6-Digit OTP and QR payload!
    If 'Rejected' -> status becomes 'Rejected'.
    """
    if decision not in ("Approved", "Rejected"):
        raise ValueError("decision must be 'Approved' or 'Rejected'")
    now = datetime.now().isoformat(timespec="seconds")

    otp = ""
    otp_expires = ""
    qr_payload = ""

    if decision == "Approved":
        # Generate random 6-digit integer (100000 to 999999)
        otp = str(random.randint(100000, 999999))
        # Valid for 12 hours
        otp_expires = (datetime.now() + timedelta(hours=12)).isoformat(timespec="seconds")
        qr_payload = f"GP:{pass_id}:{otp}"

    with db() as conn:
        cur = conn.execute(
            """UPDATE gatepass_requests
               SET hod_status=?, hod_decided_by=?, hod_decided_at=?, hod_remarks=?,
                   status=?, otp=?, otp_generated_at=?, otp_expires_at=?, qr_payload=?
               WHERE id=? AND status='Forwarded'""",
            (decision, decided_by, now, remarks, decision, otp, now if otp else "", otp_expires, qr_payload, pass_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM gatepass_requests WHERE id=?", (pass_id,)).fetchone()
        record = dict(row) if row else None

    if record:
        if decision == "Approved":
            msg = f"🎉 Final HOD Approval Granted! Your Gate Pass OTP is: {otp}. Present this to the Security Guard at the Main Gate."
        else:
            msg = f"Your Gate Pass request was rejected by HOD. Remarks: {remarks}"
        _notify_student(record["student_id"], msg)

    return record


# ── Watchman Verification & Exit Actions ─────────────────────
def verify_gatepass_otp(otp_input: str) -> dict:
    """
    Called by Watchman Portal (Port 5173 / Main Gate App).
    Checks OTP, student approval status, and expiration.
    Returns full student details and permission state.
    """
    init_gatepass_table()
    clean_otp = str(otp_input or "").strip()
    if not clean_otp:
        return {
            "valid": False,
            "status": "INVALID_INPUT",
            "message": "Please enter a valid OTP.",
        }

    with db() as conn:
        row = conn.execute(
            """SELECT g.*, s.name, s.register_number, s.roll_number, s.department,
                      s.course, s.year, s.section, s.student_mobile, s.parent_mobile
               FROM gatepass_requests g
               LEFT JOIN students s ON g.student_id = s.student_id
               WHERE g.otp = ?
               ORDER BY g.id DESC LIMIT 1""",
            (clean_otp,),
        ).fetchone()

        if not row:
            return {
                "valid": False,
                "status": "NOT_FOUND",
                "message": f"No Gate Pass found matching OTP '{clean_otp}'.",
            }

        rec = dict(row)

        if rec["is_used"] == 1:
            return {
                "valid": False,
                "status": "ALREADY_USED",
                "message": f"This Gate Pass was already used by student at {rec.get('exited_at') or 'earlier'}.",
                "pass_id": rec["id"],
                "student_name": rec["name"],
                "register_number": rec["register_number"],
                "exited_at": rec["exited_at"],
            }

        if rec["status"] != "Approved":
            return {
                "valid": False,
                "status": "NOT_APPROVED",
                "message": f"This Gate Pass is not approved yet (Current status: {rec['status']}).",
                "pass_id": rec["id"],
                "student_name": rec["name"],
                "register_number": rec["register_number"],
            }

        # Check expiration if set
        if rec.get("otp_expires_at"):
            try:
                exp_dt = datetime.fromisoformat(rec["otp_expires_at"])
                if datetime.now() > exp_dt:
                    return {
                        "valid": False,
                        "status": "EXPIRED",
                        "message": "This Gate Pass OTP has expired.",
                        "pass_id": rec["id"],
                        "student_name": rec["name"],
                        "register_number": rec["register_number"],
                    }
            except Exception:
                pass

        # Valid & Approved!
        return {
            "valid": True,
            "status": "GRANTED",
            "message": "Gate Pass Approved! Permission Granted.",
            "pass_id": rec["id"],
            "otp": rec["otp"],
            "student_id": rec["student_id"],
            "student_name": rec.get("name") or rec["student_id"],
            "register_number": rec.get("register_number") or "",
            "roll_number": rec.get("roll_number") or "",
            "department": rec.get("department") or "",
            "year": rec.get("year") or "",
            "section": rec.get("section") or "",
            "pass_type": rec["pass_type"],
            "reason": rec["reason"],
            "event_date": rec["event_date"],
            "out_time": rec["out_time"],
            "expected_in_time": rec.get("expected_in_time") or "",
            "faculty_name": rec.get("faculty_decided_by") or "",
            "faculty_time": rec.get("faculty_decided_at") or "",
            "faculty_remarks": rec.get("faculty_remarks") or "",
            "hod_name": rec.get("hod_decided_by") or "",
            "hod_time": rec.get("hod_decided_at") or "",
            "hod_remarks": rec.get("hod_remarks") or "",
            "avatar_url": f"/avatars/{rec['student_id']}.jpg",
            "is_used": rec["is_used"],
        }


def mark_gatepass_exit(pass_id: int, guard_id: str = "Main Gate Guard", remarks: str = "") -> dict:
    """Watchman confirms student exit. Marks pass as used."""
    init_gatepass_table()
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        conn.execute(
            """UPDATE gatepass_requests
               SET is_used = 1, exited_at = ?, guard_id = ?, guard_remarks = ?, status = 'Exited'
               WHERE id = ?""",
            (now, guard_id, remarks, pass_id),
        )
        row = conn.execute("SELECT * FROM gatepass_requests WHERE id = ?", (pass_id,)).fetchone()
        return dict(row) if row else {}


def list_recent_gatepass_exits(limit: int = 20) -> list[dict]:
    """List recent verified exits for the Watchman dashboard/history."""
    init_gatepass_table()
    with db() as conn:
        rows = conn.execute(
            """SELECT g.*, s.name, s.register_number, s.department
               FROM gatepass_requests g
               LEFT JOIN students s ON g.student_id = s.student_id
               WHERE g.is_used = 1
               ORDER BY g.exited_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
