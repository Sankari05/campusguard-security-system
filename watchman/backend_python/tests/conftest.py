# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.user import User


@pytest.fixture(scope="session")
def client():
    """Provides a TestClient fixture for running API integration tests."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_lockouts_between_tests():
    """Ensures test users are unlocked before and after each individual test run."""
    db = SessionLocal()
    try:
        db.query(User).filter(
            User.username.in_(["admin", "watchman1", "victim_lockout_user", "gate1_guard"])
        ).update({"failed_login_attempts": 0, "locked_until": None}, synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    yield
