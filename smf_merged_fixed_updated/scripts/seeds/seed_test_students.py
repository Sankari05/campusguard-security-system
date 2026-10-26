import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import app  # noqa: F401

"""
seed_test_students.py
----------------------
Seeds the TEST DB copy (attendance_test.db) with dummy students so every
department / year / section has at least 5 students, for local testing only.

- Operates ONLY on attendance_test.db (a copy), never on attendance.db
- Every inserted row is tagged is_test_data=1
- Generates simple placeholder "initials avatar" images (not realistic faces)
  saved under dataset/<student_id>/avatar.jpg, matching the folder convention
  enroll.py expects, so the enrollment UI has something to display.
- Provides a matching cleanup script (cleanup_test_students.py) to remove
  everything this script adds.

Run:  python3 seed_test_students.py
"""

import os
import sqlite3
import random
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

DB_PATH = "attendance_test.db"
DATASET_DIR = "dataset"

DEPARTMENTS = ["CSE", "ECE", "MECH", "AIDS", "CSBS", "EEE", "CIVIL", "BME"]
SECTIONS = ["A", "B", "C"]
YEARS = ["1", "2", "3", "4"]
STUDENTS_PER_CLASS = 5

FIRST_NAMES_M = ["Arun", "Karthik", "Vignesh", "Dinesh", "Saravanan", "Pradeep",
                  "Mohan", "Surya", "Bala", "Naveen", "Gokul", "Hari", "Sanjay",
                  "Vimal", "Yogesh", "Aravind", "Manoj", "Praveen", "Suresh", "Rajesh"]
FIRST_NAMES_F = ["Priya", "Divya", "Meena", "Kavya", "Lakshmi", "Anitha", "Swathi",
                  "Nila", "Deepa", "Revathi", "Saranya", "Abinaya", "Keerthana",
                  "Nandhini", "Pavithra", "Sangeetha", "Vidhya", "Yamuna", "Indhu", "Janani"]
LAST_NAMES = ["Kumar", "Raj", "Krishnan", "Murugan", "Subramani", "Velu", "Pandian",
              "Sundaram", "Natarajan", "Ramasamy", "Selvam", "Manickam", "Elango",
              "Chezhian", "Anbarasan"]

AVATAR_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#d97706",
                  "#0891b2", "#be185d", "#4338ca", "#15803d", "#b45309"]


def make_avatar(initials: str, path: str, color: str):
    """Simple flat-color initials avatar — explicitly NOT a realistic face,
    so it can't be mistaken for / misused as real biometric input."""
    img = Image.new("RGB", (300, 300), color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110
        )
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), initials, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((300 - w) / 2 - bbox[0], (300 - h) / 2 - bbox[1]),
               initials, fill="white", font=font)
    img.save(path, "JPEG", quality=85)


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"{DB_PATH} not found — run from smf_merged_fixed/ and "
                          f"make sure you're seeding the TEST copy, not the real DB.")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    used_names = set()
    inserted = 0

    for dept in DEPARTMENTS:
        for year in YEARS:
            for section in SECTIONS:
                for i in range(STUDENTS_PER_CLASS):
                    gender = random.choice(["M", "F"])
                    first = random.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)
                    last = random.choice(LAST_NAMES)
                    full_name = f"{first} {last}"
                    # avoid exact dup full names across the whole seed set
                    tries = 0
                    while full_name in used_names and tries < 10:
                        last = random.choice(LAST_NAMES)
                        full_name = f"{first} {last}"
                        tries += 1
                    used_names.add(full_name)

                    student_id = f"TEST_{dept}_{year}{section}_{i+1:02d}"
                    reg_no = f"TN{dept}{year}{section}{i+1:02d}{random.randint(100,999)}"
                    initials = (first[0] + last[0]).upper()
                    color = random.choice(AVATAR_COLORS)

                    student_dir = os.path.join(DATASET_DIR, student_id)
                    os.makedirs(student_dir, exist_ok=True)
                    avatar_path = os.path.join(student_dir, "avatar.jpg")
                    make_avatar(initials, avatar_path, color)

                    cur.execute("""
                        INSERT OR IGNORE INTO students
                        (student_id, name, register_number, roll_number,
                         first_name, last_name, gender, date_of_birth,
                         department, course, year, section,
                         student_email, parent_email, student_mobile, parent_mobile,
                         status, consent, enrolled_on, active, is_test_data)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        student_id, full_name, reg_no, f"{i+1:02d}",
                        first, last, gender, "2006-01-01",
                        dept, dept, year, section,
                        f"{student_id.lower()}@test.local", f"parent_{student_id.lower()}@test.local",
                        f"9{random.randint(100000000,999999999)}", f"9{random.randint(100000000,999999999)}",
                        "Active", 1, datetime.now().isoformat(), 1, 1
                    ))
                    inserted += cur.rowcount

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM students WHERE is_test_data=1")
    total = cur.fetchone()[0]
    conn.close()
    print(f"Inserted {inserted} new test student rows.")
    print(f"Total is_test_data=1 rows now in {DB_PATH}: {total}")
    print(f"Avatar images written under: {DATASET_DIR}/<student_id>/avatar.jpg")


if __name__ == "__main__":
    main()
