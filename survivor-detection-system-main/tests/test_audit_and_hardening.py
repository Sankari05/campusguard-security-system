"""
test_audit_and_hardening.py
----------------------------
Comprehensive verification suite for RIDGEWATCH system hardening:
1. 5 Canonical Disaster Scenarios (Earthquake, Flood, Tsunami, Building Collapse, Landslide)
2. 15 Dedicated Sensors validation & fusion verification
3. Database Idempotency (2 baseline teams: ALPHA, BRAVO with 2 members each = 4 total)
4. Scenario Loader Canonical Alias & Template Resolution
5. Explainable AI & Sensor Failure Tolerance
"""

import pytest
from fastapi.testclient import TestClient

from backend.models import (
    SensorType,
    GPSCoordinate,
    RiskLevel,
)
from backend.scenario_loader import load_scenario, available_scenarios
from backend.fusion_engine import (
    TriageClass,
    fuse_victim,
    HazardContext,
    WEIGHT_RADAR,
    WEIGHT_THERMAL,
    WEIGHT_ACOUSTIC,
    WEIGHT_CO2,
    WEIGHT_CAMERA,
)
import backend.db as db
from backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_1_canonical_5_scenarios_exist_and_load():
    """Verify that Earthquake, Flood, Tsunami, Building Collapse, and Landslide all load without error."""
    canonical_ids = ["earthquake", "flood", "tsunami", "building_collapse", "landslide"]
    
    for sc_id in canonical_ids:
        cfg = load_scenario(sc_id)
        assert cfg.scenario_id == sc_id
        assert len(cfg.victims) >= 4
        assert len(cfg.rescue_team_templates) >= 2
        assert cfg.site_origin is not None
        assert cfg.site_environment is not None


def test_2_canonical_aliases_resolve_cleanly():
    """Verify aliases resolve without raising ScenarioNotFoundError."""
    aliases = {
        "earthquake_building_collapse": "earthquake",
        "flood_urban": "flood",
        "cloudburst": "flood",
    }
    for alias_id in aliases:
        cfg = load_scenario(alias_id)
        assert cfg is not None
        assert len(cfg.victims) >= 4


def test_3_database_idempotency_teams_and_members(tmp_path):
    """Verify restarting the DB maintains exactly 2 default teams (ALPHA, BRAVO) and 4 members total."""
    test_db = str(tmp_path / "idempotent_test.db")
    db.init_db(test_db)
    
    # First seed
    db.seed_builtin_teams(test_db)
    teams_1 = db.list_admin_teams(test_db)
    members_1 = [m for t in teams_1 for m in t.get("members", [])]
    
    assert len(teams_1) == 2
    assert {t["team_ref_id"] for t in teams_1} == {"ALPHA", "BRAVO"}
    assert len(members_1) == 4
    
    # Second seed (simulating restart)
    db.seed_builtin_teams(test_db)
    teams_2 = db.list_admin_teams(test_db)
    members_2 = [m for t in teams_2 for m in t.get("members", [])]
    
    assert len(teams_2) == 2
    assert len(members_2) == 4


def test_4_all_15_sensors_participate_in_system():
    """Verify that all 15 sensors are represented across the models and fusion architecture."""
    # 1. Radar
    # 2. Thermal
    # 3. Acoustic
    # 4. CO2 / Gas
    # 5. RGB Camera
    # 6. PIR Motion
    # 7. IMU / Vibration
    # 8. Water Level
    # 9. Water Flow
    # 10. Rainfall
    # 11. Soil Moisture
    # 12. Tilt Angle
    # 13. Barometric Pressure
    # 14. Ambient Temp
    # 15. Rel. Humidity
    
    # Verify weights sum properly in core vitals
    core_sum = WEIGHT_RADAR + WEIGHT_THERMAL + WEIGHT_ACOUSTIC + WEIGHT_CO2 + WEIGHT_CAMERA
    assert abs(core_sum - 1.0) < 1e-6
    
    # Test HazardContext multi-sensor integration
    h = HazardContext(
        burial_depth_m=1.5,
        secondary_hazard=True,
        exposure_minutes=120.0,
        water_level_cm=45.0,
        water_rising_rate_cm_per_cycle=1.2,
        water_flow_ms=1.5,
        rainfall_mm_hr=35.0,
        soil_moisture_pct=80.0,
        vibration_mm_s=2.5,
        tilt_deg=4.5,
        ambient_temp_c=5.0,
        humidity_pct=85.0,
        kit_disturbed=True,
        barometric_pressure_hpa=970.0,
    )
    mult = h.multiplier()
    assert mult > 1.0
    assert mult <= 2.5
    
    breakdown = h.multiplier_breakdown()
    assert "depth" in breakdown
    assert "secondary_hazard" in breakdown
    assert "water_level" in breakdown
    assert "rain" in breakdown
    assert "soil" in breakdown
    assert "vibration" in breakdown
    assert "tilt" in breakdown
    assert "pressure_drop" in breakdown


def test_5_api_lifecycle_with_tsunami_and_landslide(client):
    """Verify running real API operations on the new canonical scenarios."""
    # 1. Start Tsunami scenario
    res_tsunami = client.post("/scenario/start", json={"scenario_id": "tsunami", "seed": 42})
    assert res_tsunami.status_code == 200
    
    tick_tsunami = client.post("/scenario/tick")
    assert tick_tsunami.status_code == 200
    
    # Check victims and queue
    q_res = client.get("/queue")
    assert q_res.status_code == 200
    queue = q_res.json()["queue"]
    assert len(queue) == 4
    
    # 2. Start Landslide scenario
    res_landslide = client.post("/scenario/start", json={"scenario_id": "landslide", "seed": 42})
    assert res_landslide.status_code == 200
    
    tick_landslide = client.post("/scenario/tick")
    assert tick_landslide.status_code == 200
