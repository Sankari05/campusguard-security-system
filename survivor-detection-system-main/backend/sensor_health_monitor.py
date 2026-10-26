"""
sensor_health_monitor.py
------------------------
Real-Time Sensor Fleet Health, Integrity, and Diagnostics Monitor for RIDGEWATCH.

Monitors non-contact radar/ultrasonic hydrological gauges, soil FDR probes,
MPU-6050 tilt/shear sensors, acoustic/geophone micro-sensors, and rain tipping buckets.

Features:
- Track heartbeat freshness and detect dead-sensor timeout.
- Battery level monitoring and low-voltage alerts.
- Signal quality (RSSI / SNR) tracking.
- Drift detection and frozen-sensor anomaly flagging.
- Comprehensive fleet health index calculation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any


class SensorHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    CRITICAL_BATTERY = "CRITICAL_BATTERY"
    SIGNAL_POOR = "SIGNAL_POOR"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"
    ERROR = "ERROR"
    CALIBRATION = "CALIBRATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class SensorHealthRecord:
    device_id: str
    device_name: str
    sensor_type: str
    hardware_type: str  # HARDWARE_REAL | SIMULATION_ADAPTER
    last_heartbeat_timestamp: str
    last_heartbeat_epoch: float
    battery_volts: float
    battery_percentage: int
    rssi_dbm: int
    snr_db: float
    health_status: SensorHealthStatus
    frozen_reading_counter: int = 0
    consecutive_errors: int = 0
    last_value_recorded: Optional[float] = None
    diagnostics_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["health_status"] = self.health_status.value
        return res


class SensorHealthMonitor:
    """
    Fleet health management engine auditing live sensor streams.
    """

    def __init__(self, stale_timeout_seconds: float = 60.0, offline_timeout_seconds: float = 180.0):
        self.stale_timeout_seconds = stale_timeout_seconds
        self.offline_timeout_seconds = offline_timeout_seconds
        self._registry: Dict[str, SensorHealthRecord] = {}
        self._init_default_fleet()

    def _init_default_fleet(self) -> None:
        """Populates known sensor fleet nodes across the Himalaya / Melamchi flood basin."""
        now_epoch = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        default_devices = [
            ("DEV-WATER-NC01", "Non-Contact Radar Water Level & Hydrostatic Pressure", "RADAR_NON_CONTACT", "SIMULATION_ADAPTER", 3.9, 94, -68, 18.5),
            ("DEV-WATER-US02", "Upstream Ultrasonic Gorge Level Gauge", "ULTRASONIC_NON_CONTACT", "SIMULATION_ADAPTER", 3.8, 88, -72, 16.0),
            ("DEV-RAIN-01", "Tipping Bucket Optical Rain Gauge", "OPTICAL_RAIN", "SIMULATION_ADAPTER", 4.1, 98, -62, 22.0),
            ("DEV-SOIL-FDR01", "Subsurface FDR Moisture & Matric Potential Probe", "FDR_SOIL_MOISTURE", "SIMULATION_ADAPTER", 3.7, 82, -75, 14.2),
            ("DEV-TILT-MPU01", "Slope Inclinometer & Shear Accelerometer", "MPU6050_TILT", "SIMULATION_ADAPTER", 3.8, 86, -70, 15.8),
            ("DEV-GEO-RMB01", "Debris-Flow Acoustic & Geophone Rumble Sensor", "GEOPHONE_DEBRIS", "SIMULATION_ADAPTER", 3.9, 91, -66, 19.4),
        ]

        for dev_id, name, stype, hw_type, v, bat, rssi, snr in default_devices:
            self._registry[dev_id] = SensorHealthRecord(
                device_id=dev_id,
                device_name=name,
                sensor_type=stype,
                hardware_type=hw_type,
                last_heartbeat_timestamp=now_iso,
                last_heartbeat_epoch=now_epoch,
                battery_volts=v,
                battery_percentage=bat,
                rssi_dbm=rssi,
                snr_db=snr,
                health_status=SensorHealthStatus.HEALTHY,
                diagnostics_notes=["Nominal operating condition"],
            )

    def record_heartbeat(
        self,
        device_id: str,
        value: Optional[float] = None,
        battery_volts: Optional[float] = None,
        rssi_dbm: Optional[int] = None,
        is_error: bool = False,
    ) -> SensorHealthRecord:
        """Updates health status on every incoming telemetry packet."""
        now_epoch = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        if device_id not in self._registry:
            self._registry[device_id] = SensorHealthRecord(
                device_id=device_id,
                device_name=f"Sensor Node {device_id}",
                sensor_type="GENERIC_TELEMETRY",
                hardware_type="SIMULATION_ADAPTER",
                last_heartbeat_timestamp=now_iso,
                last_heartbeat_epoch=now_epoch,
                battery_volts=battery_volts or 3.7,
                battery_percentage=85,
                rssi_dbm=rssi_dbm or -70,
                snr_db=15.0,
                health_status=SensorHealthStatus.HEALTHY,
            )

        rec = self._registry[device_id]
        rec.last_heartbeat_epoch = now_epoch
        rec.last_heartbeat_timestamp = now_iso

        if battery_volts is not None:
            rec.battery_volts = battery_volts
            # Approx 3.0V = 0%, 4.2V = 100%
            rec.battery_percentage = max(0, min(100, int((battery_volts - 3.0) / 1.2 * 100)))

        if rssi_dbm is not None:
            rec.rssi_dbm = rssi_dbm

        if is_error:
            rec.consecutive_errors += 1
        else:
            rec.consecutive_errors = 0

        # Check frozen value
        if value is not None:
            if rec.last_value_recorded is not None and abs(value - rec.last_value_recorded) < 1e-5:
                rec.frozen_reading_counter += 1
            else:
                rec.frozen_reading_counter = 0
            rec.last_value_recorded = value

        self._evaluate_health(rec)
        return rec

    def _evaluate_health(self, rec: SensorHealthRecord) -> None:
        """Determines health status based on current diagnostics."""
        notes: List[str] = []
        now = time.time()
        age = now - rec.last_heartbeat_epoch

        if age > self.offline_timeout_seconds:
            rec.health_status = SensorHealthStatus.OFFLINE
            notes.append(f"No heartbeat for {age:.0f}s (Sensor Offline)")
        elif age > self.stale_timeout_seconds:
            rec.health_status = SensorHealthStatus.STALE
            notes.append(f"Heartbeat delayed by {age:.0f}s (Stale stream)")
        elif rec.battery_volts < 3.3 or rec.battery_percentage < 15:
            rec.health_status = SensorHealthStatus.CRITICAL_BATTERY
            notes.append(f"Low battery warning: {rec.battery_volts:.2f}V ({rec.battery_percentage}%)")
        elif rec.rssi_dbm < -95:
            rec.health_status = SensorHealthStatus.SIGNAL_POOR
            notes.append(f"Weak wireless signal: {rec.rssi_dbm} dBm")
        elif rec.frozen_reading_counter > 30:
            rec.health_status = SensorHealthStatus.CALIBRATION_REQUIRED
            notes.append(f"Sensor value unchanged for {rec.frozen_reading_counter} cycles (Potential freeze)")
        elif rec.consecutive_errors > 3:
            rec.health_status = SensorHealthStatus.DEGRADED
            notes.append(f"{rec.consecutive_errors} consecutive transmission/checksum errors")
        else:
            rec.health_status = SensorHealthStatus.HEALTHY
            notes.append("Nominal operating state")

        rec.diagnostics_notes = notes

    def get_fleet_summary(self) -> Dict[str, Any]:
        """Audits all sensors and returns aggregated health overview."""
        now = time.time()
        for rec in self._registry.values():
            self._evaluate_health(rec)

        total = len(self._registry)
        healthy = sum(1 for r in self._registry.values() if r.health_status == SensorHealthStatus.HEALTHY)
        degraded = sum(1 for r in self._registry.values() if r.health_status in (SensorHealthStatus.DEGRADED, SensorHealthStatus.SIGNAL_POOR, SensorHealthStatus.CRITICAL_BATTERY))
        offline = sum(1 for r in self._registry.values() if r.health_status in (SensorHealthStatus.OFFLINE, SensorHealthStatus.STALE))

        health_index = int((healthy / max(1, total)) * 100)

        return {
            "total_sensors": total,
            "healthy_count": healthy,
            "degraded_count": degraded,
            "offline_count": offline,
            "fleet_health_index_pct": health_index,
            "monitored_at": datetime.now(timezone.utc).isoformat(),
            "sensors": [r.to_dict() for r in self._registry.values()],
        }


# Global Singleton
_SENSOR_HEALTH_MONITOR: Optional[SensorHealthMonitor] = None


def get_sensor_health_monitor() -> SensorHealthMonitor:
    global _SENSOR_HEALTH_MONITOR
    if _SENSOR_HEALTH_MONITOR is None:
        _SENSOR_HEALTH_MONITOR = SensorHealthMonitor()
    return _SENSOR_HEALTH_MONITOR
