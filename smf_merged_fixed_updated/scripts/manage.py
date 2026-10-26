"""
scripts/manage.py
=================
Enterprise Management CLI for EduTrack Pro.
Provides a unified developer & CI/CD interface for database migrations,
test data seeding, cache maintenance, and system diagnostics.

Usage:
    python scripts/manage.py [command]

Commands:
    seed-students       Seed mock students into test database
    seed-timetable      Populate faculty, courses, and timetable schedules
    add-test-student    Insert a single test student into production DB
    migrate-all         Execute all pending database schema migrations
    migrate-override    Migrate attendance override schema and historical logs
    migrate-od          Migrate OD two-stage workflow approvals
    migrate-hod         Migrate HOD role structures
    clear-cache         Remove __pycache__ and temporary artifacts
    cleanup-test-data   Purge test student records and generated avatars
    run-api             Start the FastAPI ASGI server daemon
"""

import os
import sys
import argparse

# Inject repository root onto search path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import app  # noqa: F401
from app.core import config
from app.core.logger import get_logger

log = get_logger("manage")


def cmd_seed_students(args):
    print("🌱 Running student test data seeding...")
    from scripts.seeds.seed_test_students import main
    main()


def cmd_seed_timetable(args):
    print("📅 Running timetable & course catalog seeding...")
    from scripts.seeds.timetable_seed import seed_all_timetables
    seed_all_timetables(force=getattr(args, "force", False))


def cmd_add_test_student(args):
    print("👤 Inserting single test student into database...")
    import subprocess
    subprocess.run([sys.executable, os.path.join(_ROOT, "scripts", "seeds", "add_test_student.py")])


def cmd_migrate_override(args):
    print("🔄 Running attendance override migration...")
    from scripts.migrations.migrate_override import run_migration
    run_migration(config.DB_PATH)


def cmd_migrate_od(args):
    print("🔄 Running OD two-stage approval migration...")
    from scripts.migrations.migrate_od_two_stage import migrate
    count = migrate()
    print(f"✓ OD migration completed ({count} rows updated).")


def cmd_migrate_hod(args):
    print("🔄 Running HOD table migration...")
    from scripts.migrations.migrate_hod_to_hods import migrate
    migrate()


def cmd_migrate_all(args):
    print("🚀 Executing all pending database migrations in sequence...")
    cmd_migrate_override(args)
    cmd_migrate_od(args)
    cmd_migrate_hod(args)
    print("✓ All migrations applied successfully!")


def cmd_clear_cache(args):
    print("🧹 Clearing Python pycache and bytecode artifacts...")
    removed = 0
    for root, dirs, files in os.walk(_ROOT):
        if "__pycache__" in dirs:
            pycache_dir = os.path.join(root, "__pycache__")
            import shutil
            shutil.rmtree(pycache_dir, ignore_errors=True)
            removed += 1
    print(f"✓ Removed {removed} __pycache__ directories.")


def cmd_cleanup_test_data(args):
    print("🗑️ Purging test student records...")
    from scripts.maintenance.cleanup_test_students import main
    main()


def cmd_backup_db(args):
    from scripts.maintenance.backup_db import create_atomic_backup
    print("Initiating atomic database backup...")
    ok, path, checksum = create_atomic_backup(keep_count=args.keep)
    if ok:
        print(f"✓ Backup created: {path}")
        print(f"✓ SHA-256 Checksum: {checksum}")
    else:
        print(f"✗ Backup failed: {path}")


def cmd_list_backups(args):
    from scripts.maintenance.backup_db import list_backups
    backups = list_backups()
    print(f"\nFound {len(backups)} available backup archives:")
    print(f"{'Filename':<42} {'Size':<10} {'Created At'}")
    print("-" * 72)
    for b in backups:
        print(f"{b['filename']:<42} {b['size_kb']} KB    {b['created_at']}")
    print()


def cmd_run_api(args):
    from app.main import run_api
    run_api()


def main():
    parser = argparse.ArgumentParser(
        description="EduTrack Pro Enterprise Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Management command to execute")

    # Seeds
    subparsers.add_parser("seed-students", help="Seed mock students into test database")
    p_tt = subparsers.add_parser("seed-timetable", help="Seed faculty, courses, and timetables")
    p_tt.add_argument("--force", action="store_true", help="Force wipe and re-seed")
    subparsers.add_parser("add-test-student", help="Insert a single test student into DB")

    # Migrations
    subparsers.add_parser("migrate-all", help="Execute all pending migrations")
    subparsers.add_parser("migrate-override", help="Migrate attendance override schema")
    subparsers.add_parser("migrate-od", help="Migrate OD two-stage approvals")
    subparsers.add_parser("migrate-hod", help="Migrate HOD role tables")

    # Maintenance & Disaster Recovery
    subparsers.add_parser("clear-cache", help="Clean __pycache__ and temp artifacts")
    subparsers.add_parser("cleanup-test-data", help="Purge mock student records and avatars")
    p_bak = subparsers.add_parser("backup-db", help="Create an atomic compressed database snapshot")
    p_bak.add_argument("--keep", type=int, default=14, help="Backups to retain (default: 14)")
    subparsers.add_parser("list-backups", help="List all point-in-time database backups")

    # Server
    subparsers.add_parser("run-api", help="Start the FastAPI ASGI application")

    args = parser.parse_args()

    commands = {
        "seed-students": cmd_seed_students,
        "seed-timetable": cmd_seed_timetable,
        "add-test-student": cmd_add_test_student,
        "migrate-all": cmd_migrate_all,
        "migrate-override": cmd_migrate_override,
        "migrate-od": cmd_migrate_od,
        "migrate-hod": cmd_migrate_hod,
        "clear-cache": cmd_clear_cache,
        "cleanup-test-data": cmd_cleanup_test_data,
        "backup-db": cmd_backup_db,
        "list-backups": cmd_list_backups,
        "run-api": cmd_run_api,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
