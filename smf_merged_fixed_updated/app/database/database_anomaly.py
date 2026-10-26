# =============================================================
# database_anomaly.py — NEW FILE (additive only)
#
# Pattern-based anomaly detection on top of the EXISTING
# student_attendance table. Does not alter any existing table.
# Adds one new table: anomaly_flags.
# =============================================================
import logging
from datetime import datetime, timedelta

from database import db  # reuse the existing db() context manager

log = logging.getLogger(__name__)


def init_anomaly_table():
    """Safe to call on every startup — CREATE TABLE IF NOT EXISTS only."""
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_flags (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,         -- 'student' or 'faculty'
                entity_id   TEXT NOT NULL,
                name        TEXT,
                department  TEXT,
                section     TEXT,
                flag_type   TEXT NOT NULL,         -- 'consecutive_absence' | 'declining_trend'
                severity    TEXT NOT NULL,         -- 'warning' | 'critical'
                detail      TEXT,
                detected_at TEXT,
                resolved    INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomaly_active
            ON anomaly_flags (resolved, entity_type)
        """)


# ── Detector 1: consecutive absence streaks ─────────────────────
def detect_consecutive_absences(conn, min_days: int = 3, window_days: int = 30) -> list:
    """
    Finds students with `min_days` or more CONSECUTIVE calendar days
    marked Absent (or simply missing from the present log) within the
    last `window_days`. Uses the existing student_attendance table —
    a day counts as "present" if there's a PRESENT row; any school day
    in the window without one counts as absent for that student.
    """
    cutoff = (datetime.now() - timedelta(days=window_days)).strftime("%Y-%m-%d")

    # All school days that occurred in the window (any status logged)
    school_days = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM student_attendance WHERE date >= ? ORDER BY date",
        (cutoff,)
    ).fetchall()]
    if len(school_days) < min_days:
        return []

    students = conn.execute(
        "SELECT student_id, name, department, section FROM students WHERE active=1"
    ).fetchall()

    results = []
    for srow in students:
        sid, name, dept, section = srow[0], srow[1], srow[2], srow[3]
        present_days = set(r[0] for r in conn.execute(
            "SELECT DISTINCT date FROM student_attendance "
            "WHERE student_id=? AND date >= ? AND UPPER(status)='PRESENT'",
            (sid, cutoff)
        ).fetchall())

        # walk school_days, find longest current/recent absence streak
        streak = 0
        max_streak = 0
        for d in school_days:
            if d not in present_days:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        # only care about a streak that is STILL ongoing (ends at the most
        # recent school day) so we don't flag old, already-resolved gaps
        recent_streak = 0
        for d in reversed(school_days):
            if d not in present_days:
                recent_streak += 1
            else:
                break

        if recent_streak >= min_days:
            results.append({
                "entity_type": "student",
                "entity_id": sid,
                "name": name,
                "department": dept,
                "section": section,
                "flag_type": "consecutive_absence",
                "severity": "critical" if recent_streak >= 5 else "warning",
                "detail": f"{name or sid} has been absent for {recent_streak} consecutive school days.",
            })
    return results


# ── Detector 2: declining weekly trend ───────────────────────────
def detect_declining_trend(conn, weeks: int = 4) -> list:
    """
    Compares attendance % week-over-week per department/section group.
    Flags a group if it has dropped for `weeks` consecutive weeks.
    """
    today = datetime.now()
    week_buckets = []  # list of (start, end) tuples, oldest first
    for w in range(weeks, 0, -1):
        end = today - timedelta(days=7 * (w - 1))
        start = end - timedelta(days=7)
        week_buckets.append((start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))

    groups = conn.execute(
        "SELECT DISTINCT department, section FROM students WHERE active=1"
    ).fetchall()

    results = []
    for dept, section in groups:
        if not dept and not section:
            continue
        weekly_pcts = []
        for start, end in week_buckets:
            row = conn.execute("""
                SELECT
                  COUNT(DISTINCT CASE WHEN UPPER(sa.status)='PRESENT' THEN sa.student_id||sa.date END),
                  COUNT(DISTINCT s.student_id)
                FROM students s
                LEFT JOIN student_attendance sa
                  ON s.student_id = sa.student_id AND sa.date >= ? AND sa.date < ?
                WHERE s.active=1 AND COALESCE(s.department,'')=COALESCE(?,'')
                  AND COALESCE(s.section,'')=COALESCE(?,'')
            """, (start, end, dept, section)).fetchone()
            present, total = row[0] or 0, row[1] or 1
            weekly_pcts.append(round(present / total * 100, 1) if total else 0.0)

        # check strictly non-increasing trend across the whole window
        is_declining = all(
            weekly_pcts[i] <= weekly_pcts[i - 1] for i in range(1, len(weekly_pcts))
        ) and (weekly_pcts[0] - weekly_pcts[-1] >= 5)  # at least a 5-point drop overall

        if is_declining:
            results.append({
                "entity_type": "student",
                "entity_id": f"{dept or '—'}-{section or '—'}",
                "name": f"{dept or 'Dept'} Section {section or '-'}",
                "department": dept,
                "section": section,
                "flag_type": "declining_trend",
                "severity": "critical" if weekly_pcts[-1] < 60 else "warning",
                "detail": (
                    f"{dept or 'Dept'} Section {section or '-'} attendance has been "
                    f"declining for {weeks} consecutive weeks "
                    f"({weekly_pcts[0]}% → {weekly_pcts[-1]}%)."
                ),
            })
    return results


# ── Orchestrator ──────────────────────────────────────────────
def run_anomaly_scan() -> dict:
    """
    Runs both detectors and inserts NEW flags into anomaly_flags,
    skipping duplicates (same entity_id + flag_type already unresolved).
    Returns a small summary dict.
    """
    init_anomaly_table()
    inserted = 0
    with db() as conn:
        found = detect_consecutive_absences(conn) + detect_declining_trend(conn)

        for f in found:
            existing = conn.execute(
                "SELECT id FROM anomaly_flags WHERE entity_id=? AND flag_type=? AND resolved=0",
                (f["entity_id"], f["flag_type"])
            ).fetchone()
            if existing:
                continue  # already flagged and still active, don't duplicate
            conn.execute("""
                INSERT INTO anomaly_flags
                  (entity_type, entity_id, name, department, section,
                   flag_type, severity, detail, detected_at, resolved)
                VALUES (?,?,?,?,?,?,?,?,?,0)
            """, (
                f["entity_type"], f["entity_id"], f["name"], f["department"], f["section"],
                f["flag_type"], f["severity"], f["detail"],
                datetime.now().isoformat(timespec="seconds"),
            ))
            inserted += 1

    return {"scanned": True, "new_flags": inserted, "checked_at": datetime.now().isoformat(timespec="seconds")}


def list_active_flags(dept: str = None) -> list:
    init_anomaly_table()
    with db() as conn:
        if dept:
            rows = conn.execute(
                "SELECT * FROM anomaly_flags WHERE resolved=0 AND UPPER(COALESCE(department,''))=? "
                "ORDER BY severity DESC, detected_at DESC",
                (dept.upper(),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM anomaly_flags WHERE resolved=0 "
                "ORDER BY severity DESC, detected_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def resolve_flag(flag_id: int) -> bool:
    with db() as conn:
        cur = conn.execute("UPDATE anomaly_flags SET resolved=1 WHERE id=?", (flag_id,))
        return cur.rowcount > 0
