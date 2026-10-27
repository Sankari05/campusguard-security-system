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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gate_incidents (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                guard_id            TEXT DEFAULT 'Main Gate Guard',
                category            TEXT DEFAULT 'General',
                description         TEXT NOT NULL,
                student_id          TEXT DEFAULT '',
                severity            TEXT DEFAULT 'Medium',
                voice_transcript    TEXT DEFAULT '',
                logged_at           TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gi_logged_at ON gate_incidents(logged_at)
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
        rec = dict(row)

    _notify_student(student_id, f"Gate Pass #{new_id} submitted! Sent to Class Incharge for approval.")
    return rec


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
        query += " AND UPPER(s.department) = UPPER(?)"
        params.append(scope["department"])
    if scope.get("year"):
        raw_y = str(scope["year"]).strip()
        dig = "".join([c for c in raw_y if c.isdigit()])
        if dig:
            query += " AND (s.year = ? OR s.year LIKE ? OR s.year LIKE ?)"
            params.extend([raw_y, f"{dig}%", f"{raw_y}%"])
        else:
            query += " AND s.year = ?"
            params.append(raw_y)
    if scope.get("section"):
        query += " AND UPPER(s.section) = UPPER(?)"
        params.append(scope["section"])

    if status:
        query += " AND UPPER(g.status) = UPPER(?)"
        params.append(status)

    query += " ORDER BY g.id DESC"

    with db() as conn:
        rows = conn.execute(query, params).fetchall()
        # Fallback: If scoped by year/section returned empty, but faculty has department,
        # check if there are pending/relevant requests in the department to avoid orphan requests
        if not rows and (scope.get("year") or scope.get("section")) and scope.get("department"):
            dept_query = """
                SELECT g.*, s.name, s.register_number, s.roll_number, s.department,
                       s.year, s.section
                FROM gatepass_requests g
                LEFT JOIN students s ON g.student_id = s.student_id
                WHERE UPPER(s.department) = UPPER(?)
            """
            dparams = [scope["department"]]
            if status:
                dept_query += " AND UPPER(g.status) = UPPER(?)"
                dparams.append(status)
            dept_query += " ORDER BY g.id DESC"
            rows = conn.execute(dept_query, dparams).fetchall()

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
        msg = f"Your Gate Pass #{pass_id} has been verified and approved by Class Incharge ({decided_by}) and forwarded to HOD for final exit authorization." if decision == "Approved" \
              else f"Your Gate Pass #{pass_id} request was rejected by Class Incharge ({decided_by}). Remarks: {remarks}"
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


# ── Gate Incident / Voice Situation Logging ──────────────────
def log_gate_incident(
    guard_id: str = "Main Gate Guard",
    description: str = "",
    category: str = "General",
    student_id: str = "",
    severity: str = "Medium",
    voice_transcript: str = "",
) -> dict:
    """Watchman speaks a situation or logs an incident at the gate."""
    init_gatepass_table()
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO gate_incidents
               (guard_id, category, description, student_id, severity, voice_transcript, logged_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (guard_id, category, description, student_id, severity, voice_transcript, now),
        )
        inc_id = cur.lastrowid
        row = conn.execute("SELECT * FROM gate_incidents WHERE id = ?", (inc_id,)).fetchone()
        return dict(row) if row else {}


def list_gate_incidents(limit: int = 25) -> list[dict]:
    """List recent gate incidents and voice situation logs."""
    init_gatepass_table()
    with db() as conn:
        rows = conn.execute(
            """SELECT * FROM gate_incidents ORDER BY logged_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Voice Command & Natural Language Intelligence Engine ────
# Supports:
#   1. English: "seven four five seven four three", "double seven"
#   2. Tamil Unicode: "ஏழு நான்கு ஐந்து ஏழு நான்கு மூன்று"
#   3. Tanglish (Romanized Tamil): "ezhu naalu anju ezhu naalu moonu", "onnu rendu moonu"
#   4. Mixed code-switching: "student OTP ezhu 4 anju 7 நாலு three check pannunga"
_NUMBER_MAP = {
    # ── English digits & spoken numbers ──
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "oh": "0",

    # ── Tamil Unicode script ──
    "பூஜ்ஜியம்": "0", "ஜீரோ": "0", "சுழியம்": "0",
    "ஒன்று": "1", "ஒன்னு": "1", "ஒரு": "1",
    "இரண்டு": "2", "ரெண்டு": "2", "ரண்டு": "2",
    "மூன்று": "3", "மூணு": "3",
    "நான்கு": "4", "நாலு": "4",
    "ஐந்து": "5", "அஞ்சு": "5",
    "ஆறு": "6",
    "ஏழு": "7",
    "எட்டு": "8",
    "ஒன்பது": "9",
    "பத்து": "10",

    # ── Tanglish (Tamil words written in English / Transliteration) ──
    # 0:
    "poojiyam": "0", "poojyam": "0", "pujiyam": "0", "jeero": "0", "jiro": "0", "sunna": "0", "suzhiyam": "0",
    # 1:
    "onnu": "1", "onru": "1", "ondru": "1", "oru": "1", "oone": "1",
    # 2:
    "rendu": "2", "irandu": "2", "irandhu": "2", "randu": "2", "reandu": "2",
    # 3:
    "moonu": "3", "moondru": "3", "moondhu": "3", "munu": "3", "monu": "3",
    # 4:
    "naalu": "4", "naangu": "4", "nalu": "4", "nangu": "4", "nal": "4",
    # 5:
    "anju": "5", "ainthu": "5", "aindhu": "5", "anchu": "5", "anji": "5",
    # 6:
    "aaru": "6", "aru": "6", "aara": "6",
    # 7:
    "ezhu": "7", "yezhu": "7", "elu": "7", "yelu": "7", "yealu": "7", "yelhu": "7", "ezh": "7",
    # 8:
    "ettu": "8", "yeatu": "8", "yettu": "8", "etu": "8", "eattu": "8",
    # 9:
    "onbadhu": "9", "onbathu": "9", "ombodhu": "9", "ombothu": "9", "onpathu": "9", "onbadu": "9",
    # 10:
    "pathu": "10", "padhu": "10",
}


def process_voice_command(
    transcript: str,
    guard_id: str = "Main Gate Guard",
    active_pass_id: int | None = None,
) -> dict:
    """
    Process watchman spoken voice command with full Tamil, English & Tanglish support:
      1. Phonetic & Code-Switch Normalizer (PCN)
      2. Multi-Intent Classifier (MIR-KDC)
      3. Entity / OTP Extraction
      4. Database Transaction
      5. Synthesized Acoustic Speech Feedback (for Text-To-Speech)
    """
    raw = (transcript or "").strip()
    if not raw:
        return {
            "success": False,
            "intent": "EMPTY",
            "action_taken": "NO_ACTION",
            "spoken_feedback": "No speech detected. Please speak into the microphone.",
            "data": None,
        }

    lower = raw.lower()

    # 1. Normalize numbers in transcript (Tamil + English + Tanglish)
    tokens = lower.split()
    normalized_tokens = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        # Handle 'double X', 'irattai X', 'triple X'
        if tok in ("double", "irattai") and i + 1 < len(tokens):
            next_num = _NUMBER_MAP.get(tokens[i + 1])
            if next_num:
                normalized_tokens.extend([next_num, next_num])
                i += 2
                continue
        elif tok in ("triple", "mummurai") and i + 1 < len(tokens):
            next_num = _NUMBER_MAP.get(tokens[i + 1])
            if next_num:
                normalized_tokens.extend([next_num, next_num, next_num])
                i += 2
                continue

        if tok in _NUMBER_MAP:
            normalized_tokens.append(_NUMBER_MAP[tok])
        else:
            # Check if token is already pure digits
            if tok.isdigit():
                normalized_tokens.append(tok)
            else:
                # Clean punctuation for keyword matching
                clean_tok = "".join(ch for ch in tok if ch.isalnum())
                if clean_tok:
                    if clean_tok in _NUMBER_MAP:
                        normalized_tokens.append(_NUMBER_MAP[clean_tok])
                    else:
                        normalized_tokens.append(clean_tok)
        i += 1

    combined_text = " ".join(normalized_tokens)

    # 2. Extract 6-digit OTP using continuous or spaced digit sliding window
    import re
    otp_candidate = None
    direct_match = re.search(r"\b\d{6}\b", combined_text)
    if direct_match:
        otp_candidate = direct_match.group(0)
    else:
        # Check digit sequences
        digits_only = re.sub(r"\D", "", combined_text)
        if len(digits_only) >= 6:
            otp_candidate = digits_only[:6]

    # ── Intent Route A: VERIFY_OTP ──────────────────────────────
    if otp_candidate:
        verify_res = verify_gatepass_otp(otp_candidate)
        if verify_res.get("valid"):
            name = verify_res.get("student_name", "Student")
            dept = verify_res.get("department", "")
            return {
                "success": True,
                "intent": "VERIFY_OTP",
                "extracted_otp": otp_candidate,
                "action_taken": "VERIFIED_APPROVED",
                "spoken_feedback": f"Gate pass approved for {name}. {dept}. Say 'Confirm' or 'Veliya pogalam' to allow exit.",
                "data": verify_res,
            }
        else:
            msg = verify_res.get("message", "Invalid pass")
            return {
                "success": False,
                "intent": "VERIFY_OTP",
                "extracted_otp": otp_candidate,
                "action_taken": "VERIFIED_DENIED",
                "spoken_feedback": f"Gate pass denied: {msg}",
                "data": verify_res,
            }

    def _matches_any(trigger_list: list[str], text: str) -> bool:
        for t in trigger_list:
            if " " in t:
                if t in text:
                    return True
            else:
                # Whole word match to avoid subword collision (e.g. 'sari' in 'sariyilla')
                if re.search(r"\b" + re.escape(t) + r"\b", text):
                    return True
        return False

    # ── Intent Route B: LOG_INCIDENT / SITUATION REPORT (High Priority) ──
    incident_triggers = [
        # English
        "incident", "problem", "emergency", "medical", "hospital", "ambulance",
        "unauthorized", "accident", "damage", "complaint", "stopped", "fight", "theft",
        # Tamil Unicode
        "பிரச்சனை", "மருத்துவமனை", "ஆம்புலன்ஸ்", "சண்டை", "விபத்து",
        # Tanglish
        "udambu sariyilla", "udambu mudiyala", "faint", "mayakkam", "mayangi", "vizhunthutan", "adi patturuku",
        "sanda", "sandai", "thagaraaru", "thagararu", "vambu", "argue", "vaakuvaadham",
        "illama", "no id", "id card", "id illa", "card illa", "permission illama",
        "gate jump", "wall yeri", "kudhichu", "thappikka", "cross panna", "cross",
        "thaduthu", "thaduthom", "hold pannirukom", "pudichom",
        "parent kooda", "parent vandhurukaanga", "family vandhurukaanga"
    ]
    if _matches_any(incident_triggers, lower):
        category = "Security Incident"
        severity = "Medium"
        if any(w in lower for w in [
            "medical", "hospital", "maruthuvamanai", "ambulance", "accident",
            "udambu sariyilla", "udambu mudiyala", "faint", "mayakkam", "mayangi", "adi patturuku", "விபத்து"
        ]):
            category = "Medical Emergency"
            severity = "High"
        elif any(w in lower for w in [
            "no id", "id card", "illama", "id illa", "card illa", "unauthorized",
            "permission illama", "gate jump", "wall yeri", "kudhichu", "thappikka"
        ]):
            category = "Unauthorized / Missing ID"
            severity = "Low"
        elif any(w in lower for w in ["sanda", "sandai", "fight", "thagaraaru", "argue", "vaakuvaadham", "சண்டை"]):
            category = "Dispute / Misconduct"
            severity = "High"
        elif any(w in lower for w in ["parent", "family", "kooda"]):
            category = "Parent / Visitor Checkout"
            severity = "Low"

        inc_rec = log_gate_incident(
            guard_id=guard_id,
            description=raw,
            category=category,
            severity=severity,
            voice_transcript=raw,
        )
        return {
            "success": True,
            "intent": "LOG_INCIDENT",
            "action_taken": "INCIDENT_LOGGED",
            "spoken_feedback": f"Situation logged under {category}. Incident recorded to security registry.",
            "data": inc_rec,
        }

    # ── Intent Route C: CONFIRM_EXIT (Tanglish + Tamil + English) ───────────
    exit_triggers = [
        # English
        "confirm", "allow", "exit", "left", "passed", "yes", "okay", "ok",
        # Tamil Unicode
        "வெளிய", "போகலாம்", "அனுப்பு", "விடு", "சரி", "திற",
        # Tanglish
        "veliya", "velila", "veliye", "pogalam", "pogattum", "poraaru", "poran", "poranga",
        "anuppu", "anupu", "anupunga", "anuppunga", "vidu", "vidunga",
        "allow pannu", "exit pannu", "confirm pannu", "panni vidu",
        "gate open", "gate thora", "gate theranthudu", "gate thorandhu",
        "sari", "seri", "kelambattum", "kelambalam"
    ]
    if _matches_any(exit_triggers, lower):
        if active_pass_id:
            exit_rec = mark_gatepass_exit(active_pass_id, guard_id, "Voice command confirmed exit")
            return {
                "success": True,
                "intent": "CONFIRM_EXIT",
                "action_taken": "EXIT_CONFIRMED",
                "spoken_feedback": "Exit confirmed. Student is cleared to leave the campus.",
                "data": exit_rec,
            }
        else:
            return {
                "success": False,
                "intent": "CONFIRM_EXIT",
                "action_taken": "NO_PASS_SELECTED",
                "spoken_feedback": "Please speak or verify the student OTP first before confirming exit.",
                "data": None,
            }

    # ── Fallback Route: UNKNOWN INTENT ──────────────────────────
    return {
        "success": False,
        "intent": "UNKNOWN",
        "action_taken": "UNRECOGNIZED",
        "spoken_feedback": "Command not understood. Please speak a 6-digit OTP, say 'Confirm' or 'Veliya pogalam', or describe an incident.",
        "data": {"raw_transcript": raw},
    }
