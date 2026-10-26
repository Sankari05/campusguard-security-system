"""
tests/e2e/test_admin_portal_e2e.py
Enterprise Playwright E2E Test Suite for EduTrack Pro.
Tests real user browser flows with Playwright Chromium:
1. Admin Authentication & Dashboard Navigation
2. Student Management: Data loading & KPI Counts
3. Attendance Overrides: Clean header (no subtitle) & Actions
4. Reports & Analytics: Subtitle removal & Clean KPI dashboard
"""

import json
import pytest
from playwright.sync_api import sync_playwright, expect
from app.main import create_access_token

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def admin_auth_token():
    return create_access_token("admin", "admin")


@pytest.fixture(scope="module")
def browser_instance():
    """Launches Playwright Chromium browser."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


def test_e2e_admin_login(browser_instance):
    """Flow 1: Admin logs in through the dedicated Admin portal login card."""
    context = browser_instance.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded")

    # Fill Admin credentials
    page.locator("#adminEmailInput").fill("admin")
    page.locator("#adminPass").fill("Admin@123")
    page.locator("#btnAdminSignIn").click()

    # Verify App Shell opens
    app_shell = page.locator("#appShell")
    expect(app_shell).to_be_visible(timeout=5000)

    # Verify Sidebar brand
    expect(page.locator(".sb-brand")).to_contain_text("EduTrack")
    context.close()


def test_e2e_student_management_table_loads(browser_instance, admin_auth_token):
    """Flow 2: Student Management table loads 4 active students with stats."""
    context = browser_instance.new_context(viewport={"width": 1280, "height": 800})

    # Pre-inject authenticated session to test direct portal interaction
    admin_user = json.dumps({"username": "admin", "role": "admin", "name": "ADMIN"})
    context.add_init_script(f"""
        sessionStorage.setItem('_token', '{admin_auth_token}');
        sessionStorage.setItem('_role', 'admin');
        sessionStorage.setItem('_portal', 'admin');
        sessionStorage.setItem('_user', '{admin_user}');
    """)

    page = context.new_page()
    page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded")

    # Navigate to Students Management
    page.locator("#sbNav a[data-page='hod-students']").click()

    # Wait for page to be visible
    expect(page.locator("#pg-hod-students")).to_be_visible(timeout=10000)

    # Verify Total Students count is displayed (e.g. 4)
    total_stat = page.locator("#hsTotalStudents")
    expect(total_stat).to_be_visible(timeout=10000)
    expect(total_stat).not_to_have_text("—", timeout=10000)

    # Verify table has loaded rows
    table_rows = page.locator("#hsTableWrap table tbody tr")
    expect(table_rows.first).to_be_visible(timeout=10000)
    context.close()


def test_e2e_attendance_overrides_clean_header(browser_instance, admin_auth_token):
    """Flow 3: Attendance Overrides has clean header without redundant subtitle."""
    context = browser_instance.new_context(viewport={"width": 1280, "height": 800})
    admin_user = json.dumps({"username": "admin", "role": "admin", "name": "ADMIN"})
    context.add_init_script(f"""
        sessionStorage.setItem('_token', '{admin_auth_token}');
        sessionStorage.setItem('_role', 'admin');
        sessionStorage.setItem('_portal', 'admin');
        sessionStorage.setItem('_user', '{admin_user}');
    """)

    page = context.new_page()
    page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded")

    # Navigate to Overrides
    page.locator("#sbNav a[data-page='overrides']").click()
    expect(page.locator("#pg-overrides")).to_be_visible(timeout=10000)

    # Verify redundant subtitle is NOT in page
    overrides_text = page.locator("#pg-overrides").inner_text()
    assert "Hierarchical role-based corrections with full audit trail" not in overrides_text

    # Verify New Override action button is present and active
    expect(page.locator("#ovNewOverrideBtn")).to_be_visible()
    context.close()


def test_e2e_reports_analytics_clean_header(browser_instance, admin_auth_token):
    """Flow 4: Reports & Analytics has clean header without redundant subtitle."""
    context = browser_instance.new_context(viewport={"width": 1280, "height": 800})
    admin_user = json.dumps({"username": "admin", "role": "admin", "name": "ADMIN"})
    context.add_init_script(f"""
        sessionStorage.setItem('_token', '{admin_auth_token}');
        sessionStorage.setItem('_role', 'admin');
        sessionStorage.setItem('_portal', 'admin');
        sessionStorage.setItem('_user', '{admin_user}');
    """)

    page = context.new_page()
    page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded")

    # Navigate to Reports
    page.locator("#sbNav a[data-page='reports']").click()
    expect(page.locator("#pg-reports")).to_be_visible(timeout=10000)

    # Verify redundant subtitle is NOT in page
    reports_text = page.locator("#pg-reports").inner_text()
    assert "Department Attendance Monitoring & Insights" not in reports_text

    context.close()

