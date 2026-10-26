"""
add_test_student.py
--------------------
One-off helper: inserts a single test student into the REAL attendance.db
(the one your running app actually reads) so you can test the new
Register Number + Date of Birth student login right away.

Run this from inside your smf_merged_fixed/ project folder (same folder
as attendance.db), with the server stopped or running — SQLite handles
this fine either way:

    python3 add_test_student.py

It is safe to run more than once — it uses INSERT OR REPLACE keyed on
student_id, so re-running just refreshes the same test row.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import app
import config
import sqlite3
DB_PATH = getattr(config, "DB_PATH", "data/attendance.db")


# ── Test credentials — change these if you like ───────────────
STUDENT_ID = "STU_TEST001"
NAME = "Test Student"
REGISTER_NUMBER = "912823104086"   # same one you tried in the screenshot
DATE_OF_BIRTH = "2006-01-21"       # YYYY-MM-DD — must match exactly
DEPARTMENT = "CSE"
YEAR = "3"
SECTION = "A"

conn = sqlite3.connect(DB_PATH)
conn.execute(
    """
    INSERT OR REPLACE INTO students
        (student_id, name, register_number, date_of_birth,
         department, course, year, section, status, active, consent)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', 1, 1)
    """,
    (STUDENT_ID, NAME, REGISTER_NUMBER, DATE_OF_BIRTH,
     DEPARTMENT, DEPARTMENT, YEAR, SECTION),
)
conn.commit()
conn.close()

print("Test student inserted/updated.")
print(f"  Register Number : {REGISTER_NUMBER}")
print(f"  Date of Birth   : {DATE_OF_BIRTH}  (enter as 21/01/2006 in the date picker)")
print("Now log in at http://localhost:8000/student with these credentials.")