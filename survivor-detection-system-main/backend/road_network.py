"""
road_network.py
---------------
Tactical Disaster-Zone Road Network & Dynamic Detour Routing Engine for RidgeWatch.

Provides an isolated, in-memory, zero-dependency topological road graph around
disaster site origins. Evaluates real-time multi-sensor hazard overlays (flood depth,
structural bridge tilt, soil landslide risk, debris obstacles) and executes A* shortest-path
detour routing using only Python's standard library (`heapq`, `math`).

Architecture:
- Zero external GIS/graph dependencies (no networkx, scipy, numpy, shapely, geopandas).
- Read-only consumer of existing GPS, water level, tilt, and landslide hazard metrics.
- Seamless fallback to direct geodesic navigation (FALLBACK_DIRECT) if roads are impassable.
- Fully isolated from SMSGate polling, PHONE_GPS ingestion, and survivor fusion logic.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple, Set

from models import GPSCoordinate, HIMALAYA_SITE_ORIGIN
from rescue_dispatch import haversine_distance_m, DEFAULT_TEAM_SPEED_MPS


# --------------------------------------------------------------------------- #
# Data Structures
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class RoadNode:
    node_id: str
    latitude: float
    longitude: float
    name: str
    altitude_m: Optional[float] = 3950.0
    node_type: str = "JUNCTION"  # BASE, JUNCTION, ACCESS, CROSSING, RUBBLE_ZONE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "name": self.name,
            "node_type": self.node_type,
        }

    @property
    def coordinate(self) -> GPSCoordinate:
        return GPSCoordinate(latitude=self.latitude, longitude=self.longitude, altitude_m=self.altitude_m)


@dataclass
class RoadEdge:
    edge_id: str
    source: str
    target: str
    distance_m: float
    name: str
    base_cost_multiplier: float = 1.0
    is_bridge: bool = False
    is_underpass: bool = False
    is_slope: bool = False
    is_bidirectional: bool = True
    speed_limit_mps: float = DEFAULT_TEAM_SPEED_MPS

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HazardCondition:
    hazard_type: str
    severity: str  # WARNING, DANGER, CRITICAL_BLOCKAGE
    description: str
    is_blocking: bool = True
    cost_penalty: float = 1000.0


@dataclass
class RouteResult:
    command_id: Optional[str]
    team_id: Optional[str]
    target_victim_id: Optional[str]
    routing_mode: str          # ROAD_PRIMARY | DETOUR_DYNAMIC | FALLBACK_DIRECT
    route_status: str          # ROUTE_AVAILABLE | DETOUR_ACTIVE | NO_VIABLE_ROAD_ROUTE | FALLBACK_DIRECT
    total_distance_m: float
    eta_seconds: float
    waypoints: List[Dict[str, Any]]
    node_ids: List[str]
    avoided_hazards: List[Dict[str, Any]]
    warning: Optional[str] = None
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "team_id": self.team_id,
            "target_victim_id": self.target_victim_id,
            "routing_mode": self.routing_mode,
            "route_status": self.route_status,
            "total_distance_m": round(self.total_distance_m, 1),
            "eta_seconds": round(self.eta_seconds, 1),
            "eta_minutes": round(self.eta_seconds / 60.0, 2),
            "waypoints": self.waypoints,
            "node_ids": self.node_ids,
            "avoided_hazards": self.avoided_hazards,
            "warning": self.warning,
            "generated_at": self.generated_at,
        }


# --------------------------------------------------------------------------- #
# Tactical Road Network Engine
# --------------------------------------------------------------------------- #

class TacticalRoadNetwork:
    """
    In-memory graph representation of the tactical disaster-zone corridors around SITE_ORIGIN.
    Provides deterministic A* pathfinding, dynamic cost evaluation, and hazard avoidance.
    """

    # Sensor-Driven Hazard Thresholds (strictly matching verified project specifications)
    FLOOD_WATER_BLOCK_CM = 40.0         # Depth > 40cm blocks pedestrian SAR corridor
    FLOOD_FLOW_BLOCK_MPS = 1.5          # Swift water current > 1.5m/s blocks crossing
    BRIDGE_TILT_DANGER_DEG = 3.5        # Inclinometer tilt >= 3.5 deg indicates structural compromise
    SLOPE_LANDSLIDE_RISK_BLOCK = 70.0   # Landslide risk score >= 70 blocks slope trail
    GAS_TOXIC_BLOCK_PPM = 85.0          # Toxic gas PPM >= 85 blocks transit corridor without SCBA

    def __init__(self, origin: Optional[GPSCoordinate] = None):
        self.origin = origin or HIMALAYA_SITE_ORIGIN
        self.nodes: Dict[str, RoadNode] = {}
        self.edges: Dict[str, RoadEdge] = {}
        self.adjacency: Dict[str, List[RoadEdge]] = {}
        self._build_tactical_graph()

    def _build_tactical_graph(self):
        """Constructs a clean 17-node, 24-edge tactical disaster zone network around origin."""
        lat0 = self.origin.latitude   # 32.37390
        lon0 = self.origin.longitude  # 77.24910

        # 1. Nodes definition
        node_defs = [
            # Base & Core Junctions
            ("NODE_BASE", lat0, lon0, "Command Post Base", "BASE"),
            ("NODE_CENTRAL_BRIDGE", lat0 + 0.00015, lon0, "Central Gorge Bridge", "CROSSING"),
            ("NODE_UNDERPASS", lat0 - 0.00020, lon0, "South Valley Underpass", "CROSSING"),
            ("NODE_N_JUNCTION", lat0 + 0.00050, lon0, "North Main Junction", "JUNCTION"),
            ("NODE_S_JUNCTION", lat0 - 0.00050, lon0, "South Valley Junction", "JUNCTION"),

            # West Perimeter & Ridge Paths
            ("NODE_WEST_CORRIDOR", lat0 + 0.00010, lon0 - 0.00025, "West Rubble Corridor", "JUNCTION"),
            ("NODE_W_ENTRY", lat0, lon0 - 0.00050, "West Access Gate", "ACCESS"),
            ("NODE_NW_RIDGE", lat0 + 0.00035, lon0 - 0.00050, "Northwest Ridge Path", "JUNCTION"),
            ("NODE_SW_TERRACE", lat0 - 0.00040, lon0 - 0.00050, "Southwest Terrace", "JUNCTION"),
            ("NODE_WEST_DEBRIS", lat0 - 0.00015, lon0 - 0.00025, "West Debris Sector Delta", "RUBBLE_ZONE"),
            ("NODE_NORTH_DEBRIS", lat0 + 0.00030, lon0 - 0.00010, "North Debris Field Alpha", "RUBBLE_ZONE"),

            # East Perimeter & Ridge Paths
            ("NODE_EAST_BYPASS", lat0 + 0.00010, lon0 + 0.00035, "East Ridge Bypass", "JUNCTION"),
            ("NODE_E_ENTRY", lat0, lon0 + 0.00060, "East Perimeter Access", "ACCESS"),
            ("NODE_NE_SLOPE", lat0 + 0.00045, lon0 + 0.00060, "Northeast Slope Trail", "JUNCTION"),
            ("NODE_SE_BASIN", lat0 - 0.00040, lon0 + 0.00060, "Southeast Basin Road", "JUNCTION"),
            ("NODE_EAST_DEBRIS", lat0 + 0.00025, lon0 + 0.00045, "East Rubble Zone Bravo", "RUBBLE_ZONE"),
            ("NODE_SOUTH_DEBRIS", lat0 - 0.00015, lon0 + 0.00025, "South Debris Sector Charlie", "RUBBLE_ZONE"),
        ]

        self.nodes.clear()
        for nid, nlat, nlon, nname, ntype in node_defs:
            self.nodes[nid] = RoadNode(
                node_id=nid,
                latitude=round(nlat, 6),
                longitude=round(nlon, 6),
                name=nname,
                altitude_m=self.origin.altitude_m,
                node_type=ntype,
            )

        # 2. Edges definition (bidirectional topological connections)
        edge_defs = [
            # Central Primary Corridor (North-South Mainline)
            ("EDGE_BASE_BRIDGE", "NODE_BASE", "NODE_CENTRAL_BRIDGE", "Main Avenue (Bridge Approach)", 1.0, True, False, False),
            ("EDGE_BRIDGE_NORTH", "NODE_CENTRAL_BRIDGE", "NODE_N_JUNCTION", "Main Avenue North", 1.0, True, False, False),
            ("EDGE_BASE_UNDERPASS", "NODE_BASE", "NODE_UNDERPASS", "Main Avenue South (Underpass Approach)", 1.0, False, True, False),
            ("EDGE_UNDERPASS_SOUTH", "NODE_UNDERPASS", "NODE_S_JUNCTION", "Main Avenue South", 1.0, False, True, False),

            # West Primary & Bypass Corridors
            ("EDGE_BASE_WEST", "NODE_BASE", "NODE_WEST_CORRIDOR", "West Central Way", 1.0, False, False, False),
            ("EDGE_WEST_ENTRY", "NODE_WEST_CORRIDOR", "NODE_W_ENTRY", "West Access Link", 1.0, False, False, False),
            ("EDGE_W_NW", "NODE_W_ENTRY", "NODE_NW_RIDGE", "West Ridge Trail", 1.1, False, False, True),
            ("EDGE_NW_NORTH", "NODE_NW_RIDGE", "NODE_N_JUNCTION", "Northwest Ridge Link", 1.1, False, False, True),
            ("EDGE_W_SW", "NODE_W_ENTRY", "NODE_SW_TERRACE", "Southwest Terrace Trail", 1.1, False, False, False),
            ("EDGE_SW_SOUTH", "NODE_SW_TERRACE", "NODE_S_JUNCTION", "Southwest Perimeter Link", 1.1, False, False, False),
            ("EDGE_WEST_DEBRIS_SW", "NODE_WEST_CORRIDOR", "NODE_WEST_DEBRIS", "Sector Delta Access Path", 1.2, False, False, False),
            ("EDGE_DEBRIS_SW_TERRACE", "NODE_WEST_DEBRIS", "NODE_SW_TERRACE", "Delta-Terrace Cut", 1.2, False, False, False),
            ("EDGE_WEST_NORTH_DEBRIS", "NODE_WEST_CORRIDOR", "NODE_NORTH_DEBRIS", "Alpha Sector Connector", 1.2, False, False, False),
            ("EDGE_NORTH_DEBRIS_NW", "NODE_NORTH_DEBRIS", "NODE_NW_RIDGE", "Alpha-Ridge Connector", 1.2, False, False, True),

            # East Primary & Bypass Corridors
            ("EDGE_BASE_EAST", "NODE_BASE", "NODE_EAST_BYPASS", "East Central Way", 1.0, False, False, False),
            ("EDGE_EAST_ENTRY", "NODE_EAST_BYPASS", "NODE_E_ENTRY", "East Access Link", 1.0, False, False, False),
            ("EDGE_E_NE", "NODE_E_ENTRY", "NODE_NE_SLOPE", "East Slope Path", 1.1, False, False, True),
            ("EDGE_NE_NORTH", "NODE_NE_SLOPE", "NODE_N_JUNCTION", "Northeast Ridge Link", 1.1, False, False, True),
            ("EDGE_E_SE", "NODE_E_ENTRY", "NODE_SE_BASIN", "Southeast Basin Trail", 1.1, False, False, False),
            ("EDGE_SE_SOUTH", "NODE_SE_BASIN", "NODE_S_JUNCTION", "Southeast Perimeter Link", 1.1, False, False, False),
            ("EDGE_EAST_DEBRIS_NE", "NODE_EAST_BYPASS", "NODE_EAST_DEBRIS", "Bravo Sector Connector", 1.2, False, False, True),
            ("EDGE_DEBRIS_NE_SLOPE", "NODE_EAST_DEBRIS", "NODE_NE_SLOPE", "Bravo-Slope Cut", 1.2, False, False, True),
            ("EDGE_EAST_SOUTH_DEBRIS", "NODE_EAST_BYPASS", "NODE_SOUTH_DEBRIS", "Charlie Sector Connector", 1.2, False, False, False),
            ("EDGE_DEBRIS_SE_BASIN", "NODE_SOUTH_DEBRIS", "NODE_SE_BASIN", "Charlie-Basin Cut", 1.2, False, False, False),
        ]

        self.edges.clear()
        self.adjacency.clear()
        for nid in self.nodes:
            self.adjacency[nid] = []

        for eid, src, tgt, ename, mult, is_brg, is_und, is_slp in edge_defs:
            n1 = self.nodes[src]
            n2 = self.nodes[tgt]
            dist_m = haversine_distance_m(n1.coordinate, n2.coordinate)
            edge = RoadEdge(
                edge_id=eid,
                source=src,
                target=tgt,
                distance_m=round(dist_m, 2),
                name=ename,
                base_cost_multiplier=mult,
                is_bridge=is_brg,
                is_underpass=is_und,
                is_slope=is_slp,
                is_bidirectional=True,
            )
            self.edges[eid] = edge
            self.adjacency[src].append(edge)

            # Bidirectional reverse edge
            rev_edge = RoadEdge(
                edge_id=f"{eid}_REV",
                source=tgt,
                target=src,
                distance_m=round(dist_m, 2),
                name=f"{ename} (Reverse)",
                base_cost_multiplier=mult,
                is_bridge=is_brg,
                is_underpass=is_und,
                is_slope=is_slp,
                is_bidirectional=True,
            )
            self.adjacency[tgt].append(rev_edge)

    # ----------------------------------------------------------------------- #
    # Hazard Cost & Blocking Evaluation
    # ----------------------------------------------------------------------- #

    def evaluate_edge_hazard(
        self,
        edge: RoadEdge,
        hazard_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, float, Optional[HazardCondition]]:
        """
        Evaluates whether an edge is blocked or degraded by sensor hazard metrics.
        Returns: (is_blocked, cost_multiplier, hazard_condition)
        """
        hazard = hazard_state or {}

        # 1. Direct explicit edge blockage override
        blocked_edges: List[str] = hazard.get("blocked_edge_ids", []) or []
        if edge.edge_id in blocked_edges or edge.edge_id.replace("_REV", "") in blocked_edges:
            desc = hazard.get("blocked_reason", "Corridor manually barricaded / obstructed")
            return (True, float("inf"), HazardCondition("MANUAL_BLOCKAGE", "CRITICAL_BLOCKAGE", desc, True, float("inf")))

        # 2. Bridge Structural Tilt & Vibration Hazard
        if edge.is_bridge:
            tilt_deg = float(hazard.get("tilt_deg", hazard.get("bridge_tilt_deg", 0.0)))
            vib_mm_s = float(hazard.get("vibration_mm_s", 0.0))
            aftershock = bool(hazard.get("aftershock_active", False))

            if tilt_deg >= self.BRIDGE_TILT_DANGER_DEG or (aftershock and tilt_deg >= 2.5):
                cond = HazardCondition(
                    hazard_type="BRIDGE_STRUCTURAL_COMPROMISE",
                    severity="CRITICAL_BLOCKAGE",
                    description=f"Bridge pier tilt shifted to {tilt_deg:.1f}° (danger threshold {self.BRIDGE_TILT_DANGER_DEG}°); high risk of secondary collapse.",
                    is_blocking=True,
                    cost_penalty=float("inf"),
                )
                return (True, float("inf"), cond)
            elif tilt_deg >= 1.5 or vib_mm_s >= 4.0:
                # Degraded transit
                mult = 2.5 * edge.base_cost_multiplier
                cond = HazardCondition(
                    hazard_type="BRIDGE_TILT_WARNING",
                    severity="WARNING",
                    description=f"Minor bridge vibration/tilt ({tilt_deg:.1f}°, {vib_mm_s:.1f} mm/s); transit slowed.",
                    is_blocking=False,
                    cost_penalty=mult,
                )
                return (False, mult, cond)

        # 3. Underpass / Low Basin Hydrostatic Inundation & Current Velocity
        if edge.is_underpass or "BASIN" in edge.name.upper():
            water_lvl = float(hazard.get("water_level_cm", 0.0))
            water_flow = float(hazard.get("water_flow_mps", 0.0))

            if water_lvl >= self.FLOOD_WATER_BLOCK_CM or water_flow >= self.FLOOD_FLOW_BLOCK_MPS:
                cond = HazardCondition(
                    hazard_type="CORRIDOR_FLOODED",
                    severity="CRITICAL_BLOCKAGE",
                    description=f"Underpass submerged: water depth {water_lvl:.1f} cm (limit {self.FLOOD_WATER_BLOCK_CM} cm), current {water_flow:.1f} m/s.",
                    is_blocking=True,
                    cost_penalty=float("inf"),
                )
                return (True, float("inf"), cond)
            elif water_lvl >= 15.0:
                mult = 3.0 * edge.base_cost_multiplier
                cond = HazardCondition(
                    hazard_type="SHALLOW_WATER_CROSSING",
                    severity="WARNING",
                    description=f"Shallow water standing ({water_lvl:.1f} cm); wading transit required.",
                    is_blocking=False,
                    cost_penalty=mult,
                )
                return (False, mult, cond)

        # 4. Slope Trail Saturated Landslide / Mudflow Hazard
        if edge.is_slope:
            soil_pct = float(hazard.get("soil_moisture_pct", 0.0))
            tilt_deg = float(hazard.get("tilt_deg", 0.0))
            landslide_score = float(hazard.get("landslide_risk_score", 0.0))
            rain_rate = float(hazard.get("rainfall_rate_mm_h", hazard.get("rainfall_mm_hr", 0.0)))

            if landslide_score >= self.SLOPE_LANDSLIDE_RISK_BLOCK or (soil_pct >= 80.0 and tilt_deg >= 4.0):
                cond = HazardCondition(
                    hazard_type="LANDSLIDE_DEBRIS_FLOW",
                    severity="CRITICAL_BLOCKAGE",
                    description=f"Slope failure imminent: soil saturation {soil_pct:.1f}%, slope shear {tilt_deg:.1f}°, landslide index {landslide_score:.1f}.",
                    is_blocking=True,
                    cost_penalty=float("inf"),
                )
                return (True, float("inf"), cond)
            elif soil_pct >= 60.0 or rain_rate >= 25.0:
                mult = 2.0 * edge.base_cost_multiplier
                cond = HazardCondition(
                    hazard_type="SLOPE_MUD_HAZARD",
                    severity="WARNING",
                    description=f"Saturated hillside trail ({soil_pct:.1f}% moisture); slipping risk.",
                    is_blocking=False,
                    cost_penalty=mult,
                )
                return (False, mult, cond)

        # 5. Toxic Gas / Chemical Plume Dispersion Hazard
        gas_ppm = float(hazard.get("gas_concentration", hazard.get("gas_ppm", 0.0)))
        smoke_pct = float(hazard.get("smoke_density_pct", hazard.get("smoke_pct", 0.0)))
        if gas_ppm >= self.GAS_TOXIC_BLOCK_PPM or smoke_pct >= 80.0:
            cond = HazardCondition(
                hazard_type="TOXIC_GAS_ATMOSPHERE",
                severity="CRITICAL_BLOCKAGE",
                description=f"Atmospheric toxic gas concentration breach ({gas_ppm:.1f} PPM, smoke {smoke_pct:.1f}%); hot-zone exclusion active.",
                is_blocking=True,
                cost_penalty=float("inf"),
            )
            return (True, float("inf"), cond)
        elif gas_ppm >= 40.0 or smoke_pct >= 40.0:
            mult = 2.5 * edge.base_cost_multiplier
            cond = HazardCondition(
                hazard_type="ELEVATED_SMOKE_HAZMAT",
                severity="WARNING",
                description=f"Dense smoke/fumes ({smoke_pct:.1f}% obscuration); visibility impaired.",
                is_blocking=False,
                cost_penalty=mult,
            )
            return (False, mult, cond)

        # 6. Optical Debris / Structural Obstruction from Drone Camera
        debris_present = bool(hazard.get("debris_present", False))
        if debris_present and "DEBRIS" in edge.name.upper():
            mult = 2.0 * edge.base_cost_multiplier
            cond = HazardCondition(
                hazard_type="DEBRIS_RUBBLE_CONE",
                severity="WARNING",
                description="Optical drone reconnaissance confirmed rubble scatter; scrambling required.",
                is_blocking=False,
                cost_penalty=mult,
            )
            return (False, mult, cond)

        return (False, edge.base_cost_multiplier, None)

    # ----------------------------------------------------------------------- #
    # Geospatial Nearest-Node Snapping
    # ----------------------------------------------------------------------- #

    def find_nearest_node(
        self,
        coord: GPSCoordinate,
        max_dist_m: float = 1500.0,
    ) -> Optional[RoadNode]:
        """Finds the nearest road network node to a given GPS coordinate."""
        if not coord or coord.latitude is None or coord.longitude is None:
            return None

        best_node: Optional[RoadNode] = None
        min_dist = float("inf")

        for node in self.nodes.values():
            d = haversine_distance_m(coord, node.coordinate)
            if d < min_dist:
                min_dist = d
                best_node = node

        if min_dist <= max_dist_m:
            return best_node
        return None

    # ----------------------------------------------------------------------- #
    # A* Pathfinding Algorithm (Zero External Dependencies)
    # ----------------------------------------------------------------------- #

    def _astar_search(
        self,
        start_node_id: str,
        target_node_id: str,
        hazard_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[List[str]], float, List[Dict[str, Any]]]:
        """
        Executes A* search using standard library heapq.
        Returns: (path_node_ids, total_distance_meters, avoided_hazards_list)
        """
        if start_node_id not in self.nodes or target_node_id not in self.nodes:
            return (None, 0.0, [])

        if start_node_id == target_node_id:
            return ([start_node_id], 0.0, [])

        target_node = self.nodes[target_node_id]

        # Priority queue entries: (f_score, counter, current_node_id)
        counter = 0
        open_set: List[Tuple[float, int, str]] = []
        heapq.heappush(open_set, (0.0, counter, start_node_id))

        came_from: Dict[str, str] = {}
        edge_used: Dict[str, RoadEdge] = {}
        g_score: Dict[str, float] = {start_node_id: 0.0}

        avoided_hazards: List[Dict[str, Any]] = []
        observed_hazards: Dict[str, Dict[str, Any]] = {}

        # Pre-scan blocked edges for explainability ledger
        for eid, edge in self.edges.items():
            blocked, _, cond = self.evaluate_edge_hazard(edge, hazard_state)
            if blocked and cond:
                key = f"{edge.source}->{edge.target}"
                if key not in observed_hazards:
                    observed_hazards[key] = {
                        "edge_id": edge.edge_id,
                        "road_name": edge.name,
                        "hazard_type": cond.hazard_type,
                        "severity": cond.severity,
                        "description": cond.description,
                    }

        while open_set:
            _, _, current_id = heapq.heappop(open_set)

            if current_id == target_node_id:
                # Reconstruct path
                path = [current_id]
                curr = current_id
                while curr in came_from:
                    curr = came_from[curr]
                    path.append(curr)
                path.reverse()

                # Calculate true ground distance (without multiplier penalty)
                total_dist = 0.0
                for i in range(len(path) - 1):
                    n1 = self.nodes[path[i]]
                    n2 = self.nodes[path[i + 1]]
                    total_dist += haversine_distance_m(n1.coordinate, n2.coordinate)

                avoided_list = list(observed_hazards.values())
                return (path, round(total_dist, 1), avoided_list)

            for edge in self.adjacency.get(current_id, []):
                neighbor_id = edge.target
                is_blocked, cost_mult, cond = self.evaluate_edge_hazard(edge, hazard_state)

                if is_blocked:
                    continue

                effective_edge_cost = edge.distance_m * cost_mult
                tentative_g = g_score[current_id] + effective_edge_cost

                if tentative_g < g_score.get(neighbor_id, float("inf")):
                    came_from[neighbor_id] = current_id
                    edge_used[neighbor_id] = edge
                    g_score[neighbor_id] = tentative_g

                    # Heuristic: Haversine distance to target
                    neighbor_node = self.nodes[neighbor_id]
                    h = haversine_distance_m(neighbor_node.coordinate, target_node.coordinate)
                    f = tentative_g + h

                    counter += 1
                    heapq.heappush(open_set, (f, counter, neighbor_id))

        # No path found due to total blockage
        return (None, 0.0, list(observed_hazards.values()))

    # ----------------------------------------------------------------------- #
    # Public Routing Engine Surface
    # ----------------------------------------------------------------------- #

    def calculate_route(
        self,
        start_coord: GPSCoordinate,
        target_coord: GPSCoordinate,
        hazard_state: Optional[Dict[str, Any]] = None,
        speed_mps: float = DEFAULT_TEAM_SPEED_MPS,
        command_id: Optional[str] = None,
        team_id: Optional[str] = None,
        victim_id: Optional[str] = None,
    ) -> RouteResult:
        """
        Calculates a dynamic, hazard-aware detour route from start to target coordinate.
        Gracefully falls back to direct geodesic path if the road network is partitioned.
        """
        # 1. Validate inputs
        if (
            not start_coord
            or start_coord.latitude is None
            or start_coord.longitude is None
            or not target_coord
            or target_coord.latitude is None
            or target_coord.longitude is None
        ):
            return RouteResult(
                command_id=command_id,
                team_id=team_id,
                target_victim_id=victim_id,
                routing_mode="FALLBACK_DIRECT",
                route_status="NO_VIABLE_ROAD_ROUTE",
                total_distance_m=0.0,
                eta_seconds=0.0,
                waypoints=[],
                node_ids=[],
                avoided_hazards=[],
                warning="INVALID_GPS_COORDINATES",
            )

        straight_dist_m = haversine_distance_m(start_coord, target_coord)
        speed = speed_mps if speed_mps and speed_mps > 0.1 else DEFAULT_TEAM_SPEED_MPS

        # 2. Find nearest entry and exit nodes
        start_node = self.find_nearest_node(start_coord)
        target_node = self.find_nearest_node(target_coord)

        # Baseline check: is direct baseline path nominal?
        baseline_path, _, _ = self._astar_search(
            start_node.node_id if start_node else "",
            target_node.node_id if target_node else "",
            hazard_state={},  # No hazards
        )

        if not start_node or not target_node:
            # Coordinates outside road network grid -> Direct geodesic fallback
            eta_s = straight_dist_m / speed
            return RouteResult(
                command_id=command_id,
                team_id=team_id,
                target_victim_id=victim_id,
                routing_mode="FALLBACK_DIRECT",
                route_status="FALLBACK_DIRECT",
                total_distance_m=round(straight_dist_m, 1),
                eta_seconds=round(eta_s, 1),
                waypoints=[
                    {"latitude": start_coord.latitude, "longitude": start_coord.longitude, "name": "Rescuer Position"},
                    {"latitude": target_coord.latitude, "longitude": target_coord.longitude, "name": "Target Location"},
                ],
                node_ids=[],
                avoided_hazards=[],
                warning="COORDINATES_OUTSIDE_TACTICAL_ROAD_GRID",
            )

        # 3. Execute A* search with active hazard state
        node_path, graph_dist_m, avoided_hazards = self._astar_search(
            start_node.node_id,
            target_node.node_id,
            hazard_state=hazard_state,
        )

        if not node_path:
            # All paths blocked by disaster hazards -> Graceful geodesic fallback
            eta_s = straight_dist_m / speed
            return RouteResult(
                command_id=command_id,
                team_id=team_id,
                target_victim_id=victim_id,
                routing_mode="FALLBACK_DIRECT",
                route_status="NO_VIABLE_ROAD_ROUTE",
                total_distance_m=round(straight_dist_m, 1),
                eta_seconds=round(eta_s, 1),
                waypoints=[
                    {"latitude": start_coord.latitude, "longitude": start_coord.longitude, "name": "Rescuer Position (Direct Flight)"},
                    {"latitude": target_coord.latitude, "longitude": target_coord.longitude, "name": "Target Location"},
                ],
                node_ids=[],
                avoided_hazards=avoided_hazards,
                warning="ALL_ROADS_BLOCKED_BY_DISASTER_HAZARDS",
            )

        # 4. Construct complete multi-waypoint polyline path
        waypoints: List[Dict[str, Any]] = []

        # Start waypoint (live rescuer position)
        waypoints.append({
            "latitude": round(start_coord.latitude, 6),
            "longitude": round(start_coord.longitude, 6),
            "altitude_m": start_coord.altitude_m,
            "name": "Rescuer Current Position",
            "node_type": "START",
        })

        # Intermediate road graph nodes
        leg_start_dist = haversine_distance_m(start_coord, self.nodes[node_path[0]].coordinate)
        for nid in node_path:
            n = self.nodes[nid]
            waypoints.append({
                "latitude": n.latitude,
                "longitude": n.longitude,
                "altitude_m": n.altitude_m,
                "name": n.name,
                "node_id": n.node_id,
                "node_type": n.node_type,
            })

        leg_end_dist = haversine_distance_m(self.nodes[node_path[-1]].coordinate, target_coord)

        # End waypoint (victim target location)
        waypoints.append({
            "latitude": round(target_coord.latitude, 6),
            "longitude": round(target_coord.longitude, 6),
            "altitude_m": target_coord.altitude_m,
            "name": f"Target Victim ({victim_id or 'Survivor'})",
            "node_type": "TARGET",
        })

        # Total true ground distance = start_leg + graph_distance + target_leg
        total_dist_m = leg_start_dist + graph_dist_m + leg_end_dist
        eta_s = total_dist_m / speed

        # 5. Determine if an active detour was selected
        is_detour = (baseline_path is not None and node_path != baseline_path) or len(avoided_hazards) > 0
        routing_mode = "DETOUR_DYNAMIC" if is_detour else "ROAD_PRIMARY"
        route_status = "DETOUR_ACTIVE" if is_detour else "ROUTE_AVAILABLE"

        return RouteResult(
            command_id=command_id,
            team_id=team_id,
            target_victim_id=victim_id,
            routing_mode=routing_mode,
            route_status=route_status,
            total_distance_m=round(total_dist_m, 1),
            eta_seconds=round(eta_s, 1),
            waypoints=waypoints,
            node_ids=node_path,
            avoided_hazards=avoided_hazards,
            warning=None,
        )


# Global singleton instance
global_road_network = TacticalRoadNetwork()
