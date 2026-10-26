import os
import re
import pytest

def test_hardware_html_structure():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(base_dir, "frontend", "hardware.html")
    assert os.path.exists(html_path), "hardware.html must exist"

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check topbar & header
    assert "HARDWARE MONITORING" in content
    assert "Hardware &amp; Sensor Status" in content or "Hardware & Sensor Status" in content
    assert 'id="hwSystemStatusBadge"' in content
    assert 'id="hwSystemStatusText"' in content
    assert 'id="hwHeaderTotal"' in content
    assert 'id="hwHeaderOnline"' in content

    # Verify scenario strip card is removed as requested
    assert 'id="hwScenarioCard"' not in content

    # Check KPI summary
    assert "hw-summary-grid" in content
    assert 'id="hwKpiTotal"' in content
    assert 'id="hwKpiOnline"' in content
    assert 'id="hwKpiActive"' in content
    assert 'id="hwKpiStandby"' in content
    assert 'id="hwKpiAlerts"' in content

    # Check Controls & Filters
    assert 'id="hwFilterPills"' in content
    assert 'data-filter="ALL"' in content
    assert 'data-filter="PRIMARY"' in content
    assert 'data-filter="SUPPORTING"' in content
    assert 'data-filter="STANDBY"' in content
    assert 'data-filter="ALERTS"' in content
    assert 'data-filter="OFFLINE"' in content
    assert 'id="btnViewGrid"' in content
    assert 'id="btnViewTable"' in content
    assert 'id="hwSearchInput"' in content

    # Check Grid and Table Containers
    assert 'id="hwSensorGrid"' in content
    assert 'id="hwTableContainer"' in content
    assert 'id="hwSensorTable"' in content
    assert 'id="hwTableBody"' in content

    # Check Visual Section
    assert 'id="hwVisualSection"' in content
    assert "RGB OPTICAL INTELLIGENCE" in content
    assert "FLIR LEPTON THERMAL LWIR" in content
    assert 'id="hwRgbDetectionState"' in content
    assert 'id="hwThermalBodyTemp"' in content

    # Check Detail Modal
    assert 'id="hwDetailOverlay"' in content
    assert 'id="hwDetailCard"' in content
    assert 'id="btnDetailClose"' in content
    assert 'id="hwDetailBigVal"' in content
    assert 'id="hwDetailSpecsGrid"' in content or 'hw-detail-specs-grid' in content


def test_hardware_css_tokens():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css_path = os.path.join(base_dir, "frontend", "css", "style.css")
    assert os.path.exists(css_path), "style.css must exist"

    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()

    # Verify key White + Blue classes for Hardware
    assert ".hw-topbar" in css
    assert ".hw-scenario-card" in css
    assert ".hw-role-box" in css
    assert ".hw-summary-grid" in css
    assert ".hw-kpi-card" in css
    assert ".hw-controls-bar" in css
    assert ".hw-filter-btn" in css
    assert ".hw-view-toggle" in css
    assert ".hw-sensor-grid" in css
    assert ".hw-sensor-card" in css
    assert ".hw-table-container" in css
    assert ".hw-table" in css
    assert ".hw-visual-section" in css
    assert ".hw-visual-card" in css
    assert ".hw-detail-overlay" in css
    assert ".hw-detail-card" in css


def test_hardware_js_coverage():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js_path = os.path.join(base_dir, "frontend", "js", "hardware.js")
    assert os.path.exists(js_path), "hardware.js must exist"

    with open(js_path, "r", encoding="utf-8") as f:
        js = f.read()

    # All 18 sensors must be mapped in metadata
    required_sensors = [
        "heart_rate_radar", "thermal_imaging", "acoustic", "co2", "pir_motion", "rgb_camera",
        "imu_tilt", "imu_vibration", "water_level", "water_flow", "gas_concentration",
        "smoke_density", "barometric_pressure", "rainfall_intensity", "soil_moisture",
        "temperature", "humidity", "gps"
    ]
    for s in required_sensors:
        assert s in js, f"Sensor {s} must be present in hardware.js"

    # Core view modes and functions
    assert "renderGrid" in js
    assert "renderTable" in js
    assert "renderDetailModal" in js
    assert "openDetailModal" in js
    assert "closeDetailModal" in js
    assert "renderScenarioBreakdown" in js
    assert "renderVisualIntelligence" in js
