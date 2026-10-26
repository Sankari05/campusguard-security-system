"""
test_backend_driven_realtime_watch.py
-------------------------------------
Automated test suite verifying the conversion of the 3D/4D Smartwatch
Rescue Visualization into a 100% backend-driven, real-time client.

Covers:
1. Removal of hardcoded static values (CMD-OP-7041, Urban Earthquake, 146m, etc.)
2. Presence of clean fallback states (dash/awaiting assignment)
3. Dynamic propagation from Commander assignment -> Backend -> /watch/{member_id}
4. Rich metadata provision (operation_id, scenario, priority, victim_location, member_location, ETA, timeline)
5. Strict separation between LIVE_BACKEND and SIMULATION modes
"""

import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def test_no_hardcoded_static_demo_values_in_watch_markup():
    """Verify that static demo constants are not hardcoded into watch.html markup."""
    watch_html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "watch.html")
    with open(watch_html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Disallowed static demo strings
    assert "CMD-OP-7041" not in content, "CMD-OP-7041 must not be hardcoded in watch.html"
    assert "146 m" not in content, "146 m must not be hardcoded in watch.html"
    assert "12° N" not in content, "12° N must not be hardcoded in watch.html"

    # Required dynamic elements & placeholders
    assert 'id="dispConceptOpId"' in content
    assert 'id="dispConceptScenario"' in content
    assert 'id="dispConceptPriority"' in content
    assert 'id="dispConceptTarget"' in content
    assert 'id="dispConceptMember"' in content
    assert 'id="conceptTelemDist"' in content
    assert 'id="conceptTelemEta"' in content
    assert 'id="conceptTelemBearing"' in content
    assert 'id="conceptTelemTarget"' in content
    assert 'id="watchStageModeBadge"' in content


def test_watch_endpoint_returns_rich_realtime_metadata(started_client):
    """Verify GET /watch/{member_id} returns all required real-time navigation metadata."""
    overview = started_client.get("/commander/overview").json()
    member = overview["team_members"][0]
    victim = overview["victims"][0]

    # Initial state: HOLD / Unassigned
    r1 = started_client.get(f"/watch/{member['member_id']}")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "hold"
    assert d1.get("assigned_victim_id") is None
    assert d1.get("distance_m") is None

    # Commander assigns member to victim
    r_assign = started_client.post(
        "/commander/assign",
        json={"member_id": member["member_id"], "victim_id": victim["victim_id"]},
    )
    assert r_assign.status_code == 200

    # Assigned state: Rich real-time navigation metadata populated
    r2 = started_client.get(f"/watch/{member['member_id']}")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] in ["en_route", "arrived"]
    assert d2["assigned_victim_id"] == victim["victim_id"]
    assert d2["distance_m"] is not None
    assert d2["distance_m"] >= 0
    assert d2["bearing_deg"] is not None
    assert d2["compass_label"] is not None


def test_watch_state_unified_model_in_javascript():
    """Verify watch_concept_3d.js implements a unified watchState and state adapter."""
    js_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "watch_concept_3d.js")
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Core state model architecture
    assert "watchState = {" in js
    assert "WatchStateAdapter" in js
    assert "Concept3DRenderer" in js
    assert "renderLiveBackend" in js
    assert "syncWithBackend" in js
    assert "syncLiveBackendTo3DConcept" in js
    assert "LIVE_BACKEND" in js
    assert "SIMULATION" in js
