"""
test_road_blockage_and_detour_routing.py
----------------------------------------
Automated test suite for Feature #15: Tactical Road Blockage & Dynamic Detour Routing.

Covers:
- Scenario A: Normal Open Route (all roads safe, primary route selected)
- Scenario B: Single Blocked Bridge (structural tilt 5.2°, dynamic detour selected)
- Scenario C: Multiple Blockages (flood + bridge tilt, multi-hazard avoidance)
- Scenario D: Flooded Underpass (water depth 110 cm, underpass avoidance)
- Scenario E: No Alternative (all outbound corridors blocked, graceful geodesic fallback)
- Scenario F: Hazard Cleared (previous hazards reset, primary route restored)
- Scenario G: Rescuer Movement (live GPS updates re-anchor route start)
- Scenario H: Victim Relocation (target coordinates updates re-anchor route destination)
- Robustness & Edge Cases: Unknown command, missing GPS, outside grid, malformed hazard inputs, API validation
"""

import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.models import GPSCoordinate, HIMALAYA_SITE_ORIGIN
from backend.road_network import (
    TacticalRoadNetwork,
    RoadNode,
    RoadEdge,
    HazardCondition,
    RouteResult,
    global_road_network,
)
from backend.api import app, ALPHA_M001_LATEST_GPS, reset_alpha_m001_telemetry


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Initialize DB and clean state before each test."""
    db.init_db()
    db.seed_builtin_teams()
    db.seed_builtin_scenarios()
    reset_alpha_m001_telemetry()
    yield
    reset_alpha_m001_telemetry()


@pytest.fixture
def test_network():
    """Isolated instance of TacticalRoadNetwork for deterministic unit testing."""
    return TacticalRoadNetwork(origin=HIMALAYA_SITE_ORIGIN)


@pytest.fixture
def client():
    """FastAPI TestClient instance."""
    return TestClient(app)


# ====================================================================== #
# 1. Unit Tests for Topological Graph and Hazard Evaluation
# ====================================================================== #

def test_graph_initialization(test_network):
    """Verify tactical graph builds expected node and edge counts deterministically."""
    assert len(test_network.nodes) >= 15
    assert "NODE_BASE" in test_network.nodes
    assert "NODE_CENTRAL_BRIDGE" in test_network.nodes
    assert "NODE_UNDERPASS" in test_network.nodes
    assert "NODE_N_JUNCTION" in test_network.nodes
    assert "NODE_S_JUNCTION" in test_network.nodes

    # Check bidirectional edges
    assert len(test_network.edges) >= 20
    assert len(test_network.adjacency["NODE_BASE"]) >= 3


def test_nearest_node_snapping(test_network):
    """Verify coordinate snapping locates closest topological node."""
    base_coord = test_network.nodes["NODE_BASE"].coordinate
    snapped = test_network.find_nearest_node(base_coord)
    assert snapped is not None
    assert snapped.node_id == "NODE_BASE"

    # Distant point beyond max threshold
    far_coord = GPSCoordinate(latitude=45.0, longitude=85.0)
    assert test_network.find_nearest_node(far_coord, max_dist_m=500.0) is None


# ====================================================================== #
# 2. Scenario A: Normal Open Route
# ====================================================================== #

def test_scenario_a_normal_open_route(test_network):
    """
    Scenario A: All roads safe.
    Expected: ROUTE_AVAILABLE, ROAD_PRIMARY, shortest mainline corridor selected.
    """
    start = test_network.nodes["NODE_BASE"].coordinate
    target = test_network.nodes["NODE_N_JUNCTION"].coordinate

    result = test_network.calculate_route(
        start_coord=start,
        target_coord=target,
        hazard_state={},  # No hazards
        command_id="CMD-TEST-SCENARIO-A",
        victim_id="VIC-001",
    )

    assert result.routing_mode == "ROAD_PRIMARY"
    assert result.route_status == "ROUTE_AVAILABLE"
    assert result.total_distance_m > 0
    assert result.eta_seconds > 0
    assert len(result.waypoints) >= 3
    assert result.node_ids == ["NODE_BASE", "NODE_CENTRAL_BRIDGE", "NODE_N_JUNCTION"]
    assert len(result.avoided_hazards) == 0
    assert result.warning is None


# ====================================================================== #
# 3. Scenario B: Single Blocked Bridge
# ====================================================================== #

def test_scenario_b_single_blocked_bridge(test_network):
    """
    Scenario B: Central bridge tilt set to 5.2 degrees (threshold >= 3.5°).
    Expected: Bridge edge blocked, DETOUR_DYNAMIC / DETOUR_ACTIVE, avoided hazard recorded.
    """
    start = test_network.nodes["NODE_BASE"].coordinate
    target = test_network.nodes["NODE_N_JUNCTION"].coordinate

    hazard_state = {
        "tilt_deg": 5.2,
        "vibration_mm_s": 2.0,
    }

    result = test_network.calculate_route(
        start_coord=start,
        target_coord=target,
        hazard_state=hazard_state,
        command_id="CMD-TEST-SCENARIO-B",
        victim_id="VIC-002",
    )

    assert result.routing_mode == "DETOUR_DYNAMIC"
    assert result.route_status == "DETOUR_ACTIVE"
    # Bridge should NOT be in the selected route
    assert "NODE_CENTRAL_BRIDGE" not in result.node_ids
    # Detour must bypass via West or East corridor
    assert any(nid in result.node_ids for nid in ["NODE_WEST_CORRIDOR", "NODE_EAST_BYPASS"])
    assert len(result.avoided_hazards) >= 1
    haz = result.avoided_hazards[0]
    assert haz["hazard_type"] == "BRIDGE_STRUCTURAL_COMPROMISE"
    assert "5.2" in haz["description"]


# ====================================================================== #
# 4. Scenario C: Multiple Blockages
# ====================================================================== #

def test_scenario_c_multiple_blockages(test_network):
    """
    Scenario C: Flood (water_level_cm=75) + Bridge tilt (5.2°).
    Expected: Both bridge and underpass/basin blocked, safe tertiary detour route selected, both hazards recorded.
    """
    start = test_network.nodes["NODE_BASE"].coordinate
    target = test_network.nodes["NODE_N_JUNCTION"].coordinate

    hazard_state = {
        "tilt_deg": 5.2,
        "water_level_cm": 75.0,
        "water_flow_mps": 2.1,
    }

    result = test_network.calculate_route(
        start_coord=start,
        target_coord=target,
        hazard_state=hazard_state,
        command_id="CMD-TEST-SCENARIO-C",
        victim_id="VIC-003",
    )

    assert result.routing_mode == "DETOUR_DYNAMIC"
    assert result.route_status == "DETOUR_ACTIVE"
    assert "NODE_CENTRAL_BRIDGE" not in result.node_ids
    assert "NODE_UNDERPASS" not in result.node_ids
    assert len(result.avoided_hazards) >= 2
    hazard_types = {h["hazard_type"] for h in result.avoided_hazards}
    assert "BRIDGE_STRUCTURAL_COMPROMISE" in hazard_types
    assert "CORRIDOR_FLOODED" in hazard_types


# ====================================================================== #
# 5. Scenario D: Flooded Underpass
# ====================================================================== #

def test_scenario_d_flooded_underpass(test_network):
    """
    Scenario D: Water level in underpass reaches 110 cm (threshold > 40 cm).
    Expected: Underpass corridor blocked, alternate route selected.
    """
    start = test_network.nodes["NODE_BASE"].coordinate
    target = test_network.nodes["NODE_S_JUNCTION"].coordinate

    hazard_state = {
        "water_level_cm": 110.0,
        "water_flow_mps": 1.8,
    }

    result = test_network.calculate_route(
        start_coord=start,
        target_coord=target,
        hazard_state=hazard_state,
        command_id="CMD-TEST-SCENARIO-D",
        victim_id="VIC-004",
    )

    assert result.routing_mode == "DETOUR_DYNAMIC"
    assert result.route_status == "DETOUR_ACTIVE"
    assert "NODE_UNDERPASS" not in result.node_ids
    # Must detour via West or East perimeter
    assert any(nid in result.node_ids for nid in ["NODE_SW_TERRACE", "NODE_SE_BASIN", "NODE_WEST_CORRIDOR", "NODE_EAST_BYPASS"])
    assert any(h["hazard_type"] == "CORRIDOR_FLOODED" for h in result.avoided_hazards)


# ====================================================================== #
# 6. Scenario E: No Alternative (All Outbound Corridors Blocked)
# ====================================================================== #

def test_scenario_e_no_alternative_fallback(test_network):
    """
    Scenario E: Block all outbound corridors leaving BASE.
    Expected: NO_VIABLE_ROAD_ROUTE, FALLBACK_DIRECT, warning ALL_ROADS_BLOCKED_BY_DISASTER_HAZARDS.
    """
    start = test_network.nodes["NODE_BASE"].coordinate
    target = test_network.nodes["NODE_N_JUNCTION"].coordinate

    # Block all three outbound corridors from base
    hazard_state = {
        "blocked_edge_ids": ["EDGE_BASE_BRIDGE", "EDGE_BASE_UNDERPASS", "EDGE_BASE_WEST", "EDGE_BASE_EAST"],
        "blocked_reason": "Total sector debris collapse",
    }

    result = test_network.calculate_route(
        start_coord=start,
        target_coord=target,
        hazard_state=hazard_state,
        command_id="CMD-TEST-SCENARIO-E",
        victim_id="VIC-005",
    )

    assert result.routing_mode == "FALLBACK_DIRECT"
    assert result.route_status == "NO_VIABLE_ROAD_ROUTE"
    assert result.warning == "ALL_ROADS_BLOCKED_BY_DISASTER_HAZARDS"
    assert len(result.waypoints) == 2  # Rescuer to target direct
    assert result.total_distance_m > 0
    assert result.eta_seconds > 0


# ====================================================================== #
# 7. Scenario F: Hazard Cleared
# ====================================================================== #

def test_scenario_f_hazard_cleared(test_network):
    """
    Scenario F: Clear previous flood and tilt conditions.
    Expected: Primary corridor becomes available again, status reverts to ROAD_PRIMARY / ROUTE_AVAILABLE.
    """
    start = test_network.nodes["NODE_BASE"].coordinate
    target = test_network.nodes["NODE_N_JUNCTION"].coordinate

    # 1. With active hazard -> Detour
    res_blocked = test_network.calculate_route(
        start_coord=start,
        target_coord=target,
        hazard_state={"tilt_deg": 5.0},
    )
    assert res_blocked.routing_mode == "DETOUR_DYNAMIC"

    # 2. Hazard cleared -> Reverts to primary
    res_cleared = test_network.calculate_route(
        start_coord=start,
        target_coord=target,
        hazard_state={"tilt_deg": 0.0, "water_level_cm": 0.0},
    )
    assert res_cleared.routing_mode == "ROAD_PRIMARY"
    assert res_cleared.route_status == "ROUTE_AVAILABLE"
    assert res_cleared.node_ids == ["NODE_BASE", "NODE_CENTRAL_BRIDGE", "NODE_N_JUNCTION"]
    assert len(res_cleared.avoided_hazards) == 0


# ====================================================================== #
# 8. Scenario G: Rescuer Movement Re-anchoring
# ====================================================================== #

def test_scenario_g_rescuer_movement(test_network):
    """
    Scenario G: Rescuer changes GPS position.
    Expected: Route start waypoints dynamically re-anchor to new rescuer coordinate.
    """
    target = test_network.nodes["NODE_N_JUNCTION"].coordinate

    # Initial rescuer position at BASE
    rescuer_pos_1 = GPSCoordinate(latitude=HIMALAYA_SITE_ORIGIN.latitude, longitude=HIMALAYA_SITE_ORIGIN.longitude)
    res_1 = test_network.calculate_route(start_coord=rescuer_pos_1, target_coord=target)

    # Moved rescuer position near West corridor
    rescuer_pos_2 = GPSCoordinate(
        latitude=HIMALAYA_SITE_ORIGIN.latitude + 0.00010,
        longitude=HIMALAYA_SITE_ORIGIN.longitude - 0.00025,
    )
    res_2 = test_network.calculate_route(start_coord=rescuer_pos_2, target_coord=target)

    assert res_1.waypoints[0]["latitude"] == pytest.approx(rescuer_pos_1.latitude, abs=1e-5)
    assert res_2.waypoints[0]["latitude"] == pytest.approx(rescuer_pos_2.latitude, abs=1e-5)
    assert res_2.node_ids[0] == "NODE_WEST_CORRIDOR"


# ====================================================================== #
# 9. Scenario H: Victim Relocation Re-anchoring
# ====================================================================== #

def test_scenario_h_victim_relocation(test_network):
    """
    Scenario H: Target victim coordinate shifts.
    Expected: Route target dynamically re-anchors to new destination.
    """
    start = test_network.nodes["NODE_BASE"].coordinate

    # Victim in North
    victim_pos_1 = test_network.nodes["NODE_N_JUNCTION"].coordinate
    res_1 = test_network.calculate_route(start_coord=start, target_coord=victim_pos_1)

    # Victim relocated to South Valley
    victim_pos_2 = test_network.nodes["NODE_S_JUNCTION"].coordinate
    res_2 = test_network.calculate_route(start_coord=start, target_coord=victim_pos_2)

    assert res_1.node_ids[-1] == "NODE_N_JUNCTION"
    assert res_2.node_ids[-1] == "NODE_S_JUNCTION"
    assert res_1.waypoints[-1]["latitude"] == pytest.approx(victim_pos_1.latitude, abs=1e-5)
    assert res_2.waypoints[-1]["latitude"] == pytest.approx(victim_pos_2.latitude, abs=1e-5)


# ====================================================================== #
# 10. Robustness, Edge Cases, and Fallback Direct Navigation
# ====================================================================== #

def test_route_outside_tactical_grid_fallback(test_network):
    """Coordinates outside road network bounding box cleanly fall back to direct geodesic navigation."""
    far_start = GPSCoordinate(latitude=35.0000, longitude=80.0000)
    far_target = GPSCoordinate(latitude=35.0050, longitude=80.0050)

    res = test_network.calculate_route(start_coord=far_start, target_coord=far_target)
    assert res.routing_mode == "FALLBACK_DIRECT"
    assert res.route_status == "FALLBACK_DIRECT"
    assert res.warning == "COORDINATES_OUTSIDE_TACTICAL_ROAD_GRID"
    assert len(res.waypoints) == 2
    assert res.total_distance_m > 0


def test_invalid_coordinates_handling(test_network):
    """None or invalid coordinates return safe empty result without throwing exceptions."""
    res = test_network.calculate_route(
        start_coord=None,
        target_coord=GPSCoordinate(latitude=32.3739, longitude=77.2491),
    )
    assert res.routing_mode == "FALLBACK_DIRECT"
    assert res.route_status == "NO_VIABLE_ROAD_ROUTE"
    assert res.warning == "INVALID_GPS_COORDINATES"


def test_landslide_and_toxic_gas_hazards(test_network):
    """Verify landslide risk and toxic gas thresholds trigger proper edge blocks."""
    # Landslide on slope trail
    edge_slope = test_network.edges["EDGE_W_NW"]
    blocked, _, cond = test_network.evaluate_edge_hazard(edge_slope, {"landslide_risk_score": 85.0})
    assert blocked is True
    assert cond.hazard_type == "LANDSLIDE_DEBRIS_FLOW"

    # Toxic gas breach
    edge_normal = test_network.edges["EDGE_BASE_BRIDGE"]
    blocked, _, cond = test_network.evaluate_edge_hazard(edge_normal, {"gas_ppm": 95.0})
    assert blocked is True
    assert cond.hazard_type == "TOXIC_GAS_ATMOSPHERE"


# ====================================================================== #
# 11. Read-Only API Endpoints Verification
# ====================================================================== #

def test_api_get_dispatch_route_unknown_command(client):
    """GET /api/dispatch/route/{unknown_command_id} returns 404 cleanly."""
    res = client.get("/api/dispatch/route/CMD-DOES-NOT-EXIST-999")
    assert res.status_code == 404
    data = res.json()
    assert "not found" in data["detail"].lower()


def test_api_get_dispatch_route_valid_command(client):
    """
    Test GET /api/dispatch/route/{command_id} with created rescue command.
    Ensures read-only route calculation with live ALPHA_M001 GPS integration.
    """
    # 1. Create rescue command in DB
    cmd = db.create_rescue_command(
        command_id="CMD-ROUTE-TEST-001",
        team_id="ALPHA",
        member_id="ALPHA-M001",
        victim_id="VIC-001",
        destination_latitude=HIMALAYA_SITE_ORIGIN.latitude + 0.00050,
        destination_longitude=HIMALAYA_SITE_ORIGIN.longitude,
        destination_label="Sector North",
    )
    assert cmd is not None

    # 2. Inject live ALPHA_M001 GPS telemetry
    ALPHA_M001_LATEST_GPS.update({
        "latitude": HIMALAYA_SITE_ORIGIN.latitude,
        "longitude": HIMALAYA_SITE_ORIGIN.longitude,
        "altitude_m": 3950.0,
        "accuracy_m": 2.5,
        "speed_mps": 1.2,
        "gps_status": "TRACKING",
        "location_source": "PHONE_GPS",
    })

    # 3. Call GET /api/dispatch/route/CMD-ROUTE-TEST-001
    res = client.get("/api/dispatch/route/CMD-ROUTE-TEST-001")
    assert res.status_code == 200
    data = res.json()

    assert data["command_id"] == "CMD-ROUTE-TEST-001"
    assert data["team_id"] == "ALPHA"
    assert data["target_victim_id"] == "VIC-001"
    assert data["routing_mode"] == "ROAD_PRIMARY"
    assert data["route_status"] == "ROUTE_AVAILABLE"
    assert data["total_distance_m"] > 0
    assert data["eta_seconds"] > 0
    assert len(data["waypoints"]) >= 3

    # 4. Call with query parameter hazard override (tilt_deg=5.2) -> DETOUR_DYNAMIC
    res_detour = client.get("/api/dispatch/route/CMD-ROUTE-TEST-001?tilt_deg=5.2")
    assert res_detour.status_code == 200
    data_detour = res_detour.json()
    assert data_detour["routing_mode"] == "DETOUR_DYNAMIC"
    assert data_detour["route_status"] == "DETOUR_ACTIVE"
    assert len(data_detour["avoided_hazards"]) >= 1


def test_api_get_custom_coordinates_route(client):
    """Test GET /api/dispatch/route with arbitrary query coordinates."""
    lat0 = HIMALAYA_SITE_ORIGIN.latitude
    lon0 = HIMALAYA_SITE_ORIGIN.longitude

    url = f"/api/dispatch/route?start_lat={lat0}&start_lon={lon0}&target_lat={lat0 + 0.00050}&target_lon={lon0}&water_level_cm=80.0"
    res = client.get(url)
    assert res.status_code == 200
    data = res.json()
    assert data["total_distance_m"] > 0
    assert len(data["waypoints"]) >= 2
