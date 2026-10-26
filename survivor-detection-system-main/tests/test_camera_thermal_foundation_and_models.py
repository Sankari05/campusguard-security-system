import pytest
import math
from models import (
    CameraDetectionState,
    CameraClassification,
    CameraHealthStatus,
    ThermalDetectionType,
    ThermalClassification,
    ThermalHealthStatus,
    CameraCorrelationCase,
    CameraConfig,
    CAMERA_CONFIG,
    CameraReading,
    ThermalCameraReading,
    CameraThermalCorrelation,
    GPSCoordinate,
)
import db


def test_camera_enums_and_config():
    """Verify camera and thermal enums contain all specified states."""
    assert CameraDetectionState.PERSON_DETECTED.value == "PERSON_DETECTED"
    assert CameraDetectionState.NO_DETECTION.value == "NO_DETECTION"
    assert CameraDetectionState.MULTIPLE_PERSONS.value == "MULTIPLE_PERSONS"
    assert CameraDetectionState.PARTIAL_PERSON.value == "PARTIAL_PERSON"
    assert CameraDetectionState.OCCLUDED_PERSON.value == "OCCLUDED_PERSON"
    assert CameraDetectionState.DEBRIS.value == "DEBRIS"
    assert CameraDetectionState.SMOKE.value == "SMOKE"
    assert CameraDetectionState.FIRE.value == "FIRE"
    assert CameraDetectionState.UNKNOWN_OBJECT.value == "UNKNOWN_OBJECT"

    assert ThermalDetectionType.HUMAN_HEAT_SIGNATURE.value == "HUMAN_HEAT_SIGNATURE"
    assert ThermalDetectionType.NO_HEAT.value == "NO_HEAT"
    assert ThermalDetectionType.WEAK_HEAT_SIGNATURE.value == "WEAK_HEAT_SIGNATURE"
    assert ThermalDetectionType.STRONG_HUMAN_HEAT.value == "STRONG_HUMAN_HEAT"
    assert ThermalDetectionType.MULTIPLE_HUMAN_HEAT.value == "MULTIPLE_HUMAN_HEAT"
    assert ThermalDetectionType.HOT_DEBRIS.value == "HOT_DEBRIS"
    assert ThermalDetectionType.FIRE_HOTSPOT.value == "FIRE_HOTSPOT"
    assert ThermalDetectionType.ENVIRONMENTAL_HEAT.value == "ENVIRONMENTAL_HEAT"
    assert ThermalDetectionType.THERMAL_OBSTRUCTION.value == "THERMAL_OBSTRUCTION"
    assert ThermalDetectionType.THERMAL_NOISE.value == "THERMAL_NOISE"

    assert CAMERA_CONFIG.weight_optical == 0.05
    assert CAMERA_CONFIG.weight_thermal == 0.25
    assert CAMERA_CONFIG.synergy_bonus_case1 == 0.05
    assert CAMERA_CONFIG.synergy_bonus_case4 == 0.05
    assert CAMERA_CONFIG.case2_false_positive_discount == 0.50
    assert CAMERA_CONFIG.single_sensor_max_confidence == 0.35


def test_camera_reading_validation():
    """Verify CameraReading validates correctly and rejects corrupted values."""
    # Valid reading
    valid_reading = CameraReading(
        camera_id="CAM-001",
        confidence=0.92,
        visibility=0.85,
        occlusion=0.10,
        person_count=1,
    )
    assert valid_reading.validate() is True
    d = valid_reading.to_dict()
    assert d["camera_id"] == "CAM-001"
    assert d["confidence"] == 0.92

    # Negative person count
    bad_count = CameraReading(camera_id="CAM-001", confidence=0.8, person_count=-1)
    assert bad_count.validate() is False

    # Out of bounds confidence
    bad_conf = CameraReading(camera_id="CAM-001", confidence=1.5)
    assert bad_conf.validate() is False

    # Negative visibility
    bad_vis = CameraReading(camera_id="CAM-001", confidence=0.8, visibility=-0.2)
    assert bad_vis.validate() is False

    # NaN / Inf confidence
    nan_conf = CameraReading(camera_id="CAM-001", confidence=float("nan"))
    assert nan_conf.validate() is False
    inf_conf = CameraReading(camera_id="CAM-001", confidence=float("inf"))
    assert inf_conf.validate() is False


def test_thermal_reading_validation():
    """Verify ThermalCameraReading validates correctly and rejects corrupted values."""
    # Valid reading
    valid_thm = ThermalCameraReading(
        camera_id="THERMAL-001",
        estimated_temperature=34.8,
        background_temperature=18.0,
        thermal_confidence=0.90,
        heat_signature_count=1,
    )
    assert valid_thm.validate() is True
    d = valid_thm.to_dict()
    assert d["camera_id"] == "THERMAL-001"
    assert d["estimated_temperature"] == 34.8
    assert d["temperature_delta"] == 16.8

    # Unrealistic temperature (< -100 or > 500)
    bad_temp_low = ThermalCameraReading(camera_id="THERMAL-001", estimated_temperature=-150.0)
    assert bad_temp_low.validate() is False
    bad_temp_high = ThermalCameraReading(camera_id="THERMAL-001", estimated_temperature=600.0)
    assert bad_temp_high.validate() is False

    # Negative count
    bad_count = ThermalCameraReading(camera_id="THERMAL-001", estimated_temperature=35.0, heat_signature_count=-2)
    assert bad_count.validate() is False

    # NaN / Inf
    nan_temp = ThermalCameraReading(camera_id="THERMAL-001", estimated_temperature=float("nan"))
    assert nan_temp.validate() is False


def test_camera_thermal_correlation_model():
    """Verify CameraThermalCorrelation serialization and fields."""
    corr = CameraThermalCorrelation(
        victim_id="V1",
        camera_id="CAM-001",
        thermal_camera_id="THERMAL-001",
        camera_state=CameraDetectionState.PERSON_DETECTED,
        thermal_detection=ThermalDetectionType.HUMAN_HEAT_SIGNATURE,
        correlation_case=CameraCorrelationCase.CASE_1_STRONG_SURVIVOR,
        combined_confidence=0.95,
        synergy_bonus=0.05,
        explainable_summary="Strong cross-modal survivor confirmation.",
        evidence_tokens=["CAMERA_HUMAN_CONFIRMED", "THERMAL_HUMAN_HEAT_CONFIRMED"],
    )
    d = corr.to_dict()
    assert d["victim_id"] == "V1"
    assert d["correlation_case"] == "CASE_1_STRONG_SURVIVOR"
    assert d["combined_confidence"] == 0.95
    assert d["synergy_bonus"] == 0.05
    assert len(d["evidence_tokens"]) == 2


def test_database_logging_and_analytics():
    """Verify db logging, history retrieval, and camera-thermal analytics."""
    session_id = "test-session-camera-thermal"
    
    # 1. Log camera reading
    cam_rd = CameraReading(
        camera_id="CAM-001",
        victim_id="V1",
        detection_state=CameraDetectionState.PERSON_DETECTED,
        classification=CameraClassification.HUMAN,
        person_count=1,
        confidence=0.92,
    )
    db.log_camera_reading(cam_rd, session_id=session_id)
    
    # 2. Log thermal reading
    thm_rd = ThermalCameraReading(
        camera_id="THERMAL-001",
        victim_id="V1",
        detection_type=ThermalDetectionType.HUMAN_HEAT_SIGNATURE,
        classification=ThermalClassification.HUMAN_HEAT_SIGNATURE,
        estimated_temperature=35.2,
        background_temperature=18.0,
        thermal_confidence=0.91,
        human_signature=True,
    )
    db.log_thermal_reading(thm_rd, session_id=session_id)

    # 3. Retrieve history
    cam_hist = db.get_camera_history(session_id=session_id, camera_id="CAM-001")
    assert len(cam_hist) >= 1
    assert cam_hist[0]["camera_id"] == "CAM-001"
    assert cam_hist[0]["person_count"] == 1

    thm_hist = db.get_thermal_history(session_id=session_id, camera_id="THERMAL-001")
    assert len(thm_hist) >= 1
    assert thm_hist[0]["camera_id"] == "THERMAL-001"
    assert thm_hist[0]["estimated_temperature"] == 35.2

    # 4. Analytics
    analytics = db.get_camera_thermal_analytics(session_id=session_id)
    assert analytics["total_camera_readings"] >= 1
    assert analytics["camera_person_detections"] >= 1
    assert analytics["total_thermal_readings"] >= 1
    assert analytics["thermal_human_signatures"] >= 1
