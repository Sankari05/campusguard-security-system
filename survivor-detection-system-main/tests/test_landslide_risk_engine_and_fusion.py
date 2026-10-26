"""
test_landslide_risk_engine_and_fusion.py
----------------------------------------
Tests for the Landslide Risk Analyzer, Sensor Fusion, rate of change,
persistence debouncing, compound environmental triggers, and state machine.
"""

import pytest
from backend.models import (
    SensorHealthStatus,
    MoistureTrend,
    TiltTrend,
    LandslideRiskLevel,
    LandslideEventState,
    LANDSLIDE_CONFIG,
)
from backend.scenario_intelligence import LandslideRiskAnalyzer


def test_analyzer_nominal_baseline():
    """Verify nominal soil moisture and tilt yields LOW risk and NORMAL state."""
    analyzer = LandslideRiskAnalyzer()
    res = analyzer.analyze(soil_moisture_pct=38.0, tilt_angle_deg=0.5)
    assert res["available"] is True
    assert res["risk_level"] == "LOW"
    assert res["event_state"] == "NORMAL"
    assert res["risk_score"] < 25.0
    assert res["moisture_trend"] == "STABLE"
    assert res["tilt_trend"] == "STABLE"


def test_analyzer_rising_moisture_trend():
    """Verify rising rate of change triggers RISING / RAPIDLY_RISING trend bonuses."""
    analyzer = LandslideRiskAnalyzer()
    analyzer.analyze(soil_moisture_pct=40.0, tilt_angle_deg=0.5)
    res2 = analyzer.analyze(soil_moisture_pct=46.0, tilt_angle_deg=0.5)  # +6%/cycle -> RAPIDLY_RISING
    assert res2["moisture_trend"] == "RAPIDLY_RISING"
    assert res2["moisture_trend_bonus"] == 15.0


def test_analyzer_rising_tilt_trend():
    """Verify rising tilt rate of change triggers RISING / RAPIDLY_RISING trend bonuses."""
    analyzer = LandslideRiskAnalyzer()
    analyzer.analyze(soil_moisture_pct=40.0, tilt_angle_deg=0.5)
    res2 = analyzer.analyze(soil_moisture_pct=40.0, tilt_angle_deg=1.6)  # +1.1 deg/cycle -> RAPIDLY_RISING
    assert res2["tilt_trend"] == "RAPIDLY_RISING"
    assert res2["tilt_trend_bonus"] == 25.0


def test_analyzer_single_spike_debouncing():
    """Verify single unconfirmed spike is debounced (clamped to <= 68.0 max) to prevent false alarms."""
    analyzer = LandslideRiskAnalyzer()
    # Baseline cycle
    analyzer.analyze(soil_moisture_pct=38.0, tilt_angle_deg=0.5)
    # Sudden 1-cycle spike
    res_spike = analyzer.analyze(soil_moisture_pct=88.0, tilt_angle_deg=6.5)
    # Debounced: should be clamped <= 68.0 max on first cycle
    assert res_spike["risk_score"] <= 68.0
    assert res_spike["risk_level"] != "CRITICAL"
    assert any("persistence filter" in f.lower() for f in res_spike["contributing_factors"])


def test_analyzer_multi_cycle_critical_escalation():
    """Verify sustained multi-cycle high moisture and tilt reaches CRITICAL risk (>= 75.0)."""
    analyzer = LandslideRiskAnalyzer()
    # Cycle 1: Elevated
    res1 = analyzer.analyze(soil_moisture_pct=72.0, tilt_angle_deg=2.5)
    # Cycle 2: High
    res2 = analyzer.analyze(soil_moisture_pct=82.0, tilt_angle_deg=4.5)
    # Cycle 3: Critical sustained
    res3 = analyzer.analyze(soil_moisture_pct=88.0, tilt_angle_deg=6.5)

    assert res3["risk_score"] >= LANDSLIDE_CONFIG.risk_critical_min
    assert res3["risk_level"] == "CRITICAL"
    assert res3["event_state"] == "CRITICAL"
    assert "evacuation" in res3["recommended_action"].lower()


def test_analyzer_compound_environmental_triggers():
    """Verify compound rainfall (>=25 mm/hr) and seismic shaking (>=4 mm/s) add context bonuses."""
    analyzer = LandslideRiskAnalyzer()
    res = analyzer.analyze(
        soil_moisture_pct=65.0,
        tilt_angle_deg=2.0,
        rainfall_mm_hr=35.0,
        vibration_mm_s=5.0,
    )
    assert any("torrential precipitation" in f.lower() for f in res["contributing_factors"])
    assert any("seismic ground shaking" in f.lower() for f in res["contributing_factors"])
    assert res["persistence_score"] > 0.0


def test_analyzer_offline_sensor_health():
    """Verify OFFLINE or ERROR sensor health does not emit false hazard alerts."""
    analyzer = LandslideRiskAnalyzer()
    res = analyzer.analyze(
        soil_moisture_pct=0.0,
        tilt_angle_deg=0.0,
        status=SensorHealthStatus.OFFLINE,
    )
    assert res["available"] is False
    assert res["status"] == "OFFLINE"
    assert res["risk_score"] == 0.0
    assert res["risk_level"] == "LOW"
    assert res["confidence"] == 0.0
    assert "Inspect slope telemetry" in res["recommended_action"]


def test_analyzer_recovery_hysteresis():
    """Verify recovery requires multi-cycle stabilization before returning to NORMAL state."""
    analyzer = LandslideRiskAnalyzer()
    # Bring to critical
    analyzer.analyze(soil_moisture_pct=80.0, tilt_angle_deg=4.0)
    analyzer.analyze(soil_moisture_pct=85.0, tilt_angle_deg=5.5)
    res_crit = analyzer.analyze(soil_moisture_pct=88.0, tilt_angle_deg=6.5)
    assert res_crit["event_state"] == "CRITICAL"

    # Cycle 1 back to nominal: should be in RECOVERY state
    res_rec1 = analyzer.analyze(soil_moisture_pct=38.0, tilt_angle_deg=0.5)
    assert res_rec1["risk_level"] == "LOW"
    assert res_rec1["event_state"] == "RECOVERY"

    # Cycle 2 nominal (reached 2 recovery cycles threshold) -> NORMAL
    res_rec2 = analyzer.analyze(soil_moisture_pct=38.0, tilt_angle_deg=0.5)
    assert res_rec2["event_state"] == "NORMAL"
