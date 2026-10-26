# =============================================================
# api_extras.py  —  Smart Attendance System  v10.0
#
# Routes for:
#   GET/POST /api/courses            - course catalogue
#   GET/POST /api/electives          - elective pool + assignments
#   GET/POST /api/student-extended   - enrollment with email/year/section
#   GET/POST /api/timetable/student  - student timetable
#   GET/POST /api/timetable/faculty  - faculty timetable
#   GET      /api/period-slots       - the 7 period timings
# =============================================================
import logging
log = logging.getLogger(__name__)


def register_extra_routes(app, get_current_user, teacher_required, admin_required):
    from fastapi import Depends, HTTPException, Query
    import database_extras as dbe

    # ── Faculty timetable access control ─────────────────────
    # Admin/HOD can view any class. Every other role (faculty, teacher,
    # classincharge, etc.) may only view the timetable of the single class
    # they are registered as the Class In-Charge for.
    def _enforce_class_access(user: dict, dept: str, year, section: str):
        role = (user.get("role") or "").lower()
        if role in ("admin", "hod"):
            return  # unrestricted
        import database as db
        fac_id = user.get("sub") or user.get("username") or ""
        cls = db.get_faculty_incharge_class(fac_id)
        if not cls:
            raise HTTPException(
                status_code=403,
                detail="You are not assigned as a Class In-Charge, so you cannot view any class timetable."
            )
        try:
            req_year = int(year) if year is not None else None
        except (TypeError, ValueError):
            req_year = None
        if (cls["dept"] != (dept or "").strip().upper()
                or cls["year"] != req_year
                or cls["section"] != (section or "").strip().upper()):
            raise HTTPException(
                status_code=403,
                detail="You can only view the timetable of the class you are assigned as Class In-Charge for."
            )

    # ── My assigned class (for faculty "My Timetable") ───────
    @app.get("/api/faculty/my-class")
    def my_incharge_class(user: dict = Depends(get_current_user)):
        """
        Tells the logged-in faculty member which class (if any) they are the
        Class In-Charge of, so the frontend can auto-load that timetable
        without letting them browse other classes.
        """
        role = (user.get("role") or "").lower()
        import database as db
        if role in ("admin", "hod"):
            return {"role": role, "is_class_incharge": False, "unrestricted": True,
                    "dept": None, "year": None, "section": None}
        fac_id = user.get("sub") or user.get("username") or ""
        cls = db.get_faculty_incharge_class(fac_id)
        if cls:
            return {"role": role, "is_class_incharge": True, "unrestricted": False, **cls}
        return {"role": role, "is_class_incharge": False, "unrestricted": False,
                "dept": None, "year": None, "section": None}

    # ── Period Slots ────────────────────────────────────────
    @app.get("/api/period-slots")
    def get_period_slots(_: dict = Depends(get_current_user)):
        return dbe.get_period_slots()

    # ── Courses ─────────────────────────────────────────────
    @app.get("/api/courses")
    def list_courses(dept: str, semester: int = None,
                     course_type: str = None,
                     _: dict = Depends(get_current_user)):
        return dbe.get_courses(dept, semester, course_type)

    @app.get("/api/courses/by-year")
    def courses_by_year(dept: str, year: int,
                        _: dict = Depends(get_current_user)):
        return dbe.get_courses_by_year(dept, year)

    @app.get("/api/courses/elective-pool")
    def elective_pool(dept: str, _: dict = Depends(get_current_user)):
        return dbe.get_elective_pool(dept)

    @app.post("/api/courses")
    def save_course(data: dict, user: dict = Depends(admin_required)):
        return dbe.upsert_course(
            dept        = data.get("dept",""),
            year        = int(data.get("year",1)),
            semester    = int(data.get("semester",1)),
            course_code = data.get("course_code","").upper().strip(),
            course_name = data.get("course_name","").strip(),
            course_type = data.get("course_type","core"),
            credits     = int(data.get("credits",3)),
            created_by  = user.get("username","admin"),
        )

    # ── Elective Assignments ────────────────────────────────
    @app.get("/api/electives")
    def get_electives(dept: str, semester: int, section: str = None,
                      _: dict = Depends(get_current_user)):
        return dbe.get_elective_selections(dept, semester, section)

    @app.post("/api/electives/assign")
    def assign_elective(data: dict, user: dict = Depends(teacher_required)):
        return dbe.assign_elective(
            student_id  = data.get("student_id",""),
            dept        = data.get("dept",""),
            year        = int(data.get("year",1)),
            semester    = int(data.get("semester",1)),
            section     = data.get("section","A"),
            course_code = data.get("course_code","").upper().strip(),
            selected_by = user.get("username","admin"),
        )

    # ── Semester ────────────────────────────────────────────
    @app.get("/api/semesters")
    def get_semesters(dept: str, _: dict = Depends(get_current_user)):
        return dbe.get_all_semesters(dept)

    @app.get("/api/semesters/current")
    def current_semester(dept: str, year: int,
                         _: dict = Depends(get_current_user)):
        return dbe.get_current_semester(dept, year)

    # ── Student Extended ────────────────────────────────────
    @app.get("/api/students/extended")
    def student_ext(student_id: str, _: dict = Depends(get_current_user)):
        return dbe.get_student_extended(student_id)

    @app.get("/api/students/section")
    def section_students(dept: str, year: int, section: str,
                         _: dict = Depends(get_current_user)):
        return dbe.get_section_students_extended(dept, year, section)

    @app.post("/api/students/extended")
    def save_student_ext(data: dict, _: dict = Depends(get_current_user)):
        return dbe.upsert_student_extended(
            student_id    = data.get("student_id",""),
            dept          = data.get("dept",""),
            year          = int(data.get("year",1)),
            section       = data.get("section","A"),
            semester      = int(data.get("semester",1)),
            student_email = data.get("student_email",""),
            parent_email  = data.get("parent_email",""),
            faculty_email = data.get("faculty_email",""),
            hod_email     = data.get("hod_email",""),
        )

    # ── Student Timetable ───────────────────────────────────
    @app.get("/api/timetable/student")
    def student_tt(dept: str, year: int, section: str,
                   semester: int = None,
                   user: dict = Depends(get_current_user)):
        _enforce_class_access(user, dept, year, section)
        return dbe.get_student_timetable(dept, year, section, semester)

    @app.post("/api/timetable/student")
    def save_student_tt(data: dict, force: bool = False, user: dict = Depends(admin_required)):
        # ── Clash check (NEW, additive, fail-open) ───────────────
        try:
            from timetable_clash import check_clash
            from database import db as _db
            with _db() as _conn:
                _conflicts = check_clash(
                    _conn,
                    faculty_id=data.get("faculty_id") or None,
                    section=data.get("section"),
                    dept=data.get("dept"),
                    year=int(data.get("year", 1)) if data.get("year") else None,
                    semester=int(data.get("semester", 1)) if data.get("semester") else None,
                    day=data.get("day_of_week"),
                    period=int(data.get("period_no")) if data.get("period_no") else None,
                    room=data.get("room") or None,
                )
            if _conflicts and not force:
                raise HTTPException(status_code=409, detail={"message": "Clash detected", "conflicts": _conflicts})
        except HTTPException:
            raise
        except Exception as _ce:
            log.warning("Clash check skipped (non-blocking): %s", _ce)

        return dbe.upsert_student_timetable(
            dept        = data.get("dept",""),
            year        = int(data.get("year",1)),
            section     = data.get("section","A"),
            day_of_week = data.get("day_of_week","MON"),
            period_no   = int(data.get("period_no",1)),
            course_code = data.get("course_code",""),
            course_name = data.get("course_name",""),
            faculty_id  = data.get("faculty_id",""),
            faculty_name= data.get("faculty_name",""),
            room        = data.get("room",""),
            semester    = int(data.get("semester",1)),
        )

    @app.delete("/api/timetable/student")
    def del_student_tt(dept: str, year: int, section: str,
                       day_of_week: str, period_no: int,
                       semester: int = 1,
                       user: dict = Depends(admin_required)):
        return dbe.delete_timetable_slot(dept, year, section, day_of_week, period_no, semester)

    # ── Faculty Timetable ───────────────────────────────────
    @app.get("/api/timetable/faculty")
    def faculty_tt(faculty_id: str,
                   dept: str = Query(None),
                   semester: int = Query(None),
                   _: dict = Depends(get_current_user)):
        return dbe.get_faculty_timetable(faculty_id, dept=dept, semester=semester)

    # ── Timetable: POST bulk upsert ──────────────────────────
    @app.post("/api/timetable/student/bulk")
    def bulk_student_tt(data: list, force: bool = False, user: dict = Depends(admin_required)):
        """Bulk upsert timetable slots. Body: list of slot objects."""
        # ── Clash check (NEW, additive, fail-open) ───────────────
        try:
            from timetable_clash import check_clash
            from database import db as _db
            all_conflicts = []
            with _db() as _conn:
                for slot in data:
                    c = check_clash(
                        _conn,
                        faculty_id=slot.get("faculty_id") or None,
                        section=slot.get("section"),
                        dept=slot.get("dept"),
                        year=int(slot.get("year", 1)) if slot.get("year") else None,
                        semester=int(slot.get("semester", 1)) if slot.get("semester") else None,
                        day=slot.get("day_of_week"),
                        period=int(slot.get("period_no")) if slot.get("period_no") else None,
                        room=slot.get("room") or None,
                    )
                    all_conflicts.extend(c)
            if all_conflicts and not force:
                raise HTTPException(status_code=409, detail={"message": "Clash detected", "conflicts": all_conflicts})
        except HTTPException:
            raise
        except Exception as _ce:
            log.warning("Bulk clash check skipped (non-blocking): %s", _ce)

        results = []
        for slot in data:
            r = dbe.upsert_student_timetable(
                dept        = slot.get("dept",""),
                year        = int(slot.get("year",1)),
                section     = slot.get("section","A"),
                day_of_week = slot.get("day_of_week","MON"),
                period_no   = int(slot.get("period_no",1)),
                course_code = slot.get("course_code",""),
                course_name = slot.get("course_name",""),
                faculty_id  = slot.get("faculty_id",""),
                faculty_name= slot.get("faculty_name",""),
                room        = slot.get("room",""),
                semester    = int(slot.get("semester",1)),
            )
            results.append(r)
        return {"inserted": len(results)}

    # ── Admin seed: re-run Vinoth Kumar seed ─────────────────
    @app.post("/api/admin/seed-vinoth-kumar")
    def api_seed_vinoth(user: dict = Depends(admin_required)):
        """Re-run the Vinoth Kumar faculty + timetable seed (idempotent)."""
        return dbe.seed_vinoth_kumar()

    # ── Full Timetable Seed (all depts / all sems / 50 faculty) ──
    @app.post("/api/admin/seed-timetable")
    def api_seed_all_timetables(data: dict = None, user: dict = Depends(admin_required)):
        """Seed complete timetable for all 8 departments, all semesters, sections A/B/C."""
        try:
            from timetable_seed import seed_all_timetables
            force = (data or {}).get("force", False)
            seed_all_timetables(force=force)
            return {"status": "ok", "message": "Full timetable seeded successfully."}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ── Timetable: GET by dept/year/section (from seed data) ──
    @app.get("/api/timetable/full")
    def full_student_tt(dept: str, year: int, section: str,
                        semester: int = None,
                        user: dict = Depends(get_current_user)):
        """Returns timetable from the seeded database (all depts/sems)."""
        _enforce_class_access(user, dept, year, section)
        try:
            from timetable_seed import get_student_timetable as _gst
            return _gst(dept, year, section, semester)
        except Exception:
            return dbe.get_student_timetable(dept, year, section, semester)

    # ── Faculty Timetable from seed data ─────────────────────
    @app.get("/api/timetable/faculty/full")
    def full_faculty_tt(faculty_id: str,
                        dept: str = Query(None),
                        semester: int = Query(None),
                        _: dict = Depends(get_current_user)):
        """Returns faculty timetable from seeded database, filtered by dept and semester."""
        try:
            from timetable_seed import get_faculty_timetable as _gftt
            return _gftt(faculty_id, dept=dept, semester=semester)
        except Exception:
            return dbe.get_faculty_timetable(faculty_id, dept=dept, semester=semester)

    # ── Faculty list (from seed, with fallback) ─────────────
    @app.get("/api/faculty/all")
    def get_all_faculty_seed(_: dict = Depends(get_current_user)):
        """Returns all faculty from seed DB with fallback to faculty table."""
        fac_list = []
        try:
            from timetable_seed import get_all_faculty as _gaf
            fac_list = _gaf()
        except Exception:
            pass
        if not fac_list:
            try:
                from api_features import get_all_faculty as _gaf2
                fac_list = _gaf2()
            except Exception:
                pass
        return {"faculty": fac_list}

    # ── Timetable Status — check if seeded ────────────────────
    @app.get("/api/timetable/status")
    def timetable_status(_: dict = Depends(get_current_user)):
        """Check seed status: faculty count, student slots, faculty slots."""
        try:
            import sqlite3, os, config as _cfg
            db_path = getattr(_cfg, "DB_PATH", os.path.join(_cfg.BASE_DIR, "data", "attendance.db"))
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            def safe_count(sql):
                try: return conn.execute(sql).fetchone()[0]
                except: return 0
            fac   = safe_count("SELECT COUNT(*) FROM faculty WHERE active=1")
            stud  = safe_count("SELECT COUNT(*) FROM student_timetable")
            fac_slots = safe_count("SELECT COUNT(*) FROM faculty_timetable")
            conn.close()
            return {"faculty": fac, "student_slots": stud, "faculty_slots": fac_slots,
                    "seeded": fac > 0 and fac_slots > 0}
        except Exception as e:
            return {"faculty": 0, "student_slots": 0, "faculty_slots": 0,
                    "seeded": False, "error": str(e)}

    log.info("Extra routes registered (courses, electives, timetable, full-seed)")
