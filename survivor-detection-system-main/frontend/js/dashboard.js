/* ==========================================================================
   RIDGEWATCH dashboard client
   Vanilla JS, talks to the FastAPI backend (api.py) over fetch(). No build
   step, no frameworks — this is meant to run by opening index.html (or via
   any static file server) against a locally-running `uvicorn api:app`.
   ========================================================================== */

(() => {
  "use strict";

  // ------------------------------------------------------------------ //
  // Config
  // ------------------------------------------------------------------ //

  const POLL_MS = 4000;                 // dashboard polling interval
  const MAX_ALERTS = 300;

  const SENSOR_META = {
    thermal_imaging:     { label: "THERMAL",   unit: "°C",   min: -5,  max: 35 },
    pir_motion:          { label: "MOTION",    unit: "",     min: 0,   max: 1 },
    acoustic:            { label: "ACOUSTIC",  unit: "dB",   min: 0,   max: 70 },
    co2:                 { label: "CO2",       unit: "ppm",  min: 400, max: 2500 },
    heart_rate_radar:    { label: "RADAR HR",  unit: "bpm",  min: 0,   max: 110 },
    rgb_camera:          { label: "RGB CAM",   unit: "",     min: 0,   max: 1 },
    imu_tilt:            { label: "KIT TILT",  unit: "°",   min: 0,   max: 20 },
    imu_vibration:       { label: "KIT VIBE",  unit: "g",   min: 0,   max: 1 },
    water_level:         { label: "WATER LVL", unit: "cm",  min: 0,   max: 200 },
    water_flow:          { label: "FLOW SPD",  unit: "m/s", min: 0,   max: 3.0 },
    gas_concentration:   { label: "GAS LEVEL", unit: "ppm", min: 0,   max: 500 },
    smoke_density:       { label: "SMOKE DENS",unit: "%",   min: 0,   max: 100 },
    barometric_pressure: { label: "BARO PRESS",unit: "hPa", min: 900, max: 1050 },
    rainfall_intensity:  { label: "RAINFALL",  unit: "mm/h",min: 0,   max: 100 },
    soil_moisture:       { label: "SOIL MOIST",unit: "%",   min: 0,   max: 100 },
    temperature:         { label: "AIR TEMP",  unit: "°C",  min: -40, max: 85 },
    humidity:            { label: "HUMIDITY",  unit: "%",   min: 0,   max: 100 },
    gps:                 { label: "GNSS GPS",  unit: "sats", min: 0,   max: 20 },
  };
  const SENSOR_ORDER = [
    "heart_rate_radar", "thermal_imaging", "acoustic", "co2", "pir_motion", "rgb_camera",
    "imu_tilt", "imu_vibration", "water_level", "water_flow", "gas_concentration",
    "smoke_density", "barometric_pressure", "rainfall_intensity", "soil_moisture",
    "temperature", "humidity", "gps"
  ];

  const TRIAGE_COLORS = {
    HIGH: "#ff4438",
    MEDIUM: "#ff9f0a",
    LOW: "#ffd60a",
    NO_VITAL_SIGNS: "#6e7a7d",
    SAFE: "#34d399",
  };
  const TRIAGE_EMOJI = {
    HIGH: "🔴",
    MEDIUM: "🟠",
    LOW: "🟡",
    NO_VITAL_SIGNS: "⚪",
    SAFE: "🟢",
  };
  const TRIAGE_LABELS = {
    HIGH: "🔴 HIGH — urgent, viable",
    MEDIUM: "🟠 MEDIUM — probable vitals",
    LOW: "🟡 LOW — weak signal",
    NO_VITAL_SIGNS: "⚪ NO VITAL SIGNS",
    SAFE: "🟢 SAFE — self-evacuating",
  };

  // Site origin used by the backend scenario. This used to be a fixed
  // constant (models.HIMALAYA_SITE_ORIGIN) but now comes from whichever
  // scenario is loaded server-side - see GET /scenarios / scenario.site_origin
  // on /scenario/start and /victims responses. Seeded with the Himalaya
  // default so the map has *something* to project against before the first
  // response arrives; updateSiteOrigin() below keeps it in sync afterward.
  let SITE_ORIGIN = { latitude: 32.3739, longitude: 77.2491, altitude_m: 3950 };
  const METERS_PER_DEG_LAT = 111320;

  // ------------------------------------------------------------------ //
  // State
  // ------------------------------------------------------------------ //

  const state = {
    get apiBase() { return RidgeWatchConfig.getApiBase(); },
    scenarioRunning: false,
    connected: false,
    victims: [],           // last /victims payload's `victims` array
    queue: [],              // last /queue payload's `queue` array
    teams: [],               // deprecated Step 27 — no longer polled from Dashboard/Hardware, left for backward-compat reference
    dispatchSim: null,        // deprecated Step 27 — old single-agent (RESCUE-1) auto-walk, no longer polled from Dashboard/Hardware
    teamMembers: [],           // Step 27: last /rescue-team/members-status `members` array — CMD-leader live team-member data
    selectedVictimId: null,
    prevTriageByVictim: {},    // victim_id -> last-seen triage_class, for change alerts
    prevOnlineByVictim: {},     // victim_id -> last-seen sensor_node_online
    prevLowBatteryByVictim: {},  // victim_id -> last-seen low-battery state, for one-shot alerts
    prevAftershockActive: false,   // site-wide, not per-victim
    reachedLogged: new Set(),    // dispatch arrivals already written to the alert log
    dispatchedLogged: new Set(),  // "team dispatched to X" events already logged (team_id:victim_id)
    lastArrivalCheckTs: null,   // Step 26: ISO timestamp cursor for /rescue-team/member-arrivals - only alert on genuinely new arrivals
    availableScenarioCount: 0,  // Step 28: cached from /scenarios so renderStatCards() doesn't need its own fetch
    pollTimer: null,
    polling: false,
  };

  // ------------------------------------------------------------------ //
  // DOM refs
  // ------------------------------------------------------------------ //

  const el = {
    apiBaseInput: document.getElementById("apiBaseInput"),
    apiBaseSaveBtn: document.getElementById("apiBaseSaveBtn"),
    connIndicator: document.getElementById("connIndicator"),
    connLabel: document.getElementById("connLabel"),
    startBtn: document.getElementById("startBtn"),
    resetBtn: document.getElementById("resetBtn"),
    scenarioSelect: document.getElementById("scenarioSelect"),
    siteTagValue: document.getElementById("siteTagValue"),
    scenarioState: document.getElementById("scenarioState"),
    scenarioCycle: document.getElementById("scenarioCycle"),
    scenarioClock: document.getElementById("scenarioClock"),
    scenarioRain: document.getElementById("scenarioRain"),
    scenarioSoil: document.getElementById("scenarioSoil"),
    scenarioSeismic: document.getElementById("scenarioSeismic"),
    scenarioTilt: document.getElementById("scenarioTilt"),
    scenarioEnv: document.getElementById("scenarioEnv"),
    siteMap: document.getElementById("siteMap"),
    mapEmpty: document.getElementById("mapEmpty"),
    mapLegend: document.getElementById("mapLegend"),
    readoutVictimTag: document.getElementById("readoutVictimTag"),
    oledContent: document.getElementById("oledContent"),
    queueList: document.getElementById("queueList"),
    queueCount: document.getElementById("queueCount"),
    teamsBody: document.getElementById("teamsBody"),
    alertLog: document.getElementById("alertLog"),
    clearAlertsBtn: document.getElementById("clearAlertsBtn"),
    muteToggleBtn: document.getElementById("muteToggleBtn"),
    solarChargingToggle: document.getElementById("solarChargingToggle"),
    networkAlertLog: document.getElementById("networkAlertLog"),
    statusMessage: document.getElementById("statusMessage"),
    statusPoll: document.getElementById("statusPoll"),
    statScenarioCount: document.getElementById("statScenarioCount"),
    statScenarioSub: document.getElementById("statScenarioSub"),
    statVictimCount: document.getElementById("statVictimCount"),
    statVictimSub: document.getElementById("statVictimSub"),
    statTeamCount: document.getElementById("statTeamCount"),
    statTeamSub: document.getElementById("statTeamSub"),
    statRescuedCount: document.getElementById("statRescuedCount"),
    statRescuedSub: document.getElementById("statRescuedSub"),
  };

  // ------------------------------------------------------------------ //
  // API helpers
  // ------------------------------------------------------------------ //

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
      body: JSON.stringify(payload || {}),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.detail || res.statusText);
    }
    return res.json();
  }

  class ApiError extends Error {
    constructor(status, detail) {
      super(detail || `HTTP ${status}`);
      this.status = status;
    }
  }

  // ------------------------------------------------------------------ //
  // Alert log
  // ------------------------------------------------------------------ //

  function pushAlert(level, text) {
    const row = document.createElement("div");
    row.className = `alert-row alert-level-${level}`;

    const time = document.createElement("span");
    time.className = "alert-time";
    time.textContent = new Date().toLocaleTimeString([], { hour12: false });

    const tag = document.createElement("span");
    tag.className = "alert-tag";
    tag.textContent = level.toUpperCase();

    const txt = document.createElement("span");
    txt.className = "alert-text";
    txt.textContent = text;

    row.append(time, tag, txt);

    const emptyNote = el.alertLog.querySelector(".empty-note");
    if (emptyNote) emptyNote.remove();

    el.alertLog.prepend(row);

    while (el.alertLog.children.length > MAX_ALERTS) {
      el.alertLog.removeChild(el.alertLog.lastChild);
    }
  }

  el.clearAlertsBtn.addEventListener("click", () => {
    el.alertLog.innerHTML = '<p class="empty-note">No events yet.</p>';
  });

  // ------------------------------------------------------------------ //
  // Audio alert (buzzer replacement — no physical LED/buzzer exists)
  // ------------------------------------------------------------------ //

  let audioCtx = null;
  let audioUnlocked = false;   // browsers block audio until first user gesture
  let audioMuted = localStorage.getItem("ridgewatch.audioMuted") === "true";

  const TONE_PROFILE = {
    HIGH:   { freq: 880, pattern: [180, 100, 180, 100, 180], type: "square" },  // urgent triple-beep
    MEDIUM: { freq: 660, pattern: [150, 150],                type: "sine"   }, // double-beep
    LOW:    { freq: 440, pattern: [200],                     type: "sine"   }, // single soft beep
  };

  function ensureAudioContext() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioCtx;
  }

  function playAlertTone(triageClass) {
    if (audioMuted || !audioUnlocked) return;
    const profile = TONE_PROFILE[triageClass];
    if (!profile) return;   // no tone for SAFE / NO_VITAL_SIGNS — audio is for urgent classes only

    const ctx = ensureAudioContext();
    let t = ctx.currentTime;

    for (const durationMs of profile.pattern) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = profile.type;
      osc.frequency.value = profile.freq;

      // quick attack/decay envelope so it reads as a "beep", not a harsh click
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.35, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + durationMs / 1000);

      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + durationMs / 1000 + 0.02);

      t += durationMs / 1000 + 0.08;   // small gap between beeps in the pattern
    }
  }

  function setAudioMuted(muted) {
    audioMuted = muted;
    localStorage.setItem("ridgewatch.audioMuted", String(muted));
    if (el.muteToggleBtn) {
      el.muteToggleBtn.textContent = muted ? "🔇 Sound off" : "🔊 Sound on";
      el.muteToggleBtn.setAttribute("aria-pressed", String(!muted));
    }
  }

  el.muteToggleBtn.addEventListener("click", () => {
    setAudioMuted(!audioMuted);
  });

  // ------------------------------------------------------------------ //
  // Network alert log (simulated GSM/LoRa transmission log)
  // ------------------------------------------------------------------ //
  // Distinct from pushAlert() above: this reflects the *simulated network
  // layer* (see backend/alert_dispatch.py) - latency, packet loss, retry
  // count - not just an in-app UI badge. Every HIGH-priority victim alert
  // the backend actually attempted to transmit (sent or failed) shows up
  // here, separately from the general dashboard event log.

  function pushNetworkAlert(record) {
    const statusIcon = record.status === "sent" ? "📡✅" : "📡❌";
    const text = `${statusIcon} ${record.channel.toUpperCase()} to ${record.victim_id}: ${record.reason} (${record.latency_ms}ms, battery ${record.battery_pct_at_send}%)`;

    const row = document.createElement("div");
    row.className = `alert-row net-alert-${record.status}`;

    const time = document.createElement("span");
    time.className = "alert-time";
    time.textContent = new Date(record.timestamp).toLocaleTimeString([], { hour12: false });

    const tag = document.createElement("span");
    tag.className = "alert-tag";
    tag.textContent = record.status.toUpperCase();

    const txt = document.createElement("span");
    txt.className = "alert-text";
    txt.textContent = text;

    row.append(time, tag, txt);

    const emptyNote = el.networkAlertLog.querySelector(".empty-note");
    if (emptyNote) emptyNote.remove();

    el.networkAlertLog.prepend(row);

    while (el.networkAlertLog.children.length > MAX_ALERTS) {
      el.networkAlertLog.removeChild(el.networkAlertLog.lastChild);
    }
  }

  // ------------------------------------------------------------------ //
  // Connection indicator / status bar
  // ------------------------------------------------------------------ //

  function setConnState(connState, label) {
    el.connIndicator.dataset.state = connState;
    el.connLabel.textContent = label;
  }

  function setStatusMessage(msg) {
    el.statusMessage.textContent = msg;
  }

  // ------------------------------------------------------------------ //
  // Scenario controls
  // ------------------------------------------------------------------ //

  // Sync the local SITE_ORIGIN + "SITE" header tag to whatever scenario the
  // backend reports as running - each scenario config (avalanche/earthquake/
  // flood/...) has its own site_origin + site_label (see scenario_loader.py).
  function updateSiteOrigin(scenarioMeta) {
    if (!scenarioMeta || !scenarioMeta.site_origin) return;
    SITE_ORIGIN = scenarioMeta.site_origin;
    if (scenarioMeta.site_label) {
      el.siteTagValue.textContent = scenarioMeta.site_label;
    }
  }

  // Populate the scenario dropdown from GET /scenarios, dynamically filtering
  // only ACTIVE scenarios from the Scenarios Ledger (single source of truth).
  async function loadScenarioList() {
    try {
      const res = await apiGet("/scenarios");
      const allScenarios = res.scenarios || [];
      const activeScenarios = allScenarios.filter(
        (s) => (s.status || "Active").toLowerCase() === "active"
      );
      state.availableScenarioCount = activeScenarios.length;

      el.scenarioSelect.innerHTML = "";

      if (activeScenarios.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "No active scenarios available.";
        opt.disabled = true;
        opt.selected = true;
        el.scenarioSelect.appendChild(opt);
        el.scenarioSelect.disabled = true;
        if (el.startBtn && !state.scenarioRunning) el.startBtn.disabled = true;
        renderStatCards();
        return;
      }

      el.scenarioSelect.disabled = false;
      if (el.startBtn && !state.scenarioRunning) el.startBtn.disabled = false;

      const previouslySelected = el.scenarioSelect.value;
      for (const s of activeScenarios) {
        const opt = document.createElement("option");
        opt.value = s.scenario_id || s.id;
        opt.textContent = `${s.name} (${s.victim_count})`;
        opt.title = s.description || "";
        el.scenarioSelect.appendChild(opt);
      }
      // keep the previous selection if it still exists and is active, else keep default
      if (activeScenarios.some((s) => (s.scenario_id || s.id) === previouslySelected)) {
        el.scenarioSelect.value = previouslySelected;
      }
      renderStatCards();
    } catch (err) {
      pushAlert("warn", `Could not load scenario list: ${err.message}`);
    }
  }

  el.startBtn.addEventListener("click", async () => {
    if (!el.scenarioSelect.value || el.scenarioSelect.disabled) {
      pushAlert("warn", "No active scenario available to start.");
      return;
    }
    if (!audioUnlocked) {
      ensureAudioContext();
      audioUnlocked = true;
      setAudioMuted(audioMuted);   // sync button label to saved preference
    }
    el.startBtn.disabled = true;
    el.scenarioSelect.disabled = true;
    if (el.solarChargingToggle) el.solarChargingToggle.disabled = true;
    try {
      const scenarioId = el.scenarioSelect.value;
      const res = await apiPost("/scenario/start", {
        scenario: scenarioId,
        enable_degradation: true,
        enable_solar_charging: !!(el.solarChargingToggle && el.solarChargingToggle.checked),
      });
      state.scenarioRunning = true;
      state.prevTriageByVictim = {};
      state.prevOnlineByVictim = {};
      state.prevLowBatteryByVictim = {};
      state.prevAftershockActive = false;
      state.reachedLogged = new Set();
      state.dispatchedLogged = new Set();
      state.selectedVictimId = null;
      updateSiteOrigin(res);
      el.scenarioState.textContent = "RUNNING";
      pushAlert("success", `${res.scenario_name || "Scenario"} started — ${res.victim_count} sensor nodes provisioning.`);
      startPolling();
    } catch (err) {
      pushAlert("critical", `Failed to start scenario: ${err.message}`);
      el.scenarioSelect.disabled = false;
      if (el.solarChargingToggle) el.solarChargingToggle.disabled = false;
    } finally {
      el.startBtn.disabled = false;
    }
  });

  el.resetBtn.addEventListener("click", async () => {
    try {
      await apiPost("/scenario/reset", {});
      state.scenarioRunning = false;
      state.victims = [];
      state.queue = [];
      state.teams = [];
      state.dispatchSim = null;
      state.teamMembers = [];
      state.selectedVictimId = null;
      stopPolling();
      el.scenarioState.textContent = "NOT STARTED";
      el.scenarioCycle.textContent = "cycle 0";
      if (el.scenarioRain) {
        el.scenarioRain.hidden = true;
        el.scenarioRain.textContent = "🌧️ -- mm/hr";
      }
      if (el.scenarioSoil) {
        el.scenarioSoil.hidden = true;
        el.scenarioSoil.classList.remove("soil-risk");
        el.scenarioSoil.textContent = "🪨 -- % saturated";
      }
      if (el.scenarioSeismic) {
        el.scenarioSeismic.hidden = true;
        el.scenarioSeismic.classList.remove("seismic-alert");
        el.scenarioSeismic.textContent = "📈 -- mm/s PGV";
      }
      if (el.scenarioTilt) {
        el.scenarioTilt.hidden = true;
        el.scenarioTilt.classList.remove("tilt-danger");
        el.scenarioTilt.textContent = "📐 -- °";
      }
      if (el.scenarioEnv) {
        el.scenarioEnv.hidden = true;
        el.scenarioEnv.classList.remove("env-risk");
        el.scenarioEnv.textContent = "🌡️ -- °C · -- % RH";
      }
      state.prevAftershockActive = false;
      if (el.solarChargingToggle) el.solarChargingToggle.disabled = false;
      renderMap();
      renderReadout(null);
      renderQueue();
      renderTeamMembers(state.teamMembers);
      await loadScenarioList();
      pushAlert("warn", "Scenario reset.");
    } catch (err) {
      pushAlert("critical", `Failed to reset scenario: ${err.message}`);
    }
  });

  // ------------------------------------------------------------------ //
  // Map: local flat-earth projection + SVG render
  // ------------------------------------------------------------------ //

  const MAP_SIZE = 600;          // svg viewBox units
  const MAP_METERS_SPAN = 180;   // meters shown edge-to-edge (site spans ~70-100m)
  const MAP_SAFE_MARGIN = 22;    // safe pixel margin from viewport edges

  function metersPerDegLon(latDeg) {
    return METERS_PER_DEG_LAT * Math.cos((latDeg * Math.PI) / 180);
  }

  // Project a {latitude, longitude} into local meters east/north of SITE_ORIGIN.
  function toLocalMeters(loc) {
    const dLat = loc.latitude - SITE_ORIGIN.latitude;
    const dLon = loc.longitude - SITE_ORIGIN.longitude;
    return {
      east: dLon * metersPerDegLon(SITE_ORIGIN.latitude),
      north: dLat * METERS_PER_DEG_LAT,
    };
  }

  // Project local meters into SVG (x, y). North is up, east is right.
  function metersToSvg(m) {
    const scale = MAP_SIZE / MAP_METERS_SPAN;
    return {
      x: MAP_SIZE / 2 + m.east * scale,
      y: MAP_SIZE / 2 - m.north * scale,
    };
  }

  function locToSvg(loc) {
    return metersToSvg(toLocalMeters(loc));
  }

  function clamp(val, min, max) {
    return Math.min(Math.max(val, min), max);
  }

  // Disperse markers that fall very close to each other on screen
  function disperseMarkers(items, radiusThreshold = 22) {
    const minX = MAP_SAFE_MARGIN, maxX = MAP_SIZE - MAP_SAFE_MARGIN;
    const minY = MAP_SAFE_MARGIN, maxY = MAP_SIZE - MAP_SAFE_MARGIN;

    const markers = items.map(item => {
      const raw = locToSvg(item.location || SITE_ORIGIN);
      const clampedX = clamp(raw.x, minX, maxX);
      const clampedY = clamp(raw.y, minY, maxY);
      return {
        ...item,
        rawX: raw.x,
        rawY: raw.y,
        clampedX,
        clampedY,
        renderX: clampedX,
        renderY: clampedY,
        isOffset: false,
      };
    });

    // Group close markers into clusters
    const visited = new Set();
    for (let i = 0; i < markers.length; i++) {
      if (visited.has(i)) continue;
      const cluster = [i];
      visited.add(i);

      for (let j = i + 1; j < markers.length; j++) {
        if (visited.has(j)) continue;
        const dx = markers[i].clampedX - markers[j].clampedX;
        const dy = markers[i].clampedY - markers[j].clampedY;
        if (Math.hypot(dx, dy) < radiusThreshold) {
          cluster.push(j);
          visited.add(j);
        }
      }

      if (cluster.length > 1) {
        let avgX = 0, avgY = 0;
        for (const idx of cluster) {
          avgX += markers[idx].clampedX;
          avgY += markers[idx].clampedY;
        }
        avgX /= cluster.length;
        avgY /= cluster.length;

        const spreadRadius = 14 + Math.min(cluster.length * 2.5, 18);
        cluster.forEach((idx, k) => {
          const angle = (k * 2 * Math.PI) / cluster.length - Math.PI / 2;
          const nx = clamp(avgX + spreadRadius * Math.cos(angle), minX, maxX);
          const ny = clamp(avgY + spreadRadius * Math.sin(angle), minY, maxY);
          markers[idx].renderX = nx;
          markers[idx].renderY = ny;
          if (Math.hypot(nx - markers[idx].rawX, ny - markers[idx].rawY) > 5) {
            markers[idx].isOffset = true;
          }
        });
      }
    }

    return markers;
  }

  function getSmartLabelAttrs(x, y) {
    const flipX = x > 380 || x > (MAP_SIZE - 110);
    const xOffset = flipX ? -14 : 14;
    const textAnchor = flipX ? "end" : "start";
    let yOffset = 4;
    let dominantBaseline = "middle";

    if (y < 24) {
      yOffset = 16;
      dominantBaseline = "hanging";
    } else if (y > MAP_SIZE - 24) {
      yOffset = -12;
      dominantBaseline = "auto";
    }

    return { xOffset, yOffset, textAnchor, dominantBaseline };
  }

  function svgEl(tag, attrs) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    return node;
  }

  function buildMapChrome() {
    // static background layer: contour rings, grid, N arrow, scale bar
    const g = svgEl("g", { id: "mapChrome" });

    // contour rings around the debris-cone origin (decorative, avalanche
    // debris field convention — concentric distance rings from the slide origin)
    for (let r = 40; r <= 260; r += 40) {
      g.appendChild(svgEl("circle", {
        class: "contour",
        cx: MAP_SIZE / 2, cy: MAP_SIZE / 2, r,
      }));
    }

    // light grid
    for (let i = 1; i < 6; i++) {
      const p = (MAP_SIZE / 6) * i;
      g.appendChild(svgEl("line", { class: "map-grid-line", x1: p, y1: 0, x2: p, y2: MAP_SIZE }));
      g.appendChild(svgEl("line", { class: "map-grid-line", x1: 0, y1: p, x2: MAP_SIZE, y2: p }));
    }

    // N arrow
    const nGroup = svgEl("g", { transform: `translate(${MAP_SIZE - 36}, 30)` });
    nGroup.appendChild(svgEl("path", {
      d: "M 0 14 L 0 -14 M -5 -8 L 0 -14 L 5 -8",
      stroke: "#3a4c48", "stroke-width": 1.5, fill: "none",
    }));
    nGroup.appendChild(svgEl("text", { class: "map-axis-label", x: -3, y: 26 }));
    nGroup.lastChild.textContent = "N";
    g.appendChild(nGroup);

    // scale bar (50m)
    const scaleScale = MAP_SIZE / MAP_METERS_SPAN;
    const barLen = 50 * scaleScale;
    const barX = 24, barY = MAP_SIZE - 22;
    g.appendChild(svgEl("line", { class: "scale-bar-line", x1: barX, y1: barY, x2: barX + barLen, y2: barY }));
    g.appendChild(svgEl("line", { class: "scale-bar-line", x1: barX, y1: barY - 4, x2: barX, y2: barY + 4 }));
    g.appendChild(svgEl("line", { class: "scale-bar-line", x1: barX + barLen, y1: barY - 4, x2: barX + barLen, y2: barY + 4 }));
    const scaleLabel = svgEl("text", { class: "scale-bar-label", x: barX, y: barY - 8 });
    scaleLabel.textContent = "50 m";
    g.appendChild(scaleLabel);

    // origin marker (avalanche debris-cone apex)
    const origin = svgEl("g", { transform: `translate(${MAP_SIZE / 2}, ${MAP_SIZE / 2})` });
    origin.appendChild(svgEl("path", { d: "M -6 6 L 0 -7 L 6 6 Z", fill: "none", stroke: "#2a3a37", "stroke-width": 1.2 }));
    g.appendChild(origin);

    return g;
  }

  function renderMap() {
    const svg = el.siteMap;
    svg.innerHTML = "";
    svg.appendChild(buildMapChrome());

    const hasVictims = state.victims.length > 0;
    el.mapEmpty.classList.toggle("hidden", hasVictims);
    if (!hasVictims) {
      renderMapLegend();
      return;
    }

    // triage lookup by victim id, from the ranked queue (authoritative
    // triage classification); fall back gracefully if queue hasn't loaded yet
    const triageByVictim = {};
    for (const q of state.queue) triageByVictim[q.victim_id] = q;

    const pinsLayer = svgEl("g", { id: "pinsLayer" });

    // Disperse and clamp all victims within viewport boundaries
    const dispersedVictims = disperseMarkers(state.victims);

    for (const v of dispersedVictims) {
      const q = triageByVictim[v.victim_id];
      const triageClass = q ? q.triage_class : "NO_VITAL_SIGNS";
      const color = TRIAGE_COLORS[triageClass] || TRIAGE_COLORS.NO_VITAL_SIGNS;
      const isSelected = v.victim_id === state.selectedVictimId;
      const isUrgent = triageClass === "HIGH";
      const isOffline = !v.sensor_node_online;

      // Draw dashed connector line if pin was shifted due to collision
      if (v.isOffset && Math.hypot(v.renderX - v.clampedX, v.renderY - v.clampedY) > 3) {
        pinsLayer.appendChild(svgEl("line", {
          class: "pin-leader-line",
          x1: v.clampedX,
          y1: v.clampedY,
          x2: v.renderX,
          y2: v.renderY,
          stroke: color,
          "stroke-width": 1,
          "stroke-dasharray": "2,2",
          opacity: 0.6,
        }));
      }

      const pin = svgEl("g", {
        class: `pin${isSelected ? " is-selected" : ""}${isUrgent ? " is-urgent" : ""}`,
        transform: `translate(${v.renderX}, ${v.renderY})`,
        tabindex: "0",
        role: "button",
        "aria-label": `Victim ${v.victim_id}, ${TRIAGE_LABELS[triageClass] || triageClass}`,
      });

      pin.appendChild(svgEl("circle", { class: "pin-pulse", r: 9, stroke: color }));
      pin.appendChild(svgEl("circle", {
        class: `pin-ring${isOffline ? " pin-offline" : ""}`, r: 12, stroke: color,
      }));
      pin.appendChild(svgEl("circle", {
        class: "pin-core", r: 6, fill: isOffline ? "#2a3532" : color,
      }));

      // Smart label placement to ensure labels never escape viewport boundaries
      const lblAttrs = getSmartLabelAttrs(v.renderX, v.renderY);
      const label = svgEl("text", {
        class: "pin-label",
        x: lblAttrs.xOffset,
        y: lblAttrs.yOffset,
        "text-anchor": lblAttrs.textAnchor,
        "dominant-baseline": lblAttrs.dominantBaseline,
      });
      label.textContent = v.victim_id;
      pin.appendChild(label);

      pin.addEventListener("click", () => selectVictim(v.victim_id));
      pin.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") selectVictim(v.victim_id);
      });

      pinsLayer.appendChild(pin);
    }

    svg.appendChild(pinsLayer);

    // Tracked team-member markers + path to assigned victim
    const validMembers = state.teamMembers.filter(m => m.status !== "hold" && m.location);
    const dispersedMembers = disperseMarkers(validMembers, 24);

    for (const m of dispersedMembers) {
      if (m.assigned_victim_id) {
        const targetVictim = dispersedVictims.find(v => v.victim_id === m.assigned_victim_id);
        if (targetVictim) {
          svg.appendChild(svgEl("line", {
            class: "team-path",
            x1: m.renderX, y1: m.renderY, x2: targetVictim.renderX, y2: targetVictim.renderY,
          }));
        }
      }

      const teamGroup = svgEl("g", { transform: `translate(${m.renderX}, ${m.renderY})` });
      teamGroup.appendChild(svgEl("path", {
        class: "team-marker-body",
        d: "M 0 -9 L 8 7 L -8 7 Z",
      }));

      const teamLblAttrs = getSmartLabelAttrs(m.renderX, m.renderY);
      const teamLabel = svgEl("text", {
        class: "team-marker-label",
        x: teamLblAttrs.xOffset,
        y: teamLblAttrs.yOffset,
        "text-anchor": teamLblAttrs.textAnchor,
        "dominant-baseline": teamLblAttrs.dominantBaseline,
      });
      teamLabel.textContent = m.callsign || m.member_id;
      teamGroup.appendChild(teamLabel);
      svg.appendChild(teamGroup);
    }

    renderMapLegend();
  }

  // Debounced window resize handler for responsive map re-rendering
  let resizeDebounce = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeDebounce);
    resizeDebounce = setTimeout(() => {
      if (state.victims.length) renderMap();
    }, 150);
  });

  function renderMapLegend() {
    el.mapLegend.innerHTML = "";
    for (const [cls, color] of Object.entries(TRIAGE_COLORS)) {
      const item = document.createElement("span");
      item.className = "legend-item";
      const swatch = document.createElement("span");
      swatch.className = "legend-swatch";
      swatch.style.background = color;
      item.append(swatch, document.createTextNode(`${TRIAGE_EMOJI[cls] || ""} ${cls.replace(/_/g, " ")}`));
      el.mapLegend.appendChild(item);
    }
  }

  function selectVictim(victimId) {
    state.selectedVictimId = victimId;
    renderMap();
    renderReadout(getSelectedVictim());
    highlightQueueSelection();
  }

  function getSelectedVictim() {
    return state.victims.find(v => v.victim_id === state.selectedVictimId) || null;
  }

  // ------------------------------------------------------------------ //
  // OLED readout panel
  // ------------------------------------------------------------------ //

  function renderReadout(victim) {
    if (!victim) {
      el.readoutVictimTag.textContent = "— NO TARGET SELECTED —";
      el.oledContent.innerHTML = '<p class="oled-placeholder">SELECT A VICTIM FROM THE MAP OR QUEUE</p>';
      return;
    }

    const q = state.queue.find(item => item.victim_id === victim.victim_id);
    const triageClass = q ? q.triage_class : "NO_VITAL_SIGNS";
    const color = TRIAGE_COLORS[triageClass] || TRIAGE_COLORS.NO_VITAL_SIGNS;

    el.readoutVictimTag.textContent = `${victim.victim_id} · ${TRIAGE_LABELS[triageClass] || triageClass}`;

    if (!victim.sensor_node_online) {
      el.oledContent.innerHTML = `
        <div class="oled-topline">
          <span class="oled-id">${victim.victim_id}</span>
        </div>
        <p class="oled-offline">▓▓▓ NODE OFFLINE — NO CARRIER ▓▓▓</p>`;
      return;
    }

    const confidencePct = q ? q.confidence_pct : 0;
    const sps = q ? q.sps : 0;
    const hazardMult = q ? q.hazard_multiplier : 1;
    const tapping = q ? q.tapping_detected : false;
    const notes = q ? q.notes : "";

    const lat = victim.location.latitude, lon = victim.location.longitude;
    const gpsStr = (lat != null && lon != null) ? `${lat.toFixed(5)}, ${lon.toFixed(5)}` : "—";

    let html = "";
    html += `
      <div class="oled-topline">
        <span class="oled-id">👤 ${victim.victim_id}</span>
        <span class="oled-class" style="color:${color}">${TRIAGE_EMOJI[triageClass] || ""} ${triageClass.replace(/_/g, " ")}</span>
      </div>

      <span class="oled-big-label">📊 SURVIVAL CONFIDENCE SCORE</span>
      <div class="oled-big">
        <span class="oled-big-num">${confidencePct.toFixed(1)}</span>
        <span class="oled-big-unit">%</span>
      </div>

      <div class="oled-stat-row">
        <div class="oled-stat">
          <span class="oled-stat-label">🚨 SPS</span>
          <span class="oled-stat-value">${sps.toFixed(1)}</span>
        </div>
        <div class="oled-stat">
          <span class="oled-stat-label">HAZARD ×</span>
          <span class="oled-stat-value">${hazardMult.toFixed(2)}</span>
        </div>
        <div class="oled-stat">
          <span class="oled-stat-label">ALT</span>
          <span class="oled-stat-value">${victim.location.altitude_m != null ? Math.round(victim.location.altitude_m) : "—"}<small style="font-size:9px">m</small></span>
        </div>
      </div>

      <div class="oled-section-label">📍 GPS LOCATION</div>
      <p class="oled-gps">${gpsStr}</p>

      <div class="oled-section-label">🛰️ SENSOR STATUS · CHANNELS</div>
    `;

    for (const key of SENSOR_ORDER) {
      const reading = victim.sensors[key];
      const meta = SENSOR_META[key];
      if (!reading) {
        html += `
          <div class="sensor-row is-stale">
            <span class="sensor-name">${meta.label}</span>
            <div class="sensor-bar-track"><div class="sensor-bar-fill" style="width:0%"></div></div>
            <span class="sensor-value">NO DATA</span>
          </div>`;
        continue;
      }
      const pct = Math.max(0, Math.min(100, ((reading.value - meta.min) / (meta.max - meta.min)) * 100));
      const stale = reading.noisy;
      html += `
        <div class="sensor-row${stale ? " is-stale" : ""}">
          <span class="sensor-name">${meta.label}</span>
          <div class="sensor-bar-track"><div class="sensor-bar-fill" style="width:${pct}%"></div></div>
          <span class="sensor-value">${formatSensorValue(reading.value, meta)}${meta.unit ? " " + meta.unit : ""}</span>
        </div>`;
    }

    html += `
      <div class="oled-flags">
        <span class="oled-flag${tapping ? " is-active" : ""}">TAPPING${tapping ? " ● DETECTED" : ""}</span>
        <span class="oled-flag is-active">ONLINE</span>
      </div>

      <p class="oled-notes">${escapeHtml(notes || "—")}</p>
      <p class="oled-timestamp">LAST SENSOR UPDATE ${formatTime(latestSensorTimestamp(victim)) || "—"}</p>
    `;

    el.oledContent.innerHTML = html;
  }

  function latestSensorTimestamp(victim) {
    let latest = null;
    for (const key of SENSOR_ORDER) {
      const reading = victim.sensors[key];
      if (reading && reading.timestamp && (!latest || reading.timestamp > latest)) {
        latest = reading.timestamp;
      }
    }
    return latest;
  }

  function formatSensorValue(v, meta) {
    if (meta.max <= 1) return v.toFixed(2);
    return v.toFixed(1);
  }

  function formatTime(iso) {
    if (!iso) return null;
    try {
      return new Date(iso).toLocaleTimeString([], { hour12: false });
    } catch {
      return null;
    }
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  // ------------------------------------------------------------------ //
  // Priority queue panel
  // ------------------------------------------------------------------ //

  function renderQueue() {
    el.queueCount.textContent = `${state.queue.length} tracked`;

    if (state.queue.length === 0) {
      el.queueList.innerHTML = '<p class="empty-note">Queue will populate once the scenario starts.</p>';
      return;
    }

    el.queueList.innerHTML = "";
    for (const r of state.queue) {
      const v = state.victims.find(x => x.victim_id === r.victim_id);
      const battPct = v ? v.battery_pct : null;
      const battClass = battPct != null && battPct < 25 ? "batt-low" : battPct != null && battPct < 50 ? "batt-mid" : "batt-ok";
      const chargingIcon = v && v.charging ? '<span class="queue-charging" title="Solar charging">⚡</span>' : "";
      const battBadge = battPct != null
        ? `<span class="queue-battery ${battClass}">🔋 ${battPct.toFixed(0)}%${chargingIcon}</span>`
        : "";

      const flowMs = v && v.sensors && v.sensors.water_flow ? v.sensors.water_flow.value : null;
      const flowBadge = flowMs != null && flowMs > 0.3
        ? `<span class="queue-flow">🌊 ${flowMs.toFixed(1)} m/s</span>`
        : "";

      const row = document.createElement("div");
      row.className = `queue-row${r.victim_id === state.selectedVictimId ? " is-selected" : ""}`;
      row.dataset.victimId = r.victim_id;
      row.tabIndex = 0;
      row.setAttribute("role", "button");

      row.innerHTML = `
        <span class="queue-rank">${r.rank}</span>
        <div class="queue-main">
          <div class="queue-id-line">
            <span class="queue-victim-id">${r.victim_id}</span>
            <span class="queue-class-badge badge-${r.triage_class}">${TRIAGE_EMOJI[r.triage_class] || ""} ${r.triage_class.replace(/_/g, " ")}</span>
          </div>
          <div class="queue-sub">${r.confidence_pct.toFixed(1)}% conf · hz×${r.hazard_multiplier.toFixed(2)}${battBadge}${flowBadge}${r.tapping_detected ? ' · <span class="queue-tap">TAP</span>' : ""}</div>
        </div>
        <div class="queue-sps">
          <span class="queue-sps-value">${r.sps.toFixed(0)}</span>
          <span class="queue-sps-label">🚨 SPS</span>
        </div>
      `;

      row.addEventListener("click", () => selectVictim(r.victim_id));
      row.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") selectVictim(r.victim_id);
      });

      el.queueList.appendChild(row);
    }
  }

  function highlightQueueSelection() {
    for (const row of el.queueList.querySelectorAll(".queue-row")) {
      row.classList.toggle("is-selected", row.dataset.victimId === state.selectedVictimId);
    }
  }

  // ------------------------------------------------------------------ //
  // Rescue teams panel
  // ------------------------------------------------------------------ //

  async function pollTeamMembers() {
    try {
      const res = await apiGet("/rescue-team/members-status");
      state.teamMembers = res.members || [];
      renderTeamMembers(state.teamMembers);
      renderStatCards();
    } catch (e) {
      // scenario not running - leave last-known state
    }
  }

  function renderTeamMembers(members) {
    // Step 27: container id verified against index.html — reuses the
    // existing "teamsBody" rescue-team panel (not a "rescueTeamStrip" id).
    if (!members.length) {
      el.teamsBody.innerHTML = '<p class="empty-note">No rescue team roster loaded — resize via Admin.</p>';
      return;
    }

    const visible = members.filter(m => m.status !== "hold");
    if (!visible.length) {
      el.teamsBody.innerHTML = '<p class="empty-note">All members on HOLD — awaiting CMD leader assignment.</p>';
      return;
    }

    el.teamsBody.innerHTML = visible
      .map(m => `
        <div class="team-member-card team-member-${m.status}">
          <span class="tm-callsign">${escapeHtml(m.callsign)}</span>
          <span class="tm-status">${m.status.toUpperCase()}${m.assigned_victim_id ? " → " + escapeHtml(m.assigned_victim_id) : ""}</span>
        </div>`)
      .join("");
  }

  // Step 28: dashboard stat-card row. Reads only from already-polled state
  // (state.victims / state.queue / state.teamMembers) — no extra API calls.
  function renderStatCards() {
    if (!el.statScenarioCount) return; // guard in case markup isn't present on this page

    // Available Scenarios
    el.statScenarioCount.textContent = state.availableScenarioCount;
    el.statScenarioSub.textContent = state.victims.length
      ? `current: ${el.scenarioSelect.selectedOptions[0]?.textContent || "—"}`
      : "no scenario running";

    // Victims Detected + High Priority
    el.statVictimCount.textContent = state.victims.length;
    const highCount = state.queue.filter(r => r.triage_class === "HIGH").length;
    el.statVictimSub.textContent = `High Priority: ${highCount}`;

    // Rescue Teams (unique team_id count) + tracked member count.
    // NOTE: state.teamMembers is the TRACKED sample (capped at
    // TRACKED_MEMBER_SAMPLE_SIZE per team on the backend, currently 8),
    // not the full admin-set roster count — label says "tracked".
    const uniqueTeams = new Set(state.teamMembers.map(m => m.team_id));
    el.statTeamCount.textContent = uniqueTeams.size;
    el.statTeamSub.textContent = `Tracked members: ${state.teamMembers.length}`;

    // Rescues Completed — count of tracked members who reached ARRIVED
    const arrivedCount = state.teamMembers.filter(m => m.status === "arrived").length;
    const enRouteCount = state.teamMembers.filter(m => m.status === "en_route").length;
    el.statRescuedCount.textContent = arrivedCount;
    el.statRescuedSub.textContent = `en route: ${enRouteCount}`;
  }

  // ------------------------------------------------------------------ //
  // Polling loop
  // ------------------------------------------------------------------ //

  async function checkHealth() {
    try {
      await apiGet("/health");
      state.connected = true;
      setConnState("online", "🛰️ LINK OK");
      return true;
    } catch (err) {
      state.connected = false;
      setConnState("error", "🛰️ LINK DOWN");
      return false;
    }
  }

  async function pollMemberArrivals() {
    try {
      const url = state.lastArrivalCheckTs
        ? `/rescue-team/member-arrivals?since=${encodeURIComponent(state.lastArrivalCheckTs)}`
        : `/rescue-team/member-arrivals`;
      const res = await apiGet(url);
      const arrivals = res.arrivals || [];
      for (const a of arrivals) {
        pushAlert("success", `✅ ${a.callsign} reached ${a.victim_id}!`);
      }
      if (arrivals.length) {
        state.lastArrivalCheckTs = arrivals[arrivals.length - 1].arrived_at;
      } else if (!state.lastArrivalCheckTs) {
        // first successful poll with nothing yet - set cursor to "now" so we
        // don't replay old arrivals from before the dashboard was opened
        state.lastArrivalCheckTs = new Date().toISOString();
      }
    } catch (e) {
      // scenario not running yet, or transient network issue - skip this cycle
    }
  }

  async function pollCycle() {
    if (state.polling) return; // avoid overlapping ticks if a request is slow
    state.polling = true;
    const startedAt = performance.now();

    try {
      const victimsRes = await apiGet("/victims");
      state.victims = victimsRes.victims;
      updateSiteOrigin(victimsRes.scenario);
      el.scenarioCycle.textContent = `cycle ${victimsRes.scenario.cycle}`;
      el.scenarioClock.textContent = new Date().toLocaleTimeString([], { hour12: false });

      const queueRes = await apiGet("/queue");
      state.queue = queueRes.queue;

      try {
        const rain = await apiGet("/rain");
        if (rain && rain.rainfall_mm_hr != null) {
          el.scenarioRain.hidden = false;
          el.scenarioRain.textContent = `🌧️ ${rain.rainfall_mm_hr.toFixed(1)} mm/hr`;
        }
      } catch (rainErr) {
        // non-fatal — e.g. dry scenario or transient error, just leave it hidden
      }

      try {
        const soil = await apiGet("/soil");
        if (soil && soil.soil_moisture_pct != null) {
          el.scenarioSoil.hidden = false;
          const risky = soil.soil_moisture_pct >= 60;
          el.scenarioSoil.classList.toggle("soil-risk", risky);
          el.scenarioSoil.textContent = `🪨 ${soil.soil_moisture_pct.toFixed(0)}% saturated`;
        }
      } catch (soilErr) {
        // non-fatal — e.g. scenario without a soil probe network, leave it hidden
      }

      try {
        const seismic = await apiGet("/seismic");
        if (seismic) {
          if (el.scenarioSeismic) {
            el.scenarioSeismic.hidden = false;
            el.scenarioSeismic.classList.toggle("seismic-alert", !!seismic.aftershock_active);
            el.scenarioSeismic.textContent = `📈 ${seismic.vibration_mm_s.toFixed(1)} mm/s PGV${seismic.aftershock_active ? " ⚠️ AFTERSHOCK" : ""}`;
          }
          const wasActive = state.prevAftershockActive;
          if (seismic.aftershock_active && !wasActive) {
            pushAlert("critical", `⚠️ Aftershock detected — ${seismic.vibration_mm_s.toFixed(1)} mm/s PGV. Structural risk elevated.`);
            playAlertTone("HIGH");   // reuse Step 3's tone system
          }
          state.prevAftershockActive = seismic.aftershock_active;
        }
      } catch (seismicErr) {
        // non-fatal — e.g. scenario without a seismic sensor, just skip
      }

      try {
        const tilt = await apiGet("/tilt");
        if (tilt && tilt.tilt_deg != null) {
          if (el.scenarioTilt) {
            el.scenarioTilt.hidden = false;
            const danger = tilt.tilt_deg >= 5.0;
            el.scenarioTilt.classList.toggle("tilt-danger", danger);
            el.scenarioTilt.textContent = `📐 ${tilt.tilt_deg.toFixed(1)}°`;
          }

          if (tilt.shift_detected) {
            pushAlert("critical", `Ground/structure shift detected — now ${tilt.tilt_deg.toFixed(1)}°. Slope/structure has moved — reassess access routes before proceeding.`);
            playAlertTone("HIGH");
          }
        }
      } catch (tiltErr) {
        // non-fatal — e.g. scenario without an inclinometer, just skip
      }

      try {
        const environment = await apiGet("/environment");
        if (environment && environment.ambient_temp_c != null && environment.humidity_pct != null) {
          if (el.scenarioEnv) {
            el.scenarioEnv.hidden = false;
            const cold = environment.ambient_temp_c <= 5.0;
            const heatHumid = environment.ambient_temp_c >= 32.0 && environment.humidity_pct >= 70.0;
            el.scenarioEnv.classList.toggle("env-risk", cold || heatHumid);
            el.scenarioEnv.textContent = `🌡️ ${environment.ambient_temp_c.toFixed(1)}°C · ${environment.humidity_pct.toFixed(0)}% RH`;
          }
        }
      } catch (envErr) {
        // non-fatal — e.g. scenario without a weather station, just skip
      }

      await pollMemberArrivals();

      for (const record of queueRes.new_alerts || []) {
        pushNetworkAlert(record);
      }

      await pollTeamMembers();

      state.connected = true;
      setConnState("online", "🛰️ LINK OK");

      diffAndAlert([]);

      if (!state.selectedVictimId && state.queue.length > 0) {
        state.selectedVictimId = state.queue[0].victim_id;
      }

      renderMap();
      renderReadout(getSelectedVictim());
      renderQueue();
      renderTeamMembers(state.teamMembers);
      renderStatCards();

      setStatusMessage(`Synced — cycle ${victimsRes.scenario.cycle}, ${state.victims.length} nodes.`);
    } catch (err) {
      state.connected = false;
      setConnState("error", "🛰️ LINK DOWN");
      setStatusMessage(`Poll error: ${err.message}`);
      if (err.status === 409) {
        // scenario not running server-side (e.g. backend restarted) — stop polling
        state.scenarioRunning = false;
        el.scenarioState.textContent = "NOT STARTED";
        stopPolling();
        pushAlert("warn", "Backend reports scenario is not running. Press Start Scenario.");
      } else {
        pushAlert("critical", `Poll failed: ${err.message}`);
      }
    } finally {
      const elapsed = Math.round(performance.now() - startedAt);
      el.statusPoll.textContent = `poll: ${elapsed}ms`;
      state.polling = false;
    }
  }

  function diffAndAlert(arrivals) {
    // triage class transitions + offline nodes
    for (const v of state.victims) {
      const q = state.queue.find(item => item.victim_id === v.victim_id);
      const currentClass = q ? q.triage_class : null;
      const prevClass = state.prevTriageByVictim[v.victim_id];

      if (currentClass && prevClass && currentClass !== prevClass) {
        const level = currentClass === "HIGH" ? "critical" : currentClass === "SAFE" ? "success" : "warn";
        pushAlert(level, `${v.victim_id} reclassified ${prevClass.replace(/_/g, " ")} → ${currentClass.replace(/_/g, " ")}.`);
        playAlertTone(currentClass);
      }
      if (currentClass) state.prevTriageByVictim[v.victim_id] = currentClass;

      if (q && q.tapping_detected && !state.prevOnlineByVictim[`tap:${v.victim_id}`]) {
        pushAlert("warn", `${v.victim_id} — deliberate tapping/calling detected.`);
      }
      state.prevOnlineByVictim[`tap:${v.victim_id}`] = q ? q.tapping_detected : false;

      if (v.kit_disturbed && !state.prevOnlineByVictim[`kit:${v.victim_id}`]) {
        pushAlert("warn", `${v.victim_id} — kit IMU disturbed (tilt/vibration spike detected).`);
      }
      state.prevOnlineByVictim[`kit:${v.victim_id}`] = v.kit_disturbed || false;

      const prevOnline = state.prevOnlineByVictim[v.victim_id];
      if (prevOnline === true && v.sensor_node_online === false) {
        pushAlert("critical", `${v.victim_id} sensor node lost carrier — OFFLINE.`);
      }
      state.prevOnlineByVictim[v.victim_id] = v.sensor_node_online;

      const battPct = v.battery_pct;
      const wasLow = state.prevLowBatteryByVictim[v.victim_id];
      const isLow = battPct != null && battPct < 25;
      if (isLow && !wasLow) {
        pushAlert("warn", `${v.victim_id} sensor node battery critical — ${battPct.toFixed(0)}%.`);
        playAlertTone("LOW");
      }
      state.prevLowBatteryByVictim[v.victim_id] = isLow;
    }

    // team dispatch assignments
    for (const t of state.teams) {
      if (t.assigned_victim_id && t.availability === "en_route") {
        const key = `${t.team_id}:${t.assigned_victim_id}`;
        if (!state.dispatchedLogged.has(key)) {
          state.dispatchedLogged.add(key);
          pushAlert("info", `${t.team_name} dispatched to ${t.assigned_victim_id} — ETA ${t.eta_minutes?.toFixed(1) ?? "?"} min.`);
        }
      }
    }

    // ground dispatch agent arrivals
    for (const a of arrivals) {
      const key = `${a.victim_id}:${a.order}`;
      if (!state.reachedLogged.has(key)) {
        state.reachedLogged.add(key);
        pushAlert("success", `Ground team reached ${a.victim_id} (arrival #${a.order}, ${a.travel_seconds.toFixed(0)}s travel).`);
      }
    }
  }

  function startPolling() {
    stopPolling();
    pollCycle();
    state.pollTimer = setInterval(pollCycle, POLL_MS);
  }

  function stopPolling() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  }

  // ------------------------------------------------------------------ //
  // Boot
  // ------------------------------------------------------------------ //

  let apiControlBound = false;

  async function boot() {
    setAudioMuted(audioMuted);
    renderMap();
    renderMapLegend();

    if (el.apiBaseInput) {
      el.apiBaseInput.value = RidgeWatchConfig.getApiBase();
    }
    if (!apiControlBound) {
      apiControlBound = true;
      if (el.apiBaseSaveBtn) {
        el.apiBaseSaveBtn.addEventListener("click", () => {
          const newUrl = el.apiBaseInput ? el.apiBaseInput.value.trim() : "";
          RidgeWatchConfig.setApiBase(newUrl);
          if (el.apiBaseInput) el.apiBaseInput.value = RidgeWatchConfig.getApiBase();
          el.apiBaseSaveBtn.textContent = "Saved ✓";
          setTimeout(() => {
            if (el.apiBaseSaveBtn) el.apiBaseSaveBtn.textContent = "Save";
          }, 1500);
          boot();
        });
      }
      if (el.apiBaseInput) {
        el.apiBaseInput.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            el.apiBaseSaveBtn?.click();
          }
        });
      }
    }

    const ok = await checkHealth();
    if (!ok) {
      setStatusMessage("Cannot reach backend — check the API endpoint (top right).");
      pushAlert("critical", `Could not reach ${state.apiBase}. Confirm the backend is running (uvicorn backend.api:app --reload --port 8000).`);
      return;
    }
    await loadScenarioList();

    // Step 28: check whether a scenario is ALREADY running server-side
    // (e.g. started earlier from Admin/Commander, or a previous browser tab)
    // instead of always defaulting to "NOT STARTED" until the button is pressed.
    try {
      const victimsRes = await apiGet("/victims");
      // reached here without a 409 - a scenario is genuinely live
      state.scenarioRunning = true;
      el.scenarioState.textContent = "RUNNING";
      setStatusMessage(`Reconnected to an already-running scenario — cycle ${victimsRes.scenario.cycle}, ${victimsRes.victims.length} nodes.`);
      pushAlert("success", "Reconnected to an in-progress scenario already running on the backend.");
      startPolling();
    } catch (err) {
      // 409 (not running) is the expected/normal idle case - stay on "Press Start Scenario"
      if (err.status !== 409) {
        pushAlert("warn", `Could not check for an existing scenario: ${err.message}`);
      }
      setStatusMessage("Connected to backend. Press Start Scenario to begin.");
    }

    window.addEventListener("focus", () => {
      if (!state.scenarioRunning) loadScenarioList();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && !state.scenarioRunning) {
        loadScenarioList();
      }
    });
  }

  boot();
})();
