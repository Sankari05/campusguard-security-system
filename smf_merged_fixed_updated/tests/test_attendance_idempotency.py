"""
tests/test_attendance_idempotency.py
Enterprise Idempotency & Concurrency Automated Test Suite.

Verifies:
1. First attendance mark successfully creates an atomic record (duplicate=False).
2. Consecutive identical requests return HTTP 200 with duplicate=True and create 0 duplicate rows.
3. Multiple periods for the same student on the same date are cleanly preserved.
4. High-concurrency multithreaded race conditions: 10 parallel threads hit the API simultaneously,
   resulting in exactly 1 database row with zero lock exceptions or 500 errors.
"""

import os
import sqlite3
import pytest
from concurrent.futures import ThreadPoolExecutor
from starlette.testclient import TestClient

from app.main import app
from app.core.idempotency import attendance_guard
from api import create_access_token

client = TestClient(app)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "attendance.db")


def _cleanup_test_records():
    attendance_guard.clear()
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("DELETE FROM attendance WHERE student_id LIKE 'TEST_%'")
            cur.execute("DELETE FROM student_attendance WHERE student_id LIKE 'TEST_%'")
            conn.commit()
            conn.close()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clean_idempotency_cache():
    """Clear memory guard and test records from database before and after each test."""
    _cleanup_test_records()
    yield
    _cleanup_test_records()


@pytest.fixture(scope="module")
def admin_headers():
    token = create_access_token("admin", "admin")
    return {"Authorization": f"Bearer {token}"}


def _get_db_count(student_id: str, period: str, date_str: str = "2026-10-24") -> int:
    """Helper to query direct SQLite row count."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM attendance WHERE student_id=? AND period=? AND date=?",
        (student_id, period, date_str)
    )
    count = cur.fetchone()[0]
    conn.close()
    return count


def test_first_attendance_mark_creates_record(admin_headers):
    """Flow 1: Initial attendance mark creates record with duplicate=False."""
    payload = {
        "student_id": "TEST_IDEMP_001",
        "name": "Test Student 1",
        "period": "Period_1",
        "date": "2026-10-24",
        "confidence": 0.98,
        "engine": "ArcFace"
    }

    res = client.post("/api/attendance/mark", json=payload, headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["duplicate"] is False
    assert data["action"] == "marked"

    # Direct database verification
    assert _get_db_count("TEST_IDEMP_001", "Period_1", "2026-10-24") == 1


def test_duplicate_attendance_returns_duplicate_flag_and_no_new_db_row(admin_headers):
    """Flow 2: Consecutive identical requests return duplicate=True with zero extra DB rows."""
    payload = {
        "student_id": "TEST_IDEMP_002",
        "name": "Test Student 2",
        "period": "Period_1",
        "date": "2026-10-24",
        "confidence": 0.99
    }

    # 1st request -> marks attendance
    res1 = client.post("/api/attendance/mark", json=payload, headers=admin_headers)
    assert res1.status_code == 200
    assert res1.json()["duplicate"] is False

    # 2nd, 3rd, 4th, 5th requests -> duplicate shield catches all
    for _ in range(4):
        res_dup = client.post("/api/attendance/mark", json=payload, headers=admin_headers)
        assert res_dup.status_code == 200
        data = res_dup.json()
        assert data["status"] == "success"
        assert data["duplicate"] is True
        assert data["action"] == "already_marked"

    # Direct database verification: EXACTLY 1 row must exist!
    assert _get_db_count("TEST_IDEMP_002", "Period_1", "2026-10-24") == 1


def test_different_period_same_day_creates_second_record(admin_headers):
    """Flow 3: Different periods for the same student create distinct records."""
    student_id = "TEST_IDEMP_003"
    date_str = "2026-10-24"

    # Mark Period 1
    p1 = {"student_id": student_id, "period": "Period_1", "date": date_str}
    r1 = client.post("/api/attendance/mark", json=p1, headers=admin_headers)
    assert r1.status_code == 200
    assert r1.json()["duplicate"] is False

    # Mark Period 2
    p2 = {"student_id": student_id, "period": "Period_2", "date": date_str}
    r2 = client.post("/api/attendance/mark", json=p2, headers=admin_headers)
    assert r2.status_code == 200
    assert r2.json()["duplicate"] is False

    # Verify both exist distinctly
    assert _get_db_count(student_id, "Period_1", date_str) == 1
    assert _get_db_count(student_id, "Period_2", date_str) == 1


def test_multithreaded_concurrency_race_condition(admin_headers):
    """Flow 4: High-concurrency burst of 10 simultaneous threads results in exactly 1 DB record."""
    student_id = "TEST_CONCURRENCY_999"
    period = "Period_4"
    date_str = "2026-10-24"

    payload = {
        "student_id": student_id,
        "name": "Concurrency Student",
        "period": period,
        "date": date_str
    }

    def _fire_request(_):
        return client.post("/api/attendance/mark", json=payload, headers=admin_headers)

    # Launch 10 simultaneous threads
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(_fire_request, range(10)))

    # All 10 requests must succeed with HTTP 200
    status_codes = [r.status_code for r in results]
    assert all(code == 200 for code in status_codes), f"Got non-200 codes: {status_codes}"

    # Exactly 1 marked action, 9 duplicate actions
    actions = [r.json()["action"] for r in results]
    assert actions.count("marked") == 1
    assert actions.count("already_marked") == 9

    # Direct database verification: EXACTLY 1 row exists
    assert _get_db_count(student_id, period, date_str) == 1
