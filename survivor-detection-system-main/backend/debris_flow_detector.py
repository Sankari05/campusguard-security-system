"""
backend/debris_flow_detector.py
-------------------------------
RIDGEWATCH Mountain Torrential Debris-Flow & Lahar Detection Module.

FUSES:
- River flow speed & acoustic Doppler current profiling (m/s).
- High-frequency seismic/acoustic ground shock vibration (g & dB).
- Sudden river stage drop (upstream damming) followed by sudden surge release.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


@dataclass
class DebrisFlowDetectionResult:
    """Structured assessment from torrential debris flow monitoring."""
    debris_flow_score: float = 0.0      # 0.0 - 100.0
    threat_level: str = "LOW"            # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    flow_velocity_mps: float = 0.0
    ground_vibration_g: float = 0.0
    acoustic_rumble_db: float = 0.0
    channel_damming_detected: bool = False
    contributing_factors: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ONLINE"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "debris_flow_score": round(self.debris_flow_score, 1),
            "threat_level": self.threat_level,
            "flow_velocity_mps": round(self.flow_velocity_mps, 2),
            "ground_vibration_g": round(self.ground_vibration_g, 3),
            "acoustic_rumble_db": round(self.acoustic_rumble_db, 1),
            "channel_damming_detected": self.channel_damming_detected,
            "contributing_factors": self.contributing_factors,
            "status": self.status,
            "timestamp": self.timestamp,
        }


class DebrisFlowDetector:
    """Detects torrential mud, boulder, and tree-trunk debris surges."""
    def __init__(
        self,
        velocity_critical_mps: float = 3.5,
        vibration_critical_g: float = 0.45,
    ):
        self.velocity_critical_mps = velocity_critical_mps
        self.vibration_critical_g = vibration_critical_g

    def evaluate_debris_flow(
        self,
        flow_velocity_mps: Optional[float],
        ground_vibration_g: Optional[float] = 0.0,
        acoustic_db: Optional[float] = 0.0,
        upstream_channel_blocked: bool = False,
        sensor_status: str = "ONLINE",
    ) -> DebrisFlowDetectionResult:
        if flow_velocity_mps is None or sensor_status != "ONLINE":
            return DebrisFlowDetectionResult(
                debris_flow_score=0.0,
                threat_level="UNKNOWN",
                status="OFFLINE" if sensor_status == "OFFLINE" else "UNAVAILABLE",
            )

        v_mps = max(0.0, flow_velocity_mps)
        vib_g = max(0.0, ground_vibration_g or 0.0)
        ac_db = max(0.0, acoustic_db or 0.0)

        factors = []
        # Velocity score (45%)
        vel_score = min(100.0, (v_mps / self.velocity_critical_mps) * 100.0)
        factors.append({"factor": "TORRENT_VELOCITY", "value": f"{v_mps:.2f} m/s", "score": vel_score})

        # Seismic rumble (35%)
        vib_score = min(100.0, (vib_g / self.vibration_critical_g) * 100.0)
        factors.append({"factor": "GROUND_VIBRATION", "value": f"{vib_g:.2f} g", "score": vib_score})

        # Upstream blockage multiplier (20%)
        block_score = 100.0 if upstream_channel_blocked else min(100.0, (ac_db / 75.0) * 50.0)
        factors.append({"factor": "CHANNEL_BLOCKAGE", "value": "BLOCKED" if upstream_channel_blocked else f"{ac_db:.0f} dB", "score": block_score})

        total = vel_score * 0.45 + vib_score * 0.35 + block_score * 0.20
        total = min(100.0, max(0.0, total))

        if total >= 70.0 or (v_mps >= 4.0 and vib_g >= 0.40):
            level = "CRITICAL"
        elif total >= 45.0:
            level = "HIGH"
        elif total >= 25.0:
            level = "MEDIUM"
        else:
            level = "LOW"

        res = DebrisFlowDetectionResult(
            debris_flow_score=total,
            threat_level=level,
            flow_velocity_mps=v_mps,
            ground_vibration_g=vib_g,
            acoustic_rumble_db=ac_db,
            channel_damming_detected=upstream_channel_blocked,
            contributing_factors=factors,
            status=sensor_status,
        )
        self._last_result = res
        return res

    def detect_debris_flow(
        self,
        water_flow_velocity_mps: Optional[float] = 0.5,
        water_depth_m: Optional[float] = 1.0,
        acoustic_rumble_db: Optional[float] = 30.0,
        upstream_channel_blocked: bool = False,
    ) -> DebrisFlowDetectionResult:
        return self.evaluate_debris_flow(
            flow_velocity_mps=water_flow_velocity_mps,
            ground_vibration_g=min(1.0, (acoustic_rumble_db or 30.0) / 100.0),
            acoustic_db=acoustic_rumble_db,
            upstream_channel_blocked=upstream_channel_blocked,
        )

    def get_latest_result(self) -> DebrisFlowDetectionResult:
        if not hasattr(self, "_last_result") or self._last_result is None:
            return self.detect_debris_flow()
        return self._last_result


# Add property to DebrisFlowDetectionResult
DebrisFlowDetectionResult.debris_flow_detected = property(lambda self: getattr(self, "channel_damming_detected", False) or self.threat_level in ("HIGH", "CRITICAL"))

# Global Singleton
_DEBRIS_FLOW_DETECTOR: Optional[DebrisFlowDetector] = None


def get_debris_flow_detector() -> DebrisFlowDetector:
    global _DEBRIS_FLOW_DETECTOR
    if _DEBRIS_FLOW_DETECTOR is None:
        _DEBRIS_FLOW_DETECTOR = DebrisFlowDetector()
    return _DEBRIS_FLOW_DETECTOR

