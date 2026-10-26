"""
Final Validation Scenarios Execution Script (Tests A through J).
Runs the exact 10 scenarios requested in Section 36.
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))

from backend.models import (
    SubsurfaceSimulationConfig,
    SubsurfaceSoilType,
)
from backend.subsurface_dsp import (
    estimate_dielectric_constant,
    generate_synthetic_fast_time_scan,
    process_fast_time_dsp,
    analyze_slow_time_vitals,
    SubsurfaceSimulator,
)

def run_scenarios():
    scenarios = [
        ("TEST A", "Dry soil — 1 m survivor", SubsurfaceSoilType.DRY_SOIL, 15.0, 1.0, "one", True, 18.0, 75.0, "low", "low"),
        ("TEST B", "Moist soil — 2 m survivor", SubsurfaceSoilType.SANDY_SOIL, 25.0, 2.0, "one", True, 16.0, 72.0, "medium", "low"),
        ("TEST C", "Clay — 3 m survivor", SubsurfaceSoilType.CLAY_SOIL, 35.0, 3.0, "one", True, 15.0, 68.0, "medium", "low"),
        ("TEST D", "Wet soil — 4 m survivor", SubsurfaceSoilType.WET_SOIL, 50.0, 4.0, "one", True, 14.0, 65.0, "medium", "medium"),
        ("TEST E", "Normal soil — 5 m survivor (Primary Target)", SubsurfaceSoilType.DRY_SOIL, 22.0, 5.0, "one", True, 16.0, 72.0, "medium", "low"),
        ("TEST F", "Saturated mud — 5 m survivor (Extreme loss)", SubsurfaceSoilType.SATURATED_MUD, 85.0, 5.0, "one", True, 12.0, 50.0, "high", "high"),
        ("TEST G", "Clutter-heavy — 5 m survivor", SubsurfaceSoilType.MIXED_DEBRIS_SOIL, 30.0, 5.0, "one", True, 14.0, 66.0, "high", "medium"),
        ("TEST H", "6 m boundary test", SubsurfaceSoilType.DRY_SOIL, 15.0, 5.8, "one", True, 12.0, 54.0, "low", "low"),
        ("TEST I", "Empty landslide (No survivor)", SubsurfaceSoilType.DRY_SOIL, 20.0, 0.0, "none", False, 0.0, 0.0, "medium", "low"),
        ("TEST J", "Three survivors: 1 m, 3 m, 5 m", SubsurfaceSoilType.SANDY_SOIL, 18.0, 0.0, "multiple", True, 16.0, 70.0, "low", "low"),
    ]

    sim = SubsurfaceSimulator()

    results = []
    print("=" * 80)
    print("RIDGEWATCH 0-6.0m SUBSURFACE SIMULATOR: FINAL VALIDATION SCENARIOS (TESTS A-J)")
    print("=" * 80)

    for test_id, name, soil, moisture, depth, mode, alive, rpm, bpm, clutter, noise in scenarios:
        sim.config = SubsurfaceSimulationConfig(
            soil_type=soil,
            soil_moisture_pct=moisture,
            burial_depth_m=depth,
            survivor_mode=mode,
            survivor_alive=alive,
            breathing_rate_rpm=rpm,
            heart_rate_bpm=bpm,
            clutter_level=clutter,
            sensor_noise=noise,
        )
        sim.cycle_count = 1
        telem = sim.run_simulation_cycle(seed=42)

        if mode == "multiple":
            # Multi-target report
            print(f"\n--- {test_id}: {name} ---")
            print(f"Overall Status: {telem.status} | Targets Detected: {len(telem.targets)} | Soil: {telem.soil_type} ({telem.soil_moisture_pct}%)")
            for idx, t in enumerate(telem.targets):
                err = abs(t.estimated_depth_m - t.ground_truth_depth_m) if t.ground_truth_depth_m > 0 else 0.0
                rel_err = (err / t.ground_truth_depth_m * 100.0) if t.ground_truth_depth_m > 0 else 0.0
                print(f"  Target #{idx+1} ({t.target_id}): True={t.ground_truth_depth_m:.2f}m | Est={t.estimated_depth_m:.2f}m ± {t.depth_uncertainty_m:.2f}m | AbsErr={err:.3f}m ({rel_err:.1f}%) | SNR={t.snr_db:.1f}dB | Resp={'DETECTED (' + str(round(t.respiration_rate_rpm, 1)) + ' RPM)' if t.respiration_rate_rpm > 0 else 'NONE'} | MicroMotion={'DETECTED' if t.micro_motion_detected else 'NONE'} | Conf={t.survivor_confidence*100:.1f}% | Triage={t.triage_class}")
        elif mode == "none" or not alive:
            print(f"\n--- {test_id}: {name} ---")
            print(f"Status: {telem.status} | True Depth: N/A | Est Depth: N/A | Confidence: {telem.overall_confidence_pct:.1f}% | Triage: {telem.triage_class} | Detected Targets: {len(telem.targets)}")
        else:
            pt = telem.primary_target
            if pt:
                err = abs(pt.estimated_depth_m - depth)
                rel_err = (err / depth * 100.0) if depth > 0 else 0.0
                resp_str = f"DETECTED ({pt.respiration_rate_rpm:.1f} RPM)" if pt.respiration_rate_rpm > 0 else "NOT DETECTED"
                motion_str = "DETECTED" if pt.micro_motion_detected else "NOT DETECTED"
                print(f"\n--- {test_id}: {name} ---")
                print(f"Status: {telem.status} | Soil: {telem.soil_type} ({telem.soil_moisture_pct}% moist)")
                print(f"  True Depth: {depth:.2f} m")
                print(f"  Estimated Depth: {pt.estimated_depth_m:.2f} m")
                print(f"  Absolute Error: {err:.3f} m (Relative Error: {rel_err:.1f}%)")
                print(f"  Uncertainty: ±{pt.depth_uncertainty_m:.2f} m")
                print(f"  SNR: {pt.snr_db:.2f} dB")
                print(f"  Respiration: {resp_str}")
                print(f"  Micro-Motion: {motion_str}")
                print(f"  Confidence: {telem.overall_confidence_pct:.1f}%")
                print(f"  Triage: {telem.triage_class} (SPS: {telem.sps_score:.1f})")
            else:
                print(f"\n--- {test_id}: {name} ---")
                print(f"Status: {telem.status} | No primary target detected | Confidence: {telem.overall_confidence_pct:.1f}% | Triage: {telem.triage_class}")

if __name__ == "__main__":
    run_scenarios()
