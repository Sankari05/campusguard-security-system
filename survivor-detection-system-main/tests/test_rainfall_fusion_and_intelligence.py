"""
test_rainfall_fusion_and_intelligence.py
----------------------------------------
Unit tests for RainfallAnalyzer, scenario evidence extraction, compound hazard
triggers, and sensor fusion hazard multiplier integration.
"""

import pytest
from backend.models import (
    RainfallClassification,
    RainfallTrend,
    RainfallReading,
    SensorType,
    SensorReading,
    GPSCoordinate,
    RiskLevel,
)
from backend.scenario_intelligence import RainfallAnalyzer, ScenarioIntelligenceEngine
from backend.sensor_simulator import SensorSimulator
from backend.fusion_engine import HazardContext


def test_rainfall_analyzer_validation():
    analyzer = RainfallAnalyzer()
    assert analyzer.validate_reading(None) is False
    assert analyzer.validate_reading({"rainfall_rate_mm_h": -10.0}) is False
    assert analyzer.validate_reading({"rainfall_rate_mm_h": float("nan")}) is False
    assert analyzer.validate_reading({"rainfall_rate_mm_h": 25.0}) is True

    valid_reading = RainfallReading(sensor_id="RAIN-01", rainfall_rate_mm_h=15.0)
    assert analyzer.validate_reading(valid_reading) is True


def test_rainfall_analyzer_evidence_generation():
    analyzer = RainfallAnalyzer()

    # Extreme rainfall analysis
    reading_extreme = RainfallReading(
        sensor_id="RAIN-01",
        rainfall_rate_mm_h=120.0,
        cumulative_rainfall_mm=110.0,
    )
    res_extreme = analyzer.analyze(reading_extreme, soil_moisture_pct=75.0, water_level_cm=60.0)
    assert res_extreme["classification"] == RainfallClassification.EXTREME.value
    assert res_extreme["severity"] == RiskLevel.CRITICAL.value
    assert "RAINFALL_EXTREME_CLOUD_BURST_DETECTED" in res_extreme["evidence_tokens"]
    assert "RAINFALL_ACCUMULATION_CRITICAL" in res_extreme["evidence_tokens"]
    assert "RAINFALL_WATER_COMPOUND_FLASH_FLOOD_TRIGGER" in res_extreme["evidence_tokens"]
    assert "RAINFALL_SOIL_COMPOUND_LANDSLIDE_TRIGGER" in res_extreme["evidence_tokens"]
    assert res_extreme["flood_compound_risk"] is True
    assert res_extreme["landslide_compound_risk"] is True


def test_scenario_intelligence_engine_rainfall_integration():
    engine = ScenarioIntelligenceEngine()
    sim = SensorSimulator()
    sim.rainfall_adapter.set_simulation_profile("EXTREME")

    readings = sim.generate_cycle()
    env = sim.environmental_full_report()
    battery = sim.battery_report()

    assessment = engine.process_cycle(
        session_id="test_rainfall_intelligence_sess",
        cycle=1,
        readings=readings,
        env_report=env,
        battery_map=battery,
    )

    ev_labels = [e.evidence_label for e in assessment.active_evidence]
    assert "RAINFALL_EXTREME_CLOUD_BURST_DETECTED" in ev_labels or "TORRENTIAL_PRECIPITATION" in ev_labels


def test_fusion_hazard_multiplier_with_rainfall():
    # Base hazard context without rainfall
    ctx_normal = HazardContext(rainfall_mm_hr=0.0, soil_moisture_pct=20.0, water_level_cm=0.0)
    assert ctx_normal.multiplier() >= 1.0

    # Extreme rainfall hazard context
    ctx_extreme = HazardContext(rainfall_mm_hr=100.0, soil_moisture_pct=85.0, water_level_cm=75.0)
    assert ctx_extreme.multiplier() > ctx_normal.multiplier()
    assert ctx_extreme.multiplier() <= 2.5  # Clamped within safe operational ceiling
