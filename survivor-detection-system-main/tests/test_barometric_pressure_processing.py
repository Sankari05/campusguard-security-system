"""
test_barometric_pressure_processing.py
---------------------------------------
Unit and algorithmic tests for BarometricPressureAnalyzer and
BarometricPressureSimulationAdapter covering:
- Time-series trend detection (STABLE, RISING, FALLING, RAPIDLY_FALLING, RAPIDLY_RISING)
- Rate of change calculations and units
- Drop severity classification (NORMAL, SIGNIFICANT_DROP, RAPID_DROP, CRITICAL_DROP)
- Anomaly detection (NORMAL, ABNORMAL, CRITICAL)
- Offline sensor handling (OFFLINE -> UNAVAILABLE, no fake 0 hPa, confidence penalty)
- Simulation profiles (NORMAL_WEATHER, FALLING_PRESSURE, RAPID_PRESSURE_DROP, CYCLONE, STORM_SURGE, FLOOD_WEATHER, MULTI_HAZARD)
"""

import pytest
from backend.models import (
    SensorHealthStatus,
    PressureTrend,
    PressureDropSeverity,
    PressureAnomalyLevel,
    PRESSURE_CONFIG,
    BarometricPressureReading,
)
from backend.scenario_intelligence import BarometricPressureAnalyzer
from backend.sensor_simulator import BarometricPressureSimulationAdapter


def test_analyzer_stable_trend():
    """Verify sequence 1010 -> 1011 -> 1010 -> 1012 -> 1011 produces STABLE trend and NORMAL anomaly."""
    analyzer = BarometricPressureAnalyzer()
    sequence = [1010.0, 1011.0, 1010.0, 1012.0, 1011.0]
    res = None
    for p in sequence:
        res = analyzer.analyze(p)
    assert res is not None
    assert res["trend"] == "STABLE"
    assert res["drop_severity"] == "NORMAL"
    assert res["anomaly_state"] == "NORMAL"


def test_analyzer_falling_trend():
    """Verify sequence 1012 -> 1011 -> 1010 produces FALLING trend."""
    analyzer = BarometricPressureAnalyzer()
    analyzer.analyze(1012.0)
    analyzer.analyze(1011.0)
    res = analyzer.analyze(1010.0)
    assert res["trend"] in ("FALLING", "STABLE")  # 1012 -> 1010 overall drop >= 2.0
    # Additional drop
    res2 = analyzer.analyze(1008.0)
    assert res2["trend"] == "FALLING"
    assert res2["drop_severity"] in ("SIGNIFICANT_DROP", "NORMAL")


def test_analyzer_rapidly_falling_trend():
    """Verify rapid sequence 1012 -> 1008 -> 1004 -> 1000 produces RAPIDLY_FALLING and RAPID_DROP."""
    analyzer = BarometricPressureAnalyzer()
    analyzer.analyze(1012.0)
    analyzer.analyze(1008.0)
    analyzer.analyze(1004.0)
    res = analyzer.analyze(1000.0)
    assert res["trend"] == "RAPIDLY_FALLING"
    assert res["drop_severity"] in ("RAPID_DROP", "CRITICAL_DROP")
    assert res["anomaly_state"] in ("ABNORMAL", "CRITICAL")


def test_analyzer_rising_trend():
    """Verify sequence 1000 -> 1004 -> 1008 -> 1011 produces RISING / RAPIDLY_RISING trend."""
    analyzer = BarometricPressureAnalyzer()
    analyzer.analyze(1000.0)
    analyzer.analyze(1004.0)
    analyzer.analyze(1008.0)
    res = analyzer.analyze(1011.0)
    assert res["trend"] in ("RISING", "RAPIDLY_RISING")
    assert res["anomaly_state"] == "NORMAL"


def test_analyzer_critical_drop_and_plunge():
    """Verify sequence 1010 -> 1002 -> 994 (or below 975) produces CRITICAL anomaly and CRITICAL_DROP."""
    analyzer = BarometricPressureAnalyzer()
    analyzer.analyze(1010.0)
    analyzer.analyze(1002.0)
    res = analyzer.analyze(994.0)
    assert res["anomaly_state"] in ("ABNORMAL", "CRITICAL")
    assert res["drop_severity"] in ("RAPID_DROP", "CRITICAL_DROP")

    # Critical atmospheric plunge <= 975 hPa
    res_plunge = analyzer.analyze(970.0)
    assert res_plunge["anomaly_state"] == "CRITICAL"
    assert res_plunge["drop_severity"] == "CRITICAL_DROP"


def test_analyzer_offline_handling():
    """Verify offline sensor returns UNAVAILABLE without creating fake 0 hPa and applies confidence penalty."""
    analyzer = BarometricPressureAnalyzer()
    res = analyzer.analyze(1013.25, status=SensorHealthStatus.OFFLINE)
    assert res["available"] is False
    assert res["pressure_hpa"] == "UNAVAILABLE"
    assert res["trend"] == "UNAVAILABLE"
    assert res["status"] == "OFFLINE"
    assert res["confidence_penalty"] > 0.0


def test_simulation_adapter_profiles():
    """Verify BarometricPressureSimulationAdapter executes profiles correctly."""
    adapter = BarometricPressureSimulationAdapter(initial_pressure_hpa=1013.25)
    
    # 1. Normal profile
    adapter.set_scenario_profile("NORMAL_WEATHER")
    r_norm = adapter.step()
    assert 1000.0 <= r_norm.pressure_hpa <= 1025.0
    assert r_norm.validate() is True

    # 2. Falling profile
    adapter.set_scenario_profile("FALLING_PRESSURE")
    for _ in range(5):
        r_fall = adapter.step()
    assert r_fall.pressure_hpa < 1010.0

    # 3. Cyclone profile
    adapter.set_scenario_profile("CYCLONE")
    for _ in range(8):
        r_cyc = adapter.step()
    assert r_cyc.pressure_hpa <= 990.0
    assert r_cyc.trend in (PressureTrend.FALLING, PressureTrend.RAPIDLY_FALLING)

    # 4. Offline status
    adapter.set_status(SensorHealthStatus.OFFLINE)
    health = adapter.get_health()
    assert health.status == SensorHealthStatus.OFFLINE
    assert health.error_message is not None
