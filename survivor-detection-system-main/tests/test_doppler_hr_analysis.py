"""
test_doppler_hr_analysis.py
---------------------------
Automated test suite for the isolated Doppler Heart-Rate Analysis UI feature.
Validates:
1. doppler.html exists and contains all required UI components:
   - Non-medical disclaimer banner
   - 4 summary metrics (Total Detected, Heart Available, Abnormal HR, Weak/Uncertain)
   - Filter, Search, and Sort controls
   - Compact survivor grid with mini-canvases
   - Diagnostic analysis modal with raw Doppler canvas, filtered cardiac canvas, and peak markers
2. doppler.js contains feature flag support, independent signal synthesis, and peak detection
3. Adherence to RidgeWatch light theme guidelines
"""

import re
from pathlib import Path
import pytest

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def test_doppler_html_exists():
    """Verify doppler.html exists in frontend directory."""
    doppler_html_path = FRONTEND_DIR / "doppler.html"
    assert doppler_html_path.exists(), "frontend/doppler.html must exist"


def test_doppler_html_structure_and_ids():
    """Verify all required summary cards, controls, and modal elements exist."""
    content = (FRONTEND_DIR / "doppler.html").read_text(encoding="utf-8")

    # Summary Cards
    assert 'id="statTotalSurvivors"' in content
    assert 'id="statHeartAvailable"' in content
    assert 'id="statAbnormalHr"' in content
    assert 'id="statWeakSignals"' in content

    # Controls
    assert 'id="dopplerSearchInput"' in content
    assert 'id="dopplerTriageFilter"' in content
    assert 'id="dopplerSortSelect"' in content
    assert 'id="dopplerRefreshBtn"' in content

    # Survivor list & Empty state
    assert 'id="dopplerSurvivorList"' in content
    assert 'id="dopplerEmptyState"' in content

    # Diagnostic Modal
    assert 'id="dopplerDetailModal"' in content
    assert 'id="modalTargetId"' in content
    assert 'id="modalHeartRate"' in content
    assert 'id="modalRrInterval"' in content
    assert 'id="modalConfidence"' in content
    assert 'id="rawDopplerCanvas"' in content
    assert 'id="cardiacPeaksCanvas"' in content
    assert 'id="modalBeatsLog"' in content

    # Non-medical disclaimer
    assert "NON-MEDICAL" in content or "SIMULATED ESTIMATE" in content


def test_doppler_js_logic_and_feature_flag():
    """Verify doppler.js contains feature flag, signal generator, and peak detection."""
    js_path = FRONTEND_DIR / "js" / "doppler.js"
    assert js_path.exists(), "frontend/js/doppler.js must exist"

    content = js_path.read_text(encoding="utf-8")

    # Feature flag
    assert "RIDGEWATCH_ENABLE_DOPPLER_HR_ANALYSIS" in content

    # Signal synthesis & Peak detection
    assert "generateDopplerSignals" in content
    assert "cardiacSignal" in content
    assert "rawSignal" in content
    assert "peaks" in content
    assert "rrIntervalMs" in content

    # Modal handling
    assert "openDopplerModal" in content
    assert "closeDopplerModal" in content

    # Independent data isolation (seed / per target calculation)
    assert "target.seed" in content or "hashString" in content


def test_doppler_theme_consistency():
    """Verify doppler.html adheres to the white and light blue theme tokens."""
    content = (FRONTEND_DIR / "doppler.html").read_text(encoding="utf-8")

    # Ensure no prohibited dark patterns
    dark_patterns = [
        re.compile(r'#121826', re.IGNORECASE),
        re.compile(r'rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.2', re.IGNORECASE),
    ]

    for pattern in dark_patterns:
        matches = pattern.findall(content)
        assert not matches, f"Found dark background pattern {pattern.pattern} in doppler.html"
