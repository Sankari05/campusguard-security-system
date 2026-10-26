import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
CMD_JS_PATH = FRONTEND_DIR / "js" / "commander.js"
CMD_HTML_PATH = FRONTEND_DIR / "commander.html"

def test_commander_map_legend_toggles_markup():
    """Verify commander.html contains interactive layer toggle buttons with counter badges."""
    html = CMD_HTML_PATH.read_text(encoding="utf-8")
    assert 'id="cmdMapLegend"' in html
    assert 'id="toggleLayerVictims"' in html
    assert 'id="toggleLayerMembers"' in html
    assert 'id="toggleLayerJobs"' in html
    assert 'id="toggleLayerBase"' in html
    assert 'id="legendCountVictims"' in html
    assert 'id="legendCountMembers"' in html
    assert 'id="legendCountJobs"' in html

def test_commander_js_job_clustering_and_label_collision_engine():
    """Verify commander.js implements clusterOpsJobs, isLocalEntity, and collision-free label placement."""
    js = CMD_JS_PATH.read_text(encoding="utf-8")
    assert "clusterOpsJobs" in js
    assert "isLocalEntity" in js
    assert "mapLayers" in js
    assert "cmd-cluster-pin" in js
    assert "cmd-cluster-badge" in js
    assert "legendCountVictims" in js
    assert "legendCountMembers" in js
    assert "legendCountJobs" in js
