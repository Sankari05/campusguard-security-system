"""
tests/test_backup_disaster_recovery.py
Automated Test Suite for Atomic Database Disaster Recovery Engine.

Verifies:
1. Online atomic backup creation generates valid gzip archive with SHA-256 checksum.
2. SQLite PRAGMA integrity_check passes on restored backup.
3. Automated retention pruning keeps only latest N archives.
4. Point-in-time database restoration successfully recovers data.
"""

import os
import shutil
import sqlite3
import tempfile
import pytest

from scripts.maintenance.backup_db import (
    create_atomic_backup,
    verify_backup,
    list_backups,
    prune_old_backups,
    restore_backup,
    compute_sha256
)


@pytest.fixture
def temp_backup_env():
    """Create isolated temporary environment for database backup testing."""
    temp_dir = tempfile.mkdtemp(prefix="edutrack_backup_test_")
    test_db = os.path.join(temp_dir, "test_source.db")
    backup_dir = os.path.join(temp_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    # Initialize a test SQLite database with dummy tables and records
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT);")
    cur.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@edutrack.com');")
    cur.execute("INSERT INTO users (name, email) VALUES ('Bob', 'bob@edutrack.com');")
    conn.commit()
    conn.close()

    yield {
        "temp_dir": temp_dir,
        "test_db": test_db,
        "backup_dir": backup_dir,
    }

    # Teardown
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_atomic_backup_creation(temp_backup_env):
    """Test 1: create_atomic_backup creates a verified gzip snapshot and SHA-256 checksum."""
    ok, archive_path, checksum = create_atomic_backup(
        db_path=temp_backup_env["test_db"],
        backup_dir=temp_backup_env["backup_dir"],
        keep_count=5
    )

    assert ok is True
    assert os.path.exists(archive_path)
    assert archive_path.endswith(".db.gz")
    assert os.path.getsize(archive_path) > 0

    # Verify SHA-256 checksum file
    checksum_file = archive_path + ".sha256"
    assert os.path.exists(checksum_file)
    with open(checksum_file, "r") as f:
        recorded_sum = f.read().split()[0].strip()
    assert recorded_sum == checksum
    assert compute_sha256(archive_path) == checksum


def test_backup_integrity_verification(temp_backup_env):
    """Test 2: verify_backup decompress and executes PRAGMA integrity_check."""
    ok, archive_path, _ = create_atomic_backup(
        db_path=temp_backup_env["test_db"],
        backup_dir=temp_backup_env["backup_dir"]
    )
    assert ok is True

    verify_ok, verify_msg = verify_backup(archive_path)
    assert verify_ok is True
    assert "Integrity check passed" in verify_msg


def test_backup_retention_pruning(temp_backup_env):
    """Test 3: prune_old_backups retains only the latest N backups."""
    backup_dir = temp_backup_env["backup_dir"]
    db_path = temp_backup_env["test_db"]

    # Generate 4 distinct backups
    archives = []
    for _ in range(4):
        ok, p, _ = create_atomic_backup(db_path=db_path, backup_dir=backup_dir, keep_count=10)
        assert ok is True
        archives.append(p)

    all_backups = list_backups(backup_dir)
    assert len(all_backups) == 4

    # Prune keeping only the latest 2
    pruned_count = prune_old_backups(backup_dir, keep_count=2)
    assert pruned_count == 2
    remaining = list_backups(backup_dir)
    assert len(remaining) == 2


def test_point_in_time_restoration(temp_backup_env):
    """Test 4: restore_backup successfully recovers database to exact state."""
    db_path = temp_backup_env["test_db"]
    backup_dir = temp_backup_env["backup_dir"]

    # 1. Take backup with 2 users
    ok, archive_path, _ = create_atomic_backup(db_path=db_path, backup_dir=backup_dir)
    assert ok is True

    # 2. Corrupt/Modify live database by deleting users
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM users;")
    conn.commit()
    cur.execute("SELECT count(*) FROM users;")
    assert cur.fetchone()[0] == 0
    conn.close()

    # 3. Perform restoration
    restore_ok, restore_msg = restore_backup(archive_path, db_path)
    assert restore_ok is True

    # 4. Confirm data is completely restored
    conn2 = sqlite3.connect(db_path)
    cur2 = conn2.cursor()
    cur2.execute("SELECT count(*) FROM users;")
    assert cur2.fetchone()[0] == 2
    cur2.execute("SELECT name FROM users ORDER BY id;")
    names = [r[0] for r in cur2.fetchall()]
    assert names == ["Alice", "Bob"]
    conn2.close()
