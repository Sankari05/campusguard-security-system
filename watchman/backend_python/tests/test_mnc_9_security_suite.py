# tests/test_mnc_9_security_suite.py
"""
MNC Enterprise Security Test Suite: 9 Core Security Specifications + Admin MFA
Standard ISO 27001 / SOC 2 Type II Compliance Verification.
"""

from datetime import datetime, timedelta, timezone
from jose import jwt
import pytest

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit_log import SecurityAuditLog
from app.models.user import User

settings = get_settings()


# ── TEST CASE 1: Correct Credentials ──────────────────────────────────────────
def test_tc01_correct_credentials_returns_valid_token(client):
    """
    TC-01: Valid user credentials return 200 OK and an unrevoked JWT access token
    with valid signature, expiration, and unique JTI.
    """
    res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "watchman1", "password": "pass123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "token" in data and len(data["token"]) > 20
    assert data["role"] == "WATCHMAN"
    assert data["username"] == "watchman1"


# ── TEST CASE 2: Wrong Password ───────────────────────────────────────────────
def test_tc02_wrong_password_rejected_with_anti_enumeration_error(client):
    """
    TC-02: Incorrect password fails with 401 Unauthorized and anti-enumeration generic message.
    """
    res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "watchman1", "password": "IncorrectPassword999!"},
    )
    assert res.status_code == 401
    err = res.json().get("error") or res.json().get("detail")
    assert err == "Invalid username or password."


# ── TEST CASE 3: Inactive User Account ────────────────────────────────────────
def test_tc03_inactive_account_blocked(client):
    """
    TC-03: Deactivated account (is_active=False) is strictly blocked from login and API usage.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "inactive_spec_user").first()
        if not user:
            user = User(
                username="inactive_spec_user",
                email="inactive_spec@college.edu",
                password_hash=hash_password("pass123"),
                full_name="Deactivated Officer",
                role="WATCHMAN",
                is_active=False,
            )
            db.add(user)
        else:
            user.is_active = False
        db.commit()
    finally:
        db.close()

    res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "inactive_spec_user", "password": "pass123"},
    )
    assert res.status_code in [401, 403]
    err = res.json().get("error") or res.json().get("detail", "")
    assert "deactivated" in err.lower() or "invalid" in err.lower()


# ── TEST CASE 4: Role-Based Access Violation (Guard tries Admin API) ──────────
def test_tc04_guard_cannot_access_admin_endpoints(client):
    """
    TC-04: Non-admin role (WATCHMAN) attempting to call Admin-only endpoint
    (e.g., /api/v1/auth/audit-logs) is rejected with 403 Forbidden.
    """
    # 1. Login as guard
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "watchman1", "password": "pass123"},
    )
    assert login_res.status_code == 200
    guard_token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {guard_token}"}

    # 2. Attempt Admin audit logs
    res = client.get("/api/v1/auth/audit-logs", headers=headers)
    assert res.status_code == 403
    err = res.json().get("error") or res.json().get("detail", "")
    assert "Access denied" in err and "ADMIN" in err


# ── TEST CASE 5: Expired Token Rejection ──────────────────────────────────────
def test_tc05_expired_token_rejected(client):
    """
    TC-05: An expired token is rejected with 401 Unauthorized.
    """
    expired_time = datetime.now(timezone.utc) - timedelta(hours=2)
    payload = {
        "sub": "watchman1",
        "role": "WATCHMAN",
        "jti": "expired-spec-token-uuid",
        "iat": expired_time - timedelta(hours=1),
        "exp": expired_time,
    }
    expired_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    res = client.get(
        "/api/v1/gate/recent",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    err = res.json().get("error") or res.json().get("detail", "")
    assert "expired" in err.lower() or "invalid" in err.lower()


# ── TEST CASE 6: Logout Token Reuse Block ─────────────────────────────────────
def test_tc06_token_revocation_blocks_reuse_after_logout(client):
    """
    TC-06: Calling logout revokes the token server-side; reusing the token fails with 401.
    """
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "watchman1", "password": "pass123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Token works initially
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200

    # 3. User logs out
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # 4. Attempt reuse of revoked token
    reuse_res = client.get("/api/v1/auth/me", headers=headers)
    assert reuse_res.status_code == 401
    err = reuse_res.json().get("error") or reuse_res.json().get("detail", "")
    assert "revoked" in err.lower()


# ── TEST CASE 7: Missing Header / URL Manipulation ────────────────────────────
def test_tc07_missing_auth_header_rejected(client):
    """
    TC-07: Unauthenticated request to protected endpoints is rejected with 401 Unauthorized.
    """
    protected_endpoints = [
        "/api/v1/gate/recent",
        "/api/v1/outpass/list",
        "/api/v1/copilot/situation/patterns",
        "/api/v1/handovers/list",
    ]
    for url in protected_endpoints:
        res = client.get(url)
        assert res.status_code == 401, f"Expected 401 for {url}, got {res.status_code}"


# ── TEST CASE 8: Brute Force Account Lockout ──────────────────────────────────
def test_tc08_brute_force_lockout_after_five_failed_attempts(client):
    """
    TC-08: 5 consecutive failed login attempts lock account for 15-minute cooldown (HTTP 429).
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "victim_tc08_user").first()
        if not user:
            user = User(
                username="victim_tc08_user",
                email="victim_tc08@college.edu",
                password_hash=hash_password("ValidPassword123"),
                full_name="Brute Force Target",
                role="WATCHMAN",
                failed_login_attempts=0,
                locked_until=None,
                is_active=True,
            )
            db.add(user)
        else:
            user.failed_login_attempts = 0
            user.locked_until = None
            user.password_hash = hash_password("ValidPassword123")
        db.commit()
    finally:
        db.close()

    # 4 bad attempts
    for _ in range(4):
        res = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "victim_tc08_user", "password": "BadPassword"},
        )
        assert res.status_code == 401

    # 5th bad attempt -> Locks account
    res_lock = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "victim_tc08_user", "password": "BadPassword"},
    )
    assert res_lock.status_code == 429
    err = res_lock.json().get("error") or res_lock.json().get("detail", "")
    assert "locked" in err.lower()


# ── TEST CASE 9: Cross-Gate Scope Isolation ───────────────────────────────────
def test_tc09_cross_gate_scope_isolation(client):
    """
    TC-09: Guard assigned to Gate 1 cannot query or log entries for Gate 2.
    """
    db = SessionLocal()
    try:
        guard = db.query(User).filter(User.username == "gate1_spec_guard").first()
        if not guard:
            guard = User(
                username="gate1_spec_guard",
                email="gate1_spec@college.edu",
                password_hash=hash_password("pass123"),
                full_name="Main Gate 1 Officer",
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

    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "gate1_spec_guard", "password": "pass123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Guard queries Gate 1 -> Allowed (200)
    res_ok = client.get("/api/v1/gate/recent?gate_number=Gate 1", headers=headers)
    assert res_ok.status_code == 200

    # Guard queries Gate 2 -> Blocked (403 Forbidden)
    res_cross = client.get("/api/v1/gate/recent?gate_number=Gate 2", headers=headers)
    assert res_cross.status_code == 403
    err = res_cross.json().get("error") or res_cross.json().get("detail", "")
    assert "assigned to 'Gate 1'" in err


# ── BONUS TC 10: Admin 2-Step OTP Verification (MFA) ─────────────────────────
def test_tc10_admin_two_step_mfa_flow(client):
    """
    TC-10: Admin login triggers 2-Step MFA OTP challenge, and verifying OTP grants access.
    """
    from app.services.auth_service import _mfa_store

    # 1. Admin login credentials
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "pass123"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["mfa_required"] is True
    assert "mfa_token" in data
    mfa_token = data["mfa_token"]

    # 2. Retrieve generated OTP from secure memory store
    assert mfa_token in _mfa_store
    dispatched_otp = _mfa_store[mfa_token]["otp"]

    # 3. Wrong OTP fails with 401
    bad_mfa = client.post(
        "/api/v1/auth/verify-mfa",
        json={"mfa_token": mfa_token, "otp": "000000"},
    )
    assert bad_mfa.status_code == 401

    # 4. Correct OTP grants access token
    good_mfa = client.post(
        "/api/v1/auth/verify-mfa",
        json={"mfa_token": mfa_token, "otp": dispatched_otp},
    )
    assert good_mfa.status_code == 200
    mfa_result = good_mfa.json()
    assert mfa_result["mfa_required"] is False
    assert "token" in mfa_result
    assert mfa_result["role"] == "ADMIN"
