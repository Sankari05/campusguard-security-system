import os
import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import app  # noqa: F401

"""
scripts/maintenance/reorganize_root.py
Enterprise File Organization Script.
Moves all loose Python modules from the repository root into clean, specialized app/ packages:
  - scripts/cli/                : Interactive CLI tools (enroll, recognize, clash)
  - app/database/               : Database DAOs and table schemas
  - app/services/vision/        : Face recognition engines, training, and session threads
  - app/services/notifications/ : Gmail alert workers and AI summaries
  - app/api/v1/features/        : Feature controllers and routes
  - app/core/                   : Core config, auth_utils, validators
"""

import os
import shutil

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

MOVES = [
    # 1. CLI scripts -> scripts/cli/
    ("enroll.py", "scripts/cli/enroll.py"),
    ("enroll_faculty.py", "scripts/cli/enroll_faculty.py"),
    ("enroll_hod.py", "scripts/cli/enroll_hod.py"),
    ("recognize.py", "scripts/cli/recognize.py"),
    ("recognizer1.py", "scripts/cli/recognizer1.py"),
    ("timetable_clash.py", "scripts/cli/timetable_clash.py"),
    ("timetable_seed.py", "scripts/seeds/timetable_seed.py"),

    # 2. Database DAOs -> app/database/
    ("database.py", "app/database/database.py"),
    ("database_academic.py", "app/database/database_academic.py"),
    ("database_anomaly.py", "app/database/database_anomaly.py"),
    ("database_compliance.py", "app/database/database_compliance.py"),
    ("database_extras.py", "app/database/database_extras.py"),
    ("database_faculty_requests.py", "app/database/database_faculty_requests.py"),
    ("database_override.py", "app/database/database_override.py"),
    ("database_postgres.py", "app/database/database_postgres.py"),
    ("database_workload.py", "app/database/database_workload.py"),
    ("student_portal_db.py", "app/database/student_portal_db.py"),

    # 3. Vision & session services -> app/services/vision/
    ("arcface_engine.py", "app/services/vision/arcface_engine.py"),
    ("lighting.py", "app/services/vision/lighting.py"),
    ("liveness.py", "app/services/vision/liveness.py"),
    ("train.py", "app/services/vision/train.py"),
    ("train_selective.py", "app/services/vision/train_selective.py"),
    ("twin_analysis.py", "app/services/vision/twin_analysis.py"),
    ("attendance_session.py", "app/services/vision/attendance_session.py"),
    ("role_attendance_session.py", "app/services/vision/role_attendance_session.py"),

    # 4. Notifications -> app/services/notifications/
    ("email_alerts.py", "app/services/notifications/email_alerts.py"),
    ("ai_summary.py", "app/services/notifications/ai_summary.py"),

    # 5. Feature routers -> app/api/v1/features/
    ("api_academic.py", "app/api/v1/features/api_academic.py"),
    ("api_ai_reports.py", "app/api/v1/features/api_ai_reports.py"),
    ("api_anomaly.py", "app/api/v1/features/api_anomaly.py"),
    ("api_clash.py", "app/api/v1/features/api_clash.py"),
    ("api_compliance.py", "app/api/v1/features/api_compliance.py"),
    ("api_extras.py", "app/api/v1/features/api_extras.py"),
    ("api_faculty_requests.py", "app/api/v1/features/api_faculty_requests.py"),
    ("api_features.py", "app/api/v1/features/api_features.py"),
    ("api_hod.py", "app/api/v1/features/api_hod.py"),
    ("api_override.py", "app/api/v1/features/api_override.py"),
    ("api_role_attendance.py", "app/api/v1/features/api_role_attendance.py"),
    ("api_student_portal.py", "app/api/v1/features/api_student_portal.py"),
    ("api_workload.py", "app/api/v1/features/api_workload.py"),
    ("auth_routes.py", "app/api/v1/features/auth_routes.py"),
    ("user_routes.py", "app/api/v1/features/user_routes.py"),
    ("edudrill_routes.py", "app/api/v1/features/edudrill_routes.py"),

    # 6. Core utilities -> app/core/
    ("auth_utils.py", "app/core/auth_utils.py"),
    ("config.py", "app/core/config.py"),
]


def run():
    moved_count = 0
    for src_rel, dst_rel in MOVES:
        src = os.path.join(BASE_DIR, src_rel)
        dst = os.path.join(BASE_DIR, dst_rel)
        if os.path.exists(src):
            dst_dir = os.path.dirname(dst)
            os.makedirs(dst_dir, exist_ok=True)
            # If dst already exists and is different, replace it
            if os.path.exists(dst):
                os.remove(dst)
            shutil.move(src, dst)
            moved_count += 1
            print(f"Moved: {src_rel} -> {dst_rel}")

    # Ensure __init__.py files exist in all new packages
    packages = [
        "scripts/cli",
        "app/database",
        "app/services/vision",
        "app/services/notifications",
        "app/api/v1/features",
    ]
    for pkg_rel in packages:
        init_file = os.path.join(BASE_DIR, pkg_rel, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, "w", encoding="utf-8") as f:
                f.write(f'"""\n{pkg_rel} package\n"""\n')
            print(f"Created {pkg_rel}/__init__.py")

    print(f"\nSuccessfully reorganized {moved_count} files into clean packages!")


if __name__ == "__main__":
    run()
