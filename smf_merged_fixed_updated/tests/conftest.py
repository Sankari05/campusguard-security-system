"""
tests/conftest.py
Centralized test configuration and fixtures for Pytest and Playwright.
MNC standard: clean isolation, mocked auth, reusable client fixtures.
"""

import os
import sys
import pytest
from starlette.testclient import TestClient

# Ensure root directory is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api import app, create_access_token


@pytest.fixture(scope="session")
def client():
    """Synchronous FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_token():
    """Generates a valid JWT token for the admin role."""
    return create_access_token("admin", "admin")


@pytest.fixture(scope="session")
def faculty_token():
    """Generates a valid JWT token for faculty member FAC001."""
    return create_access_token("FAC001", "faculty")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    """Authorization header dictionary for admin requests."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def faculty_headers(faculty_token):
    """Authorization header dictionary for faculty requests."""
    return {"Authorization": f"Bearer {faculty_token}"}
