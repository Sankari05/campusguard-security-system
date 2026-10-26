import pytest
from fusion_engine import fuse_victim, HazardContext, TriageClass
from models import (
    SensorType,
    SensorReading,
    GPSCoordinate,
    SensorHealthStatus,
    CameraDetectionState,
    ThermalDetectionType,
    CameraCorrelationCase,
    CAMERA_CONFIG,
)
from scenario_intelligence import CameraThermalAnalyzer, SensorEvidenceExtractor


LOC = GPSCoordinate(latitude=32.374, longitude=77.249, altitude_m=3950)


def _make_rd(sensor_type, value, confidence=1.0, unit=""):
    return SensorReading(
        sensor_type=sensor_type,
        value=value,
        unit=unit,
        location=LOC,
        victim_id="V1",
        confidence=confidence,
    )


def test_cross_modal_correlation_cases():
    """Verify CameraThermalAnalyzer accurately diagnoses Cases 1, 2, 3, and 4."""
    analyzer = CameraThermalAnalyzer()

    # Case 1: Optical Human + Thermal Human Heat -> Strong Survivor
    cam_rd_1 = {
        "status": "ONLINE",
        "detection_state": "PERSON_DETECTED",
        "confidence": 0.90,
        "person_count": 1,
    }
    thm_rd_1 = {
        "status": "ONLINE",
        "detection_type": "HUMAN_HEAT_SIGNATURE",
        "human_signature": True,
        "estimated_temperature": 35.0,
        "thermal_confidence": 0.90,
    }
    corr_1 = analyzer.analyze_cross_modal(victim_id="V1", cam_rd=cam_rd_1, thm_rd=thm_rd_1)
    assert corr_1.correlation_case == CameraCorrelationCase.CASE_1_STRONG_SURVIVOR
    assert corr_1.synergy_bonus == CAMERA_CONFIG.synergy_bonus_case1
    assert "CAMERA_HUMAN_CONFIRMED" in corr_1.evidence_tokens
    assert "THERMAL_HUMAN_HEAT_CONFIRMED" in corr_1.evidence_tokens

    # Case 2: Optical Human + Thermal No Heat -> Possible False Positive / Discount applied
    thm_rd_cold = {
        "status": "ONLINE",
        "detection_type": "NO_HEAT",
        "human_signature": False,
        "estimated_temperature": 18.0,
        "thermal_confidence": 0.10,
    }
    corr_2 = analyzer.analyze_cross_modal(victim_id="V1", cam_rd=cam_rd_1, thm_rd=thm_rd_cold)
    assert corr_2.correlation_case == CameraCorrelationCase.CASE_2_POSSIBLE_FALSE_POSITIVE
    assert "FALSE_POSITIVE_FLAGGED" in corr_2.evidence_tokens

    # Case 3: Optical No Detection + Thermal Human Heat -> Hidden/Obscured Survivor
    cam_rd_no = {
        "status": "ONLINE",
        "detection_state": "NO_DETECTION",
        "confidence": 0.05,
        "person_count": 0,
    }
    corr_3 = analyzer.analyze_cross_modal(victim_id="V1", cam_rd=cam_rd_no, thm_rd=thm_rd_1)
    assert corr_3.correlation_case == CameraCorrelationCase.CASE_3_HIDDEN_OBSCURED_SURVIVOR

    # Case 4: Quad-Sensor Corroboration (Optical + Thermal + Radar + PIR)
    corr_4 = analyzer.analyze_cross_modal(
        victim_id="V1",
        cam_rd=cam_rd_1,
        thm_rd=thm_rd_1,
        radar_bpm=75.0,
        pir_motion=0.85,
    )
    assert corr_4.correlation_case in (CameraCorrelationCase.CASE_4_QUAD_SENSOR_CORROBORATED, CameraCorrelationCase.CASE_4_MULTI_SENSOR_CONFIRMED)
    assert "QUAD_SENSOR_CORROBORATION_CONFIRMED" in corr_4.evidence_tokens
    assert corr_4.combined_confidence >= 0.90


def test_fusion_engine_single_sensor_clamping():
    """Verify single sensor alone NEVER confirms survivor (clamped to <= 35%)."""
    # Only camera active with high score, all others zero
    rd_cam = [
        _make_rd(SensorType.RGB_CAMERA, 0.95),
        _make_rd(SensorType.THERMAL_IMAGING, 20.0),
        _make_rd(SensorType.HEART_RATE_RADAR, 0.0),
        _make_rd(SensorType.PIR_MOTION, 0.0),
        _make_rd(SensorType.ACOUSTIC, 0.0),
        _make_rd(SensorType.CO2, 400.0),
    ]
    fused_cam = fuse_victim(rd_cam)
    assert fused_cam.confidence_pct <= 35.0

    # Only thermal active with high score, all others zero
    rd_thm = [
        _make_rd(SensorType.RGB_CAMERA, 0.0),
        _make_rd(SensorType.THERMAL_IMAGING, 35.5),
        _make_rd(SensorType.HEART_RATE_RADAR, 0.0),
        _make_rd(SensorType.PIR_MOTION, 0.0),
        _make_rd(SensorType.ACOUSTIC, 0.0),
        _make_rd(SensorType.CO2, 400.0),
    ]
    fused_thm = fuse_victim(rd_thm)
    assert fused_thm.confidence_pct <= 35.0


def test_fusion_engine_case2_false_positive_mitigation():
    """Verify Case 2 discounts optical score when thermal sees no body heat."""
    # When thermal confirms human heat (35°C), optical score contributes fully
    rd_1 = [
        _make_rd(SensorType.RGB_CAMERA, 0.90),
        _make_rd(SensorType.THERMAL_IMAGING, 35.5),
        _make_rd(SensorType.HEART_RATE_RADAR, 75.0),
        _make_rd(SensorType.PIR_MOTION, 0.70),
        _make_rd(SensorType.ACOUSTIC, 35.0),
        _make_rd(SensorType.CO2, 600.0),
    ]
    fused_1 = fuse_victim(rd_1)

    # When thermal sees no heat (e.g. 18°C cold mannequin), optical score is discounted
    rd_2 = [
        _make_rd(SensorType.RGB_CAMERA, 0.90),
        _make_rd(SensorType.THERMAL_IMAGING, 18.0),
        _make_rd(SensorType.HEART_RATE_RADAR, 75.0),
        _make_rd(SensorType.PIR_MOTION, 0.70),
        _make_rd(SensorType.ACOUSTIC, 35.0),
        _make_rd(SensorType.CO2, 600.0),
    ]
    fused_2 = fuse_victim(rd_2)

    # fused_1 should have significantly higher confidence due to thermal corroboration
    assert fused_1.confidence_pct > fused_2.confidence_pct
