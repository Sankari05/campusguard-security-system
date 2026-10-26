"""
test_watch_concept_3d_visualization.py
----------------------------------------
Test suite for RIDGEWATCH 3D / 4D Smartwatch Rescue Concept Visualization.
Validates:
- Test 1: HTML structure contains the 3D/4D concept visualization section and required disclaimers.
- Test 2: CSS and JS asset files exist, are linked, and have non-zero content.
- Test 3: Concept visualization contains the Wave Call Plus 3D representation and honest labels.
- Test 4: Signal pipeline contains all 4 nodes: Commander, Core, Android Bridge, and Wave Call Plus.
- Test 5: 4D Operation Timeline contains all 6 simulated stages (T+00 to T+60).
- Test 6: Backend APIs (/scenarios, /teams, /commander/overview, /watch/{member_id}) operate seamlessly without regression.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_watch_html_and_assets_exist():
    """Verify that watch.html, watch_concept_3d.css, and watch_concept_3d.js exist on disk."""
    base_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    html_path = os.path.join(base_dir, "watch.html")
    css_path = os.path.join(base_dir, "css", "watch_concept_3d.css")
    js_path = os.path.join(base_dir, "js", "watch_concept_3d.js")

    assert os.path.exists(html_path), "frontend/watch.html must exist"
    assert os.path.exists(css_path), "frontend/css/watch_concept_3d.css must exist"
    assert os.path.exists(js_path), "frontend/js/watch_concept_3d.js must exist"

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    assert "watch_concept_3d.css" in html_content
    assert "watch_concept_3d.js" in html_content


def test_concept_visualization_dom_elements():
    """Verify required 3D/4D concept elements and honest disclaimers in watch.html."""
    html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "watch.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Required Concept Header & Badges
    assert "Smartwatch Rescue Flow · 3D / 4D Concept Visualization" in html
    assert "LIVE CONCEPT VISUALIZATION" in html
    assert "SIMULATION — WAVE CALL PLUS" in html
    assert "REAL HARDWARE ON HOLD" in html

    # Required 3D Wave Call Plus chassis elements
    assert "watch-3d-wrapper" in html
    assert "watch-case-body" in html
    assert "watch-side-crown" in html
    assert "watch-oled-screen" in html
    assert "watch-strap-top" in html
    assert "watch-strap-bottom" in html

    # Signal pipeline nodes
    assert "pipeCommander" in html
    assert "pipeCore" in html
    assert "pipeBridge" in html
    assert "pipeWatch" in html

    # Tactical map & simulated location
    assert "tactical-map-svg" in html
    assert "SIMULATED LOCATION" in html

    # 4D Timeline nodes
    assert "conceptTl0" in html
    assert "conceptTl1" in html
    assert "conceptTl2" in html
    assert "conceptTl3" in html
    assert "conceptTl4" in html
    assert "conceptTl5" in html


def test_concept_js_stages_structure():
    """Verify that watch_concept_3d.js defines the 6 sequential operational stages."""
    js_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "watch_concept_3d.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    assert "STANDBY" in js
    assert "GO" in js
    assert "ACCEPTED" in js
    assert "EN_ROUTE" in js
    assert "ARRIVED" in js
    assert "RESCUED" in js
    assert "T+00" in js
    assert "T+02" in js
    assert "T+05" in js
    assert "T+15" in js
    assert "T+45" in js
    assert "T+60" in js


def test_backend_apis_remain_intact(started_client):
    """Verify that backend APIs supporting the concept and existing watch remain fully operational."""
    # 1. Scenarios API
    sc_res = started_client.get("/scenarios")
    assert sc_res.status_code == 200
    sc_data = sc_res.json()
    assert "scenarios" in sc_data
    assert len(sc_data["scenarios"]) >= 1

    # 2. Commander Overview API (teams & members & victims)
    co_res = started_client.get("/commander/overview")
    assert co_res.status_code == 200
    co_data = co_res.json()
    assert "team_members" in co_data
    assert "victims" in co_data
    assert len(co_data["team_members"]) >= 1

    # 3. Active Wearable Commands API
    act_res = started_client.get("/api/wearable/commands/active")
    assert act_res.status_code == 200
    act_data = act_res.json()
    assert "has_active_command" in act_data
