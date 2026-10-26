"""
demo_sensor_simulator.py
-------------------------
Small standalone test script (not a pytest suite) that runs the
SensorSimulator for 10 cycles across all 4 Himalaya victims and prints
the readings in a readable table, plus a battery/degradation summary.

Run with:
    python tests/demo_sensor_simulator.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sensor_simulator import SensorSimulator
from models import HIMALAYA_VICTIMS, SensorType


SENSOR_ORDER = [
    SensorType.THERMAL_IMAGING,
    SensorType.PIR_MOTION,
    SensorType.ACOUSTIC,
    SensorType.CO2,
    SensorType.HEART_RATE_RADAR,
    SensorType.RGB_CAMERA,
]

# Kit-level IMU sensors (Step 10) are emitted unconditionally for every
# non-dropped-out node every cycle (see sensor_simulator.generate_cycle()) -
# unlike WATER_LEVEL/WATER_FLOW, there's no enable_* flag gating them off.
IMU_SENSOR_TYPES = [SensorType.IMU_TILT, SensorType.IMU_VIBRATION]

HEADER = (
    f"{'Cyc':>3} | {'Victim':<10} | {'Thermal(C)':>10} | {'Motion':>7} | "
    f"{'Acoustic':>8} | {'CO2(ppm)':>9} | {'HR(bpm)':>8} | {'Cam':>5} | "
    f"{'Conf':>5} | Flags"
)


def assert_imu_readings_present_every_cycle(num_cycles: int = 10, seed: int = 7):
    """
    Smoke check for Step 10: with degradation disabled (so no node ever
    silently drops out), every victim must produce both an IMU_TILT and an
    IMU_VIBRATION reading on every single cycle.
    """
    sim = SensorSimulator(HIMALAYA_VICTIMS, seed=seed, enable_degradation=False)

    for cycle in range(1, num_cycles + 1):
        readings = sim.generate_cycle()
        by_victim: dict = {}
        for r in readings:
            by_victim.setdefault(r.victim_id, {})[r.sensor_type] = r

        for victim in HIMALAYA_VICTIMS:
            vid = victim.victim_id
            sensors = by_victim.get(vid)
            assert sensors is not None, (
                f"cycle {cycle}: victim {vid} produced no readings at all "
                f"(degradation is disabled, so every node should report)"
            )
            for imu_type in IMU_SENSOR_TYPES:
                assert imu_type in sensors, (
                    f"cycle {cycle}: victim {vid} missing {imu_type.value} reading"
                )

    print(f"OK - {SensorType.IMU_TILT.value}/{SensorType.IMU_VIBRATION.value} "
          f"present every cycle for all {len(HIMALAYA_VICTIMS)} victims "
          f"across {num_cycles} cycles.")


def run_demo(num_cycles: int = 10, seed: int = 7, enable_degradation: bool = True):
    sim = SensorSimulator(HIMALAYA_VICTIMS, seed=seed, enable_degradation=enable_degradation)

    print(f"Simulating {num_cycles} sensor cycles for {len(HIMALAYA_VICTIMS)} victims "
          f"(degradation={'ON' if enable_degradation else 'OFF'})\n")
    print(HEADER)
    print("-" * len(HEADER))

    for cycle in range(1, num_cycles + 1):
        readings = sim.generate_cycle()

        # group this cycle's readings by victim_id
        by_victim: dict = {}
        for r in readings:
            by_victim.setdefault(r.victim_id, {})[r.sensor_type] = r

        for victim in HIMALAYA_VICTIMS:
            vid = victim.victim_id
            sensors = by_victim.get(vid)

            if sensors is None:
                print(f"{cycle:>3} | {vid:<10} | "
                      f"{'--':>10} | {'--':>7} | {'--':>8} | {'--':>9} | "
                      f"{'--':>8} | {'--':>5} | {'--':>5} | DROPPED OUT (signal lost)")
                continue

            thermal = sensors[SensorType.THERMAL_IMAGING]
            motion = sensors[SensorType.PIR_MOTION]
            acoustic = sensors[SensorType.ACOUSTIC]
            co2 = sensors[SensorType.CO2]
            hr = sensors[SensorType.HEART_RATE_RADAR]
            cam = sensors[SensorType.RGB_CAMERA]

            flags = "noisy" if thermal.noisy else ""

            print(f"{cycle:>3} | {vid:<10} | "
                  f"{thermal.value:>10.1f} | {motion.value:>7.2f} | "
                  f"{acoustic.value:>8.1f} | {co2.value:>9.1f} | "
                  f"{hr.value:>8.1f} | {cam.value:>5.2f} | "
                  f"{thermal.confidence:>5.2f} | {flags}")

        print("-" * len(HEADER))

    print("\nFinal battery levels after", num_cycles, "cycles:")
    for vid, pct in sim.battery_report().items():
        print(f"  {vid}: {pct}%")


if __name__ == "__main__":
    run_demo(num_cycles=10, seed=7, enable_degradation=True)
    assert_imu_readings_present_every_cycle(num_cycles=10, seed=7)

