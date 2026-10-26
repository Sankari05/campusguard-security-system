# =============================================================
# timetable_clash.py — NEW FILE (additive only)
#
# Detects scheduling conflicts BEFORE a timetable slot is saved:
#   - same faculty already teaching another section at that day+period
#   - same section already has a class at that day+period
#   - same room already booked at that day+period
# Reads from the EXISTING faculty_timetable / student_timetable tables.
# Writes nothing, creates nothing — pure read-only check function.
# =============================================================
import logging

log = logging.getLogger(__name__)


def check_clash(conn, faculty_id=None, section=None, dept=None, year=None,
                 semester=None, day=None, period=None, room=None,
                 exclude_id=None) -> list:
    """
    Returns a list of conflicting slot dicts (empty list = no clash).
    `conn` must be an already-open sqlite3 connection (row_factory=Row).
    """
    conflicts = []
    if not day or not period:
        return conflicts

    # 1) Faculty clash — same faculty, same day+period, any section/dept
    if faculty_id:
        q = """
            SELECT 'faculty_clash' AS reason, dept, year, section, semester,
                   day_of_week, period_no, course_name, faculty_id,
                   faculty_id AS faculty_name, room
            FROM faculty_timetable
            WHERE faculty_id = ? AND day_of_week = ? AND period_no = ?
        """
        params = [faculty_id, day, period]
        if semester:
            q += " AND semester = ?"
            params.append(semester)
        if exclude_id:
            q += " AND id != ?"
            params.append(exclude_id)
        rows = conn.execute(q, params).fetchall()
        conflicts.extend(dict(r) for r in rows)

    # 2) Section clash — same dept/year/section already has a class that period
    if section and dept and year:
        q = """
            SELECT 'section_clash' AS reason, dept, year, section, semester,
                   day_of_week, period_no, course_name, faculty_id, faculty_name, room
            FROM student_timetable
            WHERE dept = ? AND year = ? AND section = ? AND day_of_week = ? AND period_no = ?
        """
        params = [dept, year, section, day, period]
        if semester:
            q += " AND semester = ?"
            params.append(semester)
        if exclude_id:
            q += " AND id != ?"
            params.append(exclude_id)
        rows = conn.execute(q, params).fetchall()
        conflicts.extend(dict(r) for r in rows)

    # 3) Room clash — same room already booked that day+period (if room given)
    if room:
        q = """
            SELECT 'room_clash' AS reason, dept, year, section, semester,
                   day_of_week, period_no, course_name, faculty_id, faculty_name, room
            FROM student_timetable
            WHERE room = ? AND day_of_week = ? AND period_no = ? AND room != ''
        """
        params = [room, day, period]
        if exclude_id:
            q += " AND id != ?"
            params.append(exclude_id)
        rows = conn.execute(q, params).fetchall()
        conflicts.extend(dict(r) for r in rows)

    return conflicts
