"""
test_watch_view_toggle.py
--------------------------
Test suite for RIDGEWATCH Watch Module Two-View Toggle Redesign.
Validates:
- Test 1: Single sidebar entry for Watch pointing to watch.html.
- Test 2: Topbar internal view switcher toggle with [WATCH CONSOLE] and [RESCUE FLOW] buttons.
- Test 3: View A (#viewWatchConsole) contains complete Watch Console layout.
- Test 4: View B (#viewRescueFlow) contains 3D/4D concept visualization layout.
- Test 5: CSS contains view toggle pill styles and visibility classes.
- Test 6: JS contains view switching logic and backend state synchronization.
- Test 7: Backend state (/teams, /commander/overview, /watch/{member_id}) feeds both views identically.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_watch_single_sidebar_and_two_views():
    """Verify watch.html maintains a single sidebar module and 2 internal views."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "watch.html")
    assert os.path.exists(html_path)

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Single sidebar link for Watch
    assert 'href="watch.html" class="sidebar-link is-active"' in html

    # 2. Topbar View Toggle Switcher
    assert 'id="watchViewToggle"' in html
    assert 'id="btnViewConsole"' in html
    assert 'id="btnViewRescueFlow"' in html
    assert "WATCH CONSOLE" in html
    assert "RESCUE FLOW" in html

    # 3. Two Isolated View Containers
    assert 'id="viewWatchConsole"' in html
    assert 'id="viewRescueFlow"' in html
    assert 'class="watch-view-container is-hidden"' in html or 'class="watch-view-container"' in html


def test_watch_console_view_structure():
    """Verify View A (Watch Console) has all required operational components."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "watch.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Hardware Specs Card
    assert "WEARABLE HARDWARE" in html
    assert "u-blox NEO-M9N" in html
    assert "Nordic nRF52840" in html

    # Hardware & Bridge Status Card
    assert "HARDWARE &amp; BRIDGE STATUS" in html or "HARDWARE & BRIDGE STATUS" in html
    assert "statBridgeVal" in html
    assert "statBleVal" in html
    assert "statWatchVal" in html

    # Location Card
    assert "CURRENT RESCUE LOCATION" in html
    assert "locValLat" in html
    assert "locValLon" in html
    assert "mini-map-svg" in html

    # Live Watch Preview Card
    assert "LIVE WATCH PREVIEW" in html
    assert "watchMemberSelect" in html
    assert "watchCircleScreen" in html
    assert "watchGoText" in html
    assert "watchCompassWrap" in html

    # Operation Timeline Card
    assert "RESCUE OPERATION TIMELINE" in html
    assert "tlNode1" in html
    assert "tlNode2" in html
    assert "tlNode3" in html
    assert "tlNode4" in html
    assert "tlNode5" in html


def test_rescue_flow_view_structure():
    """Verify View B (Rescue Flow 3D/4D) has all concept visualizer components."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "watch.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Concept Header & Badges
    assert "Smartwatch Rescue Flow · 3D / 4D Concept Visualization" in html
    assert "LIVE CONCEPT VISUALIZATION" in html
    assert "SIMULATION — WAVE CALL PLUS" in html
    assert "REAL HARDWARE ON HOLD" in html

    # Controls Toolbar
    assert "btnConceptPlay" in html
    assert "btnConceptPause" in html
    assert "btnConceptStep" in html
    assert "btnConceptReset" in html
    assert "conceptScenarioSelect" in html
    assert "conceptMemberSelect" in html

    # Left: Commander Dispatch & Signal Pipeline
    assert "Commander Dispatch" in html
    assert "Rescue Signal Pipeline" in html
    assert "pipeCommander" in html
    assert "pipeCore" in html
    assert "pipeBridge" in html
    assert "pipeWatch" in html

    # Center: 3D Wave Call Plus Stage
    assert "watch-3d-wrapper" in html
    assert "watch-case-body" in html
    assert "watch-side-crown" in html
    assert "watch-oled-screen" in html

    # Right: Tactical Map
    assert "Tactical Rescue Map" in html
    assert "tactical-map-svg" in html
    assert "SIMULATED LOCATION" in html

    # Bottom: 4D Operation Timeline
    assert "4D Operation Timeline (Simulated Timeline)" in html
    assert "conceptTl0" in html
    assert "conceptTl5" in html


def test_css_and_js_toggle_bindings():
    """Verify CSS and JS provide seamless view switching and backend synchronization."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "css", "watch_concept_3d.css")
    js_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "watch_concept_3d.js")

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # CSS Toggle Classes
    assert ".watch-view-toggle" in css
    assert ".view-toggle-btn" in css
    assert ".watch-view-container" in css
    assert ".watch-view-container.is-hidden" in css

    # JS Toggle & Sync Logic
    assert "initViewToggle" in js
    assert "btnViewConsole" in js
    assert "btnViewRescueFlow" in js
    assert "syncLiveBackendTo3DConcept" in js


def test_backend_sync_for_both_views(started_client):
    """Verify backend endpoints serve data consumed identically by both views."""
    # 1. Check /teams
    res_teams = started_client.get("/teams")
    assert res_teams.status_code == 200
    teams_data = res_teams.json()
    assert "teams" in teams_data
    assert len(teams_data["teams"]) > 0

    # 2. Check /watch/{member_id}
    member_id = "ALPHA-M001"
    res_watch = started_client.get(f"/watch/{member_id}")
    assert res_watch.status_code == 200
    watch_data = res_watch.json()
    assert watch_data["member_id"] == member_id
    assert "status" in watch_data

    # 3. Assign rescue task via Commander
    res_assign = started_client.post(
        "/commander/assign",
        json={"member_id": member_id, "victim_id": "V3"}
    )
    assert res_assign.status_code == 200

    # 4. Re-query /watch/{member_id} — should now reflect active rescue state
    res_watch_active = started_client.get(f"/watch/{member_id}")
    assert res_watch_active.status_code == 200
    active_data = res_watch_active.json()
    assert active_data["assigned_victim_id"] == "V3"
    assert active_data["status"] in ("en_route", "go", "arrived")
    assert "distance_m" in active_data
    assert "bearing_deg" in active_data
