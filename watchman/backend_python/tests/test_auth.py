# tests/test_auth.py
def test_login_demo_admin(client):
    response = client.post(
        "/api/auth/login",
        json={"username_or_email": "admin", "password": "pass123", "role": "ADMIN"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["role"] == "ADMIN"
