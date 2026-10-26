/* ==========================================================================
   RIDGEWATCH AI DECISION CENTER & SIMULATION LOGIC EXPLAINABILITY
   Pure frontend, read-only operational intelligence & multi-modal fusion.
   Provides real-time explainable decisions, sensor evidence hierarchy,
   fusion flow visualization, tactical alerts, recommended commander actions,
   and expandable deep technical formulas (Steps 0 through 9).
   ========================================================================== */

(() => {
  "use strict";

  // ------------------------------------------------------------------ //
  // Configuration & Constants
  // ------------------------------------------------------------------ //

  const POLL_MS = 3500;

  const TRIAGE_COLORS = {
    HIGH: "#e0311f",
    MEDIUM: "#e8850a",
    LOW: "#d4a90a",
    NO_VITAL_SIGNS: "#8998b8",
    SAFE: "#16a34a",
  };

  const TRIAGE_EMOJI = {
    HIGH: "🔴",
    MEDIUM: "🟠",
    LOW: "🟡",
    NO_VITAL_SIGNS: "⚪",
    SAFE: "🟢",
  };

  const HAZARD_TERM_LABELS = {
    depth: "Burial depth",
    secondary_hazard: "Secondary hazard (active path)",
    exposure: "Exposure duration",
    water_level: "Water level",
    water_rising: "Water rising rate",
    water_flow: "Water flow speed",
    rain: "Rainfall intensity",
    soil: "Soil saturation (landslide)",
    vibration: "Ground vibration (PGV)",
    aftershock_soil_compound: "Aftershock × saturated soil",
    tilt: "Ground/structure tilt",
    cold_exposure: "Cold exposure",
    heat_humidity_compound: "Heat × humidity",
    kit_imu: "Kit disturbed (IMU)",
    pressure_drop: "Barometric pressure drop",
  };

  // ------------------------------------------------------------------ //
  // State
  // ------------------------------------------------------------------ //

  const state = {
    get apiBase() { return RidgeWatchConfig.getApiBase(); },
    config: null,
    victims: [],
    queue: [],
    selectedVictimId: null,
    scenarioRunning: false,
    activeProfile: null,
    recentEvents: [],
  };

  // ------------------------------------------------------------------ //
  // DOM Elements
  // ------------------------------------------------------------------ //

  const el = {
    // Header & Controls
    liveStatusBadge: document.getElementById("aiLiveStatusBadge"),
    scenarioSelectorWrap: document.getElementById("logicScenarioSelectorWrap"),
    scenarioDropdownBtn: document.getElementById("logicScenarioDropdownBtn"),
    selectedScenarioText: document.getElementById("logicSelectedScenarioText"),
    scenarioPopover: document.getElementById("logicScenarioPopover"),
    scenarioSearchInput: document.getElementById("logicScenarioSearchInput"),
    scenarioOptionList: document.getElementById("logicScenarioOptionList"),
    simClock: document.getElementById("logicSimClock"),
    aiEngineState: document.getElementById("logicAiEngineState"),
    statusSub: document.getElementById("logicStatusSub"),
    statusMessage: document.getElementById("logicStatusMessage"),
    statusPoll: document.getElementById("logicStatusPoll"),
    victimTabs: document.getElementById("logicVictimTabs"),

    // Level 1: Hero Section Cards
    heroScenarioName: document.getElementById("aiHeroScenarioName"),
    heroSiteLabel: document.getElementById("aiHeroSiteLabel"),
    heroScenarioStatusPill: document.getElementById("aiHeroScenarioStatusPill"),
    heroRiskScore: document.getElementById("aiHeroRiskScore"),
    heroRiskLevel: document.getElementById("aiHeroRiskLevel"),
    heroRiskTrend: document.getElementById("aiHeroRiskTrend"),
    heroConfPct: document.getElementById("aiHeroConfPct"),
    heroTriagePill: document.getElementById("aiHeroTriagePill"),
    heroSpsScore: document.getElementById("aiHeroSpsScore"),

    // Level 2: Why Banner
    whySentence: document.getElementById("aiWhySentence"),
    calcSummaryBar: document.querySelector(".ai-calc-summary-bar"),
    calcSumConfidence: document.getElementById("aiCalcSumConfidence"),
    calcSumHazard: document.getElementById("aiCalcSumHazard"),
    calcSumSps: document.getElementById("aiCalcSumSps"),
    calcSumRisk: document.getElementById("aiCalcSumRisk"),
    calcSumTriage: document.getElementById("aiCalcSumTriage"),

    // Level 3: Evidence Grids & Calculation Workbench
    calcTableBody: document.getElementById("aiCalcTableBody"),
    mathConfidenceLine: document.getElementById("aiMathConfidenceLine"),
    mathHazardLine: document.getElementById("aiMathHazardLine"),
    mathSpsLine: document.getElementById("aiMathSpsLine"),
    evidenceBadge: document.getElementById("aiEvidenceBadge"),
    btnJumpToRoleMatrix: document.getElementById("btnJumpToRoleMatrix"),
    evidencePrimaryGrid: document.getElementById("aiEvidencePrimaryGrid"),
    evidenceSupportingGrid: document.getElementById("aiEvidenceSupportingGrid"),

    // Earthquake Intelligence Widget
    eqScenarioBadge: document.getElementById("logicEqScenarioBadge"),
    eqVibVal: document.getElementById("logicEqVibVal"),
    eqVibStatus: document.getElementById("logicEqVibStatus"),
    eqTiltVal: document.getElementById("logicEqTiltVal"),
    eqTiltStatus: document.getElementById("logicEqTiltStatus"),
    eqMultiplierShare: document.getElementById("logicEqMultiplierShare"),
    eqAftershockStatus: document.getElementById("logicEqAftershockStatus"),
    eqAftershockSub: document.getElementById("logicEqAftershockSub"),
    eqKitStatus: document.getElementById("logicEqKitStatus"),
    eqKitSub: document.getElementById("logicEqKitSub"),
    eqBeforeSps: document.getElementById("logicEqBeforeSps"),
    eqAfterSps: document.getElementById("logicEqAfterSps"),
    eqSpsDelta: document.getElementById("logicEqSpsDelta"),

    // Level 4: Fusion SVG
    fusionSvg: document.getElementById("aiFusionSvg"),

    // Level 5: Decision Pipeline
    valPipeEvidence: document.getElementById("valPipeEvidence"),
    valPipeConfidence: document.getElementById("valPipeConfidence"),
    valPipeTriage: document.getElementById("valPipeTriage"),
    valPipeHazard: document.getElementById("valPipeHazard"),
    valPipeSps: document.getElementById("valPipeSps"),
    valPipePriority: document.getElementById("valPipePriority"),

    // Level 6: Explainable AI
    evidenceBullets: document.getElementById("aiEvidenceBullets"),
    conflictWarning: document.getElementById("aiConflictWarning"),
    conflictText: document.getElementById("aiConflictText"),

    // Level 7: Operational Right Panel
    summaryRiskScore: document.getElementById("aiSummaryRiskScore"),
    summaryConfidence: document.getElementById("aiSummaryConfidence"),
    summaryEvidenceStrength: document.getElementById("aiSummaryEvidenceStrength"),
    summaryRiskLevel: document.getElementById("aiSummaryRiskLevel"),
    alertCard: document.getElementById("aiAlertCard"),
    alertBadge: document.getElementById("aiAlertBadge"),
    alertTitle: document.getElementById("aiAlertTitle"),
    alertMetaGrid: document.getElementById("aiAlertMetaGrid"),
    alertLocation: document.getElementById("aiAlertLocation"),
    alertConfidence: document.getElementById("aiAlertConfidence"),
    alertTriggers: document.getElementById("aiAlertTriggers"),
    alertTime: document.getElementById("aiAlertTime"),
    actionList: document.getElementById("aiActionList"),
    timelineList: document.getElementById("aiTimelineList"),

    // Level 8: Technical Details (Steps 0–9)
    btnToggleTechDetails: document.getElementById("btnToggleTechDetails"),
    iconTechToggle: document.getElementById("iconTechToggle"),
    techDetailsContainer: document.getElementById("aiTechDetailsContainer"),
    profileMatrix: document.getElementById("logicProfileMatrix"),
    profileSub: document.getElementById("logicProfileSub"),
    confidenceSteps: document.getElementById("logicConfidenceSteps"),
    triageBar: document.getElementById("logicTriageBar"),
    hazardBars: document.getElementById("logicHazardBars"),
    finalSps: document.getElementById("logicFinalSps"),
    landslideFormula: document.getElementById("logicLandslideFormula"),
    landslideSub: document.getElementById("logicLandslideSub"),
    cameraThermalFormula: document.getElementById("logicCameraThermalFormula"),
    cameraThermalSub: document.getElementById("logicCameraThermalSub"),
    rainfallFormula: document.getElementById("logicRainfallFormula"),
    rainfallSub: document.getElementById("logicRainfallSub"),
    baroFormula: document.getElementById("logicBaroFormula"),
    baroSub: document.getElementById("logicBaroSub"),
    gasSmokeFormula: document.getElementById("logicGasSmokeFormula"),
    gasSmokeSub: document.getElementById("logicGasSmokeSub"),
  };

  // ------------------------------------------------------------------ //
  // API Helpers
  // ------------------------------------------------------------------ //

  class ApiError extends Error {
    constructor(status, detail) {
      super(detail || `HTTP ${status}`);
      this.status = status;
    }
  }

  async function apiGet(path) {
    const res = await fetch(state.apiBase + path, { method: "GET" });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail || res.statusText);
    }
    return res.json();
  }

  async function apiPost(path, payload) {
    const res = await fetch(state.apiBase + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail || res.statusText);
    }
    return res.json();
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str == null ? "" : String(str);
    return d.innerHTML;
  }

  // ------------------------------------------------------------------ //
  // Main Polling Loop
  // ------------------------------------------------------------------ //

  async function poll() {
    try {
      if (!state.config) {
        state.config = await apiGet("/fusion-config").catch(() => null);
      }
      const victimsRes = await apiGet("/victims").catch(() => ({ victims: [] }));
      state.victims = victimsRes.victims || [];

      const queueRes = await apiGet("/queue").catch(() => ({ queue: [] }));
      state.queue = queueRes.queue || [];

      state.scenarioRunning = true;

      const profileRes = await apiGet("/scenario/sensor-profile").catch(() => null);
      state.activeProfile = profileRes;

      const landslideRisk = await apiGet("/hazards/landslide/risk").catch(() => null);
      const rainRes = await apiGet("/sensors/rainfall/current").catch(() => null);
      const baroRes = await apiGet("/sensors/pressure/current").catch(() => null);
      const gasSmokeRes = await apiGet("/sensors/gas-smoke/current").catch(() => null);

      if (!state.selectedVictimId || !state.victims.some(v => v.victim_id === state.selectedVictimId)) {
        state.selectedVictimId = state.victims.length ? state.victims[0].victim_id : null;
      }

      const selected = state.victims.find(v => v.victim_id === state.selectedVictimId);
      const f = selected ? (selected.fusion || selected.fused_detection || null) : null;
      const corrRes = state.selectedVictimId ? await apiGet(`/sensors/camera-thermal/correlation?victim_id=${encodeURIComponent(state.selectedVictimId)}`).catch(() => null) : null;

      // Update Topbar Status
      if (el.statusSub) {
        el.statusSub.textContent = `${state.victims.length} node${state.victims.length === 1 ? "" : "s"} online`;
      }
      if (el.statusMessage) {
        el.statusMessage.textContent = "AI Decision Center connected — streaming live intelligence.";
      }
      if (el.simClock) {
        const now = new Date();
        const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
        const cycle = victimsRes.cycle || 0;
        el.simClock.textContent = `🕒 CYCLE ${cycle} · ${timeStr} UTC`;
      }
      if (el.aiEngineState) {
        el.aiEngineState.textContent = "🤖 AI ENGINE: ONLINE";
        el.aiEngineState.className = "ai-engine-badge is-online";
      }

      renderVictimTabs();

      // Render Executive AI Decision Center Layers
      const riskMeta = calculateCompositeRisk(profileRes, landslideRisk, rainRes, baroRes, gasSmokeRes);
      renderHeroSection(profileRes, f, riskMeta);
      renderCalculationWorkbench(f, profileRes, selected, riskMeta);
      renderEarthquakeSection(profileRes, f, selected, landslideRisk);
      renderWhyBanner(profileRes, f, riskMeta, landslideRisk, rainRes, baroRes, gasSmokeRes, corrRes);
      renderEvidenceSection(profileRes, landslideRisk, rainRes, baroRes, gasSmokeRes);
      renderFusionDiagram(profileRes, riskMeta.score, f ? f.confidence_pct : 0);
      renderDecisionPipeline(f, profileRes, riskMeta);
      renderExplainableChecklist(profileRes, f, riskMeta, landslideRisk, rainRes, baroRes, gasSmokeRes, corrRes);
      renderOperationalPanel(riskMeta, f, profileRes, landslideRisk, rainRes, gasSmokeRes);

      // Render Preserved Deep Technical Formulas (Steps 0–9)
      if (profileRes) renderProfileMatrix(profileRes);
      if (f) {
        renderConfidenceSteps(f);
        renderTriageBar(f);
        renderHazardBars(f);
        renderFinalSps(f);
      } else {
        renderEmptyTechnicalWalkthrough();
      }
      if (landslideRisk) renderLandslideLogic(landslideRisk);
      if (corrRes) renderCameraThermalLogic(corrRes);
      if (rainRes) renderRainfallLogic(rainRes, f);
      if (baroRes) renderBaroLogic(baroRes, f);
      if (gasSmokeRes) renderGasSmokeLogic(gasSmokeRes, f);

    } catch (e) {
      state.scenarioRunning = false;
      renderIdleState(e);
    }

    if (el.statusPoll) {
      el.statusPoll.textContent = `poll: ${new Date().toLocaleTimeString([], { hour12: false })}`;
    }
    setTimeout(poll, POLL_MS);
  }

  // ------------------------------------------------------------------ //
  // Composite Risk Engine
  // ------------------------------------------------------------------ //

  function calculateCompositeRisk(profile, landslide, rain, baro, gas) {
    let score = 15.0; // Baseline ambient risk
    let level = "LOW";
    let factors = [];
    let trend = "Nominal stable baseline";

    if (landslide && landslide.risk_score > 0) {
      score = Math.max(score, landslide.risk_score);
      if (landslide.contributing_factors && landslide.contributing_factors.length) {
        factors.push(...landslide.contributing_factors);
      }
    }

    if (rain && rain.rainfall) {
      const rate = rain.rainfall.rainfall_rate_mm_h || 0;
      if (rate >= 25.0) {
        score = Math.max(score, Math.min(100, score + 25.0));
        factors.push(`Heavy precipitation rate (${rate.toFixed(1)} mm/h)`);
      } else if (rate >= 10.0) {
        score = Math.max(score, Math.min(100, score + 12.0));
      }
    }

    if (baro && baro.pressure) {
      const roc = baro.pressure.rate_of_change || 0;
      if (roc <= -3.0 || baro.pressure.pressure_hpa < 990.0) {
        score = Math.max(score, Math.min(100, score + 20.0));
        factors.push("Severe barometric depression plunge");
      }
    }

    if (gas && gas.gas_smoke) {
      const ppm = gas.gas_smoke.gas_concentration_ppm || 0;
      const smoke = gas.gas_smoke.smoke_density_pct || 0;
      if (ppm >= 100.0 || smoke >= 40.0) {
        score = Math.max(score, Math.min(100, score + 35.0));
        factors.push(`Toxic gas / smoke hazard (${ppm.toFixed(0)} PPM, ${smoke.toFixed(0)}% smoke)`);
      }
    }

    // Determine semantic level
    if (score >= 75.0) level = "CRITICAL";
    else if (score >= 50.0) level = "HIGH";
    else if (score >= 30.0) level = "MODERATE";
    else level = "LOW";

    if (factors.length) {
      trend = factors.slice(0, 2).join(" · ");
    }

    return { score: Math.round(score), level, factors, trend };
  }

  // ------------------------------------------------------------------ //
  // Level 1: Hero Section Rendering
  // ------------------------------------------------------------------ //

  function renderHeroSection(profile, f, riskMeta) {
    if (!profile) {
      if (el.heroScenarioName) el.heroScenarioName.textContent = "STANDBY";
      if (el.heroSiteLabel) el.heroSiteLabel.textContent = "Waiting for live scenario telemetry…";
      if (el.heroScenarioStatusPill) {
        el.heroScenarioStatusPill.textContent = "STANDBY";
        el.heroScenarioStatusPill.style.background = "rgba(148,163,184,0.15)";
        el.heroScenarioStatusPill.style.color = "#64748b";
      }
      if (el.heroRiskScore) el.heroRiskScore.innerHTML = `-- <span style="font-size: 16px; font-weight: 500; color: var(--ink-dim);">/ 100</span>`;
      if (el.heroRiskLevel) {
        el.heroRiskLevel.textContent = "STANDBY";
        el.heroRiskLevel.style.background = "rgba(148,163,184,0.15)";
        el.heroRiskLevel.style.color = "#64748b";
      }
      if (el.heroRiskTrend) el.heroRiskTrend.textContent = "Waiting for live scenario telemetry…";
      if (el.heroConfPct) el.heroConfPct.textContent = "--%";
      if (el.heroTriagePill) {
        el.heroTriagePill.textContent = "STANDBY";
        el.heroTriagePill.style.background = "rgba(148,163,184,0.15)";
        el.heroTriagePill.style.color = "#64748b";
      }
      if (el.heroSpsScore) el.heroSpsScore.textContent = "SPS: -- · Multi-Sensor Weighted Reliability: --";
      return;
    }

    // Active Disaster Card
    if (el.heroScenarioName) {
      el.heroScenarioName.textContent = (profile.name || profile.hazard_type || "DISASTER SCENARIO").toUpperCase();
    }
    if (el.heroSiteLabel) {
      el.heroSiteLabel.textContent = `${profile.site_label || "Rescue Site"} · Active Multi-Modal Sensor Gating`;
    }
    if (el.heroScenarioStatusPill) {
      el.heroScenarioStatusPill.textContent = "ACTIVE";
      el.heroScenarioStatusPill.style.background = "rgba(37,99,235,0.12)";
      el.heroScenarioStatusPill.style.color = "#2563eb";
    }

    // Composite Hazard Risk Card
    if (el.heroRiskScore) {
      el.heroRiskScore.innerHTML = `${riskMeta.score} <span style="font-size: 16px; font-weight: 500; color: var(--ink-dim);">/ 100</span>`;
    }
    if (el.heroRiskLevel) {
      el.heroRiskLevel.textContent = riskMeta.level;
      if (riskMeta.level === "CRITICAL") {
        el.heroRiskLevel.style.background = "rgba(239,68,68,0.15)";
        el.heroRiskLevel.style.color = "#dc2626";
      } else if (riskMeta.level === "HIGH") {
        el.heroRiskLevel.style.background = "rgba(249,115,22,0.15)";
        el.heroRiskLevel.style.color = "#ea580c";
      } else if (riskMeta.level === "MODERATE") {
        el.heroRiskLevel.style.background = "rgba(234,179,8,0.15)";
        el.heroRiskLevel.style.color = "#ca8a04";
      } else {
        el.heroRiskLevel.style.background = "rgba(16,185,129,0.15)";
        el.heroRiskLevel.style.color = "#059669";
      }
    }
    if (el.heroRiskTrend) {
      el.heroRiskTrend.textContent = riskMeta.trend;
    }

    // Survivor Detection Confidence Card
    if (f) {
      if (el.heroConfPct) el.heroConfPct.textContent = `${f.confidence_pct.toFixed(1)}%`;
      if (el.heroTriagePill) {
        el.heroTriagePill.textContent = `${TRIAGE_EMOJI[f.triage_class] || ""} ${f.triage_class}`;
        const color = TRIAGE_COLORS[f.triage_class] || "#2563eb";
        el.heroTriagePill.style.background = `${color}20`;
        el.heroTriagePill.style.color = color;
      }
      if (el.heroSpsScore) {
        el.heroSpsScore.textContent = `SPS: ${f.sps.toFixed(2)} · Reliability: ${(f.reliability || 0).toFixed(2)} · Hazard: ${f.hazard_multiplier.toFixed(2)}x`;
      }
    } else {
      if (el.heroConfPct) el.heroConfPct.textContent = "--%";
      if (el.heroTriagePill) {
        el.heroTriagePill.textContent = "WAITING FOR TELEMETRY";
        el.heroTriagePill.style.background = "rgba(148,163,184,0.15)";
        el.heroTriagePill.style.color = "#64748b";
      }
      if (el.heroSpsScore) {
        el.heroSpsScore.textContent = "Waiting for live victim vital telemetry.";
      }
    }
  }

  // ------------------------------------------------------------------ //
  // Level 2: One-Sentence AI Explanation ("Why?")
  // ------------------------------------------------------------------ //

  function renderWhyBanner(profile, f, riskMeta, landslide, rain, baro, gas, corr) {
    if (!el.whySentence) return;

    if (!profile) {
      el.whySentence.textContent = "AI inference standing by. Select an active disaster scenario to inspect live multi-modal fusion evidence.";
      return;
    }

    const hazardType = (profile.hazard_type || "").toLowerCase();
    let explanation = "";

    if (hazardType.includes("landslide") || profile.name.toLowerCase().includes("landslide")) {
      const moist = landslide && landslide.score_breakdown ? (landslide.score_breakdown.moisture_subscore || 0) : 0;
      const tilt = landslide && landslide.score_breakdown ? (landslide.score_breakdown.tilt_subscore || 0) : 0;
      const rate = rain && rain.rainfall ? rain.rainfall.rainfall_rate_mm_h : 0;
      explanation = `Landslide risk classified as ${riskMeta.level} (${riskMeta.score}/100) due to elevated soil moisture saturation and abnormal inclinometer ground tilt${rate > 5 ? `, corroborated by active rainfall at ${rate.toFixed(1)} mm/h` : ""}.`;
    } else if (hazardType.includes("flood") || profile.name.toLowerCase().includes("flood")) {
      const rate = rain && rain.rainfall ? rain.rainfall.rainfall_rate_mm_h : 0;
      explanation = `Flood risk elevated to ${riskMeta.level} (${riskMeta.score}/100) driven by active surface runoff accumulation and heavy precipitation rate at ${rate.toFixed(1)} mm/h.`;
    } else if (hazardType.includes("chemical") || hazardType.includes("gas") || profile.name.toLowerCase().includes("chemical")) {
      const ppm = gas && gas.gas_smoke ? gas.gas_smoke.gas_concentration_ppm : 0;
      explanation = `Toxic atmospheric threat classified as ${riskMeta.level} with gas concentration at ${ppm.toFixed(1)} PPM exceeding standard exposure thresholds, requiring mandatory SCBA life safety doctrine.`;
    } else if (hazardType.includes("earthquake") || profile.name.toLowerCase().includes("earthquake") || profile.name.toLowerCase().includes("collapse")) {
      explanation = `Structural collapse assessment active with seismic IMU vibration tracking and multi-modal void search${f ? ` confirming survivor vital signs at ${f.confidence_pct.toFixed(1)}% confidence` : ""}.`;
    } else if (hazardType.includes("cyclone") || profile.name.toLowerCase().includes("cyclone")) {
      const p = baro && baro.pressure ? baro.pressure.pressure_hpa : 1013;
      explanation = `Severe cyclonic depression tracking at ${p.toFixed(1)} hPa with rapid barometric pressure plunge, multiplying secondary inundation threat.`;
    } else {
      explanation = `Multi-modal sensor fusion active for ${profile.name} at ${riskMeta.score}/100 composite risk, continuously gating baseline noise and verifying cross-sensor evidence channels.`;
    }

    if (f && f.confidence_pct > 50) {
      explanation += ` Target victim node indicates high vital sign corroboration (${f.confidence_pct.toFixed(1)}% Confidence, ${f.triage_class} Triage Priority).`;
    }

    el.whySentence.textContent = explanation;
  }

  // ------------------------------------------------------------------ //
  // Live Multi-Modal Calculation Workbench
  // ------------------------------------------------------------------ //

  function renderCalculationWorkbench(f, profile, victim, riskMeta) {
    if (!el.calcTableBody) return;

    if (!f || !f.score_breakdown) {
      if (el.calcSumConfidence) el.calcSumConfidence.textContent = "--%";
      if (el.calcSumHazard) el.calcSumHazard.textContent = "--x";
      if (el.calcSumSps) el.calcSumSps.textContent = "--";
      if (el.calcSumRisk) el.calcSumRisk.textContent = riskMeta && profile ? `${riskMeta.score} / 100` : "-- / 100";
      if (el.calcSumTriage) {
        el.calcSumTriage.textContent = "STANDBY";
        el.calcSumTriage.style.color = "#64748b";
      }
      el.calcTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--ink-dim); padding: 14px;">Waiting for live victim telemetry…</td></tr>`;
      if (el.mathConfidenceLine) el.mathConfidenceLine.innerHTML = `100 × (Σ wᵢ · sᵢ) × R = <strong>--%</strong>`;
      if (el.mathHazardLine) el.mathHazardLine.innerHTML = `Base (1.00) + Σ Hazards = <strong>--x</strong>`;
      if (el.mathSpsLine) el.mathSpsLine.innerHTML = `Confidence % × Hazard Multiplier = <strong style="color: #2563eb; font-size: 13.5px;">--</strong>`;
      return;
    }

    // Populate Calculation Summary Bar
    if (el.calcSumConfidence) el.calcSumConfidence.textContent = `${f.confidence_pct.toFixed(1)}%`;
    if (el.calcSumHazard) el.calcSumHazard.textContent = `${f.hazard_multiplier.toFixed(3)}x`;
    if (el.calcSumSps) el.calcSumSps.textContent = `${f.sps.toFixed(2)}`;
    if (el.calcSumRisk) el.calcSumRisk.textContent = riskMeta ? `${riskMeta.score} / 100` : "-- / 100";
    if (el.calcSumTriage) {
      el.calcSumTriage.textContent = `${TRIAGE_EMOJI[f.triage_class] || ""} ${f.triage_class}`;
      el.calcSumTriage.style.color = TRIAGE_COLORS[f.triage_class] || "#2563eb";
    }

    const w = state.config ? state.config.confidence_weights : { radar: 0.35, thermal: 0.25, acoustic: 0.20, co2: 0.10, camera: 0.10 };
    const sb = f.score_breakdown || {};
    const rel = f.reliability != null ? f.reliability : 1.0;

    const modalities = [
      {
        name: "Radar / Pulse",
        icon: "💓",
        weight: w.radar || 0.35,
        subscore: sb.heart_rate_radar != null ? sb.heart_rate_radar : 0.0,
        signal: (victim && victim.sensors && victim.sensors.heart_rate_radar && victim.sensors.heart_rate_radar.value != null)
          ? `${victim.sensors.heart_rate_radar.value.toFixed(0)} BPM`
          : (victim && victim.raw_sensor_frame && victim.raw_sensor_frame.radar_bpm != null ? `${victim.raw_sensor_frame.radar_bpm.toFixed(0)} BPM` : "Active Signal"),
        role: "PRIMARY"
      },
      {
        name: "Thermal Imaging",
        icon: "🌡️",
        weight: w.thermal || 0.25,
        subscore: sb.thermal_imaging != null ? sb.thermal_imaging : 0.0,
        signal: (victim && victim.sensors && victim.sensors.thermal_imaging && victim.sensors.thermal_imaging.value != null)
          ? `${victim.sensors.thermal_imaging.value.toFixed(1)}°C`
          : (victim && victim.raw_sensor_frame && victim.raw_sensor_frame.thermal_c != null ? `${victim.raw_sensor_frame.thermal_c.toFixed(1)}°C` : "Active Signal"),
        role: "PRIMARY"
      },
      {
        name: "Acoustic / Taps",
        icon: "🔊",
        weight: w.acoustic || 0.20,
        subscore: sb.acoustic != null ? sb.acoustic : 0.0,
        signal: f.tapping_detected
          ? "👊 Tapping Active"
          : ((victim && victim.sensors && victim.sensors.acoustic && victim.sensors.acoustic.value != null)
              ? `${victim.sensors.acoustic.value.toFixed(0)} dB`
              : (victim && victim.raw_sensor_frame && victim.raw_sensor_frame.acoustic_db != null ? `${victim.raw_sensor_frame.acoustic_db.toFixed(0)} dB` : "Nominal")),
        role: "SUPPORTING"
      },
      {
        name: "CO₂ Respiration",
        icon: "💨",
        weight: w.co2 || 0.10,
        subscore: sb.co2 != null ? sb.co2 : 0.0,
        signal: (victim && victim.sensors && victim.sensors.co2 && victim.sensors.co2.value != null)
          ? `${victim.sensors.co2.value.toFixed(0)} PPM`
          : (victim && victim.raw_sensor_frame && victim.raw_sensor_frame.co2_ppm != null ? `${victim.raw_sensor_frame.co2_ppm.toFixed(0)} PPM` : "Nominal"),
        role: "SUPPORTING"
      },
      {
        name: "Optical Camera",
        icon: "📷",
        weight: w.camera || 0.10,
        subscore: sb.rgb_camera != null ? sb.rgb_camera : (sb.optical_camera != null ? sb.optical_camera : 0.0),
        signal: (() => {
          const camVal = (victim && victim.sensors && victim.sensors.rgb_camera && victim.sensors.rgb_camera.value != null)
            ? victim.sensors.rgb_camera.value
            : ((victim && victim.sensors && victim.sensors.optical_camera && victim.sensors.optical_camera.value != null)
                ? victim.sensors.optical_camera.value
                : (victim && victim.raw_sensor_frame ? victim.raw_sensor_frame.camera_confidence : null));
          if (camVal == null) return "Standard";
          const pct = camVal <= 1.0 ? Math.round(camVal * 100) : Math.round(camVal);
          return `${pct}% Conf`;
        })(),
        role: "SUPPORTING"
      }
    ];

    let sumWeightedScore = 0;

    const rowsHtml = modalities.map(m => {
      const share = m.weight * m.subscore * rel;
      sumWeightedScore += m.weight * m.subscore;
      const isContributing = m.subscore > 0.01;
      const scoreColor = m.subscore >= 0.7 ? "#16a34a" : (m.subscore >= 0.3 ? "#2563eb" : (m.subscore > 0.05 ? "#ea580c" : "#64748b"));
      const pctWidth = Math.min(100, Math.max(0, Math.round(m.subscore * 100)));

      return `
        <tr>
          <td>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span>${m.icon}</span>
              <strong>${escapeHtml(m.name)}</strong>
            </div>
          </td>
          <td><span class="ai-calc-pill weight">${(m.weight * 100).toFixed(0)}%</span></td>
          <td style="font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: ${isContributing ? '#0f2547' : '#8998b8'}; font-weight: 600;">
            ${escapeHtml(m.signal)}
          </td>
          <td>
            <div style="display: flex; flex-direction: column; gap: 4px; min-width: 100px;">
              <div style="display: flex; align-items: center; justify-content: space-between; gap: 6px;">
                <span class="ai-calc-pill score" style="color: ${scoreColor}; font-weight: 700;">${m.subscore.toFixed(2)}</span>
                <span style="font-size: 10.5px; color: var(--ink-dim); font-family: 'JetBrains Mono', monospace;">${pctWidth}%</span>
              </div>
              <div class="ai-calc-progress-wrap">
                <div class="ai-calc-progress-fill" style="width: ${pctWidth}%; background: ${scoreColor};"></div>
              </div>
            </div>
          </td>
          <td><span class="ai-calc-pill rel">${rel.toFixed(2)}</span></td>
          <td style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: ${share > 0 ? '#2563eb' : '#8998b8'};">
            +${share.toFixed(3)}
          </td>
        </tr>
      `;
    }).join("");

    el.calcTableBody.innerHTML = rowsHtml;

    // Arithmetic lines
    if (el.mathConfidenceLine) {
      el.mathConfidenceLine.innerHTML = `100 × (${sumWeightedScore.toFixed(3)} Σ wᵢ · sᵢ) × ${rel.toFixed(2)} = <strong>${f.confidence_pct.toFixed(1)}%</strong>`;
    }
    if (el.mathHazardLine) {
      const hazardBonus = Math.max(0, f.hazard_multiplier - 1.0);
      el.mathHazardLine.innerHTML = `Base (1.00) + Hazard Bonuses (+${hazardBonus.toFixed(3)}) = <strong>${f.hazard_multiplier.toFixed(3)}x</strong>`;
    }
    if (el.mathSpsLine) {
      el.mathSpsLine.innerHTML = `${f.confidence_pct.toFixed(1)}% × ${f.hazard_multiplier.toFixed(3)} = <strong style="color: #2563eb; font-size: 13.5px;">${f.sps.toFixed(2)} SPS</strong> (${f.triage_class})`;
    }
  }

  // ------------------------------------------------------------------ //
  // Dedicated Earthquake & Geotechnical Intelligence Section
  // ------------------------------------------------------------------ //

  function renderEarthquakeSection(profile, f, victim, landslideRisk) {
    if (!el.eqVibVal) return;

    let vibVal = 0.0;
    let tiltVal = 0.0;
    let aftershockBonus = 0.0;
    let kitBonus = 0.0;

    if (f && f.hazard_breakdown) {
      const hb = f.hazard_breakdown;
      if (hb.vibration != null && hb.vibration > 0) {
        vibVal = (hb.vibration / 0.20) * 20.0;
      }
      if (hb.tilt != null && hb.tilt > 0) {
        tiltVal = 5.0 + (hb.tilt / 0.30) * (15.0 - 5.0);
      }
      aftershockBonus = hb.aftershock_soil_compound || 0.0;
      kitBonus = hb.kit_imu || 0.0;
    }

    if (profile && profile.sensor_matrix) {
      const vibSensor = profile.sensor_matrix.find(s => (s.sensor_type || "").toLowerCase().includes("vibration") || (s.sensor_type || "").toLowerCase().includes("seismic"));
      if (vibSensor && vibSensor.current_value != null && vibSensor.current_value > 0) {
        vibVal = vibSensor.current_value;
      }
      const tiltSensor = profile.sensor_matrix.find(s => (s.sensor_type || "").toLowerCase().includes("tilt") || (s.sensor_type || "").toLowerCase().includes("inclinometer"));
      if (tiltSensor && tiltSensor.current_value != null && tiltSensor.current_value > 0) {
        tiltVal = tiltSensor.current_value;
      }
    }

    if (landslideRisk && landslideRisk.score_breakdown && landslideRisk.score_breakdown.tilt_subscore > 0) {
      tiltVal = Math.max(tiltVal, (landslideRisk.score_breakdown.tilt_subscore / 25.0) * 15.0);
    }

    const eqTotalBonus = (f && f.hazard_breakdown ? (f.hazard_breakdown.vibration || 0) + (f.hazard_breakdown.tilt || 0) + aftershockBonus + kitBonus : 0);

    if (el.eqScenarioBadge) {
      el.eqScenarioBadge.textContent = profile ? `${profile.name} · Geotechnical Core` : "Seismic & Inclinometer Tracking";
    }

    el.eqVibVal.textContent = `${vibVal.toFixed(1)} mm/s`;
    if (vibVal >= 10.0) {
      el.eqVibStatus.textContent = "CRITICAL VIB";
      el.eqVibStatus.className = "ai-eq-status trend-rising";
    } else if (vibVal >= 3.0) {
      el.eqVibStatus.textContent = "ELEVATED";
      el.eqVibStatus.className = "ai-eq-status trend-abnormal";
    } else {
      el.eqVibStatus.textContent = "NOMINAL";
      el.eqVibStatus.className = "ai-eq-status trend-nominal";
    }

    el.eqTiltVal.textContent = `${tiltVal.toFixed(1)}°`;
    if (tiltVal >= 10.0) {
      el.eqTiltStatus.textContent = "SHEAR FAILURE";
      el.eqTiltStatus.className = "ai-eq-status trend-rising";
    } else if (tiltVal >= 4.0) {
      el.eqTiltStatus.textContent = "UNSTABLE TILT";
      el.eqTiltStatus.className = "ai-eq-status trend-abnormal";
    } else {
      el.eqTiltStatus.textContent = "STABLE";
      el.eqTiltStatus.className = "ai-eq-status trend-nominal";
    }

    if (el.eqMultiplierShare) {
      el.eqMultiplierShare.textContent = `+${eqTotalBonus.toFixed(3)}x`;
    }

    if (el.eqAftershockStatus) {
      if (aftershockBonus > 0 || (profile && profile.name.toLowerCase().includes("earthquake"))) {
        el.eqAftershockStatus.textContent = "ACTIVE TREMOR";
        if (el.eqAftershockSub) {
          el.eqAftershockSub.textContent = "COMPOUND SOIL RISK";
          el.eqAftershockSub.className = "ai-eq-status trend-rising";
        }
      } else {
        el.eqAftershockStatus.textContent = "NO TREMORS";
        if (el.eqAftershockSub) {
          el.eqAftershockSub.textContent = "DECAYED / STABLE";
          el.eqAftershockSub.className = "ai-eq-status trend-nominal";
        }
      }
    }

    if (el.eqKitStatus) {
      if (kitBonus > 0) {
        el.eqKitStatus.textContent = "DISTURBANCE DETECTED";
        if (el.eqKitSub) {
          el.eqKitSub.textContent = "LOCALIZED JITTER";
          el.eqKitSub.className = "ai-eq-status trend-abnormal";
        }
      } else {
        el.eqKitStatus.textContent = "QUIESCENT";
        if (el.eqKitSub) {
          el.eqKitSub.textContent = "NO JITTER";
          el.eqKitSub.className = "ai-eq-status trend-nominal";
        }
      }
    }

    // Before vs After Impact on SPS
    if (f) {
      const nonSeismicMultiplier = Math.max(1.0, f.hazard_multiplier - eqTotalBonus);
      const beforeSps = f.confidence_pct * nonSeismicMultiplier;
      const afterSps = f.sps;
      const delta = Math.max(0, afterSps - beforeSps);

      if (el.eqBeforeSps) el.eqBeforeSps.textContent = `${beforeSps.toFixed(2)} SPS`;
      if (el.eqAfterSps) el.eqAfterSps.textContent = `${afterSps.toFixed(2)} SPS`;
      if (el.eqSpsDelta) {
        if (delta > 0.001) {
          el.eqSpsDelta.textContent = `+${delta.toFixed(2)} pts (Seismic Multiplier +${eqTotalBonus.toFixed(3)}x)`;
        } else {
          el.eqSpsDelta.textContent = "+0.00 pts (No seismic escalation)";
        }
      }
    } else {
      if (el.eqBeforeSps) el.eqBeforeSps.textContent = "--";
      if (el.eqAfterSps) el.eqAfterSps.textContent = "--";
      if (el.eqSpsDelta) el.eqSpsDelta.textContent = "--";
    }
  }

  // ------------------------------------------------------------------ //
  // Level 3: Sensor Evidence Section (Primary vs Supporting)
  // ------------------------------------------------------------------ //

  function renderEvidenceSection(profile, landslide, rain, baro, gas) {
    if (!el.evidencePrimaryGrid || !el.evidenceSupportingGrid) return;

    if (!profile || !profile.sensor_matrix || !profile.sensor_matrix.length) {
      el.evidencePrimaryGrid.innerHTML = `<div style="grid-column:1/-1; padding: 12px; font-size: 11.5px; color: var(--ink-dim); text-align: center;">Awaiting active scenario telemetry…</div>`;
      el.evidenceSupportingGrid.innerHTML = `<div style="grid-column:1/-1; padding: 12px; font-size: 11.5px; color: var(--ink-dim); text-align: center;">Awaiting supporting sensor channels…</div>`;
      return;
    }

    const primarySensors = profile.sensor_matrix.filter(s => s.role === "PRIMARY");
    const supportingSensors = profile.sensor_matrix.filter(s => s.role === "SUPPORTING");

    function renderCards(sensors, isPrimary) {
      if (!sensors.length) {
        return `<div style="grid-column:1/-1; padding: 10px; font-size: 11.5px; color: var(--ink-dim); text-align: center;">No ${isPrimary ? 'primary' : 'supporting'} sensors assigned for this scenario profile.</div>`;
      }

      return sensors.map(s => {
        const valStr = s.current_value != null ? `${s.current_value} ${s.unit || ''}` : "0.0";
        let trendClass = "trend-nominal";
        let trendLabel = "NOMINAL";

        const type = (s.sensor_type || "").toLowerCase();
        if (type.includes("moisture") || type.includes("water") || type.includes("gas")) {
          trendClass = "trend-rising";
          trendLabel = "↑ RISING";
        } else if (type.includes("tilt") || type.includes("imu") || type.includes("pressure")) {
          trendClass = "trend-abnormal";
          trendLabel = "↑ ELEVATED";
        } else if (type.includes("rain") || type.includes("smoke") || type.includes("temperature")) {
          trendClass = "trend-increasing";
          trendLabel = "↑ ACTIVE";
        }

        const roleBadgeClass = isPrimary ? "hw-role-primary" : "hw-role-supporting";

        return `
          <div class="ai-evidence-card ${isPrimary ? 'is-primary' : 'is-supporting'}">
            <div class="ai-evidence-card-top">
              <span class="ai-evidence-name">${escapeHtml(s.sensor_type)}</span>
              <span class="ai-evidence-role-badge ${roleBadgeClass}">${escapeHtml(s.role)}</span>
            </div>
            <div class="ai-evidence-val-row">
              <span class="ai-evidence-val">${escapeHtml(valStr)}</span>
              <span class="ai-evidence-trend ${trendClass}">${trendLabel}</span>
            </div>
            <div class="ai-evidence-sub">Fusion Weight: ${(s.weight * 100).toFixed(0)}% · Active Trigger Channel</div>
          </div>
        `;
      }).join("");
    }

    el.evidencePrimaryGrid.innerHTML = renderCards(primarySensors, true);
    el.evidenceSupportingGrid.innerHTML = renderCards(supportingSensors, false);
  }

  // ------------------------------------------------------------------ //
  // Level 4: Sensor Fusion Dynamic SVG Diagram
  // ------------------------------------------------------------------ //

  function renderFusionDiagram(profile, riskScore, confPct) {
    if (!el.fusionSvg) return;

    if (!profile || !profile.sensor_matrix) {
      el.fusionSvg.innerHTML = `
        <text x="350" y="95" text-anchor="middle" fill="#8998b8" font-family="'JetBrains Mono', monospace" font-size="12">
          Awaiting active multi-modal sensor telemetry…
        </text>
      `;
      return;
    }

    const activeSensors = profile.sensor_matrix.filter(s => s.role === "PRIMARY" || s.role === "SUPPORTING").slice(0, 4);
    if (!activeSensors.length) {
      el.fusionSvg.innerHTML = `
        <text x="350" y="95" text-anchor="middle" fill="#8998b8" font-family="'JetBrains Mono', monospace" font-size="12">
          All sensor channels currently at standby baseline.
        </text>
      `;
      return;
    }

    let svgHtml = "";
    const startX = 140;
    const coreX = 350;
    const outX = 560;
    const stepY = 160 / (activeSensors.length + 1);

    // Draw Input Nodes and Beams
    activeSensors.forEach((s, idx) => {
      const y = stepY * (idx + 1);
      const isPrimary = s.role === "PRIMARY";
      const beamClass = isPrimary ? "fusion-line-primary" : "fusion-line-supporting";
      const nodeColor = isPrimary ? "#2563eb" : "#0d9488";

      // Connecting Path Curve
      svgHtml += `
        <path d="M ${startX + 10} ${y} C ${startX + 90} ${y}, ${coreX - 90} 90, ${coreX - 45} 90" fill="none" class="${beamClass}" />
      `;

      // Input Node Card
      svgHtml += `
        <g transform="translate(${startX - 110}, ${y - 14})">
          <rect width="115" height="28" rx="6" fill="#ffffff" stroke="${nodeColor}" stroke-width="1.5" filter="drop-shadow(0 2px 4px rgba(15,37,71,0.06))" />
          <text x="58" y="14" text-anchor="middle" dominant-baseline="middle" font-family="'Space Grotesk', sans-serif" font-size="10" font-weight="700" fill="#0f2547">
            ${escapeHtml(s.sensor_type.length > 14 ? s.sensor_type.slice(0, 13) + '…' : s.sensor_type)}
          </text>
        </g>
      `;
    });

    // Output Connecting Path
    svgHtml += `
      <path d="M ${coreX + 45} 90 C ${coreX + 110} 90, ${outX - 70} 90, ${outX - 25} 90" fill="none" class="fusion-line-primary" />
    `;

    // Central Fusion Core Node
    svgHtml += `
      <g transform="translate(${coreX}, 90)">
        <circle r="42" fill="url(#fusionGrad)" stroke="#2563eb" stroke-width="2" />
        <circle r="48" fill="none" stroke="#93c5fd" stroke-width="1" stroke-dasharray="3 3" />
        <text x="0" y="-8" text-anchor="middle" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="700" fill="#2563eb">SENSOR FUSION</text>
        <text x="0" y="8" text-anchor="middle" font-family="'Space Grotesk', sans-serif" font-size="12" font-weight="800" fill="#0f2547">AI CORE</text>
        <text x="0" y="20" text-anchor="middle" font-family="'JetBrains Mono', monospace" font-size="8" fill="#4d5f80">REAL-TIME</text>
      </g>
    `;

    // Output Decision Node
    svgHtml += `
      <g transform="translate(${outX - 20}, 58)">
        <rect width="145" height="64" rx="8" fill="#ffffff" stroke="#2563eb" stroke-width="2" filter="drop-shadow(0 4px 10px rgba(37,99,235,0.1))" />
        <text x="72" y="16" text-anchor="middle" font-family="'JetBrains Mono', monospace" font-size="9" font-weight="700" fill="#2563eb">DECISION OUTPUT</text>
        <text x="72" y="34" text-anchor="middle" font-family="'Space Grotesk', sans-serif" font-size="13" font-weight="800" fill="#0f2547">RISK: ${riskScore}/100</text>
        <text x="72" y="50" text-anchor="middle" font-family="'JetBrains Mono', monospace" font-size="10" font-weight="700" fill="#059669">CONFIDENCE: ${confPct.toFixed(1)}%</text>
      </g>
    `;

    // SVG Gradient Definitions
    svgHtml = `
      <defs>
        <radialGradient id="fusionGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#eff6ff" />
          <stop offset="100%" stop-color="#dbeafe" />
        </radialGradient>
      </defs>
    ` + svgHtml;

    el.fusionSvg.innerHTML = svgHtml;
  }

  // ------------------------------------------------------------------ //
  // Level 5: AI Decision Pipeline (Compact 6-Stage Flow)
  // ------------------------------------------------------------------ //

  function renderDecisionPipeline(f, profile, riskMeta) {
    if (!el.valPipeEvidence) return;

    const primaryCount = profile && profile.sensor_matrix ? profile.sensor_matrix.filter(s => s.role === "PRIMARY" || s.role === "SUPPORTING").length : 0;

    if (f) {
      el.valPipeEvidence.textContent = `${primaryCount} Active Modalities`;
      el.valPipeConfidence.textContent = `${f.confidence_pct.toFixed(1)}% (Rel: ${(f.reliability || 0).toFixed(2)})`;
      el.valPipeTriage.textContent = `Fused: ${f.confidence_pct.toFixed(1)}%`;
      el.valPipeHazard.textContent = `Multiplier: ${f.hazard_multiplier.toFixed(2)}x`;
      if (el.valPipeSps) el.valPipeSps.textContent = `${f.sps.toFixed(2)} SPS`;
      el.valPipePriority.textContent = `${f.sps.toFixed(1)} SPS · ${TRIAGE_EMOJI[f.triage_class] || ""} ${f.triage_class}`;
    } else {
      el.valPipeEvidence.textContent = primaryCount > 0 ? `${primaryCount} Configured Channels` : "Standby";
      el.valPipeConfidence.textContent = "Confidence: --%";
      el.valPipeTriage.textContent = "Fused: --%";
      el.valPipeHazard.textContent = "Multiplier: --x";
      if (el.valPipeSps) el.valPipeSps.textContent = "-- SPS";
      el.valPipePriority.textContent = "-- SPS · STANDBY";
    }
  }

  // ------------------------------------------------------------------ //
  // Level 6: Explainable AI Checklist & Conflict Detection
  // ------------------------------------------------------------------ //

  function renderExplainableChecklist(profile, f, riskMeta, landslide, rain, baro, gas, corr) {
    if (!el.evidenceBullets) return;

    const sections = [];

    // 1. Which sensors increased confidence
    const confSensors = [];
    if (f && f.score_breakdown) {
      const sb = f.score_breakdown;
      if (sb.heart_rate_radar > 0.05) confSensors.push(`Radar pulse (score: ${sb.heart_rate_radar.toFixed(2)})`);
      if (sb.thermal_imaging > 0.05) confSensors.push(`Thermal body heat (score: ${sb.thermal_imaging.toFixed(2)})`);
      if (sb.acoustic > 0.05 || f.tapping_detected) confSensors.push(`Acoustic vibrations${f.tapping_detected ? ' [Tapping Detected]' : ''} (score: ${(sb.acoustic || 0).toFixed(2)})`);
      if (sb.co2 > 0.05) confSensors.push(`CO₂ exhalation (score: ${sb.co2.toFixed(2)})`);
      if (sb.rgb_camera > 0.05 || (sb.optical_camera && sb.optical_camera > 0.05)) confSensors.push(`Optical camera confirmation (score: ${(sb.rgb_camera || sb.optical_camera).toFixed(2)})`);
    }

    if (confSensors.length) {
      sections.push({
        title: "Life-Sign Confidence Contributors",
        desc: `${confSensors.join(" and ")} actively increased detection confidence to ${f.confidence_pct.toFixed(1)}%.`
      });
    } else if (f) {
      sections.push({
        title: "Life-Sign Assessment",
        desc: "All physiological sensor channels currently below critical vital detection thresholds (0.00 subscore)."
      });
    }

    // 2. Which hazards increased the multiplier
    const hazardFactors = [];
    if (f && f.hazard_breakdown) {
      const hb = f.hazard_breakdown;
      if (hb.depth > 0) hazardFactors.push(`Burial depth (+${hb.depth.toFixed(2)}x)`);
      if (hb.secondary_hazard > 0) hazardFactors.push(`Active secondary hazard path (+${hb.secondary_hazard.toFixed(2)}x)`);
      if (hb.vibration > 0) hazardFactors.push(`Ground vibration (+${hb.vibration.toFixed(2)}x)`);
      if (hb.tilt > 0) hazardFactors.push(`Ground tilt (+${hb.tilt.toFixed(2)}x)`);
      if (hb.rain > 0) hazardFactors.push(`Rainfall rate (+${hb.rain.toFixed(2)}x)`);
      if (hb.soil > 0) hazardFactors.push(`Saturated soil (+${hb.soil.toFixed(2)}x)`);
      if (hb.water_level > 0 || hb.water_rising > 0) hazardFactors.push(`Water immersion (+${((hb.water_level || 0) + (hb.water_rising || 0)).toFixed(2)}x)`);
      if (hb.aftershock_soil_compound > 0) hazardFactors.push(`Compound aftershock × soil (+${hb.aftershock_soil_compound.toFixed(2)}x)`);
      if (hb.pressure_drop > 0) hazardFactors.push(`Barometric depression (+${hb.pressure_drop.toFixed(2)}x)`);
      if (hb.kit_imu > 0) hazardFactors.push(`Local kit disturbance (+${hb.kit_imu.toFixed(2)}x)`);
    }

    if (hazardFactors.length) {
      sections.push({
        title: "Situational Hazard Multipliers",
        desc: `${hazardFactors.join(", ")} raised the hazard multiplier to ${f.hazard_multiplier.toFixed(3)}x.`
      });
    } else if (f) {
      sections.push({
        title: "Hazard Synthesis",
        desc: "Environmental threats currently operating at baseline nominal multiplier (1.000x)."
      });
    }

    // 3. Which sensors are unavailable or weak / dormant
    if (f && f.score_breakdown) {
      const sb = f.score_breakdown;
      const weakSensors = [];

      if (sb.heart_rate_radar <= 0.05) weakSensors.push("Radar (no rhythmic pulse)");
      if (sb.thermal_imaging <= 0.05) weakSensors.push("Thermal (within ambient envelope)");
      if (sb.acoustic <= 0.05 && !f.tapping_detected) weakSensors.push("Acoustic (no resonant tapping detected)");
      if (sb.co2 <= 0.05) weakSensors.push("CO₂ (baseline ambient ~410 PPM)");
      if ((sb.rgb_camera || 0) <= 0.05 && (sb.optical_camera || 0) <= 0.05) weakSensors.push("Optical (obscured / dark void)");

      if (profile && profile.sensor_matrix) {
        profile.sensor_matrix.filter(s => s.role === "INACTIVE").forEach(s => {
          if (!weakSensors.some(ws => ws.toLowerCase().includes(s.sensor_type.toLowerCase()))) {
            weakSensors.push(`${s.sensor_type} (de-weighted for ${profile.name || 'scenario'})`);
          }
        });
      }

      if (weakSensors.length) {
        sections.push({
          title: "Unavailable or Weak Sensor Modalities",
          desc: `${weakSensors.join(" · ")} — these channels contributed 0.00 to prevent false-alarm escalation.`
        });
      }
    }

    // 4. Why the final triage level was selected
    if (f) {
      const triage = f.triage_class;
      let rationale = "";
      if (triage === "HIGH") {
        rationale = f.tapping_detected
          ? `Classified as HIGH PRIORITY: Deliberate acoustic tapping detected (lowering high threshold to 15%) combined with verified life signs (Confidence ${f.confidence_pct.toFixed(1)}%).`
          : `Classified as HIGH PRIORITY: Multi-modal Confidence (${f.confidence_pct.toFixed(1)}% ≥ 30.0%) and SPS (${f.sps.toFixed(2)}) demand immediate tactical SAR extraction.`;
      } else if (triage === "MEDIUM") {
        rationale = `Classified as MEDIUM PRIORITY: Confidence (${f.confidence_pct.toFixed(1)}% in 15%–30% window) confirms probable survivor requiring prioritized response.`;
      } else if (triage === "LOW") {
        rationale = `Classified as LOW PRIORITY: Confidence (${f.confidence_pct.toFixed(1)}% in 5%–15% range) shows weak physiological signatures requiring secondary sensor passes.`;
      } else if (triage === "SAFE") {
        rationale = `Classified as SAFE / SELF-EVACUATING: Visual and thermal motility confirm ambulatory survivor without life-threatening burial.`;
      } else {
        rationale = `Classified as NO VITAL SIGNS: Fused confidence (${f.confidence_pct.toFixed(1)}% < 5.0%) confirms absence of detectable vital rhythms.`;
      }

      sections.push({
        title: "Triage & Rescue Priority Rationale",
        desc: rationale
      });
    }

    // Geotechnical / Cross-Modal Specifics
    if (landslide && landslide.risk_score >= 50) {
      sections.push({
        title: "Geotechnical Warning",
        desc: `Soil moisture saturation and inclinometer tilt rate confirm active slope failure vector.`
      });
    }

    if (corr && corr.correlation && corr.correlation.synergy_bonus > 0) {
      sections.push({
        title: "Optical & Thermal Synergy",
        desc: `Cross-modal visual and infrared synergy verified (+${Math.round(corr.correlation.synergy_bonus * 100)}% confidence bonus).`
      });
    }

    if (!sections.length) {
      sections.push({
        title: "Standby Operational Mode",
        desc: "AI Decision Center standing by. Multi-modal sensor cross-gating active to prevent single-sensor false alarms."
      });
    }

    el.evidenceBullets.innerHTML = sections.map(s => `
      <div class="ai-bullet-item">
        <span class="ai-bullet-icon">✓</span>
        <div>
          <strong style="color: var(--ink, #0f2547); display: block; font-size: 12px; margin-bottom: 2px;">${escapeHtml(s.title)}</strong>
          <span style="font-size: 11.5px; color: var(--ink-dim, #4d5f80); line-height: 1.4;">${escapeHtml(s.desc)}</span>
        </div>
      </div>
    `).join("");

    // Conflict detection
    if (corr && corr.correlation && corr.correlation.penalties_applied && corr.correlation.penalties_applied.length) {
      if (el.conflictWarning) {
        el.conflictWarning.hidden = false;
        if (el.conflictText) {
          el.conflictText.textContent = `Conflicting / uncorroborated evidence detected: ${corr.correlation.penalties_applied.join(", ")}.`;
        }
      }
    } else {
      if (el.conflictWarning) el.conflictWarning.hidden = true;
    }
  }

  // ------------------------------------------------------------------ //
  // Level 7: Operational Right Panel (Summary, Alert, Actions, Timeline)
  // ------------------------------------------------------------------ //

  function renderOperationalPanel(riskMeta, f, profile, landslide, rain, gas) {
    // Decision Summary Metrics
    if (el.summaryRiskScore) el.summaryRiskScore.textContent = profile ? `${riskMeta.score} / 100` : "-- / 100";
    if (el.summaryConfidence) el.summaryConfidence.textContent = f ? `${f.confidence_pct.toFixed(1)}%` : "--%";
    if (el.summaryEvidenceStrength) {
      const count = profile && profile.sensor_matrix ? profile.sensor_matrix.filter(s => s.role === "PRIMARY" || s.role === "SUPPORTING").length : 0;
      el.summaryEvidenceStrength.textContent = count > 0 ? `${count} Modalities` : "--";
    }
    if (el.summaryRiskLevel) el.summaryRiskLevel.textContent = profile ? riskMeta.level : "STANDBY";

    // Active Tactical Alert Card
    if (riskMeta.score >= 50 || (f && f.triage_class === "HIGH")) {
      if (el.alertCard) {
        el.alertCard.className = "ai-op-card ai-alert-card has-alert";
      }
      if (el.alertBadge) {
        el.alertBadge.textContent = `🚨 ${riskMeta.level} ALERT`;
        el.alertBadge.className = "ai-alert-badge badge-critical";
      }
      if (el.alertTitle) {
        el.alertTitle.textContent = `HIGH ${profile ? profile.name.toUpperCase() : 'HAZARD'} THREAT VECTOR ACTIVE`;
      }
      if (el.alertMetaGrid) el.alertMetaGrid.style.display = "grid";
      if (el.alertLocation) el.alertLocation.textContent = profile ? profile.site_label || "Active Site" : "Rohtang Pass";
      if (el.alertConfidence) el.alertConfidence.textContent = f ? `${f.confidence_pct.toFixed(1)}%` : `${riskMeta.score}%`;
      if (el.alertTriggers) el.alertTriggers.textContent = riskMeta.factors.length ? riskMeta.factors[0] : "Multi-sensor threshold breach";
      if (el.alertTime) el.alertTime.textContent = new Date().toLocaleTimeString([], { hour12: false });
    } else {
      if (el.alertCard) {
        el.alertCard.className = "ai-op-card ai-alert-card no-alert";
      }
      if (el.alertBadge) {
        el.alertBadge.textContent = "✓ NO ACTIVE ALERTS";
        el.alertBadge.className = "ai-alert-badge badge-nominal";
      }
      if (el.alertTitle) {
        el.alertTitle.textContent = "All environmental and survivor vital signs within nominal threshold envelopes.";
      }
      if (el.alertMetaGrid) el.alertMetaGrid.style.display = "none";
    }

    // Recommended Actions
    const actions = [];
    if (riskMeta.score >= 70 || (f && f.triage_class === "HIGH")) {
      actions.push("Notify Commander and restrict ground access to affected sector.");
      actions.push("Dispatch primary SAR team to target coordinates with life safety equipment.");
      actions.push("Continuously monitor sensor trend telemetry for escalation.");
    } else if (riskMeta.score >= 40) {
      actions.push("Alert field reconnaissance units to monitor slope stability and weather conditions.");
      actions.push("Pre-stage standby medical evacuation equipment.");
    } else {
      actions.push("Maintain continuous automated telemetry surveillance and multi-sensor baseline monitoring.");
    }

    if (el.actionList) {
      el.actionList.innerHTML = actions.map(a => `
        <div class="ai-action-item">
          <span>→</span> <span>${escapeHtml(a)}</span>
        </div>
      `).join("");
    }

    // Timeline Logging
    logTimelineEvents(riskMeta, f);
  }

  function logTimelineEvents(riskMeta, f) {
    if (!el.timelineList) return;

    const timeStr = new Date().toLocaleTimeString([], { hour12: false });
    const events = [];

    if (riskMeta.score >= 50) {
      events.push({ time: timeStr, desc: `Risk score elevated to ${riskMeta.level} (${riskMeta.score}/100)` });
    }
    if (f && f.triage_class === "HIGH") {
      events.push({ time: timeStr, desc: `Survivor ${state.selectedVictimId || 'V1'} classified as HIGH priority (${f.confidence_pct.toFixed(1)}%)` });
    }

    events.push({ time: timeStr, desc: "Sensor fusion telemetry synchronized across modalities." });

    el.timelineList.innerHTML = events.map(e => `
      <div class="ai-timeline-item">
        <span class="ai-timeline-time">${e.time}</span>
        <span class="ai-timeline-desc">${escapeHtml(e.desc)}</span>
      </div>
    `).join("");
  }

  // ------------------------------------------------------------------ //
  // Preserved Deep Technical Formulas (Steps 0 through 9)
  // ------------------------------------------------------------------ //

  function renderEmptyTechnicalWalkthrough() {
    const msg = "Select an active victim node to inspect live formula breakdown.";
    if (el.confidenceSteps) el.confidenceSteps.innerHTML = `<p class="empty-note">${msg}</p>`;
    if (el.triageBar) el.triageBar.innerHTML = `<p class="empty-note">${msg}</p>`;
    if (el.hazardBars) el.hazardBars.innerHTML = `<p class="empty-note">${msg}</p>`;
    if (el.finalSps) el.finalSps.innerHTML = `<p class="empty-note">${msg}</p>`;
  }

  function renderProfileMatrix(profile) {
    if (!el.profileMatrix) return;
    if (!profile || !profile.sensor_matrix) {
      el.profileMatrix.innerHTML = '<p class="empty-note">Awaiting scenario sensor profile…</p>';
      return;
    }
    if (el.profileSub && profile.name) {
      el.profileSub.textContent = `${profile.name} · Scenario-Specific Active Modalities & Gating Rules`;
    }
    if (el.selectedScenarioText && profile.name) {
      el.selectedScenarioText.textContent = profile.name.toUpperCase();
    }

    const rowsHtml = profile.sensor_matrix.map(row => {
      const role = row.role || "INACTIVE";
      const isPrimary = role === "PRIMARY";
      const isSupporting = role === "SUPPORTING";
      const isInactive = role === "INACTIVE";

      let roleBg = isPrimary ? "rgba(37,99,235,0.12)" : (isSupporting ? "rgba(22,163,74,0.12)" : "rgba(137,152,184,0.1)");
      let roleColor = isPrimary ? "#2563eb" : (isSupporting ? "#16a34a" : "#4d5f80");
      let roleBorder = isPrimary ? "rgba(37,99,235,0.3)" : (isSupporting ? "rgba(22,163,74,0.3)" : "rgba(137,152,184,0.2)");
      let explainText = "";

      if (isPrimary) {
        explainText = `Primary driving evidence for ${profile.name}. Directly informs vital sign detection or core hazard assessment with ${(row.weight * 100).toFixed(0)}% weight.`;
      } else if (isSupporting) {
        explainText = `Supporting corroboration channel. Provides cross-modal verification without triggering standalone false alarms.`;
      } else {
        explainText = `Modality inactive for ${profile.name}. Held at nominal ambient baseline; hazard bonus contribution is gated to strictly 0.0 to prevent cross-scenario false positives.`;
      }

      return `
        <tr style="border-bottom: 1px solid var(--border, #d3e1f5); font-size: 0.85rem;">
          <td style="padding: 8px 10px; font-weight: 600; color: var(--ink, #0f2547); font-family: monospace;">${escapeHtml(row.sensor_type)}</td>
          <td style="padding: 8px 10px;">
            <span style="display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: ${roleBg}; color: ${roleColor}; border: 1px solid ${roleBorder};">
              ${escapeHtml(role)}
            </span>
          </td>
          <td style="padding: 8px 10px; font-weight: 600; color: ${isInactive ? 'var(--ink-dim, #4d5f80)' : 'var(--accent-ice, #2563eb)'}; font-family: 'JetBrains Mono', monospace;">
            ${row.current_value != null ? escapeHtml(row.current_value + " " + (row.unit || '')) : "0.0"}
          </td>
          <td style="padding: 8px 10px; font-size: 0.8rem; color: ${isInactive ? 'var(--ink-dim, #4d5f80)' : 'var(--ink, #0f2547)'};">
            ${escapeHtml(explainText)}
          </td>
        </tr>
      `;
    }).join("");

    el.profileMatrix.innerHTML = `
      <table style="width: 100%; border-collapse: collapse; text-align: left;">
        <thead>
          <tr style="border-bottom: 1px solid var(--border, #d3e1f5); color: var(--ink-dim, #4d5f80); font-size: 0.75rem; text-transform: uppercase;">
            <th style="padding: 6px 10px;">Sensor Channel</th>
            <th style="padding: 6px 10px;">Scenario Role</th>
            <th style="padding: 6px 10px;">Live Value</th>
            <th style="padding: 6px 10px;">Gating &amp; Fusion Behavior</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
    `;
  }

  function renderConfidenceSteps(f) {
    if (!el.confidenceSteps) return;
    const w = state.config ? state.config.confidence_weights : { radar: 0.35, thermal: 0.25, acoustic: 0.20, co2: 0.10, camera: 0.10 };
    const sb = f.score_breakdown || {};

    if (!f.contributing_sensors || !f.contributing_sensors.length) {
      el.confidenceSteps.innerHTML = `<p class="empty-note">No sensor data this cycle — Confidence % = 0.0%.</p>`;
      return;
    }

    const rows = [
      ["Radar",    w.radar,    sb.heart_rate_radar],
      ["Thermal",  w.thermal,  sb.thermal_imaging],
      ["Acoustic", w.acoustic, sb.acoustic],
      ["CO2",      w.co2,      sb.co2],
      ["Camera",   w.camera,   sb.rgb_camera],
    ];

    el.confidenceSteps.innerHTML = rows.map(([label, weight, score]) => {
      const s = score ?? 0;
      return `<div class="logic-line"><span class="logic-line-label">${label}:</span> ${weight.toFixed(2)} × ${s.toFixed(2)} = <b>${(weight * s).toFixed(3)}</b></div>`;
    }).join("") + `
      <div class="logic-line logic-total">× Reliability (${(f.reliability ?? 0).toFixed(2)}) → Confidence % = <b>${f.confidence_pct.toFixed(1)}%</b></div>
    `;
  }

  function renderTriageBar(f) {
    if (!el.triageBar) return;
    const t = state.config ? state.config.triage_thresholds_pct : { low: 25, medium: 50, high: 75, tap_high_min: 65 };
    const pct = Math.max(0, Math.min(f.confidence_pct, 100));
    const color = TRIAGE_COLORS[f.triage_class] || TRIAGE_COLORS.NO_VITAL_SIGNS;
    el.triageBar.innerHTML = `
      <div class="logic-bar-track">
        <div class="logic-bar-marker" style="left:${pct}%" title="Confidence ${f.confidence_pct.toFixed(1)}%"></div>
        <span class="logic-bar-tick" style="left:${t.low}%">LOW ${t.low}</span>
        <span class="logic-bar-tick" style="left:${t.medium}%">MED ${t.medium}</span>
        <span class="logic-bar-tick" style="left:${t.high}%">HIGH ${t.high}</span>
      </div>
      <div class="logic-line">Result: <b style="color:${color}">${TRIAGE_EMOJI[f.triage_class] || ""} ${escapeHtml(f.triage_class)}</b>${f.tapping_detected ? " · 👊 tapping detected (lowers HIGH bar to " + t.tap_high_min + ")" : ""}</div>
      <div class="logic-line dim">${escapeHtml(f.notes || "")}</div>
    `;
  }

  function renderHazardBars(f) {
    if (!el.hazardBars) return;
    const hb = f.hazard_breakdown || {};
    const active = Object.entries(hb).filter(([k, val]) => k !== "base" && val > 0.0001);

    const rowsHtml = active
      .sort((a, b) => b[1] - a[1])
      .map(([k, val]) => {
        const label = HAZARD_TERM_LABELS[k] || k;
        const widthPx = Math.max(2, Math.round(val * 200));
        return `<div class="logic-hazard-row"><span class="logic-hazard-label">${escapeHtml(label)}</span><div class="logic-hazard-fill" style="width:${widthPx}px"></div><span class="logic-hazard-value">+${val.toFixed(3)}</span></div>`;
      }).join("");

    const cap = state.config ? state.config.hazard_multiplier_cap : 2.5;
    const total = hb.base != null ? Object.values(hb).reduce((a, b) => a + b, 0) : null;

    el.hazardBars.innerHTML = `
      <div class="logic-line">Base: <b>1.000</b></div>
      ${rowsHtml || "<p class='empty-note'>No hazard bonuses active this cycle.</p>"}
      <div class="logic-line logic-total">Sum (capped at ${cap.toFixed(1)}×) → Hazard Multiplier = <b>${f.hazard_multiplier.toFixed(3)}×</b>${total != null && total > cap ? ` <span class="dim">(raw sum ${total.toFixed(3)}, capped)</span>` : ""}</div>
    `;
  }

  function renderFinalSps(f) {
    if (!el.finalSps) return;
    el.finalSps.innerHTML = `
      <div class="logic-line logic-total">SPS = Confidence % × Hazard Multiplier</div>
      <div class="logic-line logic-total">SPS = ${f.confidence_pct.toFixed(1)}% × ${f.hazard_multiplier.toFixed(3)} = <b>${f.sps.toFixed(2)}</b></div>
    `;
  }

  function renderLandslideLogic(data) {
    if (!el.landslideFormula) return;
    const bd = data.score_breakdown || {};
    const riskLevel = data.risk_level || "LOW";
    const riskColor = riskLevel === "CRITICAL" ? "#ef4444" : (riskLevel === "HIGH" ? "#f97316" : (riskLevel === "MODERATE" ? "#eab308" : "#22c55e"));

    el.landslideFormula.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 14px;">
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">1. Soil Moisture Subscore (0–25 pts)</div>
          <div style="font-size: 16px; font-weight: 700; color: #2563eb;">+${(bd.moisture_subscore || 0).toFixed(1)} pts</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">2. Moisture Trend Bonus (0–15 pts)</div>
          <div style="font-size: 16px; font-weight: 700; color: #2563eb;">+${(bd.moisture_trend_bonus || 0).toFixed(1)} pts</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">3. Inclinometer Tilt Subscore (0–25 pts)</div>
          <div style="font-size: 16px; font-weight: 700; color: #f59e0b;">+${(bd.tilt_subscore || 0).toFixed(1)} pts</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">4. Tilt Trend Bonus (0–25 pts)</div>
          <div style="font-size: 16px; font-weight: 700; color: #f59e0b;">+${(bd.tilt_trend_bonus || 0).toFixed(1)} pts</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">5. Compound / Persistence (0–10 pts)</div>
          <div style="font-size: 16px; font-weight: 700; color: #8b5cf6;">+${(bd.persistence_score || 0).toFixed(1)} pts</div>
        </div>
      </div>
      <div class="logic-line logic-total" style="font-size: 15px; border-left: 4px solid ${riskColor}; padding-left: 10px;">
        Final Landslide Risk Score = <b>${(data.risk_score || 0).toFixed(1)} / 100</b> &rarr; <span style="color: ${riskColor}; font-weight: 800;">${escapeHtml(riskLevel)}</span> (${escapeHtml(data.event_state || 'NORMAL')})
      </div>
      <div class="logic-line dim" style="margin-top: 8px;">
        Contributing Factors: <b>${(data.contributing_factors || []).join('; ') || 'Nominal stable equilibrium'}</b>
      </div>
      <div class="logic-line dim">
        Recommended Action: <b>${escapeHtml(data.recommended_action || 'Routine monitoring')}</b>
      </div>
    `;
  }

  function renderCameraThermalLogic(data) {
    if (!el.cameraThermalFormula) return;
    if (!data || !data.correlation) {
      el.cameraThermalFormula.innerHTML = '<p class="empty-note">Awaiting optical &amp; thermal cross-modal telemetry…</p>';
      return;
    }
    const c = data.correlation;
    const caseColor = c.correlation_case === "CASE_4_QUAD_SENSOR_CORROBORATED" ? "#16a34a" :
                      c.correlation_case === "CASE_1_STRONG_SURVIVOR" ? "#2563eb" :
                      c.correlation_case === "CASE_2_POSSIBLE_FALSE_POSITIVE" ? "#ea580c" :
                      c.correlation_case === "CASE_3_HIDDEN_OBSCURED_SURVIVOR" ? "#8b5cf6" : "#64748b";

    el.cameraThermalFormula.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 14px;">
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Optical Camera State</div>
          <div style="font-size: 14px; font-weight: 700; color: #2563eb;">${escapeHtml(c.camera_state)}</div>
          <div style="font-size: 11px; color: var(--ink-dim);">Conf: ${Math.round((c.camera_confidence || 0) * 100)}% · Occ: ${Math.round((c.camera_occlusion || 0) * 100)}%</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Thermal Infrared State</div>
          <div style="font-size: 14px; font-weight: 700; color: #e11d48;">${escapeHtml(c.thermal_detection)}</div>
          <div style="font-size: 11px; color: var(--ink-dim);">Temp: ${c.thermal_temperature ? c.thermal_temperature.toFixed(1) : '20'}°C (Δ${c.thermal_delta ? c.thermal_delta.toFixed(1) : '0'}°C)</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Cross-Modal Synergy / Penalties</div>
          <div style="font-size: 14px; font-weight: 700; color: ${c.synergy_bonus > 0 ? '#16a34a' : (c.penalties_applied && c.penalties_applied.length ? '#ea580c' : '#64748b')};">
            ${c.synergy_bonus > 0 ? `+${Math.round(c.synergy_bonus * 100)}% Synergy Bonus` : (c.penalties_applied && c.penalties_applied.length ? 'Discount / Penalties Applied' : 'Baseline Fusion')}
          </div>
          <div style="font-size: 11px; color: var(--ink-dim);">Single-Sensor Clamped: ${c.single_modality_clamped ? 'YES (≤35%)' : 'NO'}</div>
        </div>
      </div>
      <div class="logic-line logic-total" style="font-size: 15px; border-left: 4px solid ${caseColor}; padding-left: 10px;">
        Cross-Modal Correlation Classification: <b style="color: ${caseColor};">${escapeHtml(c.correlation_case)}</b> &rarr; <span style="font-weight: 800; color: #2563eb;">${Math.round((c.combined_confidence || 0) * 100)}% Combined Modality Score</span>
      </div>
      <div class="logic-line dim" style="margin-top: 8px;">
        Explainable AI Narrative: <b>${escapeHtml(c.explainable_summary)}</b>
      </div>
    `;
  }

  function renderRainfallLogic(rainData, f) {
    if (!el.rainfallFormula) return;
    const r = (rainData && rainData.rainfall) ? rainData.rainfall : null;
    if (!r) {
      el.rainfallFormula.innerHTML = '<p class="empty-note">Awaiting rainfall &amp; meteorological telemetry…</p>';
      return;
    }

    const rate = r.rainfall_rate_mm_h != null ? r.rainfall_rate_mm_h : 0.0;
    const cumul = r.cumulative_rainfall_mm != null ? r.cumulative_rainfall_mm : 0.0;
    const cls = r.classification || "NO_RAIN";
    const sev = r.severity || "LOW";

    const clsColor = cls === "EXTREME" ? "#ef4444" :
                     cls === "VERY_HEAVY" ? "#f43f5e" :
                     cls === "HEAVY" ? "#f97316" :
                     cls === "MODERATE" ? "#eab308" :
                     cls === "LIGHT" ? "#2563eb" : "#64748b";

    const rainMultiplierContribution = Math.min(0.40, (rate / 100.0) * 0.40);

    el.rainfallFormula.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 14px;">
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Precipitation Intensity Rate</div>
          <div style="font-size: 18px; font-weight: 800; color: ${clsColor};">${rate.toFixed(1)} mm/h</div>
          <div style="font-size: 11px; color: var(--ink-dim); margin-top: 2px;">Class: <b>${escapeHtml(cls)}</b> (${escapeHtml(sev)})</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Cumulative Precipitation Exposure</div>
          <div style="font-size: 18px; font-weight: 800; color: #2563eb;">${cumul.toFixed(1)} mm</div>
          <div style="font-size: 11px; color: var(--ink-dim); margin-top: 2px;">Critical Threshold: 100.0 mm</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Hazard Multiplier Share</div>
          <div style="font-size: 18px; font-weight: 800; color: #ea580c;">+${(rainMultiplierContribution).toFixed(2)}x</div>
          <div style="font-size: 11px; color: var(--ink-dim); margin-top: 2px;">Scaling: min(0.40, rate/100 * 0.40)</div>
        </div>
      </div>
      <div class="logic-line logic-total" style="font-size: 14px; border-left: 4px solid ${clsColor}; padding-left: 10px;">
        Meteorological Hazard State: <b style="color: ${clsColor};">${escapeHtml(cls)}</b> &rarr; <span style="font-weight: 700; color: var(--ink, #0f2547);">Environmental Threat Factor Active in Triage Multiplier</span>
      </div>
    `;
  }

  function renderBaroLogic(baroData, f) {
    if (!el.baroFormula) return;
    const p = (baroData && baroData.pressure) ? baroData.pressure : null;
    if (!p) {
      el.baroFormula.innerHTML = '<p class="empty-note">Awaiting barometric telemetry…</p>';
      return;
    }

    const pressureHpa = p.pressure_hpa != null ? p.pressure_hpa : 1013.25;
    const trend = p.trend || "STABLE";
    const dropSev = p.drop_severity || "NORMAL";
    const roc = p.rate_of_change != null ? p.rate_of_change : 0.0;
    const pColor = dropSev === "CRITICAL" ? "#ef4444" : (dropSev === "WARNING" ? "#f97316" : "#2563eb");

    const pressureDropContribution = (roc <= -3.0 || pressureHpa < 990.0) ? 0.20 : (roc <= -1.5 ? 0.10 : 0.0);

    el.baroFormula.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 14px;">
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Current Barometric Pressure</div>
          <div style="font-size: 18px; font-weight: 800; color: ${pColor};">${pressureHpa.toFixed(1)} hPa</div>
          <div style="font-size: 11px; color: var(--ink-dim); margin-top: 2px;">Baseline: ${(p.baseline_hpa || 1013.25).toFixed(1)} hPa</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Rate of Pressure Change</div>
          <div style="font-size: 18px; font-weight: 800; color: ${roc < 0 ? '#ef4444' : '#2563eb'};">${roc > 0 ? '+' : ''}${roc.toFixed(2)} hPa/cyc</div>
          <div style="font-size: 11px; color: var(--ink-dim); margin-top: 2px;">Trend: <b>${escapeHtml(trend)}</b> (${escapeHtml(dropSev)})</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Hazard Multiplier Share</div>
          <div style="font-size: 18px; font-weight: 800; color: #ea580c;">+${pressureDropContribution.toFixed(2)}x</div>
          <div style="font-size: 11px; color: var(--ink-dim); margin-top: 2px;">Threshold: &Delta; &le; -1.5 hPa/cyc (+0.10x), &le; -3.0 hPa/cyc (+0.20x)</div>
        </div>
      </div>
      <div class="logic-line logic-total" style="font-size: 14px; border-left: 4px solid ${pColor}; padding-left: 10px;">
        Atmospheric Trend Assessment: <b style="color: ${pColor};">${escapeHtml(trend)}</b> &rarr; <span style="font-weight: 700; color: var(--ink, #0f2547);">${dropSev === 'CRITICAL' ? 'Severe Weather / Storm Surge Threat Vector Active' : 'Normal Atmospheric Equilibrium'}</span>
      </div>
    `;
  }

  function renderGasSmokeLogic(gasSmokeData, f) {
    if (!el.gasSmokeFormula) return;
    const gs = (gasSmokeData && gasSmokeData.gas_smoke) ? gasSmokeData.gas_smoke : null;
    if (!gs) {
      el.gasSmokeFormula.innerHTML = '<p class="empty-note">Awaiting gas and smoke telemetry…</p>';
      return;
    }

    const gasPpm = gs.gas_concentration_ppm != null ? gs.gas_concentration_ppm : 0.0;
    const smokePct = gs.smoke_density_pct != null ? gs.smoke_density_pct : 0.0;
    const gasLevel = gs.gas_level || "NORMAL";
    const smokeLevel = gs.smoke_level || "LOW";

    const gasColor = gasLevel === "CRITICAL" ? "#ef4444" : (gasLevel === "ELEVATED" ? "#f97316" : "#16a34a");
    const smokeColor = smokeLevel === "HIGH" ? "#ef4444" : (smokeLevel === "MEDIUM" ? "#f97316" : "#16a34a");

    el.gasSmokeFormula.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 14px;">
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Toxic Gas Concentration</div>
          <div style="font-size: 18px; font-weight: 800; color: ${gasColor};">${gasPpm.toFixed(1)} PPM</div>
          <div style="font-size: 11px; color: var(--ink-dim); margin-top: 2px;">Threshold: &ge;50 PPM (Elevated), &ge;150 PPM (Critical)</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Particulate Smoke Density</div>
          <div style="font-size: 18px; font-weight: 800; color: ${smokeColor};">${smokePct.toFixed(1)}%</div>
          <div style="font-size: 11px; color: var(--ink-dim); margin-top: 2px;">Threshold: &ge;20% (Medium), &ge;40% (High)</div>
        </div>
        <div style="background: var(--bg-panel-raised, #f8fafc); border: 1px solid var(--border, #d3e1f5); padding: 10px; border-radius: 8px;">
          <div style="font-size: 11px; color: var(--ink-dim);">Life Safety Protection Protocol</div>
          <div style="font-size: 18px; font-weight: 800; color: ${gasPpm >= 100.0 || smokePct >= 40.0 ? '#ef4444' : '#16a34a'};">${gasPpm >= 100.0 || smokePct >= 40.0 ? 'SCBA MANDATORY' : 'STANDARD PPE'}</div>
          <div style="font-size: 11px; color: var(--ink-dim); margin-top: 2px;">Status: <b>${escapeHtml(gasLevel)} / ${escapeHtml(smokeLevel)}</b></div>
        </div>
      </div>
      <div class="logic-line logic-total" style="font-size: 14px; border-left: 4px solid ${gasColor}; padding-left: 10px;">
        Atmospheric Safety Doctrine: <b style="color: ${gasColor};">${gasPpm >= 100.0 || smokePct >= 40.0 ? 'IMMEDIATELY DANGEROUS TO LIFE OR HEALTH (IDLH)' : 'NOMINAL SAFE BREATHING AIR'}</b>
      </div>
    `;
  }

  // ------------------------------------------------------------------ //
  // Victim Tabs
  // ------------------------------------------------------------------ //

  function renderVictimTabs() {
    if (!el.victimTabs) return;
    if (!state.victims.length) {
      el.victimTabs.innerHTML = '<p class="empty-note">No victim nodes online yet.</p>';
      return;
    }
    el.victimTabs.innerHTML = "";
    for (const v of state.victims) {
      const q = state.queue.find(item => item.victim_id === v.victim_id);
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = "hw-victim-tab" + (v.victim_id === state.selectedVictimId ? " is-selected" : "");
      const emoji = q ? (TRIAGE_EMOJI[q.triage_class] || "") : "";
      tab.innerHTML = `<span class="hw-victim-tab-id">${escapeHtml(v.victim_id)}</span>${emoji ? `<span class="hw-victim-tab-badge">${emoji}</span>` : ""}${v.sensor_node_online ? "" : `<span class="hw-victim-tab-offline">OFFLINE</span>`}`;
      tab.onclick = () => {
        state.selectedVictimId = v.victim_id;
        renderVictimTabs();
        poll();
      };
      el.victimTabs.appendChild(tab);
    }
  }

  // ------------------------------------------------------------------ //
  // Compact Scenario Dropdown Component Engine for Logic Page
  // ------------------------------------------------------------------ //

  const LOGIC_BUILTIN_SCENARIOS = [
    { id: "himalaya_avalanche", name: "Himalaya Avalanche", icon: "❄️", meta: "High altitude avalanche · Rohtang Pass" },
    { id: "flood", name: "Urban Flash Flood", icon: "🌊", meta: "Rising floodwaters & submerged structures" },
    { id: "landslide", name: "Monsoon Landslide", icon: "⛰️", meta: "Slope failure & soil liquefaction" },
    { id: "earthquake", name: "Structural Collapse", icon: "🌋", meta: "Pancake collapse & rubble void search" },
    { id: "chemical_leak", name: "Industrial Chemical Leak", icon: "☣️", meta: "Toxic gas dispersion & plume containment" },
    { id: "cyclone", name: "Coastal Cyclone & Storm Surge", icon: "🌀", meta: "Barometric depression & high wind surge" },
    { id: "wildfire", name: "Wildfire Perimeter", icon: "🔥", meta: "Thermal front & active smoke plume" },
  ];

  async function initLogicScenarioDropdown() {
    if (!el.scenarioDropdownBtn || !el.scenarioPopover) return;

    let scenarios = [...LOGIC_BUILTIN_SCENARIOS];
    try {
      const res = await apiGet("/scenarios").catch(() => null);
      if (res && Array.isArray(res.scenarios)) {
        res.scenarios.forEach(sc => {
          const sId = sc.id || sc.scenario_id;
          if (!scenarios.some(s => s.id === sId)) {
            scenarios.push({
              id: sId,
              name: sc.name || sId,
              icon: "🗺️",
              meta: sc.hazard_type ? `${sc.hazard_type.toUpperCase()} · ${sc.victim_count || 0} victims` : "Disaster Scenario"
            });
          }
        });
      }
    } catch (e) {
      // Fallback
    }

    function renderOptions(filterQuery = "") {
      if (!el.scenarioOptionList) return;
      el.scenarioOptionList.innerHTML = "";
      const q = filterQuery.trim().toLowerCase();
      const filtered = scenarios.filter(s => !q || s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q) || s.meta.toLowerCase().includes(q));

      if (!filtered.length) {
        el.scenarioOptionList.innerHTML = '<div style="padding: 12px; font-size: 11px; color: var(--ink-dim, #4d5f80); text-align: center;">No matching scenarios</div>';
        return;
      }

      filtered.forEach(sc => {
        const item = document.createElement("div");
        const isSel = el.selectedScenarioText && el.selectedScenarioText.textContent.toUpperCase() === sc.name.toUpperCase();
        item.className = `scenario-option-item ${isSel ? "is-selected" : ""}`;
        item.setAttribute("data-scenario", sc.id);
        item.setAttribute("role", "option");
        item.tabIndex = 0;
        item.innerHTML = `
          <span style="display: flex; align-items: center; gap: 6px;">
            <span>${sc.icon || "🗺️"}</span>
            <span>${sc.name}</span>
          </span>
          <span class="scenario-opt-meta">${sc.meta || ""}</span>
        `;

        const selectThis = async () => {
          if (el.selectedScenarioText) el.selectedScenarioText.textContent = sc.name.toUpperCase();
          closeDropdown();
          try {
            if (el.statusMessage) el.statusMessage.textContent = `Starting scenario [${sc.name}]…`;
            await apiPost("/scenario/start", { scenario: sc.id });
            await poll();
          } catch (err) {
            console.error("Scenario switch error:", err);
          }
        };

        item.onclick = selectThis;
        item.onkeydown = (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            selectThis();
          }
        };

        el.scenarioOptionList.appendChild(item);
      });
    }

    function openDropdown() {
      el.scenarioPopover.hidden = false;
      el.scenarioDropdownBtn.setAttribute("aria-expanded", "true");
      el.scenarioDropdownBtn.classList.add("is-active");
      if (el.scenarioSearchInput) {
        el.scenarioSearchInput.value = "";
        renderOptions("");
        setTimeout(() => el.scenarioSearchInput.focus(), 50);
      }
    }

    function closeDropdown() {
      el.scenarioPopover.hidden = true;
      el.scenarioDropdownBtn.setAttribute("aria-expanded", "false");
      el.scenarioDropdownBtn.classList.remove("is-active");
    }

    el.scenarioDropdownBtn.onclick = (e) => {
      e.stopPropagation();
      if (el.scenarioPopover.hidden) openDropdown();
      else closeDropdown();
    };

    if (el.scenarioSearchInput) {
      el.scenarioSearchInput.addEventListener("input", (e) => {
        renderOptions(e.target.value);
      });
      el.scenarioSearchInput.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          closeDropdown();
          el.scenarioDropdownBtn.focus();
        } else if (e.key === "ArrowDown") {
          const firstOpt = el.scenarioOptionList.querySelector(".scenario-option-item");
          if (firstOpt) firstOpt.focus();
        }
      });
    }

    document.addEventListener("click", (e) => {
      if (el.scenarioSelectorWrap && !el.scenarioSelectorWrap.contains(e.target)) {
        closeDropdown();
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !el.scenarioPopover.hidden) {
        closeDropdown();
        el.scenarioDropdownBtn.focus();
      }
    });

    renderOptions();
  }

  // ------------------------------------------------------------------ //
  // UI Interaction Bindings (Technical Accordion & Jumps)
  // ------------------------------------------------------------------ //

  function initUI() {
    initLogicScenarioDropdown();

    // Expandable Technical Details Drawer
    if (el.btnToggleTechDetails && el.techDetailsContainer) {
      el.btnToggleTechDetails.onclick = () => {
        const isHidden = el.techDetailsContainer.hidden;
        el.techDetailsContainer.hidden = !isHidden;
        el.btnToggleTechDetails.classList.toggle("is-open", isHidden);
        el.btnToggleTechDetails.setAttribute("aria-expanded", isHidden ? "true" : "false");
      };
    }

    // Jump from Evidence Section to Step 0 Role Matrix
    if (el.btnJumpToRoleMatrix && el.techDetailsContainer) {
      el.btnJumpToRoleMatrix.onclick = () => {
        el.techDetailsContainer.hidden = false;
        if (el.btnToggleTechDetails) {
          el.btnToggleTechDetails.classList.add("is-open");
          el.btnToggleTechDetails.setAttribute("aria-expanded", "true");
        }
        if (el.profileMatrix) {
          el.profileMatrix.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      };
    }
  }

  // ------------------------------------------------------------------ //
  // Idle / Standby State Handler
  // ------------------------------------------------------------------ //

  function renderIdleState(e) {
    const notRunning = e instanceof ApiError && e.status === 409;
    const msg = notRunning
      ? "AI Decision Center standing by — select an active scenario above to start live intelligence."
      : `Could not reach ${state.apiBase}. Confirm the backend is running.`;

    if (el.statusSub) el.statusSub.textContent = "— STANDBY —";
    if (el.statusMessage) el.statusMessage.textContent = msg;

    const idleRisk = { score: 0, level: "STANDBY", factors: [], trend: "Waiting for live scenario telemetry…" };
    renderHeroSection(null, null, idleRisk);
    renderCalculationWorkbench(null, null, null, idleRisk);
    renderEarthquakeSection(null, null, null, null);
    renderWhyBanner(null, null, idleRisk, null, null, null, null, null);
    renderEvidenceSection(null, null, null, null, null);
    renderFusionDiagram(null, 0, 0);
    renderDecisionPipeline(null, null, idleRisk);
    renderExplainableChecklist(null, null, idleRisk, null, null, null, null, null);
    renderOperationalPanel(idleRisk, null, null, null, null, null);
    renderEmptyTechnicalWalkthrough();
  }

  // ------------------------------------------------------------------ //
  // Initialization Entry Point
  // ------------------------------------------------------------------ //

  document.addEventListener("DOMContentLoaded", () => {
    initUI();
    poll();
  });

})();
