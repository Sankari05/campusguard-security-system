"""
backend/landslide_detector.py
-----------------------------
RIDGEWATCH Mountainous Slope Saturation & Landslide Detection Module.

FUSES:
- Frequency Domain Reflectometry (FDR) volumetric soil saturation (%).
- Multi-Axis Inclinometer (MPU-6050) angular shear drift (degrees & deg/s).
- Cumulative rainfall volume (mm) and antecedent precipitation threshold.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


@dataclass
class LandslideDetectionResult:
    """Structured assessment from slope geotechnical monitoring."""
    risk_score: float = 0.0              # 0.0 - 100.0
    risk_level: str = "LOW"              # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    soil_moisture_pct: float = 0.0
    tilt_angle_deg: float = 0.0
    tilt_rate_deg_s: float = 0.0
    cumulative_rainfall_mm: float = 0.0
    is_triggered: bool = False
    contributing_factors: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ONLINE"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_score": round(self.risk_score, 1),
            "risk_level": self.risk_level,
            "soil_moisture_pct": round(self.soil_moisture_pct, 1),
            "tilt_angle_deg": round(self.tilt_angle_deg, 2),
            "tilt_rate_deg_s": round(self.tilt_rate_deg_s, 3),
            "cumulative_rainfall_mm": round(self.cumulative_rainfall_mm, 1),
            "is_triggered": self.is_triggered,
            "contributing_factors": self.contributing_factors,
            "status": self.status,
            "timestamp": self.timestamp,
        }


class LandslideDetector:
    """Geotechnical slope stability analyzer."""
    def __init__(
        self,
        moisture_threshold_pct: float = 75.0,
        tilt_threshold_deg: float = 15.0,
    ):
        self.moisture_threshold_pct = moisture_threshold_pct
        self.tilt_threshold_deg = tilt_threshold_deg

    def evaluate_slope(
        self,
        soil_moisture_pct: Optional[float],
        tilt_angle_deg: Optional[float],
        tilt_rate_deg_s: float = 0.0,
        cumulative_rainfall_mm: float = 0.0,
        sensor_status: str = "ONLINE",
    ) -> LandslideDetectionResult:
        if soil_moisture_pct is None or tilt_angle_deg is None or sensor_status != "ONLINE":
            return LandslideDetectionResult(
                risk_score=0.0,
                risk_level="UNKNOWN",
                status="OFFLINE" if sensor_status == "OFFLINE" else "UNAVAILABLE",
            )

        factors = []
        # Saturation score (40%)
        m_score = min(100.0, (soil_moisture_pct / self.moisture_threshold_pct) * 100.0)
        factors.append({"factor": "SOIL_SATURATION", "value": f"{soil_moisture_pct:.1f}%", "score": m_score})

        # Tilt shear score (40%)
        t_score = min(100.0, (tilt_angle_deg / self.tilt_threshold_deg) * 100.0)
        if tilt_rate_deg_s > 0.5:
            t_score = min(100.0, t_score + 20.0)
        factors.append({"factor": "STRUCTURAL_TILT", "value": f"{tilt_angle_deg:.1f}°", "score": t_score})

        # Rain accumulation (20%)
        r_score = min(100.0, (cumulative_rainfall_mm / 100.0) * 100.0)
        factors.append({"factor": "CUMULATIVE_RAIN", "value": f"{cumulative_rainfall_mm:.1f} mm", "score": r_score})

        total_score = m_score * 0.40 + t_score * 0.40 + r_score * 0.20
        total_score = min(100.0, max(0.0, total_score))

        if total_score >= 75.0 or tilt_angle_deg >= 20.0:
            level = "CRITICAL"
            triggered = True
        elif total_score >= 50.0:
            level = "HIGH"
            triggered = False
        elif total_score >= 25.0:
            level = "MEDIUM"
            triggered = False
        else:
            level = "LOW"
            triggered = False

        res = LandslideDetectionResult(
            risk_score=total_score,
            risk_level=level,
            soil_moisture_pct=soil_moisture_pct,
            tilt_angle_deg=tilt_angle_deg,
            tilt_rate_deg_s=tilt_rate_deg_s,
            cumulative_rainfall_mm=cumulative_rainfall_mm,
            is_triggered=triggered,
            contributing_factors=factors,
            status=sensor_status,
        )
        self._last_result = res
        return res

    def detect_landslide(
        self,
        soil_moisture_pct: Optional[float] = 40.0,
        tilt_angle_deg: Optional[float] = 0.0,
        cumulative_rainfall_mm: float = 0.0,
    ) -> LandslideDetectionResult:
        return self.evaluate_slope(
            soil_moisture_pct=soil_moisture_pct,
            tilt_angle_deg=tilt_angle_deg,
            cumulative_rainfall_mm=cumulative_rainfall_mm,
        )

    def get_latest_result(self) -> LandslideDetectionResult:
        if not hasattr(self, "_last_result") or self._last_result is None:
            return self.detect_landslide()
        return self._last_result


# Add property to LandslideDetectionResult
LandslideDetectionResult.landslide_detected = property(lambda self: getattr(self, "is_triggered", False) or self.risk_level in ("HIGH", "CRITICAL"))

# Global Singleton
_LANDSLIDE_DETECTOR: Optional[LandslideDetector] = None


def get_landslide_detector() -> LandslideDetector:
    global _LANDSLIDE_DETECTOR
    if _LANDSLIDE_DETECTOR is None:
        _LANDSLIDE_DETECTOR = LandslideDetector()
    return _LANDSLIDE_DETECTOR

