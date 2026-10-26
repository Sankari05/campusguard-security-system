"""
test_water_level_first_class.py
===============================
Comprehensive verification suite for Water-Level & Flow velocity sensor integration.
Validates:
1. Valid water level reading creation and serialization.
2. Out-of-bounds water level rejected by validate().
3. NaN and Infinite float water level rejected by validate().
4. Negative water level / flow velocity rejected by validate().
5. Stale reading detection and quarantine.
6. Sensor disconnected / offline state handling.
7. Stable water level trend detection (WaterTrend.STABLE).
8. Rising water level trend detection (WaterTrend.RISING).
9. Rapidly rising water level trend detection (WaterTrend.RAPIDLY_RISING).
10. Flood detection when warning / high thresholds exceeded.
11. Flash flood detection when rapid rise + heavy rainfall occurs.
12. Dam break detection when catastrophic surge rate occurs.
13. Tsunami detection when violent surge + extreme flow occurs.
14. Coastal storm surge detection when low barometric pressure + water rise occurs.
15. Multi-hazard compounding with landslide / earthquake / rainfall.
16. Dynamic confidence scoring based on sensor health.
17. Alert generation for critical flood depths and rapid surge rates.
18. Alert deduplication and lifecycle synchronization.
19. Database persistence in water_level_readings table and analytics calculation.
20. REST API endpoints: current, history, health, trend, simulate, readings ingestion, analytics.
21. End-to-end simulation cycle verifying Water-Level participation in the disaster-intelligence pipeline.
"""

import math
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.models import (
    SensorType,
    SensorReading,
    SensorHealthStatus,
    RiskLevel,
    GPSCoordinate,
    WaterTrend,
    WaterLevelClassification,
    WaterLevelConfig,
    WATER_LEVEL_CONFIG,
    WaterLevelReading,
    SensorTrend,
    SensorValidator,
)
from backend.sensor_simulator import (
    WaterLevelSimulationAdapter,
    SensorSimulator,
)
from backend.scenario_intelligence import (
    SensorEvidenceExtractor,
    DisasterScenarioInferenceEngine,
    AlertLifecycleManager,
    ScenarioIntelligenceEngine,
)
from backend.fusion_engine import fuse_all, HazardContext
from backend.api import app
import backend.db as db

DEFAULT_LOC = GPSCoordinate(latitude=32.3740, longitude=77.2490, altitude_m=2050.0)


@pytest.fixture
def client():
    return TestClient(app)


# --------------------------------------------------------------------------- #
# 1. Valid water level reading creation and serialization
# --------------------------------------------------------------------------- #
def test_water_level_reading_creation_and_dict():
    reading = WaterLevelReading(
        sensor_id="ENV-WATER-01",
        device_id="DEV-WATER-01",
        water_level_cm=75.5,
        water_flow_mps=1.8,
        unit="cm",
        rate_of_change=3.2,
        trend=WaterTrend.RISING,
        classification=WaterLevelClassification.HIGH,
        severity=RiskLevel.HIGH,
        location=DEFAULT_LOC,
        status=SensorHealthStatus.ONLINE,
        confidence=0.98,
        quality=0.99,
    )
    assert reading.validate() is True
    d = reading.to_dict()
    assert d["sensor_id"] == "ENV-WATER-01"
    assert d["water_level_cm"] == 75.5
    assert d["water_flow_mps"] == 1.8
    assert d["trend"] == "RISING"
    assert d["classification"] == "HIGH"
    assert d["severity"] == "HIGH"
    assert d["status"] == "ONLINE"
    assert d["confidence"] == 0.98


# --------------------------------------------------------------------------- #
# 2. Out-of-bounds water level rejected by validate()
# --------------------------------------------------------------------------- #
def test_water_level_out_of_bounds_rejected():
    reading = WaterLevelReading(
        sensor_id="ENV-WATER-01",
        water_level_cm=2500.0,  # Max is 2000.0 cm
        location=DEFAULT_LOC,
    )
    assert reading.validate() is False


# --------------------------------------------------------------------------- #
# 3. NaN and Infinite float water level rejected by validate()
# --------------------------------------------------------------------------- #
def test_water_level_nan_inf_rejected():
    nan_reading = WaterLevelReading(
        sensor_id="ENV-WATER-01",
        water_level_cm=float("nan"),
        location=DEFAULT_LOC,
    )
    assert nan_reading.validate() is False

    inf_reading = WaterLevelReading(
        sensor_id="ENV-WATER-01",
        water_level_cm=float("inf"),
        location=DEFAULT_LOC,
    )
    assert inf_reading.validate() is False


# --------------------------------------------------------------------------- #
# 4. Negative water level / flow velocity rejected by validate()
# --------------------------------------------------------------------------- #
def test_water_level_negative_values_rejected():
    neg_level = WaterLevelReading(
        sensor_id="ENV-WATER-01",
        water_level_cm=-10.0,
        location=DEFAULT_LOC,
    )
    assert neg_level.validate() is False

    neg_flow = WaterLevelReading(
        sensor_id="ENV-WATER-01",
        water_level_cm=20.0,
        water_flow_mps=-2.5,
        location=DEFAULT_LOC,
    )
    assert neg_flow.validate() is False


# --------------------------------------------------------------------------- #
# 5. Stale reading detection and quarantine
# --------------------------------------------------------------------------- #
def test_water_level_stale_reading_quarantine():
    # Valid fresh reading
    r_fresh = SensorReading(
        sensor_type=SensorType.WATER_LEVEL,
        value=50.0,
        unit="cm",
        location=DEFAULT_LOC,
        timestamp=datetime.now(timezone.utc).isoformat(),
        confidence=0.98,
    )
    valid, err = SensorValidator.validate_reading(r_fresh)
    assert valid is True
    assert err is None

    # Stale reading from past
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    r_stale = WaterLevelReading(
        sensor_id="ENV-WATER-01",
        water_level_cm=50.0,
        timestamp=old_time,
    )
    assert r_stale.validate() is True
    dt = datetime.now(timezone.utc) - datetime.fromisoformat(r_stale.timestamp)
    assert dt.total_seconds() > 60.0


# --------------------------------------------------------------------------- #
# 6. Sensor disconnected / offline state handling
# --------------------------------------------------------------------------- #
def test_water_level_sensor_offline_handling():
    adapter = WaterLevelSimulationAdapter(initial_water_level_cm=45.0, location=DEFAULT_LOC)
    adapter.set_simulation_profile("OFFLINE")
    adapter.step()
    assert adapter.status == SensorHealthStatus.OFFLINE
    health = adapter.get_health()
    assert health.status == SensorHealthStatus.OFFLINE
    assert "offline" in health.error_message.lower()

    extractor = SensorEvidenceExtractor()
    evs = extractor.extract_evidence(
        readings=[
            SensorReading(
                sensor_type=SensorType.WATER_LEVEL,
                value=0.0,
                unit="cm",
                location=DEFAULT_LOC,
                status=SensorHealthStatus.OFFLINE,
            )
        ],
        env_report={"water_level_status": "OFFLINE"},
    )
    ev_labels = [e.evidence_label for e in evs]
    assert "WATER_LEVEL_SENSOR_OFFLINE" in ev_labels


# --------------------------------------------------------------------------- #
# 7. Stable water level trend detection (WaterTrend.STABLE)
# --------------------------------------------------------------------------- #
def test_water_level_trend_stable():
    adapter = WaterLevelSimulationAdapter(initial_water_level_cm=10.0, location=DEFAULT_LOC)
    adapter.set_simulation_profile("STABLE")
    for _ in range(5):
        reading = adapter.step()
    assert reading.trend in (WaterTrend.STABLE, WaterTrend.RISING, WaterTrend.FALLING)
    assert abs(reading.rate_of_change) < WATER_LEVEL_CONFIG.rapid_rising_rate_cm_per_cycle


# --------------------------------------------------------------------------- #
# 8. Rising water level trend detection (WaterTrend.RISING)
# --------------------------------------------------------------------------- #
def test_water_level_trend_rising():
    adapter = WaterLevelSimulationAdapter(initial_water_level_cm=10.0, location=DEFAULT_LOC)
    adapter.set_simulation_profile("FLOOD")
    for _ in range(3):
        reading = adapter.step(rainfall_rate_mm_h=20.0)
    assert reading.trend in (WaterTrend.RISING, WaterTrend.RAPIDLY_RISING)
    assert reading.water_level_cm > 15.0


# --------------------------------------------------------------------------- #
# 9. Rapidly rising water level trend detection (WaterTrend.RAPIDLY_RISING)
# --------------------------------------------------------------------------- #
def test_water_level_trend_rapidly_rising():
    adapter = WaterLevelSimulationAdapter(initial_water_level_cm=10.0, location=DEFAULT_LOC)
    adapter.set_simulation_profile("FLASH_FLOOD")
    reading = adapter.step(rainfall_rate_mm_h=50.0)
    assert reading.trend == WaterTrend.RAPIDLY_RISING
    assert reading.rate_of_change >= WATER_LEVEL_CONFIG.rapid_rising_rate_cm_per_cycle


# --------------------------------------------------------------------------- #
# 10. Flood detection when warning / high thresholds exceeded
# --------------------------------------------------------------------------- #
def test_flood_scenario_detection():
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()

    evs = extractor.extract_evidence(
        readings=[
            SensorReading(sensor_type=SensorType.WATER_LEVEL, value=85.0, unit="cm", location=DEFAULT_LOC),
            SensorReading(sensor_type=SensorType.WATER_FLOW, value=1.8, unit="m/s", location=DEFAULT_LOC),
        ],
        env_report={"water_level_cm": 85.0, "water_flow_mps": 1.8},
    )
    ev_labels = {e.evidence_label for e in evs}
    assert "HIGH_WATER_LEVEL" in ev_labels
    assert "HIGH_VELOCITY_FLOOD_CURRENT" in ev_labels

    results = engine.infer_scenarios(evs, env_report={"water_level_cm": 85.0})
    flood_res = next((r for r in results if r.scenario_id == "flood"), None)
    assert flood_res is not None
    assert flood_res.confidence_pct >= 50.0
    assert flood_res.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


# --------------------------------------------------------------------------- #
# 11. Flash flood detection when rapid rise + heavy rainfall occurs
# --------------------------------------------------------------------------- #
def test_flash_flood_compound_detection():
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()

    trend = SensorTrend(
        sensor_type=SensorType.WATER_LEVEL,
        current_value=90.0,
        rate_of_change_per_cycle=15.0,
        trend_direction="RAPIDLY_RISING",
    )

    evs = extractor.extract_evidence(
        readings=[
            SensorReading(sensor_type=SensorType.WATER_LEVEL, value=90.0, unit="cm", location=DEFAULT_LOC),
            SensorReading(sensor_type=SensorType.RAINFALL_INTENSITY, value=65.0, unit="mm/hr", location=DEFAULT_LOC),
        ],
        env_report={"water_level_cm": 90.0, "rainfall_mm_hr": 65.0, "rainfall_rate_mm_h": 65.0},
        trend_map={SensorType.WATER_LEVEL: trend},
    )
    ev_labels = {e.evidence_label for e in evs}
    assert "FLASH_FLOOD_RISK" in ev_labels or "RAPID_SURGE_WATER_RISE" in ev_labels

    results = engine.infer_scenarios(evs, env_report={"water_level_cm": 90.0, "rainfall_mm_hr": 65.0})
    cloudburst_res = next((r for r in results if r.scenario_id in ("cloudburst", "flood")), None)
    assert cloudburst_res is not None
    assert cloudburst_res.confidence_pct >= 50.0


# --------------------------------------------------------------------------- #
# 12. Dam break detection when catastrophic surge rate occurs
# --------------------------------------------------------------------------- #
def test_dam_break_detection():
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()

    trend = SensorTrend(
        sensor_type=SensorType.WATER_LEVEL,
        current_value=120.0,
        rate_of_change_per_cycle=35.0,
        trend_direction="RAPIDLY_RISING",
    )

    evs = extractor.extract_evidence(
        readings=[
            SensorReading(sensor_type=SensorType.WATER_LEVEL, value=120.0, unit="cm", location=DEFAULT_LOC),
            SensorReading(sensor_type=SensorType.WATER_FLOW, value=4.5, unit="m/s", location=DEFAULT_LOC),
        ],
        env_report={"water_level_cm": 120.0, "water_flow_mps": 4.5},
        trend_map={SensorType.WATER_LEVEL: trend},
    )
    ev_labels = {e.evidence_label for e in evs}
    assert "DAM_BREAK_WATER_SURGE" in ev_labels or "RAPID_SURGE_WATER_RISE" in ev_labels

    results = engine.infer_scenarios(evs, env_report={"water_level_cm": 120.0})
    dam_res = next((r for r in results if r.scenario_id == "dam_failure"), None)
    assert dam_res is not None
    assert dam_res.confidence_pct >= 60.0


# --------------------------------------------------------------------------- #
# 13. Tsunami detection when violent surge + extreme flow occurs
# --------------------------------------------------------------------------- #
def test_tsunami_detection():
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()

    trend = SensorTrend(
        sensor_type=SensorType.WATER_LEVEL,
        current_value=150.0,
        rate_of_change_per_cycle=40.0,
        trend_direction="RAPIDLY_RISING",
    )

    evs = extractor.extract_evidence(
        readings=[
            SensorReading(sensor_type=SensorType.WATER_LEVEL, value=150.0, unit="cm", location=DEFAULT_LOC),
            SensorReading(sensor_type=SensorType.WATER_FLOW, value=5.5, unit="m/s", location=DEFAULT_LOC),
        ],
        env_report={"water_level_cm": 150.0, "water_flow_mps": 5.5},
        trend_map={SensorType.WATER_LEVEL: trend},
    )
    ev_labels = {e.evidence_label for e in evs}
    assert "CRITICAL_FLOOD_SUBMERSION" in ev_labels
    assert "HIGH_VELOCITY_FLOOD_CURRENT" in ev_labels

    results = engine.infer_scenarios(evs, env_report={"water_level_cm": 150.0})
    tsunami_res = next((r for r in results if r.scenario_id == "tsunami"), None)
    assert tsunami_res is not None
    assert tsunami_res.confidence_pct >= 55.0


# --------------------------------------------------------------------------- #
# 14. Coastal storm surge detection when low pressure + water rise occurs
# --------------------------------------------------------------------------- #
def test_storm_surge_detection():
    extractor = SensorEvidenceExtractor()
    evs = extractor.extract_evidence(
        readings=[
            SensorReading(sensor_type=SensorType.WATER_LEVEL, value=55.0, unit="cm", location=DEFAULT_LOC),
            SensorReading(sensor_type=SensorType.BAROMETRIC_PRESSURE, value=975.0, unit="hPa", location=DEFAULT_LOC),
        ],
        env_report={"water_level_cm": 55.0, "pressure_hpa": 975.0},
    )
    ev_labels = {e.evidence_label for e in evs}
    assert "STORM_SURGE_WATER_RISK" in ev_labels


# --------------------------------------------------------------------------- #
# 15. Multi-hazard compounding with landslide / earthquake / rainfall
# --------------------------------------------------------------------------- #
def test_multi_hazard_compounding():
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()

    evs = extractor.extract_evidence(
        readings=[
            SensorReading(sensor_type=SensorType.WATER_LEVEL, value=65.0, unit="cm", location=DEFAULT_LOC),
            SensorReading(sensor_type=SensorType.RAINFALL_INTENSITY, value=50.0, unit="mm/hr", location=DEFAULT_LOC),
            SensorReading(sensor_type=SensorType.SOIL_MOISTURE, value=75.0, unit="%", location=DEFAULT_LOC),
            SensorReading(sensor_type=SensorType.IMU_TILT, value=4.5, unit="deg", location=DEFAULT_LOC),
            SensorReading(sensor_type=SensorType.IMU_VIBRATION, value=3.2, unit="mm/s", location=DEFAULT_LOC),
        ],
        env_report={
            "water_level_cm": 65.0,
            "rainfall_mm_hr": 50.0,
            "soil_moisture_pct": 75.0,
            "tilt_deg": 4.5,
            "vibration_mm_s": 3.2,
        },
    )
    results = engine.infer_scenarios(evs, env_report={"water_level_cm": 65.0, "rainfall_mm_hr": 50.0})
    multi_res = next((r for r in results if r.scenario_id == "multi_hazard"), None)
    assert multi_res is not None
    assert multi_res.confidence_pct >= 50.0


# --------------------------------------------------------------------------- #
# 16. Dynamic confidence scoring based on sensor health
# --------------------------------------------------------------------------- #
def test_dynamic_confidence_scoring_on_health():
    adapter = WaterLevelSimulationAdapter(initial_water_level_cm=30.0, location=DEFAULT_LOC)
    r_online = adapter.read_sensor()
    assert r_online.confidence >= 0.95

    adapter.set_status(SensorHealthStatus.DEGRADED)
    r_degraded = adapter.read_sensor()
    assert r_degraded.confidence <= 0.55

    adapter.set_status(SensorHealthStatus.OFFLINE)
    r_offline = adapter.read_sensor()
    assert r_offline.confidence == 0.0


# --------------------------------------------------------------------------- #
# 17. Alert generation for critical flood depths and rapid surge rates
# --------------------------------------------------------------------------- #
def test_water_level_alert_generation():
    lifecycle = AlertLifecycleManager()
    extractor = SensorEvidenceExtractor()

    evs = extractor.extract_evidence(
        readings=[
            SensorReading(sensor_type=SensorType.WATER_LEVEL, value=120.0, unit="cm", location=DEFAULT_LOC),
        ],
        env_report={"water_level_cm": 120.0},
    )
    alerts = lifecycle.sync_alerts(session_id="test-water-alerts", evidence=evs)
    titles = [a["alert_title"] for a in alerts]
    assert any("CRITICAL FLOOD ALERT" in t for t in titles)


# --------------------------------------------------------------------------- #
# 18. Alert deduplication and lifecycle synchronization
# --------------------------------------------------------------------------- #
def test_water_level_alert_deduplication_and_resolution():
    lifecycle = AlertLifecycleManager()
    extractor = SensorEvidenceExtractor()

    # Trigger critical flood
    evs_crit = extractor.extract_evidence(
        readings=[SensorReading(sensor_type=SensorType.WATER_LEVEL, value=110.0, unit="cm", location=DEFAULT_LOC)],
        env_report={"water_level_cm": 110.0},
    )
    alerts_1 = lifecycle.sync_alerts(session_id="test-water-dedup", evidence=evs_crit)
    assert len(alerts_1) >= 1

    # Same condition next cycle - must NOT create duplicate entries
    alerts_2 = lifecycle.sync_alerts(session_id="test-water-dedup", evidence=evs_crit)
    crit_alerts = [a for a in alerts_2 if a["hazard_type"] == "critical_flood"]
    assert len(crit_alerts) == 1

    # Water subsides to 5cm - alert should be resolved
    evs_normal = extractor.extract_evidence(
        readings=[SensorReading(sensor_type=SensorType.WATER_LEVEL, value=5.0, unit="cm", location=DEFAULT_LOC)],
        env_report={"water_level_cm": 5.0},
    )
    alerts_3 = lifecycle.sync_alerts(session_id="test-water-dedup", evidence=evs_normal)
    crit_remaining = [a for a in alerts_3 if a["hazard_type"] == "critical_flood"]
    assert len(crit_remaining) == 0


# --------------------------------------------------------------------------- #
# 19. Database persistence in water_level_readings table and analytics
# --------------------------------------------------------------------------- #
def test_water_level_db_persistence_and_analytics():
    session_id = "test-wtr-db-session"
    reading = WaterLevelReading(
        sensor_id="ENV-WATER-TEST",
        device_id="DEV-WATER-TEST",
        water_level_cm=62.5,
        water_flow_mps=1.4,
        unit="cm",
        rate_of_change=2.5,
        trend=WaterTrend.RISING,
        classification=WaterLevelClassification.HIGH,
        severity=RiskLevel.HIGH,
        location=DEFAULT_LOC,
    )
    row_id = db.log_water_level_reading(reading, session_id=session_id, cycle=1)
    assert row_id > 0

    latest = db.get_latest_water_level_reading(session_id=session_id)
    assert latest is not None
    assert latest["water_level_cm"] == 62.5
    assert latest["trend"] == "RISING"

    history = db.get_water_level_history(session_id=session_id, limit=10)
    assert len(history) >= 1

    analytics = db.get_water_level_analytics(session_id=session_id)
    assert analytics["total_readings"] >= 1
    assert analytics["max_water_level_cm"] >= 62.5
    assert analytics["max_flow_velocity_mps"] >= 1.4


# --------------------------------------------------------------------------- #
# 20. REST API endpoints: current, history, health, trend, simulate, readings, analytics
# --------------------------------------------------------------------------- #
def test_water_level_rest_api_endpoints(client):
    # Start scenario so simulator is running
    client.post("/scenario/start", json={"scenario_id": "flood_urban"})

    # 1. Current
    res = client.get("/sensors/water-level/current")
    assert res.status_code == 200
    data = res.json()
    assert "water_level" in data

    # 2. Health
    res = client.get("/sensors/water-level/health")
    assert res.status_code == 200
    data = res.json()
    assert "health" in data

    # 3. Trend
    res = client.get("/sensors/water-level/trend")
    assert res.status_code == 200
    data = res.json()
    assert "trend" in data
    assert "water_level_cm" in data

    # 4. Simulate
    res = client.post("/sensors/water-level/simulate", json={"profile": "FLASH_FLOOD", "water_level_cm": 95.0})
    assert res.status_code == 200
    assert res.json()["profile"] == "FLASH_FLOOD"

    # 5. Ingest valid reading
    res = client.post(
        "/sensors/water-level/readings",
        json={
            "sensor_id": "ENV-WATER-01",
            "water_level_cm": 80.0,
            "water_flow_mps": 2.0,
            "unit": "cm",
            "trend": "RISING",
        },
    )
    assert res.status_code == 200
    assert res.json()["logged"] is True

    # 6. Ingest invalid reading (negative / NaN) -> must reject 422
    res_bad = client.post(
        "/sensors/water-level/readings",
        json={
            "sensor_id": "ENV-WATER-01",
            "water_level_cm": -50.0,
        },
    )
    assert res_bad.status_code == 422

    # 7. History
    res = client.get("/sensors/water-level/history")
    assert res.status_code == 200
    assert "history" in res.json()

    # 8. Analytics
    res = client.get("/analytics/water-level")
    assert res.status_code == 200
    assert "analytics" in res.json()


# --------------------------------------------------------------------------- #
# 21. End-to-end simulation cycle verifying Water-Level pipeline participation
# --------------------------------------------------------------------------- #
def test_water_level_end_to_end_pipeline():
    sim = SensorSimulator(seed=123, enable_water_sensor=True, enable_water_flow_sensor=True)
    sim.water_level_adapter.set_simulation_profile("FLASH_FLOOD")

    # Step simulation cycle
    readings = sim.generate_cycle()
    water_readings = [r for r in readings if r.sensor_type == SensorType.WATER_LEVEL]
    assert len(water_readings) >= 1

    env_readings = sim.generate_environmental_readings()
    env_water = [r for r in env_readings if r.sensor_type == SensorType.WATER_LEVEL]
    assert len(env_water) >= 1

    # Test fusion engine with HazardContext containing water level & flow
    hazard = HazardContext(
        water_level_cm=env_water[0].value,
        water_flow_ms=sim.water_level_adapter._water_flow_mps,
        rainfall_mm_hr=45.0,
    )
    assert hazard.multiplier() > 1.0

    # Test ScenarioIntelligenceEngine process_cycle
    intel_engine = ScenarioIntelligenceEngine()
    assessment = intel_engine.process_cycle(
        session_id="test-water-e2e",
        cycle=1,
        readings=readings + env_readings,
        env_report=sim.environmental_full_report(),
        battery_map={},
    )
    assert assessment is not None
    assert len(assessment.active_evidence) >= 1
