import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import app  # noqa: F401

"""
cleanup_test_students.py
--------------------------
Removes everything seed_test_students.py added: rows with is_test_data=1
from the TEST DB copy, and their dataset/<student_id>/ avatar folders.

Run:  python3 cleanup_test_students.py
"""

import os
import shutil
import sqlite3

DB_PATH = "attendance_test.db"
DATASET_DIR = "dataset"


def main():
    if not os.path.exists(DB_PATH):
        print(f"Test database {DB_PATH} not found. Nothing to clean.")
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT student_id FROM students WHERE is_test_data=1")
        ids = [r[0] for r in cur.fetchall()]
        cur.execute("DELETE FROM students WHERE is_test_data=1")
        conn.commit()
    except sqlite3.OperationalError:
        ids = []
    finally:
        conn.close()


    removed_dirs = 0
    for sid in ids:
        d = os.path.join(DATASET_DIR, sid)
        if os.path.isdir(d):
            shutil.rmtree(d)
            removed_dirs += 1

    print(f"Deleted {len(ids)} test student rows from {DB_PATH}.")
    print(f"Removed {removed_dirs} avatar folders under {DATASET_DIR}/.")


if __name__ == "__main__":
    main()
