"""
conftest.py
------------
Shared pytest fixtures for the backend test suite. Puts backend/ on
sys.path (matching the convention already used by the existing
tests/test_*.py files) so every test module can `import models`,
`import fusion_engine`, `from api import app`, etc. without repeating
the sys.path boilerplate.

Also transparently wraps TestClient to handle operation_id resolution
for multi-operation backend routes while supporting legacy test invocations.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from typing import Optional
import fastapi.testclient
from fastapi.testclient import TestClient as _BaseTestClient

from models import GPSCoordinate, SensorType, SensorReading
from api import app, operations


LOC = GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950)


def make_reading(sensor_type, value, confidence=1.0, unit="", victim_id="TEST", location=LOC):
    """Shared helper for building a single SensorReading in tests."""
    return SensorReading(
        sensor_type=sensor_type,
        value=value,
        unit=unit,
        location=location,
        victim_id=victim_id,
        confidence=confidence,
    )


SCOPED_PREFIXES = (
    "/victims",
    "/queue",
    "/commander",
    "/watch",
    "/teams",
    "/staff",
    "/battery",
    "/power",
    "/rain",
    "/soil",
    "/seismic",
    "/tilt",
    "/environment",
    "/alerts",
    "/rescue-team",
    "/admin/victims/add",
    "/admin/team-members/add-unassigned",
    "/commander/team/assign-member",
    "/sensors",
    "/hazards",
    "/scenario/tick",
    "/scenario/assessment",
    "/scenario/status",
    "/telemetry",
    "/analytics",
    "/geospatial",
)


class OperationTestClient(_BaseTestClient):
    """
    TestClient that tracks the active operation_id and rewrites unscoped route URLs
    to their /operations/{operation_id}/... counterparts.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.operation_id: Optional[str] = None

    def _resolve_url(self, url: str) -> str:
        if url.startswith("/operations/"):
            return url
        for prefix in SCOPED_PREFIXES:
            if url == prefix or url.startswith(prefix + "/") or url.startswith(prefix + "?"):
                op_id = self.operation_id or (list(operations.keys())[-1] if operations else "__no_op__")
                return f"/operations/{op_id}{url}"
        if url.startswith("/admin/teams/") and url.endswith("/roster"):
            op_id = self.operation_id or (list(operations.keys())[-1] if operations else "__no_op__")
            team_part = url[len("/admin/teams/"):]
            return f"/operations/{op_id}/admin/teams/{team_part}"
        return url

    def request(self, method: str, url: str, **kwargs):
        resolved = self._resolve_url(url)
        resp = super().request(method, resolved, **kwargs)
        if url in ("/scenario/start", "/admin/scenario/create") and method.upper() == "POST" and resp.status_code == 200:
            data = resp.json()
            if "operation_id" in data:
                self.operation_id = data["operation_id"]
        elif url in ("/scenario/reset",) and method.upper() == "POST":
            self.operation_id = None
        return resp


# Monkey-patch fastapi.testclient.TestClient so all test files get OperationTestClient transparently
fastapi.testclient.TestClient = OperationTestClient


@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path, monkeypatch):
    """
    Ensure every test executes against an isolated, clean temporary SQLite database
    and clean isolated environment variables using monkeypatch.
    This guarantees running pytest NEVER contaminates or alters the real backend database or environment.
    """
    import db
    from api import operations, reset_alpha_m001_telemetry
    operations.clear()
    reset_alpha_m001_telemetry()
    test_db = str(tmp_path / "test_survivor_detection.db")
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", test_db)
    if "backend.db" in sys.modules:
        monkeypatch.setattr(sys.modules["backend.db"], "DEFAULT_DB_PATH", test_db)
    monkeypatch.setenv("SMS_PROVIDER", "SMSGATE")
    monkeypatch.setenv("SMSGATE_ENABLED", "true")
    monkeypatch.setenv("SMSGATE_LOCAL_URL", "http://192.168.1.100:8080")
    monkeypatch.setenv("SMSGATE_USERNAME", "test_user")
    monkeypatch.setenv("SMSGATE_PASSWORD", "test_password")
    monkeypatch.setenv("SMSGATE_SIM_NUMBER", "1")
    db.init_db(test_db)
    db.seed_builtin_scenarios(test_db)
    db.seed_builtin_teams(test_db)
    yield test_db
    operations.clear()
    reset_alpha_m001_telemetry()


@pytest.fixture
def api_client():
    """A fresh FastAPI TestClient with scenario state reset before use."""
    client = OperationTestClient(app)
    client.post("/scenario/reset")
    yield client
    client.post("/scenario/reset")


@pytest.fixture
def started_client(api_client):
    """api_client with a deterministic (seeded, degradation-off) scenario started."""
    r = api_client.post("/scenario/start", json={"seed": 42, "enable_degradation": False})
    assert r.status_code == 200
    api_client.operation_id = r.json().get("operation_id")
    return api_client


@pytest.fixture
def tmp_db_path(tmp_path):
    """A throwaway SQLite file path + initialized schema for db.py unit tests."""
    import db

    path = str(tmp_path / "test_survivor.db")
    db.init_db(path)
    return path
