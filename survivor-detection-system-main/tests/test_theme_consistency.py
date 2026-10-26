import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

def test_no_hardcoded_dark_cards_in_frontend_html():
    """Verify that none of the HTML pages have hardcoded dark surface cards or black panel backgrounds."""
    dark_patterns = [
        re.compile(r'#121826', re.IGNORECASE),
        re.compile(r'rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.2', re.IGNORECASE),
    ]

    html_files = list(FRONTEND_DIR.glob("*.html"))
    assert len(html_files) > 0, "HTML files should exist in frontend/"

    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8")
        for pattern in dark_patterns:
            matches = pattern.findall(content)
            assert not matches, f"Found dark background pattern {pattern.pattern} in {html_file.name}"

def test_commander_intelligence_panels_light_theme():
    """Verify commander.html panels and cards use the white with blue design system tokens."""
    commander_html = (FRONTEND_DIR / "commander.html").read_text(encoding="utf-8")
    
    assert "cmdLandslidePanel" in commander_html
    assert "cmdCameraPanel" in commander_html
    assert "cmdRainfallPanel" in commander_html

    # Check for light theme background tokens in stat cards
    assert "--bg-panel-raised" in commander_html
    assert "--border" in commander_html

def test_style_css_stat_card_light_theme_rules():
    """Verify style.css enforces light theme tokens for stat-card and commander panels."""
    style_css = (FRONTEND_DIR / "css" / "style.css").read_text(encoding="utf-8")
    
    assert ".stat-card" in style_css
    assert ".commander-landslide-panel" in style_css
    assert "--bg-panel-raised" in style_css
