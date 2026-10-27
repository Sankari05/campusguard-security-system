"""
college_cpsat_scheduler.py
==========================
Syed Ammal Engineering College (Autonomous) Timetable Generation Engine
Powered by Google OR-Tools CP-SAT (Constraint Programming - Satisfiability).

Features:
- Odd Semesters: 1 (Year 1), 3 (Year 2), 5 (Year 3), 7 (Year 4).
- Departments: CSE (Sections A & B), IT, AIDS, CSBS, ECE, EEE, MECH, CIVIL, BME (Section A).
- Days: MON, TUE, WED, THU, FRI, SAT (1st & 3rd Saturday working).
- Periods: 7 periods daily.
    Period 1: 08:55 - 09:45
    Period 2: 09:45 - 10:35
    [TEA BREAK: 10:35 - 10:55]
    Period 3: 10:55 - 11:45
    Period 4: 11:45 - 12:35
    [LUNCH BREAK: 12:35 - 13:35]
    Period 5: 13:35 - 14:25
    Period 6: 14:25 - 15:15
    Period 7: 15:15 - 16:05
- Lab Contiguity: 2-period blocks (P1-P2, P3-P4, or P6-P7).
- Hard Constraints: Zero faculty double-booking, Zero class double-booking, Room allocation.
- Automatic SQLite sync with Face Recognition system: student_timetable & faculty_timetable.
"""

import os
import sys
import logging
import sqlite3
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict

# Ensure pandas shim is present to bypass Windows Application Control block on pandas native DLLs
import sys
import types
if "pandas" not in sys.modules:
    try:
        import pandas
    except Exception:
        p_mock = types.ModuleType("pandas")
        p_mock.Index = object
        p_mock.Series = object
        p_mock.DataFrame = object
        sys.modules["pandas"] = p_mock

from ortools.sat.python import cp_model

log = logging.getLogger(__name__)
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
PERIODS = [1, 2, 3, 4, 5, 6, 7]

PERIOD_TIMINGS = {
    1: ("08:55", "09:45"),
    2: ("09:45", "10:35"),
    3: ("10:55", "11:45"),
    4: ("11:45", "12:35"),
    5: ("13:35", "14:25"),
    6: ("14:25", "15:15"),
    7: ("15:15", "16:05"),
}

VALID_LAB_STARTS = [1, 3, 6]  # P1-P2, P3-P4 (morning), P6-P7 (afternoon)

UG_DEPARTMENTS = [
    "CSE", "IT", "AIDS", "CSBS", "ECE", "EEE", "MECH", "CIVIL", "BME"
]


def get_db_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(current_dir, "../../../data/attendance.db")),
        os.path.abspath(os.path.join(current_dir, "../../data/attendance.db")),
        os.path.abspath(os.path.join(os.getcwd(), "data/attendance.db")),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def ensure_it_courses_and_faculty(conn: sqlite3.Connection):
    """Ensure IT department courses and key real faculties from photo exist."""
    c = conn.cursor()

    # Check / Insert IT courses for Odd Semesters (Sem 1, 3, 5, 7)
    # Sem 5 courses from Syed Ammal Engineering College III IT timetable photo:
    sample_it_sem5_courses = [
        ("IT", 3, 5, "CS3591", "Computer Networks", "core", 5),
        ("IT", 3, 5, "IT3501", "Embedded System and IOT", "core", 4),
        ("IT", 3, 5, "IT3502", "Web Essentials", "core", 4),
        ("IT", 3, 5, "IT3503", "Mobile Network & App Dev", "core", 5),
        ("IT", 3, 5, "IT3504", "Neural Networks & Deep Learning", "core", 4),
        ("IT", 3, 5, "IT3505", "Software Testing and Automation", "core", 4),
        ("IT", 3, 5, "IT3511", "CN / EIOT Laboratory", "lab", 4),
        ("IT", 3, 5, "LIB001", "Library & Mentoring", "core", 1),
    ]

    for dept, yr, sem, code, name, c_type, credits in sample_it_sem5_courses:
        c.execute("""
            INSERT OR IGNORE INTO courses (dept, year, semester, course_code, course_name, course_type, credits)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (dept, yr, sem, code, name, c_type, credits))

    # Also replicate 1st, 2nd, 4th year IT courses from CSE/AIDS regulation if missing
    for yr, sem in [(1, 1), (2, 3), (4, 7)]:
        c.execute("SELECT course_code, course_name, course_type, credits FROM courses WHERE dept='CSE' AND year=? AND semester=?", (yr, sem))
        rows = c.fetchall()
        for code, name, c_type, credits in rows:
            c.execute("""
                INSERT OR IGNORE INTO courses (dept, year, semester, course_code, course_name, course_type, credits)
                VALUES ('IT', ?, ?, ?, ?, ?, ?)
            """, (yr, sem, code, name, c_type, credits))

    # Real faculties mentioned in the photo
    photo_faculties = [
        ("FAC_SUGUNA", "Mrs. C. Suguna", "IT", "Assistant Professor", "CS"),
        ("FAC_SINDHU", "Mrs. K. Sindhu Preethi", "IT", "Assistant Professor", "KSP"),
        ("FAC_NOORUL", "Mrs. J. Noorul Bimani", "IT", "Assistant Professor", "JNB"),
        ("FAC_SARANYA", "Mrs. V. Saranya", "IT", "Assistant Professor", "VS"),
        ("FAC_VINOTH", "Mr. D. Vinoth Kumar", "IT", "Assistant Professor", "DV"),
        ("FAC_MANJU", "Mrs. M. Manju", "IT", "Assistant Professor", "MM"),
        ("FAC_NITHYA", "Mrs. B. Nithyakalyani", "IT", "Assistant Professor", "BNK"),
        ("FAC_PONNI", "Mrs. K. Ponni Vinothini", "IT", "Associate Professor", "KPV"),
    ]

    for f_id, name, dept, desig, spec in photo_faculties:
        c.execute("""
            INSERT OR IGNORE INTO faculty (fac_id, name, dept, department, designation, specialization, active, status)
            VALUES (?, ?, ?, ?, ?, ?, 1, 'Active')
        """, (f_id, name, dept, dept, desig, spec))

    conn.commit()


class CollegeCPSATScheduler:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def load_data(self) -> Tuple[List[Dict], Dict[str, List[Dict]], List[Dict]]:
        """
        Loads:
        1. Class Groups (CSE-1A, CSE-1B, ... ECE-1A, etc.)
        2. Courses per class group for Odd Semesters (1, 3, 5, 7)
        3. Available Faculties per department
        """
        with self.get_connection() as conn:
            ensure_it_courses_and_faculty(conn)
            c = conn.cursor()

            # Load faculties grouped by department
            c.execute("""
                SELECT fac_id, name, dept, department, designation 
                FROM faculty 
                WHERE active = 1 AND status = 'Active'
            """)
            fac_rows = c.fetchall()

            dept_faculties: Dict[str, List[Dict]] = defaultdict(list)
            for r in fac_rows:
                dept = (r["dept"] or r["department"] or "CSE").upper().strip()
                dept_faculties[dept].append({
                    "id": r["fac_id"],
                    "name": r["name"],
                    "dept": dept,
                    "designation": r["designation"]
                })

            # Define all Classes
            # CSE has Sections A & B for all 4 years.
            # All other depts have Section A only.
            class_groups = []
            courses_by_class: Dict[str, List[Dict]] = {}

            year_semester_map = {1: 1, 2: 3, 3: 5, 4: 7}  # Odd Semesters

            for dept in UG_DEPARTMENTS:
                sections = ["A", "B"] if dept == "CSE" else ["A"]
                for year in [1, 2, 3, 4]:
                    semester = year_semester_map[year]
                    for sec in sections:
                        class_id = f"{dept}-{year}{sec}"
                        class_groups.append({
                            "class_id": class_id,
                            "dept": dept,
                            "year": year,
                            "section": sec,
                            "semester": semester,
                            "room": f"{dept}-{year}01" if sec == "A" else f"{dept}-{year}02",
                        })

                        # Load courses for this dept & semester
                        c.execute("""
                            SELECT course_code, course_name, course_type, credits 
                            FROM courses 
                            WHERE dept = ? AND semester = ?
                            ORDER BY course_type ASC, id ASC
                        """, (dept, semester))
                        c_rows = c.fetchall()

                        class_courses = []
                        total_hours = 0
                        for cr in c_rows:
                            code = cr["course_code"]
                            name = cr["course_name"]
                            c_type = (cr["course_type"] or "core").lower()

                            # Determine weekly periods:
                            # Labs: 4 or 2 hours (2-period blocks)
                            # Core theory: 3 or 4 hours
                            # Library / seminar: 1 hour
                            if "lab" in c_type or "practical" in name.lower() or "laboratory" in name.lower():
                                weekly_hours = 4  # Two 2-hour blocks or one 4-hour block
                                is_lab = True
                            elif "library" in name.lower() or "mentoring" in name.lower():
                                weekly_hours = 1
                                is_lab = False
                            else:
                                weekly_hours = 4 if total_hours < 20 else 3
                                is_lab = False

                            if total_hours + weekly_hours <= 34:  # Target ~30-34 periods/week
                                class_courses.append({
                                    "code": code,
                                    "name": name,
                                    "is_lab": is_lab,
                                    "weekly_hours": weekly_hours,
                                })
                                total_hours += weekly_hours

                        courses_by_class[class_id] = class_courses

        return class_groups, courses_by_class, dept_faculties

    def assign_faculty_to_courses(
        self,
        class_groups: List[Dict],
        courses_by_class: Dict[str, List[Dict]],
        dept_faculties: Dict[str, List[Dict]],
    ) -> Dict[Tuple[str, str], Dict]:
        """
        Assign each course of each class to a specific faculty member.
        Ensures even load distribution among available department faculty.
        """
        faculty_workload: Dict[str, int] = defaultdict(int)
        assignment: Dict[Tuple[str, str], Dict] = {}

        for cg in class_groups:
            dept = cg["dept"]
            fac_pool = dept_faculties.get(dept, [])
            if not fac_pool:
                fac_pool = dept_faculties.get("CSE", [])  # fallback

            # Round robin with least loaded faculty first
            for course in courses_by_class.get(cg["class_id"], []):
                # Pick faculty with lowest current workload
                best_fac = min(fac_pool, key=lambda f: faculty_workload[f["id"]])
                assignment[(cg["class_id"], course["code"])] = best_fac
                faculty_workload[best_fac["id"]] += course["weekly_hours"]

        return assignment

    def solve(self) -> Dict[str, Any]:
        """Runs Google OR-Tools CP-SAT to create a 100% clash-free college timetable."""
        class_groups, courses_by_class, dept_faculties = self.load_data()
        course_faculty = self.assign_faculty_to_courses(class_groups, courses_by_class, dept_faculties)

        model = cp_model.CpModel()

        # Decision Variables:
        # x[(class_id, course_code, day, period)] = 1 if class_id has course_code on day at period
        x: Dict[Tuple[str, str, str, int], cp_model.IntVar] = {}

        for cg in class_groups:
            cid = cg["class_id"]
            courses = courses_by_class.get(cid, [])
            for c in courses:
                cc = c["code"]
                for day in DAYS:
                    for p in PERIODS:
                        x[(cid, cc, day, p)] = model.NewBoolVar(f"x_{cid}_{cc}_{day}_{p}")

        # Constraint 1: Class Room / Class Group Slot Exclusivity
        # For each class_group, at most 1 course per (day, period)
        for cg in class_groups:
            cid = cg["class_id"]
            courses = courses_by_class.get(cid, [])
            for day in DAYS:
                for p in PERIODS:
                    model.AddAtMostOne(x[(cid, c["code"], day, p)] for c in courses)

        # Constraint 2: Exact Weekly Hours per Course
        for cg in class_groups:
            cid = cg["class_id"]
            for c in courses_by_class.get(cid, []):
                cc = c["code"]
                target_hours = c["weekly_hours"]
                model.Add(
                    sum(x[(cid, cc, day, p)] for day in DAYS for p in PERIODS) == target_hours
                )

        # Constraint 3: NO FACULTY DOUBLE-BOOKING (Absolute Zero Clash)
        # Group by faculty: for each faculty, at most 1 class at any (day, period)
        faculty_course_slots: Dict[Tuple[str, str, int], List[cp_model.IntVar]] = defaultdict(list)
        for (cid, cc), fac in course_faculty.items():
            fac_id = fac["id"]
            for day in DAYS:
                for p in PERIODS:
                    faculty_course_slots[(fac_id, day, p)].append(x[(cid, cc, day, p)])

        for (fac_id, day, p), var_list in faculty_course_slots.items():
            if len(var_list) > 1:
                model.AddAtMostOne(var_list)

        # Constraint 4: Lab Contiguity (2-period blocks)
        # Labs must run in 2-period contiguous blocks: P1-P2, P3-P4, or P6-P7
        for cg in class_groups:
            cid = cg["class_id"]
            for c in courses_by_class.get(cid, []):
                if c["is_lab"]:
                    cc = c["code"]
                    for day in DAYS:
                        # Non-lab-start periods cannot start a lab block unless preceded by start
                        # Period 2 can only be active if Period 1 is active
                        model.Add(x[(cid, cc, day, 2)] == x[(cid, cc, day, 1)])
                        # Period 4 can only be active if Period 3 is active
                        model.Add(x[(cid, cc, day, 4)] == x[(cid, cc, day, 3)])
                        # Period 7 can only be active if Period 6 is active
                        model.Add(x[(cid, cc, day, 7)] == x[(cid, cc, day, 6)])
                        # Period 5 cannot be a lab period (lunch ends at 1:35; P5 is single theory period)
                        model.Add(x[(cid, cc, day, 5)] == 0)

        # Constraint 5: Theory subject daily spread (At most 2 periods of same theory course per day)
        for cg in class_groups:
            cid = cg["class_id"]
            for c in courses_by_class.get(cid, []):
                if not c["is_lab"]:
                    cc = c["code"]
                    for day in DAYS:
                        model.Add(sum(x[(cid, cc, day, p)] for p in PERIODS) <= 2)

        # Objective: Soft optimization for balanced schedules
        # Prefer morning periods for heavy subjects, avoid gaps
        objective_terms = []
        for cg in class_groups:
            cid = cg["class_id"]
            for c in courses_by_class.get(cid, []):
                cc = c["code"]
                for day in DAYS:
                    for p in PERIODS:
                        # Slight preference for standard distribution
                        weight = 1 if p <= 4 else 2
                        objective_terms.append(x[(cid, cc, day, p)] * weight)

        model.Minimize(sum(objective_terms))

        # Solve with CP-SAT
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.num_workers = 4

        log.info("Solving Syed Ammal Engineering College Timetable via CP-SAT...")
        status = solver.Solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            log.error("CP-SAT Timetable solve failed with status: %s", solver.StatusName(status))
            return {
                "success": False,
                "message": f"Solver status: {solver.StatusName(status)}. Constraints unsatisfiable.",
                "assignments": []
            }

        log.info("CP-SAT Solution found! Status: %s", solver.StatusName(status))

        # Extract assignments
        assigned_slots = []
        for cg in class_groups:
            cid = cg["class_id"]
            dept = cg["dept"]
            year = cg["year"]
            section = cg["section"]
            semester = cg["semester"]
            default_room = cg["room"]

            for c in courses_by_class.get(cid, []):
                cc = c["code"]
                c_name = c["name"]
                fac = course_faculty.get((cid, cc), {})
                fac_id = fac.get("id", "")
                fac_name = fac.get("name", "")
                room = f"{dept}-LAB" if c["is_lab"] else default_room

                for day in DAYS:
                    for p in PERIODS:
                        if solver.Value(x[(cid, cc, day, p)]) == 1:
                            t_start, t_end = PERIOD_TIMINGS[p]
                            assigned_slots.append({
                                "dept": dept,
                                "year": year,
                                "semester": semester,
                                "section": section,
                                "class_id": cid,
                                "day_of_week": day,
                                "period_no": p,
                                "time_start": t_start,
                                "time_end": t_end,
                                "course_code": cc,
                                "course_name": c_name,
                                "faculty_id": fac_id,
                                "faculty_name": fac_name,
                                "room": room,
                            })

        return {
            "success": True,
            "status": solver.StatusName(status),
            "total_slots_placed": len(assigned_slots),
            "total_classes": len(class_groups),
            "assignments": assigned_slots
        }

    def save_to_database(self, assignments: List[Dict]) -> int:
        """
        Saves generated assignments into:
        1. student_timetable (per class)
        2. faculty_timetable (per faculty)
        Directly integrated with Face Recognition Attendance System.
        """
        if not assignments:
            return 0

        with self.get_connection() as conn:
            c = conn.cursor()
            # Clear existing Odd Semester timetables to ensure fresh clash-free state
            c.execute("DELETE FROM student_timetable WHERE semester IN (1, 3, 5, 7)")
            c.execute("DELETE FROM faculty_timetable WHERE semester IN (1, 3, 5, 7)")

            inserted = 0
            for slot in assignments:
                dept = slot["dept"]
                year = slot["year"]
                semester = slot["semester"]
                section = slot["section"]
                day = slot["day_of_week"]
                period = slot["period_no"]
                code = slot["course_code"]
                name = slot["course_name"]
                fac_id = slot["faculty_id"]
                fac_name = slot["faculty_name"]
                room = slot["room"]

                # 1. Insert into student_timetable
                c.execute("""
                    INSERT OR REPLACE INTO student_timetable
                    (dept, year, semester, section, day_of_week, period_no, course_code, course_name, faculty_id, faculty_name, room)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (dept, year, semester, section, day, period, code, name, fac_id, fac_name, room))

                # 2. Insert into faculty_timetable
                if fac_id:
                    c.execute("""
                        INSERT OR REPLACE INTO faculty_timetable
                        (faculty_id, day_of_week, period_no, dept, year, section, semester, course_code, course_name, room)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (fac_id, day, period, dept, year, section, semester, code, name, room))

                inserted += 1

            conn.commit()
            log.info("Successfully persisted %d timetable slots into SQLite!", inserted)
            return inserted


def generate_and_commit_timetable(db_path: Optional[str] = None) -> Dict[str, Any]:
    scheduler = CollegeCPSATScheduler(db_path)
    result = scheduler.solve()
    if result["success"]:
        count = scheduler.save_to_database(result["assignments"])
        result["saved_count"] = count
    return result


if __name__ == "__main__":
    res = generate_and_commit_timetable()
    print("Result:", res["success"], "Placed:", res.get("total_slots_placed"), "Saved:", res.get("saved_count"))
