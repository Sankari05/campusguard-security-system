"""
test_cors_configuration.py
--------------------------
Verifies FastAPI CORS middleware configuration:
1. Preflight OPTIONS /commander/assign from http://127.0.0.1:5000
2. Preflight OPTIONS /commander/assign from http://localhost:5000
3. Actual POST /commander/assign request headers
4. GET /commander/overview headers with CORS origin
5. Disallowed origin does not get Access-Control-Allow-Origin header
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from starlette.testclient import TestClient
from api import app


def test_cors_options_preflight_127_0_0_1_5000(started_client):
    """Verify OPTIONS preflight request to /commander/assign from http://127.0.0.1:5000 returns 200 and CORS headers."""
    headers = {
        "Origin": "http://127.0.0.1:5000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = started_client.options("/commander/assign", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5000"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_options_preflight_localhost_5000(started_client):
    """Verify OPTIONS preflight request from http://localhost:5000."""
    headers = {
        "Origin": "http://localhost:5000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = started_client.options("/commander/assign", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5000"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_post_assign_from_127_0_0_1_5000(started_client):
    """Verify POST /commander/assign contains Access-Control-Allow-Origin for 127.0.0.1:5000."""
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    headers = {"Origin": "http://127.0.0.1:5000"}
    response = started_client.post(
        "/commander/assign",
        json={"member_id": member["member_id"], "victim_id": victim["victim_id"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5000"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_get_overview_from_127_0_0_1_5000(started_client):
    """Verify GET /commander/overview contains Access-Control-Allow-Origin."""
    headers = {"Origin": "http://127.0.0.1:5000"}
    response = started_client.get("/commander/overview", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5000"


def test_cors_disallowed_origin(started_client):
    """Verify unknown origins do not receive allow headers."""
    headers = {
        "Origin": "http://unauthorized-domain.com",
        "Access-Control-Request-Method": "POST",
    }
    response = started_client.options("/commander/assign", headers=headers)
    assert response.headers.get("access-control-allow-origin") is None
