"""
cleanup_default_data.py
-----------------------
One-time/maintenance cleanup utility to reset default admin teams and scenarios
to the authoritative 2-team (4 members total) and 5-scenario baseline.
"""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db


def cleanup_and_seed(db_path: str = None) -> None:
    path = db_path or db.DEFAULT_DB_PATH
    print(f"Cleaning teams and personnel in database at: {path}")
    db.init_db(path)
    db.reset_team_demo_data(path)
    print(f"Cleanup complete. Exactly 2 teams (4 members total) and 5 scenarios seeded in {path}.")


if __name__ == "__main__":
    cleanup_and_seed()
