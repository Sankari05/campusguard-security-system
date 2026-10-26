"""
test_visual_ui.py
-----------------
Automated test suite validating the Visual 2D, 3D, and 4D LIVE Digital Twin:
- HTML structure, mode selector (2D/3D/4D), and script bindings.
- Procedural 3D hardware representations (Raspberry Pi 5, ESP32-S3, Thermal Camera FOV, Radar, etc.).
- Physical wire protocol colors and Connection Inspector.
- 4D Live Timeline, clock, and playback controls.
- "Fit All Hardware" bounding box camera framing solver.
- Hardware inventory synchronization with backend APIs.
"""

import os
import re
import pytest
from fastapi.testclient import TestClient
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

import hardware_registry
from api import app

client = TestClient(app)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VISUAL_HTML_PATH = os.path.join(REPO_ROOT, "frontend", "visual.html")
VISUAL_JS_PATH = os.path.join(REPO_ROOT, "frontend", "js", "visual.js")
STYLE_CSS_PATH = os.path.join(REPO_ROOT, "frontend", "css", "style.css")


def test_visual_html_structure_and_4d_elements():
    """Verify visual.html includes 2D/3D/4D mode selector, Connection Inspector, and Timeline."""
    assert os.path.exists(VISUAL_HTML_PATH), "visual.html must exist in frontend/"

    with open(VISUAL_HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Mode Selector Buttons
    assert 'id="btnView2D"' in html, "Missing 2D button"
    assert 'id="btnView3D"' in html, "Missing 3D button"
    assert 'id="btnView4D"' in html, "Missing 4D Live button"

    # 2. Source Badge
    assert 'id="dtSourceBadgeLabel"' in html, "Missing data source badge in topbar"

    # 3. Connection Inspector
    conn_inspector_ids = [
        "dtConnectionInspector",
        "btnConnClose",
        "dtConnId",
        "dtConnSource",
        "dtConnTarget",
        "dtConnProtocol",
        "dtConnPinMapping",
        "dtConnPowerRail",
        "dtConnDataLine",
        "dtConnStatus",
    ]
    for cid in conn_inspector_ids:
        assert f'id="{cid}"' in html, f"Missing Connection Inspector element id='{cid}'"

    # 4. Verify 4D Live Timeline has been removed
    assert 'id="dtLiveTimelineBar"' not in html, "Timeline bar should be removed from visual.html"
    assert 'id="btnTlLive"' not in html, "btnTlLive should be removed from visual.html"
    assert 'id="btnTlPause"' not in html, "btnTlPause should be removed from visual.html"
    assert 'id="btnTlClear"' not in html, "btnTlClear should be removed from visual.html"

    # 5. Fit All Hardware Camera Button
    assert 'id="btnCamFitAll"' in html, "Missing Fit All camera button"


def test_visual_js_4d_digital_twin_engine():
    """Verify visual.js implements 4D state, procedural hardware, thermal FOV cone, and wire inspection."""
    assert os.path.exists(VISUAL_JS_PATH), "visual.js must exist in frontend/js/"

    with open(VISUAL_JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    # 1. Verify visualMode state exists and supports 2D, 3D, and 4D
    assert "visualMode:" in js
    assert "function switchView(" in js

    # 2. Verify procedural physical hardware shapes exist
    assert "pi5_board" in js
    assert "esp32_board" in js
    assert "lifepo4_pmu" in js
    assert "cam_thermal" in js
    assert "cam_optical" in js
    assert "radar_patch" in js
    assert "soil_probe" in js
    assert "water_probe" in js
    assert "flow_doppler" in js
    assert "rain_optical" in js
    assert "baro_chip" in js
    assert "gas_mox" in js
    assert "smoke_laser" in js
    assert "temp_sht" in js
    assert "gps_helix" in js
    assert "antenna_lora" in js
    assert "antenna_cell" in js
    assert "mic_mems" in js
    assert "co2_ndir" in js
    assert "slope_array" in js

    # 3. Verify Rescue Station Chassis and Holographic 3D Badges
    assert "buildRescueStationChassis" in js
    assert "createHolographicBadge" in js

    # 4. Verify Thermal Camera FOV Cone and Radiometric scanning frustum
    assert "thermalConeMesh" in js
    assert "ConeGeometry" in js

    # 5. Verify Connection Inspector and wire selection
    assert "function selectConnection(" in js
    assert "function deselectConnection(" in js
    assert "HARDWARE_CONNECTIONS" in js

    # 6. Verify Fit All Hardware bounding box solver
    assert "function fitAllHardware()" in js
    assert "THREE.Box3" in js

    # 7. Verify 4D Live Timeline logger removed cleanly
    assert "logTimelineEvent" not in js
    assert "renderTimeline" not in js

    # 8. Verify Panel Close Buttons & Deselection Logic
    assert "el.btnDetailClose.onclick" in js
    assert "el.btnConnClose.onclick" in js
    assert "el.btnInventoryClose.onclick" in js
    assert "function deselectHardware()" in js
    assert "function deselectConnection()" in js

    # 9. Verify 2D, 3D vs 4D Mode Separation
    assert 'state.visualMode = mode' in js
    assert 'state.visualMode = mode' in js


def test_visual_css_classes():
    """Verify style.css contains styles for 4D live pulse, Connection Inspector, Timeline, and [hidden] display rule."""
    assert os.path.exists(STYLE_CSS_PATH), "style.css must exist"

    with open(STYLE_CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    assert ".dt-conn-inspector" in css
    assert ".dt-live-timeline-bar" in css
    assert ".dt-live-pulse-icon" in css
    assert ".dt-tl-event" in css
    assert ".dt-detail-drawer[hidden]" in css
    assert ".dt-inventory-drawer[hidden]" in css
    assert ".dt-conn-inspector[hidden]" in css


def test_hardware_api_inventory_and_topology_consistency():
    """Verify backend hardware inventory and topology match frontend expectations."""
    # Inventory check
    res_inv = client.get("/hardware/inventory")
    assert res_inv.status_code == 200
    data_inv = res_inv.json()
    assert data_inv["status"] == "success"
    assert data_inv["total_equipment"] >= 21

    # Topology check
    res_top = client.get("/hardware/topology")
    assert res_top.status_code == 200
    data_top = res_top.json()
    assert data_top["status"] == "success"
    assert data_top["total_connections"] >= 20

    # Summary check
    res_sum = client.get("/hardware/summary")
    assert res_sum.status_code == 200
    data_sum = res_sum.json()
    assert data_sum["status"] == "success"
    assert data_sum["total_equipment"] >= 21


def test_visual_white_blue_theme_styling():
    """Verify that Visual 3D/4D module adheres strictly to the RIDGEWATCH White + Blue theme."""
    with open(STYLE_CSS_PATH, "r", encoding="utf-8") as f:
        css = f.read()

    # Check Visual Console uses White + Blue void background & ink color
    assert ".visual-console" in css
    assert "background: var(--bg-void, #eef3fb)" in css
    assert "color: var(--ink, #0f2547)" in css

    # Check topbar & controls use panel white & blue accents
    assert ".visual-topbar" in css
    assert "background: var(--bg-panel, #ffffff)" in css
    assert ".dt-toggle-btn.is-active" in css
    assert "background: var(--accent-ice, #2563eb)" in css

    # Check drawers use white panel styling with blue borders
    assert ".dt-detail-drawer" in css
    assert ".dt-inventory-drawer" in css
    assert ".dt-conn-inspector" in css

    # Check 3D scene & 2D schematic use light background in JS
    with open(VISUAL_JS_PATH, "r", encoding="utf-8") as f:
        js = f.read()

    assert "scene.background = new THREE.Color(0xf0f6fc)" in js
    assert "scene.fog = new THREE.FogExp2(0xf0f6fc, 0.025)" in js
    assert "grid = new THREE.GridHelper(24, 48, 0x93c5fd, 0xdbeafe)" in js
    assert "stop-color=\"#eff6ff\"" in js

