"""
test_commander_map.py
---------------------
Automated test suite for Commander Site Map / GPS Map navigation:
- Initial map container dimensions & layout integrity.
- Deep Map Exploration mode controls (HUD, badge, zoom, pan, fit all, reset).
- World-to-screen coordinate projection and stability.
- Off-screen entity visibility test (top-left, top-right, bottom-left, bottom-right, center, far outside).
- FIT ALL bounding box solver bringing all entities into view.
- RESET view restoring default origin.
- Interaction with backend /commander/overview endpoint.
"""

import os
import math
import pytest
from fastapi.testclient import TestClient
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from api import app

client = TestClient(app)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COMMANDER_HTML_PATH = os.path.join(REPO_ROOT, "frontend", "commander.html")
COMMANDER_JS_PATH = os.path.join(REPO_ROOT, "frontend", "js", "commander.js")
STYLE_CSS_PATH = os.path.join(REPO_ROOT, "frontend", "css", "style.css")


def test_commander_html_map_structure_and_controls():
    """Verify commander.html contains map wrapper, deep mode badge, HUD buttons, and popover."""
    assert os.path.exists(COMMANDER_HTML_PATH)
    with open(COMMANDER_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # Verify panel and SVG
    assert 'class="panel commander-map-panel"' in html
    assert 'id="cmdMap"' in html
    assert 'viewBox="0 0 600 600"' in html

    # Verify deep mode wrap and badge
    assert 'id="cmdMapWrap"' in html
    assert 'id="cmdDeepBadge"' in html
    assert "DEEP MAP MODE" in html

    # Verify HUD navigation buttons
    assert 'id="btnCmdZoomIn"' in html
    assert 'id="btnCmdZoomOut"' in html
    assert 'id="btnCmdFitAll"' in html
    assert 'id="btnCmdReset"' in html
    assert 'id="btnCmdExitDeep"' in html

    # Verify coordinates & zoom readout
    assert 'id="cmdMapCoordsBar"' in html
    assert 'id="cmdCoordsText"' in html
    assert 'id="cmdZoomText"' in html

    # Verify detail popover card
    assert 'id="cmdMapPopover"' in html
    assert 'id="popoverTitle"' in html
    assert 'id="popoverBody"' in html
    assert 'id="btnPopoverClose"' in html


def test_commander_css_classes():
    """Verify style.css contains styles for deep map mode, HUD, and pin animations."""
    assert os.path.exists(STYLE_CSS_PATH)
    with open(STYLE_CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".cmd-map-wrap" in css
    assert ".cmd-map-wrap.is-deep-mode" in css
    assert ".cmd-deep-badge" in css
    assert ".cmd-map-hud" in css
    assert ".cmd-hud-btn" in css
    assert ".cmd-map-coords-bar" in css
    assert ".cmd-map-popover" in css
    assert ".cmd-victim-pin" in css
    assert ".cmd-member-pin" in css


def test_world_to_screen_coordinate_projection_model():
    """
    Mathematical verification of coordinate projection:
    - Base origin: (32.3739, 77.2491) -> World SVG (300, 300)
    - World coordinates remain invariant when zooming or panning.
    - Screen projection: screenX = 300 + (worldX - 300) * zoom + panX.
    """
    site_origin = {"latitude": 32.3739, "longitude": 77.2491}
    meters_per_deg_lat = 111320
    lat_rad = (site_origin["latitude"] * math.pi) / 180
    meters_per_deg_lon = meters_per_deg_lat * math.cos(lat_rad)
    map_size = 600
    map_meters_span = 180
    scale = map_size / map_meters_span  # 3.3333 px/m

    def loc_to_world_svg(loc):
        d_lat = loc["latitude"] - site_origin["latitude"]
        d_lon = loc["longitude"] - site_origin["longitude"]
        east_m = d_lon * meters_per_deg_lon
        north_m = d_lat * meters_per_deg_lat
        return {
            "x": map_size / 2 + east_m * scale,
            "y": map_size / 2 - north_m * scale,
            "east_m": east_m,
            "north_m": north_m,
        }

    def world_to_screen(world_pt, zoom, pan_x, pan_y):
        return {
            "x": 300 + (world_pt["x"] - 300) * zoom + pan_x,
            "y": 300 + (world_pt["y"] - 300) * zoom + pan_y,
        }

    # 1. Origin point
    origin_world = loc_to_world_svg(site_origin)
    assert abs(origin_world["x"] - 300.0) < 1e-6
    assert abs(origin_world["y"] - 300.0) < 1e-6

    # 2. Point 30m East, 45m North (inside base 180m span)
    pt_inside = {
        "latitude": site_origin["latitude"] + (45.0 / meters_per_deg_lat),
        "longitude": site_origin["longitude"] + (30.0 / meters_per_deg_lon),
    }
    w_inside = loc_to_world_svg(pt_inside)
    assert abs(w_inside["x"] - (300 + 30 * scale)) < 1e-4
    assert abs(w_inside["y"] - (300 - 45 * scale)) < 1e-4
    assert 0 <= w_inside["x"] <= 600
    assert 0 <= w_inside["y"] <= 600

    # 3. Point 200m East, -150m North (outside base 180m span)
    pt_outside = {
        "latitude": site_origin["latitude"] - (150.0 / meters_per_deg_lat),
        "longitude": site_origin["longitude"] + (200.0 / meters_per_deg_lon),
    }
    w_outside = loc_to_world_svg(pt_outside)
    # Outside [0, 600] in base view
    assert w_outside["x"] > 600
    assert w_outside["y"] > 600

    # 4. Pan to bring outside entity to center: pan_x = -(w_outside.x - 300), pan_y = -(w_outside.y - 300)
    pan_x = -(w_outside["x"] - 300)
    pan_y = -(w_outside["y"] - 300)
    s_panned = world_to_screen(w_outside, zoom=1.0, pan_x=pan_x, pan_y=pan_y)
    assert abs(s_panned["x"] - 300.0) < 1e-6
    assert abs(s_panned["y"] - 300.0) < 1e-6


def test_fit_all_solver_with_distributed_and_offscreen_entities():
    """
    Test scenario where entities are positioned:
    - Top-left (-70m East, +70m North)
    - Top-right (+70m East, +70m North)
    - Bottom-left (-70m East, -70m North)
    - Bottom-right (+70m East, -70m North)
    - Center (0, 0)
    - Far outside (+350m East, -280m North)
    Verify that FIT ALL calculates zoom and pan such that ALL entities are within [20, 580] screen bounds.
    """
    scale = 600.0 / 180.0  # 3.3333

    entities = [
        {"name": "Center Base", "x": 300.0, "y": 300.0},
        {"name": "Top-Left Victim V1", "x": 300.0 - 70.0 * scale, "y": 300.0 - 70.0 * scale},
        {"name": "Top-Right Victim V2", "x": 300.0 + 70.0 * scale, "y": 300.0 - 70.0 * scale},
        {"name": "Bottom-Left Member A1", "x": 300.0 - 70.0 * scale, "y": 300.0 + 70.0 * scale},
        {"name": "Bottom-Right Member B1", "x": 300.0 + 70.0 * scale, "y": 300.0 + 70.0 * scale},
        {"name": "Far-Outside Hazard H1", "x": 300.0 + 350.0 * scale, "y": 300.0 + 280.0 * scale},
    ]

    # Initial default view: zoom = 1.0, pan = (0, 0)
    # The far outside entity is well outside [0, 600]
    assert entities[-1]["x"] > 600.0
    assert entities[-1]["y"] > 600.0

    # Execute FIT ALL algorithm
    min_x = min(e["x"] for e in entities) - 60
    max_x = max(e["x"] for e in entities) + 60
    min_y = min(e["y"] for e in entities) - 60
    max_y = max(e["y"] for e in entities) + 60

    bbox_w = max_x - min_x
    bbox_h = max_y - min_y
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0

    target_zoom = min(600.0 / bbox_w, 600.0 / bbox_h, 2.5)
    pan_x = -(center_x - 300.0) * target_zoom
    pan_y = -(center_y - 300.0) * target_zoom

    # Verify that every entity is now strictly inside [20, 580] screen bounds
    for e in entities:
        screen_x = 300.0 + (e["x"] - 300.0) * target_zoom + pan_x
        screen_y = 300.0 + (e["y"] - 300.0) * target_zoom + pan_y
        assert 20.0 <= screen_x <= 580.0, f"{e['name']} screenX={screen_x} outside [20, 580]"
        assert 20.0 <= screen_y <= 580.0, f"{e['name']} screenY={screen_y} outside [20, 580]"


def test_commander_api_endpoint_overview():
    """Verify GET /commander/overview returns valid scenario, victims, members, and jobs data."""
    # Start default scenario if needed
    client.post("/scenario/start", json={"scenario_id": "himalaya_avalanche"})

    res = client.get("/commander/overview")
    assert res.status_code == 200
    data = res.json()

    assert "scenario" in data
    assert "victims" in data
    assert "team_members" in data
    assert "jobs" in data
    assert isinstance(data["victims"], list)
    assert isinstance(data["team_members"], list)

    # Check scenario origin
    if data.get("scenario") and data["scenario"].get("site_origin"):
        origin = data["scenario"]["site_origin"]
        assert "latitude" in origin
        assert "longitude" in origin
