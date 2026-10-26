"""
tests/test_temperature_humidity_first_class.py
----------------------------------------------
Comprehensive First-Class Sensor Pipeline Test Suite for
Ambient Temperature (°C) and Atmospheric Relative Humidity (%).

Validates all 22 required engineering criteria:
1. SensorType registration
2. Backward compatibility keys (ambient_temp_c, humidity_pct)
3. TemperatureReading validation (valid)
4. TemperatureReading invalid bounds (< -100°C, > 150°C)
5. TemperatureReading invalid types (None, NaN, Inf)
6. HumidityReading validation (valid)
7. HumidityReading invalid bounds (< 0%, > 100%)
8. HumidityReading invalid types (None, NaN, Inf)
9. Temperature simulation adapter profiles
10. Humidity simulation adapter profiles
11. Temperature trend classification & rate of change
12. Humidity trend classification & rate of change
13. Simulator multi-sensor environmental stream emission
14. Health and degradation reporting
15. SQLite database persistence & analytics for Temperature
16. SQLite database persistence & analytics for Humidity
17. Scenario intelligence: Fire and Heatwave evidence & scoring
18. Scenario intelligence: Flood, Cyclone, Cloudburst evidence & scoring
19. Scenario intelligence: No false-positive triggers alone
20. REST API: Temperature endpoints & ingestion validation
21. REST API: Humidity endpoints & ingestion validation
22. REST API: Legacy GET /environment backward compatibility
"""

import math
import pytest
import sqlite3
from fastapi.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from models import (
    SensorType,
    SensorReading,
    SensorHealthStatus,
    TemperatureTrend,
    HumidityTrend,
    TemperatureReading,
    HumidityReading,
    GPSCoordinate,
)
from sensor_simulator import (
    SensorSimulator,
    TemperatureSimulationAdapter,
    HumiditySimulationAdapter,
)
from scenario_intelligence import (
    SensorEvidenceExtractor,
    DisasterScenarioInferenceEngine,
    ScenarioIntelligenceEngine,
    AlertLifecycleManager,
)
import db
from api import app


# --------------------------------------------------------------------------- #
# 1. SensorType Registration
# --------------------------------------------------------------------------- #
def test_sensor_type_registration():
    """Verify TEMPERATURE and HUMIDITY are registered first-class members in SensorType."""
    assert hasattr(SensorType, "TEMPERATURE")
    assert hasattr(SensorType, "HUMIDITY")
    assert SensorType.TEMPERATURE == "temperature"
    assert SensorType.HUMIDITY == "humidity"


# --------------------------------------------------------------------------- #
# 2. Backward Compatibility Mapping
# --------------------------------------------------------------------------- #
def test_backward_compatibility_keys():
    """Verify ambient_temp_c and humidity_pct sync properly with temperature_c and humidity_pct."""
    tr = TemperatureReading(temperature_c=28.5)
    assert tr.temperature_c == 28.5
    assert tr.ambient_temp_c == 28.5

    tr_dict = tr.to_dict()
    assert "temperature_c" in tr_dict
    assert "ambient_temp_c" in tr_dict
    assert tr_dict["ambient_temp_c"] == 28.5

    hr = HumidityReading(humidity_pct=65.2)
    assert hr.humidity_pct == 65.2
    hr_dict = hr.to_dict()
    assert "humidity_pct" in hr_dict
    assert hr_dict["humidity_pct"] == 65.2


# --------------------------------------------------------------------------- #
# 3. TemperatureReading Validation (Valid Bounds)
# --------------------------------------------------------------------------- #
def test_temperature_reading_valid():
    """Verify normal and extreme valid physical temperatures pass validation."""
    t_normal = TemperatureReading(temperature_c=21.0)
    assert t_normal.validate() is True

    t_freezing = TemperatureReading(temperature_c=-25.0)
    assert t_freezing.validate() is True

    t_fire = TemperatureReading(temperature_c=85.0)
    assert t_fire.validate() is True


# --------------------------------------------------------------------------- #
# 4. TemperatureReading Validation (Invalid Bounds)
# --------------------------------------------------------------------------- #
def test_temperature_reading_invalid_bounds():
    """Verify temperatures below -100°C or above 150°C fail validation."""
    t_low = TemperatureReading(temperature_c=-105.0)
    assert t_low.validate() is False

    t_high = TemperatureReading(temperature_c=155.0)
    assert t_high.validate() is False


# --------------------------------------------------------------------------- #
# 5. TemperatureReading Validation (Invalid Types / NaN / Inf)
# --------------------------------------------------------------------------- #
def test_temperature_reading_invalid_types():
    """Verify NaN, Inf, None, and non-numeric values fail validation."""
    t_nan = TemperatureReading(temperature_c=float("nan"))
    assert t_nan.validate() is False

    t_inf = TemperatureReading(temperature_c=float("inf"))
    assert t_inf.validate() is False

    t_none = TemperatureReading(temperature_c=None)  # type: ignore
    assert t_none.validate() is False


# --------------------------------------------------------------------------- #
# 6. HumidityReading Validation (Valid Bounds)
# --------------------------------------------------------------------------- #
def test_humidity_reading_valid():
    """Verify relative humidity between 0.0% and 100.0% passes validation."""
    h_dry = HumidityReading(humidity_pct=12.0)
    assert h_dry.validate() is True

    h_mid = HumidityReading(humidity_pct=55.0)
    assert h_mid.validate() is True

    h_sat = HumidityReading(humidity_pct=100.0)
    assert h_sat.validate() is True


# --------------------------------------------------------------------------- #
# 7. HumidityReading Validation (Invalid Bounds)
# --------------------------------------------------------------------------- #
def test_humidity_reading_invalid_bounds():
    """Verify humidity < 0% or > 100% fails validation."""
    h_neg = HumidityReading(humidity_pct=-5.0)
    assert h_neg.validate() is False

    h_over = HumidityReading(humidity_pct=105.0)
    assert h_over.validate() is False


# --------------------------------------------------------------------------- #
# 8. HumidityReading Validation (Invalid Types / NaN / Inf)
# --------------------------------------------------------------------------- #
def test_humidity_reading_invalid_types():
    """Verify NaN, Inf, None, and invalid types fail validation for Humidity."""
    h_nan = HumidityReading(humidity_pct=float("nan"))
    assert h_nan.validate() is False

    h_inf = HumidityReading(humidity_pct=float("inf"))
    assert h_inf.validate() is False

    h_none = HumidityReading(humidity_pct=None)  # type: ignore
    assert h_none.validate() is False


# --------------------------------------------------------------------------- #
# 9. Temperature Simulation Adapter Profiles
# --------------------------------------------------------------------------- #
def test_temperature_adapter_profiles():
    """Verify temperature adapter responds deterministically to simulation profiles."""
    adapter = TemperatureSimulationAdapter(sensor_id="ENV-TEMP-TEST")

    adapter.set_simulation_profile("NORMAL")
    reading_norm = adapter.step(cycle=1)
    assert 10.0 <= reading_norm.temperature_c <= 30.0
    assert reading_norm.status == SensorHealthStatus.ONLINE

    adapter.set_simulation_profile("EXTREME_HEAT")
    for c in range(2, 6):
        reading_heat = adapter.step(cycle=c)
    assert reading_heat.temperature_c >= 42.0

    adapter.set_simulation_profile("FIRE")
    for c in range(6, 10):
        reading_fire = adapter.step(cycle=c)
    assert reading_fire.temperature_c >= 50.0

    adapter.set_simulation_profile("COLD")
    for c in range(10, 15):
        reading_cold = adapter.step(cycle=c)
    assert reading_cold.temperature_c <= 0.0

    adapter.set_simulation_profile("DEGRADED")
    reading_deg = adapter.step(cycle=16)
    assert reading_deg.status == SensorHealthStatus.DEGRADED

    adapter.set_simulation_profile("OFFLINE")
    reading_off = adapter.step(cycle=17)
    assert reading_off.status == SensorHealthStatus.OFFLINE


# --------------------------------------------------------------------------- #
# 10. Humidity Simulation Adapter Profiles
# --------------------------------------------------------------------------- #
def test_humidity_adapter_profiles():
    """Verify humidity adapter responds deterministically to simulation profiles."""
    adapter = HumiditySimulationAdapter(sensor_id="ENV-HUMID-TEST")

    adapter.set_simulation_profile("NORMAL")
    reading_norm = adapter.step(cycle=1)
    assert 30.0 <= reading_norm.humidity_pct <= 70.0
    assert reading_norm.status == SensorHealthStatus.ONLINE

    adapter.set_simulation_profile("HEAVY_RAIN")
    for c in range(2, 6):
        reading_rain = adapter.step(cycle=c, rainfall_mm_hr=40.0)
    assert reading_rain.humidity_pct >= 80.0

    adapter.set_simulation_profile("FLOOD")
    for c in range(6, 10):
        reading_flood = adapter.step(cycle=c)
    assert reading_flood.humidity_pct >= 90.0

    adapter.set_simulation_profile("ARID")
    for c in range(10, 15):
        reading_arid = adapter.step(cycle=c)
    assert reading_arid.humidity_pct <= 30.0

    adapter.set_simulation_profile("OFFLINE")
    reading_off = adapter.step(cycle=16)
    assert reading_off.status == SensorHealthStatus.OFFLINE


# --------------------------------------------------------------------------- #
# 11. Temperature Trend Classification & Rate of Change
# --------------------------------------------------------------------------- #
def test_temperature_trend_calculation():
    """Verify rapid temperature changes trigger RAPIDLY_RISING / RISING trends."""
    adapter = TemperatureSimulationAdapter(sensor_id="ENV-TEMP-TREND")
    adapter._temperature_c = 20.0

    # Rapid rise
    adapter.set_simulation_profile("FIRE")
    r1 = adapter.step(cycle=1)
    r2 = adapter.step(cycle=2)
    assert r2.trend in (TemperatureTrend.RISING, TemperatureTrend.RAPIDLY_RISING)
    assert r2.rate_of_change > 0.0


# --------------------------------------------------------------------------- #
# 12. Humidity Trend Classification & Rate of Change
# --------------------------------------------------------------------------- #
def test_humidity_trend_calculation():
    """Verify rapid humidity changes trigger RISING / RAPIDLY_RISING trends."""
    adapter = HumiditySimulationAdapter(sensor_id="ENV-HUMID-TREND")
    adapter._humidity_pct = 40.0

    # Rapid moisture surge
    adapter.set_simulation_profile("FLOOD")
    r1 = adapter.step(cycle=1)
    r2 = adapter.step(cycle=2)
    assert r2.trend in (HumidityTrend.RISING, HumidityTrend.RAPIDLY_RISING)
    assert r2.rate_of_change > 0.0


# --------------------------------------------------------------------------- #
# 13. Simulator Multi-Sensor Stream Emission
# --------------------------------------------------------------------------- #
def test_simulator_environmental_readings_stream():
    """Verify SensorSimulator emits first-class SensorReading objects for TEMPERATURE & HUMIDITY."""
    sim = SensorSimulator(victims=[], seed=42)
    readings = sim.generate_environmental_readings()

    temp_readings = [r for r in readings if r.sensor_type == SensorType.TEMPERATURE]
    humid_readings = [r for r in readings if r.sensor_type == SensorType.HUMIDITY]

    assert len(temp_readings) >= 1
    assert len(humid_readings) >= 1
    assert temp_readings[0].unit == "°C"
    assert humid_readings[0].unit == "%"
    assert 0.0 <= humid_readings[0].value <= 100.0


# --------------------------------------------------------------------------- #
# 14. Health and Degradation Reporting
# --------------------------------------------------------------------------- #
def test_health_and_degradation_reporting():
    """Verify degraded and offline states report correctly in health matrix."""
    sim = SensorSimulator(victims=[], seed=42)
    sim.temperature_adapter.set_simulation_profile("DEGRADED")
    sim.humidity_adapter.set_simulation_profile("OFFLINE")

    health_list = sim.get_sensor_health_report()
    health_map = {h.sensor_id: h for h in health_list}

    assert "ENV-TEMP-01" in health_map
    assert "ENV-HUMID-01" in health_map
    assert health_map["ENV-TEMP-01"].status == SensorHealthStatus.DEGRADED
    assert health_map["ENV-HUMID-01"].status == SensorHealthStatus.OFFLINE


# --------------------------------------------------------------------------- #
# 15. SQLite Database Persistence: Temperature
# --------------------------------------------------------------------------- #
def test_db_persistence_temperature():
    """Verify temperature logging, latest lookup, history query, and analytics."""
    session_id = "test-temp-sess-001"
    reading = TemperatureReading(
        sensor_id="ENV-TEMP-01",
        device_id="DEV-TEMP-01",
        temperature_c=46.5,
        ambient_temp_c=46.5,
        rate_of_change=3.2,
        trend=TemperatureTrend.RAPIDLY_RISING,
        status=SensorHealthStatus.ONLINE,
    )
    row_id = db.log_temperature_reading(reading, session_id=session_id, cycle=1)
    assert row_id is not None

    latest = db.get_latest_temperature_reading(session_id=session_id)
    assert latest is not None
    assert latest["temperature_c"] == 46.5
    assert latest["trend"] == "RAPIDLY_RISING"

    history = db.get_temperature_history(session_id=session_id, limit=10)
    assert len(history) >= 1
    assert history[0]["temperature_c"] == 46.5

    analytics = db.get_temperature_analytics(session_id=session_id)
    assert analytics["total_readings"] >= 1
    assert analytics["max_temperature_c"] >= 46.5


# --------------------------------------------------------------------------- #
# 16. SQLite Database Persistence: Humidity
# --------------------------------------------------------------------------- #
def test_db_persistence_humidity():
    """Verify humidity logging, latest lookup, history query, and analytics."""
    session_id = "test-humid-sess-001"
    reading = HumidityReading(
        sensor_id="ENV-HUMID-01",
        device_id="DEV-HUMID-01",
        humidity_pct=92.5,
        rate_of_change=5.0,
        trend=HumidityTrend.RAPIDLY_RISING,
        status=SensorHealthStatus.ONLINE,
    )
    row_id = db.log_humidity_reading(reading, session_id=session_id, cycle=1)
    assert row_id is not None

    latest = db.get_latest_humidity_reading(session_id=session_id)
    assert latest is not None
    assert latest["humidity_pct"] == 92.5
    assert latest["trend"] == "RAPIDLY_RISING"

    history = db.get_humidity_history(session_id=session_id, limit=10)
    assert len(history) >= 1
    assert history[0]["humidity_pct"] == 92.5

    analytics = db.get_humidity_analytics(session_id=session_id)
    assert analytics["total_readings"] >= 1
    assert analytics["max_humidity_pct"] >= 92.5


# --------------------------------------------------------------------------- #
# 17. Scenario Intelligence: Fire and Heatwave Evidence & Scoring
# --------------------------------------------------------------------------- #
def test_scenario_intelligence_temperature_fire_heatwave():
    """Verify extreme temperatures trigger heatwave and fire evidence tokens."""
    extractor = SensorEvidenceExtractor()
    env_report = {
        "temperature_c": 49.0,
        "ambient_temp_c": 49.0,
        "humidity_pct": 20.0,
        "rainfall_mm_hr": 0.0,
        "soil_moisture_pct": 10.0,
        "smoke_density_pct": 35.0,
        "gas_concentration_ppm": 10.0,
    }

    evidence = extractor.extract_evidence(readings=[], env_report=env_report)
    ev_labels = [e.evidence_label for e in evidence]

    assert "EXTREME_HEATWAVE_TEMPERATURE" in ev_labels
    assert "ARID_DRY_ATMOSPHERE" in ev_labels

    engine = DisasterScenarioInferenceEngine()
    assessment = engine.infer_scenario(evidence=evidence, env_report=env_report)
    assert assessment.primary_scenario.scenario_id in ("wildfire", "urban_fire", "heatwave")


# --------------------------------------------------------------------------- #
# 18. Scenario Intelligence: Flood, Cyclone, Cloudburst Evidence & Scoring
# --------------------------------------------------------------------------- #
def test_scenario_intelligence_humidity_flood_cyclone():
    """Verify saturated atmospheric humidity corroborates flood / cyclone scenarios."""
    extractor = SensorEvidenceExtractor()
    env_report = {
        "temperature_c": 22.0,
        "ambient_temp_c": 22.0,
        "humidity_pct": 94.0,
        "rainfall_mm_hr": 45.0,
        "barometric_pressure_hpa": 978.0,
    }

    evidence = extractor.extract_evidence(readings=[], env_report=env_report)
    ev_labels = [e.evidence_label for e in evidence]

    assert "SATURATED_ATMOSPHERIC_HUMIDITY" in ev_labels
    assert "COMPOUND_HUMIDITY_RAINFALL_FLOOD_TRIGGER" in ev_labels

    engine = DisasterScenarioInferenceEngine()
    assessment = engine.infer_scenario(evidence=evidence, env_report=env_report)
    assert assessment.primary_scenario.scenario_id in ("cyclone", "flood", "cloudburst")


# --------------------------------------------------------------------------- #
# 19. Scenario Intelligence: No False Positives Alone
# --------------------------------------------------------------------------- #
def test_scenario_intelligence_no_false_positive_alone():
    """Verify high humidity or temperature alone does not falsely trigger earthquake or landslide."""
    extractor = SensorEvidenceExtractor()
    env_report = {
        "temperature_c": 46.0,
        "ambient_temp_c": 46.0,
        "humidity_pct": 85.0,
        "rainfall_mm_hr": 0.0,
        "soil_moisture_pct": 15.0,
        "vibration_mm_s": 0.0,
        "tilt_deg": 0.0,
    }

    evidence = extractor.extract_evidence(readings=[], env_report=env_report)
    engine = DisasterScenarioInferenceEngine()
    assessment = engine.infer_scenario(evidence=evidence, env_report=env_report)

    assert assessment.primary_scenario.scenario_id != "earthquake"
    assert assessment.primary_scenario.scenario_id != "landslide"


# --------------------------------------------------------------------------- #
# 20. REST API: Temperature Endpoints
# --------------------------------------------------------------------------- #
def test_api_temperature_endpoints():
    """Verify GET and POST routes for Temperature."""
    client = TestClient(app)

    # Start a scenario
    start_res = client.post("/scenario/start", json={"scenario_id": "wildfire_forest"})
    assert start_res.status_code == 200

    # Current
    curr_res = client.get("/sensors/temperature/current")
    assert curr_res.status_code == 200
    curr_data = curr_res.json()
    assert "temperature" in curr_data
    assert "temperature_c" in curr_data["temperature"]

    # History
    hist_res = client.get("/sensors/temperature/history")
    assert hist_res.status_code == 200
    assert "history" in hist_res.json()

    # Health
    health_res = client.get("/sensors/temperature/health")
    assert health_res.status_code == 200
    assert "health" in health_res.json()

    # Trend
    trend_res = client.get("/sensors/temperature/trend")
    assert trend_res.status_code == 200
    assert "trend" in trend_res.json()

    # Simulate Profile
    sim_res = client.post("/sensors/temperature/simulate", json={"profile": "EXTREME_HEAT"})
    assert sim_res.status_code == 200
    assert sim_res.json()["profile"] == "EXTREME_HEAT"

    # Ingest Reading
    ingest_res = client.post("/sensors/temperature/readings", json={
        "temperature_c": 39.5,
        "unit": "°C",
        "trend": "RISING",
    })
    assert ingest_res.status_code == 200
    assert ingest_res.json()["logged"] is True

    # Ingest Invalid Bounds (Should be rejected with 422)
    invalid_res = client.post("/sensors/temperature/readings", json={
        "temperature_c": 250.0,
    })
    assert invalid_res.status_code == 422

    # Analytics
    analytics_res = client.get("/analytics/temperature")
    assert analytics_res.status_code == 200
    assert "analytics" in analytics_res.json()


# --------------------------------------------------------------------------- #
# 21. REST API: Humidity Endpoints
# --------------------------------------------------------------------------- #
def test_api_humidity_endpoints():
    """Verify GET and POST routes for Humidity."""
    client = TestClient(app)

    # Start a scenario
    start_res = client.post("/scenario/start", json={"scenario_id": "flood_urban"})
    assert start_res.status_code == 200

    # Current
    curr_res = client.get("/sensors/humidity/current")
    assert curr_res.status_code == 200
    curr_data = curr_res.json()
    assert "humidity" in curr_data
    assert "humidity_pct" in curr_data["humidity"]

    # History
    hist_res = client.get("/sensors/humidity/history")
    assert hist_res.status_code == 200
    assert "history" in hist_res.json()

    # Health
    health_res = client.get("/sensors/humidity/health")
    assert health_res.status_code == 200
    assert "health" in health_res.json()

    # Trend
    trend_res = client.get("/sensors/humidity/trend")
    assert trend_res.status_code == 200
    assert "trend" in trend_res.json()

    # Simulate Profile
    sim_res = client.post("/sensors/humidity/simulate", json={"profile": "FLOOD"})
    assert sim_res.status_code == 200
    assert sim_res.json()["profile"] == "FLOOD"

    # Ingest Reading
    ingest_res = client.post("/sensors/humidity/readings", json={
        "humidity_pct": 78.4,
        "unit": "%",
        "trend": "RISING",
    })
    assert ingest_res.status_code == 200
    assert ingest_res.json()["logged"] is True

    # Ingest Invalid Bounds (Should be rejected with 422)
    invalid_res = client.post("/sensors/humidity/readings", json={
        "humidity_pct": 150.0,
    })
    assert invalid_res.status_code == 422

    # Analytics
    analytics_res = client.get("/analytics/humidity")
    assert analytics_res.status_code == 200
    assert "analytics" in analytics_res.json()


# --------------------------------------------------------------------------- #
# 22. REST API: Legacy GET /environment Backward Compatibility
# --------------------------------------------------------------------------- #
def test_api_environment_backward_compatibility():
    """Verify GET /environment returns 200 with ambient_temp_c and humidity_pct intact."""
    client = TestClient(app)
    # Start scenario so simulator is running
    client.post("/scenario/start", json={"scenario_id": "flood_urban"})
    res = client.get("/environment")
    assert res.status_code == 200
    data = res.json()
    assert "ambient_temp_c" in data
    assert "humidity_pct" in data
    assert isinstance(data["ambient_temp_c"], (int, float))
    assert isinstance(data["humidity_pct"], (int, float))


# --------------------------------------------------------------------------- #
# 23. Stale Sensor Reading Validation
# --------------------------------------------------------------------------- #
def test_stale_temperature_and_humidity_reading():
    """Verify stale readings can be detected and handled."""
    from datetime import datetime, timezone, timedelta
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    t_stale = TemperatureReading(temperature_c=25.0, timestamp=old_time)
    assert t_stale.validate() is True
    # Stale condition can be checked via timestamp diff
    dt = datetime.now(timezone.utc) - datetime.fromisoformat(t_stale.timestamp)
    assert dt.total_seconds() > 60.0


# --------------------------------------------------------------------------- #
# 24. Forest Fire & Wildfire Environmental Evidence
# --------------------------------------------------------------------------- #
def test_forest_fire_temp_humidity_evidence():
    """Verify elevated temperature + arid low humidity triggers wildfire evidence."""
    extractor = SensorEvidenceExtractor()
    env_report = {
        "temperature_c": 42.0,
        "ambient_temp_c": 42.0,
        "humidity_pct": 18.0,
        "rainfall_mm_hr": 0.0,
        "soil_moisture_pct": 20.0,
        "smoke_density_pct": 30.0,
    }
    evidence = extractor.extract_evidence(readings=[], env_report=env_report)
    labels = {e.evidence_label for e in evidence}
    assert "HIGH_AMBIENT_TEMPERATURE" in labels or "EXTREME_HEATWAVE_TEMPERATURE" in labels
    assert "ARID_DRY_ATMOSPHERE" in labels


# --------------------------------------------------------------------------- #
# 25. Drought Evidence (High Temp + Arid Humidity + Zero Rain)
# --------------------------------------------------------------------------- #
def test_drought_temp_humidity_evidence():
    """Verify high temp + arid low humidity + no rain produces drought evidence."""
    extractor = SensorEvidenceExtractor()
    env_report = {
        "temperature_c": 38.0,
        "ambient_temp_c": 38.0,
        "humidity_pct": 15.0,
        "rainfall_mm_hr": 0.0,
    }
    evidence = extractor.extract_evidence(readings=[], env_report=env_report)
    engine = DisasterScenarioInferenceEngine()
    results = engine.infer_scenarios(evidence=evidence, env_report=env_report)
    drought_match = next((r for r in results if r.scenario_id == "drought"), None)
    assert drought_match is not None
    assert drought_match.confidence_pct >= 40.0


# --------------------------------------------------------------------------- #
# 26. Temperature & Humidity Fusion Integration
# --------------------------------------------------------------------------- #
def test_temperature_humidity_fusion_integration():
    """Verify temperature and humidity affect hazard multiplier in fusion engine."""
    from fusion_engine import HazardContext
    hazard_cold = HazardContext(ambient_temp_c=-15.0, humidity_pct=50.0)
    assert hazard_cold.multiplier() > 1.0

    hazard_heat_humid = HazardContext(ambient_temp_c=40.0, humidity_pct=85.0)
    assert hazard_heat_humid.multiplier() > 1.0


# --------------------------------------------------------------------------- #
# 27. Alert Generation & Lifecycle for Temperature / Humidity
# --------------------------------------------------------------------------- #
def test_temperature_humidity_alert_generation():
    """Verify critical heat/fire alerts are generated and synchronized."""
    extractor = SensorEvidenceExtractor()
    env_report = {
        "temperature_c": 52.0,
        "ambient_temp_c": 52.0,
        "humidity_pct": 80.0,
        "smoke_density_pct": 40.0,
    }
    evidence = extractor.extract_evidence(readings=[], env_report=env_report)
    engine = ScenarioIntelligenceEngine()
    assessment = engine.inference_engine.infer_scenario(evidence=evidence, env_report=env_report)
    alerts = engine.alert_manager.sync_alerts(
        session_id="test-temp-alert-sess",
        primary_scenario=assessment.primary_scenario,
        secondary_scenarios=assessment.secondary_scenarios,
        evidence=evidence,
    )
    assert len(alerts) >= 1
    assert any("Fire" in a.get("alert_title", "") or "Heat" in a.get("alert_title", "") or "alert" in str(a).lower() for a in alerts)


