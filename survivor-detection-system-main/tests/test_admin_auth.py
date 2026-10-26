"""
test_admin_auth.py
--------------------
Verifies that all operations and endpoints are directly accessible without
authentication (zero login / zero auth architecture).
"""


def test_login_endpoint_is_removed(api_client):
    r = api_client.post("/admin/login", json={"username": "admin", "password": "Admin@123"})
    assert r.status_code == 404


def test_signup_endpoint_is_removed(api_client):
    r = api_client.post("/admin/signup", json={"username": "newuser", "password": "pass123"})
    assert r.status_code == 404


def test_logout_endpoint_is_removed(api_client):
    r = api_client.post("/admin/logout")
    assert r.status_code == 404


def test_personnel_endpoint_direct_access(api_client):
    r = api_client.get("/admin/personnel")
    assert r.status_code == 200
    assert "personnel" in r.json()


def test_scenarios_endpoint_direct_access(api_client):
    r = api_client.get("/admin/scenarios")
    assert r.status_code == 200
    assert "scenarios" in r.json()


def test_teams_endpoint_direct_access(api_client):
    r = api_client.get("/admin/teams")
    assert r.status_code == 200
    assert "teams" in r.json()
