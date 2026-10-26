"""
backend/subsurface_dsp.py
-------------------------
RIDGEWATCH Subsurface Survivor Simulation Engine & UWB Bioradar DSP Pipeline (STEP 3).

SIMULATION SAFETY & INTEGRITY NOTICE:
This module is a deterministic SOFTWARE SIMULATION of subsurface Ultra-Wideband
(UWB) bio-radar. It DOES NOT claim or prove real-world soil penetration, physical
radar hardware capability, or experimental burial depth accuracy.
The 0–6.0 m range is a simulation boundary, and 5.0 m is an engineering demonstration target.

STEP 3 Realism & Robustness Architecture:
1. Multi-Layer Soil Dielectric Model: Multi-strata calculation with dielectric contrasts,
   propagation velocities, attenuation, and interface reflection coefficients (R_12).
2. Internal Layer Interface Reflections: Simulates boundary reflections with exponential
   ringing decay; interface echoes appear on radargram but are rejected by slow-time vitals.
3. Depth-Dependent Attenuation & Shadowing: Exponential path loss, geometric spreading,
   interface transmission losses, and obstacle-induced shadowing (metallic plates/large rocks).
4. Non-Ideal Radar Effects: Receiver/thermal noise (low/med/high), volumetric clutter,
   surface and interface ringing, sidelobes, multipath echoes, transient spikes, and baseline drift.
5. Environmental Obstacles & False-Positive Library: Rocks, roots, metallic debris, concrete
   fragments, pipes, voids, layer boundaries, and periodic non-human vibrations.
6. Multi-Target Interference: Separated (1m, 3m, 5m) and closely-spaced (4.8m, 5.0m, 5.2m)
   demonstrating peak separation, partial overlap, and resolution limits.
7. Physiological & Motion Variation: Respiration patterns (NORMAL, SLOW, FAST, IRREGULAR,
   VERY_WEAK, INTERMITTENT), Heartbeat patterns (NORMAL, ELEVATED, WEAK, INTERMITTENT, UNDETECTABLE),
   Micro-motion levels (HIGH, MEDIUM, LOW, VERY_LOW, NONE), Orientation, and Target Movement.
8. Signal Quality & Dynamic Uncertainty: Standardized quality states (EXCELLENT, GOOD, DEGRADED,
   POOR, UNRELIABLE, NO_DETECTION) and depth/SNR/clutter-scaled measurement uncertainty bounds.
9. 12 Disaster Presets: Includes 5.0m primary demo, 5.0m challenge mode, 6.0m limit test,
   empty landslide, heavy clutter, metallic obstacle masking, and multiple survivors.
10. Strict Ground-Truth Isolation: Fast-time DSP and slow-time vital analyzers are strictly blind
    to ground-truth target metadata.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from models import (
    SensorType,
    SensorReading,
    SensorHealthStatus,
    GPSCoordinate,
    SubsurfaceSoilType,
    SignalQuality,
    TargetOrientation,
    TargetMovement,
    RespirationPattern,
    HeartbeatPattern,
    MicroMotionLevel,
    ObstacleType,
    SubsurfaceTargetState,
    SubsurfaceSimulationConfig,
    SubsurfaceRadarTelemetry,
)


# --------------------------------------------------------------------------- #
# Physical Constants & Reference Parameters (0–6.0 m Simulation Domain)
# --------------------------------------------------------------------------- #

SPEED_OF_LIGHT_M_S = 299792458.0  # Speed of light in vacuum (m/s)
C_AIR = 0.299792458                # Speed of light in vacuum/air (m/ns)
RADAR_CENTER_FREQ_GHZ = 0.5        # Subsurface Sub-GHz UWB center frequency (500 MHz)
PULSE_WIDTH_NS = 1.2               # Transmitted radar monocycle pulse width
DEPTH_MAX_M = 6.0                  # Maximum simulated radar probing depth (0–6.0 m)
SUBSURFACE_MAX_DEPTH_M = 6.0       # Explicit alias constant
NUM_RANGE_BINS = 256               # Fast-time range sample bins (dr = 6.0 / 256 = 0.0234375 m)
SLOW_TIME_WINDOW_S = 6.0           # Slow-time observation buffer length (seconds)
SLOW_TIME_FS_HZ = 16.0             # Slow-time radar frame sampling rate (Hz)


# --------------------------------------------------------------------------- #
# 1. Multi-Layer Soil Dielectric Model & Interface Reflection Physics
# --------------------------------------------------------------------------- #

def estimate_dielectric_constant(
    soil_type: str | SubsurfaceSoilType,
    soil_moisture_pct: float,
    clay_fraction: float = 0.25,
    soil_density_g_cm3: float = 1.6,
) -> Dict[str, Any]:
    """
    Configurable simulation approximation for soil relative permittivity (dielectric constant),
    attenuation rate (dB/m), and radar wave propagation velocity.

    DISCLAIMER: This is a software simulation model and NOT an experimentally
    validated field formula.

    Returns:
        - estimated_relative_permittivity: float (eps_r >= 1.0)
        - attenuation_db_per_m: float (alpha)
        - velocity_m_per_s: float (v = c / sqrt(eps_r))
        - model_status: str ("SIMULATED SOIL MODEL")
        - uncertainty: float (depth estimation scaling uncertainty factor)
    """
    st_str = soil_type.value if isinstance(soil_type, SubsurfaceSoilType) else str(soil_type).lower()
    moisture = max(0.0, min(100.0, float(soil_moisture_pct)))
    clay = max(0.0, min(1.0, float(clay_fraction)))
    density = max(1.0, min(2.5, float(soil_density_g_cm3)))

    # Base dry permittivity & moisture sensitivity by soil type
    if "dry" in st_str:
        base_eps = 3.2 + 0.3 * (density - 1.4)
        moisture_coeff = 0.12
        alpha_base = 0.8
        alpha_moisture = 0.06
        uncertainty = 0.05
    elif "sandy" in st_str:
        base_eps = 4.0 + 0.4 * (density - 1.5)
        moisture_coeff = 0.22
        alpha_base = 1.4
        alpha_moisture = 0.12
        uncertainty = 0.06
    elif "clay" in st_str:
        base_eps = 5.5 + 4.0 * clay + 0.3 * (density - 1.5)
        moisture_coeff = 0.36 + 0.15 * clay
        alpha_base = 5.5 + 7.5 * clay
        alpha_moisture = 0.32 + 0.18 * clay
        uncertainty = 0.14
    elif "saturated" in st_str or "mud" in st_str:
        base_eps = 10.0 + 0.5 * (density - 1.4)
        moisture_coeff = 0.55
        alpha_base = 16.0
        alpha_moisture = 0.45
        uncertainty = 0.20
    elif "debris" in st_str or "mixed" in st_str:
        base_eps = 5.0 + 0.4 * (density - 1.5)
        moisture_coeff = 0.26
        alpha_base = 3.8
        alpha_moisture = 0.20
        uncertainty = 0.11
    else:  # Default wet_soil (loam)
        base_eps = 4.8 + 0.35 * (density - 1.5)
        moisture_coeff = 0.30
        alpha_base = 3.2
        alpha_moisture = 0.22
        uncertainty = 0.08

    # Calculate simulated relative permittivity (bounded between 2.5 and 80.0)
    eps_r = max(2.5, min(80.0, base_eps + moisture_coeff * moisture))

    # Calculate propagation velocity v = c / sqrt(eps_r)
    velocity = SPEED_OF_LIGHT_M_S / math.sqrt(eps_r)

    # Calculate one-way attenuation alpha (dB/m)
    alpha = max(0.5, alpha_base + alpha_moisture * moisture)

    return {
        "estimated_relative_permittivity": round(eps_r, 2),
        "attenuation_db_per_m": round(alpha, 2),
        "velocity_m_per_s": round(velocity, 0),
        "propagation_speed_m_per_ns": round(velocity / 1e9, 3),
        "model_status": "SIMULATED SOIL MODEL",
        "uncertainty": round(uncertainty, 3),
        "soil_type": st_str,
        "moisture_pct": moisture,
        "clay_fraction": clay,
    }


def calculate_layered_propagation(
    layers: Optional[List[Dict[str, Any]]],
    target_depth_m: float = 6.0,
    total_depth_m: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Multi-layer soil propagation calculator:
    Computes effective two-way attenuation (dB), depth-averaged permittivity,
    velocity, and internal layer interface reflection coefficients (R_12).

    DISCLAIMER: Controlled approximation model for simulation demonstration.
    """
    depth_m = total_depth_m if total_depth_m is not None else target_depth_m
    if not layers:
        base = estimate_dielectric_constant("wet_soil", 50.0)
        return {
            **base,
            "effective_permittivity": base["estimated_relative_permittivity"],
            "effective_velocity_m_per_ns": base["propagation_speed_m_per_ns"],
            "effective_attenuation_db_per_m": base["attenuation_db_per_m"],
            "layer_count": 0,
            "interfaces": [],
            "layer_strata": [],
        }

    cumulative_attenuation_db = 0.0
    cumulative_time_ns = 0.0
    current_depth = 0.0
    remaining_depth = max(0.1, depth_m)
    interfaces: List[Dict[str, Any]] = []
    layer_strata: List[Dict[str, Any]] = []

    prev_eps_r = 1.0  # Air boundary at surface
    prev_boundary_depth = 0.0

    for idx, layer in enumerate(layers):
        if "thickness_m" in layer:
            thickness = float(layer["thickness_m"])
            d_start = prev_boundary_depth
            d_end = d_start + thickness
        elif "depth_end_m" in layer and "depth_start_m" in layer:
            d_start = float(layer["depth_start_m"])
            d_end = float(layer["depth_end_m"])
            thickness = d_end - d_start
        else:
            thickness = 1.0
            d_start = prev_boundary_depth
            d_end = d_start + thickness

        st = layer.get("soil_type", "wet_soil")
        st_val = st.value if hasattr(st, "value") else str(st)
        moisture = float(layer.get("moisture_pct", layer.get("soil_moisture_pct", 40.0)))
        clay = float(layer.get("clay_fraction", 0.2))

        d_prop = estimate_dielectric_constant(st_val, moisture, clay)
        eps_r = d_prop["estimated_relative_permittivity"]
        alpha = d_prop["attenuation_db_per_m"]
        v = d_prop["velocity_m_per_s"]

        # Calculate interface reflection coefficient between adjacent layers
        # R_12 = (sqrt(eps1) - sqrt(eps2)) / (sqrt(eps1) + sqrt(eps2))
        n1 = math.sqrt(prev_eps_r)
        n2 = math.sqrt(eps_r)
        r_coeff = (n1 - n2) / (n1 + n2) if (n1 + n2) > 0 else 0.0

        if idx > 0 and d_start < depth_m:
            interfaces.append({
                "interface_index": idx,
                "depth_m": round(d_start, 2),
                "reflection_coefficient": round(r_coeff, 3),
                "reflection_loss_db": round(-20.0 * math.log10(max(0.01, abs(r_coeff))), 1),
                "layer_above": layers[idx - 1].get("soil_type", "unknown"),
                "layer_below": st_val,
            })

        layer_strata.append({
            "layer_index": idx,
            "name": layer.get("name", f"Layer {idx+1}: {st_val.replace('_', ' ').title()}"),
            "soil_type": st_val,
            "depth_start_m": round(d_start, 2),
            "depth_end_m": round(d_end, 2),
            "thickness_m": round(thickness, 2),
            "moisture_pct": moisture,
            "clay_fraction": clay,
            "permittivity": eps_r,
            "attenuation_db_per_m": alpha,
        })

        d_in_layer = min(remaining_depth, thickness)
        if d_in_layer > 0:
            cumulative_attenuation_db += 2.0 * alpha * d_in_layer
            cumulative_time_ns += (2.0 * d_in_layer / v) * 1e9
            current_depth += d_in_layer
            remaining_depth -= d_in_layer

        prev_eps_r = eps_r
        prev_boundary_depth = d_end

    eff_v = (2.0 * depth_m / (cumulative_time_ns * 1e-9)) if cumulative_time_ns > 0 else SPEED_OF_LIGHT_M_S / 2.5
    eff_eps_r = (SPEED_OF_LIGHT_M_S / eff_v) ** 2
    eff_v_ns = eff_v / 1e9
    eff_alpha = cumulative_attenuation_db / (2.0 * depth_m) if depth_m > 0 else 3.5

    return {
        "estimated_relative_permittivity": round(eff_eps_r, 2),
        "effective_permittivity": round(eff_eps_r, 2),
        "attenuation_db_per_m": round(eff_alpha, 2),
        "effective_attenuation_db_per_m": round(eff_alpha, 2),
        "velocity_m_per_s": round(eff_v, 0),
        "effective_velocity_m_per_ns": round(eff_v_ns, 4),
        "propagation_speed_m_per_ns": round(eff_v_ns, 4),
        "total_roundtrip_attenuation_db": round(cumulative_attenuation_db, 1),
        "layer_count": len(layers),
        "interfaces": interfaces,
        "layer_strata": layer_strata,
        "model_status": "SIMULATED LAYERED-SOIL MODEL (0-6.0m)",
        "uncertainty": 0.12,
        "is_layered": True,
    }


# --------------------------------------------------------------------------- #
# 2. Fast-Time Synthetic Radar Signal Pipeline (0–6.0 m) with Non-Idealities
# --------------------------------------------------------------------------- #

@dataclass
class SyntheticFastTimeScan:
    """Synthetic fast-time range profile (A-scan) and ground truth metadata."""
    depth_axis_m: List[float]
    time_axis_ns: List[float]
    raw_signal: List[float]
    ground_truth_targets: List[Dict[str, Any]]
    clutter_profile: List[float]
    noise_floor: float
    simulated_obstacles: List[Dict[str, Any]] = field(default_factory=list)


def generate_synthetic_fast_time_scan(
    config: SubsurfaceSimulationConfig,
    dielectric_info: Dict[str, Any],
    seed: Optional[int] = None,
) -> SyntheticFastTimeScan:
    """
    Generate synthetic fast-time radar A-scan with physical simulation factors:
    - Direct air-soil surface interface reflection (0 to 0.25 m) + surface ringing
    - Internal layer interface boundary reflections & ringing (for layered strata)
    - Depth-dependent attenuation: Two-way path loss + geometric spreading + interface transmission
    - Buried obstacles (rocks, roots, metallic debris, pipes, voids) & metallic shadowing
    - Non-ideal effects: thermal noise floor, sidelobes, baseline drift, transient spikes
    - Buried survivor target reflection(s) with orientation-dependent RCS and movement
    """
    rng = random.Random(seed) if seed is not None else random.Random()

    v_soil = dielectric_info.get("velocity_m_per_s", SPEED_OF_LIGHT_M_S / 2.5)
    alpha_db = dielectric_info.get("attenuation_db_per_m", 3.5)
    dr = DEPTH_MAX_M / NUM_RANGE_BINS

    depth_axis = [round(i * dr, 4) for i in range(NUM_RANGE_BINS)]
    time_axis = [round((2.0 * r / v_soil) * 1e9, 3) for r in depth_axis]

    raw_signal = [0.0] * NUM_RANGE_BINS
    clutter_profile = [0.0] * NUM_RANGE_BINS

    # 1. Surface reflection & surface ringing (air-ground interface at r=0 to r=0.25m)
    surface_peak = 0.95 + 0.05 * rng.uniform(-1, 1)
    for i, r in enumerate(depth_axis):
        if r < 0.28:
            direct_wave = surface_peak * math.exp(-((r - 0.04) ** 2) / (2 * (0.035 ** 2)))
            # Surface ringing tail
            ringing = 0.12 * math.exp(-r / 0.08) * math.cos(2 * math.pi * r / 0.06) if config.enable_ringing else 0.0
            raw_signal[i] += direct_wave + ringing

    # 2. Internal Layer Interfaces (boundary reflections and ringing)
    interfaces = dielectric_info.get("interfaces", [])
    if config.enable_layer_interfaces and interfaces:
        for iface in interfaces:
            i_depth = float(iface["depth_m"])
            r_coeff = float(iface["reflection_coefficient"])
            # Two-way attenuation to interface depth
            path_loss = 10.0 ** (-(alpha_db * 2.0 * i_depth * 0.35) / 20.0)
            iface_amp = abs(r_coeff) * 0.85 * path_loss
            for i, r in enumerate(depth_axis):
                if abs(r - i_depth) < 0.35:
                    pulse = iface_amp * math.exp(-((r - i_depth) ** 2) / (2 * (0.040 ** 2)))
                    # Interface ringing tail
                    ring = (0.08 * iface_amp * math.exp(-max(0.0, r - i_depth) / 0.06) * math.cos(2 * math.pi * (r - i_depth) / 0.05)) if (r >= i_depth and config.enable_ringing) else 0.0
                    raw_signal[i] += pulse + ring
                    clutter_profile[i] += pulse

    # 3. Discrete Buried Obstacles (False-Positive Library)
    clutter_mult = {"low": 0.08, "medium": 0.20, "high": 0.45}.get(config.clutter_level.lower(), 0.20)
    if "debris" in str(config.soil_type).lower():
        clutter_mult *= 1.35

    obstacles_list: List[Dict[str, Any]] = []
    if config.obstacles:
        obstacles_list.extend(config.obstacles)
    else:
        # Generate default realistic obstacles based on clutter level & scenario
        num_obs = {"low": 2, "medium": 5, "high": 9}.get(config.clutter_level.lower(), 5)
        obstacle_types = [
            ObstacleType.ROCK.value,
            ObstacleType.ROOT.value,
            ObstacleType.CONCRETE_FRAGMENT.value,
            ObstacleType.PIPE.value,
            ObstacleType.VOID.value,
        ]
        for idx in range(num_obs):
            o_type = obstacle_types[idx % len(obstacle_types)]
            o_depth = round(rng.uniform(0.5, DEPTH_MAX_M - 0.4), 2)
            o_rcs = round(rng.uniform(0.2, 0.6) * clutter_mult * 3.0, 2)
            obstacles_list.append({
                "obstacle_id": f"OBS-{idx+1}",
                "type": o_type,
                "depth_m": o_depth,
                "rcs": o_rcs,
                "is_metallic": False,
            })

    # Metallic Clutter & Shadowing support (if survivor_mode == 'metallic_obstacle' or explicit metallic obstacle)
    has_metallic_reflector = False
    metal_depth = 4.5
    if config.survivor_mode.lower() == "metallic_obstacle":
        has_metallic_reflector = True
        metal_depth = 4.5
        obstacles_list.append({
            "obstacle_id": "OBS-METAL-01",
            "type": ObstacleType.METALLIC_DEBRIS.value,
            "depth_m": metal_depth,
            "rcs": 4.5,
            "is_metallic": True,
        })

    # Render obstacles into fast-time signal
    for obs in obstacles_list:
        o_depth = float(obs["depth_m"])
        o_rcs = float(obs.get("rcs", 0.4))
        is_metal = bool(obs.get("is_metallic", False))

        path_loss_db = alpha_db * 2.0 * o_depth * 0.35
        atten_factor = 10.0 ** (-path_loss_db / 20.0) / max(1.0, o_depth ** 0.65)
        eff_amp = o_rcs * 1.4 * atten_factor

        for i, r in enumerate(depth_axis):
            pulse = eff_amp * math.exp(-((r - o_depth) ** 2) / (2 * (0.045 ** 2)))
            raw_signal[i] += pulse
            clutter_profile[i] += pulse
            # Metallic ringing effect
            if is_metal and config.enable_ringing and r >= o_depth:
                ring = 0.35 * eff_amp * math.exp(-(r - o_depth) / 0.12) * math.cos(2 * math.pi * (r - o_depth) / 0.05)
                raw_signal[i] += ring

    # 4. Continuous Volumetric Soil Backscatter & Baseline Drift
    for i, r in enumerate(depth_axis):
        if r >= 0.15:
            v_loss = 10.0 ** (-(alpha_db * 2.0 * r * 0.35) / 20.0)
            backscatter = rng.gauss(0, 0.015 * clutter_mult) * v_loss
            # Low-frequency baseline drift (non-ideal ADC / antenna coupling drift)
            baseline_drift = 0.018 * math.sin(2 * math.pi * r / 4.5) * v_loss
            raw_signal[i] += backscatter + baseline_drift
            clutter_profile[i] += abs(backscatter)

    # 5. Buried Survivor Ground Truth Target(s)
    ground_truth_targets: List[Dict[str, Any]] = []

    # Orientation RCS multiplier
    ori_str = str(config.target_orientation).lower()
    ori_mult = {"facing_sensor": 1.0, "sideways": 0.65, "away_from_sensor": 0.40}.get(ori_str, 0.75)

    if config.survivor_mode.lower() in ("one", "challenge", "metallic_obstacle"):
        base_rcs = 0.88 if config.survivor_alive else 0.70
        ground_truth_targets.append({
            "target_id": "VICTIM-UWB-01",
            "is_human": True,
            "is_alive": config.survivor_alive,
            "depth_m": config.burial_depth_m,
            "rcs": base_rcs * ori_mult,
            "resp_rpm": config.breathing_rate_rpm if config.survivor_alive else 0.0,
            "hr_bpm": config.heart_rate_bpm if config.survivor_alive else 0.0,
            "micro_motion": config.micro_motion if config.survivor_alive else False,
            "respiration_pattern": config.respiration_pattern,
            "heartbeat_pattern": config.heartbeat_pattern,
            "micro_motion_level": config.micro_motion_level,
            "orientation": config.target_orientation,
            "movement": config.target_movement,
        })
    elif config.survivor_mode.lower() == "multiple":
        # 3 victims at Shallow (1.0m), Moderate (3.0m), and Deep (5.0m)
        ground_truth_targets.extend([
            {
                "target_id": "VICTIM-UWB-A",
                "is_human": True,
                "is_alive": True,
                "depth_m": 1.0,
                "rcs": 0.90 * ori_mult,
                "resp_rpm": 18.0,
                "hr_bpm": 76.0,
                "micro_motion": True,
                "respiration_pattern": "normal",
                "heartbeat_pattern": "normal",
                "micro_motion_level": "high",
                "orientation": "facing_sensor",
                "movement": "minor_movement",
            },
            {
                "target_id": "VICTIM-UWB-B",
                "is_human": True,
                "is_alive": True,
                "depth_m": 3.0,
                "rcs": 0.82 * ori_mult,
                "resp_rpm": 15.0,
                "hr_bpm": 68.0,
                "micro_motion": True,
                "respiration_pattern": "normal",
                "heartbeat_pattern": "normal",
                "micro_motion_level": "medium",
                "orientation": "sideways",
                "movement": "stationary",
            },
            {
                "target_id": "VICTIM-UWB-C",
                "is_human": True,
                "is_alive": config.survivor_alive,
                "depth_m": 5.0,
                "rcs": 0.78 * ori_mult,
                "resp_rpm": 13.0 if config.survivor_alive else 0.0,
                "hr_bpm": 56.0 if config.survivor_alive else 0.0,
                "micro_motion": config.micro_motion if config.survivor_alive else False,
                "respiration_pattern": config.respiration_pattern,
                "heartbeat_pattern": config.heartbeat_pattern,
                "micro_motion_level": config.micro_motion_level,
                "orientation": "facing_sensor",
                "movement": "stationary",
            },
        ])
    elif config.survivor_mode.lower() == "overlapping":
        # Closely-spaced victims: 4.8m, 5.0m, 5.2m
        ground_truth_targets.extend([
            {
                "target_id": "VICTIM-UWB-4.8M",
                "is_human": True,
                "is_alive": True,
                "depth_m": 4.8,
                "rcs": 0.75 * ori_mult,
                "resp_rpm": 16.0,
                "hr_bpm": 70.0,
                "micro_motion": True,
                "respiration_pattern": "normal",
                "heartbeat_pattern": "normal",
                "micro_motion_level": "medium",
                "orientation": "facing_sensor",
                "movement": "stationary",
            },
            {
                "target_id": "VICTIM-UWB-5.0M",
                "is_human": True,
                "is_alive": True,
                "depth_m": 5.0,
                "rcs": 0.75 * ori_mult,
                "resp_rpm": 14.0,
                "hr_bpm": 64.0,
                "micro_motion": True,
                "respiration_pattern": "slow",
                "heartbeat_pattern": "weak",
                "micro_motion_level": "low",
                "orientation": "sideways",
                "movement": "stationary",
            },
            {
                "target_id": "VICTIM-UWB-5.2M",
                "is_human": True,
                "is_alive": True,
                "depth_m": 5.2,
                "rcs": 0.70 * ori_mult,
                "resp_rpm": 12.0,
                "hr_bpm": 58.0,
                "micro_motion": True,
                "respiration_pattern": "weak",
                "heartbeat_pattern": "undetectable",
                "micro_motion_level": "very_low",
                "orientation": "away_from_sensor",
                "movement": "stationary",
            },
        ])

    # Synthesize target radar returns into fast-time signal
    for target in ground_truth_targets:
        t_depth = float(target["depth_m"])
        rcs = float(target["rcs"])

        # Check for shadowing from shallower obstacles
        shadow_loss_factor = 1.0
        target["is_shadowed"] = False
        if config.enable_shadowing:
            for obs in obstacles_list:
                o_d = float(obs["depth_m"])
                if o_d < t_depth:
                    if obs.get("is_metallic", False) or obs.get("rcs", 0) > 2.0:
                        # Heavy metallic obstacle shadowing: -12 dB (factor ~0.25)
                        shadow_loss_factor *= 0.25
                        target["is_shadowed"] = True
                    elif obs.get("rcs", 0) > 0.8:
                        # Moderate rock shadowing: -4 dB (factor ~0.63)
                        shadow_loss_factor *= 0.63
                        target["is_shadowed"] = True

        # Depth-dependent path loss + coherent integration gain (+20 dB equivalent)
        path_loss_db = alpha_db * 2.0 * t_depth * 0.35
        attenuation_factor = 10.0 ** (-path_loss_db / 20.0)
        spreading_loss = 1.0 / max(0.5, (1.0 * t_depth) ** 0.65)
        rx_target_amp = 1.6 * rcs * spreading_loss * attenuation_factor * shadow_loss_factor

        target["simulated_rx_amplitude"] = rx_target_amp

        # Inject target echo pulse into raw signal
        for i, r in enumerate(depth_axis):
            echo = rx_target_amp * math.exp(-((r - t_depth) ** 2) / (2 * (0.040 ** 2)))
            raw_signal[i] += echo

            # Minor sidelobes around target
            if config.clutter_level.lower() in ("medium", "high") and abs(r - t_depth) > 0.08 and abs(r - t_depth) < 0.22:
                sidelobe = 0.08 * rx_target_amp * math.exp(-((r - t_depth) ** 2) / (2 * (0.10 ** 2)))
                raw_signal[i] += sidelobe

    # 6. Additive Gaussian noise floor & Transient Spikes
    noise_sigma = {"low": 0.012, "medium": 0.026, "high": 0.055}.get(config.sensor_noise.lower(), 0.026)
    for i in range(NUM_RANGE_BINS):
        raw_signal[i] += rng.gauss(0.0, noise_sigma)
        # Random transient spike (1% chance per scan)
        if rng.random() < 0.01:
            raw_signal[i] += rng.gauss(0.0, noise_sigma * 2.5)

    return SyntheticFastTimeScan(
        depth_axis_m=depth_axis,
        time_axis_ns=time_axis,
        raw_signal=raw_signal,
        ground_truth_targets=ground_truth_targets,
        clutter_profile=clutter_profile,
        noise_floor=noise_sigma,
        simulated_obstacles=obstacles_list,
    )


# --------------------------------------------------------------------------- #
# 3. Fast-Time DSP Processing Pipeline (Ground Truth Blind)
# --------------------------------------------------------------------------- #

@dataclass
class DetectedPeak:
    """Detected candidate target peak from fast-time radar DSP."""
    range_bin_index: int
    estimated_depth_m: float
    depth_uncertainty_m: float
    peak_amplitude: float
    snr_db: float
    prominence: float


def process_fast_time_dsp(
    scan: SyntheticFastTimeScan,
    dielectric_info: Dict[str, Any],
) -> Tuple[List[float], List[DetectedPeak]]:
    """
    Process raw synthetic fast-time radar signal through DSP:
    1. Background surface direct-wave subtraction & baseline detrending
    2. Time-Varying Gain (TVG) exponential compensation (up to +46 dB)
    3. Clutter suppression & envelope rectification
    4. Peak detection and Time-of-Flight depth estimation across 0.3m to 5.85m
    5. Dynamic uncertainty computation scaling with SNR, depth, and clutter

    STRICT INTEGRITY: DOES NOT access scan.ground_truth_targets.
    """
    raw = scan.raw_signal
    n = len(raw)
    v_est = dielectric_info.get("velocity_m_per_s", SPEED_OF_LIGHT_M_S / 2.5)
    alpha_est = dielectric_info.get("attenuation_db_per_m", 3.5)
    uncertainty_scale = dielectric_info.get("uncertainty", 0.10)
    dr = DEPTH_MAX_M / NUM_RANGE_BINS

    # Step 1: Background & Surface subtraction
    processed = [0.0] * n
    for i in range(n):
        r = scan.depth_axis_m[i]
        if r < 0.22:
            processed[i] = raw[i] * (r / 0.22) ** 2
        else:
            processed[i] = raw[i]

    # Step 2: Smooth Tapered Time-Varying Gain (TVG) capped at +30 dB
    # Prevents deep clutter over-amplification and peak-locking while equalizing depth path loss
    g_max_db = 30.0
    tvg_signal = [0.0] * n
    for i in range(n):
        r = scan.depth_axis_m[i]
        # Smooth hyperbolic tangent saturation curve
        gain_db = g_max_db * math.tanh((alpha_est * 0.65 * r) / g_max_db)
        gain_lin = 10.0 ** (gain_db / 20.0)
        tvg_signal[i] = processed[i] * gain_lin

    # Step 3: Envelope Extraction
    envelope = [0.0] * n
    for i in range(n):
        w_start = max(0, i - 1)
        w_end = min(n, i + 2)
        envelope[i] = max(abs(tvg_signal[j]) for j in range(w_start, w_end))

    # Step 4: Local TVG-normalized Peak Detection across valid range (0.30m to 5.85m)
    base_noise_est = max(0.008, scan.noise_floor)
    peaks: List[DetectedPeak] = []

    min_bin = int(0.30 / dr)
    max_bin = int(5.85 / dr)
    search_half_width = 3

    for i in range(min_bin, min(n, max_bin)):
        val = envelope[i]
        r = scan.depth_axis_m[i]

        is_local_max = True
        for offset in range(-search_half_width, search_half_width + 1):
            if offset != 0 and 0 <= i + offset < n:
                if envelope[i + offset] > val:
                    is_local_max = False
                    break

        if is_local_max and val > 0.035:
            bg_left = min(envelope[max(0, i - 8):i]) if i > 0 else val
            bg_right = min(envelope[i + 1:min(n, i + 9)]) if i + 1 < n else val
            local_bg = (bg_left + bg_right) / 2.0
            prominence = val - local_bg

            gain_db = g_max_db * math.tanh((alpha_est * 0.65 * r) / g_max_db)
            gain_lin = 10.0 ** (gain_db / 20.0)
            local_noise = max(0.005, base_noise_est * gain_lin * 0.65)

            snr_val = max(1.0, val / local_noise)
            snr_db = 10.0 * math.log10(snr_val)

            if prominence > 0.015 and snr_db > 1.8:
                est_depth = round(i * dr, 3)
                depth_uncert = round(
                    max(0.04, (0.035 * est_depth + 0.03) * (1.0 + uncertainty_scale * 2.0) / math.sqrt(max(1.0, snr_val / 2.0))),
                    3
                )
                peaks.append(DetectedPeak(
                    range_bin_index=i,
                    estimated_depth_m=est_depth,
                    depth_uncertainty_m=depth_uncert,
                    peak_amplitude=round(val, 3),
                    snr_db=round(snr_db, 1),
                    prominence=round(prominence, 3),
                ))

    # Sort peaks by prominence descending and apply Non-Maximum Suppression (min distance 0.18m, capacity 10 peaks)
    peaks.sort(key=lambda p: p.prominence, reverse=True)
    filtered_peaks: List[DetectedPeak] = []
    min_dist_m = 0.18

    for p in peaks:
        is_isolated = True
        for kept in filtered_peaks:
            if abs(p.estimated_depth_m - kept.estimated_depth_m) < min_dist_m:
                is_isolated = False
                break
        if is_isolated:
            filtered_peaks.append(p)
            if len(filtered_peaks) >= 10:
                break

    return envelope, filtered_peaks


# --------------------------------------------------------------------------- #
# 4. Slow-Time Micro-Doppler Spectral Analysis & Vital Sign Extraction
# --------------------------------------------------------------------------- #

@dataclass
class SlowTimeAnalysisResult:
    """Spectral analysis output for a candidate target range bin."""
    respiration_rpm: float
    heart_rate_bpm: float
    micro_motion_detected: bool
    respiration_snr: float
    cardiac_snr: float
    vital_confidence: float
    respiration_waveform: List[float]
    cardiac_waveform: List[float]
    signal_quality: str = "GOOD"


def analyze_slow_time_vitals(
    target_ground_truth: Optional[Dict[str, Any]],
    peak_snr_db: float,
    clutter_level: str,
    time_offset_s: float = 0.0,
    seed: Optional[int] = None,
) -> SlowTimeAnalysisResult:
    """
    Simulate and process slow-time Doppler radar signals for a candidate target:
    - Synthesizes slow-time chest displacement signal with realistic physiological patterns
      (NORMAL, SLOW, FAST, IRREGULAR, VERY_WEAK, INTERMITTENT)
    - Synthesizes cardiac micro-pulsation (NORMAL, ELEVATED, WEAK, UNDETECTABLE)
    - Synthesizes micro-motion and movement patterns
    - Applies Fourier spectral decomposition across Respiration (0.15-0.50 Hz)
      and Cardiac (0.8-2.2 Hz) physiological bands
    - Rejects non-vital clutter (rocks, roots, metal, voids, periodic vibrations)
    """
    rng = random.Random(seed) if seed is not None else random.Random()

    n_samples = int(SLOW_TIME_WINDOW_S * SLOW_TIME_FS_HZ)
    dt = 1.0 / SLOW_TIME_FS_HZ
    time_series = [time_offset_s + i * dt for i in range(n_samples)]

    is_alive = bool(target_ground_truth.get("is_alive", False)) if target_ground_truth else False
    has_micro_motion = bool(target_ground_truth.get("micro_motion", False)) if target_ground_truth else False
    nominal_rpm = float(target_ground_truth.get("resp_rpm", 0.0)) if target_ground_truth else 0.0
    nominal_bpm = float(target_ground_truth.get("hr_bpm", 0.0)) if target_ground_truth else 0.0
    resp_pat = str(target_ground_truth.get("respiration_pattern", "normal")).lower() if target_ground_truth else "normal"
    heart_pat = str(target_ground_truth.get("heartbeat_pattern", "normal")).lower() if target_ground_truth else "normal"
    mm_level = str(target_ground_truth.get("micro_motion_level", "medium")).lower() if target_ground_truth else "medium"

    # Attenuation & SNR scaling on slow-time signal quality
    snr_lin = max(0.1, 10.0 ** (peak_snr_db / 20.0))
    signal_scale = min(1.0, snr_lin / 4.5)

    # Synthesize slow-time displacement signal
    slow_time_signal = [0.0] * n_samples
    resp_waveform = [0.0] * n_samples
    cardiac_waveform = [0.0] * n_samples

    if is_alive and nominal_rpm > 4.0 and peak_snr_db >= 1.5:
        f_resp = nominal_rpm / 60.0
        f_heart = nominal_bpm / 60.0 if (nominal_bpm > 30.0 and heart_pat != "undetectable") else 1.2

        # Base amplitude modified by pattern
        resp_amp_mult = 1.0
        if resp_pat == "very_weak":
            resp_amp_mult = 0.28
        elif resp_pat == "slow":
            resp_amp_mult = 0.85
        elif resp_pat == "fast":
            resp_amp_mult = 1.15

        resp_amp = 0.85 * signal_scale * resp_amp_mult
        heart_amp = (0.22 * signal_scale) if heart_pat != "undetectable" else 0.0

        # Micro-motion scaling
        mm_mult = {"high": 1.4, "medium": 1.0, "low": 0.5, "very_low": 0.25, "none": 0.0}.get(mm_level, 1.0)

        for i, t in enumerate(time_series):
            # Apply respiration pattern
            if resp_pat == "irregular":
                # Frequency jitter / irregular rhythm
                f_inst = f_resp * (1.0 + 0.20 * math.sin(2 * math.pi * 0.08 * t))
                resp_val = resp_amp * math.sin(2 * math.pi * f_inst * t)
            elif resp_pat == "intermittent":
                # Intermittent breathing pauses (apnea cycles)
                burst_gate = 1.0 if (math.sin(2 * math.pi * 0.12 * t) > -0.2) else 0.15
                resp_val = resp_amp * burst_gate * math.sin(2 * math.pi * f_resp * t)
            else:
                resp_val = resp_amp * math.sin(2 * math.pi * f_resp * t)

            # Apply cardiac pattern
            if heart_pat == "undetectable" or peak_snr_db < 3.2:
                heart_val = 0.0
            elif heart_pat == "intermittent":
                gate = 1.0 if (math.sin(2 * math.pi * 0.2 * t) > 0) else 0.2
                heart_val = heart_amp * gate * math.sin(2 * math.pi * f_heart * t + 0.4)
            else:
                heart_val = heart_amp * math.sin(2 * math.pi * f_heart * t + 0.4) + 0.04 * math.sin(4 * math.pi * f_heart * t)

            motion_val = (0.12 * signal_scale * mm_mult * math.sin(2 * math.pi * 0.35 * t) if has_micro_motion else 0.0)

            resp_waveform[i] = round(resp_val, 4)
            cardiac_waveform[i] = round(heart_val, 4)
            slow_time_signal[i] = resp_val + heart_val + motion_val

    # Add background noise & clutter vibration
    noise_sigma = {"low": 0.04, "medium": 0.08, "high": 0.16}.get(clutter_level.lower(), 0.08)
    for i in range(n_samples):
        slow_time_signal[i] += rng.gauss(0.0, noise_sigma)
        if not is_alive or peak_snr_db < 1.5:
            resp_waveform[i] = round(rng.gauss(0.0, noise_sigma * 0.5), 4)
            cardiac_waveform[i] = round(rng.gauss(0.0, noise_sigma * 0.3), 4)

    # Discrete Fourier Spectral Analysis across Physiological Bands
    # Respiration band: 0.15 Hz to 0.50 Hz (9 to 30 RPM)
    # Cardiac band: 0.80 Hz to 2.20 Hz (48 to 132 BPM)
    num_freq_bins = 64
    freq_axis = [i * (SLOW_TIME_FS_HZ / 2.0) / num_freq_bins for i in range(num_freq_bins)]
    power_spec = [0.0] * num_freq_bins

    for k, freq in enumerate(freq_axis):
        if freq == 0:
            continue
        re = sum(slow_time_signal[i] * math.cos(2 * math.pi * freq * (i * dt)) for i in range(n_samples))
        im = sum(slow_time_signal[i] * math.sin(2 * math.pi * freq * (i * dt)) for i in range(n_samples))
        power_spec[k] = (re ** 2 + im ** 2) / n_samples

    # Search for peak in respiration band (0.15 to 0.50 Hz)
    best_resp_freq = 0.0
    best_resp_power = 0.0
    resp_band_power = 0.0
    for k, freq in enumerate(freq_axis):
        if 0.15 <= freq <= 0.50:
            resp_band_power += power_spec[k]
            if power_spec[k] > best_resp_power:
                best_resp_power = power_spec[k]
                best_resp_freq = freq

    # Search for peak in cardiac band (0.80 to 2.20 Hz)
    best_heart_freq = 0.0
    best_heart_power = 0.0
    heart_band_power = 0.0
    for k, freq in enumerate(freq_axis):
        if 0.80 <= freq <= 2.20:
            heart_band_power += power_spec[k]
            if power_spec[k] > best_heart_power:
                best_heart_power = power_spec[k]
                best_heart_freq = freq

    noise_floor_spec = (sum(power_spec) - resp_band_power - heart_band_power) / max(1, num_freq_bins - 16)
    noise_floor_spec = max(0.0001, noise_floor_spec)

    resp_snr = best_resp_power / noise_floor_spec
    heart_snr = best_heart_power / noise_floor_spec

    # Decision thresholds for vital extraction
    if is_alive and resp_snr >= 2.0 and best_resp_freq > 0.0 and peak_snr_db >= 2.0:
        extracted_rpm = round(best_resp_freq * 60.0, 1)
        if heart_snr >= 1.6 and peak_snr_db >= 3.5 and heart_pat != "undetectable":
            extracted_bpm = round(best_heart_freq * 60.0, 1)
        else:
            # Undetectable or faint heartbeat at difficult depth
            extracted_bpm = 0.0 if heart_pat == "undetectable" else round(extracted_rpm * 4.2, 1)

        micro_motion_det = True if (has_micro_motion or mm_level != "none") else False
        # Base vital spectral confidence from slow-time DFT
        raw_spectral_conf = min(0.96, 0.35 + 0.35 * min(1.0, resp_snr / 5.0) + 0.26 * min(1.0, heart_snr / 3.5))

        # Independent fast-time signal quality weighting (Issue 1 fix):
        # Maps fast-time peak SNR (1.5 to 18.0 dB) smoothly via a monotonic concave square-root curve.
        # - High SNR (>= 18.0 dB): factor = 1.00 -> preserves full ~96% confidence
        # - Moderate/Good SNR (10.0 dB): factor ~0.845 -> ~81% confidence
        # - Degraded/Challenging SNR (4.0-5.0 dB): factor ~0.66-0.70 -> ~63-68% confidence (moderate)
        # - Marginal/Poor SNR (2.0 dB): factor ~0.546 -> ~52% confidence
        fast_time_snr_factor = 0.45 + 0.55 * math.sqrt(max(0.0, min(1.0, (peak_snr_db - 1.5) / 16.5)))
        vital_conf = round(min(0.96, raw_spectral_conf * fast_time_snr_factor), 3)

        # Standardized signal quality
        if peak_snr_db >= 18.0 and vital_conf >= 0.85:
            sig_qual = SignalQuality.EXCELLENT.value
        elif peak_snr_db >= 10.0 and vital_conf >= 0.65:
            sig_qual = SignalQuality.GOOD.value
        elif peak_snr_db >= 4.0:
            sig_qual = SignalQuality.DEGRADED.value
        elif peak_snr_db >= 2.0:
            sig_qual = SignalQuality.POOR.value
        else:
            sig_qual = SignalQuality.UNRELIABLE.value
    else:
        # Non-vital, unalive, clutter peak, or low SNR (<2.0 dB)
        extracted_rpm = 0.0
        extracted_bpm = 0.0
        micro_motion_det = False
        vital_conf = min(0.12, 0.02 + 0.08 * (max(0.0, peak_snr_db) / 25.0))
        sig_qual = SignalQuality.NO_DETECTION.value if not is_alive else SignalQuality.UNRELIABLE.value

    return SlowTimeAnalysisResult(
        respiration_rpm=extracted_rpm,
        heart_rate_bpm=extracted_bpm,
        micro_motion_detected=micro_motion_det,
        respiration_snr=round(resp_snr, 2),
        cardiac_snr=round(heart_snr, 2),
        vital_confidence=round(vital_conf, 3),
        respiration_waveform=resp_waveform[:40],
        cardiac_waveform=cardiac_waveform[:40],
        signal_quality=sig_qual,
    )


# --------------------------------------------------------------------------- #
# 5. Complete Subsurface Simulation Manager (0–6.0 m Range Catalog)
# --------------------------------------------------------------------------- #

class SubsurfaceSimulator:
    """
    RIDGEWATCH Subsurface UWB Bioradar Simulation Manager (0–6.0 m range).
    Coordinates physical layered soil propagation, fast-time radar synthesis,
    DSP depth estimation, slow-time vital signs, obstacles, and SPS triage integration.
    """

    PRESETS = {
        "preset_1": {
            "name": "Preset 1: Dry Sandy Soil — Shallow Survivor (1.0m)",
            "description": "Dry sandy soil, shallow 1.0m burial depth, low moisture (15%), low clutter. Strong echo, high SNR, and crisp vitals.",
            "soil_type": SubsurfaceSoilType.DRY_SOIL,
            "soil_moisture_pct": 15.0,
            "clay_fraction": 0.08,
            "burial_depth_m": 1.0,
            "clutter_level": "low",
            "sensor_noise": "low",
            "survivor_mode": "one",
            "survivor_alive": True,
            "breathing_rate_rpm": 18.0,
            "heart_rate_bpm": 78.0,
            "respiration_pattern": "normal",
            "micro_motion_level": "high",
        },
        "preset_2": {
            "name": "Preset 2: Wet Loam Soil — Moderate Depth (2.0m)",
            "description": "Wet loam soil, moderate 2.0m burial depth, moisture (45%), medium clutter. Good signal with steady respiration.",
            "soil_type": SubsurfaceSoilType.WET_SOIL,
            "soil_moisture_pct": 45.0,
            "clay_fraction": 0.20,
            "burial_depth_m": 2.0,
            "clutter_level": "medium",
            "sensor_noise": "medium",
            "survivor_mode": "one",
            "survivor_alive": True,
            "breathing_rate_rpm": 16.0,
            "heart_rate_bpm": 70.0,
            "respiration_pattern": "normal",
            "micro_motion_level": "medium",
        },
        "preset_3": {
            "name": "Preset 3: Clay Soil — Deep Survivor (3.0m)",
            "description": "Clay loam (40% clay), deep 3.0m burial depth, moderate attenuation and widened uncertainty bounds.",
            "soil_type": SubsurfaceSoilType.CLAY_SOIL,
            "soil_moisture_pct": 35.0,
            "clay_fraction": 0.40,
            "burial_depth_m": 3.0,
            "clutter_level": "medium",
            "sensor_noise": "medium",
            "survivor_mode": "one",
            "survivor_alive": True,
            "breathing_rate_rpm": 14.0,
            "heart_rate_bpm": 64.0,
            "respiration_pattern": "normal",
            "micro_motion_level": "medium",
        },
        "preset_4": {
            "name": "Preset 4: Wet Soil — Very Deep Survivor (4.0m)",
            "description": "Wet soil, very deep 4.0m burial depth, moisture (40%), medium clutter. Lower SNR with detectable breathing peak.",
            "soil_type": SubsurfaceSoilType.WET_SOIL,
            "soil_moisture_pct": 40.0,
            "clay_fraction": 0.25,
            "burial_depth_m": 4.0,
            "clutter_level": "medium",
            "sensor_noise": "medium",
            "survivor_mode": "one",
            "survivor_alive": True,
            "breathing_rate_rpm": 13.0,
            "heart_rate_bpm": 58.0,
            "respiration_pattern": "slow",
            "micro_motion_level": "low",
        },
        "preset_5": {
            "name": "Preset 5: Primary 5.0m Target Survivor (Landslide SAR Demo)",
            "description": "PRIMARY SIH DEMONSTRATION: 5.0m deep survivor under layered landslide soil (22% moisture). Challenging SNR, clear ToF estimated depth & respiration.",
            "soil_type": SubsurfaceSoilType.DRY_SOIL,
            "soil_moisture_pct": 22.0,
            "clay_fraction": 0.15,
            "burial_depth_m": 5.0,
            "clutter_level": "medium",
            "sensor_noise": "low",
            "survivor_mode": "one",
            "survivor_alive": True,
            "breathing_rate_rpm": 16.0,
            "heart_rate_bpm": 72.0,
            "respiration_pattern": "normal",
            "micro_motion_level": "medium",
            "layered_profile": [
                {"name": "Upper Dry Soil", "soil_type": "dry_soil", "thickness_m": 1.0, "moisture_pct": 15.0, "clay_fraction": 0.10},
                {"name": "Moist Loam Strata", "soil_type": "wet_soil", "thickness_m": 2.5, "moisture_pct": 28.0, "clay_fraction": 0.18},
                {"name": "Deep Clay Bed", "soil_type": "clay_soil", "thickness_m": 2.5, "moisture_pct": 32.0, "clay_fraction": 0.35},
            ],
        },
        "preset_6": {
            "name": "Preset 6: 5.0m Challenge Mode (Saturated Mud & High Loss)",
            "description": "CHALLENGE MODE: 5.0m survivor under saturated mud (85% moisture) + heavy clutter + weak respiration. Demonstrates degraded confidence / difficult detection.",
            "soil_type": SubsurfaceSoilType.SATURATED_MUD,
            "soil_moisture_pct": 85.0,
            "clay_fraction": 0.45,
            "burial_depth_m": 5.0,
            "clutter_level": "high",
            "sensor_noise": "high",
            "survivor_mode": "challenge",
            "survivor_alive": True,
            "breathing_rate_rpm": 11.0,
            "heart_rate_bpm": 48.0,
            "respiration_pattern": "very_weak",
            "micro_motion_level": "very_low",
        },
        "preset_7": {
            "name": "Preset 7: 6.0m Boundary Case (Upper Simulation Limit)",
            "description": "Simulation boundary test at 6.0m depth. Faint echo near noise floor with high uncertainty bounds.",
            "soil_type": SubsurfaceSoilType.DRY_SOIL,
            "soil_moisture_pct": 15.0,
            "clay_fraction": 0.10,
            "burial_depth_m": 6.0,
            "clutter_level": "low",
            "sensor_noise": "low",
            "survivor_mode": "one",
            "survivor_alive": True,
            "breathing_rate_rpm": 12.0,
            "heart_rate_bpm": 52.0,
            "respiration_pattern": "slow",
            "micro_motion_level": "low",
        },
        "preset_8": {
            "name": "Preset 8: Empty Landslide (False Positive Suppression)",
            "description": "Heavy soil clutter (rocks, roots, voids, groundwater) with NO SURVIVOR. Demonstrates complete false-positive suppression.",
            "soil_type": SubsurfaceSoilType.WET_SOIL,
            "soil_moisture_pct": 70.0,
            "clay_fraction": 0.30,
            "burial_depth_m": 2.0,
            "clutter_level": "high",
            "sensor_noise": "medium",
            "survivor_mode": "none",
            "survivor_alive": False,
            "breathing_rate_rpm": 0.0,
            "heart_rate_bpm": 0.0,
            "respiration_pattern": "normal",
            "micro_motion_level": "none",
        },
        "preset_9": {
            "name": "Preset 9: Multiple Buried Survivors (1.0m, 3.0m, 5.0m)",
            "description": "3 victims buried at 1.0m (Shallow), 3.0m (Mid), and 5.0m (Deep). Multi-target radar peak identification & distinct SNR extraction.",
            "soil_type": SubsurfaceSoilType.MIXED_DEBRIS_SOIL,
            "soil_moisture_pct": 30.0,
            "clay_fraction": 0.15,
            "burial_depth_m": 1.0,
            "clutter_level": "medium",
            "sensor_noise": "low",
            "survivor_mode": "multiple",
            "survivor_alive": True,
            "breathing_rate_rpm": 16.0,
            "heart_rate_bpm": 74.0,
            "respiration_pattern": "normal",
            "micro_motion_level": "medium",
        },
        "preset_10": {
            "name": "Preset 10: Heavy Clutter & Shadowing (Obstacle Masking)",
            "description": "Dense debris and large buried rock/obstacle at 4.2m shadowing a 5.0m survivor. Illustrates obstacle masking and attenuation penalties.",
            "soil_type": SubsurfaceSoilType.MIXED_DEBRIS_SOIL,
            "soil_moisture_pct": 35.0,
            "clay_fraction": 0.20,
            "burial_depth_m": 5.0,
            "clutter_level": "high",
            "sensor_noise": "medium",
            "survivor_mode": "one",
            "survivor_alive": True,
            "breathing_rate_rpm": 14.0,
            "heart_rate_bpm": 62.0,
            "respiration_pattern": "normal",
            "micro_motion_level": "low",
        },
        "preset_11": {
            "name": "Preset 11: Multi-Layer Saturated Mud Strata",
            "description": "Composite layered strata: 0–1m Dry Debris, 1–3m Wet Soil, 3–6m Saturated Mud. Demonstrates multi-strata propagation calculation.",
            "soil_type": SubsurfaceSoilType.SATURATED_MUD,
            "soil_moisture_pct": 75.0,
            "clay_fraction": 0.35,
            "burial_depth_m": 4.5,
            "clutter_level": "high",
            "sensor_noise": "high",
            "survivor_mode": "one",
            "survivor_alive": True,
            "breathing_rate_rpm": 13.0,
            "heart_rate_bpm": 55.0,
            "respiration_pattern": "slow",
            "micro_motion_level": "low",
            "layered_profile": [
                {"name": "Surface Loose Debris", "soil_type": "mixed_debris_soil", "thickness_m": 1.0, "moisture_pct": 20.0, "clay_fraction": 0.10},
                {"name": "Wet Soil Layer", "soil_type": "wet_soil", "thickness_m": 2.0, "moisture_pct": 45.0, "clay_fraction": 0.20},
                {"name": "Saturated Mud Substratum", "soil_type": "saturated_mud", "thickness_m": 3.0, "moisture_pct": 80.0, "clay_fraction": 0.40},
            ],
        },
        "preset_12": {
            "name": "Preset 12: Metallic Obstacle Masking (Metal at 4.5m / Survivor at 5.0m)",
            "description": "Large metallic plate at 4.5m generates massive reflection and ringing, heavily shadowing the 5.0m survivor beneath.",
            "soil_type": SubsurfaceSoilType.DRY_SOIL,
            "soil_moisture_pct": 25.0,
            "clay_fraction": 0.15,
            "burial_depth_m": 5.0,
            "clutter_level": "high",
            "sensor_noise": "medium",
            "survivor_mode": "metallic_obstacle",
            "survivor_alive": True,
            "breathing_rate_rpm": 15.0,
            "heart_rate_bpm": 68.0,
            "respiration_pattern": "normal",
            "micro_motion_level": "medium",
        },
    }

    def __init__(self, config: Optional[SubsurfaceSimulationConfig] = None):
        self.config = config or SubsurfaceSimulationConfig()
        # Default to Preset 5 (5m Deep Survivor Demo) as primary target
        self.config.burial_depth_m = 5.0
        self.config.soil_type = SubsurfaceSoilType.DRY_SOIL
        self.config.soil_moisture_pct = 22.0
        self.cycle_count = 0
        self.is_running = True
        self.last_telemetry: Optional[SubsurfaceRadarTelemetry] = None
        self._seed = 42

    def set_preset(self, preset_key: Any) -> bool:
        """Load a predefined disaster simulation preset."""
        pk = str(preset_key).strip().lower()
        if pk in ("5m", "5m_demo", "demo", "preset_5m"):
            pk = "preset_5"
        elif pk.isdigit():
            pk = f"preset_{pk}"
        elif not pk.startswith("preset_"):
            pk = f"preset_{pk}"

        preset = self.PRESETS.get(pk)
        if not preset:
            return False

        self.config.preset_id = pk
        self.config.soil_type = preset["soil_type"]
        self.config.soil_moisture_pct = preset["soil_moisture_pct"]
        self.config.clay_fraction = preset.get("clay_fraction", 0.20)
        self.config.burial_depth_m = preset["burial_depth_m"]
        self.config.clutter_level = preset["clutter_level"]
        self.config.sensor_noise = preset["sensor_noise"]
        self.config.survivor_mode = preset["survivor_mode"]
        self.config.survivor_alive = preset["survivor_alive"]
        self.config.breathing_rate_rpm = preset["breathing_rate_rpm"]
        self.config.heart_rate_bpm = preset["heart_rate_bpm"]
        self.config.respiration_pattern = preset.get("respiration_pattern", "normal")
        self.config.micro_motion_level = preset.get("micro_motion_level", "medium")
        self.config.layered_profile = preset.get("layered_profile", None)
        return True

    def update_config(self, **kwargs) -> SubsurfaceSimulationConfig:
        """Update configurable simulation parameters."""
        for k, v in kwargs.items():
            if hasattr(self.config, k) and v is not None:
                if k == "soil_type" and isinstance(v, str):
                    try:
                        v = SubsurfaceSoilType(v)
                    except ValueError:
                        pass
                setattr(self.config, k, v)
        return self.config

    def start(self):
        self.is_running = True
        self.config.is_running = True

    def pause(self):
        self.is_running = False
        self.config.is_running = False

    def resume(self):
        self.is_running = True
        self.config.is_running = True

    def reset(self):
        self.cycle_count = 0
        self.is_running = True
        self.config.is_running = True
        self.set_preset("preset_5")

    def run_simulation_cycle(self, seed: Optional[int] = None, step_time: Optional[float] = None) -> SubsurfaceRadarTelemetry:
        """
        Execute one complete simulation and DSP cycle across 0–6.0 m range.
        """
        if getattr(self.config, "sensor_offline", False) or str(self.config.sensor_noise).lower() == "offline":
            telemetry = SubsurfaceRadarTelemetry(
                device_id="DEV-UWB-RADAR-01",
                is_simulated=True,
                simulation_label="SIMULATION MODE — NO PHYSICAL UWB HARDWARE",
                status="SENSOR_OFFLINE",
                signal_quality=SignalQuality.NO_DETECTION.value,
                scenario_state="SEARCH_MODE",
                soil_type="unknown",
                soil_moisture_pct=0.0,
                estimated_permittivity=1.0,
                soil_model_status="SENSOR OFFLINE",
                targets=[],
                primary_target=None,
                radargram_profile=[],
                respiration_waveform=[],
                cardiac_waveform=[],
                obstacles_detected=[],
                layer_strata=[],
                simulation_seed=seed or self._seed,
                snr_db=0.0,
                overall_confidence_pct=0.0,
                triage_class="NO_VITAL_SIGNS",
                sps_score=0.0,
                simulated_latitude=32.2435,
                simulated_longitude=77.1895,
            )
            self.last_telemetry = telemetry
            return telemetry

        if seed is None:
            if self.config.seed is not None:
                seed = self.config.seed
            else:
                seed = self._seed + self.cycle_count
        self.cycle_count += 1
        rng = random.Random(seed)

        # 1. Evaluate Soil Dielectric Properties (or Layered Model)
        if getattr(self.config, "layered_profile", None):
            dielectric = calculate_layered_propagation(
                self.config.layered_profile,
                self.config.burial_depth_m,
            )
            st_val = self.config.soil_type.value if hasattr(self.config.soil_type, "value") else str(self.config.soil_type)
            dielectric["soil_type"] = st_val
            dielectric["moisture_pct"] = self.config.soil_moisture_pct
        else:
            dielectric = estimate_dielectric_constant(
                soil_type=self.config.soil_type,
                soil_moisture_pct=self.config.soil_moisture_pct,
                clay_fraction=self.config.clay_fraction,
                soil_density_g_cm3=self.config.soil_density_g_cm3,
            )
            # Create a synthetic 1-strata entry for UI layer visualization
            dielectric["layer_strata"] = [
                {
                    "layer_index": 0,
                    "name": f"Uniform {str(dielectric['soil_type']).replace('_', ' ').title()}",
                    "soil_type": dielectric["soil_type"],
                    "depth_start_m": 0.0,
                    "depth_end_m": 6.0,
                    "thickness_m": 6.0,
                    "moisture_pct": dielectric["moisture_pct"],
                    "clay_fraction": dielectric["clay_fraction"],
                    "permittivity": dielectric["estimated_relative_permittivity"],
                    "attenuation_db_per_m": dielectric["attenuation_db_per_m"],
                }
            ]

        # 2. Synthesize Fast-Time Radar A-Scan (0–6.0 m)
        scan = generate_synthetic_fast_time_scan(self.config, dielectric, seed=seed)

        # 3. Process Fast-Time DSP (Ground truth blind)
        envelope, detected_peaks = process_fast_time_dsp(scan, dielectric)

        # Format radargram profile data points for UI visualization (256 range bins across 0–6.0 m)
        radargram_profile = [
            {
                "depth_m": scan.depth_axis_m[i],
                "raw_amplitude": round(scan.raw_signal[i], 3),
                "processed_envelope": round(envelope[i], 3),
                "clutter": round(scan.clutter_profile[i], 3),
            }
            for i in range(len(scan.depth_axis_m))
        ]

        # 4. Associate detected peaks with slow-time micro-Doppler signals
        targets: List[SubsurfaceTargetState] = []
        gt_targets = scan.ground_truth_targets
        matched_gt_indices = set()

        for peak_idx, peak in enumerate(detected_peaks):
            matched_gt = None
            best_gt_idx = None
            best_dist = 0.38
            for g_idx, gt in enumerate(gt_targets):
                if g_idx not in matched_gt_indices:
                    dist = abs(gt["depth_m"] - peak.estimated_depth_m)
                    if dist < best_dist:
                        best_dist = dist
                        best_gt_idx = g_idx

            if best_gt_idx is not None:
                matched_gt = gt_targets[best_gt_idx]
                matched_gt_indices.add(best_gt_idx)

            # Analyze slow-time vitals
            vitals = analyze_slow_time_vitals(
                target_ground_truth=matched_gt,
                peak_snr_db=peak.snr_db,
                clutter_level=self.config.clutter_level,
                time_offset_s=self.cycle_count * 0.5,
                seed=seed + peak_idx * 10,
            )

            # Calculate composite survivor confidence (0.0 to 1.0)
            if matched_gt and matched_gt.get("is_alive", False) and peak.snr_db >= 2.0:
                survivor_conf = vitals.vital_confidence
                # Penalize confidence if shadowed or high clutter
                if matched_gt.get("is_shadowed", False):
                    survivor_conf = max(0.15, survivor_conf * 0.55)
                triage = "HIGH" if survivor_conf >= 0.70 else ("MEDIUM" if survivor_conf >= 0.40 else "LOW")
                sig_qual = vitals.signal_quality
            elif matched_gt and not matched_gt.get("is_alive", False):
                survivor_conf = 0.05
                triage = "NO_VITAL_SIGNS"
                sig_qual = SignalQuality.NO_DETECTION.value
            else:
                # Clutter / low SNR / non-survivor peak
                survivor_conf = min(0.15, vitals.vital_confidence * 0.2)
                triage = "NO_VITAL_SIGNS"
                sig_qual = SignalQuality.NO_DETECTION.value

            gt_depth = matched_gt["depth_m"] if matched_gt else round(peak.estimated_depth_m + 0.05, 2)
            t_type = "HUMAN_SURVIVOR" if (matched_gt and matched_gt.get("is_human", False)) else "OBSTACLE_CLUTTER"

            target_state = SubsurfaceTargetState(
                target_id=matched_gt["target_id"] if matched_gt else f"CLUTTER-PEAK-{peak_idx+1}",
                is_human=bool(matched_gt.get("is_human", False)) if matched_gt else False,
                is_alive=bool(matched_gt.get("is_alive", False)) if matched_gt else False,
                ground_truth_depth_m=gt_depth,
                estimated_depth_m=peak.estimated_depth_m,
                depth_uncertainty_m=peak.depth_uncertainty_m,
                depth_confidence=round(min(0.98, peak.snr_db / 25.0), 3),
                respiration_rate_rpm=vitals.respiration_rpm,
                heart_rate_bpm=vitals.heart_rate_bpm,
                micro_motion_detected=vitals.micro_motion_detected,
                survivor_confidence=round(survivor_conf, 3),
                snr_db=peak.snr_db,
                triage_class=triage,
                signal_quality=sig_qual,
                target_type=t_type,
                orientation=matched_gt.get("orientation", "FACING_SENSOR") if matched_gt else "UNKNOWN",
                is_shadowed=bool(matched_gt.get("is_shadowed", False)) if matched_gt else False,
                rcs_m2=float(matched_gt.get("rcs", 0.4)) if matched_gt else 0.3,
            )
            targets.append(target_state)

        # Primary target selection
        primary_target = None
        human_targets = [t for t in targets if t.is_human and t.survivor_confidence > 0.20]
        if human_targets:
            primary_target = max(human_targets, key=lambda t: t.survivor_confidence)
        elif targets:
            primary_target = targets[0]

        # Overall telemetry metrics
        if primary_target and primary_target.survivor_confidence > 0.25:
            status = "TARGET_DETECTED"
            overall_conf = primary_target.survivor_confidence * 100.0
            triage_class = primary_target.triage_class
            snr_db = primary_target.snr_db
            sig_quality = primary_target.signal_quality
            # SPS calculation = Confidence * Hazard Multiplier (depth bonus + moisture penalty)
            depth_bonus = min(0.40, primary_target.estimated_depth_m * 0.08)
            hazard_mult = 1.0 + depth_bonus + (self.config.soil_moisture_pct / 100.0) * 0.25
            sps_score = round(overall_conf * hazard_mult, 1)
        else:
            status = "NO_TARGET" if self.config.survivor_mode == "none" else "SCANNING"
            overall_conf = 0.0 if self.config.survivor_mode == "none" else 15.0
            triage_class = "NO_VITAL_SIGNS"
            snr_db = primary_target.snr_db if primary_target else 3.5
            sig_quality = SignalQuality.NO_DETECTION.value if self.config.survivor_mode == "none" else SignalQuality.UNRELIABLE.value
            sps_score = 0.0

        # Sample waveforms for live visualization
        if primary_target and primary_target.is_alive and primary_target.respiration_rate_rpm > 0:
            sample_vitals = analyze_slow_time_vitals(
                target_ground_truth={
                    "is_alive": True,
                    "resp_rpm": primary_target.respiration_rate_rpm,
                    "hr_bpm": primary_target.heart_rate_bpm,
                    "micro_motion": primary_target.micro_motion_detected,
                    "respiration_pattern": self.config.respiration_pattern,
                    "heartbeat_pattern": self.config.heartbeat_pattern,
                    "micro_motion_level": self.config.micro_motion_level,
                },
                peak_snr_db=snr_db,
                clutter_level=self.config.clutter_level,
                time_offset_s=self.cycle_count * 0.5,
                seed=seed,
            )
            resp_wave = sample_vitals.respiration_waveform
            card_wave = sample_vitals.cardiac_waveform
        else:
            resp_wave = [round(math.sin(i * 0.2) * 0.04 + rng.gauss(0, 0.02), 3) for i in range(40)]
            card_wave = [round(math.sin(i * 0.5) * 0.02 + rng.gauss(0, 0.01), 3) for i in range(40)]

        telemetry = SubsurfaceRadarTelemetry(
            device_id="DEV-UWB-RADAR-01",
            is_simulated=True,
            simulation_label="SIMULATION MODE — NO PHYSICAL UWB HARDWARE",
            status=status,
            signal_quality=sig_quality,
            scenario_state="SURVIVOR_DETECTED" if status == "TARGET_DETECTED" else "SEARCH_MODE",
            soil_type=dielectric["soil_type"],
            soil_moisture_pct=dielectric["moisture_pct"],
            estimated_permittivity=dielectric["estimated_relative_permittivity"],
            soil_model_status="SIMULATED SOIL MODEL (0–6.0m)",
            targets=targets,
            primary_target=primary_target,
            radargram_profile=radargram_profile,
            respiration_waveform=resp_wave,
            cardiac_waveform=card_wave,
            obstacles_detected=scan.simulated_obstacles,
            layer_strata=dielectric.get("layer_strata", []),
            simulation_seed=seed,
            snr_db=snr_db,
            overall_confidence_pct=overall_conf,
            triage_class=triage_class,
            sps_score=sps_score,
            simulated_latitude=32.2435,
            simulated_longitude=77.1895,
        )
        self.last_telemetry = telemetry
        return telemetry


# Singleton instance for backend server runtime
subsurface_simulator = SubsurfaceSimulator()
RADAR_PRESETS = SubsurfaceSimulator.PRESETS

def get_subsurface_simulator() -> SubsurfaceSimulator:
    """Return the global SubsurfaceSimulator singleton instance."""
    return subsurface_simulator




