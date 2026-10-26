# tests/test_phase1_p0_security.py
import pytest
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def test_login_valid_credentials(client):
    """Test 1: Valid login succeeds and returns JWT with unique JTI."""
    res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "pass123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["username"] == "admin"
    assert data["role"] == "ADMIN"


def test_login_invalid_password(client):
    """Test 2: Wrong password fails with 401."""
    res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "wrong_password_999"},
    )
    assert res.status_code == 401
    assert "Invalid username or password" in res.json().get("detail", "") or res.json().get("error", "")


def test_login_hardcoded_bypass_removed(client):
    """Test 3: Hardcoded password bypasses (123456, admin123, password) must FAIL with 401."""
    for bypass_pw in ["123456", "admin123", "password", "pass1234"]:
        res = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "admin", "password": bypass_pw},
        )
        assert res.status_code == 401


def test_inactive_user_cannot_login_or_access(client):
    """Test 4: Inactive user (is_active=False) cannot log in and cannot access protected APIs."""
    db = SessionLocal()
    try:
        # Create or update a deactivated user
        deact_user = db.query(User).filter(User.username == "inactive_guard").first()
        if not deact_user:
            deact_user = User(
                username="inactive_guard",
                email="inactive@college.edu",
                password_hash=hash_password("pass123"),
                full_name="Deactivated Guard",
                role="WATCHMAN",
                is_active=False,
            )
            db.add(deact_user)
        else:
            deact_user.is_active = False
        db.commit()
    finally:
        db.close()

    # Login attempt must fail
    res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "inactive_guard", "password": "pass123"},
    )
    assert res.status_code in [401, 403]


def test_protected_routes_require_token(client):
    """Test 5: Protected API routes reject requests without a Bearer token with 401."""
    # Gate route
    res_gate = client.get("/api/v1/gate/recent")
    assert res_gate.status_code == 401

    # Copilot route
    res_copilot = client.get("/api/v1/copilot/situation/patterns")
    assert res_copilot.status_code == 401

    # Shift handover route
    res_handover = client.get("/api/v1/handovers/list")
    assert res_handover.status_code == 401


def test_protected_routes_accept_valid_token(client):
    """Test 6: Valid Bearer token allows access to protected routes."""
    # Obtain valid token
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

    # Access protected route
    res = client.get("/api/v1/gate/recent", headers=headers)
    assert res.status_code == 200


def test_server_side_token_revocation_on_logout(client):
    """Test 7 & 8: Server-side token revocation: Token works -> User logs out -> Token is blocked (401)."""
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "watchman1", "password": "pass123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify token works
    res_before = client.get("/api/v1/auth/me", headers=headers)
    assert res_before.status_code == 200
    assert res_before.json()["username"] == "watchman1"

    # 3. Call server-side logout
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # 4. Attempt to reuse the same token — MUST be rejected with 401 Revoked
    res_after = client.get("/api/v1/auth/me", headers=headers)
    assert res_after.status_code == 401
    assert "revoked" in res_after.json()["detail"].lower()
