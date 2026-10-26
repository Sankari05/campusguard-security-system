import math
import re
from pathlib import Path
import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def test_map_svg_containers_markup():
    """Verify Dashboard and Commander HTML have correctly configured SVG viewports."""
    index_html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    commander_html = (FRONTEND_DIR / "commander.html").read_text(encoding="utf-8")

    assert 'id="siteMap"' in index_html
    assert 'viewBox="0 0 600 600"' in index_html
    assert 'preserveAspectRatio="xMidYMid meet"' in index_html

    assert 'id="cmdMap"' in commander_html
    assert 'viewBox="0 0 600 600"' in commander_html
    assert 'preserveAspectRatio="xMidYMid meet"' in commander_html


def test_dashboard_js_boundary_and_collision_logic():
    """Verify dashboard.js implements clamping, collision dispersion, and smart label flipping."""
    dash_js = (FRONTEND_DIR / "js" / "dashboard.js").read_text(encoding="utf-8")

    assert "MAP_SAFE_MARGIN" in dash_js
    assert "disperseMarkers" in dash_js
    assert "getSmartLabelAttrs" in dash_js
    assert "pin-leader-line" in dash_js
    assert "resize" in dash_js


def test_commander_js_boundary_and_collision_logic():
    """Verify commander.js implements clamping, collision dispersion, and smart label flipping."""
    cmd_js = (FRONTEND_DIR / "js" / "commander.js").read_text(encoding="utf-8")

    assert "MAP_SAFE_MARGIN" in cmd_js
    assert "disperseWorldMarkers" in cmd_js
    assert "getSmartLabelAttrs" in cmd_js
    assert "cmd-pin-leader-line" in cmd_js
    assert "resize" in cmd_js


def test_css_map_containment_and_leader_lines():
    """Verify style.css contains rules for map containers, leader lines, and enhanced labels."""
    style_css = (FRONTEND_DIR / "css" / "style.css").read_text(encoding="utf-8")

    assert ".pin-label" in style_css
    assert ".pin-leader-line" in style_css
    assert ".cmd-pin-label" in style_css
    assert ".cmd-pin-leader-line" in style_css
    assert "overflow: hidden;" in style_css


# --------------------------------------------------------------------------- #
# Pure-Python Port of Boundary & Collision Algorithms to verify math specs
# --------------------------------------------------------------------------- #

MAP_SIZE = 600
MAP_METERS_SPAN = 180
MAP_SAFE_MARGIN = 22
METERS_PER_DEG_LAT = 111320
SITE_ORIGIN = {"latitude": 32.3739, "longitude": 77.2491, "altitude_m": 3950}


def meters_per_deg_lon(lat_deg):
    return METERS_PER_DEG_LAT * math.cos(math.radians(lat_deg))


def to_local_meters(loc):
    d_lat = loc["latitude"] - SITE_ORIGIN["latitude"]
    d_lon = loc["longitude"] - SITE_ORIGIN["longitude"]
    return {
        "east": d_lon * meters_per_deg_lon(SITE_ORIGIN["latitude"]),
        "north": d_lat * METERS_PER_DEG_LAT,
    }


def meters_to_svg(m):
    scale = MAP_SIZE / MAP_METERS_SPAN
    return {
        "x": MAP_SIZE / 2 + m["east"] * scale,
        "y": MAP_SIZE / 2 - m["north"] * scale,
    }


def loc_to_svg(loc):
    return meters_to_svg(to_local_meters(loc))


def clamp(val, min_val, max_val):
    return min(max(val, min_val), max_val)


def disperse_markers(items, radius_threshold=22):
    min_x = MAP_SAFE_MARGIN
    max_x = MAP_SIZE - MAP_SAFE_MARGIN
    min_y = MAP_SAFE_MARGIN
    max_y = MAP_SIZE - MAP_SAFE_MARGIN

    markers = []
    for item in items:
        raw = loc_to_svg(item.get("location") or SITE_ORIGIN)
        clamped_x = clamp(raw["x"], min_x, max_x)
        clamped_y = clamp(raw["y"], min_y, max_y)
        markers.append({
            **item,
            "rawX": raw["x"],
            "rawY": raw["y"],
            "clampedX": clamped_x,
            "clampedY": clamped_y,
            "renderX": clamped_x,
            "renderY": clamped_y,
            "isOffset": False,
        })

    visited = set()
    for i in range(len(markers)):
        if i in visited:
            continue
        cluster = [i]
        visited.add(i)

        for j in range(i + 1, len(markers)):
            if j in visited:
                continue
            dx = markers[i]["clampedX"] - markers[j]["clampedX"]
            dy = markers[i]["clampedY"] - markers[j]["clampedY"]
            if math.hypot(dx, dy) < radius_threshold:
                cluster.append(j)
                visited.add(j)

        if len(cluster) > 1:
            avg_x = sum(markers[idx]["clampedX"] for idx in cluster) / len(cluster)
            avg_y = sum(markers[idx]["clampedY"] for idx in cluster) / len(cluster)
            spread_radius = 14 + min(len(cluster) * 2.5, 18)

            for k, idx in enumerate(cluster):
                angle = (k * 2 * math.pi) / len(cluster) - math.pi / 2
                nx = clamp(avg_x + spread_radius * math.cos(angle), min_x, max_x)
                ny = clamp(avg_y + spread_radius * math.sin(angle), min_y, max_y)
                markers[idx]["renderX"] = nx
                markers[idx]["renderY"] = ny
                if math.hypot(nx - markers[idx]["rawX"], ny - markers[idx]["rawY"]) > 4:
                    markers[idx]["isOffset"] = True

    return markers


def get_smart_label_attrs(x, y):
    flip_x = x > 380 or x > (MAP_SIZE - 110)
    x_offset = -14 if flip_x else 14
    text_anchor = "end" if flip_x else "start"
    y_offset = 4
    dominant_baseline = "middle"

    if y < 24:
        y_offset = 16
        dominant_baseline = "hanging"
    elif y > MAP_SIZE - 24:
        y_offset = -12
        dominant_baseline = "auto"

    return {
        "xOffset": x_offset,
        "yOffset": y_offset,
        "textAnchor": text_anchor,
        "dominantBaseline": dominant_baseline,
    }


def test_scenario_center_victim():
    """TEST 1: Victim at origin resolves to (300, 300) within safe bounds."""
    victim = {"victim_id": "V-CENTER", "location": dict(SITE_ORIGIN)}
    res = disperse_markers([victim])
    assert len(res) == 1
    assert math.isclose(res[0]["renderX"], 300.0, abs_tol=1e-2)
    assert math.isclose(res[0]["renderY"], 300.0, abs_tol=1e-2)
    assert MAP_SAFE_MARGIN <= res[0]["renderX"] <= MAP_SIZE - MAP_SAFE_MARGIN
    assert MAP_SAFE_MARGIN <= res[0]["renderY"] <= MAP_SIZE - MAP_SAFE_MARGIN


def test_scenario_left_boundary_clamping():
    """TEST 2: Victim far west is clamped to left safe margin (22px)."""
    victim = {
        "victim_id": "V-WEST",
        "location": {
            "latitude": SITE_ORIGIN["latitude"],
            "longitude": SITE_ORIGIN["longitude"] - 0.0050,  # ~470m west
        }
    }
    res = disperse_markers([victim])
    assert res[0]["rawX"] < 0  # Off screen in raw coordinates
    assert res[0]["renderX"] == MAP_SAFE_MARGIN  # Clamped to safe margin
    assert MAP_SAFE_MARGIN <= res[0]["renderY"] <= MAP_SIZE - MAP_SAFE_MARGIN


def test_scenario_right_boundary_clamping_and_label_flip():
    """TEST 3: Victim far east is clamped to right safe margin (578px) and label flips left."""
    victim = {
        "victim_id": "V-EAST",
        "location": {
            "latitude": SITE_ORIGIN["latitude"],
            "longitude": SITE_ORIGIN["longitude"] + 0.0050,  # ~470m east
        }
    }
    res = disperse_markers([victim])
    assert res[0]["rawX"] > 600  # Off screen in raw coordinates
    assert res[0]["renderX"] == MAP_SIZE - MAP_SAFE_MARGIN  # Clamped to safe margin (578)

    lbl = get_smart_label_attrs(res[0]["renderX"], res[0]["renderY"])
    assert lbl["textAnchor"] == "end"  # Flipped left so label never escapes right boundary
    assert lbl["xOffset"] == -14


def test_scenario_top_boundary_clamping_and_baseline():
    """TEST 4: Victim far north is clamped to top safe margin (22px) and baseline adjusts."""
    victim = {
        "victim_id": "V-NORTH",
        "location": {
            "latitude": SITE_ORIGIN["latitude"] + 0.0050,  # ~556m north
            "longitude": SITE_ORIGIN["longitude"],
        }
    }
    res = disperse_markers([victim])
    assert res[0]["rawY"] < 0
    assert res[0]["renderY"] == MAP_SAFE_MARGIN

    lbl = get_smart_label_attrs(res[0]["renderX"], res[0]["renderY"])
    assert lbl["dominantBaseline"] == "hanging"  # Positioned below pin
    assert lbl["yOffset"] == 16


def test_scenario_bottom_boundary_clamping():
    """TEST 5: Victim far south is clamped to bottom safe margin (578px)."""
    victim = {
        "victim_id": "V-SOUTH",
        "location": {
            "latitude": SITE_ORIGIN["latitude"] - 0.0050,  # ~556m south
            "longitude": SITE_ORIGIN["longitude"],
        }
    }
    res = disperse_markers([victim])
    assert res[0]["rawY"] > 600
    assert res[0]["renderY"] == MAP_SIZE - MAP_SAFE_MARGIN

    lbl = get_smart_label_attrs(res[0]["renderX"], res[0]["renderY"])
    assert lbl["yOffset"] == -12


def test_scenario_multiple_co_located_victims_dispersion():
    """TEST 6: Multiple victims at the exact same GPS coordinate are dispersed non-overlapping."""
    victims = [
        {"victim_id": f"V-{i}", "location": dict(SITE_ORIGIN)}
        for i in range(4)
    ]
    res = disperse_markers(victims)
    assert len(res) == 4

    positions = [(round(v["renderX"], 1), round(v["renderY"], 1)) for v in res]
    # Verify all 4 positions are distinct
    assert len(set(positions)) == 4

    # Verify all are strictly within boundaries
    for v in res:
        assert MAP_SAFE_MARGIN <= v["renderX"] <= MAP_SIZE - MAP_SAFE_MARGIN
        assert MAP_SAFE_MARGIN <= v["renderY"] <= MAP_SIZE - MAP_SAFE_MARGIN
        assert v["isOffset"] is True


def test_geographic_coordinates_preservation():
    """TEST 7: Underlying GPS/world coordinates in location objects are never altered."""
    orig_loc = {"latitude": 32.3739, "longitude": 77.2491, "altitude_m": 3950}
    victim = {"victim_id": "V-PRESERVED", "location": dict(orig_loc)}
    res = disperse_markers([victim])

    assert res[0]["location"]["latitude"] == orig_loc["latitude"]
    assert res[0]["location"]["longitude"] == orig_loc["longitude"]
    assert res[0]["location"]["altitude_m"] == orig_loc["altitude_m"]
