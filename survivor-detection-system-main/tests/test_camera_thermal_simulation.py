import pytest
from sensor_simulator import (
    SensorSimulator,
    CameraSimulationAdapter,
    ThermalCameraSimulationAdapter,
)
from models import (
    VictimProfile,
    VictimStatus,
    GPSCoordinate,
    SensorSignatureRange,
    CameraDetectionState,
    ThermalDetectionType,
    CameraHealthStatus,
    ThermalHealthStatus,
)


def _make_dummy_victim(victim_id="V1"):
    return VictimProfile(
        victim_id=victim_id,
        label=f"Victim {victim_id}",
        status=VictimStatus.CRITICAL,
        location=GPSCoordinate(latitude=32.3740, longitude=77.2492, altitude_m=3955.0),
        burial_depth_m=1.0,
        signature_range=SensorSignatureRange(
            thermal_imaging_c=(34.0, 36.0),
            pir_motion=(0.6, 0.9),
            acoustic_db=(45.0, 60.0),
            co2_ppm=(500.0, 800.0),
            heart_rate_radar_bpm=(70.0, 90.0),
            rgb_camera_conf=(0.7, 0.95),
        ),
    )


def test_camera_simulation_adapter_profiles():
    """Verify CameraSimulationAdapter generates accurate profiles."""
    victim = _make_dummy_victim("V1")
    adapter = CameraSimulationAdapter(victims=[victim])

    # 1. PERSON_DETECTED profile
    adapter.set_scenario_profile("PERSON_DETECTED")
    rd = adapter.read_camera(camera_id="CAM-001")
    assert rd.detection_state == CameraDetectionState.PERSON_DETECTED
    assert rd.confidence >= 0.75
    assert rd.person_count >= 1
    assert rd.status == CameraHealthStatus.ONLINE

    # 2. OCCLUDED_PERSON profile
    adapter.set_scenario_profile("OCCLUDED_PERSON")
    rd_occ = adapter.read_camera(camera_id="CAM-001")
    assert rd_occ.detection_state == CameraDetectionState.OCCLUDED_PERSON
    assert rd_occ.occlusion >= 0.35

    # 3. DEBRIS profile (mannequin / false positive)
    adapter.set_scenario_profile("DEBRIS")
    rd_deb = adapter.read_camera(camera_id="CAM-001")
    assert rd_deb.detection_state == CameraDetectionState.DEBRIS
    assert rd_deb.debris_present is True

    # 4. CAMERA_FAILURE profile
    adapter.set_scenario_profile("CAMERA_FAILURE")
    rd_fail = adapter.read_camera(camera_id="CAM-001")
    assert rd_fail.status == CameraHealthStatus.OFFLINE
    assert rd_fail.confidence == 0.0


def test_thermal_simulation_adapter_profiles():
    """Verify ThermalCameraSimulationAdapter generates accurate thermal signatures."""
    victim = _make_dummy_victim("V1")
    adapter = ThermalCameraSimulationAdapter(victims=[victim])

    # 1. HUMAN_HEAT profile
    adapter.set_scenario_profile("HUMAN_HEAT")
    rd = adapter.read_thermal(camera_id="THERMAL-001")
    assert rd.detection_type == ThermalDetectionType.HUMAN_HEAT_SIGNATURE
    assert rd.human_signature is True
    assert 32.0 <= rd.estimated_temperature <= 38.0
    assert rd.thermal_confidence >= 0.80

    # 2. FIRE_HOTSPOT profile
    adapter.set_scenario_profile("FIRE_HOTSPOT")
    rd_fire = adapter.read_thermal(camera_id="THERMAL-001")
    assert rd_fire.detection_type == ThermalDetectionType.FIRE_HOTSPOT
    assert rd_fire.fire_hotspot is True
    assert rd_fire.estimated_temperature >= 55.0

    # 3. HOT_DEBRIS profile
    adapter.set_scenario_profile("HOT_DEBRIS")
    rd_deb = adapter.read_thermal(camera_id="THERMAL-001")
    assert rd_deb.detection_type == ThermalDetectionType.HOT_DEBRIS
    assert rd_deb.hot_debris is True
    assert 40.0 <= rd_deb.estimated_temperature <= 55.0

    # 4. NO_HEAT profile
    adapter.set_scenario_profile("NO_HEAT")
    rd_cold = adapter.read_thermal(camera_id="THERMAL-001")
    assert rd_cold.detection_type == ThermalDetectionType.NO_HEAT
    assert rd_cold.human_signature is False
    assert rd_cold.heat_signature_count == 0


def test_sensor_simulator_multi_camera_reports():
    """Verify SensorSimulator aggregates multi-camera channels cleanly."""
    sim = SensorSimulator()
    v1 = _make_dummy_victim("V1")
    v2 = _make_dummy_victim("V2")
    sim.victims = [v1, v2]

    # Generate cycle
    sim.generate_cycle()

    # Reports
    cam_rep = sim.cameras_all_report()
    assert cam_rep["camera_count"] >= 4
    assert "CAM-001" in cam_rep["cameras"]

    thm_rep = sim.thermal_all_report()
    assert thm_rep["thermal_count"] >= 4
    assert "THERMAL-001" in thm_rep["thermal_cameras"]

    corr_rep = sim.camera_thermal_correlation_report("V1")
    assert corr_rep["victim_id"] == "V1"
    assert "correlation_case" in corr_rep
    assert "combined_confidence" in corr_rep
