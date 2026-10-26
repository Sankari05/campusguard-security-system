"""
evacuation_engine.py
--------------------
Real-Time Dynamic Flood & Debris-Flow Evacuation Routing Engine for RIDGEWATCH.

Designed for severe Nepal-style flash-flood emergencies (e.g. Melamchi & Seti River surges).
Identifies high-risk inundation zones, low-lying river basins, and compromised bridges.
Computes safe routes to high-ground assembly points, evaluates time-to-inundation, and
generates clear tactical evacuation recommendations.

Zero external GIS dependencies (uses pure Python math and topological graph nodes).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

from models import GPSCoordinate, HIMALAYA_SITE_ORIGIN
from rescue_dispatch import haversine_distance_m
from road_network import (
    TacticalRoadNetwork,
    RoadNode,
    global_road_network,
    HazardCondition,
)
from flood_intelligence_engine import (
    FloodRiskLevel,
    FloodIntelligenceReport,
    FloodRiskAssessment,
)


class ZoneDangerLevel(str, Enum):
    EXTREME_DANGER = "EXTREME_DANGER"
    HIGH_RISK = "HIGH_RISK"
    CAUTION = "CAUTION"
    SAFE = "SAFE"


class RouteSafetyConfidence(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    ROUTE_SAFETY_UNVERIFIED = "ROUTE_SAFETY_UNVERIFIED"


@dataclass
class SafeAssemblyPoint:
    point_id: str
    name: str
    latitude: float
    longitude: float
    altitude_m: float
    capacity: int
    current_occupancy: int = 0
    shelter_type: str = "HIGH_GROUND_RIDGE"  # HIGH_GROUND_RIDGE, ELEVATED_SHELTER, HELIPAD, COMMUNITY_HALL
    is_accessible: bool = True
    medical_support_available: bool = True
    food_water_supply: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def coordinate(self) -> GPSCoordinate:
        return GPSCoordinate(latitude=self.latitude, longitude=self.longitude, altitude_m=self.altitude_m)


@dataclass
class InundationDangerZone:
    zone_id: str
    name: str
    center_latitude: float
    center_longitude: float
    radius_m: float
    base_altitude_m: float
    danger_level: ZoneDangerLevel
    estimated_population: int
    time_to_inundation_minutes: Optional[float] = None
    critical_depth_threshold_m: float = 1.5
    current_water_depth_m: float = 0.0
    hazard_factors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["danger_level"] = self.danger_level.value
        return res


@dataclass
class EvacuationRouteRecommendation:
    recommendation_id: str
    zone_id: str
    zone_name: str
    recommended_assembly_point: SafeAssemblyPoint
    route_safety_confidence: RouteSafetyConfidence
    urgency: str  # IMMEDIATE_EVACUATION, PREPARE_EVACUATION, MONITOR, SAFE
    estimated_transit_minutes: float
    time_to_inundation_minutes: Optional[float]
    safety_margin_minutes: Optional[float]
    waypoints: List[Dict[str, Any]]
    avoided_hazards: List[str]
    tactical_instructions: List[str]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "recommended_assembly_point": self.recommended_assembly_point.to_dict(),
            "route_safety_confidence": self.route_safety_confidence.value,
            "urgency": self.urgency,
            "estimated_transit_minutes": round(self.estimated_transit_minutes, 1),
            "time_to_inundation_minutes": (
                round(self.time_to_inundation_minutes, 1)
                if self.time_to_inundation_minutes is not None
                else None
            ),
            "safety_margin_minutes": (
                round(self.safety_margin_minutes, 1)
                if self.safety_margin_minutes is not None
                else None
            ),
            "waypoints": self.waypoints,
            "avoided_hazards": self.avoided_hazards,
            "tactical_instructions": self.tactical_instructions,
            "generated_at": self.generated_at,
        }


# --------------------------------------------------------------------------- #
# Predefined High-Ground Assembly Points & Danger Basins (Nepal/Melamchi Area)
# --------------------------------------------------------------------------- #

DEFAULT_ASSEMBLY_POINTS = [
    SafeAssemblyPoint(
        point_id="SAP-01",
        name="Melamchi Upper Ridge Refuge (Elev. 4,120m)",
        latitude=HIMALAYA_SITE_ORIGIN.latitude + 0.0040,
        longitude=HIMALAYA_SITE_ORIGIN.longitude + 0.0035,
        altitude_m=4120.0,
        capacity=250,
        shelter_type="HIGH_GROUND_RIDGE",
        medical_support_available=True,
    ),
    SafeAssemblyPoint(
        point_id="SAP-02",
        name="Helambu Elevated Community Center (Elev. 4,050m)",
        latitude=HIMALAYA_SITE_ORIGIN.latitude + 0.0020,
        longitude=HIMALAYA_SITE_ORIGIN.longitude - 0.0040,
        altitude_m=4050.0,
        capacity=180,
        shelter_type="ELEVATED_SHELTER",
        medical_support_available=True,
    ),
    SafeAssemblyPoint(
        point_id="SAP-03",
        name="Kodari High Helipad & Emergency Base (Elev. 4,200m)",
        latitude=HIMALAYA_SITE_ORIGIN.latitude + 0.0065,
        longitude=HIMALAYA_SITE_ORIGIN.longitude - 0.0010,
        altitude_m=4200.0,
        capacity=100,
        shelter_type="HELIPAD",
        medical_support_available=True,
    ),
]

DEFAULT_DANGER_ZONES = [
    InundationDangerZone(
        zone_id="ZONE-RIVERBANK-01",
        name="Melamchi River Low-Lying Basin",
        center_latitude=HIMALAYA_SITE_ORIGIN.latitude - 0.0010,
        center_longitude=HIMALAYA_SITE_ORIGIN.longitude + 0.0005,
        radius_m=350.0,
        base_altitude_m=3880.0,
        danger_level=ZoneDangerLevel.HIGH_RISK,
        estimated_population=120,
        critical_depth_threshold_m=1.2,
    ),
    InundationDangerZone(
        zone_id="ZONE-BRIDGE-UNDERPASS-02",
        name="Valley Bridge Underpass & Confluence",
        center_latitude=HIMALAYA_SITE_ORIGIN.latitude + 0.0005,
        center_longitude=HIMALAYA_SITE_ORIGIN.longitude - 0.0015,
        radius_m=200.0,
        base_altitude_m=3865.0,
        danger_level=ZoneDangerLevel.EXTREME_DANGER,
        estimated_population=45,
        critical_depth_threshold_m=0.8,
    ),
    InundationDangerZone(
        zone_id="ZONE-DEBRIS-FAN-03",
        name="Upper Torrent Alluvial Fan",
        center_latitude=HIMALAYA_SITE_ORIGIN.latitude + 0.0025,
        center_longitude=HIMALAYA_SITE_ORIGIN.longitude + 0.0010,
        radius_m=300.0,
        base_altitude_m=3920.0,
        danger_level=ZoneDangerLevel.CAUTION,
        estimated_population=60,
        critical_depth_threshold_m=1.5,
    ),
]


# --------------------------------------------------------------------------- #
# Evacuation Engine
# --------------------------------------------------------------------------- #

class EvacuationEngine:
    """
    Evaluates real-time flood/landslide telemetry against known population zones
    and road graphs to generate actionable, safe evacuation plans.
    """

    def __init__(
        self,
        assembly_points: Optional[List[SafeAssemblyPoint]] = None,
        danger_zones: Optional[List[InundationDangerZone]] = None,
        road_graph: Optional[TacticalRoadNetwork] = None,
    ):
        self.assembly_points = assembly_points or list(DEFAULT_ASSEMBLY_POINTS)
        self.danger_zones = danger_zones or list(DEFAULT_DANGER_ZONES)
        self.road_graph = road_graph or global_road_network

    def evaluate_evacuation_plan(
        self,
        flood_report: Optional[FloodIntelligenceReport] = None,
        landslide_active: bool = False,
        debris_flow_active: bool = False,
    ) -> List[EvacuationRouteRecommendation]:
        """
        Calculates dynamic evacuation recommendations for all monitored zones.
        """
        recommendations: List[EvacuationRouteRecommendation] = []
        now_str = datetime.now(timezone.utc).isoformat()

        # Extract current flood telemetry
        water_depth_m = 0.0
        rise_rate_mps = 0.0
        flood_level = FloodRiskLevel.NORMAL
        if flood_report and flood_report.current_assessment:
            water_depth_m = flood_report.current_assessment.water_depth_m
            rise_rate_mps = flood_report.current_assessment.rise_rate_mps
            flood_level = flood_report.current_assessment.risk_level

        for zone in self.danger_zones:
            zone_current_depth = max(0.0, water_depth_m)
            zone.current_water_depth_m = zone_current_depth

            # Calculate time to inundation
            time_to_inundation_min: Optional[float] = None
            if rise_rate_mps > 0.001:
                depth_remaining = max(0.0, zone.critical_depth_threshold_m - zone_current_depth)
                rise_rate_mpm = rise_rate_mps * 60.0
                time_to_inundation_min = max(0.1, depth_remaining / rise_rate_mpm)
            elif zone_current_depth >= zone.critical_depth_threshold_m:
                time_to_inundation_min = 0.0

            zone.time_to_inundation_minutes = time_to_inundation_min

            # Determine Zone Danger Level
            hazard_factors: List[str] = []
            if flood_level == FloodRiskLevel.CRITICAL or zone_current_depth >= zone.critical_depth_threshold_m:
                danger_level = ZoneDangerLevel.EXTREME_DANGER
                hazard_factors.append(f"Inundation depth {zone_current_depth:.2f}m exceeds critical threshold")
            elif flood_level == FloodRiskLevel.WARNING or (time_to_inundation_min is not None and time_to_inundation_min < 20.0):
                danger_level = ZoneDangerLevel.HIGH_RISK
                hazard_factors.append(f"Rapid water level rise ({rise_rate_mps*60:.2f} m/min)")
            elif flood_level == FloodRiskLevel.WATCH or debris_flow_active or landslide_active:
                danger_level = ZoneDangerLevel.CAUTION
                if debris_flow_active:
                    hazard_factors.append("Debris flow upstream channel activity detected")
                if landslide_active:
                    hazard_factors.append("Saturated slope shear movement detected")
            else:
                danger_level = ZoneDangerLevel.SAFE

            zone.danger_level = danger_level
            zone.hazard_factors = hazard_factors

            # Select Best Assembly Point (highest altitude and closest accessible)
            zone_coord = GPSCoordinate(latitude=zone.center_latitude, longitude=zone.center_longitude, altitude_m=zone.base_altitude_m)
            best_point = self._select_best_assembly_point(zone_coord)

            # Determine Route Safety & Routing Waypoints
            confidence, waypoints, avoided, transit_min = self._compute_evacuation_path(
                zone_coord, best_point, flood_level, debris_flow_active
            )

            # Calculate Safety Margin (Time to Inundation - Transit Time)
            safety_margin_min: Optional[float] = None
            if time_to_inundation_min is not None:
                safety_margin_min = time_to_inundation_min - transit_min

            # Tactical Instructions
            instructions = self._generate_instructions(
                zone, best_point, danger_level, safety_margin_min, avoided
            )

            # Determine Urgency
            if danger_level == ZoneDangerLevel.EXTREME_DANGER or (safety_margin_min is not None and safety_margin_min <= 5.0):
                urgency = "IMMEDIATE_EVACUATION"
            elif danger_level == ZoneDangerLevel.HIGH_RISK:
                urgency = "HIGH_PRIORITY_EVACUATION"
            elif danger_level == ZoneDangerLevel.CAUTION:
                urgency = "PREPARE_EVACUATION"
            else:
                urgency = "MONITOR_CONDITIONS"

            rec = EvacuationRouteRecommendation(
                recommendation_id=f"EVAC-{zone.zone_id}-{datetime.now(timezone.utc).strftime('%H%M%S')}",
                zone_id=zone.zone_id,
                zone_name=zone.name,
                recommended_assembly_point=best_point,
                route_safety_confidence=confidence,
                urgency=urgency,
                estimated_transit_minutes=transit_min,
                time_to_inundation_minutes=time_to_inundation_min,
                safety_margin_minutes=safety_margin_min,
                waypoints=waypoints,
                avoided_hazards=avoided,
                tactical_instructions=instructions,
                generated_at=now_str,
            )
            recommendations.append(rec)

        return recommendations

    def _select_best_assembly_point(self, origin: GPSCoordinate) -> SafeAssemblyPoint:
        """Chooses the safest accessible high-ground assembly point minimizing distance and maximizing elevation."""
        accessible_points = [p for p in self.assembly_points if p.is_accessible]
        if not accessible_points:
            accessible_points = self.assembly_points

        # Score by distance (lower is better) and altitude (higher is better)
        best_p = accessible_points[0]
        best_score = float("inf")

        for p in accessible_points:
            dist = haversine_distance_m(origin, p.coordinate)
            alt_bonus = (p.altitude_m - origin.altitude_m) if origin.altitude_m else 0.0
            # Normalize score: distance in meters minus 2x elevation gain in meters
            score = dist - (max(0.0, alt_bonus) * 2.0)
            if score < best_score:
                best_score = score
                best_p = p

        return best_p

    def _compute_evacuation_path(
        self,
        origin: GPSCoordinate,
        destination: SafeAssemblyPoint,
        flood_level: FloodRiskLevel,
        debris_flow_active: bool,
    ) -> Tuple[RouteSafetyConfidence, List[Dict[str, Any]], List[str], float]:
        """
        Uses road graph to find safe topological path, avoiding inundated roads and bridge choke points.
        """
        avoided: List[str] = []
        if flood_level in (FloodRiskLevel.WARNING, FloodRiskLevel.CRITICAL):
            avoided.append("Melamchi Low-Basin Bridge (Flood Risk)")
        if debris_flow_active:
            avoided.append("Upper Torrent Gully Road (Debris Risk)")

        # Attempt A* route via road graph
        try:
            hazard_state = {}
            if flood_level in (FloodRiskLevel.WARNING, FloodRiskLevel.CRITICAL):
                hazard_state["water_level_cm"] = 80.0
            if debris_flow_active:
                hazard_state["debris_present"] = True

            route_res = self.road_graph.calculate_route(
                start_coord=origin,
                target_coord=destination.coordinate,
                hazard_state=hazard_state,
            )
            if route_res and route_res.route_status in ("ROUTE_AVAILABLE", "DETOUR_ACTIVE"):
                waypoints = route_res.waypoints
                transit_min = (route_res.total_distance_m / 0.8) / 60.0  # Walking speed ~ 0.8 m/s
                confidence = RouteSafetyConfidence.HIGH
                if route_res.route_status == "DETOUR_ACTIVE":
                    confidence = RouteSafetyConfidence.MODERATE
                    for h in route_res.avoided_hazards:
                        avoided.append(f"Avoided: {h.get('description', 'Hazard zone')}")
                return confidence, waypoints, avoided, max(1.0, transit_min)
        except Exception:
            pass

        # Fallback Direct Ridge Line Navigation
        dist_m = haversine_distance_m(origin, destination.coordinate)
        transit_min = (dist_m / 0.6) / 60.0  # Conservative mountain ridge speed 0.6 m/s
        waypoints = [
            {"latitude": origin.latitude, "longitude": origin.longitude, "name": "Zone Origin"},
            {
                "latitude": (origin.latitude + destination.latitude) / 2.0,
                "longitude": (origin.longitude + destination.longitude) / 2.0,
                "name": "High Ridge Ascent Waypoint",
            },
            {"latitude": destination.latitude, "longitude": destination.longitude, "name": destination.name},
        ]
        return RouteSafetyConfidence.ROUTE_SAFETY_UNVERIFIED, waypoints, avoided, max(2.0, transit_min)

    def _generate_instructions(
        self,
        zone: InundationDangerZone,
        point: SafeAssemblyPoint,
        danger_level: ZoneDangerLevel,
        safety_margin_min: Optional[float],
        avoided: List[str],
    ) -> List[str]:
        instructions: List[str] = []

        if danger_level == ZoneDangerLevel.EXTREME_DANGER:
            instructions.append(f"CRITICAL: Immediate evacuation required for {zone.name}.")
            instructions.append(f"Move directly toward {point.name} on high ground.")
        elif danger_level == ZoneDangerLevel.HIGH_RISK:
            instructions.append(f"WARNING: High flood risk in {zone.name}.")
            instructions.append(f"Proceed to elevated refuge at {point.name}.")
        else:
            instructions.append(f"ADVISORY: Monitor water levels in {zone.name}.")

        if safety_margin_min is not None:
            if safety_margin_min <= 5.0:
                instructions.append(f"EXTREME URGENCY: Estimated safety margin is only {safety_margin_min:.1f} minutes!")
            else:
                instructions.append(f"Estimated safety margin: {safety_margin_min:.1f} minutes before critical inundation.")

        if avoided:
            for item in avoided:
                instructions.append(f"DO NOT USE: {item}")

        instructions.append("Bring essential emergency kit, stay on designated ridge trails, and avoid riverbank crossings.")
        return instructions


# Global Singleton
_EVACUATION_ENGINE: Optional[EvacuationEngine] = None


def get_evacuation_engine() -> EvacuationEngine:
    global _EVACUATION_ENGINE
    if _EVACUATION_ENGINE is None:
        _EVACUATION_ENGINE = EvacuationEngine()
    return _EVACUATION_ENGINE
