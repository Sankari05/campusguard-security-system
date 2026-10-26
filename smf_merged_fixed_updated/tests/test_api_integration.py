"""
tests/test_api_integration.py
Integration tests validating FastAPI endpoints, authentication, and responses.
"""

import pytest


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_unauthorized_access(client):
    # Endpoints requiring token must reject requests with 401
    response = client.get("/api/students/stats")
    assert response.status_code == 401


def test_admin_students_list(client, admin_headers):
    response = client.get("/api/students/list", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    # Expect either array or object containing students list
    students = data if isinstance(data, list) else data.get("students", [])
    assert isinstance(students, list)
    assert len(students) > 0


def test_admin_students_stats(client, admin_headers):
    response = client.get("/api/students/stats", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "present_today" in data
    assert "absent_today" in data
    assert "critical_count" in data


def test_reports_analytics_endpoint(client, admin_headers):
    response = client.get("/api/reports/analytics?days=180", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "year_wise" in data
    assert "section_wise" in data
    assert "trend" in data
