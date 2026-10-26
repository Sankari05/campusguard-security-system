"""
test_barometric_sensor_fusion_alerts.py
---------------------------------------
Tests for Barometric Pressure integration into Multi-Sensor Fusion,
Disaster Scenario Inference (Cyclone, Flood, Storm Surge, Multi-Hazard),
Confidence & Risk Scoring, and Alert Lifecycle / Deduplication.
"""

import tempfile
import os
import pytest
from backend.models import (
    SensorType,
    SensorReading,
    SensorEvidence,
    RiskLevel,
    GPSCoordinate,
    PRESSURE_CONFIG,
)
from backend.scenario_intelligence import (
    SensorEvidenceExtractor,
    DisasterScenarioInferenceEngine,
    AlertLifecycleManager,
    ScenarioIntelligenceEngine,
)
from backend.fusion_engine import HazardContext, fuse_all
import backend.db as db


def test_evidence_extraction_cyclonic_pressure_drop():
    """Verify severe pressure drop generates SEVERE_BAROMETRIC_PRESSURE_DROP evidence."""
    extractor = SensorEvidenceExtractor()
    env_report = {
        "barometric_pressure_hpa": 982.0,
        "rainfall_mm_hr": 35.0,
    }
    evidence = extractor.extract_evidence(readings=[], trends=[], env_report=env_report)
    labels = {e.evidence_label for e in evidence}
    assert "SEVERE_BAROMETRIC_PRESSURE_DROP" in labels
    assert "PRESSURE_WEATHER_DETERIORATION" in labels


def test_evidence_extraction_offline_penalty():
    """Verify offline status generates BAROMETRIC_SENSOR_OFFLINE and no fake values."""
    extractor = SensorEvidenceExtractor()
    env_report = {
        "barometric_status": "OFFLINE",
    }
    evidence = extractor.extract_evidence(readings=[], trends=[], env_report=env_report)
    labels = {e.evidence_label for e in evidence}
    assert "BAROMETRIC_SENSOR_OFFLINE" in labels


def test_disaster_inference_cyclone():
    """Verify steep pressure plunge + torrential rain infers Cyclone scenario with HIGH/CRITICAL risk."""
    engine = DisasterScenarioInferenceEngine()
    extractor = SensorEvidenceExtractor()
    env_report = {
        "barometric_pressure_hpa": 972.0,
        "rainfall_mm_hr": 45.0,
    }
    evidence = extractor.extract_evidence(readings=[], trends=[], env_report=env_report)
    assessment = engine.infer_scenario(evidence=evidence, env_report=env_report, active_scenario_hint="cyclone")
    
    assert assessment.primary_scenario is not None
    assert assessment.primary_scenario.scenario_id == "cyclone"
    assert assessment.primary_scenario.confidence_pct >= 70.0
    assert assessment.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert any("barometric" in ev.lower() or "pressure" in ev.lower() for ev in assessment.primary_scenario.primary_evidence)


def test_alert_lifecycle_deduplication():
    """Verify AlertLifecycleManager upserts alerts in-place without duplicating rows across cycles."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        db.init_db(db_path=db_path)
        session_id = "test-alert-session-01"
        db.create_session(session_id=session_id, seed=42, enable_degradation=False, victim_count=2, db_path=db_path)

        extractor = SensorEvidenceExtractor()
        engine = DisasterScenarioInferenceEngine()
        manager = AlertLifecycleManager()

        env_report = {"barometric_pressure_hpa": 980.0, "rainfall_mm_hr": 30.0}
        evidence = extractor.extract_evidence([], trends=[], env_report=env_report)
        assessment = engine.infer_scenario(evidence, env_report=env_report)

        # Cycle 1
        alerts_c1 = manager.sync_alerts(
            session_id=session_id,
            primary_scenario=assessment.primary_scenario,
            secondary_scenarios=assessment.secondary_scenarios,
            evidence=assessment.active_evidence,
        )
        assert len(alerts_c1) >= 1
        initial_count = len(db.list_active_alerts(session_id=session_id))

        # Cycle 2 (same condition)
        alerts_c2 = manager.sync_alerts(
            session_id=session_id,
            primary_scenario=assessment.primary_scenario,
            secondary_scenarios=assessment.secondary_scenarios,
            evidence=assessment.active_evidence,
        )
        # Verify no duplicate alert keys created
        post_count = len(db.list_active_alerts(session_id=session_id))
        assert post_count == initial_count

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_fusion_engine_hazard_multiplier_with_pressure():
    """Verify HazardContext incorporates barometric pressure drop into SPS multiplier."""
    hz_normal = HazardContext(barometric_pressure_hpa=1013.25)
    hz_cyclone = HazardContext(barometric_pressure_hpa=965.0)

    assert hz_cyclone.multiplier() > hz_normal.multiplier()
    breakdown = hz_cyclone.multiplier_breakdown()
    assert "pressure_drop" in breakdown
    assert breakdown["pressure_drop"] > 0.10
