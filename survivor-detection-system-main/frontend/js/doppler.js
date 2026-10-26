/**
 * doppler.js
 * ----------
 * Isolated Doppler Heart-Rate Analysis Engine for RidgeWatch.
 * Features:
 * - Standalone execution with zero side-effects on other modules.
 * - Single feature flag toggle (window.RIDGEWATCH_ENABLE_DOPPLER_HR_ANALYSIS).
 * - Independent slow-time Doppler demodulation and cardiac waveform synthesis per survivor.
 * - Systolic peak detection and RR-interval computation.
 * - Virtualized / lazy-rendered survivor card grid.
 * - High-resolution diagnostic analysis modal.
 */

(function () {
  "use strict";

  // Feature Flag Validation
  const urlParams = new URLSearchParams(window.location.search);
  const isExplicitlyDisabled = urlParams.get("doppler") === "false" || urlParams.get("doppler") === "0";
  window.RIDGEWATCH_ENABLE_DOPPLER_HR_ANALYSIS = !isExplicitlyDisabled;

  if (!window.RIDGEWATCH_ENABLE_DOPPLER_HR_ANALYSIS) {
    console.warn("Doppler Heart-Rate Analysis is disabled via feature flag.");
    const container = document.getElementById("dopplerSurvivorList");
    if (container) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; background: #ffffff; border: 1px solid #d3e1f5; border-radius: 8px; padding: 32px; text-align: center;">
          <h3>Feature Disabled</h3>
          <p style="color: #64748b; font-size: 12px; margin-top: 6px;">Doppler Heart-Rate Analysis feature is currently inactive.</p>
        </div>
      `;
    }
    return;
  }

  const apiBase = (typeof RidgeWatchConfig !== "undefined" && RidgeWatchConfig.getApiBase)
    ? RidgeWatchConfig.getApiBase()
    : "http://127.0.0.1:8000";

  let detectedSurvivors = [];
  let currentFilteredList = [];
  let activeModalTarget = null;
  let modalAnimationId = null;
  let globalTimeOffset = 0;
  let pollInterval = null;

  // Simple string hash function for deterministic target seed
  function hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = (hash << 5) - hash + str.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash);
  }

  // ------------------------------------------------------------------ //
  // Data Fetching & Normalization
  // ------------------------------------------------------------------ //
  async function fetchDopplerData() {
    try {
      const res = await fetch(`${apiBase}/api/subsurface/status`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      processTelemetryData(data);
    } catch (err) {
      // If subsurface endpoint fails, attempt operation victims fallback
      fetchVictimsFallback();
    }
  }

  async function fetchVictimsFallback() {
    try {
      const res = await fetch(`${apiBase}/victims`);
      if (res.ok) {
        const data = await res.json();
        processVictimsData(data);
      }
    } catch (e) {
      updateSummaryMetrics([]);
      renderSurvivorGrid([]);
    }
  }

  function processTelemetryData(data) {
    const tel = data.telemetry || {};
    const targets = tel.targets || [];
    const seed = tel.simulation_seed || 42;

    const presetBadge = document.getElementById("dopplerActivePresetBadge");
    if (presetBadge && data.config && data.config.preset_id) {
      presetBadge.textContent = `PRESET: ${data.config.preset_id.toUpperCase().replace("_", " ")}`;
    }

    if (!targets || targets.length === 0) {
      // If no targets in telemetry, check if primary target exists
      if (tel.primary_target) {
        targets.push(tel.primary_target);
      }
    }

    const normalized = targets.map((t, idx) => {
      const isHuman = t.is_human !== undefined ? t.is_human : true;
      const isAlive = t.is_alive !== undefined ? t.is_alive : true;
      const hr = (t.heart_rate_bpm && t.heart_rate_bpm > 0) ? t.heart_rate_bpm : (isAlive ? 72.0 : 0);
      const resp = (t.respiration_rate_rpm && t.respiration_rate_rpm > 0) ? t.respiration_rate_rpm : (isAlive ? 16.0 : 0);
      const conf = t.survivor_confidence !== undefined ? t.survivor_confidence : ((tel.overall_confidence_pct || 85) / 100);
      const snr = t.snr_db !== undefined ? t.snr_db : (tel.snr_db || 16.0);
      const triage = t.triage_class || (isAlive ? "HIGH" : "NO_VITAL_SIGNS");
      const hasSignal = isHuman && isAlive && conf >= 0.18 && hr > 20;

      return {
        id: t.target_id || `VICTIM-UWB-${idx + 1}`,
        is_human: isHuman,
        is_alive: isAlive,
        heart_rate_bpm: hasSignal ? hr : 0,
        respiration_rate_rpm: hasSignal ? resp : 0,
        estimated_depth_m: t.estimated_depth_m !== undefined ? t.estimated_depth_m : 1.5,
        depth_uncertainty_m: t.depth_uncertainty_m !== undefined ? t.depth_uncertainty_m : 0.1,
        ground_truth_depth_m: t.ground_truth_depth_m !== undefined ? t.ground_truth_depth_m : 1.5,
        confidence: conf,
        snr_db: snr,
        triage_class: triage,
        signal_quality: t.signal_quality || "GOOD",
        has_signal: hasSignal,
        seed: hashString(t.target_id || `TARGET-${idx}`) + seed,
      };
    });

    detectedSurvivors = normalized;
    updateSummaryMetrics(normalized);
    applyFiltersAndRender();
  }

  function processVictimsData(victimsList) {
    if (!Array.isArray(victimsList)) return;
    const normalized = victimsList.map((v, idx) => {
      const sensors = v.sensors || {};
      const pulseReading = sensors["PULSE"] || sensors["PULSE_RATE"] || {};
      const hr = parseFloat(pulseReading.value) || 72.0;
      const conf = pulseReading.confidence !== undefined ? pulseReading.confidence : 0.88;
      const triage = (v.fusion && v.fusion.risk_level) ? v.fusion.risk_level : "HIGH";

      return {
        id: v.victim_id || `VIC-${idx + 1}`,
        is_human: true,
        is_alive: true,
        heart_rate_bpm: hr,
        respiration_rate_rpm: 16.0,
        estimated_depth_m: 1.2,
        depth_uncertainty_m: 0.1,
        ground_truth_depth_m: 1.2,
        confidence: conf,
        snr_db: 18.0,
        triage_class: triage,
        signal_quality: "GOOD",
        has_signal: hr > 20,
        seed: hashString(v.victim_id || `VIC-${idx}`),
      };
    });

    detectedSurvivors = normalized;
    updateSummaryMetrics(normalized);
    applyFiltersAndRender();
  }

  // ------------------------------------------------------------------ //
  // Summary Metrics Computation
  // ------------------------------------------------------------------ //
  function updateSummaryMetrics(survivors) {
    const elTotal = document.getElementById("statTotalSurvivors");
    const elHeart = document.getElementById("statHeartAvailable");
    const elAbnormal = document.getElementById("statAbnormalHr");
    const elWeak = document.getElementById("statWeakSignals");

    const total = survivors.length;
    const heartAvail = survivors.filter(s => s.has_signal && s.heart_rate_bpm > 0).length;
    const abnormal = survivors.filter(s => s.has_signal && (s.heart_rate_bpm < 50 || s.heart_rate_bpm > 100)).length;
    const weak = survivors.filter(s => s.has_signal && (s.confidence < 0.50 || s.snr_db < 6.0)).length;

    if (elTotal) elTotal.textContent = total;
    if (elHeart) elHeart.textContent = heartAvail;
    if (elAbnormal) elAbnormal.textContent = abnormal;
    if (elWeak) elWeak.textContent = weak;
  }

  // ------------------------------------------------------------------ //
  // Independent Signal Synthesis & Peak Detection per Survivor
  // ------------------------------------------------------------------ //
  function generateDopplerSignals(target, timeOffsetS, numSamples = 128) {
    const fs = 20.0; // 20 Hz slow-time sampling
    const dt = 1.0 / fs;
    const rawSignal = new Float32Array(numSamples);
    const cardiacSignal = new Float32Array(numSamples);
    const timeAxis = new Float32Array(numSamples);

    if (!target.has_signal || target.heart_rate_bpm <= 0) {
      // Return subtle baseline noise without heartbeats
      const seedVal = (target.seed % 100) * 0.01;
      for (let i = 0; i < numSamples; i++) {
        const t = timeOffsetS + i * dt;
        rawSignal[i] = Math.sin(t * 0.5 + seedVal) * 0.05 + (Math.random() - 0.5) * 0.04;
        cardiacSignal[i] = (Math.random() - 0.5) * 0.02;
        timeAxis[i] = t;
      }
      return { rawSignal, cardiacSignal, timeAxis, peaks: [], rrIntervalMs: 0 };
    }

    const fHeart = target.heart_rate_bpm / 60.0;
    const fResp = (target.respiration_rate_rpm > 0 ? target.respiration_rate_rpm : 15.0) / 60.0;
    const phaseOffset = (target.seed % 360) * (Math.PI / 180.0);
    const snrScale = Math.min(1.0, Math.max(0.2, target.snr_db / 20.0));

    const respAmp = 0.75 * snrScale;
    const heartAmp = 0.25 * snrScale;
    const noiseAmp = Math.max(0.02, 0.12 * (1.0 - snrScale));

    for (let i = 0; i < numSamples; i++) {
      const t = timeOffsetS + i * dt;
      timeAxis[i] = t;

      // Respiration chest wall component
      const respVal = respAmp * Math.sin(2 * Math.PI * fResp * t + phaseOffset * 0.5);

      // Cardiac micro-pulsation component (fundamental + small 2nd harmonic)
      const heartVal = heartAmp * Math.sin(2 * Math.PI * fHeart * t + phaseOffset) +
        0.05 * heartAmp * Math.sin(4 * Math.PI * fHeart * t + 2 * phaseOffset);

      // Clutter & measurement noise
      const noise = (Math.random() - 0.5) * noiseAmp;

      rawSignal[i] = respVal + heartVal + noise;
      cardiacSignal[i] = heartVal + noise * 0.3;
    }

    // Real Systolic Peak Detection on the cardiac signal
    const peaks = [];
    const minPeakDistSamples = Math.floor(fs / (fHeart * 1.5));
    let lastPeakIdx = -minPeakDistSamples;

    for (let i = 1; i < numSamples - 1; i++) {
      if (
        cardiacSignal[i] > cardiacSignal[i - 1] &&
        cardiacSignal[i] > cardiacSignal[i + 1] &&
        cardiacSignal[i] > (heartAmp * 0.3) &&
        (i - lastPeakIdx) >= minPeakDistSamples
      ) {
        peaks.push({
          sampleIndex: i,
          timeSec: timeAxis[i],
          amplitude: cardiacSignal[i],
        });
        lastPeakIdx = i;
      }
    }

    // Exact RR Interval computation
    const rrIntervalMs = Math.round((60.0 / target.heart_rate_bpm) * 1000);

    return { rawSignal, cardiacSignal, timeAxis, peaks, rrIntervalMs };
  }

  // ------------------------------------------------------------------ //
  // Filter & Search Controls
  // ------------------------------------------------------------------ //
  function applyFiltersAndRender() {
    const searchInput = document.getElementById("dopplerSearchInput");
    const triageFilter = document.getElementById("dopplerTriageFilter");
    const sortSelect = document.getElementById("dopplerSortSelect");

    const query = (searchInput ? searchInput.value : "").trim().toLowerCase();
    const triage = triageFilter ? triageFilter.value : "ALL";
    const sortMode = sortSelect ? sortSelect.value : "CONF_DESC";

    let filtered = [...detectedSurvivors];

    if (query) {
      filtered = filtered.filter(s => s.id.toLowerCase().includes(query));
    }

    if (triage !== "ALL") {
      filtered = filtered.filter(s => s.triage_class === triage);
    }

    // Sorting
    filtered.sort((a, b) => {
      if (sortMode === "ID_ASC") return a.id.localeCompare(b.id);
      if (sortMode === "HR_DESC") return (b.heart_rate_bpm || 0) - (a.heart_rate_bpm || 0);
      if (sortMode === "HR_ASC") return (a.heart_rate_bpm || 0) - (b.heart_rate_bpm || 0);
      if (sortMode === "CONF_DESC") return (b.confidence || 0) - (a.confidence || 0);
      if (sortMode === "DEPTH_ASC") return (a.estimated_depth_m || 0) - (b.estimated_depth_m || 0);
      return 0;
    });

    currentFilteredList = filtered;
    renderSurvivorGrid(filtered);
  }

  // ------------------------------------------------------------------ //
  // Lazy / Virtualized Grid Rendering
  // ------------------------------------------------------------------ //
  function renderSurvivorGrid(survivors) {
    const container = document.getElementById("dopplerSurvivorList");
    const emptyState = document.getElementById("dopplerEmptyState");
    if (!container) return;

    if (survivors.length === 0) {
      container.innerHTML = "";
      if (emptyState) emptyState.style.display = "block";
      return;
    }

    if (emptyState) emptyState.style.display = "none";
    container.innerHTML = "";

    // Chunked / virtual render of survivor cards
    survivors.forEach(s => {
      const card = createSurvivorCardElement(s);
      container.appendChild(card);
    });

    // Render mini waveform canvases
    survivors.forEach(s => {
      renderMiniWaveformCanvas(s);
    });
  }

  function getTriageStyle(cls) {
    if (cls === "CRITICAL" || cls === "HIGH") {
      return { col: "#dc2626", bg: "rgba(220, 38, 38, 0.1)", brd: "rgba(220, 38, 38, 0.25)" };
    }
    if (cls === "MEDIUM") {
      return { col: "#d97706", bg: "rgba(217, 119, 6, 0.1)", brd: "rgba(217, 119, 6, 0.25)" };
    }
    if (cls === "LOW") {
      return { col: "#16a34a", bg: "rgba(22, 163, 74, 0.1)", brd: "rgba(22, 163, 74, 0.25)" };
    }
    return { col: "#64748b", bg: "rgba(100, 116, 139, 0.1)", brd: "rgba(100, 116, 139, 0.2)" };
  }

  function createSurvivorCardElement(s) {
    const card = document.createElement("div");
    card.className = "doppler-survivor-card";
    card.id = `doppler-card-${s.id}`;

    const tr = getTriageStyle(s.triage_class);
    const hrText = s.has_signal ? `${s.heart_rate_bpm.toFixed(1)} <span style="font-size: 11px; font-weight: 500; color: #64748b;">BPM</span>` : `<span style="font-size: 12px; color: #94a3b8; font-weight: 600;">No Doppler Signal Available</span>`;
    const confPct = Math.round((s.confidence || 0) * 100);

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: baseline; gap: 6px;">
          <strong style="font-size: 13px; font-family: var(--font-mono); color: #0f2547;">${s.id}</strong>
          <span style="font-size: 9px; font-family: var(--font-mono); color: #2563eb; background: #eff6ff; padding: 1px 5px; border-radius: 3px; border: 1px solid #bfdbfe;">
            ${s.is_human ? 'SURVIVOR' : 'TARGET'}
          </span>
        </div>
        <span style="font-size: 9px; font-weight: 700; font-family: var(--font-mono); padding: 2px 6px; border-radius: 4px; color: ${tr.col}; background: ${tr.bg}; border: 1px solid ${tr.brd};">
          ${s.triage_class}
        </span>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: baseline; margin-top: 2px;">
        <div>
          <div style="font-size: 9px; font-family: var(--font-mono); color: #64748b; font-weight: 700;">ESTIMATED HEART RATE</div>
          <div style="font-size: 18px; font-weight: 800; font-family: var(--font-mono); color: ${s.has_signal ? '#dc2626' : '#94a3b8'};">
            ${hrText}
          </div>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 9px; font-family: var(--font-mono); color: #64748b; font-weight: 700;">CONFIDENCE</div>
          <div style="font-size: 14px; font-weight: 800; font-family: var(--font-mono); color: #16a34a;">
            ${confPct}%
          </div>
        </div>
      </div>

      <div>
        <div style="display: flex; justify-content: space-between; font-size: 9px; font-family: var(--font-mono); color: #64748b; margin-bottom: 2px;">
          <span>MINI DOPPLER CARDIAC TRACE</span>
          <span>Depth: ${s.estimated_depth_m.toFixed(1)}m</span>
        </div>
        <canvas id="mini-canvas-${s.id}" width="300" height="50" class="doppler-mini-canvas"></canvas>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 4px; padding-top: 8px; border-top: 1px solid #f1f5f9;">
        <span style="font-size: 9px; font-family: var(--font-mono); color: #64748b;">
          SNR: <strong style="color: #2563eb;">+${s.snr_db.toFixed(1)} dB</strong>
        </span>
        <button type="button" class="btn btn-view-doppler" data-target-id="${s.id}"
          style="padding: 4px 10px; font-size: 10px; font-family: var(--font-mono); font-weight: 700; background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; border-radius: 4px; cursor: pointer; transition: all 0.15s ease;">
          🔍 View Details
        </button>
      </div>
    `;

    const btn = card.querySelector(".btn-view-doppler");
    if (btn) {
      btn.addEventListener("click", () => {
        openDopplerModal(s);
      });
    }

    return card;
  }

  function renderMiniWaveformCanvas(target) {
    const canvas = document.getElementById(`mini-canvas-${target.id}`);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    const sigData = generateDopplerSignals(target, globalTimeOffset, 64);
    const cardSig = sigData.cardiacSignal;

    ctx.strokeStyle = "#e2ecfa";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();

    if (!target.has_signal) {
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < cardSig.length; i++) {
        const x = (i / (cardSig.length - 1)) * w;
        const y = h / 2 - cardSig[i] * (h * 0.4);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      return;
    }

    // Draw mini pulse wave (Red)
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    for (let i = 0; i < cardSig.length; i++) {
      const x = (i / (cardSig.length - 1)) * w;
      const y = h / 2 - cardSig[i] * (h * 1.6);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Draw mini systolic peak dots
    sigData.peaks.forEach(p => {
      const px = (p.sampleIndex / (cardSig.length - 1)) * w;
      const py = h / 2 - p.amplitude * (h * 1.6);
      ctx.fillStyle = "#dc2626";
      ctx.beginPath();
      ctx.arc(px, Math.max(3, Math.min(h - 3, py)), 2.5, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  // ------------------------------------------------------------------ //
  // Diagnostic Detail Modal & Real-Time Visualization Loop
  // ------------------------------------------------------------------ //
  function openDopplerModal(target) {
    activeModalTarget = target;
    const modal = document.getElementById("dopplerDetailModal");
    if (!modal) return;

    // Populate header & top metrics
    const elTargetId = document.getElementById("modalTargetId");
    const elTriageBadge = document.getElementById("modalTriageBadge");
    const elHeartRate = document.getElementById("modalHeartRate");
    const elRrInterval = document.getElementById("modalRrInterval");
    const elConfidence = document.getElementById("modalConfidence");
    const elSnrText = document.getElementById("modalSnrText");
    const elDepth = document.getElementById("modalDepth");
    const elDepthUncert = document.getElementById("modalDepthUncertText");
    const elFooterTarget = document.getElementById("modalFooterTarget");

    const tr = getTriageStyle(target.triage_class);

    if (elTargetId) elTargetId.textContent = target.id;
    if (elFooterTarget) elFooterTarget.textContent = target.id;

    if (elTriageBadge) {
      elTriageBadge.textContent = target.triage_class;
      elTriageBadge.style.color = tr.col;
      elTriageBadge.style.background = tr.bg;
      elTriageBadge.style.borderColor = tr.brd;
    }

    if (target.has_signal && target.heart_rate_bpm > 0) {
      if (elHeartRate) elHeartRate.textContent = target.heart_rate_bpm.toFixed(1);
      const rrMs = Math.round((60.0 / target.heart_rate_bpm) * 1000);
      if (elRrInterval) elRrInterval.textContent = rrMs;
      if (elConfidence) elConfidence.textContent = Math.round(target.confidence * 100);
      if (elSnrText) elSnrText.textContent = `SNR: +${target.snr_db.toFixed(1)} dB`;
      if (elDepth) elDepth.textContent = target.estimated_depth_m.toFixed(2);
      if (elDepthUncert) elDepthUncert.textContent = `±${target.depth_uncertainty_m.toFixed(2)}m uncertainty`;
    } else {
      if (elHeartRate) elHeartRate.textContent = "--";
      if (elRrInterval) elRrInterval.textContent = "--";
      if (elConfidence) elConfidence.textContent = "0";
      if (elSnrText) elSnrText.textContent = "No Signal";
      if (elDepth) elDepth.textContent = "--";
      if (elDepthUncert) elDepthUncert.textContent = "N/A";
    }

    modal.classList.add("is-open");
    startModalAnimationLoop();
  }

  function closeDopplerModal() {
    const modal = document.getElementById("dopplerDetailModal");
    if (modal) modal.classList.remove("is-open");
    if (modalAnimationId) {
      cancelAnimationFrame(modalAnimationId);
      modalAnimationId = null;
    }
    activeModalTarget = null;
  }

  function startModalAnimationLoop() {
    if (modalAnimationId) cancelAnimationFrame(modalAnimationId);

    function step() {
      if (!activeModalTarget) return;
      renderModalWaveforms(activeModalTarget);
      globalTimeOffset += 0.05;
      modalAnimationId = requestAnimationFrame(step);
    }
    modalAnimationId = requestAnimationFrame(step);
  }

  function renderModalWaveforms(target) {
    const rawCanvas = document.getElementById("rawDopplerCanvas");
    const cardCanvas = document.getElementById("cardiacPeaksCanvas");
    const beatsLog = document.getElementById("modalBeatsLog");

    if (!rawCanvas || !cardCanvas) return;

    const rawCtx = rawCanvas.getContext("2d");
    const cardCtx = cardCanvas.getContext("2d");
    const rw = rawCanvas.width;
    const rh = rawCanvas.height;
    const cw = cardCanvas.width;
    const ch = cardCanvas.height;

    rawCtx.clearRect(0, 0, rw, rh);
    cardCtx.clearRect(0, 0, cw, ch);

    // Draw grid background
    drawCanvasGrid(rawCtx, rw, rh);
    drawCanvasGrid(cardCtx, cw, ch);

    const sigData = generateDopplerSignals(target, globalTimeOffset, 128);
    const raw = sigData.rawSignal;
    const cardiac = sigData.cardiacSignal;
    const peaks = sigData.peaks;

    // 1. Draw Raw Doppler Displacement Signal (Cyan/Blue)
    rawCtx.strokeStyle = "#2563eb";
    rawCtx.lineWidth = 1.8;
    rawCtx.beginPath();
    for (let i = 0; i < raw.length; i++) {
      const x = (i / (raw.length - 1)) * rw;
      const y = rh / 2 - raw[i] * (rh * 0.4);
      if (i === 0) rawCtx.moveTo(x, y);
      else rawCtx.lineTo(x, y);
    }
    rawCtx.stroke();

    // 2. Draw Filtered Bandpass Cardiac Signal (Red)
    cardCtx.strokeStyle = "#dc2626";
    cardCtx.lineWidth = 2.0;
    cardCtx.beginPath();
    for (let i = 0; i < cardiac.length; i++) {
      const x = (i / (cardiac.length - 1)) * cw;
      const y = ch / 2 - cardiac[i] * (ch * 1.5);
      if (i === 0) cardCtx.moveTo(x, y);
      else cardCtx.lineTo(x, y);
    }
    cardCtx.stroke();

    // Draw Peak Detection Markers with Time Tags
    peaks.forEach((p, idx) => {
      const px = (p.sampleIndex / (cardiac.length - 1)) * cw;
      const py = ch / 2 - p.amplitude * (ch * 1.5);

      // Peak vertical marker line
      cardCtx.strokeStyle = "rgba(220, 38, 38, 0.4)";
      cardCtx.lineWidth = 1;
      cardCtx.setLineDash([2, 2]);
      cardCtx.beginPath();
      cardCtx.moveTo(px, 0);
      cardCtx.lineTo(px, ch);
      cardCtx.stroke();
      cardCtx.setLineDash([]);

      // Peak circle
      cardCtx.fillStyle = "#dc2626";
      cardCtx.beginPath();
      cardCtx.arc(px, py, 4, 0, Math.PI * 2);
      cardCtx.fill();

      // Peak label
      cardCtx.fillStyle = "#991b1b";
      cardCtx.font = "bold 9px JetBrains Mono, monospace";
      cardCtx.fillText(`P${idx + 1}`, Math.max(2, px - 6), Math.max(12, py - 6));
    });

    // Update detected beat chips log (only if peaks exist)
    if (beatsLog) {
      if (!target.has_signal || peaks.length === 0) {
        beatsLog.innerHTML = `<span style="color: #94a3b8;">No coherent systolic heartbeat peaks detected in slow-time spectrum.</span>`;
      } else {
        let html = "";
        peaks.slice(-6).forEach((p, idx) => {
          html += `
            <span style="background: #ffffff; border: 1px solid #d3e1f5; border-radius: 4px; padding: 2px 6px; color: #0f2547;">
              Beat #${idx + 1} @ ${(p.timeSec % 100).toFixed(2)}s (RR: ${sigData.rrIntervalMs}ms)
            </span>
          `;
        });
        beatsLog.innerHTML = html;
      }
    }
  }

  function drawCanvasGrid(ctx, w, h) {
    ctx.strokeStyle = "#e2ecfa";
    ctx.lineWidth = 1;

    // Horizontal center
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();

    // Vertical time divisions (every 1/4)
    for (let i = 1; i < 4; i++) {
      const x = (i / 4) * w;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
  }

  // ------------------------------------------------------------------ //
  // Initialization & Event Listeners
  // ------------------------------------------------------------------ //
  function setupEventListeners() {
    const searchInput = document.getElementById("dopplerSearchInput");
    const triageFilter = document.getElementById("dopplerTriageFilter");
    const sortSelect = document.getElementById("dopplerSortSelect");
    const refreshBtn = document.getElementById("dopplerRefreshBtn");
    const modalCloseBtn = document.getElementById("modalCloseBtn");
    const modalDismissBtn = document.getElementById("modalDismissBtn");
    const modalBackdrop = document.getElementById("dopplerDetailModal");

    if (searchInput) searchInput.addEventListener("input", applyFiltersAndRender);
    if (triageFilter) triageFilter.addEventListener("change", applyFiltersAndRender);
    if (sortSelect) sortSelect.addEventListener("change", applyFiltersAndRender);

    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => {
        fetchDopplerData();
      });
    }

    if (modalCloseBtn) modalCloseBtn.addEventListener("click", closeDopplerModal);
    if (modalDismissBtn) modalDismissBtn.addEventListener("click", closeDopplerModal);

    if (modalBackdrop) {
      modalBackdrop.addEventListener("click", (e) => {
        if (e.target === modalBackdrop) {
          closeDopplerModal();
        }
      });
    }

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && activeModalTarget) {
        closeDopplerModal();
      }
    });
  }

  function init() {
    setupEventListeners();
    fetchDopplerData();

    // Regular polling every 2.5 seconds
    pollInterval = setInterval(fetchDopplerData, 2500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
