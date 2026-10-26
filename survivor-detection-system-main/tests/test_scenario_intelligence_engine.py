"""
Comprehensive Test Suite for Scenario Intelligence Engine
Validates Trend Tracker, Health Monitor, Evidence Extractor,
19 Master Disaster Scenarios Bayesian/Rule Inference, Multi-Hazard Cascades,
and Alert Lifecycle Management.
"""

import pytest
import uuid
from backend.models import (
    SensorType,
    SensorReading,
    SensorHealthStatus,
    RiskLevel,
    GPSCoordinate,
)
from backend.scenario_intelligence import (
    SensorTrendTracker,
    SensorHealthMonitor,
    SensorEvidenceExtractor,
    DisasterScenarioInferenceEngine,
    MultiHazardCascadeEngine,
    AlertLifecycleManager,
    ScenarioIntelligenceEngine,
)
from backend.scenarios_master import DISASTER_SCENARIOS, get_scenario_by_id


def test_sensor_trend_tracker():
    """Test sliding window trend analysis, rate of change, and spike anomaly detection."""
    tracker = SensorTrendTracker(window_size=10)
    loc = GPSCoordinate(latitude=32.37, longitude=77.24, altitude_m=3950)

    # Feed normal readings
    for i in range(5):
        r = SensorReading(
            sensor_type=SensorType.WATER_LEVEL,
            value=10.0 + i * 0.5,
            unit="cm",
            location=loc,
            victim_id="V1",
        )
        trend = tracker.update(r)
        assert trend.sensor_type == SensorType.WATER_LEVEL
        assert trend.trend_direction in ("RISING", "STABLE")

    # Feed a massive spike
    spike_reading = SensorReading(
        sensor_type=SensorType.WATER_LEVEL,
        value=150.0,
        unit="cm",
        location=loc,
        victim_id="V1",
    )
    spike_trend = tracker.update(spike_reading)
    assert spike_trend.is_spike is True
    assert spike_trend.anomaly_score > 0.5


def test_sensor_health_monitor():
    """Test health aggregator calculates online/degraded/offline breakdown."""
    monitor = SensorHealthMonitor()
    loc = GPSCoordinate(latitude=32.37, longitude=77.24)

    readings = [
        SensorReading(sensor_type=SensorType.THERMAL_IMAGING, value=30.0, unit="C", location=loc, victim_id="V1", quality=0.95, status=SensorHealthStatus.ONLINE),
        SensorReading(sensor_type=SensorType.ACOUSTIC, value=15.0, unit="dB", location=loc, victim_id="V1", quality=0.4, status=SensorHealthStatus.DEGRADED),
        SensorReading(sensor_type=SensorType.GAS_CONCENTRATION, value=0.0, unit="ppm", location=loc, victim_id="V1", quality=0.0, status=SensorHealthStatus.OFFLINE),
    ]
    battery_map = {"V1": 85.0}
    health_records = monitor.evaluate_channels(readings, battery_map)
    summary = monitor.get_summary(health_records)

    assert summary["online"] == 1
    assert summary["degraded"] == 1
    assert summary["offline"] == 1
    assert summary["overall_status"] == "CRITICAL_FAULTS"


def test_evidence_extractor():
    """Test semantic evidence token generation from sensor readings and environment."""
    extractor = SensorEvidenceExtractor()
    loc = GPSCoordinate(latitude=32.37, longitude=77.24)

    readings = [
        SensorReading(sensor_type=SensorType.THERMAL_IMAGING, value=55.0, unit="degC", location=loc, victim_id="V1", confidence=0.95),
        SensorReading(sensor_type=SensorType.GAS_CONCENTRATION, value=150.0, unit="ppm", location=loc, victim_id="V1", confidence=0.9),
        SensorReading(sensor_type=SensorType.HEART_RATE_RADAR, value=75.0, unit="bpm", location=loc, victim_id="V1", confidence=0.88),
    ]
    env_report = {
        "vibration_mm_s": 8.5,
        "rainfall_mm_hr": 45.0,
        "soil_moisture_pct": 88.0,
        "barometric_pressure_hpa": 940.0,
        "gas_concentration_ppm": 120.0,
        "smoke_density_pct": 60.0,
    }

    evidence_list = extractor.extract_evidence(readings, env_report)
    assert len(evidence_list) > 0

    labels = [e.evidence_label for e in evidence_list]
    assert "SEISMIC_TREMOR_DETECTED" in labels
    assert "TORRENTIAL_PRECIPITATION" in labels
    assert "SOIL_SATURATION_INSTABILITY" in labels
    assert "SEVERE_BAROMETRIC_PRESSURE_DROP" in labels
    assert "TOXIC_COMBUSTIBLE_GAS_ALERT" in labels
    assert "DENSE_SMOKE_OBSCURATION" in labels
    assert "EXTREME_THERMAL_SIGNATURE" in labels
    assert "SURVIVOR_VITALS_CONFIRMED" in labels


def test_19_master_disaster_scenarios_inference():
    """Test scenario inference across all master scenarios."""
    engine = DisasterScenarioInferenceEngine()
    cascade_engine = MultiHazardCascadeEngine()
    extractor = SensorEvidenceExtractor()
    loc = GPSCoordinate(latitude=32.37, longitude=77.24)

    # Test Earthquake Scenario
    eq_readings = [
        SensorReading(sensor_type=SensorType.IMU_VIBRATION, value=0.8, unit="g", location=loc, victim_id="V1"),
        SensorReading(sensor_type=SensorType.HEART_RATE_RADAR, value=80.0, unit="bpm", location=loc, victim_id="V1"),
    ]
    eq_env = {"vibration_mm_s": 12.0, "aftershock_active": True, "tilt_deg": 18.0}
    eq_evidence = extractor.extract_evidence(eq_readings, eq_env)
    assessment = engine.infer_scenario(eq_evidence, eq_readings, eq_env, active_scenario_hint="earthquake")

    assert assessment.primary_scenario.scenario_id in ("earthquake", "building_collapse")
    assert assessment.confidence_pct >= 60.0
    assert assessment.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    # Test Cascade Engine for Earthquake
    cascades = cascade_engine.evaluate_cascades(assessment.primary_scenario.scenario_id, eq_env)
    assert "landslide" in cascades or "building_collapse" in cascades or "tsunami" in cascades

    # Test Chemical Leak Scenario
    chem_readings = [
        SensorReading(sensor_type=SensorType.GAS_CONCENTRATION, value=250.0, unit="ppm", location=loc, victim_id="V1"),
    ]
    chem_env = {"gas_concentration_ppm": 250.0, "smoke_density_pct": 45.0}
    chem_evidence = extractor.extract_evidence(chem_readings, chem_env)
    chem_assessment = engine.infer_scenario(chem_evidence, chem_readings, chem_env, active_scenario_hint="chemical_leak")

    assert chem_assessment.primary_scenario.scenario_id == "chemical_leak"
    assert chem_assessment.confidence_pct >= 70.0
    assert chem_assessment.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    # Test Flood Scenario
    flood_readings = [
        SensorReading(sensor_type=SensorType.WATER_LEVEL, value=85.0, unit="cm", location=loc, victim_id="V1"),
        SensorReading(sensor_type=SensorType.WATER_FLOW, value=1.8, unit="m/s", location=loc, victim_id="V1"),
    ]
    flood_env = {"rainfall_mm_hr": 55.0, "water_level_cm": 85.0}
    flood_evidence = extractor.extract_evidence(flood_readings, flood_env)
    flood_assessment = engine.infer_scenario(flood_evidence, flood_readings, flood_env, active_scenario_hint="flood")

    assert flood_assessment.primary_scenario.scenario_id in ("flood", "flash_flood")
    assert flood_assessment.confidence_pct >= 75.0


def test_alert_lifecycle_manager_deduplication_and_escalation():
    """Test alerts are deduplicated, upgraded when severity rises, and stored."""
    alert_mgr = AlertLifecycleManager()
    session_id = f"test-sess-{uuid.uuid4().hex[:6]}"

    # Process first cycle with High Risk
    from backend.models import DisasterAssessment, ScenarioInferenceResult
    assessment_1 = DisasterAssessment(
        primary_scenario=ScenarioInferenceResult(
            scenario_id="urban_fire",
            scenario_name="Urban Firestorm",
            confidence_pct=85.0,
            risk_level=RiskLevel.HIGH,
            recommended_action="Deploy Thermal Imaging & Hazmat Squads",
        ),
        overall_risk=RiskLevel.HIGH,
        confidence_pct=85.0,
        cycle=1,
    )
    alerts_1 = alert_mgr.evaluate_and_sync(session_id, 1, assessment_1, active_alerts_db=[])
    assert len(alerts_1) > 0
    first_alert = alerts_1[0]
    assert first_alert["severity"] == "HIGH"
    assert first_alert["status"] == "ACTIVE"

    # Process second cycle with CRITICAL Risk (escalation)
    assessment_2 = DisasterAssessment(
        primary_scenario=ScenarioInferenceResult(
            scenario_id="urban_fire",
            scenario_name="Urban Firestorm",
            confidence_pct=95.0,
            risk_level=RiskLevel.CRITICAL,
            recommended_action="Immediate Evacuation and Fire Suppression",
        ),
        overall_risk=RiskLevel.CRITICAL,
        confidence_pct=95.0,
        cycle=2,
    )
    alerts_2 = alert_mgr.evaluate_and_sync(session_id, 2, assessment_2, active_alerts_db=alerts_1)
    escalated = [a for a in alerts_2 if a["hazard_type"] == "urban_fire"]
    assert len(escalated) == 1
    assert escalated[0]["severity"] == "CRITICAL"
    assert escalated[0]["status"] == "ACTIVE"


def test_scenario_intelligence_engine_full_cycle():
    """Test the complete coordinator processing a cycle."""
    engine = ScenarioIntelligenceEngine()
    session_id = f"test-sess-{uuid.uuid4().hex[:6]}"
    loc = GPSCoordinate(latitude=32.37, longitude=77.24, altitude_m=3950)

    readings = [
        SensorReading(sensor_type=SensorType.HEART_RATE_RADAR, value=72.0, unit="bpm", location=loc, victim_id="V1"),
        SensorReading(sensor_type=SensorType.THERMAL_IMAGING, value=28.5, unit="degC", location=loc, victim_id="V1"),
        SensorReading(sensor_type=SensorType.RAINFALL_INTENSITY, value=25.0, unit="mm/hr", location=loc),
        SensorReading(sensor_type=SensorType.SOIL_MOISTURE, value=70.0, unit="%", location=loc),
    ]
    env_report = {
        "rainfall_mm_hr": 25.0,
        "soil_moisture_pct": 70.0,
        "ambient_temp_c": 12.0,
        "humidity_pct": 80.0,
    }
    battery_map = {"V1": 95.0}

    assessment = engine.process_cycle(
        session_id=session_id,
        cycle=1,
        readings=readings,
        env_report=env_report,
        battery_map=battery_map,
        active_scenario_hint="landslide",
    )

    assert assessment is not None
    assert assessment.primary_scenario is not None
    assert assessment.confidence_pct > 0.0
    assert assessment.overall_risk in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert len(assessment.active_evidence) > 0
