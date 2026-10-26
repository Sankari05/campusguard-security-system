# =============================================================
# student_portal_db.py — Student self-service portal (DB layer)
#
# Adds:
#   - Login by Register Number + Date of Birth (every login — there
#     is no student password; students cannot set/change one)
#   - Profile view / edit
#   - Avatar upload
#
# Reuses the existing `students` table (columns added via
# database._safe_add_column in database.init_db):
#   password_hash, must_set_password, avatar_path,
#   token_version, last_login
#
# NOTE: password_hash / must_set_password remain in the schema for
# backward compatibility but are intentionally unused by this module —
# login is always Register Number + Date of Birth. See
# api_student_portal.py's LOGIN POLICY note for details.
# =============================================================
import logging
from datetime import datetime
from database import db

log = logging.getLogger(__name__)

# Fields a student is allowed to edit on their own profile.
# register_number, date_of_birth, student_id, department, course,
# year, section are institution-controlled and NOT editable here.
EDITABLE_FIELDS = {
    "student_email",
    "student_mobile",
    "parent_email",
    "parent_mobile",
    "first_name",
    "last_name",
}


def _norm_dob(dob: str) -> str:
    """Normalise a DOB string to YYYY-MM-DD for comparison."""
    return (dob or "").strip()


def get_student_by_register_number(register_number: str):
    """Look up a student by register number (case-insensitive)."""
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE UPPER(register_number)=UPPER(?) AND active=1",
            (register_number.strip(),),
        ).fetchone()
        return dict(row) if row else None


def verify_register_and_dob(register_number: str, dob: str):
    """
    The student portal's ONLY authentication method, used on EVERY
    login (not just the first). Register Number + Date of Birth must
    match the institution's record exactly.
    Returns the student dict on match, else None.
    """
    student = get_student_by_register_number(register_number)
    if not student:
        return None
    if _norm_dob(student.get("date_of_birth")) == _norm_dob(dob):
        return student
    return None


def touch_last_login(student_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE students SET last_login=datetime('now','localtime') WHERE student_id=?",
            (student_id,),
        )


def get_token_version(student_id: str) -> int:
    with db() as conn:
        row = conn.execute(
            "SELECT token_version FROM students WHERE student_id=?",
            (student_id,),
        ).fetchone()
        return int(row["token_version"]) if row and row["token_version"] is not None else 0


def bump_token_version(student_id: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE students SET token_version = COALESCE(token_version,0) + 1 WHERE student_id=?",
            (student_id,),
        )


def get_profile(student_id: str):
    with db() as conn:
        row = conn.execute(
            "SELECT student_id, name, register_number, roll_number, first_name, "
            "last_name, gender, date_of_birth, department, course, year, section, "
            "student_email, parent_email, student_mobile, parent_mobile, status, "
            "avatar_path, last_login FROM students WHERE student_id=? AND active=1",
            (student_id,),
        ).fetchone()
        return dict(row) if row else None


def update_profile(student_id: str, fields: dict) -> dict | None:
    """
    Update only whitelisted, student-editable fields.
    Returns the refreshed profile dict, or None if student not found.
    """
    safe = {k: v for k, v in fields.items() if k in EDITABLE_FIELDS and v is not None}
    if not safe:
        return get_profile(student_id)

    set_clause = ", ".join(f"{k}=?" for k in safe)
    values = list(safe.values()) + [student_id]
    with db() as conn:
        conn.execute(
            f"UPDATE students SET {set_clause} WHERE student_id=?",
            values,
        )
    return get_profile(student_id)


def update_avatar(student_id: str, avatar_path: str) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE students SET avatar_path=? WHERE student_id=?",
            (avatar_path, student_id),
        )


# =============================================================
# Dashboard summary
# =============================================================
def _get_attendance_percent(student_id: str):
    """Overall attendance % from the existing student_attendance table.
    Returns None if the table is missing or the student has no records yet."""
    try:
        with db() as conn:
            row = conn.execute(
                """SELECT
                       COUNT(*) AS total,
                       SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) AS present
                   FROM student_attendance
                   WHERE student_id=?""",
                (student_id,),
            ).fetchone()
    except Exception:
        log.exception("Could not read student_attendance for dashboard summary")
        return None

    if not row or not row["total"]:
        return None
    return round((row["present"] or 0) * 100.0 / row["total"], 1)


def _get_current_semester(student_id: str):
    """Most recent semester on record in student_academics, if any.
    Falls back to None — the existing `year` field is shown elsewhere."""
    try:
        import database_academic as dac
        records = dac.get_for_student(student_id)
    except Exception:
        log.exception("Could not read student_academics for dashboard summary")
        return None

    if not records:
        return None
    return records[0].get("semester")


def get_dashboard_summary(student_id: str) -> dict:
    """
    Aggregated data for the Dashboard Home panel.
    Leave/Events/Assignments are not implemented yet — they return
    safe zero/empty defaults until those modules are added.
    """
    profile = get_profile(student_id) or {}
    return {
        "name": profile.get("name"),
        "attendance_percent": _get_attendance_percent(student_id),
        "current_semester": _get_current_semester(student_id),
        "pending_leave_requests": 0,
        "upcoming_events": [],
        "assignment_deadlines": [],
    }


# =============================================================
# Attendance summary (overall + subject-wise)
# =============================================================
def get_attendance_summary(student_id: str) -> dict:
    """
    Overall + subject-wise attendance %, computed from the existing
    student_attendance table (status='Present' vs total marked rows).
    Returns empty/zero values if the student has no attendance rows yet.
    """
    try:
        with db() as conn:
            overall_row = conn.execute(
                """SELECT
                       COUNT(*) AS total,
                       SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) AS present
                   FROM student_attendance
                   WHERE student_id=?""",
                (student_id,),
            ).fetchone()

            subject_rows = conn.execute(
                """SELECT
                       subject_id,
                       COUNT(*) AS total,
                       SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) AS present
                   FROM student_attendance
                   WHERE student_id=?
                   GROUP BY subject_id
                   ORDER BY subject_id""",
                (student_id,),
            ).fetchall()
    except Exception:
        log.exception("Could not read student_attendance for attendance summary")
        return {"overall_percent": None, "subjects": []}

    overall_total = overall_row["total"] if overall_row else 0
    overall_present = overall_row["present"] if overall_row else 0
    overall_percent = (
        round(overall_present * 100.0 / overall_total, 1) if overall_total else None
    )

    # Try to resolve friendly subject names via the existing courses table
    # (keyed by course_code == subject_id). Falls back to the raw code.
    name_lookup = {}
    try:
        profile = get_profile(student_id) or {}
        dept = profile.get("department")
        if dept:
            with db() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT course_code, course_name FROM courses WHERE dept=?",
                    (dept,),
                ).fetchall()
                name_lookup = {r["course_code"]: r["course_name"] for r in rows}
    except Exception:
        pass  # courses table may not exist / no match — fall back to raw subject_id

    subjects = []
    for row in subject_rows:
        subject_id = (row["subject_id"] or "").strip() or "Unspecified"
        total = row["total"] or 0
        present = row["present"] or 0
        percent = round(present * 100.0 / total, 1) if total else 0
        subjects.append({
            "subject_id": subject_id,
            "subject_name": name_lookup.get(subject_id, subject_id),
            "percent": percent,
            "present": present,
            "total": total,
        })

    return {"overall_percent": overall_percent, "subjects": subjects}


# =============================================================
# Attendance detail — date-wise / period-wise full log
# (new read-only view over existing student_attendance table)
# =============================================================
def get_attendance_detail(student_id: str) -> dict:
    """
    Date-wise, period-wise full attendance log for the student portal.
    Read-only — queries the existing student_attendance table only,
    no new table or column is added.
    Returns records sorted newest-first, plus present/absent counts.
    """
    try:
        with db() as conn:
            rows = conn.execute(
                """SELECT date, time, period, subject_id, status, confidence
                   FROM student_attendance
                   WHERE student_id=?
                   ORDER BY date DESC, period ASC""",
                (student_id,),
            ).fetchall()

            # Resolve friendly subject names from courses table (same
            # logic used by get_attendance_summary above — falls back to
            # raw subject_id code if courses table is absent/no match).
            name_lookup = {}
            try:
                profile = get_profile(student_id) or {}
                dept = profile.get("department")
                if dept:
                    course_rows = conn.execute(
                        "SELECT DISTINCT course_code, course_name FROM courses WHERE dept=?",
                        (dept,),
                    ).fetchall()
                    name_lookup = {r["course_code"]: r["course_name"] for r in course_rows}
            except Exception:
                pass

    except Exception:
        log.exception("Could not read student_attendance for detail view")
        return {"records": [], "total": 0, "present": 0, "absent": 0}

    records = []
    present_count = 0
    absent_count = 0
    for row in rows:
        subj_id = (row["subject_id"] or "").strip() or "General"
        status = row["status"] or "Present"
        if status == "Present":
            present_count += 1
        else:
            absent_count += 1
        records.append({
            "date": row["date"] or "",
            "time": row["time"] or "",
            "period": row["period"] or "",
            "subject_id": subj_id,
            "subject_name": name_lookup.get(subj_id, subj_id),
            "status": status,
            "confidence": round(row["confidence"] or 0, 2),
        })

    return {
        "records": records,
        "total": len(records),
        "present": present_count,
        "absent": absent_count,
    }


# =============================================================
# Internal marks (CIA 1 / CIA 2 / CIA 3 / Model Exam)
# =============================================================
def init_internal_marks_table():
    """Safe to call on every startup — CREATE TABLE IF NOT EXISTS only.
    No existing CIA/internal-marks table was found elsewhere in the
    codebase, so this is a new, additive table."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_internal_marks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  TEXT NOT NULL,
                subject_id  TEXT NOT NULL,
                cia1        REAL DEFAULT 0,
                cia2        REAL DEFAULT 0,
                cia3        REAL DEFAULT 0,
                model_exam  REAL DEFAULT 0,
                max_marks   REAL DEFAULT 100,
                updated_at  TEXT,
                updated_by  TEXT,
                UNIQUE(student_id, subject_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_intmarks_student ON student_internal_marks(student_id)
        """)


def get_marks_summary(student_id: str) -> dict:
    """
    CIA1 / CIA2 / CIA3 / Model Exam + Total per subject for the logged-in
    student, read from student_internal_marks (created above if missing).
    Returns an empty list if no marks have been entered yet — no error.
    """
    init_internal_marks_table()
    try:
        with db() as conn:
            rows = conn.execute(
                """SELECT subject_id, cia1, cia2, cia3, model_exam, max_marks
                   FROM student_internal_marks
                   WHERE student_id=?
                   ORDER BY subject_id""",
                (student_id,),
            ).fetchall()
    except Exception:
        log.exception("Could not read student_internal_marks")
        return {"subjects": []}

    # Reuse the same courses-table name lookup used for attendance.
    name_lookup = {}
    try:
        profile = get_profile(student_id) or {}
        dept = profile.get("department")
        if dept:
            with db() as conn:
                course_rows = conn.execute(
                    "SELECT DISTINCT course_code, course_name FROM courses WHERE dept=?",
                    (dept,),
                ).fetchall()
                name_lookup = {r["course_code"]: r["course_name"] for r in course_rows}
    except Exception:
        pass

    subjects = []
    for row in rows:
        subject_id = (row["subject_id"] or "").strip() or "Unspecified"
        cia1 = row["cia1"] or 0
        cia2 = row["cia2"] or 0
        cia3 = row["cia3"] or 0
        model_exam = row["model_exam"] or 0
        total = round(cia1 + cia2 + cia3 + model_exam, 1)
        subjects.append({
            "subject_id": subject_id,
            "subject_name": name_lookup.get(subject_id, subject_id),
            "cia1": cia1,
            "cia2": cia2,
            "cia3": cia3,
            "model_exam": model_exam,
            "max_marks": row["max_marks"] or 100,
            "total": total,
        })

    return {"subjects": subjects}


# =============================================================
# Semester results (reuses database_academic.student_academics)
# =============================================================
def get_results_summary(student_id: str) -> dict:
    """
    Semester-wise SGPA/CGPA + backlog info for the logged-in student,
    read from the existing student_academics table (database_academic.py).
    No new table is created here — this only formats that data for the
    student-facing Results panel.
    """
    try:
        import database_academic as dac
        records = dac.get_for_student(student_id)
    except Exception:
        log.exception("Could not read student_academics for results summary")
        return {"semesters": [], "cgpa": None}

    if not records:
        return {"semesters": [], "cgpa": None}

    # records are ordered semester DESC (database_academic.get_for_student)
    semesters = []
    for r in records:
        backlog_subjects = r.get("backlog_subjects") or ""
        semesters.append({
            "semester": r.get("semester"),
            "sgpa": r.get("sgpa"),
            "cgpa": r.get("cgpa"),
            "backlog_count": r.get("backlog_count") or 0,
            "backlog_subjects": [s.strip() for s in backlog_subjects.split(",") if s.strip()],
        })

    # Latest semester's CGPA is the "current" CGPA shown at the top.
    current_cgpa = semesters[0].get("cgpa") if semesters else None

    # Sort ascending by semester for a natural Semester 1 -> N display.
    semesters_sorted = sorted(semesters, key=lambda s: s["semester"] or 0)

    return {"semesters": semesters_sorted, "cgpa": current_cgpa}


# =============================================================
# Timetable (reuses database_extras.get_student_timetable)
# =============================================================
_DAY_ORDER = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
_TODAY_CODE = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]  # datetime.weekday() 0=Mon


def get_timetable_summary(student_id: str) -> dict:
    """
    Weekly timetable for the logged-in student, wrapping the existing
    database_extras.get_student_timetable(dept, year, section, semester)
    used by the faculty/HOD timetable features — no new table is created.
    """
    profile = get_profile(student_id) or {}
    dept = profile.get("department")
    year = profile.get("year")
    section = profile.get("section")
    semester = _get_current_semester(student_id)

    if not (dept and year and section):
        return {"days": [], "today": None}

    # students.year is stored as free text (e.g. "3", "3rd Year"); the
    # timetable table expects an integer year — extract the first number.
    import re
    year_match = re.search(r"\d+", str(year))
    if not year_match:
        return {"days": [], "today": None}
    year_int = int(year_match.group())

    try:
        import database_extras as dbe
        # Try with semester filter first; fall back to without if no rows
        # (covers cases where current-semester lookup doesn't line up
        # exactly with how the timetable was seeded).
        rows = dbe.get_student_timetable(dept, year_int, section, semester)
        if not rows and semester is not None:
            rows = dbe.get_student_timetable(dept, year_int, section, None)
    except Exception:
        log.exception("Could not read student_timetable for timetable panel")
        return {"days": [], "today": None}

    by_day = {d: [] for d in _DAY_ORDER}
    for r in rows:
        day = (r.get("day_of_week") or "").upper().strip()
        if day not in by_day:
            continue
        by_day[day].append({
            "period_no": r.get("period_no"),
            "course_code": r.get("course_code"),
            "course_name": r.get("course_name"),
            "faculty_name": r.get("faculty_name") or "",
            "room": r.get("room") or "",
        })

    days = []
    for d in _DAY_ORDER:
        periods = sorted(by_day[d], key=lambda p: p["period_no"] or 0)
        days.append({"day": d, "periods": periods})

    today_code = _TODAY_CODE[datetime.now().weekday()]
    today = today_code if today_code in _DAY_ORDER else None

    return {"days": days, "today": today}


# =============================================================
# Leave Requests (new, additive table — no existing leave table
# was found anywhere else in this codebase)
# =============================================================
def init_leave_table():
    """Safe to call on every startup — CREATE TABLE IF NOT EXISTS only."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_leave_requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  TEXT NOT NULL,
                from_date   TEXT NOT NULL,
                to_date     TEXT NOT NULL,
                reason      TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'Pending',  -- Pending/Approved/Rejected
                applied_at  TEXT NOT NULL,
                decided_by  TEXT DEFAULT '',
                decided_at  TEXT DEFAULT '',
                remarks     TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_leave_student ON student_leave_requests(student_id)
        """)


def apply_leave(student_id: str, from_date: str, to_date: str, reason: str) -> dict:
    init_leave_table()

    # ── Real-world date validation ──
    # from_date/to_date must be valid calendar dates, not in the past
    # (relative to the server's current date), and to_date >= from_date.
    try:
        f_dt = datetime.strptime(from_date, "%Y-%m-%d").date()
        t_dt = datetime.strptime(to_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Dates must be in YYYY-MM-DD format.")

    today = datetime.now().date()
    if f_dt < today:
        raise ValueError("From date cannot be in the past.")
    if t_dt < f_dt:
        raise ValueError("To date cannot be before the from date.")

    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO student_leave_requests
               (student_id, from_date, to_date, reason, status, applied_at)
               VALUES (?, ?, ?, ?, 'Pending', ?)""",
            (student_id, from_date, to_date, reason, now),
        )
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM student_leave_requests WHERE id=?", (new_id,)
        ).fetchone()
        return dict(row)


def get_leave_history(student_id: str) -> list:
    init_leave_table()
    with db() as conn:
        rows = conn.execute(
            """SELECT id, from_date, to_date, reason, status, applied_at, remarks
               FROM student_leave_requests
               WHERE student_id=?
               ORDER BY applied_at DESC""",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# =============================================================
# OD Requests
# Reuses the existing `od_requests` table created by
# database_faculty_requests.py (Phase 1 — Faculty Request
# Management) so the Faculty approval UI sees the exact same rows.
# No new table is created here.
# =============================================================
def apply_od(student_id: str, event_name: str, event_date: str, reason: str) -> dict:
    # Ensures od_requests exists even if database_faculty_requests.py
    # hasn't been imported/initialized yet in this process.
    import database_faculty_requests as freq
    freq.init_od_table()

    # ── Real-world date validation (same rule as apply_leave) ──
    try:
        e_dt = datetime.strptime(event_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Event date must be in YYYY-MM-DD format.")

    today = datetime.now().date()
    if e_dt < today:
        raise ValueError("Event date cannot be in the past.")

    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO od_requests
               (student_id, event_name, event_date, reason, status, applied_at)
               VALUES (?, ?, ?, ?, 'Pending', ?)""",
            (student_id, event_name, event_date, reason, now),
        )
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM od_requests WHERE id=?", (new_id,)
        ).fetchone()
        return dict(row)


def get_od_history(student_id: str) -> list:
    import database_faculty_requests as freq
    freq.init_od_table()
    with db() as conn:
        rows = conn.execute(
            """SELECT id, event_name, event_date, reason, status, applied_at, remarks
               FROM od_requests
               WHERE student_id=?
               ORDER BY applied_at DESC""",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# =============================================================
# Request Tracker (Prompt 5)
# Merges student_leave_requests + od_requests into one timeline so
# the student can see every request's journey.
#
# Leave requests stay single-stage (Faculty-only decision, per the
# business rule applied in Step 2) and keep the original 3-stage
# stepper:
#   Submitted -> Reviewed -> Approved/Rejected
#
# OD requests now go through the two-stage Faculty -> HOD pipeline
# (Step 1), so Step 7 expands their stepper to FOUR stages instead of
# three:
#   Submitted -> Faculty Review -> HOD Review -> Approved/Rejected
# Each request also carries a `stages` list (label/state/date/remarks)
# so the frontend can render a stepper without re-deriving the logic.
# =============================================================
def _tracker_stages(status: str, applied_at: str, decided_at: str, decided_by: str, remarks: str) -> list:
    status = (status or "Pending").strip().title()
    is_decided = status in ("Approved", "Rejected")

    stages = [
        {
            "label": "Submitted",
            "state": "done",
            "date": applied_at or "",
            "detail": "Request submitted.",
        },
        {
            "label": "Reviewed",
            # "active" = currently sitting with faculty/HOD, awaiting a decision
            "state": "done" if is_decided else "active",
            "date": decided_at if is_decided else "",
            "detail": (
                f"Reviewed by {decided_by}." if (is_decided and decided_by)
                else ("Reviewed." if is_decided else "Awaiting review.")
            ),
        },
        {
            "label": "Approved" if status == "Approved" else "Rejected" if status == "Rejected" else "Decision",
            "state": (
                "done" if status == "Approved"
                else "rejected" if status == "Rejected"
                else "pending"
            ),
            "date": decided_at if is_decided else "",
            "detail": (
                remarks if (is_decided and remarks)
                else (f"{status} by {decided_by}." if (is_decided and decided_by) else "Pending decision.")
            ),
        },
    ]
    return stages


def _od_final_detail(status: str, faculty_decided_by: str, hod_decided_by: str,
                      faculty_remarks: str, hod_remarks: str) -> str:
    """The headline text for an OD request's final ('Decision') stage,
    summarizing exactly where the two-stage Faculty -> HOD pipeline
    currently stands (Step 7 mapping):

      status='Forwarded'                       -> "Faculty Review: Approved, HOD Review: Pending"
      status='Rejected', hod_decided_by empty   -> "Rejected by Faculty"   (never reached HOD)
      status='Rejected', hod_decided_by set     -> "Rejected by HOD"
      status='Approved'                          -> both stages cleared HOD has the final say
      status='Pending'                           -> neither stage has acted yet
    """
    if status == "Forwarded":
        return "Faculty Review: Approved, HOD Review: Pending"
    if status == "Rejected":
        if hod_decided_by:
            base = "Rejected by HOD"
            return f"{base}. Remarks: {hod_remarks}" if hod_remarks else base
        base = "Rejected by Faculty"
        return f"{base}. Remarks: {faculty_remarks}" if faculty_remarks else base
    if status == "Approved":
        if not hod_decided_by:
            # Legacy single-stage row (pre-dates the Step 1 two-stage
            # pipeline): approved directly by faculty, never touched by
            # HOD. Step 9's migrate_od_two_stage.py backfills
            # faculty_status/faculty_decided_by for these rows, but
            # hod_decided_by is intentionally left blank since HOD truly
            # never reviewed it — that's the signal used here.
            return "Approved (legacy single-stage decision)"
        return "Faculty Review: Approved, HOD Review: Approved"
    # Pending — hasn't even reached faculty's decision yet
    return "Faculty Review: Pending, HOD Review: Pending"


def _tracker_stages_od(status: str, applied_at: str,
                        faculty_status: str, faculty_decided_by: str,
                        faculty_decided_at: str, faculty_remarks: str,
                        hod_status: str, hod_decided_by: str,
                        hod_decided_at: str, hod_remarks: str) -> list:
    """Step 7 — OD-specific 4-stage stepper:
        Submitted -> Faculty Review -> HOD Review -> Approved/Rejected

    Unlike leave requests (single-stage, see _tracker_stages above), OD
    requests go through the two-stage Faculty -> HOD pipeline added in
    Step 1, so the tracker needs to surface both decisions separately
    instead of collapsing them into one generic "Reviewed" step.

    status is one of: Pending / Forwarded / Approved / Rejected.
      - Pending:   awaiting Faculty decision (stage 2 not yet reached)
      - Forwarded: Faculty approved; awaiting HOD's final decision
      - Approved:  HOD gave final approval
      - Rejected:  rejected at either the Faculty or HOD stage —
                    distinguished below by whether hod_decided_by is set
    """
    status = (status or "Pending").strip().title()
    faculty_decided = bool(faculty_status)
    hod_decided = bool(hod_decided_by)
    rejected_by_faculty = status == "Rejected" and not hod_decided
    # Under the new pipeline, status only ever becomes 'Approved' via
    # hod_decide_od_request(), which always sets hod_decided_by in the
    # same write -- so 'Approved' with no hod_decided_by can only be a
    # legacy single-stage row backfilled by Step 9's migration script.
    approved_legacy = status == "Approved" and not hod_decided

    # Stage 1 — Submitted
    stages = [
        {
            "label": "Submitted",
            "state": "done",
            "date": applied_at or "",
            "detail": "Request submitted.",
        },
    ]

    # Stage 2 — Faculty Review
    if not faculty_decided:
        f_state, f_date = "active", ""
        f_detail = "Awaiting faculty review."
    else:
        f_state = "done" if faculty_status == "Approved" else "rejected"
        f_date = faculty_decided_at or ""
        f_detail = f"{faculty_status} by {faculty_decided_by}." if faculty_decided_by else f"{faculty_status}."
        if faculty_remarks:
            f_detail += f" Remarks: {faculty_remarks}"
    stages.append({"label": "Faculty Review", "state": f_state, "date": f_date, "detail": f_detail})

    # Stage 3 — HOD Review
    if rejected_by_faculty:
        # Faculty rejected at stage 2 — the request never reached HOD.
        h_state, h_date = "skipped", ""
        h_detail = "Not applicable — rejected at Faculty stage."
    elif approved_legacy:
        # Legacy single-stage approval (see Step 9) — HOD never reviewed it.
        h_state, h_date = "skipped", ""
        h_detail = "Not applicable — approved under the previous single-stage process."
    elif hod_decided:
        h_state = "done" if hod_status == "Approved" else "rejected"
        h_date = hod_decided_at or ""
        h_detail = f"{hod_status} by {hod_decided_by}." if hod_decided_by else f"{hod_status}."
        if hod_remarks:
            h_detail += f" Remarks: {hod_remarks}"
    elif status == "Forwarded":
        h_state, h_date = "active", ""
        h_detail = "Awaiting HOD review."
    else:
        # status == 'Pending' — hasn't even cleared Faculty yet
        h_state, h_date = "pending", ""
        h_detail = "Awaiting Faculty approval first."
    stages.append({"label": "HOD Review", "state": h_state, "date": h_date, "detail": h_detail})

    # Stage 4 — final decision
    final_label = "Approved" if status == "Approved" else "Rejected" if status == "Rejected" else "Decision"
    final_state = "done" if status == "Approved" else "rejected" if status == "Rejected" else "pending"
    final_date = (
        hod_decided_at if (status == "Approved" and hod_decided)
        else faculty_decided_at if (status == "Approved" and not hod_decided)  # legacy, see Step 9
        else hod_decided_at if (status == "Rejected" and hod_decided)
        else faculty_decided_at if (status == "Rejected" and not hod_decided)
        else ""
    )
    final_detail = _od_final_detail(status, faculty_decided_by, hod_decided_by, faculty_remarks, hod_remarks)
    stages.append({"label": final_label, "state": final_state, "date": final_date or "", "detail": final_detail})

    return stages


def get_request_tracker(student_id: str) -> list:
    """
    Returns a single, time-sorted (most recent first) list combining
    both request types. Each item:
      {
        type: "leave" | "od",
        id, status, applied_at, decided_at, decided_by, remarks,
        title: human-readable summary line,
        stages: [ {label, state, date, detail}, ... ]   // for the stepper UI
        ...plus the type-specific raw fields (from_date/to_date or
           event_name/event_date) for any extra detail the UI wants.
      }

    Leave items get the original 3-stage stepper (_tracker_stages).
    OD items get the 4-stage Faculty -> HOD stepper added in Step 7
    (_tracker_stages_od), since od_requests now carries separate
    faculty_*/hod_* decision columns (Step 1) instead of one flat
    decided_by/decided_at/remarks.
    """
    init_leave_table()
    import database_faculty_requests as freq
    freq.init_od_table()

    with db() as conn:
        leave_rows = conn.execute(
            """SELECT id, from_date, to_date, reason, status, applied_at,
                      decided_by, decided_at, remarks
               FROM student_leave_requests
               WHERE student_id=?""",
            (student_id,),
        ).fetchall()
        od_rows = conn.execute(
            """SELECT id, event_name, event_date, reason, status, applied_at,
                      decided_by, decided_at, remarks,
                      faculty_status, faculty_decided_by, faculty_decided_at, faculty_remarks,
                      hod_status, hod_decided_by, hod_decided_at, hod_remarks
               FROM od_requests
               WHERE student_id=?""",
            (student_id,),
        ).fetchall()

    timeline = []

    for r in leave_rows:
        r = dict(r)
        timeline.append({
            "type": "leave",
            "id": r["id"],
            "title": f"Leave — {r['from_date']} to {r['to_date']}",
            "from_date": r["from_date"],
            "to_date": r["to_date"],
            "reason": r["reason"],
            "status": r["status"] or "Pending",
            "applied_at": r["applied_at"],
            "decided_by": r["decided_by"] or "",
            "decided_at": r["decided_at"] or "",
            "remarks": r["remarks"] or "",
            "stages": _tracker_stages(
                r["status"], r["applied_at"], r["decided_at"], r["decided_by"], r["remarks"]
            ),
        })

    for r in od_rows:
        r = dict(r)
        timeline.append({
            "type": "od",
            "id": r["id"],
            "title": f"OD — {r['event_name']} ({r['event_date']})",
            "event_name": r["event_name"],
            "event_date": r["event_date"],
            "reason": r["reason"],
            "status": r["status"] or "Pending",
            "applied_at": r["applied_at"],
            "decided_by": r["decided_by"] or "",
            "decided_at": r["decided_at"] or "",
            "remarks": r["remarks"] or "",
            "faculty_status": r["faculty_status"] or "",
            "faculty_decided_by": r["faculty_decided_by"] or "",
            "faculty_decided_at": r["faculty_decided_at"] or "",
            "faculty_remarks": r["faculty_remarks"] or "",
            "hod_status": r["hod_status"] or "",
            "hod_decided_by": r["hod_decided_by"] or "",
            "hod_decided_at": r["hod_decided_at"] or "",
            "hod_remarks": r["hod_remarks"] or "",
            "stages": _tracker_stages_od(
                r["status"], r["applied_at"],
                r["faculty_status"], r["faculty_decided_by"], r["faculty_decided_at"], r["faculty_remarks"],
                r["hod_status"], r["hod_decided_by"], r["hod_decided_at"], r["hod_remarks"],
            ),
        })

    # Most recent submission first
    timeline.sort(key=lambda x: x["applied_at"] or "", reverse=True)
    return timeline


# =============================================================
# Notifications (new, additive table)
#
# Populated by database_faculty_requests.py whenever
# decide_leave_request()/decide_od_request() change a request's
# status to Approved/Rejected (wired there — no duplicate decision
# logic lives in this module). The student bell panel reads from
# this table only.
# =============================================================
def init_notifications_table():
    """Safe to call on every startup — CREATE TABLE IF NOT EXISTS only."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id  TEXT NOT NULL,
                message     TEXT NOT NULL,
                is_read     INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notif_student ON student_notifications(student_id)
        """)


def add_notification(student_id: str, message: str) -> dict:
    """Insert a new notification for a student. Returns the created row.
    Called from database_faculty_requests.py on leave/OD decisions."""
    init_notifications_table()
    now = datetime.now().isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO student_notifications (student_id, message, is_read, created_at)
               VALUES (?, ?, 0, ?)""",
            (student_id, message, now),
        )
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT * FROM student_notifications WHERE id=?", (new_id,)
        ).fetchone()
        return dict(row)


def get_notifications(student_id: str) -> list:
    init_notifications_table()
    with db() as conn:
        rows = conn.execute(
            """SELECT id, message, is_read, created_at
               FROM student_notifications
               WHERE student_id=?
               ORDER BY created_at DESC, id DESC""",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_unread_notification_count(student_id: str) -> int:
    init_notifications_table()
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM student_notifications WHERE student_id=? AND is_read=0",
            (student_id,),
        ).fetchone()
        return int(row[0]) if row else 0


def mark_notification_read(student_id: str, notif_id: int) -> dict | None:
    """Marks a single notification as read. Scoped to student_id so a
    student can only mark their own notifications. Returns the updated
    row, or None if no matching (unowned/missing) notification exists."""
    init_notifications_table()
    with db() as conn:
        cur = conn.execute(
            "UPDATE student_notifications SET is_read=1 WHERE id=? AND student_id=?",
            (notif_id, student_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, message, is_read, created_at FROM student_notifications WHERE id=?",
            (notif_id,),
        ).fetchone()
        return dict(row) if row else None
