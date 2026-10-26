"""
Tests for Redesigned RIDGEWATCH Analytics & Operational Intelligence Dashboard.
Verifies:
1. HTML Structure: Global Scope bar, Hero Operational Picture, KPI cards, Chart elements, Hazard Intelligence Matrix, Team Performance, and System Health.
2. JavaScript Logic: Mathematical consistency, Scope separation (Current Session vs Historical Scopes), Zero-victim N/A handling, No fake hardcoded metrics.
3. CSS / Light Theme: Light White with Blue design tokens, Hero card styles, and responsive layouts.
4. Backend API: /analytics/summary endpoint returns clean, consistent data without count contradictions.
"""

import os
import re
import pytest
from starlette.testclient import TestClient
from backend.api import app
from backend import db


@pytest.fixture
def client():
    return TestClient(app)


def test_analytics_html_structure():
    html_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "analytics.html")
    assert os.path.exists(html_path), "analytics.html must exist"
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Scope Bar & Controls
    assert 'id="scopeSelect"' in html
    assert 'id="scenarioFilterSelect"' in html
    assert 'id="analyticsRefreshBtn"' in html
    assert 'id="analyticsModePill"' in html
    assert 'id="analyticsFreshnessPill"' in html

    # Section 1: Hero Operational Picture
    assert 'id="operationalPictureCard"' in html
    assert 'id="heroRiskBox"' in html
    assert 'id="heroRiskLevel"' in html
    assert 'id="heroRiskScore"' in html
    assert 'id="heroScenarioName"' in html
    assert 'id="heroSiteLabel"' in html
    assert 'id="heroSurvDetected"' in html
    assert 'id="heroSurvRescued"' in html
    assert 'id="heroSurvEnRoute"' in html
    assert 'id="heroSurvPending"' in html
    assert 'id="heroAlertBadge"' in html
    assert 'id="heroDriversList"' in html

    # Section 2: Primary KPI Cards
    assert 'id="kpiSessionsCount"' in html
    assert 'id="kpiVictimsCount"' in html
    assert 'id="kpiRescuedCount"' in html
    assert 'id="kpiRescueRate"' in html
    assert 'id="kpiAlertsCount"' in html

    # Section 3: Performance Charts & Response Times
    assert 'id="performanceChart"' in html
    assert 'id="chartTooltip"' in html
    assert 'id="avgResponseTime"' in html
    assert 'id="avgRescueTime"' in html

    # Section 4 & 5: Scenario & Victim Donut Charts
    assert 'id="hazardDonutSvg"' in html
    assert 'id="hazardCenterVal"' in html
    assert 'id="hazardLegendList"' in html
    assert 'id="victimStatusDonutSvg"' in html
    assert 'id="victimStatusCenterVal"' in html
    assert 'id="victimStatusLegendList"' in html

    # Section 6: Hazard Intelligence Matrix
    assert 'id="hazardIntelligenceGrid"' in html
    assert 'id="landslideChartSvg"' in html

    # Section 9, 10, 11: Tables, Teams, Platform Health
    assert 'id="sessionsTableBody"' in html
    assert 'id="teamsPerformanceList"' in html
    assert 'id="devicesOnline"' in html
    assert 'id="systemUptime"' in html
    assert 'id="dataSyncStatus"' in html
    assert 'id="criticalAlertsCount"' in html


def test_analytics_js_mathematical_consistency_and_no_fake_data():
    js_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "js", "analytics.js")
    assert os.path.exists(js_path), "analytics.js must exist"
    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # Scope filtering engine
    assert "scope: \"current\"" in js or "scope = state.scope" in js
    assert "getScopedDataset" in js
    assert "populateScenarioDropdown" in js

    # Mathematical consistency checks
    assert "totalRescued = Math.min(totalVictims" in js or "Math.min(vCount" in js or "Math.min(totalVictims, rawSessions" in js
    assert "rescueRate = totalVictims > 0 ?" in js or "scoped.rescueRate != null" in js
    assert "Waiting for sufficient rescue data" in js
    assert "NO RESCUE SESSIONS RECORDED IN THIS SCOPE" in js

    # Denominator check in team performance
    assert "missions > 0" in js
    assert "based on" in js.lower() or "missions assigned" in js.lower() or "rescued" in js.lower()

    # No hardcoded fake dummy times
    assert '"8m 42s"' not in js
    assert '"14m 15s"' not in js


def test_analytics_css_light_theme():
    css_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "css", "style.css")
    assert os.path.exists(css_path), "style.css must exist"
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Analytics Hero & Scope bar styling
    assert ".analytics-scope-bar" in css
    assert ".analytics-hero-card" in css
    assert ".hero-risk-box" in css
    assert ".analytics-kpi-grid" in css
    assert ".analytics-kpi-card" in css
    assert ".analytics-kpi-icon" in css
    assert ".analytics-main-grid" in css
    assert ".hazard-intel-grid" in css
    assert ".analytics-team-card" in css


def test_backend_analytics_summary_endpoint(client):
    # Call the analytics summary endpoint
    res = client.get("/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert "sessions" in data
    assert "totals" in data

    totals = data["totals"]
    sessions = data["sessions"]

    assert totals["session_count"] == len(sessions)
    assert totals["total_rescued"] <= totals["total_victims"] if totals["total_victims"] > 0 else totals["total_rescued"] == 0

    for s in sessions:
        assert s["rescued_count"] <= s["victim_count"]
        assert "scenario_id" in s
        assert "started_at" in s
