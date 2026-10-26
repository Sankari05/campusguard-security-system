"""
Tests for Redesigned RIDGEWATCH Logic Page — AI Decision Center & Explainable AI.
Verifies Level 1 to Level 8 information hierarchy:
- Level 1: Hero Decision Cards (Scenario, Risk, Survivor Confidence)
- Level 2: One-Sentence AI Explanation ("Why?")
- Level 3: Sensor Evidence (Primary & Supporting Modalities)
- Level 4: Sensor Fusion Dynamic Flow Diagram
- Level 5: 6-Stage Deterministic Decision Pipeline
- Level 6: Explainable AI Checklist & Conflict Detection
- Level 7: Operational Right Panel (Summary, Active Alerts, Actions, Timeline)
- Level 8: Expandable Technical Calculation Details (Preserved Steps 0 to 9)
"""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGIC_HTML = REPO_ROOT / "frontend" / "logic.html"
LOGIC_JS = REPO_ROOT / "frontend" / "js" / "logic.js"
STYLE_CSS = REPO_ROOT / "frontend" / "css" / "style.css"


def test_logic_html_ai_decision_center_elements():
    """Verify logic.html contains all AI Decision Center components."""
    content = LOGIC_HTML.read_text(encoding="utf-8")

    # Header & Topbar controls
    assert 'id="aiLiveStatusBadge"' in content
    assert 'id="logicScenarioDropdownBtn"' in content
    assert 'id="logicSimClock"' in content
    assert 'id="logicAiEngineState"' in content
    assert 'id="logicVictimTabs"' in content

    # Level 1: Hero Cards
    assert 'id="aiHeroSection"' in content
    assert 'id="aiHeroScenarioCard"' in content
    assert 'id="aiHeroScenarioName"' in content
    assert 'id="aiHeroRiskCard"' in content
    assert 'id="aiHeroRiskScore"' in content
    assert 'id="aiHeroRiskLevel"' in content
    assert 'id="aiHeroConfidenceCard"' in content
    assert 'id="aiHeroConfPct"' in content
    assert 'id="aiHeroTriagePill"' in content

    # Level 2: Why Explanation Banner
    assert 'id="aiWhyBanner"' in content
    assert 'id="aiWhySentence"' in content

    # Level 3: Evidence Grids
    assert 'id="aiEvidenceSection"' in content
    assert 'id="aiEvidencePrimaryGrid"' in content
    assert 'id="aiEvidenceSupportingGrid"' in content
    assert 'id="btnJumpToRoleMatrix"' in content

    # Level 4: Sensor Fusion Diagram
    assert 'id="aiFusionBox"' in content
    assert 'id="aiFusionSvgContainer"' in content
    assert 'id="aiFusionSvg"' in content

    # Level 5: Decision Pipeline (6 stages)
    assert 'id="aiPipelineBox"' in content
    assert 'id="aiPipelineFlow"' in content
    assert 'id="pipeStepEvidence"' in content
    assert 'id="pipeStepConfidence"' in content
    assert 'id="pipeStepTriage"' in content
    assert 'id="pipeStepHazard"' in content
    assert 'id="pipeStepSps"' in content
    assert 'id="pipeStepPriority"' in content

    # Level 6: Explainable AI
    assert 'id="aiExplainBox"' in content
    assert 'id="aiEvidenceBullets"' in content
    assert 'id="aiConflictWarning"' in content

    # Level 7: Operational Right Panel
    assert 'id="aiRiskSummaryCard"' in content
    assert 'id="aiSummaryRiskScore"' in content
    assert 'id="aiSummaryConfidence"' in content
    assert 'id="aiAlertCard"' in content
    assert 'id="aiAlertBadge"' in content
    assert 'id="aiAlertTitle"' in content
    assert 'id="aiActionCard"' in content
    assert 'id="aiActionList"' in content
    assert 'id="aiTimelineCard"' in content
    assert 'id="aiTimelineList"' in content

    # Level 8: Expandable Technical Calculation Details (Steps 0–9)
    assert 'id="btnToggleTechDetails"' in content
    assert 'id="aiTechDetailsContainer"' in content
    assert 'id="logicProfileMatrix"' in content
    assert 'id="logicConfidenceSteps"' in content
    assert 'id="logicTriageBar"' in content
    assert 'id="logicHazardBars"' in content
    assert 'id="logicFinalSps"' in content
    assert 'id="logicLandslideFormula"' in content
    assert 'id="logicCameraThermalFormula"' in content
    assert 'id="logicRainfallFormula"' in content
    assert 'id="logicBaroFormula"' in content
    assert 'id="logicGasSmokeFormula"' in content

    # Live Calculation Workbench & Arithmetic Bar
    assert 'id="aiCalcWorkbench"' in content
    assert 'id="aiCalcTableBody"' in content
    assert 'id="aiCalcArithmeticBar"' in content
    assert 'id="aiMathConfidenceLine"' in content
    assert 'id="aiMathHazardLine"' in content
    assert 'id="aiMathSpsLine"' in content

    # Formula Cards Box
    assert 'id="aiFormulaCardsBox"' in content

    # Earthquake & Geotechnical Intelligence
    assert 'id="aiEarthquakeBox"' in content
    assert 'id="logicEqVibVal"' in content
    assert 'id="logicEqVibStatus"' in content
    assert 'id="logicEqTiltVal"' in content
    assert 'id="logicEqTiltStatus"' in content
    assert 'id="logicEqMultiplierShare"' in content
    assert 'id="logicEqAftershockStatus"' in content
    assert 'id="logicEqKitStatus"' in content


def test_logic_css_ai_decision_center_rules():
    """Verify style.css contains all styling classes for AI Decision Center."""
    content = STYLE_CSS.read_text(encoding="utf-8")

    assert ".ai-hero-grid" in content
    assert ".ai-hero-card" in content
    assert ".ai-why-banner" in content
    assert ".ai-center-layout" in content
    assert ".ai-calc-box" in content
    assert ".ai-calc-table" in content
    assert ".ai-calc-arithmetic-bar" in content
    assert ".ai-formula-grid" in content
    assert ".ai-formula-card" in content
    assert ".ai-earthquake-box" in content
    assert ".ai-eq-grid" in content
    assert ".ai-evidence-section" in content
    assert ".ai-evidence-grid" in content
    assert ".ai-fusion-svg-container" in content
    assert ".ai-pipeline-flow" in content
    assert ".ai-explain-box" in content
    assert ".ai-op-card" in content
    assert ".ai-alert-card" in content
    assert ".ai-action-card" in content
    assert ".ai-timeline-card" in content
    assert ".ai-tech-toggle-btn" in content
    assert ".ai-tech-container" in content


def test_logic_js_engine_functions():
    """Verify logic.js implements full AI Decision Center hierarchy and formulas."""
    content = LOGIC_JS.read_text(encoding="utf-8")

    # Composite Risk and Executive Layer Functions
    assert "calculateCompositeRisk" in content
    assert "renderHeroSection" in content
    assert "renderCalculationWorkbench" in content
    assert "renderEarthquakeSection" in content
    assert "renderWhyBanner" in content
    assert "renderEvidenceSection" in content
    assert "renderFusionDiagram" in content
    assert "renderDecisionPipeline" in content
    assert "renderExplainableChecklist" in content
    assert "renderOperationalPanel" in content

    # Preserved Step 0–Step 9 Technical Formula Functions
    assert "renderProfileMatrix" in content
    assert "renderConfidenceSteps" in content
    assert "renderTriageBar" in content
    assert "renderHazardBars" in content
    assert "renderFinalSps" in content
    assert "renderLandslideLogic" in content
    assert "renderCameraThermalLogic" in content
    assert "renderRainfallLogic" in content
    assert "renderBaroLogic" in content
    assert "renderGasSmokeLogic" in content
