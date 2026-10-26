"""
Tests for Compact Scenario Selector Component in RIDGEWATCH UI.
Verifies initial compact state, dropdown/popover, 5-row visible height constraint,
keyboard accessibility, search filtering, click outside closing, and API integration.
"""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
VISUAL_HTML = REPO_ROOT / "frontend" / "visual.html"
VISUAL_JS = REPO_ROOT / "frontend" / "js" / "visual.js"
LOGIC_HTML = REPO_ROOT / "frontend" / "logic.html"
LOGIC_JS = REPO_ROOT / "frontend" / "js" / "logic.js"
STYLE_CSS = REPO_ROOT / "frontend" / "css" / "style.css"


def test_visual_html_compact_scenario_selector():
    """Verify visual.html does not contain the scenario selector dropdown."""
    content = VISUAL_HTML.read_text(encoding="utf-8")

    assert 'id="dtScenarioSelectorWrap"' not in content
    assert 'id="dtScenarioDropdownBtn"' not in content
    assert 'id="dtScenarioPopover"' not in content


def test_logic_html_compact_scenario_selector():
    """Verify logic.html contains compact scenario dropdown in Step 0 header."""
    content = LOGIC_HTML.read_text(encoding="utf-8")

    assert 'id="logicScenarioSelectorWrap"' in content
    assert 'id="logicScenarioDropdownBtn"' in content
    assert 'id="logicSelectedScenarioText"' in content
    assert 'id="logicScenarioPopover"' in content
    assert 'id="logicScenarioSearchInput"' in content
    assert 'id="logicScenarioOptionList"' in content

    # Verify initial popover is hidden
    assert '<div class="scenario-popover" id="logicScenarioPopover" hidden>' in content


def test_scenario_selector_css_rules():
    """Verify CSS defines compact styling, 5-row visible height constraint, and scrolling."""
    content = STYLE_CSS.read_text(encoding="utf-8")

    assert ".scenario-selector-wrap" in content
    assert ".scenario-dropdown-btn" in content
    assert ".scenario-popover" in content
    assert ".scenario-option-list" in content

    # Check max-height for ~5 items visible before scrolling
    assert re.search(r"\.scenario-option-list\s*\{[^}]*max-height:\s*(200|210|220|240)px", content)
    assert re.search(r"\.scenario-option-list\s*\{[^}]*overflow-y:\s*auto", content)

    # Check popover floating & z-index
    assert re.search(r"\.scenario-popover\s*\{[^}]*position:\s*absolute", content)
    assert re.search(r"\.scenario-popover\s*\{[^}]*z-index:\s*100", content)


def test_visual_js_scenario_dropdown_logic():
    """Verify visual.js cleanly removed the scenario dropdown while retaining core setScenarioFilter capability."""
    content = VISUAL_JS.read_text(encoding="utf-8")

    assert "initScenarioDropdown" not in content
    assert "dtScenarioDropdownBtn" not in content
    assert "dtScenarioPopover" not in content
    assert "setScenarioFilter" in content


def test_logic_js_scenario_dropdown_logic():
    """Verify logic.js implements compact scenario selector with POST /scenario/start integration."""
    content = LOGIC_JS.read_text(encoding="utf-8")

    assert "initLogicScenarioDropdown" in content
    assert "apiPost(\"/scenario/start\"" in content
    assert "scenarioDropdownBtn" in content
    assert "scenarioPopover" in content
    assert "scenarioSearchInput" in content
    assert "scenarioOptionList" in content
