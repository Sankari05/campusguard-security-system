"""
test_gas_smoke_hazard_module.py
--------------------------------
Comprehensive test suite for the Gas & Smoke Hazard Detection Module
and its end-to-end integration into the disaster scenario intelligence
and rescue operations pipeline.
"""

import math
import uuid
import pytest

from models import (
    SensorType,
    SensorReading,
    SensorHealthStatus,
    GasType,
    GasConcentrationLevel,
    SmokeLevel,
    GasSmokeReading,
    GPSCoordinate,
    RiskLevel,
    ScenarioInferenceResult,
    DisasterAssessment,
)
import db
from sensor_simulator import SensorSimulator, GasSmokeSimulationAdapter
from scenario_loader import load_scenario, SiteEnvironment
from scenario_intelligence import (
    GasSmokeAnalyzer,
    SensorTrendTracker,
    SensorHealthMonitor,
    SensorEvidenceExtractor,
    DisasterScenarioInferenceEngine,
    AlertLifecycleManager,
    ScenarioIntelligenceEngine,
)


def test_1_normal_baseline():
    """Test 1: Normal ambient baseline (Gas=10, Smoke=5, Temp=30) -> No hazard."""
    analyzer = GasSmokeAnalyzer()
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)

    reading = GasSmokeReading(
        gas_type=GasType.GENERIC_SMOKE,
        gas_concentration=10.0,
        smoke_density_pct=5.0,
        gas_level=analyzer.classify_gas(10.0),
        smoke_level=analyzer.classify_smoke(5.0),
        location=loc,
    )
    assert reading.validate() is True
    assert reading.gas_level == GasConcentrationLevel.NORMAL
    assert reading.smoke_level == SmokeLevel.LOW

    analysis = analyzer.analyze(gas_ppm=10.0, smoke_pct=5.0)
    assert analysis["available"] is True
    assert analysis["gas_level"] == "NORMAL"
    assert analysis["smoke_level"] == "LOW"
    assert analysis["anomaly_state"] == "NORMAL"

    extractor = SensorEvidenceExtractor()
    evidence = extractor.extract_evidence(
        readings=[],
        env_report={"gas_concentration_ppm": 10.0, "smoke_density_pct": 5.0, "ambient_temp_c": 30.0},
    )
    labels = [e.evidence_label for e in evidence]
    assert "TOXIC_COMBUSTIBLE_GAS_ALERT" not in labels
    assert "DENSE_SMOKE_OBSCURATION" not in labels
    assert "CRITICAL_GAS_CONCENTRATION" not in labels


def test_2_smoke_progression_and_alert():
    """Test 2: Smoke rises: 10 -> 20 -> 40 -> 70 -> Smoke alert & dense smoke obscuration."""
    analyzer = GasSmokeAnalyzer()
    tracker = SensorTrendTracker()
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)

    smoke_values = [10.0, 20.0, 40.0, 70.0]
    trends = []
    analyses = []
    for s in smoke_values:
        r = SensorReading(
            sensor_type=SensorType.SMOKE_DENSITY,
            value=s,
            unit="%",
            location=loc,
        )
        trends.append(tracker.push_reading(r))
        analyses.append(analyzer.analyze(gas_ppm=12.0, smoke_pct=s))

    latest_trend = trends[-1]
    latest_analysis = analyses[-1]

    assert latest_trend.trend_direction == "RISING"
    assert latest_analysis["smoke_level"] == "HIGH" or latest_analysis["smoke_level"] == "CRITICAL"
    assert latest_analysis["anomaly_state"] in ("ABNORMAL", "CRITICAL")

    extractor = SensorEvidenceExtractor()
    evidence = extractor.extract_evidence(
        readings=[SensorReading(sensor_type=SensorType.SMOKE_DENSITY, value=70.0, unit="%", location=loc)],
        trends=trends,
        env_report={"smoke_density_pct": 70.0, "gas_concentration_ppm": 12.0},
    )
    labels = [e.evidence_label for e in evidence]
    assert "DENSE_SMOKE_OBSCURATION" in labels or "CRITICAL_SMOKE_OBSCURATION" in labels


def test_3_fire_multi_sensor_correlation():
    """Test 3: Fire: Temp (35->50), Smoke (10->85), Gas (10->70) -> Fire confidence increases."""
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)

    readings = [
        SensorReading(sensor_type=SensorType.THERMAL_IMAGING, value=52.0, unit="degC", location=loc),
        SensorReading(sensor_type=SensorType.SMOKE_DENSITY, value=85.0, unit="%", location=loc),
        SensorReading(sensor_type=SensorType.GAS_CONCENTRATION, value=70.0, unit="ppm", location=loc),
    ]
    env_report = {
        "ambient_temp_c": 52.0,
        "smoke_density_pct": 85.0,
        "gas_concentration_ppm": 70.0,
    }

    evidence = extractor.extract_evidence(readings, env_report=env_report)
    assessment = engine.infer_scenario(evidence, env_report=env_report)

    assert assessment.primary_scenario is not None
    assert assessment.primary_scenario.scenario_id in ("urban_fire", "wildfire", "industrial_accident")
    assert assessment.confidence_pct >= 75.0
    assert assessment.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)


def test_4_toxic_gas_leak_disambiguation_from_fire():
    """Test 4: Toxic Gas: Gas (10->90), Smoke (5->10), Temp (30->32) -> Chemical Leak inferred, NOT Fire."""
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)

    readings = [
        SensorReading(sensor_type=SensorType.THERMAL_IMAGING, value=31.0, unit="degC", location=loc),
        SensorReading(sensor_type=SensorType.GAS_CONCENTRATION, value=92.0, unit="ppm", location=loc),
        SensorReading(sensor_type=SensorType.SMOKE_DENSITY, value=8.0, unit="%", location=loc),
    ]
    env_report = {
        "ambient_temp_c": 31.0,
        "smoke_density_pct": 8.0,
        "gas_concentration_ppm": 92.0,
    }

    evidence = extractor.extract_evidence(readings, env_report=env_report)
    assessment = engine.infer_scenario(evidence, env_report=env_report)

    # Primary scenario MUST be chemical leak or toxic gas, NOT fire
    assert assessment.primary_scenario.scenario_id == "chemical_leak"
    assert assessment.confidence_pct >= 80.0
    assert assessment.overall_risk == RiskLevel.CRITICAL


def test_5_industrial_accident():
    """Test 5: Industrial Accident: Gas rapid surge + Smoke + Temp spike -> Industrial Accident high confidence."""
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)

    readings = [
        SensorReading(sensor_type=SensorType.THERMAL_IMAGING, value=42.0, unit="degC", location=loc),
        SensorReading(sensor_type=SensorType.GAS_CONCENTRATION, value=75.0, unit="ppm", location=loc),
        SensorReading(sensor_type=SensorType.SMOKE_DENSITY, value=45.0, unit="%", location=loc),
    ]
    env_report = {
        "ambient_temp_c": 42.0,
        "smoke_density_pct": 45.0,
        "gas_concentration_ppm": 75.0,
    }

    evidence = extractor.extract_evidence(readings, env_report=env_report)
    all_scenarios = engine.infer_scenarios(evidence, env_report=env_report, active_scenario_hint="industrial_accident")
    industrial = next((s for s in all_scenarios if s.scenario_id == "industrial_accident"), None)

    assert industrial is not None
    assert industrial.confidence_pct >= 75.0


def test_6_survivor_correlation_and_risk_escalation():
    """Test 6: Survivor: Gas/Smoke Critical + Radar human detected -> Risk escalates to CRITICAL."""
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)

    readings = [
        SensorReading(sensor_type=SensorType.GAS_CONCENTRATION, value=85.0, unit="ppm", location=loc, victim_id="V1"),
        SensorReading(sensor_type=SensorType.SMOKE_DENSITY, value=55.0, unit="%", location=loc, victim_id="V1"),
        SensorReading(sensor_type=SensorType.HEART_RATE_RADAR, value=82.0, unit="bpm", location=loc, victim_id="V1"),
        SensorReading(sensor_type=SensorType.PIR_MOTION, value=0.45, unit="index", location=loc, victim_id="V1"),
    ]
    env_report = {
        "gas_concentration_ppm": 85.0,
        "smoke_density_pct": 55.0,
    }

    evidence = extractor.extract_evidence(readings, env_report=env_report)
    labels = [e.evidence_label for e in evidence]
    assert "HAZARDOUS_AREA_SURVIVOR_DETECTED" in labels

    assessment = engine.infer_scenario(evidence, env_report=env_report)
    assert assessment.overall_risk == RiskLevel.CRITICAL


def test_7_sensor_failure_and_offline_handling():
    """Test 7: Gas Sensor OFFLINE -> Gas unavailable, confidence reduced, does NOT report safe."""
    analyzer = GasSmokeAnalyzer()
    analysis = analyzer.analyze(gas_ppm=0.0, smoke_pct=0.0, status=SensorHealthStatus.OFFLINE)

    assert analysis["available"] is False
    assert analysis["warning"] == "Gas detection unavailable"
    assert analysis["confidence_penalty"] > 0.0
    assert analysis["gas_level"] == "UNKNOWN"


def test_8_history_and_persistence():
    """Test 8: History: Generate multiple readings, store in SQLite, verify retrieval."""
    session_id = f"test-sess-{uuid.uuid4().hex[:6]}"
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)

    for i in range(15):
        reading = GasSmokeReading(
            sensor_id="GAS-SMOKE-SITE",
            gas_type=GasType.TOXIC_GAS,
            gas_concentration=10.0 + i * 4.0,
            smoke_density_pct=5.0 + i * 2.0,
            location=loc,
        )
        db.log_gas_smoke_reading(reading, session_id=session_id)

    history = db.get_gas_smoke_history(session_id=session_id, limit=50)
    assert len(history) == 15
    assert history[0]["gas_type"] == "TOXIC_GAS"
    assert history[-1]["gas_concentration"] == pytest.approx(66.0, 0.1)

    latest = db.get_latest_gas_smoke_reading(session_id=session_id)
    assert latest is not None
    assert latest["gas_concentration"] == pytest.approx(66.0, 0.1)


def test_9_alert_deduplication_and_escalation():
    """Test 9: Alert Deduplication: Keep gas critical for multiple cycles -> One alert updated continuously."""
    alert_mgr = AlertLifecycleManager()
    session_id = f"test-sess-{uuid.uuid4().hex[:6]}"

    # Cycle 1: High Severity
    assessment_1 = DisasterAssessment(
        primary_scenario=ScenarioInferenceResult(
            scenario_id="chemical_leak",
            scenario_name="Chemical / Toxic Gas Leak",
            confidence_pct=80.0,
            risk_level=RiskLevel.HIGH,
            recommended_action="Deploy SCBA teams",
        ),
        overall_risk=RiskLevel.HIGH,
        confidence_pct=80.0,
        cycle=1,
    )
    alerts_1 = alert_mgr.evaluate_and_sync(session_id, 1, assessment_1)
    assert len(alerts_1) == 1
    assert alerts_1[0]["severity"] == "HIGH"

    # Cycle 2: Escalate to Critical Severity
    assessment_2 = DisasterAssessment(
        primary_scenario=ScenarioInferenceResult(
            scenario_id="chemical_leak",
            scenario_name="Chemical / Toxic Gas Leak",
            confidence_pct=95.0,
            risk_level=RiskLevel.CRITICAL,
            recommended_action="Hot Zone Evacuation",
        ),
        overall_risk=RiskLevel.CRITICAL,
        confidence_pct=95.0,
        cycle=2,
    )
    alerts_2 = alert_mgr.evaluate_and_sync(session_id, 2, assessment_2)
    # Deduplicated: still 1 alert in ledger for this hazard, but escalated to CRITICAL
    assert len(alerts_2) == 1
    assert alerts_2[0]["severity"] == "CRITICAL"


def test_10_adapter_and_scenario_profiles():
    """Test 10: Verify GasSmokeSimulationAdapter handles scenario profiles."""
    adapter = GasSmokeSimulationAdapter(
        gas_type=GasType.TOXIC_GAS,
        scenario_profile="CHEMICAL_LEAK",
        initial_gas_ppm=10.0,
        initial_smoke_pct=5.0,
    )
    assert adapter.gas_type == GasType.TOXIC_GAS

    # Step 5 times in Chemical Leak mode
    for _ in range(5):
        reading = adapter.step()

    assert reading.gas_concentration > 50.0
    assert reading.smoke_density_pct <= 20.0   # chemical leak maintains low smoke
    assert reading.validate() is True

    health = adapter.get_health()
    assert health.status == SensorHealthStatus.ONLINE
    assert health.battery_pct > 0.0


def test_11_api_gas_smoke_endpoints(api_client):
    """Test 11: REST API /sensors/gas-smoke/current, /history, /health, and /readings."""
    start_res = api_client.post("/scenario/start", json={
        "scenario": "earthquake_building_collapse",
        "seed": 42,
    })
    assert start_res.status_code == 200

    # Query current gas/smoke
    cur_res = api_client.get("/sensors/gas-smoke/current")
    assert cur_res.status_code == 200
    cur_data = cur_res.json()
    assert "gas_smoke" in cur_data
    assert "gas_concentration" in cur_data["gas_smoke"]
    assert "smoke_density_pct" in cur_data["gas_smoke"]

    # Query gas/smoke health
    health_res = api_client.get("/sensors/gas-smoke/health")
    assert health_res.status_code == 200
    assert "health" in health_res.json()

    # Ingest external IoT reading
    ingest_res = api_client.post("/sensors/gas-smoke/readings", json={
        "gas_type": "TOXIC_GAS",
        "gas_concentration": 68.5,
        "smoke_density_pct": 22.0,
        "latitude": 32.374,
        "longitude": 77.249,
    })
    assert ingest_res.status_code == 200
    assert ingest_res.json()["logged"] is True

    # Query history
    hist_res = api_client.get("/sensors/gas-smoke/history")
    assert hist_res.status_code == 200
    assert len(hist_res.json()["history"]) > 0


def test_12_commander_hazmat_staff_matching(api_client):
    """Test 12: Commander Job creation for Chemical Leak correctly matches HazMat-trained staff."""
    # 1. Register HazMat specialist and Flood specialist
    p_hazmat = api_client.post("/admin/personnel/add", json={
        "full_name": "Dr. Sarah Chen (HazMat Lead)",
        "role": "HazMat Specialist",
        "scenarios": ["chemical_leak", "industrial_accident"],
    }).json()

    p_flood = api_client.post("/admin/personnel/add", json={
        "full_name": "Captain Mark Davis",
        "role": "Boat Specialist",
        "scenarios": ["flood", "tsunami"],
    }).json()

    # 2. Create job for Chemical Leak
    job_res = api_client.post("/commander/jobs/create", json={
        "job_name": "Toxic Gas Hot Zone Containment",
        "scenario_id": "chemical_leak",
        "priority": "CRITICAL",
        "latitude": 32.374,
        "longitude": 77.249,
        "description": "CRITICAL TOXIC GAS - LEVEL A HAZMAT PPE REQUIRED",
    })
    assert job_res.status_code == 200
    job_id = job_res.json()["job_id"]

    # 3. Check eligible staff
    staff_res = api_client.get(f"/commander/jobs/{job_id}/eligible-staff")
    assert staff_res.status_code == 200
    eligible = staff_res.json()["eligible"]
    ineligible = staff_res.json()["ineligible"]

    eligible_ids = [s["personnel_id"] for s in eligible if s.get("personnel_id")]
    ineligible_ids = [s["personnel_id"] for s in ineligible if s.get("personnel_id")]

    assert p_hazmat["person_id"] in eligible_ids
    assert p_flood["person_id"] in ineligible_ids

    # 4. Assign eligible HazMat staff
    assign_res = api_client.post("/commander/jobs/assign", json={
        "job_id": job_id,
        "member_id": p_hazmat["person_id"],
        "notes": "Lead HazMat entry specialist",
    })
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "ASSIGNED"


def test_13_end_to_end_gas_hazard_pipeline(api_client):
    """Test 13: Full end-to-end intelligence and rescue pipeline with chemical hazard."""
    # 1. Start scenario
    start_res = api_client.post("/scenario/start", json={
        "scenario": "earthquake_building_collapse",
        "seed": 55,
        "enable_degradation": True,
    })
    assert start_res.status_code == 200

    # 2. Ingest critical gas surge
    api_client.post("/sensors/gas-smoke/readings", json={
        "gas_type": "TOXIC_GAS",
        "gas_concentration": 88.0,
        "smoke_density_pct": 12.0,
        "latitude": 32.374,
        "longitude": 77.249,
    })

    # 3. Advance tick
    tick_res = api_client.post("/scenario/tick")
    assert tick_res.status_code == 200

    # 4. Check assessment
    assessment_res = api_client.get("/scenario/assessment")
    assert assessment_res.status_code == 200
    assessment = assessment_res.json()["assessment"]
    assert assessment["overall_risk"] in ("HIGH", "CRITICAL")

    # 5. Check active alerts
    alerts_res = api_client.get("/alerts/active")
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()["alerts"]
    assert len(alerts) > 0


def test_14_multi_hazard_cascade_test():
    """Test 14: Multi-Hazard cascade (Earthquake -> Building Collapse -> Fire -> Smoke/Gas -> Survivor)."""
    extractor = SensorEvidenceExtractor()
    engine = DisasterScenarioInferenceEngine()
    loc = GPSCoordinate(latitude=32.374, longitude=77.249)

    readings = [
        SensorReading(sensor_type=SensorType.IMU_VIBRATION, value=4.5, unit="g", location=loc),
        SensorReading(sensor_type=SensorType.IMU_TILT, value=5.2, unit="deg", location=loc),
        SensorReading(sensor_type=SensorType.THERMAL_IMAGING, value=55.0, unit="degC", location=loc),
        SensorReading(sensor_type=SensorType.SMOKE_DENSITY, value=65.0, unit="%", location=loc),
        SensorReading(sensor_type=SensorType.GAS_CONCENTRATION, value=60.0, unit="ppm", location=loc),
        SensorReading(sensor_type=SensorType.HEART_RATE_RADAR, value=78.0, unit="bpm", location=loc, victim_id="V1"),
    ]
    env_report = {
        "vibration_mm_s": 6.8,
        "tilt_deg": 5.2,
        "ambient_temp_c": 55.0,
        "smoke_density_pct": 65.0,
        "gas_concentration_ppm": 60.0,
    }

    evidence = extractor.extract_evidence(readings, env_report=env_report)
    assessment = engine.infer_scenario(evidence, env_report=env_report)

    assert assessment.primary_scenario is not None
    assert len(assessment.secondary_scenarios) > 0
    assert assessment.overall_risk == RiskLevel.CRITICAL
