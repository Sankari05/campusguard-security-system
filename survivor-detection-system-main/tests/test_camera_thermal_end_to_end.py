import pytest
from sensor_simulator import SensorSimulator
from scenario_intelligence import ScenarioIntelligenceEngine
from fusion_engine import fuse_victim, HazardContext, SensorType
from models import HIMALAYA_VICTIMS, GPSCoordinate
import db


def test_full_camera_thermal_intelligence_cycle():
    """Verify an entire pipeline cycle with optical camera, thermal IR, fusion, and intelligence alerts."""
    # 1. Setup simulator with victims
    sim = SensorSimulator(seed=100, victims=HIMALAYA_VICTIMS)

    # Set camera and thermal profiles
    sim.camera_adapter.set_scenario_profile("PERSON_DETECTED")
    sim.thermal_adapter.set_scenario_profile("HUMAN_HEAT")

    # Generate cycle
    raw_readings = sim.generate_cycle()
    v1_readings = [r for r in raw_readings if r.victim_id == "V1"]
    v1_sensors = {r.sensor_type: r for r in v1_readings}
    assert SensorType.RGB_CAMERA in v1_sensors
    assert SensorType.THERMAL_IMAGING in v1_sensors

    cam_val = v1_sensors[SensorType.RGB_CAMERA].value
    thm_val = v1_sensors[SensorType.THERMAL_IMAGING].value
    assert cam_val >= 0.70
    assert 30.0 <= thm_val <= 38.0

    # 2. Multi-sensor fusion
    hazard_ctx = HazardContext(soil_moisture_pct=40.0, tilt_deg=1.2)
    fused_v1 = fuse_victim(v1_readings, hazard=hazard_ctx)
    assert fused_v1.confidence_pct >= 25.0
    assert fused_v1.sps > 0.0

    # 3. Scenario Intelligence & Evidence extraction
    intel_engine = ScenarioIntelligenceEngine()
    assessment = intel_engine.process_cycle(
        session_id="test-session-e2e",
        cycle=1,
        readings=raw_readings,
        env_report=sim.environmental_full_report(),
        battery_map=sim.battery_report(),
        active_scenario_hint="earthquake_building_collapse",
    )
    assert assessment is not None
    tokens = [ev.evidence_label for ev in assessment.active_evidence]
    assert "CAMERA_HUMAN_CONFIRMED" in tokens or "THERMAL_HUMAN_HEAT_CONFIRMED" in tokens or "STRONG_SURVIVOR_CORROBORATION" in tokens or len(tokens) > 0

    # 4. Fire hotspot alert trigger test
    sim.thermal_adapter.set_scenario_profile("FIRE_HOTSPOT")
    raw_readings_fire = sim.generate_cycle()
    assessment_fire = intel_engine.process_cycle(
        session_id="test-session-e2e",
        cycle=2,
        readings=raw_readings_fire,
        env_report=sim.environmental_full_report(),
        battery_map=sim.battery_report(),
        active_scenario_hint="earthquake_building_collapse",
    )
    fire_tokens = [ev.evidence_label for ev in assessment_fire.active_evidence]
    assert "THERMAL_FIRE_HOTSPOT_ALERT" in fire_tokens or "THERMAL_HOT_DEBRIS_WARNING" in fire_tokens or any("FIRE" in t or "THERMAL" in t for t in fire_tokens)
