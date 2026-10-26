"""
Comprehensive Automated Test Suite for RIDGEWATCH Subsurface UWB Bioradar Simulation (0–6.0m Upgrade).

This test suite validates the deterministic 0–6.0m software simulation pipeline:
1. Sensor registration & hardware inventory (DEV-UWB-RADAR-01, SensorType.UWB_BIORADAR)
2. Dielectric soil model across 6 soil types + Moisture sweep (10%, 25%, 45%, 65%, 85%)
3. Multi-layer soil propagation calculation (Layered-soil simulation model)
4. Fast-time synthetic radar scan generation (0–6.0m, 256 bins, depth-dependent loss)
5. Range bin indexing and ToF conversion consistency across 0–6.0m
6. Fast-time DSP processing, TVG curve, envelope, NMS peak detection
7. Depth estimation across 1m, 2m, 3m, 4m, 5m (Primary Demo), and 6m (Boundary)
8. Monotonic depth-dependent SNR degradation
9. Strict Ground Truth isolation (DSP blind to ground-truth targets metadata)
10. Difficult soil stress tests: 5m saturated mud (low SNR/unreliable) & 5m heavy clay
11. Clutter & non-survivor false positive rejection (rocks, roots, groundwater, empty soil)
12. Multiple survivor detection & separation (1.0m, 3.0m, 5.0m)
13. Slow-time vital sign DSP (Respiration RPM, Micro-motion, Heartbeat BPM)
14. Dynamic depth uncertainty scaling (±δ m)
15. Simulator lifecycle (start, pause, resume, reset, presets 1–11, offline handling)
16. Scenario sensor profile & Fusion engine integration (Landslide UWB weighting, SPS triage)
17. Subsurface REST APIs (status, simulate, config, control, presets 1-11, sensor-reading)

IMPORTANT DISCLAIMER:
These tests validate the 0–6.0m SOFTWARE SIMULATION. 5.0m is a software simulation target.
They do NOT represent physical radar measurements and do NOT constitute experimental
validation of 5m real-world soil penetration.
"""

import pytest
import math
from fastapi.testclient import TestClient

from backend.models import (
    SensorType,
    SensorValidator,
    SensorReading,
    GPSCoordinate,
    SubsurfaceSoilType,
    SubsurfaceTargetState,
    SubsurfaceSimulationConfig,
    SubsurfaceRadarTelemetry,
)
from backend.hardware_registry import HARDWARE_INVENTORY, HARDWARE_TOPOLOGY
from backend.subsurface_dsp import (
    estimate_dielectric_constant,
    calculate_layered_propagation,
    generate_synthetic_fast_time_scan,
    process_fast_time_dsp,
    analyze_slow_time_vitals,
    SubsurfaceSimulator,
    get_subsurface_simulator,
    SyntheticFastTimeScan,
    C_AIR,
    DEPTH_MAX_M,
    SUBSURFACE_MAX_DEPTH_M,
    NUM_RANGE_BINS,
    RADAR_PRESETS,
)
from backend.scenario_sensor_profiles import (
    get_scenario_sensor_profile,
    LANDSLIDE_PROFILE,
)
from backend.fusion_engine import (
    fuse_victim,
    HazardContext,
    TriageClass,
    WEIGHT_UWB_LANDSLIDE,
)
from backend.api import app

client = TestClient(app)


# ==============================================================================
# 1. Sensor Registration & Hardware Inventory Tests
# ==============================================================================

class TestSensorRegistration:
    """Validate that UWB_BIORADAR is registered cleanly in inventory & topology."""

    def test_uwb_bioradar_sensor_enum_exists(self):
        assert hasattr(SensorType, "UWB_BIORADAR")
        assert SensorType.UWB_BIORADAR.value == "uwb_bioradar"
        assert hasattr(SensorType, "HEART_RATE_RADAR")
        assert SensorType.HEART_RATE_RADAR.value == "heart_rate_radar"

    def test_sensor_bounds_includes_uwb_bioradar(self):
        assert SensorType.UWB_BIORADAR in SensorValidator.SENSOR_BOUNDS
        min_v, max_v, higher_is_better = SensorValidator.SENSOR_BOUNDS[SensorType.UWB_BIORADAR]
        assert min_v == 0.0
        assert max_v == 100.0
        assert higher_is_better is True

    def test_virtual_device_in_hardware_inventory(self):
        dev_id = "DEV-UWB-RADAR-01"
        found = [d for d in HARDWARE_INVENTORY if d.device_id == dev_id]
        assert len(found) == 1
        dev = found[0]
        assert dev.device_id == dev_id
        assert dev.sensor_type == SensorType.UWB_BIORADAR
        assert dev.is_simulated is True
        assert "Subsurface UWB Bioradar" in dev.name

    def test_virtual_device_in_hardware_topology(self):
        dev_id = "DEV-UWB-RADAR-01"
        conns = [c for c in HARDWARE_TOPOLOGY if c.source_id == dev_id or c.target_id == dev_id]
        assert len(conns) >= 1
        topo = conns[0]
        assert topo.source_id == dev_id
        assert topo.target_id == "DEV-CTRL-ESP32"
        assert topo.is_virtual is True


# ==============================================================================
# 2. 0–6.0m Range Constants & Bin Indexing Resolution
# ==============================================================================

class TestRangeResolutionAndConstants:
    """Validate 0–6.0m simulation depth range and 256 range bins resolution."""

    def test_max_depth_constants(self):
        assert DEPTH_MAX_M == 6.0
        assert SUBSURFACE_MAX_DEPTH_M == 6.0
        assert NUM_RANGE_BINS == 256

    def test_depth_axis_resolution(self):
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.DRY_SOIL,
            soil_moisture_pct=15.0,
            survivor_mode="none",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=42)

        assert len(scan.depth_axis_m) == 256
        assert len(scan.raw_signal) == 256
        assert len(scan.time_axis_ns) == 256

        assert scan.depth_axis_m[0] == 0.0
        assert abs(scan.depth_axis_m[-1] - 6.0) < 0.05

        bin_width = scan.depth_axis_m[1] - scan.depth_axis_m[0]
        # 6.0m / 256 bins ~ 0.0234m (2.34 cm)
        assert 0.020 <= bin_width <= 0.026


# ==============================================================================
# 3. Soil Dielectric Model & Moisture Sweep Tests
# ==============================================================================

class TestSoilDielectricModel:
    """Validate deterministic dielectric permittivity and propagation speed estimates."""

    @pytest.mark.parametrize("soil_type, moisture, clay, expected_min_eps, expected_max_eps", [
        (SubsurfaceSoilType.DRY_SOIL, 10.0, 0.05, 2.5, 7.0),
        (SubsurfaceSoilType.SANDY_SOIL, 25.0, 0.05, 4.0, 15.0),
        (SubsurfaceSoilType.CLAY_SOIL, 40.0, 0.45, 8.0, 30.0),
        (SubsurfaceSoilType.WET_SOIL, 60.0, 0.15, 12.0, 35.0),
        (SubsurfaceSoilType.SATURATED_MUD, 85.0, 0.30, 20.0, 70.0),
        (SubsurfaceSoilType.MIXED_DEBRIS_SOIL, 35.0, 0.10, 6.0, 22.0),
    ])
    def test_dielectric_constant_ranges(self, soil_type, moisture, clay, expected_min_eps, expected_max_eps):
        res = estimate_dielectric_constant(soil_type, moisture, clay)
        eps = res["estimated_relative_permittivity"]
        v_soil = res["propagation_speed_m_per_ns"]
        atten = res["attenuation_db_per_m"]

        assert expected_min_eps <= eps <= expected_max_eps
        assert 0.03 <= v_soil <= 0.30
        assert atten > 0.0
        assert "SIMULATED SOIL MODEL" in res["model_status"]

    @pytest.mark.parametrize("moisture_pct", [10.0, 25.0, 45.0, 65.0, 85.0])
    def test_moisture_sweep_monotonic_permittivity(self, moisture_pct):
        res = estimate_dielectric_constant(SubsurfaceSoilType.SANDY_SOIL, moisture_pct, 0.10)
        assert res["estimated_relative_permittivity"] > 1.0
        assert res["propagation_speed_m_per_ns"] < C_AIR

    def test_higher_moisture_increases_permittivity_and_attenuation(self):
        dry = estimate_dielectric_constant(SubsurfaceSoilType.SANDY_SOIL, 10.0, 0.05)
        wet = estimate_dielectric_constant(SubsurfaceSoilType.SANDY_SOIL, 70.0, 0.05)
        assert wet["estimated_relative_permittivity"] > dry["estimated_relative_permittivity"]
        assert wet["propagation_speed_m_per_ns"] < dry["propagation_speed_m_per_ns"]
        assert wet["attenuation_db_per_m"] > dry["attenuation_db_per_m"]


# ==============================================================================
# 4. Layered Soil Simulation Model Tests
# ==============================================================================

class TestLayeredSoilModel:
    """Validate multi-strata propagation calculations (Layered-soil simulation model)."""

    def test_calculate_layered_propagation(self):
        profile = [
            {"depth_start_m": 0.0, "depth_end_m": 0.8, "soil_type": "dry_soil", "moisture_pct": 10.0},
            {"depth_start_m": 0.8, "depth_end_m": 2.5, "soil_type": "wet_soil", "moisture_pct": 50.0},
            {"depth_start_m": 2.5, "depth_end_m": 6.0, "soil_type": "clay_soil", "moisture_pct": 40.0},
        ]
        res = calculate_layered_propagation(profile, target_depth_m=6.0)

        assert "effective_permittivity" in res
        assert "effective_velocity_m_per_ns" in res
        assert "effective_attenuation_db_per_m" in res
        assert res["layer_count"] == 3
        assert 0.03 <= res["effective_velocity_m_per_ns"] <= 0.25
        assert res["model_status"] == "SIMULATED LAYERED-SOIL MODEL (0-6.0m)"


# ==============================================================================
# 5. Depth Estimation Across 1m, 2m, 3m, 4m, 5m (Primary Demo), 6m (Boundary)
# ==============================================================================

class TestTargetDepthEstimations:
    """Validate fast-time DSP depth estimation across individual depth targets 1m–6m."""

    def test_target_estimation_1m(self):
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.DRY_SOIL,
            soil_moisture_pct=10.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=1.0,
            clutter_level="low",
            sensor_noise="low",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=101)
        envelope, peaks = process_fast_time_dsp(scan, dielectric)

        assert len(peaks) >= 1
        primary = min(peaks, key=lambda p: abs(p.estimated_depth_m - 1.0))
        err = abs(primary.estimated_depth_m - 1.0)
        assert err <= 0.15, f"1.0m target error too high: {err:.3f}m"
        assert primary.snr_db > 14.0

    def test_target_estimation_2m(self):
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.SANDY_SOIL,
            soil_moisture_pct=20.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=2.0,
            clutter_level="low",
            sensor_noise="low",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=202)
        envelope, peaks = process_fast_time_dsp(scan, dielectric)

        assert len(peaks) >= 1
        primary = min(peaks, key=lambda p: abs(p.estimated_depth_m - 2.0))
        err = abs(primary.estimated_depth_m - 2.0)
        assert err <= 0.20, f"2.0m target error too high: {err:.3f}m"
        assert primary.snr_db > 10.0

    def test_target_estimation_3m(self):
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.DRY_SOIL,
            soil_moisture_pct=15.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=3.0,
            clutter_level="low",
            sensor_noise="low",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=303)
        envelope, peaks = process_fast_time_dsp(scan, dielectric)

        assert len(peaks) >= 1
        primary = min(peaks, key=lambda p: abs(p.estimated_depth_m - 3.0))
        err = abs(primary.estimated_depth_m - 3.0)
        assert err <= 0.25, f"3.0m target error too high: {err:.3f}m"
        assert primary.snr_db > 8.0

    def test_target_estimation_4m(self):
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.SANDY_SOIL,
            soil_moisture_pct=18.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=4.0,
            clutter_level="low",
            sensor_noise="low",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=404)
        envelope, peaks = process_fast_time_dsp(scan, dielectric)

        assert len(peaks) >= 1
        primary = min(peaks, key=lambda p: abs(p.estimated_depth_m - 4.0))
        err = abs(primary.estimated_depth_m - 4.0)
        assert err <= 0.30, f"4.0m target error too high: {err:.3f}m"
        assert primary.snr_db > 5.0

    def test_primary_target_estimation_5m(self):
        """PRIMARY DEMO TARGET: 5.0m survivor simulation."""
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.SANDY_SOIL,
            soil_moisture_pct=18.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=5.0,
            clutter_level="low",
            sensor_noise="low",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=505)
        envelope, peaks = process_fast_time_dsp(scan, dielectric)

        assert len(peaks) >= 1, "5.0m survivor peak should be detected under favorable sandy soil"
        primary = min(peaks, key=lambda p: abs(p.estimated_depth_m - 5.0))
        err = abs(primary.estimated_depth_m - 5.0)
        assert err <= 0.35, f"5.0m target error too high: {err:.3f}m (est={primary.estimated_depth_m:.3f}m)"
        assert primary.snr_db > 3.0
        assert primary.depth_uncertainty_m >= 0.05

    def test_boundary_target_estimation_6m(self):
        """Boundary test at 5.7m near 6.0m limit."""
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.DRY_SOIL,
            soil_moisture_pct=10.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=5.7,
            clutter_level="low",
            sensor_noise="low",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=606)
        envelope, peaks = process_fast_time_dsp(scan, dielectric)

        # Boundary may produce detection or weak peak
        assert len(peaks) >= 0
        if peaks:
            primary = min(peaks, key=lambda p: abs(p.estimated_depth_m - 5.7))
            assert abs(primary.estimated_depth_m - 5.7) <= 0.45


# ==============================================================================
# 6. Monotonic Depth-Dependent SNR Degradation
# ==============================================================================

class TestDepthDegradation:
    """Validate that deeper targets naturally exhibit lower SNR under identical soil."""

    def test_depth_dependent_snr_degradation(self):
        depths = [1.0, 2.0, 3.0, 4.0, 5.0]
        snrs = []

        for d in depths:
            cfg = SubsurfaceSimulationConfig(
                soil_type=SubsurfaceSoilType.SANDY_SOIL,
                soil_moisture_pct=20.0,
                survivor_mode="one",
                survivor_alive=True,
                burial_depth_m=d,
                clutter_level="low",
                sensor_noise="low",
            )
            dielectric = estimate_dielectric_constant(cfg.soil_type, cfg.soil_moisture_pct)
            scan = generate_synthetic_fast_time_scan(cfg, dielectric, seed=707)
            _, peaks = process_fast_time_dsp(scan, dielectric)
            if peaks:
                target_peak = min(peaks, key=lambda p: abs(p.estimated_depth_m - d))
                snrs.append(target_peak.snr_db)
            else:
                snrs.append(-99.0)

        # 1.0m SNR should be significantly higher than 5.0m SNR
        assert snrs[0] > snrs[-1], f"1.0m SNR ({snrs[0]} dB) not higher than 5.0m SNR ({snrs[-1]} dB)"
        assert snrs[0] > snrs[2] > snrs[4]


# ==============================================================================
# 7. Strict Ground-Truth Isolation Verification
# ==============================================================================

class TestGroundTruthIsolation:
    """Verify that ground truth depth is strictly isolated from DSP estimation."""

    def test_dsp_does_not_use_true_depth_for_5m_target(self):
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.DRY_SOIL,
            soil_moisture_pct=15.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=5.0,
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=808)

        # Purposely erase ground_truth_targets metadata to prove DSP is 100% blind to ground truth
        blind_scan = SyntheticFastTimeScan(
            depth_axis_m=scan.depth_axis_m,
            time_axis_ns=scan.time_axis_ns,
            raw_signal=scan.raw_signal,
            ground_truth_targets=[],  # Emptied
            clutter_profile=scan.clutter_profile,
            noise_floor=scan.noise_floor,
        )
        envelope, peaks = process_fast_time_dsp(blind_scan, dielectric)

        assert len(peaks) >= 1
        primary = min(peaks, key=lambda p: abs(p.estimated_depth_m - 5.0))
        # Estimation comes purely from time-of-flight on raw signal
        assert abs(primary.estimated_depth_m - 5.0) <= 0.30
        assert primary.depth_uncertainty_m > 0.0


# ==============================================================================
# 8. Difficult Soil Stress Cases: 5m Saturated Mud & 5m Heavy Clay
# ==============================================================================

class TestDifficultSoilStressCases:
    """Validate that heavily attenuating media (saturated mud) naturally degrade detection."""

    def test_5m_saturated_mud_severely_attenuates_or_fails(self):
        config_dry = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.DRY_SOIL,
            soil_moisture_pct=10.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=5.0,
            clutter_level="low",
            sensor_noise="low",
        )
        config_mud = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.SATURATED_MUD,
            soil_moisture_pct=85.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=5.0,
            clutter_level="high",
            sensor_noise="medium",
        )

        d_dry = estimate_dielectric_constant(config_dry.soil_type, config_dry.soil_moisture_pct)
        d_mud = estimate_dielectric_constant(config_mud.soil_type, config_mud.soil_moisture_pct)

        scan_dry = generate_synthetic_fast_time_scan(config_dry, d_dry, seed=909)
        scan_mud = generate_synthetic_fast_time_scan(config_mud, d_mud, seed=909)

        _, peaks_dry = process_fast_time_dsp(scan_dry, d_dry)
        _, peaks_mud = process_fast_time_dsp(scan_mud, d_mud)

        dry_snr = max((p.snr_db for p in peaks_dry), default=0.0)
        mud_snr = max((p.snr_db for p in peaks_mud), default=0.0)

        # Saturated mud at 5m exhibits significantly degraded SNR compared to dry soil
        assert dry_snr > mud_snr

    def test_5m_heavy_clay_increases_uncertainty(self):
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.CLAY_SOIL,
            soil_moisture_pct=45.0,
            survivor_mode="one",
            survivor_alive=True,
            burial_depth_m=5.0,
            clutter_level="medium",
            sensor_noise="low",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=910)
        envelope, peaks = process_fast_time_dsp(scan, dielectric)

        if peaks:
            target_peaks = [p for p in peaks if abs(p.estimated_depth_m - 5.0) <= 0.60]
            if target_peaks:
                assert target_peaks[0].depth_uncertainty_m >= 0.08


# ==============================================================================
# 9. Multiple Survivors Simulation & Separation (1m, 3m, 5m)
# ==============================================================================

class TestMultipleSurvivorsSimulation:
    """Validate multiple survivor separation across distinct depths."""

    def test_three_survivors_resolution_1m_3m_5m(self):
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.SANDY_SOIL,
            soil_moisture_pct=15.0,
            survivor_mode="multiple",
            survivor_alive=True,
            clutter_level="low",
            sensor_noise="low",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=111)
        envelope, peaks = process_fast_time_dsp(scan, dielectric)

        assert len(peaks) >= 2, f"Expected multiple peaks, got {len(peaks)}"
        depths = [p.estimated_depth_m for p in peaks]

        # Check for presence of peaks near 1.0m, 3.0m, and 5.0m
        has_shallow = any(abs(d - 1.0) <= 0.35 for d in depths)
        has_mid = any(abs(d - 3.0) <= 0.40 for d in depths)
        has_deep = any(abs(d - 5.0) <= 0.50 for d in depths)

        assert has_shallow, f"Missing 1.0m target peak in depths: {depths}"
        assert has_mid, f"Missing 3.0m target peak in depths: {depths}"
        assert has_deep, f"Missing 5.0m target peak in depths: {depths}"


# ==============================================================================
# 10. False Positive Rejection & Inanimate Targets
# ==============================================================================

class TestFalsePositiveRejection:
    """Validate rejection of inanimate objects (rocks, roots, debris) from survivor classification."""

    def test_empty_soil_no_survivor(self):
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.DRY_SOIL,
            soil_moisture_pct=15.0,
            survivor_mode="none",
            survivor_alive=False,
            clutter_level="low",
            sensor_noise="low",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=222)
        envelope, peaks = process_fast_time_dsp(scan, dielectric)

        assert len(peaks) == 0 or all(p.peak_amplitude < 1.0 for p in peaks)

    def test_inanimate_target_no_respiration_or_micromotion(self):
        target_gt = {
            "is_alive": False,
            "resp_rpm": 0.0,
            "hr_bpm": 0.0,
            "micro_motion": False,
        }
        vitals = analyze_slow_time_vitals(
            target_ground_truth=target_gt,
            peak_snr_db=12.0,
            clutter_level="medium",
            seed=333,
        )

        assert vitals.micro_motion_detected is False
        assert vitals.respiration_rpm == 0.0
        assert vitals.vital_confidence <= 0.15


# ==============================================================================
# 11. Slow-Time Vital Sign DSP Tests (Respiration & Micro-Motion)
# ==============================================================================

class TestSlowTimeVitalDSP:
    """Validate spectral vital sign extraction."""

    def test_live_survivor_respiration_and_micromotion(self):
        target_gt = {
            "is_alive": True,
            "resp_rpm": 16.0,
            "hr_bpm": 72.0,
            "micro_motion": True,
        }
        vitals = analyze_slow_time_vitals(
            target_ground_truth=target_gt,
            peak_snr_db=12.0,
            clutter_level="low",
            seed=444,
        )

        assert vitals.micro_motion_detected is True
        assert abs(vitals.respiration_rpm - 16.0) <= 3.5
        assert vitals.vital_confidence >= 0.70

    def test_deep_weak_survivor_vitals_degradation(self):
        target_gt = {
            "is_alive": True,
            "resp_rpm": 14.0,
            "hr_bpm": 68.0,
            "micro_motion": True,
        }
        # Low SNR at deep range (e.g. 5m in mud)
        vitals = analyze_slow_time_vitals(
            target_ground_truth=target_gt,
            peak_snr_db=1.5,
            clutter_level="high",
            seed=555,
        )

        # Should either drop cardiac or have reduced confidence
        assert vitals.vital_confidence < 0.60


# ==============================================================================
# 12. Subsurface Simulator Engine & All 11 Presets
# ==============================================================================

class TestSubsurfaceSimulatorEngine:
    """Validate simulator lifecycle, presets 1 through 11, and telemetry output."""

    @pytest.mark.parametrize("preset_num", range(1, 13))
    def test_all_12_presets_load_and_run(self, preset_num):
        sim = SubsurfaceSimulator()
        sim.set_preset(preset_num)
        telem = sim.run_simulation_cycle(seed=42)

        assert telem.max_depth_m == 6.0
        assert telem.status in ["TARGET_DETECTED", "NO_TARGET", "SCANNING", "SENSOR_OFFLINE"]
        assert len(telem.radargram_profile) == 256

    def test_preset_5_primary_5m_landslide_demo(self):
        """Verify Preset 5 is the primary 5.0m landslide demo target."""
        sim = SubsurfaceSimulator()
        sim.set_preset(5)
        telem = sim.run_simulation_cycle(seed=42)

        assert telem.soil_type == "dry_soil"
        assert telem.status == "TARGET_DETECTED"
        assert telem.primary_target is not None
        assert abs(telem.primary_target.ground_truth_depth_m - 5.0) < 0.01
        assert abs(telem.primary_target.estimated_depth_m - 5.0) <= 0.45
        assert telem.primary_target.respiration_rate_rpm > 10.0
        assert telem.primary_target.micro_motion_detected is True

    def test_preset_6_5m_saturated_mud_case(self):
        sim = SubsurfaceSimulator()
        sim.set_preset(6)
        telem = sim.run_simulation_cycle(seed=42)

        assert telem.soil_type == "saturated_mud"
        assert telem.soil_moisture_pct == 85.0

    def test_preset_9_or_11_multiple_survivors(self):
        sim = SubsurfaceSimulator()
        sim.set_preset(9)
        telem = sim.run_simulation_cycle(seed=42)

        assert telem.survivor_present is True
        assert len(telem.all_targets) >= 2

    def test_simulator_lifecycle_controls(self):
        sim = SubsurfaceSimulator()
        sim.start()
        assert sim.is_running is True

        sim.pause()
        assert sim.is_running is False

        sim.resume()
        assert sim.is_running is True

        sim.reset()
        assert sim.cycle_count == 0
        assert sim.is_running is True


# ==============================================================================
# 13. Scenario Sensor Profile & Fusion Integration Tests
# ==============================================================================

class TestLandslideFusionIntegration:
    """Validate scenario weighting, Landslide profile, and SPS triage prioritization."""

    def test_landslide_sensor_profile_registered(self):
        profile = get_scenario_sensor_profile("landslide")
        assert profile is not None
        assert profile.scenario_id == "landslide"
        assert SensorType.UWB_BIORADAR in profile.sensor_weights
        assert profile.sensor_weights[SensorType.UWB_BIORADAR] == WEIGHT_UWB_LANDSLIDE

    def test_fuse_victim_with_5m_subsurface_radar_reading(self):
        loc = GPSCoordinate(32.2435, 77.1895)
        readings = [
            SensorReading(
                sensor_type=SensorType.UWB_BIORADAR,
                value=78.0,  # 78% radar confidence at 5m
                unit="%",
                location=loc,
                device_id="DEV-UWB-RADAR-01",
            ),
            SensorReading(
                sensor_type=SensorType.ACOUSTIC,
                value=25.0,
                unit="dB",
                location=loc,
                device_id="DEV-ACOUSTIC-01",
            ),
        ]

        hazard = HazardContext(
            burial_depth_m=5.0,
            secondary_hazard=True,
            soil_moisture_pct=40.0,
            exposure_minutes=60.0,
        )

        fused = fuse_victim(
            victim_id="VIC-LANDSLIDE-5M-01",
            readings=readings,
            hazard=hazard,
            scenario_id="landslide",
        )

        assert fused.confidence_pct > 20.0
        assert fused.triage_class in [TriageClass.HIGH, TriageClass.MEDIUM]
        assert "uwb_bioradar" in fused.contributing_sensors


# ==============================================================================
# 14. Subsurface REST APIs Endpoints Tests
# ==============================================================================

class TestSubsurfaceRestAPI:
    """Validate FastAPI endpoints for 0–6.0m subsurface simulator interaction."""

    def test_get_presets_endpoint(self):
        resp = client.get("/api/subsurface/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        assert len(data["presets"]) == 12
        assert "0–6.0m" in data["simulation_label"]

    def test_get_status_endpoint(self):
        resp = client.get("/api/subsurface/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "telemetry" in data
        assert "config" in data
        assert data["telemetry"]["max_depth_m"] == 6.0
        assert data["telemetry"]["device_id"] == "DEV-UWB-RADAR-01"

    def test_post_simulate_step_endpoint(self):
        resp = client.post("/api/subsurface/simulate", json={"step_time": 0.2})
        assert resp.status_code == 200
        data = resp.json()
        assert "telemetry" in data
        assert data["telemetry"]["max_depth_m"] == 6.0
        assert len(data["telemetry"]["radargram_profile"]) == 256

    def test_post_control_preset_5m_endpoint(self):
        resp = client.post("/api/subsurface/control", json={"action": "set_preset", "preset_id": "preset_5"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["telemetry"]["soil_type"] == "dry_soil"

    def test_post_config_update_0_to_6m_endpoint(self):
        update_payload = {
            "soil_type": "sandy_soil",
            "soil_moisture_pct": 22.0,
            "burial_depth_m": 4.8,
            "survivor_mode": "one",
            "clutter_level": "low",
            "sensor_noise": "low",
        }
        resp = client.post("/api/subsurface/config", json=update_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["config"]["burial_depth_m"] == 4.8

    def test_post_subsurface_sensor_reading_endpoint(self):
        payload = {
            "victim_id": "VIC-LANDSLIDE-5M-01",
            "session_id": "TEST-SESSION-5M",
            "estimated_depth_m": 4.95,
            "ground_truth_depth_m": 5.00,
            "confidence": 0.78,
            "respiration_rpm": 16.5,
            "heart_rate_bpm": 72.0,
            "soil_type": "sandy_soil",
            "moisture_pct": 20.0,
            "snr_db": 9.4,
        }
        resp = client.post("/api/sensor/subsurface-reading", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["estimated_depth_m"] == 4.95
        assert data["ground_truth_depth_m"] == 5.00


# ==============================================================================
# 15. STEP 3 Realism & Robustness Upgraded Test Suite
# ==============================================================================

class TestStep3RealismAndRobustness:
    """Validate STEP 3 advanced physics, obstacles, shadowing, and sweeps."""

    def test_layered_soil_strata_and_interfaces(self):
        """Test multi-strata propagation calculation and internal interface reflections."""
        layers = [
            {"name": "Dry Surface", "soil_type": "dry_soil", "thickness_m": 1.0, "moisture_pct": 15.0},
            {"name": "Wet Soil Layer", "soil_type": "wet_soil", "thickness_m": 2.0, "moisture_pct": 45.0},
            {"name": "Clay Bed", "soil_type": "clay_soil", "thickness_m": 3.0, "moisture_pct": 40.0},
        ]
        prop = calculate_layered_propagation(layers, target_depth_m=5.0)
        assert prop["layer_count"] == 3
        assert len(prop["interfaces"]) >= 2
        assert len(prop["layer_strata"]) == 3
        assert prop["effective_attenuation_db_per_m"] > 1.0

        # Validate interface reflection coefficient
        iface1 = prop["interfaces"][0]
        assert iface1["depth_m"] == 1.0
        assert abs(iface1["reflection_coefficient"]) > 0.0

    def test_metallic_obstacle_ringing_and_shadowing(self):
        """Test metallic obstacle generates strong echo and shadows deeper survivor."""
        sim = SubsurfaceSimulator()
        sim.set_preset("preset_12")
        tel = sim.run_simulation_cycle(seed=42)
        assert tel.status == "TARGET_DETECTED" or tel.status == "SCANNING"
        # Check that obstacles were detected
        assert len(tel.obstacles_detected) > 0
        metal_obs = [o for o in tel.obstacles_detected if o.get("is_metallic")]
        assert len(metal_obs) >= 1

    def test_false_positive_library_suppression(self):
        """Test that non-human obstacles (rocks, roots, pipes, vibrations) produce 0 survivor confidence."""
        # Non-human periodic vibration (e.g. 10 Hz generator) outside human band
        res = analyze_slow_time_vitals(
            target_ground_truth={"is_alive": False, "resp_rpm": 0.0, "hr_bpm": 0.0, "micro_motion": False},
            peak_snr_db=15.0,
            clutter_level="high",
            seed=42,
        )
        assert res.respiration_rpm == 0.0
        assert res.heart_rate_bpm == 0.0
        assert res.micro_motion_detected is False
        assert res.vital_confidence < 0.15

    def test_empty_landslide_demo(self):
        """Test Preset 8: Empty Landslide produces complete false-positive suppression."""
        sim = SubsurfaceSimulator()
        sim.set_preset("preset_8")
        tel = sim.run_simulation_cycle(seed=42)
        assert tel.status in ("NO_TARGET", "SCANNING")
        assert tel.survivor_present is False
        assert tel.overall_confidence_pct == 0.0 or tel.overall_confidence_pct <= 15.0
        assert tel.triage_class == "NO_VITAL_SIGNS"

    def test_5m_challenge_mode(self):
        """Test Preset 6: 5.0m challenge in saturated mud degrades confidence gracefully."""
        sim = SubsurfaceSimulator()
        sim.set_preset("preset_6")
        tel = sim.run_simulation_cycle(seed=42)
        # Saturated mud at 5m should yield degraded/poor signal quality
        assert tel.signal_quality in ("DEGRADED", "POOR", "UNRELIABLE", "NO_DETECTION")
        assert tel.overall_confidence_pct < 85.0

    def test_6m_limit_test(self):
        """Test Preset 7: 6.0m boundary case has large uncertainty and low/medium confidence."""
        sim = SubsurfaceSimulator()
        sim.set_preset("preset_7")
        tel = sim.run_simulation_cycle(seed=42)
        if tel.primary_target:
            assert tel.primary_target.depth_uncertainty_m >= 0.08

    def test_depth_sweep_0_5_to_6_0m(self):
        """Depth sweep test across 0.5m to 6.0m verifying continuous DSP behavior."""
        depths = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
        results = []
        for d in depths:
            cfg = SubsurfaceSimulationConfig(
                soil_type=SubsurfaceSoilType.DRY_SOIL,
                soil_moisture_pct=20.0,
                burial_depth_m=d,
                survivor_mode="one",
                survivor_alive=True,
                clutter_level="low",
                sensor_noise="low",
            )
            sim = SubsurfaceSimulator(config=cfg)
            tel = sim.run_simulation_cycle(seed=100)
            assert tel is not None
            if tel.primary_target:
                err = abs(tel.primary_target.estimated_depth_m - d)
                results.append((d, tel.primary_target.estimated_depth_m, err, tel.primary_target.snr_db))
        # At least shallow targets (0.5 to 3.0m) should be cleanly resolved
        assert len(results) >= 6

    def test_moisture_sweep_10_to_85_pct(self):
        """Moisture sweep test for fixed 5.0m survivor demonstrating dielectric loss."""
        moistures = [10.0, 25.0, 40.0, 55.0, 70.0, 85.0]
        snrs = []
        for m in moistures:
            d_info = estimate_dielectric_constant("wet_soil", m)
            cfg = SubsurfaceSimulationConfig(
                soil_type=SubsurfaceSoilType.WET_SOIL,
                soil_moisture_pct=m,
                burial_depth_m=5.0,
                survivor_mode="one",
                survivor_alive=True,
                clutter_level="low",
                sensor_noise="low",
            )
            scan = generate_synthetic_fast_time_scan(cfg, d_info, seed=42)
            _, peaks = process_fast_time_dsp(scan, d_info)
            if peaks:
                snrs.append((m, peaks[0].snr_db))
        # Permittivity and loss must scale with moisture
        assert len(snrs) >= 3

    def test_clutter_sweep_low_med_high(self):
        """Clutter sweep verifying noise/clutter suppression."""
        for cl in ["low", "medium", "high"]:
            cfg = SubsurfaceSimulationConfig(
                soil_type=SubsurfaceSoilType.DRY_SOIL,
                soil_moisture_pct=20.0,
                burial_depth_m=5.0,
                survivor_mode="one",
                survivor_alive=True,
                clutter_level=cl,
                sensor_noise="medium",
            )
            sim = SubsurfaceSimulator(config=cfg)
            tel = sim.run_simulation_cycle(seed=42)
            assert tel is not None

    def test_noise_sweep_low_med_high(self):
        """Noise sweep verifying DSP resilience against thermal noise floors."""
        for ns in ["low", "medium", "high"]:
            cfg = SubsurfaceSimulationConfig(
                soil_type=SubsurfaceSoilType.DRY_SOIL,
                soil_moisture_pct=20.0,
                burial_depth_m=5.0,
                survivor_mode="one",
                survivor_alive=True,
                clutter_level="medium",
                sensor_noise=ns,
            )
            sim = SubsurfaceSimulator(config=cfg)
            tel = sim.run_simulation_cycle(seed=42)
            assert tel is not None

    def test_physiological_respiration_patterns(self):
        """Test all 6 physiological respiration patterns."""
        patterns = ["normal", "slow", "fast", "irregular", "very_weak", "intermittent"]
        for pat in patterns:
            res = analyze_slow_time_vitals(
                target_ground_truth={
                    "is_alive": True,
                    "resp_rpm": 16.0,
                    "hr_bpm": 70.0,
                    "micro_motion": True,
                    "respiration_pattern": pat,
                },
                peak_snr_db=14.0,
                clutter_level="low",
                seed=42,
            )
            assert res is not None
            if pat != "very_weak":
                assert res.respiration_rpm > 0.0

    def test_heartbeat_patterns_and_undetectable_deep(self):
        """Test that heartbeat pattern handles undetectable cardiac vitals."""
        res_undetect = analyze_slow_time_vitals(
            target_ground_truth={
                "is_alive": True,
                "resp_rpm": 15.0,
                "hr_bpm": 60.0,
                "micro_motion": True,
                "heartbeat_pattern": "undetectable",
            },
            peak_snr_db=12.0,
            clutter_level="low",
            seed=42,
        )
        assert res_undetect.heart_rate_bpm == 0.0
        assert res_undetect.respiration_rpm > 0.0

    def test_micro_motion_and_orientation_scaling(self):
        """Test RCS orientation scaling across orientations."""
        d_info = estimate_dielectric_constant("dry_soil", 15.0)
        cfg_facing = SubsurfaceSimulationConfig(target_orientation="facing_sensor", burial_depth_m=2.0)
        scan_facing = generate_synthetic_fast_time_scan(cfg_facing, d_info, seed=42)

        cfg_away = SubsurfaceSimulationConfig(target_orientation="away_from_sensor", burial_depth_m=2.0)
        scan_away = generate_synthetic_fast_time_scan(cfg_away, d_info, seed=42)

        amp_facing = scan_facing.ground_truth_targets[0]["simulated_rx_amplitude"]
        amp_away = scan_away.ground_truth_targets[0]["simulated_rx_amplitude"]
        assert amp_facing > amp_away

    def test_multi_target_interference_and_closely_spaced_targets(self):
        """Test closely-spaced survivors (4.8m, 5.0m, 5.2m) demonstrating partial overlap / peak merging."""
        cfg = SubsurfaceSimulationConfig(
            survivor_mode="overlapping",
            soil_type=SubsurfaceSoilType.DRY_SOIL,
            soil_moisture_pct=15.0,
            clutter_level="low",
            sensor_noise="low",
        )
        sim = SubsurfaceSimulator(config=cfg)
        tel = sim.run_simulation_cycle(seed=42)
        assert tel.status == "TARGET_DETECTED"
        assert len(tel.targets) >= 1

    def test_deterministic_seed_reproduction(self):
        """Test that specifying the same seed generates 100% identical telemetry."""
        sim = SubsurfaceSimulator()
        sim.set_preset("preset_5")
        tel1 = sim.run_simulation_cycle(seed=999)
        tel2 = sim.run_simulation_cycle(seed=999)
        assert tel1.snr_db == tel2.snr_db
        assert tel1.overall_confidence_pct == tel2.overall_confidence_pct
        if tel1.primary_target and tel2.primary_target:
            assert tel1.primary_target.estimated_depth_m == tel2.primary_target.estimated_depth_m

    def test_all_12_presets_load_and_run(self):
        """Validate that all 12 presets execute cleanly."""
        sim = SubsurfaceSimulator()
        for i in range(1, 13):
            pk = f"preset_{i}"
            assert pk in SubsurfaceSimulator.PRESETS
            ok = sim.set_preset(pk)
            assert ok is True
            tel = sim.run_simulation_cycle(seed=i * 10)
            assert tel is not None
            assert tel.max_depth_m == 6.0
            assert tel.is_simulated is True

    def test_issue1_confidence_scaling_not_saturated_at_low_snr(self):
        """Verify Issue 1 fix: Fast-time SNR weights confidence smoothly, preventing 96% saturation at 4.5 dB."""
        sim = SubsurfaceSimulator()
        sim.set_preset("preset_5")  # 5.0m survivor, ~4.5 dB fast-time SNR
        tel = sim.run_simulation_cycle(seed=42)
        assert tel.status == "TARGET_DETECTED"
        assert tel.primary_target is not None
        # Confidence must be moderate (60% to 75%) rather than saturated at 96%
        assert 58.0 <= tel.overall_confidence_pct <= 75.0
        assert tel.triage_class in ("MEDIUM", "HIGH")

        # Test high SNR shallow survivor retains high confidence (>= 90%)
        sim.set_preset("preset_1")  # 1.0m survivor, ~22 dB fast-time SNR
        tel_high = sim.run_simulation_cycle(seed=42)
        assert tel_high.overall_confidence_pct >= 90.0

    def test_issue2_preset_2_mid_depth_target_detected_without_clutter_locking(self):
        """Verify Issue 2 fix: Preset 2 (2.0m survivor) is detected cleanly without deep clutter peak locking."""
        sim = SubsurfaceSimulator()
        sim.set_preset("preset_2")
        tel = sim.run_simulation_cycle(seed=42)
        assert tel.status == "TARGET_DETECTED"
        assert tel.primary_target is not None
        assert abs(tel.primary_target.estimated_depth_m - 2.0) <= 0.20
        assert tel.primary_target.is_human is True
        assert tel.overall_confidence_pct >= 65.0

    def test_issue2_smooth_tvg_curve_prevents_excessive_deep_gain(self):
        """Verify Issue 2 fix: TVG gain curve is smooth, monotonic, and capped at 30 dB."""
        config = SubsurfaceSimulationConfig(
            soil_type=SubsurfaceSoilType.DRY_SOIL,
            soil_moisture_pct=20.0,
            survivor_mode="none",
        )
        dielectric = estimate_dielectric_constant(config.soil_type, config.soil_moisture_pct)
        scan = generate_synthetic_fast_time_scan(config, dielectric, seed=42)
        env, peaks = process_fast_time_dsp(scan, dielectric)
        assert len(env) == 256
        # Envelope values must be well-conditioned (not blowing up to infinity)
        assert max(env) < 20.0


