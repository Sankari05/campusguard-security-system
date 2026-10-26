# tests/test_phase2_p1_security.py
import pytest
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit_log import SecurityAuditLog
from app.models.user import User


def test_account_lockout_after_five_failed_attempts(client):
    """
    Test 1: Account Lockout Policy
    5 consecutive failed attempts trigger 429 Too Many Requests cooldown.
    """
    db = SessionLocal()
    try:
        # Create a test victim user
        test_user = db.query(User).filter(User.username == "victim_lockout_user").first()
        if not test_user:
            test_user = User(
                username="victim_lockout_user",
                email="victim@college.edu",
                password_hash=hash_password("RealPassword123"),
                full_name="Victim User",
                role="WATCHMAN",
                assigned_gate="Main Gate 1",
                failed_login_attempts=0,
                locked_until=None,
                is_active=True,
            )
            db.add(test_user)
        else:
            test_user.failed_login_attempts = 0
            test_user.locked_until = None
            test_user.password_hash = hash_password("RealPassword123")
        db.commit()
    finally:
        db.close()

    # Attempts 1 to 4 should return 401 Unauthorized
    for i in range(1, 5):
        res = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "victim_lockout_user", "password": "WrongPassword!"},
        )
        assert res.status_code == 401, f"Attempt {i} expected 401, got {res.status_code}"
        msg = res.json().get("error") or res.json().get("detail")
        assert msg == "Invalid username or password."

    # 5th attempt must trigger Lockout (429 Too Many Requests)
    res_5 = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "victim_lockout_user", "password": "WrongPassword!"},
    )
    assert res_5.status_code == 429, f"Attempt 5 expected 429, got {res_5.status_code}"
    msg_5 = res_5.json().get("error") or res_5.json().get("detail", "")
    assert "locked" in msg_5.lower()

    # 6th attempt while locked (even with correct password) must be rejected with 429
    res_6 = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "victim_lockout_user", "password": "RealPassword123"},
    )
    assert res_6.status_code == 429
    msg_6 = res_6.json().get("error") or res_6.json().get("detail", "")
    assert "locked" in msg_6.lower()


def test_anti_user_enumeration_generic_errors(client):
    """
    Test 2: Anti-Enumeration Protection
    Non-existent user and wrong password return exact identical error response.
    """
    res_wrong_pw = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "definitely_wrong_password"},
    )
    res_unknown_user = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "non_existent_hacker_999", "password": "any_password"},
    )

    assert res_wrong_pw.status_code == 401
    assert res_unknown_user.status_code == 401
    # Both messages must be completely identical
    msg_wrong = res_wrong_pw.json().get("error") or res_wrong_pw.json().get("detail")
    msg_unknown = res_unknown_user.json().get("error") or res_unknown_user.json().get("detail")
    assert msg_wrong == "Invalid username or password."
    assert msg_unknown == "Invalid username or password."


def test_gate_scoping_guard_isolation(client):
    """
    Test 3: Gate Scope Isolation
    A guard assigned to Gate 1 cannot access or record entries for Gate 2.
    """
    db = SessionLocal()
    try:
        # Create Gate 1 Guard
        guard = db.query(User).filter(User.username == "gate1_guard").first()
        if not guard:
            guard = User(
                username="gate1_guard",
                email="gate1guard@college.edu",
                password_hash=hash_password("pass123"),
                full_name="Gate 1 Security Officer",
                role="WATCHMAN",
                assigned_gate="Gate 1",
                is_active=True,
            )
            db.add(guard)
        else:
            guard.assigned_gate = "Gate 1"
            guard.failed_login_attempts = 0
            guard.locked_until = None
        db.commit()
    finally:
        db.close()

    # Login as Gate 1 guard
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "gate1_guard", "password": "pass123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Guard queries their own gate -> 200 OK
    res_own = client.get("/api/v1/gate/recent?gate_number=Gate 1", headers=headers)
    assert res_own.status_code == 200

    # 2. Guard attempts to access Gate 2 data -> 403 Forbidden!
    res_cross = client.get("/api/v1/gate/recent?gate_number=Gate 2", headers=headers)
    assert res_cross.status_code == 403
    assert "assigned to 'Gate 1'" in res_cross.json().get("detail", "")

    # 3. Guard attempts to log entry into Gate 2 -> 403 Forbidden!
    res_cross_entry = client.post(
        "/api/v1/gate/check-in",
        json={"person_name": "Test Person", "gate_number": "Gate 2", "direction": "IN"},
        headers=headers,
    )
    assert res_cross_entry.status_code == 403


def test_admin_cross_gate_access(client):
    """
    Test 4: Admin Gate Access
    Admins have global oversight across all gates.
    """
    # Login as admin
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "pass123"},
    )
    assert login_res.status_code == 200
    if login_res.json().get("mfa_required"):
        from app.services.auth_service import _mfa_store
        mfa_token = login_res.json()["mfa_token"]
        otp = _mfa_store[mfa_token]["otp"]
        mfa_res = client.post(
            "/api/v1/auth/verify-mfa",
            json={"mfa_token": mfa_token, "otp": otp},
        )
        assert mfa_res.status_code == 200
        token = mfa_res.json()["token"]
    else:
        token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Admin can access Gate 1, Gate 2, or all gates
    res_g1 = client.get("/api/v1/gate/recent?gate_number=Gate 1", headers=headers)
    assert res_g1.status_code == 200

    res_g2 = client.get("/api/v1/gate/recent?gate_number=Gate 2", headers=headers)
    assert res_g2.status_code == 200

    res_all = client.get("/api/v1/gate/recent", headers=headers)
    assert res_all.status_code == 200


def test_security_audit_logging_and_rbac(client):
    """
    Test 5: Security Audit Log Table & Access Control
    - Security events are stored in DB.
    - Admins can view audit logs.
    - Non-admins are rejected with 403 Forbidden.
    """
    # 1. Verify audit logs exist in DB
    db = SessionLocal()
    try:
        count = db.query(SecurityAuditLog).count()
        assert count > 0, "Expected security audit events to be populated in DB"
    finally:
        db.close()

    # 2. Watchman attempts to view audit logs -> 403 Forbidden
    guard_login = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "watchman1", "password": "pass123"},
    )
    assert guard_login.status_code == 200
    guard_headers = {"Authorization": f"Bearer {guard_login.json()['token']}"}

    res_guard_audit = client.get("/api/v1/auth/audit-logs", headers=guard_headers)
    assert res_guard_audit.status_code == 403

    # 3. Admin views audit logs -> 200 OK
    admin_login = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "pass123"},
    )
    assert admin_login.status_code == 200
    if admin_login.json().get("mfa_required"):
        from app.services.auth_service import _mfa_store
        mfa_token = admin_login.json()["mfa_token"]
        otp = _mfa_store[mfa_token]["otp"]
        mfa_res = client.post(
            "/api/v1/auth/verify-mfa",
            json={"mfa_token": mfa_token, "otp": otp},
        )
        assert mfa_res.status_code == 200
        admin_token = mfa_res.json()["token"]
    else:
        admin_token = admin_login.json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    res_admin_audit = client.get("/api/v1/auth/audit-logs", headers=admin_headers)
    assert res_admin_audit.status_code == 200
    data = res_admin_audit.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "eventType" in data[0]
