# tests/test_guardmate_lifecycle.py
"""
GuardMate End-to-End 18-Step Enterprise SaaS Lifecycle Test Suite.
Tests:
1. Public Vertical Inquiry (College, Hospital, Apartment, Factory, Office)
2. Organization Self-Serve Registration (PENDING_APPROVAL state)
3. Platform Super-Admin Review & Vetting
4. Platform Super-Admin Approval & Automated Tenant Admin Provisioning
5. Super-Admin Rejection with Reason
6. Tenant Admin Gate & Duty Shift Configuration
7. Tenant Admin Watchman Account Creation & Gate/Shift Assignment
8. Watchman Authentication & Adaptive Industry Vertical Profile Delivery
9. Daily Operations & Scoped Security Incident Logging
10. Multi-Tenant Data Isolation (Zero Cross-Tenant Leakage)
"""

import pytest
from starlette.testclient import TestClient
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.models.organization import Organization, OrganizationGate, OrganizationShift, IncidentReport
from app.models.user import User


def test_step01_public_supported_organization_types(client: TestClient):
    """Step 1 & 3: Landing page queries the 5 supported GuardMate industry verticals."""
    res = client.get("/api/v1/organizations/types")
    assert res.status_code == 200
    types = res.json()
    assert len(types) == 5
    type_names = {t["type"] for t in types}
    expected = {"COLLEGE", "HOSPITAL", "APARTMENT", "FACTORY", "OFFICE"}
    assert type_names == expected


def test_step02_to_05_organization_registration_and_db_save(client: TestClient):
    """Step 2, 4, 5: New organization registers and details are saved in DB as PENDING_APPROVAL."""
    payload = {
        "name": "Fortis Care Heart Institute",
        "org_type": "HOSPITAL",
        "contact_person": "Dr. Arvind Swaminathan",
        "contact_email": "chief.admin@fortiscare.org",
        "contact_phone": "9884011223",
        "address": "142 Arcot Road, Vadapalani",
        "city": "Chennai",
        "gate_count": 3,
        "expected_guards": 10,
        "security_requirements": "Ambulance emergency fast-track, ICU visitors biometric pass, oxygen storage guard",
    }
    res = client.post("/api/v1/organizations/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "PENDING_APPROVAL"
    assert data["org_type"] == "HOSPITAL"
    assert "fortis-care-heart-institute" in data["slug"]

    # Verify directly in DB
    db = SessionLocal()
    try:
        saved = db.query(Organization).filter(Organization.id == data["id"]).first()
        assert saved is not None
        assert saved.name == "Fortis Care Heart Institute"
        assert saved.status == "PENDING_APPROVAL"
    finally:
        db.close()


def test_step06_super_admin_review_pending_organizations(client: TestClient):
    """Step 6: Registered organization details appear in Platform Super Admin dashboard."""
    # Create Super-Admin token
    token = create_access_token(subject="superadmin", role="SUPER_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/super-admin/organizations?status=PENDING_APPROVAL", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(o["status"] == "PENDING_APPROVAL" for o in data)


def test_step07_and_08_super_admin_approval_and_admin_account_creation(client: TestClient):
    """Step 7 & 8: Super Admin approves organization, which creates the Tenant Admin account."""
    token = create_access_token(subject="superadmin", role="SUPER_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    try:
        pending_org = db.query(Organization).filter(Organization.status == "PENDING_APPROVAL").first()
        assert pending_org is not None
        org_id = pending_org.id
    finally:
        db.close()

    # Approve application
    res = client.post(
        f"/api/v1/super-admin/organizations/{org_id}/approve",
        json={"admin_username": f"admin_fortis_{org_id}", "admin_password": "pass123"},
        headers=headers,
    )
    assert res.status_code == 200
    approval_data = res.json()
    assert approval_data["success"] is True
    assert "admin_credentials" in approval_data
    cred = approval_data["admin_credentials"]
    assert cred["role"] == "ORG_ADMIN"

    # Verify admin user in DB
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == cred["username"]).first()
        assert admin_user is not None
        assert admin_user.role == "ORG_ADMIN"
        assert admin_user.organization_id == org_id
    finally:
        db.close()


def test_step07_super_admin_rejection_flow(client: TestClient):
    """Step 7 (Alternative): Super Admin rejects invalid organization with reason."""
    # Register a spam org
    spam_res = client.post(
        "/api/v1/organizations/register",
        json={
            "name": "Spam Shell Corp",
            "org_type": "OFFICE",
            "contact_person": "Spam User",
            "contact_email": "spam@fakecorp.xyz",
            "contact_phone": "1112223334",
            "security_requirements": "None",
        },
    )
    assert spam_res.status_code == 201
    org_id = spam_res.json()["id"]

    token = create_access_token(subject="superadmin", role="SUPER_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    reject_res = client.post(
        f"/api/v1/super-admin/organizations/{org_id}/reject",
        json={"reason": "Incomplete corporate credentials and unverified email address."},
        headers=headers,
    )
    assert reject_res.status_code == 200
    data = reject_res.json()
    assert data["status"] == "REJECTED"
    assert "Incomplete corporate credentials" in data["rejection_reason"]


def test_step09_organization_setup_gates_and_shifts(client: TestClient):
    """Step 9: Tenant Admin configures gates and duty shifts."""
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.status == "APPROVED").first()
        assert org is not None
        admin_user = db.query(User).filter(User.organization_id == org.id, User.role == "ORG_ADMIN").first()
        assert admin_user is not None
        username = admin_user.username
    finally:
        db.close()

    token = create_access_token(subject=username, role="ORG_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch setup overview
    setup_res = client.get("/api/v1/tenant/setup", headers=headers)
    assert setup_res.status_code == 200

    # 2. Add custom gate
    gate_res = client.post(
        "/api/v1/tenant/gates",
        json={"gate_number": "Gate 9 VIP", "gate_name": "VIP & Diplomatic Entry", "gate_type": "VEHICLE"},
        headers=headers,
    )
    assert gate_res.status_code == 200
    assert gate_res.json()["gate_number"] == "Gate 9 VIP"

    # 3. Add custom shift
    shift_res = client.post(
        "/api/v1/tenant/shifts",
        json={"shift_name": "Weekend Special Patrol", "start_time": "10:00", "end_time": "18:00"},
        headers=headers,
    )
    assert shift_res.status_code == 200
    assert shift_res.json()["shift_name"] == "Weekend Special Patrol"


def test_step10_to_12_tenant_admin_provisions_watchman(client: TestClient):
    """Step 10, 11, 12: Admin creates Watchman and assigns organization, gate, and shift."""
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.status == "APPROVED").first()
        admin_user = db.query(User).filter(User.organization_id == org.id, User.role == "ORG_ADMIN").first()
        username = admin_user.username
        org_id = org.id
    finally:
        db.close()

    import uuid
    token = create_access_token(subject=username, role="ORG_ADMIN")
    headers = {"Authorization": f"Bearer {token}"}
    guard_username = f"guard_{uuid.uuid4().hex[:6]}"
    guard_res = client.post(
        "/api/v1/tenant/guards",
        json={
            "full_name": "Senthil Nathan",
            "username": guard_username,
            "email": f"{guard_username}@guardmate.test",
            "phone_number": "9876543111",
            "assigned_gate": "Gate 9 VIP",
            "assigned_shift": "Weekend Special Patrol",
            "password": "pass123",
        },
        headers=headers,
    )
    assert guard_res.status_code == 200
    guard_data = guard_res.json()
    assert guard_data["role"] == "WATCHMAN"
    assert guard_data["assigned_gate"] == "Gate 9 VIP"
    assert guard_data["assigned_shift"] == "Weekend Special Patrol"


def test_step13_to_15_watchman_login_and_adaptive_profile(client: TestClient):
    """Step 13, 14, 15: Watchman authenticates and receives tailored industry operational modules."""
    # Login as seeded hospital watchman
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "watchman_hospital", "password": "pass123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch adaptive watchman profile
    profile_res = client.get("/api/v1/watchman/profile", headers=headers)
    assert profile_res.status_code == 200
    profile = profile_res.json()

    assert profile["organization"]["org_type"] == "HOSPITAL"
    vertical = profile["vertical_profile"]
    assert "Hospital" in vertical["title"]
    module_ids = [m["id"] for m in vertical["modules"]]
    assert "ambulance" in module_ids
    assert "icu_passes" in module_ids


def test_step16_watchman_daily_security_incident_logging(client: TestClient):
    """Step 16: Watchman logs a security incident scoped to their organization."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "watchman_hospital", "password": "pass123"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    inc_res = client.post(
        "/api/v1/watchman/incidents",
        json={
            "incident_type": "MEDICAL_EMERGENCY",
            "severity": "HIGH",
            "gate_number": "Ambulance Bay",
            "description": "Ambulance arriving with trauma patient. Fast-track lane activated.",
            "action_taken": "Cleared passenger vehicles, summoned ER stretcher team.",
        },
        headers=headers,
    )
    assert inc_res.status_code == 200
    incident = inc_res.json()
    assert incident["incident_type"] == "MEDICAL_EMERGENCY"
    assert incident["status"] == "OPEN"

    # List incidents
    list_res = client.get("/api/v1/watchman/incidents", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) > 0


def test_step17_and_18_tenant_telemetry_and_strict_data_isolation(client: TestClient):
    """Step 17 & 18: Admin monitors telemetry, and guards cannot access another org's admin setup."""
    # 1. Tenant Admin of Hospital views telemetry
    login_admin = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin_hospital", "password": "pass123"},
    )
    # If admin has MFA challenge, verify it
    if login_admin.json().get("mfa_required"):
        from app.services.auth_service import _mfa_store
        mfa_token = login_admin.json()["mfa_token"]
        otp = _mfa_store[mfa_token]["otp"]
        mfa_res = client.post("/api/v1/auth/verify-mfa", json={"mfa_token": mfa_token, "otp": otp})
        admin_token = mfa_res.json()["token"]
    else:
        admin_token = login_admin.json()["token"]

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    telem_res = client.get("/api/v1/tenant/telemetry", headers=admin_headers)
    assert telem_res.status_code == 200
    telem = telem_res.json()
    assert telem["org_type"] == "HOSPITAL"
    assert "guards_on_duty_count" in telem

    # 2. Watchman from College tries to access Tenant Admin Setup -> 403 Forbidden!
    login_guard = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "watchman_college", "password": "pass123"},
    )
    guard_headers = {"Authorization": f"Bearer {login_guard.json()['token']}"}
    forbidden_res = client.get("/api/v1/tenant/setup", headers=guard_headers)
    assert forbidden_res.status_code == 403
