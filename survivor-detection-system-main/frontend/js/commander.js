/* ==========================================================================
   RIDGEWATCH commander console client
   Direct unauthenticated access to Commander Console & Live Operations.
   Deep Map Exploration Engine, World-to-Screen Projection, and Live Telemetry.
   ========================================================================== */

(() => {
  "use strict";

  // ------------------------------------------------------------------ //
  // Config & Constants
  // ------------------------------------------------------------------ //

  const POLL_MS = 4000;
  const NEAREST_SUGGESTION_COUNT = 3;

  const apiBase = RidgeWatchConfig.getApiBase();

  const TRIAGE_COLORS = {
    HIGH: "#ff4438",
    MEDIUM: "#ff9f0a",
    LOW: "#ffd60a",
    NO_VITAL_SIGNS: "#6e7a7d",
    SAFE: "#34d399",
  };

  // Default origin; poll() keeps this synchronized with the active scenario.
  let SITE_ORIGIN = { latitude: 32.3739, longitude: 77.2491, altitude_m: 3950 };
  const METERS_PER_DEG_LAT = 111320;
  const MAP_SIZE = 600;          // SVG viewBox units: 0 0 600 600
  const MAP_METERS_SPAN = 180;   // Base meters shown edge-to-edge at zoom=1.0

  // ------------------------------------------------------------------ //
  // Map State & Coordinates
  // ------------------------------------------------------------------ //

  const mapState = {
    isDeepMode: false,
    zoom: 1.0,
    panX: 0,
    panY: 0,
    minZoom: 0.15,
    maxZoom: 15.0,
    isDragging: false,
    dragStart: { x: 0, y: 0 },
    panStart: { x: 0, y: 0 },
    hasMovedDuringDrag: false,
    selectedEntityId: null,
    lastVictims: [],
    lastMembers: [],
    lastJobs: [],
    scenarioMeta: null,
    touchStartDist: 0,
    touchStartZoom: 1.0,
    lastValidAlpha1Location: null,
  };

  // ------------------------------------------------------------------ //
  // API helpers & Coordinate Validation
  // ------------------------------------------------------------------ //

  function isValidGpsCoordinate(lat, lon) {
    if (lat == null || lon == null) return false;
    const nLat = Number(lat);
    const nLon = Number(lon);
    if (!Number.isFinite(nLat) || !Number.isFinite(nLon)) return false;
    if (nLat < -90 || nLat > 90) return false;
    if (nLon < -180 || nLon > 180) return false;
    return true;
  }

  class ApiError extends Error {
    constructor(status, detail) {
      super(detail || `HTTP ${status}`);
      this.status = status;
    }
  }

  async function apiPost(path, payload) {
    const res = await fetch(apiBase + path, {
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

  function svgEl(tag, attrs) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    return node;
  }

  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ------------------------------------------------------------------ //
  // Map Projection & World Coordinate Helpers
  // ------------------------------------------------------------------ //

  const MAP_SAFE_MARGIN = 22; // Safe pixel margin from viewport edges in overview mode

  function clamp(val, min, max) {
    return Math.min(Math.max(val, min), max);
  }

  function metersPerDegLon(latDeg) {
    return METERS_PER_DEG_LAT * Math.cos((latDeg * Math.PI) / 180);
  }

  function toLocalMeters(loc) {
    if (!loc || loc.latitude == null || loc.longitude == null) return { east: 0, north: 0 };
    const dLat = loc.latitude - SITE_ORIGIN.latitude;
    const dLon = loc.longitude - SITE_ORIGIN.longitude;
    return {
      east: dLon * metersPerDegLon(SITE_ORIGIN.latitude),
      north: dLat * METERS_PER_DEG_LAT,
    };
  }

  function worldMetersToSvgBase(m) {
    const scale = MAP_SIZE / MAP_METERS_SPAN; // 600 / 180 = 3.3333 px / meter
    return {
      x: MAP_SIZE / 2 + m.east * scale,
      y: MAP_SIZE / 2 - m.north * scale,
    };
  }

  function locToWorldSvg(loc) {
    return worldMetersToSvgBase(toLocalMeters(loc));
  }

  function worldToScreen(worldPt) {
    return {
      x: 300 + (worldPt.x - 300) * mapState.zoom + mapState.panX,
      y: 300 + (worldPt.y - 300) * mapState.zoom + mapState.panY,
    };
  }

  function screenToWorld(screenX, screenY) {
    return {
      x: 300 + (screenX - 300 - mapState.panX) / mapState.zoom,
      y: 300 + (screenY - 300 - mapState.panY) / mapState.zoom,
    };
  }

  const mapLayers = {
    victims: true,
    members: true,
    jobs: true,
    base: true,
  };

  function isLocalEntity(loc) {
    if (!loc || loc.latitude == null || loc.longitude == null) return false;
    const m = toLocalMeters(loc);
    // 3500m operational perimeter around active incident site origin
    return Math.hypot(m.east, m.north) <= 3500;
  }

  // Disperse markers that overlap closely in world coordinates or overview screen
  function disperseWorldMarkers(items, radiusThreshold = 22) {
    const minX = MAP_SAFE_MARGIN, maxX = MAP_SIZE - MAP_SAFE_MARGIN;
    const minY = MAP_SAFE_MARGIN, maxY = MAP_SIZE - MAP_SAFE_MARGIN;

    // Filter out items that have no coordinates or are outside the local mission theater
    const localItems = items.filter(item => {
      const loc = item.location || { latitude: item.latitude, longitude: item.longitude };
      return loc && loc.latitude != null && loc.longitude != null && isLocalEntity(loc);
    });

    const markers = localItems.map(item => {
      const loc = item.location || { latitude: item.latitude, longitude: item.longitude };
      const raw = locToWorldSvg(loc);
      // In overview mode (zoom=1, pan=0), clamp raw coordinates to keep inside map boundary
      const clampedX = mapState.isDeepMode ? raw.x : clamp(raw.x, minX, maxX);
      const clampedY = mapState.isDeepMode ? raw.y : clamp(raw.y, minY, maxY);
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
          const nx = mapState.isDeepMode ? (avgX + spreadRadius * Math.cos(angle)) : clamp(avgX + spreadRadius * Math.cos(angle), minX, maxX);
          const ny = mapState.isDeepMode ? (avgY + spreadRadius * Math.sin(angle)) : clamp(avgY + spreadRadius * Math.sin(angle), minY, maxY);
          markers[idx].renderX = nx;
          markers[idx].renderY = ny;
          if (Math.hypot(nx - markers[idx].rawX, ny - markers[idx].rawY) > 4) {
            markers[idx].isOffset = true;
          }
        });
      }
    }

    return markers;
  }

  function getSmartLabelAttrs(renderX, renderY, textStr = "", placedBoxes = null) {
    const screen = mapState.isDeepMode ? worldToScreen({ x: renderX, y: renderY }) : { x: renderX, y: renderY };
    const flipX = screen.x > 380 || screen.x > (MAP_SIZE - 110);
    let xOffset = flipX ? -14 : 14;
    let textAnchor = flipX ? "end" : "start";
    let yOffset = 3;
    let dominantBaseline = "middle";

    if (screen.y < 24) {
      yOffset = 16;
      dominantBaseline = "hanging";
    } else if (screen.y > MAP_SIZE - 24) {
      yOffset = -12;
      dominantBaseline = "auto";
    }

    if (placedBoxes && Array.isArray(placedBoxes)) {
      const textLen = (textStr || "").length;
      const labelW = Math.min(textLen * 6.5 + 8, 150);

      const candidates = [
        {
          xOffset: flipX ? -14 : 14,
          yOffset: yOffset,
          textAnchor: textAnchor,
          dominantBaseline: dominantBaseline,
          box: {
            x1: flipX ? screen.x - 14 - labelW : screen.x + 14,
            y1: screen.y - 7,
            x2: flipX ? screen.x - 14 : screen.x + 14 + labelW,
            y2: screen.y + 7,
          },
        },
        {
          xOffset: flipX ? 14 : -14,
          yOffset: yOffset,
          textAnchor: flipX ? "start" : "end",
          dominantBaseline: dominantBaseline,
          box: {
            x1: flipX ? screen.x + 14 : screen.x - 14 - labelW,
            y1: screen.y - 7,
            x2: flipX ? screen.x + 14 + labelW : screen.x - 14,
            y2: screen.y + 7,
          },
        },
        {
          xOffset: 0,
          yOffset: -14,
          textAnchor: "middle",
          dominantBaseline: "auto",
          box: {
            x1: screen.x - labelW / 2,
            y1: screen.y - 20,
            x2: screen.x + labelW / 2,
            y2: screen.y - 6,
          },
        },
        {
          xOffset: 0,
          yOffset: 16,
          textAnchor: "middle",
          dominantBaseline: "hanging",
          box: {
            x1: screen.x - labelW / 2,
            y1: screen.y + 6,
            x2: screen.x + labelW / 2,
            y2: screen.y + 20,
          },
        },
      ];

      let chosen = candidates[0];
      for (const cand of candidates) {
        let collides = false;
        for (const pb of placedBoxes) {
          if (!(cand.box.x2 < pb.x1 || cand.box.x1 > pb.x2 || cand.box.y2 < pb.y1 || cand.box.y1 > pb.y2)) {
            collides = true;
            break;
          }
        }
        if (!collides) {
          chosen = cand;
          break;
        }
      }
      placedBoxes.push(chosen.box);
      return {
        xOffset: chosen.xOffset,
        yOffset: chosen.yOffset,
        textAnchor: chosen.textAnchor,
        dominantBaseline: chosen.dominantBaseline,
      };
    }

    return { xOffset, yOffset, textAnchor, dominantBaseline };
  }

  // ------------------------------------------------------------------ //
  // DOM Elements
  // ------------------------------------------------------------------ //

  let scenarioName = null;
  let lastMembers = [];

  const el = {
    mainView: document.getElementById("cmdMainView"),
    mapWrap: document.getElementById("cmdMapWrap"),
    map: document.getElementById("cmdMap"),
    deepBadge: document.getElementById("cmdDeepBadge"),
    btnZoomIn: document.getElementById("btnCmdZoomIn"),
    btnZoomOut: document.getElementById("btnCmdZoomOut"),
    btnFitAll: document.getElementById("btnCmdFitAll"),
    btnReset: document.getElementById("btnCmdReset"),
    btnExitDeep: document.getElementById("btnCmdExitDeep"),
    coordsText: document.getElementById("cmdCoordsText"),
    zoomText: document.getElementById("cmdZoomText"),
    popover: document.getElementById("cmdMapPopover"),
    popoverTitle: document.getElementById("popoverTitle"),
    popoverBody: document.getElementById("popoverBody"),
    btnPopoverClose: document.getElementById("btnPopoverClose"),
    memberList: document.getElementById("cmdMemberList"),
    suggestPanel: document.getElementById("cmdSuggestPanel"),
    suggestMember: document.getElementById("cmdSuggestMember"),
    suggestList: document.getElementById("cmdSuggestList"),
    assignFormPanel: document.getElementById("cmdAssignFormPanel"),
    formScenario: document.getElementById("cmdFormScenario"),
    formTeam: document.getElementById("cmdFormTeam"),
    formMember: document.getElementById("cmdFormMember"),
    formVictim: document.getElementById("cmdFormVictim"),
    confirmBanner: document.getElementById("cmdConfirmBanner"),
    confirmIcon: document.getElementById("cmdConfirmIcon"),
    confirmText: document.getElementById("cmdConfirmText"),
    formAssignBtn: document.getElementById("cmdFormAssignBtn"),
    formResult: document.getElementById("cmdFormResult"),
    pressureVal: document.getElementById("cmdPressureVal"),
    pressureTrend: document.getElementById("cmdPressureTrend"),
    pressureStatus: document.getElementById("cmdPressureStatus"),
    pressureRate: document.getElementById("cmdPressureRate"),
    pressureModeBadge: document.getElementById("cmdPressureModeBadge"),
    pressureSvg: document.getElementById("cmdPressureSvg"),
    confidenceScore: document.getElementById("cmdConfidenceScore"),
    evidenceList: document.getElementById("cmdEvidenceList"),
  };

  // ------------------------------------------------------------------ //
  // Transform & HUD Application
  // ------------------------------------------------------------------ //

  function clampPan() {
    // Sensible world limits (approx ±3000m span)
    const maxPan = 6000 * mapState.zoom;
    mapState.panX = Math.max(-maxPan, Math.min(maxPan, mapState.panX));
    mapState.panY = Math.max(-maxPan, Math.min(maxPan, mapState.panY));
  }

  function applyTransform() {
    const worldGroup = document.getElementById("cmdMapWorld");
    if (worldGroup) {
      worldGroup.setAttribute(
        "transform",
        `translate(${300 + mapState.panX}, ${300 + mapState.panY}) scale(${mapState.zoom}) translate(-300, -300)`
      );
    }
    updateHudReadouts();
  }

  function updateHudReadouts() {
    if (el.zoomText) {
      const curSpanMeters = Math.round(MAP_METERS_SPAN / mapState.zoom);
      el.zoomText.textContent = `Zoom: ${mapState.zoom.toFixed(1)}x (~${curSpanMeters}m)`;
    }

    if (el.coordsText && SITE_ORIGIN) {
      const centerWorld = screenToWorld(300, 300);
      const dEastMeters = (centerWorld.x - 300) * (MAP_METERS_SPAN / MAP_SIZE);
      const dNorthMeters = -(centerWorld.y - 300) * (MAP_METERS_SPAN / MAP_SIZE);
      const centerLat = SITE_ORIGIN.latitude + (dNorthMeters / METERS_PER_DEG_LAT);
      const centerLon = SITE_ORIGIN.longitude + (dEastMeters / metersPerDegLon(SITE_ORIGIN.latitude));
      el.coordsText.textContent = `Center: ${centerLat.toFixed(4)}°N, ${centerLon.toFixed(4)}°E`;
    }

    // Dynamic scale bar in fixed HUD
    const scaleBarLine = document.getElementById("cmdHudScaleLine");
    const scaleBarLabel = document.getElementById("cmdHudScaleLabel");
    if (scaleBarLine && scaleBarLabel) {
      // 50 base units corresponds to (50 / (600 / 180)) / zoom = 15m / zoom
      const rawMeters = (60 / (MAP_SIZE / MAP_METERS_SPAN)) / mapState.zoom;
      let niceMeters = 50;
      if (rawMeters <= 10) niceMeters = 5;
      else if (rawMeters <= 25) niceMeters = 10;
      else if (rawMeters <= 60) niceMeters = 25;
      else if (rawMeters <= 120) niceMeters = 50;
      else if (rawMeters <= 300) niceMeters = 100;
      else if (rawMeters <= 600) niceMeters = 250;
      else niceMeters = 500;

      const pxLength = (niceMeters * (MAP_SIZE / MAP_METERS_SPAN)) * mapState.zoom;
      scaleBarLine.setAttribute("x2", String(530 - pxLength));
      scaleBarLabel.textContent = `${niceMeters} m`;
      scaleBarLabel.setAttribute("x", String(530 - pxLength / 2));
    }
  }

  function setDeepMode(active) {
    mapState.isDeepMode = !!active;
    if (el.mapWrap) {
      el.mapWrap.classList.toggle("is-deep-mode", mapState.isDeepMode);
    }
    if (el.deepBadge) {
      el.deepBadge.hidden = !mapState.isDeepMode;
    }
    if (el.btnExitDeep) {
      el.btnExitDeep.hidden = !mapState.isDeepMode;
    }
  }

  function zoomAroundPoint(newZoom, screenX, screenY) {
    const clampedZoom = Math.min(Math.max(newZoom, mapState.minZoom), mapState.maxZoom);
    if (Math.abs(clampedZoom - mapState.zoom) < 0.001) return;

    const factor = clampedZoom / mapState.zoom;
    mapState.panX = (screenX - 300) - (screenX - 300 - mapState.panX) * factor;
    mapState.panY = (screenY - 300) - (screenY - 300 - mapState.panY) * factor;
    mapState.zoom = clampedZoom;

    clampPan();
    applyTransform();
  }

  // ------------------------------------------------------------------ //
  // Fit All & Reset Solvers
  // ------------------------------------------------------------------ //

  function fitAllEntities() {
    const points = [{ x: 300, y: 300 }]; // Origin Base Camp

    for (const v of mapState.lastVictims) {
      if (v.location) points.push(locToWorldSvg(v.location));
    }
    for (const m of mapState.lastMembers) {
      if (m.location) points.push(locToWorldSvg(m.location));
    }
    for (const j of mapState.lastJobs) {
      if (j.latitude != null && j.longitude != null) {
        points.push(locToWorldSvg({ latitude: j.latitude, longitude: j.longitude }));
      }
    }

    if (points.length === 0) {
      resetMapView();
      return;
    }

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const p of points) {
      if (p.x < minX) minX = p.x;
      if (p.x > maxX) maxX = p.x;
      if (p.y < minY) minY = p.y;
      if (p.y > maxY) maxY = p.y;
    }

    // Add padding (60 svg units)
    const pad = 60;
    minX -= pad; maxX += pad;
    minY -= pad; maxY += pad;

    const bboxW = Math.max(maxX - minX, 80);
    const bboxH = Math.max(maxY - minY, 80);
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    const fitZoom = Math.min(MAP_SIZE / bboxW, MAP_SIZE / bboxH, 2.5);
    const targetZoom = Math.max(Math.min(fitZoom, mapState.maxZoom), mapState.minZoom);

    mapState.zoom = targetZoom;
    mapState.panX = -(centerX - 300) * targetZoom;
    mapState.panY = -(centerY - 300) * targetZoom;

    clampPan();
    applyTransform();
  }

  function resetMapView() {
    mapState.zoom = 1.0;
    mapState.panX = 0;
    mapState.panY = 0;
    clampPan();
    applyTransform();
  }

  // ------------------------------------------------------------------ //
  // Entity Detail Popover
  // ------------------------------------------------------------------ //

  function showPopover(title, rows) {
    if (!el.popover) return;
    el.popoverTitle.textContent = title;
    el.popoverBody.innerHTML = rows.map(r => `
      <div class="popover-row">
        <span class="popover-lbl">${escapeHtml(r.label)}</span>
        <span class="popover-val" style="${r.style || ''}">${escapeHtml(r.value)}</span>
      </div>
    `).join("");
    el.popover.hidden = false;
  }

  function hidePopover() {
    if (el.popover) el.popover.hidden = true;
    mapState.selectedEntityId = null;
  }

  // ------------------------------------------------------------------ //
  // Map SVG Construction & Rendering
  // ------------------------------------------------------------------ //

  function getSvgPoint(e) {
    const rect = el.map.getBoundingClientRect();
    const svgX = ((e.clientX - rect.left) / rect.width) * MAP_SIZE;
    const svgY = ((e.clientY - rect.top) / rect.height) * MAP_SIZE;
    return { svgX, svgY };
  }

  function initMapSvgStructure() {
    const svg = el.map;
    svg.innerHTML = "";

    // 1. Defs
    const defs = svgEl("defs", {});

    // Fine grid (20px)
    const patFine = svgEl("pattern", { id: "cmdGridFine", width: "20", height: "20", patternUnits: "userSpaceOnUse" });
    patFine.appendChild(svgEl("path", { d: "M 20 0 L 0 0 0 20", fill: "none", stroke: "rgba(148, 163, 184, 0.12)", "stroke-width": "0.75" }));
    defs.appendChild(patFine);

    // Coarse grid (100px)
    const patCoarse = svgEl("pattern", { id: "cmdGridCoarse", width: "100", height: "100", patternUnits: "userSpaceOnUse" });
    patCoarse.appendChild(svgEl("rect", { width: "100", height: "100", fill: "url(#cmdGridFine)" }));
    patCoarse.appendChild(svgEl("path", { d: "M 100 0 L 0 0 0 100", fill: "none", stroke: "rgba(148, 163, 184, 0.28)", "stroke-width": "1.2" }));
    defs.appendChild(patCoarse);

    svg.appendChild(defs);

    // 2. World Group (transformed by pan & zoom)
    const world = svgEl("g", { id: "cmdMapWorld" });

    // 2a. Boundless background & grid
    world.appendChild(svgEl("rect", { x: "-6000", y: "-6000", width: "12000", height: "12000", fill: "#f8fafc" }));
    world.appendChild(svgEl("rect", { x: "-6000", y: "-6000", width: "12000", height: "12000", fill: "url(#cmdGridCoarse)" }));

    // 2b. Terrain distance rings from origin (50m, 100m, 150m, 250m, 500m)
    const ringGroup = svgEl("g", { id: "cmdRingsLayer" });
    const scale = MAP_SIZE / MAP_METERS_SPAN;
    const ringDistances = [25, 50, 75, 100, 150, 250, 500];
    for (const rMeters of ringDistances) {
      const rPx = rMeters * scale;
      ringGroup.appendChild(svgEl("circle", {
        cx: 300, cy: 300, r: rPx,
        fill: "none",
        stroke: "rgba(100, 116, 139, 0.2)",
        "stroke-width": "1",
        "stroke-dasharray": "3 4",
      }));
      const lbl = svgEl("text", {
        x: 300 + rPx + 4, y: 296,
        fill: "rgba(100, 116, 139, 0.6)",
        "font-size": "8.5",
        "font-family": "monospace",
      });
      lbl.textContent = `${rMeters}m`;
      ringGroup.appendChild(lbl);
    }
    world.appendChild(ringGroup);

    // 2c. Coordinate Crosshair Axes
    const axes = svgEl("g", { id: "cmdAxesLayer" });
    axes.appendChild(svgEl("line", { x1: "-5000", y1: "300", x2: "5000", y2: "300", stroke: "rgba(100, 116, 139, 0.35)", "stroke-width": "1", "stroke-dasharray": "4 4" }));
    axes.appendChild(svgEl("line", { x1: "300", y1: "-5000", x2: "300", y2: "5000", stroke: "rgba(100, 116, 139, 0.35)", "stroke-width": "1", "stroke-dasharray": "4 4" }));
    world.appendChild(axes);

    // 2d. Base Origin / Command Apex Marker
    const base = svgEl("g", { id: "cmdBaseMarker", transform: "translate(300, 300)", class: "cmd-base-pin" });
    base.appendChild(svgEl("circle", { r: "18", fill: "rgba(37, 99, 235, 0.12)", stroke: "#2563eb", "stroke-width": "1.2" }));
    base.appendChild(svgEl("path", { d: "M -7 7 L 0 -8 L 7 7 Z", fill: "#2563eb" }));
    const baseLbl = svgEl("text", { x: "12", y: "4", class: "cmd-pin-label", "font-weight": "700" });
    baseLbl.textContent = "COMMAND BASE (0,0)";
    base.appendChild(baseLbl);
    base.addEventListener("click", () => {
      showPopover("Command Post & Base Origin", [
        { label: "Location", value: `${SITE_ORIGIN.latitude.toFixed(4)}°N, ${SITE_ORIGIN.longitude.toFixed(4)}°E` },
        { label: "Altitude", value: `${SITE_ORIGIN.altitude_m || 3950} m` },
        { label: "Status", value: "ACTIVE HEADQUARTERS", style: "color:#22c55e" },
      ]);
    });
    world.appendChild(base);

    // 2e. Dynamic Entity Layers
    world.appendChild(svgEl("g", { id: "cmdPathsLayer" }));
    world.appendChild(svgEl("g", { id: "cmdJobsLayer" }));
    world.appendChild(svgEl("g", { id: "cmdVictimsLayer" }));
    world.appendChild(svgEl("g", { id: "cmdMembersLayer" }));

    svg.appendChild(world);

    // 3. Fixed HUD Elements in SVG (North Arrow & Bottom-Right Scale Bar)
    const hud = svgEl("g", { id: "cmdFixedHud" });

    // Compass Rose (Top-Left under badge)
    const compass = svgEl("g", { transform: "translate(40, 75)" });
    compass.appendChild(svgEl("circle", { r: "14", fill: "rgba(255, 255, 255, 0.85)", stroke: "rgba(148, 163, 184, 0.4)", "stroke-width": "1" }));
    compass.appendChild(svgEl("path", { d: "M 0 -11 L 3.5 0 L 0 -3.5 L -3.5 0 Z", fill: "#ef4444" })); // North arrow red
    compass.appendChild(svgEl("path", { d: "M 0 11 L 3.5 0 L 0 3.5 L -3.5 0 Z", fill: "#64748b" })); // South arrow grey
    const nTxt = svgEl("text", { x: "-3", y: "-13", "font-size": "8", "font-weight": "700", fill: "#ef4444", "font-family": "monospace" });
    nTxt.textContent = "N";
    compass.appendChild(nTxt);
    hud.appendChild(compass);

    // Bottom-Right Scale Bar
    const scaleBar = svgEl("g", { id: "cmdHudScaleGroup", transform: "translate(0, 580)" });
    scaleBar.appendChild(svgEl("line", { id: "cmdHudScaleLine", x1: "530", y1: "0", x2: "450", y2: "0", stroke: "#0f172a", "stroke-width": "2" }));
    scaleBar.appendChild(svgEl("line", { x1: "530", y1: "-4", x2: "530", y2: "4", stroke: "#0f172a", "stroke-width": "1.5" }));
    scaleBar.appendChild(svgEl("line", { id: "cmdHudScaleEndCap", x1: "450", y1: "-4", x2: "450", y2: "4", stroke: "#0f172a", "stroke-width": "1.5" }));
    const sTxt = svgEl("text", { id: "cmdHudScaleLabel", x: "490", y: "-6", "text-anchor": "middle", "font-size": "9", "font-weight": "700", fill: "#0f172a", "font-family": "monospace" });
    sTxt.textContent = "50 m";
    scaleBar.appendChild(sTxt);
    hud.appendChild(scaleBar);

    svg.appendChild(hud);
  }

  function clusterOpsJobs(dispersedJobs, radiusThreshold = 22) {
    const clusters = [];
    const visited = new Set();
    for (let i = 0; i < dispersedJobs.length; i++) {
      if (visited.has(i)) continue;
      const group = [dispersedJobs[i]];
      visited.add(i);
      for (let j = i + 1; j < dispersedJobs.length; j++) {
        if (visited.has(j)) continue;
        const dist = Math.hypot(dispersedJobs[i].renderX - dispersedJobs[j].renderX, dispersedJobs[i].renderY - dispersedJobs[j].renderY);
        if (dist < radiusThreshold) {
          group.push(dispersedJobs[j]);
          visited.add(j);
        }
      }
      clusters.push({
        renderX: dispersedJobs[i].renderX,
        renderY: dispersedJobs[i].renderY,
        clampedX: dispersedJobs[i].clampedX,
        clampedY: dispersedJobs[i].clampedY,
        isOffset: dispersedJobs[i].isOffset,
        items: group,
      });
    }
    return clusters;
  }

  // ------------------------------------------------------------------ //
  // Feature #15: Tactical Road Route Asynchronous Fetch & Render Helpers
  // ------------------------------------------------------------------ //

  async function fetchRouteForMember(member, targetVictim) {
    if (!member || !member.location || !targetVictim || !targetVictim.location) return;
    const cacheKey = `${member.member_id}:${member.location.latitude.toFixed(5)},${member.location.longitude.toFixed(5)}->${targetVictim.location.latitude.toFixed(5)},${targetVictim.location.longitude.toFixed(5)}`;
    mapState.activeRouteKeys = mapState.activeRouteKeys || {};
    if (mapState.activeRouteKeys[member.member_id] === cacheKey) {
      return;
    }
    mapState.activeRouteKeys[member.member_id] = cacheKey;

    try {
      let url = `${apiBase}/api/dispatch/route?start_lat=${member.location.latitude}&start_lon=${member.location.longitude}&target_lat=${targetVictim.location.latitude}&target_lon=${targetVictim.location.longitude}&command_id=${member.active_command_id || ''}&team_id=${member.team_id || ''}&victim_id=${member.assigned_victim_id || ''}`;
      if (member.active_command_id) {
        url = `${apiBase}/api/dispatch/route/${member.active_command_id}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        mapState.cachedRoutes = mapState.cachedRoutes || {};
        mapState.cachedRoutes[member.member_id] = data;
        renderPathsOnly();
      }
    } catch (e) {
      /* transient route query failure -> falls back cleanly to direct line */
    }
  }

  function renderPathsOnly() {
    const pathsLayer = document.getElementById("cmdPathsLayer");
    if (!pathsLayer || !mapState.lastMembers || !mapState.lastVictims) return;
    pathsLayer.innerHTML = "";
    const validMembers = (mapState.lastMembers || []).filter(m => m.location);
    const dispersedMembers = disperseWorldMarkers(validMembers, 24);
    const dispersedVictims = disperseWorldMarkers(mapState.lastVictims || []);

    for (const m of dispersedMembers) {
      if (m.status === "hold" || !m.assigned_victim_id) continue;
      const targetVictim = dispersedVictims.find(v => v.victim_id === m.assigned_victim_id);
      if (targetVictim) {
        const isAlpha1 = m.member_id === "ALPHA-M001" || m.location_source === "PHONE_GPS";
        const isWrongDir = isAlpha1 && m.navigation_status === "WRONG_DIRECTION";
        const isArrived = m.status === "arrived" || m.navigation_status === "ARRIVED";

        const cachedRoute = mapState.cachedRoutes && mapState.cachedRoutes[m.member_id];
        const hasWaypoints = cachedRoute && Array.isArray(cachedRoute.waypoints) && cachedRoute.waypoints.length > 2;

        let pathStroke = isArrived ? "#22c55e" : (isWrongDir ? "#ef4444" : (isAlpha1 ? "#00f0ff" : "#38bdf8"));
        let pathDash = isWrongDir ? "5,3" : (isAlpha1 ? "4,2" : "none");

        if (cachedRoute && cachedRoute.routing_mode === "DETOUR_DYNAMIC" && !isArrived && !isWrongDir) {
          pathStroke = "#f59e0b";
          pathDash = "6,3";
        } else if (cachedRoute && cachedRoute.route_status === "NO_VIABLE_ROAD_ROUTE" && !isArrived) {
          pathStroke = "#ef4444";
          pathDash = "4,4";
        }

        if (hasWaypoints && !isArrived) {
          const pts = [];
          pts.push(`${m.renderX},${m.renderY}`);
          for (let i = 1; i < cachedRoute.waypoints.length - 1; i++) {
            const wp = cachedRoute.waypoints[i];
            const svgPt = locToWorldSvg(wp);
            pts.push(`${svgPt.x},${svgPt.y}`);

            const wpDot = svgEl("circle", {
              cx: svgPt.x,
              cy: svgPt.y,
              r: "2.5",
              fill: cachedRoute.routing_mode === "DETOUR_DYNAMIC" ? "#f59e0b" : "#00f0ff",
              stroke: "#ffffff",
              "stroke-width": "0.75",
              opacity: "0.85",
            });
            pathsLayer.appendChild(wpDot);
          }
          pts.push(`${targetVictim.renderX},${targetVictim.renderY}`);

          const polyline = svgEl("polyline", {
            class: "cmd-path cmd-road-route",
            points: pts.join(" "),
            fill: "none",
            stroke: pathStroke,
            "stroke-width": isAlpha1 ? "2.5" : "2",
            "stroke-dasharray": pathDash,
          });
          pathsLayer.appendChild(polyline);

          if (cachedRoute.avoided_hazards && cachedRoute.avoided_hazards.length > 0) {
            const firstHaz = cachedRoute.avoided_hazards[0];
            const labelGroup = svgEl("g", {
              transform: `translate(${(m.renderX + targetVictim.renderX) / 2}, ${(m.renderY + targetVictim.renderY) / 2 - 12})`,
              class: "cmd-hazard-route-badge",
            });
            const hazPill = svgEl("rect", {
              x: "-50", y: "-8", width: "100", height: "16", rx: "4",
              fill: "rgba(15, 23, 42, 0.85)", stroke: "#f59e0b", "stroke-width": "1"
            });
            const hazTxt = svgEl("text", {
              x: "0", y: "3", "text-anchor": "middle",
              fill: "#fbbf24", "font-size": "8", "font-weight": "700", "font-family": "monospace"
            });
            hazTxt.textContent = `DETOUR: ${firstHaz.hazard_type.replace(/_/g, " ").substring(0, 14)}`;
            labelGroup.appendChild(hazPill);
            labelGroup.appendChild(hazTxt);
            pathsLayer.appendChild(labelGroup);
          }
        } else {
          const path = svgEl("line", {
            class: "cmd-path",
            x1: m.renderX, y1: m.renderY,
            x2: targetVictim.renderX, y2: targetVictim.renderY,
            stroke: pathStroke,
            "stroke-width": isAlpha1 ? "2.5" : "2",
            "stroke-dasharray": pathDash,
          });
          pathsLayer.appendChild(path);
        }
      }
    }
  }

  function renderMap(victims, members, jobs) {
    mapState.lastVictims = victims || [];
    mapState.lastMembers = members || [];
    mapState.lastJobs = jobs || [];

    // Ensure structural groups exist
    if (!document.getElementById("cmdMapWorld")) {
      initMapSvgStructure();
    }

    const pathsLayer = document.getElementById("cmdPathsLayer");
    const jobsLayer = document.getElementById("cmdJobsLayer");
    const victimsLayer = document.getElementById("cmdVictimsLayer");
    const membersLayer = document.getElementById("cmdMembersLayer");

    if (pathsLayer) pathsLayer.innerHTML = "";
    if (jobsLayer) jobsLayer.innerHTML = "";
    if (victimsLayer) victimsLayer.innerHTML = "";
    // membersLayer is NOT cleared to allow smooth in-place CSS transform interpolation!

    const placedBoxes = [];

    // 1. Disperse and clamp all entities to prevent boundary escape and overlapping
    const dispersedVictims = disperseWorldMarkers(mapState.lastVictims);

    // Validate Alpha Member 1 coordinates & handle stale state
    const processedMembers = (mapState.lastMembers || []).map(m => {
      const copy = { ...m };
      if (copy.member_id === "ALPHA-M001") {
        if (copy.location && isValidGpsCoordinate(copy.location.latitude, copy.location.longitude)) {
          mapState.lastValidAlpha1Location = { ...copy.location };
        } else if (mapState.lastValidAlpha1Location) {
          copy.location = { ...mapState.lastValidAlpha1Location };
        } else {
          copy.location = null;
        }

        // Stale evaluation (15-second threshold)
        let isStale = (copy.gps_status === "STALE" || copy.gps_status === "GPS_UNAVAILABLE" || copy.gps_status === "PERMISSION_DENIED");
        if (!isStale && copy.gps_timestamp) {
          try {
            const ts = new Date(copy.gps_timestamp).getTime();
            if (!isNaN(ts) && (Date.now() - ts) > 15000) {
              isStale = true;
              copy.gps_status = "STALE";
            }
          } catch (e) { }
        }
        copy.isStale = isStale;
      }
      return copy;
    });

    const validMembers = processedMembers.filter(m => m.location);
    const dispersedMembers = disperseWorldMarkers(validMembers, 24);
    const validJobs = mapState.lastJobs.filter(j => j.latitude != null && j.longitude != null);
    const dispersedJobs = disperseWorldMarkers(validJobs, 24);
    const jobClusters = clusterOpsJobs(dispersedJobs, 22);

    // Update legend counts
    const countV = document.getElementById("legendCountVictims");
    if (countV) countV.textContent = dispersedVictims.length;
    const countM = document.getElementById("legendCountMembers");
    if (countM) countM.textContent = dispersedMembers.length;
    const countJ = document.getElementById("legendCountJobs");
    if (countJ) countJ.textContent = dispersedJobs.length;

    // Apply layer visibility
    if (victimsLayer) victimsLayer.style.display = mapLayers.victims ? "" : "none";
    if (membersLayer) membersLayer.style.display = mapLayers.members ? "" : "none";
    if (pathsLayer) pathsLayer.style.display = mapLayers.members ? "" : "none";
    if (jobsLayer) jobsLayer.style.display = mapLayers.jobs ? "" : "none";
    const baseMarker = document.getElementById("cmdBaseMarker");
    if (baseMarker) baseMarker.style.display = mapLayers.base ? "" : "none";

    // 2. Rescue Paths Layer (Feature #15 Tactical Multi-Waypoint Road Detour Routing)
    if (pathsLayer) {
      for (const m of dispersedMembers) {
        if (m.status === "hold" || !m.assigned_victim_id) continue;
        const targetVictim = dispersedVictims.find(v => v.victim_id === m.assigned_victim_id);
        if (targetVictim) {
          const isAlpha1 = m.member_id === "ALPHA-M001" || m.location_source === "PHONE_GPS";
          const isWrongDir = isAlpha1 && m.navigation_status === "WRONG_DIRECTION";
          const isArrived = m.status === "arrived" || m.navigation_status === "ARRIVED";

          // Request tactical route in background if available
          if (m.location && targetVictim.location) {
            fetchRouteForMember(m, targetVictim);
          }

          const cachedRoute = mapState.cachedRoutes && mapState.cachedRoutes[m.member_id];
          const hasWaypoints = cachedRoute && Array.isArray(cachedRoute.waypoints) && cachedRoute.waypoints.length > 2;

          let pathStroke = isArrived ? "#22c55e" : (isWrongDir ? "#ef4444" : (isAlpha1 ? "#00f0ff" : "#38bdf8"));
          let pathDash = isWrongDir ? "5,3" : (isAlpha1 ? "4,2" : "none");

          if (cachedRoute && cachedRoute.routing_mode === "DETOUR_DYNAMIC" && !isArrived && !isWrongDir) {
            pathStroke = "#f59e0b"; // Detour amber
            pathDash = "6,3";
          } else if (cachedRoute && cachedRoute.route_status === "NO_VIABLE_ROAD_ROUTE" && !isArrived) {
            pathStroke = "#ef4444"; // Fallback direct red
            pathDash = "4,4";
          }

          if (hasWaypoints && !isArrived) {
            const pts = [];
            pts.push(`${m.renderX},${m.renderY}`);
            for (let i = 1; i < cachedRoute.waypoints.length - 1; i++) {
              const wp = cachedRoute.waypoints[i];
              const svgPt = locToWorldSvg(wp);
              pts.push(`${svgPt.x},${svgPt.y}`);

              // Tactical waypoint marker dot
              const wpDot = svgEl("circle", {
                cx: svgPt.x,
                cy: svgPt.y,
                r: "2.5",
                fill: cachedRoute.routing_mode === "DETOUR_DYNAMIC" ? "#f59e0b" : "#00f0ff",
                stroke: "#ffffff",
                "stroke-width": "0.75",
                opacity: "0.85",
              });
              pathsLayer.appendChild(wpDot);
            }
            pts.push(`${targetVictim.renderX},${targetVictim.renderY}`);

            const polyline = svgEl("polyline", {
              class: "cmd-path cmd-road-route",
              points: pts.join(" "),
              fill: "none",
              stroke: pathStroke,
              "stroke-width": isAlpha1 ? "2.5" : "2",
              "stroke-dasharray": pathDash,
            });
            pathsLayer.appendChild(polyline);

            // Concise Tactical Hazard Warning Badge on detour
            if (cachedRoute.avoided_hazards && cachedRoute.avoided_hazards.length > 0) {
              const firstHaz = cachedRoute.avoided_hazards[0];
              const labelGroup = svgEl("g", {
                transform: `translate(${(m.renderX + targetVictim.renderX) / 2}, ${(m.renderY + targetVictim.renderY) / 2 - 12})`,
                class: "cmd-hazard-route-badge",
              });
              const hazPill = svgEl("rect", {
                x: "-50", y: "-8", width: "100", height: "16", rx: "4",
                fill: "rgba(15, 23, 42, 0.85)", stroke: "#f59e0b", "stroke-width": "1"
              });
              const hazTxt = svgEl("text", {
                x: "0", y: "3", "text-anchor": "middle",
                fill: "#fbbf24", "font-size": "8", "font-weight": "700", "font-family": "monospace"
              });
              hazTxt.textContent = `DETOUR: ${firstHaz.hazard_type.replace(/_/g, " ").substring(0, 14)}`;
              labelGroup.appendChild(hazPill);
              labelGroup.appendChild(hazTxt);
              pathsLayer.appendChild(labelGroup);
            }
          } else {
            // Straight line fallback
            const path = svgEl("line", {
              class: "cmd-path",
              x1: m.renderX, y1: m.renderY,
              x2: targetVictim.renderX, y2: targetVictim.renderY,
              stroke: pathStroke,
              "stroke-width": isAlpha1 ? "2.5" : "2",
              "stroke-dasharray": pathDash,
            });
            pathsLayer.appendChild(path);
          }
        }
      }
    }

    // 3. Operational Jobs Layer
    if (jobsLayer) {
      for (const cl of jobClusters) {
        const isMulti = cl.items.length > 1;
        const mainJob = cl.items[0];

        const jobPin = svgEl("g", {
          transform: `translate(${cl.renderX}, ${cl.renderY})`,
          class: isMulti ? "cmd-cluster-pin" : "cmd-job-pin",
        });

        jobPin.appendChild(svgEl("polygon", {
          points: isMulti ? "-9,-5 0,-11 9,-5 9,5 0,11 -9,5" : "-7,-4 0,-8 7,-4 7,4 0,8 -7,4",
          fill: "#a855f7",
          stroke: "#ffffff",
          "stroke-width": isMulti ? "2" : "1.5",
        }));

        if (isMulti) {
          const badge = svgEl("text", {
            x: "0",
            y: "0",
            class: "cmd-cluster-badge",
          });
          badge.textContent = cl.items.length;
          jobPin.appendChild(badge);
        }

        const rawTitle = mainJob.job_name || mainJob.job_id || "Ops Mission";
        const cleanTitle = isMulti
          ? `${rawTitle.slice(0, 16)}… (+${cl.items.length - 1} jobs)`
          : (rawTitle.length > 24 ? rawTitle.slice(0, 22) + "…" : rawTitle);

        const lblAttrs = getSmartLabelAttrs(cl.renderX, cl.renderY, cleanTitle, placedBoxes);
        const lbl = svgEl("text", {
          x: lblAttrs.xOffset,
          y: lblAttrs.yOffset,
          "text-anchor": lblAttrs.textAnchor,
          "dominant-baseline": lblAttrs.dominantBaseline,
          class: "cmd-pin-label",
        });
        lbl.textContent = cleanTitle;
        jobPin.appendChild(lbl);

        jobPin.addEventListener("click", (e) => {
          e.stopPropagation();
          if (isMulti) {
            const rows = [
              { label: "Cluster Items", value: `${cl.items.length} Active Jobs`, style: "color:#a855f7; font-weight:700;" },
            ];
            cl.items.forEach((j, idx) => {
              rows.push({
                label: `Job #${idx + 1}`,
                value: `${j.job_name || j.job_id} [${j.priority || 'HIGH'}] (${j.status || 'OPEN'})`,
              });
            });
            showPopover(`Ops Cluster (${cl.items.length} Jobs)`, rows);
          } else {
            showPopover(mainJob.job_name || `Job ${mainJob.job_id}`, [
              { label: "Job ID", value: mainJob.job_id },
              { label: "Priority", value: mainJob.priority || "HIGH", style: "color:#a855f7" },
              { label: "Scenario", value: mainJob.scenario_name || mainJob.scenario_id || "Active" },
              { label: "Status", value: mainJob.status || "OPEN" },
              { label: "Assigned To", value: mainJob.assigned_team_id || "Unassigned" },
            ]);
          }
        });

        jobsLayer.appendChild(jobPin);
      }
    }

    // 4. Victims Layer (Needy people pins)
    if (victimsLayer) {
      for (const v of dispersedVictims) {
        const color = TRIAGE_COLORS[v.triage_class] || TRIAGE_COLORS.NO_VITAL_SIGNS;
        const isUrgent = v.triage_class === "HIGH";

        // Draw leader line if pin was dispersed from original location
        if (v.isOffset && Math.hypot(v.renderX - v.clampedX, v.renderY - v.clampedY) > 3) {
          victimsLayer.appendChild(svgEl("line", {
            class: "cmd-pin-leader-line",
            x1: v.clampedX,
            y1: v.clampedY,
            x2: v.renderX,
            y2: v.renderY,
            stroke: color,
            "stroke-width": "1",
            "stroke-dasharray": "2,2",
            opacity: 0.6,
          }));
        }

        const pin = svgEl("g", {
          transform: `translate(${v.renderX}, ${v.renderY})`,
          class: `cmd-victim-pin${isUrgent ? " is-urgent" : ""}`,
        });

        if (isUrgent) {
          pin.appendChild(svgEl("circle", { class: "cmd-ring-pulse", r: "8", fill: "none", stroke: color, "stroke-width": "1.5" }));
        }
        pin.appendChild(svgEl("circle", { r: "7.5", fill: color, stroke: "#ffffff", "stroke-width": "1.5" }));

        const victimText = `${v.victim_id} (${v.triage_class})`;
        const lblAttrs = getSmartLabelAttrs(v.renderX, v.renderY, victimText, placedBoxes);
        const label = svgEl("text", {
          x: lblAttrs.xOffset,
          y: lblAttrs.yOffset,
          "text-anchor": lblAttrs.textAnchor,
          "dominant-baseline": lblAttrs.dominantBaseline,
          class: "cmd-pin-label",
        });
        label.textContent = victimText;
        pin.appendChild(label);

        // Single click: select and show details
        pin.addEventListener("click", (e) => {
          e.stopPropagation();
          mapState.selectedEntityId = v.victim_id;
          showPopover(`Needy Person · ${v.victim_id}`, [
            { label: "Triage Class", value: v.triage_class, style: `color:${color}; font-weight:700;` },
            { label: "Survival Probability", value: `${v.sps ? v.sps.toFixed(1) : '--'}%` },
            { label: "Confidence", value: `${v.confidence_pct ? v.confidence_pct.toFixed(0) : '--'}%` },
            { label: "GPS Coordinates", value: `${(v.location && v.location.latitude != null) ? v.location.latitude.toFixed(4) : '--'}°N, ${(v.location && v.location.longitude != null) ? v.location.longitude.toFixed(4) : '--'}°E` },
            { label: "Altitude", value: `${(v.location && v.location.altitude_m != null) ? v.location.altitude_m.toFixed(0) : '--'} m` },
          ]);

          // Sync with dropdown assignment form
          if (el.formVictim && !el.formVictim.disabled) {
            el.formVictim.value = v.victim_id;
            el.formVictim.dispatchEvent(new Event("change"));
          }
        });

        // Double click: center on victim and enter deep mode
        pin.addEventListener("dblclick", (e) => {
          e.stopPropagation();
          setDeepMode(true);
          zoomAroundPoint(2.2, v.renderX, v.renderY);
        });

        victimsLayer.appendChild(pin);
      }
    }

    // 5. Team Members Layer (Rescuer markers) with In-Place Update & Smooth Transition
    if (membersLayer) {
      const activeMemberPinIds = new Set();
      for (const m of dispersedMembers) {
        const isAlpha1 = m.member_id === "ALPHA-M001" || m.location_source === "PHONE_GPS";
        const isArrived = m.status === "arrived" || m.navigation_status === "ARRIVED";
        const isWrongDir = isAlpha1 && m.navigation_status === "WRONG_DIRECTION";
        const isStale = isAlpha1 && (m.isStale || m.gps_status === "STALE");

        const statusColor = isArrived ? "#22c55e" : (isWrongDir ? "#ef4444" : (m.status === "hold" ? "#8a96a3" : (isAlpha1 ? "#00f0ff" : "#38bdf8")));
        const pinId = `cmdPin_Member_${m.member_id}`;
        activeMemberPinIds.add(pinId);

        let marker = document.getElementById(pinId);
        const isNew = !marker;
        if (isNew) {
          marker = svgEl("g", { id: pinId });
          membersLayer.appendChild(marker);
        }

        // Set class and transform (triggers CSS transition for is-real-gps, disables when is-stale)
        marker.setAttribute("class", `cmd-member-pin${isAlpha1 ? " is-real-gps" : ""}${isStale ? " is-stale" : ""}`);
        marker.setAttribute("transform", `translate(${m.renderX}, ${m.renderY})`);

        // Rebuild internal marker visuals
        marker.innerHTML = "";

        if (isAlpha1) {
          // Accuracy radius circle
          if (m.accuracy_m && m.accuracy_m > 0 && !isStale) {
            const scale = (MAP_SIZE / MAP_METERS_SPAN) * mapState.zoom;
            const accRadiusPx = clamp(m.accuracy_m * scale, 6, 80);
            marker.appendChild(svgEl("circle", {
              r: accRadiusPx,
              fill: isWrongDir ? "rgba(239, 68, 68, 0.12)" : "rgba(0, 240, 255, 0.12)",
              stroke: isWrongDir ? "rgba(239, 68, 68, 0.4)" : "rgba(0, 240, 255, 0.4)",
              "stroke-width": "1",
              "stroke-dasharray": "3,2",
            }));
          }

          // Pulsing halo for live Real GPS
          if (!isStale) {
            marker.appendChild(svgEl("circle", {
              class: "cmd-ring-pulse",
              r: "12",
              fill: "none",
              stroke: isWrongDir ? "#ef4444" : "#00f0ff",
              "stroke-width": "1.5",
            }));
          }

          // Central Real GPS Diamond Symbol
          marker.appendChild(svgEl("polygon", {
            points: "0,-9 9,0 0,9 -9,0",
            fill: isStale ? "#f59e0b" : statusColor,
            stroke: "#ffffff",
            "stroke-width": "2",
          }));

          // Heading pointer arrow when heading is available
          if (m.heading_deg != null && !isNaN(m.heading_deg) && !isStale) {
            const arrowGroup = svgEl("g", { transform: `rotate(${m.heading_deg})` });
            arrowGroup.appendChild(svgEl("polygon", {
              points: "0,-16 -4,-9 4,-9",
              fill: isWrongDir ? "#ef4444" : "#00f0ff",
              stroke: "#ffffff",
              "stroke-width": "1",
            }));
            marker.appendChild(arrowGroup);
          }
        } else {
          // Simulated member standard square marker
          marker.appendChild(svgEl("rect", { x: "-6", y: "-6", width: "12", height: "12", rx: "2", fill: statusColor, stroke: "#ffffff", "stroke-width": "1.5" }));
        }

        const memberText = isAlpha1 ? `${m.callsign} [REAL GPS]` : `${m.callsign} [SIMULATED]`;
        const lblAttrs = getSmartLabelAttrs(m.renderX, m.renderY, memberText, placedBoxes);
        const label = svgEl("text", {
          x: lblAttrs.xOffset,
          y: lblAttrs.yOffset,
          "text-anchor": lblAttrs.textAnchor,
          "dominant-baseline": lblAttrs.dominantBaseline,
          class: isAlpha1 ? "cmd-pin-label cmd-gps-label" : "cmd-pin-label",
          fill: isAlpha1 ? (isStale ? "#f59e0b" : "#00f0ff") : "",
        });
        label.textContent = memberText;
        marker.appendChild(label);

        // Single click: select rescuer and show details
        marker.onclick = (e) => {
          e.stopPropagation();
          mapState.selectedEntityId = m.member_id;
          const rows = [
            { label: "Callsign", value: m.callsign },
            { label: "Tracking Source", value: isAlpha1 ? "🛰️ REAL PHONE GPS (Native Android)" : "⚙️ SIMULATED", style: isAlpha1 ? "color:#00f0ff; font-weight:700;" : "color:#94a3b8;" },
            { label: "Mission Status", value: m.status.toUpperCase(), style: `color:${statusColor}; font-weight:700;` },
            { label: "Team ID", value: m.team_id || "Unassigned" },
            { label: "Assigned Target", value: m.assigned_victim_id || "None" },
            { label: "GPS Coordinates", value: `${(m.location && m.location.latitude != null) ? m.location.latitude.toFixed(6) : '--'}°N, ${(m.location && m.location.longitude != null) ? m.location.longitude.toFixed(6) : '--'}°E` },
          ];

          if (isAlpha1) {
            rows.push({ label: "GPS Status", value: isStale ? "STALE" : (m.gps_status || "STANDBY"), style: !isStale && m.gps_status === "TRACKING" ? "color:#34d399; font-weight:700;" : (isStale ? "color:#f59e0b; font-weight:700;" : "color:#ef4444;") });
            rows.push({ label: "Accuracy", value: m.accuracy_m != null ? `${m.accuracy_m.toFixed(1)} m` : "--" });
            rows.push({ label: "Speed", value: m.speed_mps != null ? `${m.speed_mps.toFixed(2)} m/s (${(m.speed_mps * 3.6).toFixed(1)} km/h)` : "--" });
            rows.push({ label: "Heading", value: m.heading_deg != null ? `${m.heading_deg.toFixed(1)}°` : "--" });
            rows.push({ label: "Target Bearing", value: m.target_bearing_deg != null ? `${m.target_bearing_deg.toFixed(1)}°` : "--" });
            rows.push({ label: "Distance to Target", value: m.distance_to_target_m != null ? `${m.distance_to_target_m.toFixed(1)} m` : "--", style: "color:#facc15; font-weight:700;" });
            rows.push({ label: "Navigation State", value: m.navigation_status || (m.status === "arrived" ? "ARRIVED" : "ON_TRACK"), style: isWrongDir ? "color:#ef4444; font-weight:700;" : "color:#34d399; font-weight:700;" });
            if (m.direction_guidance) {
              rows.push({ label: "Guidance", value: m.direction_guidance, style: isWrongDir ? "color:#ef4444; font-weight:700;" : "color:#38bdf8;" });
            }
          }

          showPopover(`Rescue Team · ${m.callsign}`, rows);

          loadNearestSuggestions(m.member_id);

          if (el.formTeam && m.team_id) {
            el.formTeam.value = m.team_id;
            el.formTeam.dispatchEvent(new Event("change"));
            setTimeout(() => {
              if (el.formMember) {
                el.formMember.value = m.member_id;
                el.formMember.dispatchEvent(new Event("change"));
              }
            }, 50);
          }
        };

        // Double click: center on member and enter deep mode
        marker.ondblclick = (e) => {
          e.stopPropagation();
          setDeepMode(true);
          zoomAroundPoint(2.2, m.renderX, m.renderY);
        };
      }

      // Remove pins that no longer exist
      const existingPins = membersLayer.querySelectorAll(".cmd-member-pin");
      existingPins.forEach(p => {
        if (!activeMemberPinIds.has(p.id)) {
          p.remove();
        }
      });
    }

    applyTransform();
  }

  // ------------------------------------------------------------------ //
  // Interactive Map Event Listeners (Drag, Wheel, Arrows, Touch, Double-Click, Layer Toggles)
  // ------------------------------------------------------------------ //

  function setupMapInteractivity() {
    const wrap = el.mapWrap;
    const svg = el.map;
    if (!wrap || !svg) return;

    // 0. Setup Legend Layer Toggles
    const legendToggles = document.querySelectorAll("#cmdMapLegend .legend-toggle");
    legendToggles.forEach((btn) => {
      btn.addEventListener("click", () => {
        const layerKey = btn.getAttribute("data-layer");
        if (layerKey && mapLayers.hasOwnProperty(layerKey)) {
          mapLayers[layerKey] = !mapLayers[layerKey];
          btn.classList.toggle("is-active", mapLayers[layerKey]);
          btn.classList.toggle("is-inactive", !mapLayers[layerKey]);
          renderMap(mapState.lastVictims, mapState.lastMembers, mapState.lastJobs);
        }
      });
    });

    // 1. Mouse Drag to Pan
    svg.addEventListener("mousedown", (e) => {
      if (e.button !== 0) return; // Only left mouse button
      mapState.isDragging = true;
      mapState.hasMovedDuringDrag = false;
      mapState.dragStart = { x: e.clientX, y: e.clientY };
      mapState.panStart = { x: mapState.panX, y: mapState.panY };
      wrap.classList.add("is-dragging");
    });

    window.addEventListener("mousemove", (e) => {
      if (!mapState.isDragging) return;
      const dx = e.clientX - mapState.dragStart.x;
      const dy = e.clientY - mapState.dragStart.y;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
        mapState.hasMovedDuringDrag = true;
      }
      const rect = svg.getBoundingClientRect();
      const scaleRatio = MAP_SIZE / rect.width;
      mapState.panX = mapState.panStart.x + dx * scaleRatio;
      mapState.panY = mapState.panStart.y + dy * scaleRatio;
      clampPan();
      applyTransform();
    });

    window.addEventListener("mouseup", () => {
      if (mapState.isDragging) {
        mapState.isDragging = false;
        wrap.classList.remove("is-dragging");
      }
    });

    // 2. Mouse Wheel to Zoom toward cursor
    wrap.addEventListener("wheel", (e) => {
      e.preventDefault();
      const pt = getSvgPoint(e);
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      zoomAroundPoint(mapState.zoom * zoomFactor, pt.svgX, pt.svgY);
    }, { passive: false });

    // 3. Double-Click to Activate Deep Exploration / Zoom In
    wrap.addEventListener("dblclick", (e) => {
      e.preventDefault();
      const pt = getSvgPoint(e);
      if (!mapState.isDeepMode) {
        setDeepMode(true);
      } else {
        zoomAroundPoint(mapState.zoom * 1.35, pt.svgX, pt.svgY);
      }
    });

    // 4. Keyboard Navigation (Arrows to Pan, +/- to Zoom, R to Reset, F for Fit All, Esc to Exit)
    wrap.addEventListener("keydown", (e) => {
      let handled = true;
      const panStep = 45;

      switch (e.key) {
        case "ArrowLeft":
          mapState.panX += panStep;
          break;
        case "ArrowRight":
          mapState.panX -= panStep;
          break;
        case "ArrowUp":
          mapState.panY += panStep;
          break;
        case "ArrowDown":
          mapState.panY -= panStep;
          break;
        case "+":
        case "=":
          zoomAroundPoint(mapState.zoom * 1.25, 300, 300);
          break;
        case "-":
        case "_":
          zoomAroundPoint(mapState.zoom / 1.25, 300, 300);
          break;
        case "f":
        case "F":
          fitAllEntities();
          break;
        case "r":
        case "R":
          resetMapView();
          break;
        case "Escape":
          setDeepMode(false);
          hidePopover();
          break;
        default:
          handled = false;
      }

      if (handled) {
        e.preventDefault();
        clampPan();
        applyTransform();
      }
    });

    // 5. Touch Events (Pan & Pinch-to-Zoom)
    wrap.addEventListener("touchstart", (e) => {
      if (e.touches.length === 1) {
        mapState.isDragging = true;
        mapState.dragStart = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        mapState.panStart = { x: mapState.panX, y: mapState.panY };
      } else if (e.touches.length === 2) {
        mapState.isDragging = false;
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        mapState.touchStartDist = Math.sqrt(dx * dx + dy * dy);
        mapState.touchStartZoom = mapState.zoom;
      }
    }, { passive: true });

    wrap.addEventListener("touchmove", (e) => {
      if (e.touches.length === 1 && mapState.isDragging) {
        e.preventDefault();
        const dx = e.touches[0].clientX - mapState.dragStart.x;
        const dy = e.touches[0].clientY - mapState.dragStart.y;
        const rect = svg.getBoundingClientRect();
        const scaleRatio = MAP_SIZE / rect.width;
        mapState.panX = mapState.panStart.x + dx * scaleRatio;
        mapState.panY = mapState.panStart.y + dy * scaleRatio;
        clampPan();
        applyTransform();
      } else if (e.touches.length === 2 && mapState.touchStartDist > 0) {
        e.preventDefault();
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const currentDist = Math.sqrt(dx * dx + dy * dy);
        const factor = currentDist / mapState.touchStartDist;
        zoomAroundPoint(mapState.touchStartZoom * factor, 300, 300);
      }
    }, { passive: false });

    wrap.addEventListener("touchend", () => {
      mapState.isDragging = false;
      mapState.touchStartDist = 0;
    });

    // 6. HUD Button Controls
    if (el.btnZoomIn) el.btnZoomIn.addEventListener("click", () => zoomAroundPoint(mapState.zoom * 1.25, 300, 300));
    if (el.btnZoomOut) el.btnZoomOut.addEventListener("click", () => zoomAroundPoint(mapState.zoom / 1.25, 300, 300));
    if (el.btnFitAll) el.btnFitAll.addEventListener("click", () => fitAllEntities());
    if (el.btnReset) el.btnReset.addEventListener("click", () => resetMapView());
    if (el.btnExitDeep) el.btnExitDeep.addEventListener("click", () => setDeepMode(false));
    if (el.btnPopoverClose) el.btnPopoverClose.addEventListener("click", () => hidePopover());

    // 7. Debounced Window Resize Handler
    let cmdResizeDebounce = null;
    window.addEventListener("resize", () => {
      clearTimeout(cmdResizeDebounce);
      cmdResizeDebounce = setTimeout(() => {
        if (mapState.lastVictims.length || mapState.lastMembers.length) {
          renderMap(mapState.lastVictims, mapState.lastMembers, mapState.lastJobs);
        }
      }, 150);
    });
  }

  // ------------------------------------------------------------------ //
  // Live Metadata Card (Alpha Member 1 Real GPS) & Member List
  // ------------------------------------------------------------------ //

  function updateAlpha1LiveCard(a1) {
    const card = document.getElementById("cmdAlpha1LiveCard");
    if (!card) return;

    const elMember = document.getElementById("a1CardMemberVal");
    const elSource = document.getElementById("a1CardLocationSource");
    const elState = document.getElementById("a1CardGpsState");
    const elStatusBadge = document.getElementById("a1CardGpsStatus");
    const elLat = document.getElementById("a1CardLat");
    const elLon = document.getElementById("a1CardLon");
    const elAcc = document.getElementById("a1CardAccuracy");
    const elSpeed = document.getElementById("a1CardSpeed");
    const elHead = document.getElementById("a1CardHeading");
    const elTargetBearing = document.getElementById("a1CardTargetBearing");
    const elHeadingDiff = document.getElementById("a1CardHeadingDiff");
    const elDist = document.getElementById("a1CardDistance");
    const elDistTrend = document.getElementById("a1CardDistanceTrend");
    const elMissionId = document.getElementById("a1CardMissionId");
    const elMissionStatus = document.getElementById("a1CardMissionStatus");
    const elMission = document.getElementById("a1CardMission");
    const elNav = document.getElementById("a1CardNav");
    const elGuidance = document.getElementById("a1CardGuidance");
    const elLastUpdate = document.getElementById("a1CardLastUpdate");

    if (!a1) {
      if (elState) elState.textContent = "STANDBY";
      if (elStatusBadge) {
        elStatusBadge.textContent = "STANDBY";
        elStatusBadge.className = "badge alpha1-status-pill";
      }
      if (elMissionId) elMissionId.textContent = "--";
      if (elMissionStatus) elMissionStatus.textContent = "STANDBY";
      if (elLastUpdate) elLastUpdate.textContent = "--";
      return;
    }

    const isRealGps = a1.location_source === "PHONE_GPS" || a1.member_id === "ALPHA-M001";
    const effectiveGpsStatus = a1.gps_status || "STANDBY";
    const isTracking = effectiveGpsStatus === "TRACKING";
    const isStale = effectiveGpsStatus === "STALE";

    if (elMember) elMember.textContent = a1.callsign ? `${a1.callsign} (${a1.member_id})` : "Alpha Member 1";
    if (elSource) {
      elSource.textContent = isRealGps ? "REAL GPS" : "SIMULATED";
      elSource.style.color = isRealGps ? "#0284c7" : "#64748b";
    }
    if (elState) {
      elState.textContent = effectiveGpsStatus;
      elState.style.color = isTracking ? "#16a34a" : (isStale ? "#d97706" : "#64748b");
    }
    if (elStatusBadge) {
      elStatusBadge.textContent = effectiveGpsStatus;
      elStatusBadge.className = `badge alpha1-status-pill ${isTracking ? "is-tracking" : (isStale ? "is-stale" : "")}`;
    }

    if (a1.location && isValidGpsCoordinate(a1.location.latitude, a1.location.longitude)) {
      if (elLat) elLat.textContent = a1.location.latitude.toFixed(6) + "°";
      if (elLon) elLon.textContent = a1.location.longitude.toFixed(6) + "°";
    } else {
      if (elLat) elLat.textContent = "--";
      if (elLon) elLon.textContent = "--";
    }

    if (elAcc) elAcc.textContent = a1.accuracy_m != null ? `${a1.accuracy_m.toFixed(1)} m` : "--";
    if (elSpeed) elSpeed.textContent = a1.speed_mps != null ? `${a1.speed_mps.toFixed(2)} m/s (${(a1.speed_mps * 3.6).toFixed(1)} km/h)` : "--";
    if (elHead) elHead.textContent = a1.heading_deg != null ? `${a1.heading_deg.toFixed(1)}°` : "--";
    if (elTargetBearing) elTargetBearing.textContent = a1.target_bearing_deg != null ? `${a1.target_bearing_deg.toFixed(1)}°` : "--";
    const hDiff = a1.heading_difference_deg != null ? a1.heading_difference_deg : a1.direction_delta_deg;
    if (elHeadingDiff) elHeadingDiff.textContent = hDiff != null ? `${hDiff.toFixed(1)}°` : "--";
    if (elDist) elDist.textContent = a1.distance_to_target_m != null ? `${a1.distance_to_target_m.toFixed(1)} m` : "--";
    if (elDistTrend) {
      elDistTrend.textContent = a1.distance_trend || "--";
      elDistTrend.style.color = a1.distance_trend === "APPROACHING" ? "#16a34a" : (a1.distance_trend === "MOVING_AWAY" ? "#ef4444" : "#64748b");
    }
    if (elMissionId) elMissionId.textContent = a1.active_command_id || a1.assigned_job_id || (a1.assigned_victim_id ? `CMD-${a1.assigned_victim_id}` : "--");
    if (elMissionStatus) elMissionStatus.textContent = (a1.status || "HOLD").toUpperCase();
    if (elMission) elMission.textContent = (a1.status || "HOLD").toUpperCase();

    if (elNav) {
      const nav = a1.navigation_status || (a1.status === "arrived" ? "ARRIVED" : (a1.status === "en_route" ? "ON_TRACK" : "--"));
      elNav.textContent = nav;
      if (nav === "ARRIVED") elNav.style.color = "#16a34a";
      else if (nav === "WRONG_DIRECTION") elNav.style.color = "#ef4444";
      else if (nav === "ON_TRACK") elNav.style.color = "#0284c7";
      else if (nav === "STATIONARY") elNav.style.color = "#d97706";
      else if (nav === "STALE" || nav === "GPS_STALE") elNav.style.color = "#f59e0b";
      else elNav.style.color = "#0f172a";
    }

    if (elGuidance) {
      elGuidance.textContent = a1.direction_guidance || "--";
      if (a1.navigation_status === "WRONG_DIRECTION") elGuidance.style.color = "#ef4444";
      else if (a1.navigation_status === "ARRIVED") elGuidance.style.color = "#16a34a";
      else elGuidance.style.color = "#0284c7";
    }

    if (elLastUpdate) {
      const ts = a1.gps_timestamp || a1.last_updated;
      if (ts) {
        try {
          const dt = new Date(ts);
          const diffSec = Math.max(0, Math.floor((Date.now() - dt.getTime()) / 1000));
          if (diffSec < 5) elLastUpdate.textContent = "Just now (<5s)";
          else if (diffSec < 60) elLastUpdate.textContent = `${diffSec}s ago${isStale ? " (STALE)" : ""}`;
          else elLastUpdate.textContent = `${Math.floor(diffSec / 60)}m ${diffSec % 60}s ago${isStale ? " (STALE)" : ""}`;
          elLastUpdate.style.color = isStale ? "#d97706" : "#16a34a";
        } catch (e) {
          elLastUpdate.textContent = ts;
        }
      } else {
        elLastUpdate.textContent = "--";
      }
    }
  }

  function renderMemberList(members) {
    el.memberList.innerHTML = members.map(m => {
      const isAlpha1 = m.member_id === "ALPHA-M001" || m.location_source === "PHONE_GPS";
      const navStatus = m.navigation_status || (m.status === "arrived" ? "ARRIVED" : (m.status === "en_route" ? "ON_TRACK" : null));
      const gpsPill = isAlpha1
        ? `<span class="status-pill" style="background:rgba(0, 240, 255, 0.15); color:#0284c7; font-weight:700; font-size:10px; border:1px solid rgba(0, 240, 255, 0.4);">📡 REAL GPS</span>`
        : `<span class="status-pill" style="font-size:10px; color:#64748b; background:rgba(148, 163, 184, 0.12); border:1px solid rgba(148, 163, 184, 0.25);">⚙️ SIMULATED</span>`;
      const navPill = (isAlpha1 && navStatus && m.assigned_victim_id)
        ? `<span class="status-pill" style="font-size:10px; font-weight:700; color:${navStatus === 'WRONG_DIRECTION' ? '#ef4444' : '#16a34a'}; background:${navStatus === 'WRONG_DIRECTION' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)'}; border:1px solid ${navStatus === 'WRONG_DIRECTION' ? '#ef444466' : '#22c55e66'};">${navStatus}</span>`
        : "";

      return `
        <div class="cmd-member-row" data-member-id="${m.member_id}">
          <span style="font-weight:600;">${escapeHtml(m.callsign)}</span>
          ${gpsPill}
          <span class="cmd-member-status status-${m.status} status-pill status-pill-${m.status}">${m.status.toUpperCase()}</span>
          ${navPill}
          ${m.team_id === "UNASSIGNED" ? `<span class="status-pill status-pill-unassigned" style="font-size:10.5px; padding:1px 7px; font-weight:700;">Unassigned - Pool</span>` : ""}
          ${m.assigned_victim_id ? `<span>→ ${escapeHtml(m.assigned_victim_id)}</span>` : ""}
        </div>
      `;
    }).join("") || "<div class='dim'>No tracked members yet — increase roster count in Testing Console.</div>";

    el.memberList.querySelectorAll(".cmd-member-row").forEach(row => {
      row.addEventListener("click", () => loadNearestSuggestions(row.dataset.memberId));
    });
  }

  function populateTeamDropdown(members) {
    lastMembers = members;
    const teamIds = [...new Set(members.map(m => m.team_id))];
    const prev = el.formTeam.value;
    el.formTeam.innerHTML = `<option value="">Select team…</option>` +
      teamIds.map(t => `<option value="${t}">${t === "UNASSIGNED" ? "Unassigned - Pool" : t}</option>`).join("");
    if (teamIds.includes(prev)) el.formTeam.value = prev;
    el.formScenario.value = scenarioName || "—";
  }

  function resetVictimAndBanner() {
    el.formVictim.innerHTML = `<option value="">Select member first…</option>`;
    el.formVictim.disabled = true;
    el.confirmBanner.hidden = true;
    el.formAssignBtn.disabled = true;
    el.formResult.textContent = "";
  }

  el.formTeam.addEventListener("change", () => {
    const teamId = el.formTeam.value;
    const membersInTeam = lastMembers.filter(m => m.team_id === teamId);
    el.formMember.innerHTML = `<option value="">Select member…</option>` +
      membersInTeam.map(m => `<option value="${m.member_id}" data-status="${m.status}">${m.callsign} (${m.status.toUpperCase()})</option>`).join("");
    el.formMember.disabled = !teamId;
    resetVictimAndBanner();
  });

  el.formMember.addEventListener("change", async () => {
    const memberId = el.formMember.value;
    resetVictimAndBanner();
    if (!memberId) return;

    const selectedOption = el.formMember.selectedOptions[0];
    const memberStatus = selectedOption.dataset.status;

    if (memberStatus !== "hold") {
      el.confirmBanner.hidden = false;
      el.confirmIcon.textContent = "🚫";
      el.confirmText.textContent = `This member is already ${memberStatus.toUpperCase()} — cannot reassign. Pick a HOLD member.`;
      el.formVictim.disabled = true;
      el.formAssignBtn.disabled = true;
      return;
    }

    el.confirmBanner.hidden = false;
    el.confirmIcon.textContent = "✅";
    el.confirmText.textContent = "Member status is HOLD — safe to assign.";

    try {
      const res = await fetch(`${apiBase}/commander/nearest/${memberId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      el.formVictim.innerHTML = `<option value="">Select victim…</option>` +
        (data.suggestions || []).map(s =>
          `<option value="${s.victim_id}">${s.victim_id} — ${s.triage_class} — ${s.distance_label}</option>`
        ).join("");
      el.formVictim.disabled = false;
    } catch (e) {
      el.formResult.textContent = `❌ Could not load nearest victims: ${e.message}`;
    }
  });

  el.formVictim.addEventListener("change", () => {
    el.formAssignBtn.disabled = !el.formVictim.value;
  });

  el.formAssignBtn.addEventListener("click", async () => {
    const member_id = el.formMember.value;
    const victim_id = el.formVictim.value;
    el.formAssignBtn.disabled = true;
    try {
      const res = await fetch(`${apiBase}/commander/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_id, victim_id }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Assign failed");
      el.formResult.textContent = `✅ ${member_id} assigned to ${victim_id} — GO signal sent.`;
      el.formMember.value = "";
      resetVictimAndBanner();
      el.formTeam.dispatchEvent(new Event("change"));
    } catch (err) {
      el.formResult.textContent = `❌ ${err.message}`;
      el.formAssignBtn.disabled = false;
    }
  });

  async function loadNearestSuggestions(memberId) {
    try {
      const res = await fetch(`${apiBase}/commander/nearest/${memberId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      el.suggestPanel.hidden = false;
      el.suggestMember.textContent = data.member.callsign;
      el.suggestList.innerHTML = data.suggestions.map(s => `
        <div class="cmd-suggest-row" data-victim-id="${s.victim_id}">
          <span class="cmd-suggest-triage" style="color:${TRIAGE_COLORS[s.triage_class] || TRIAGE_COLORS.NO_VITAL_SIGNS}">${s.triage_class}</span>
          <span>${s.victim_id}</span>
          <span class="cmd-suggest-dist">${s.distance_label}</span>
          <button class="btn btn-primary btn-small cmd-assign-btn" data-member-id="${memberId}" data-victim-id="${s.victim_id}">Send to Watch</button>
        </div>
      `).join("") || "<div class='dim'>No needy people currently detected.</div>";

      el.suggestList.querySelectorAll(".cmd-assign-btn").forEach(btn => {
        btn.addEventListener("click", () => assignMemberToVictim(btn));
      });
    } catch (err) {
      el.suggestList.innerHTML = `<div class="dim">Failed to load: ${err.message}</div>`;
    }
  }

  async function assignMemberToVictim(btn) {
    btn.disabled = true;
    btn.textContent = "Sending...";
    try {
      const res = await fetch(`${apiBase}/commander/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_id: btn.dataset.memberId, victim_id: btn.dataset.victimId }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      el.suggestPanel.hidden = true;
    } catch (err) {
      btn.disabled = false;
      btn.textContent = "❌ Failed — retry";
    }
  }

  function showArrivalToast(text) {
    const toast = document.createElement("div");
    toast.className = "cmd-arrival-toast";
    toast.textContent = text;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  }

  // ------------------------------------------------------------------ //
  // Sensor Telemetry Polling (Pressure, Landslide, Camera, Rainfall)
  // ------------------------------------------------------------------ //

  async function pollPressureTelemetry() {
    try {
      const curRes = await fetch(`${apiBase}/sensors/pressure/current`);
      if (curRes.ok) {
        const curData = await curRes.json();
        const p = curData.pressure || {};
        if (el.pressureVal) el.pressureVal.textContent = p.pressure_hpa != null ? p.pressure_hpa.toFixed(1) : "--";
        if (el.pressureRate) el.pressureRate.textContent = `Rate: ${p.rate_of_change != null ? (p.rate_of_change > 0 ? "+" : "") + p.rate_of_change.toFixed(2) : "0.0"} hPa/cycle`;

        if (el.pressureTrend) {
          const tr = p.trend || "STABLE";
          el.pressureTrend.textContent = tr.replace(/_/g, " ");
          el.pressureTrend.className = "badge-pressure-trend " + (
            tr === "RAPIDLY_FALLING" ? "trend-rapidly-falling" :
              tr === "FALLING" ? "trend-falling" :
                tr === "RAPIDLY_RISING" ? "trend-rapidly-rising" :
                  tr === "RISING" ? "trend-rising" : "trend-stable"
          );
        }

        if (el.pressureStatus) {
          el.pressureStatus.textContent = p.status || "ONLINE";
          el.pressureStatus.className = `badge status-pill-${(p.status || "online").toLowerCase()}`;
        }
      }

      const histRes = await fetch(`${apiBase}/sensors/pressure/history?limit=30`);
      if (histRes.ok) {
        const histData = await histRes.json();
        renderPressureChart(histData.history || []);
      }

      const assessRes = await fetch(`${apiBase}/scenario/assessment`);
      if (assessRes.ok) {
        const assessData = await assessRes.json();
        if (el.confidenceScore) {
          el.confidenceScore.textContent = `Confidence Score: ${assessData.confidence_pct != null ? assessData.confidence_pct.toFixed(1) : "--"}% (${assessData.overall_risk || "LOW"} RISK)`;
        }
        if (el.evidenceList) {
          el.evidenceList.innerHTML = "";
          const evList = assessData.active_evidence || [];
          if (evList.length === 0) {
            el.evidenceList.innerHTML = `<li class="pressure-evidence-item">Atmospheric conditions nominal; no active warnings.</li>`;
          } else {
            for (const ev of evList) {
              const li = document.createElement("li");
              li.className = "pressure-evidence-item";
              li.textContent = `🔍 ${ev.evidence_label}: ${ev.description} (Conf: ${(ev.confidence * 100).toFixed(0)}%)`;
              el.evidenceList.appendChild(li);
            }
          }
        }
      }
    } catch (err) {
      /* ignore transient telemetry errors */
    }
  }

  function renderPressureChart(history) {
    if (!el.pressureSvg) return;
    const svg = el.pressureSvg;
    svg.innerHTML = "";

    if (!history || history.length === 0) {
      const txt = svgEl("text", { x: "250", y: "80", "text-anchor": "middle", fill: "#8a96a3", "font-size": "12" });
      txt.textContent = "Awaiting pressure history data...";
      svg.appendChild(txt);
      return;
    }

    const W = 500, H = 160;
    const padL = 45, padR = 25, padT = 20, padB = 25;
    const chartW = W - padL - padR;
    const chartH = H - padT - padB;

    const values = history.map(h => parseFloat(h.pressure_hpa)).filter(v => !isNaN(v));
    if (values.length === 0) return;

    let minP = Math.min(...values);
    let maxP = Math.max(...values);
    if (maxP - minP < 4) {
      minP -= 2;
      maxP += 2;
    }

    for (let i = 0; i <= 3; i++) {
      const yVal = minP + (i / 3) * (maxP - minP);
      const y = padT + chartH - (i / 3) * chartH;
      const line = svgEl("line", { x1: padL, y1: y, x2: padL + chartW, y2: y, stroke: "#e2e8f0", "stroke-dasharray": "3 3" });
      const lbl = svgEl("text", { x: padL - 6, y: y + 4, "text-anchor": "end", fill: "#64748b", "font-size": "10", "font-family": "monospace" });
      lbl.textContent = yVal.toFixed(0);
      svg.appendChild(line);
      svg.appendChild(lbl);
    }

    const points = values.map((val, idx) => {
      const x = padL + (idx / Math.max(values.length - 1, 1)) * chartW;
      const y = padT + chartH - ((val - minP) / (maxP - minP)) * chartH;
      return { x, y, val };
    });

    const d = points.map((pt, i) => (i === 0 ? `M ${pt.x} ${pt.y}` : `L ${pt.x} ${pt.y}`)).join(" ");
    const path = svgEl("path", { d, fill: "none", stroke: "#0284c7", "stroke-width": "2.5", "stroke-linejoin": "round", "stroke-linecap": "round" });
    svg.appendChild(path);

    if (points.length > 1) {
      const areaD = `${d} L ${points[points.length - 1].x} ${padT + chartH} L ${points[0].x} ${padT + chartH} Z`;
      const area = svgEl("path", { d: areaD, fill: "#0284c7", "fill-opacity": "0.1" });
      svg.insertBefore(area, path);
    }

    for (const pt of points) {
      const circ = svgEl("circle", { cx: pt.x, cy: pt.y, r: "3.5", fill: "#ffffff", stroke: "#0284c7", "stroke-width": "2" });
      svg.appendChild(circ);
    }
  }

  async function pollLandslideTelemetry() {
    try {
      const nodesRes = await fetch(`${apiBase}/hazards/landslide/nodes`);
      if (nodesRes.ok) {
        const data = await nodesRes.json();
        const score = data.highest_risk_score || 0.0;
        const level = data.overall_risk_level || "LOW";
        const riskColor = level === "CRITICAL" ? "#ef4444" : (level === "HIGH" ? "#f97316" : (level === "MODERATE" ? "#eab308" : "#22c55e"));

        const elScore = document.getElementById("cmdLandslideRiskScore");
        const elBadge = document.getElementById("cmdLandslideRiskBadge");
        const elState = document.getElementById("cmdLandslideStateBadge");
        const elPersist = document.getElementById("cmdLandslidePersistBadge");
        const elAction = document.getElementById("cmdLandslideAction");
        const elNodesList = document.getElementById("cmdSlopeNodesList");
        const elFactorsList = document.getElementById("cmdLandslideFactorsList");

        if (elScore) {
          elScore.textContent = score.toFixed(1);
          elScore.style.color = riskColor;
        }
        if (elBadge) {
          elBadge.textContent = `${level} (${score.toFixed(1)})`;
          elBadge.style.background = `${riskColor}22`;
          elBadge.style.color = riskColor;
          elBadge.style.borderColor = `${riskColor}66`;
        }
        if (elAction) {
          elAction.textContent = data.recommended_action || "Routine slope stability monitoring active.";
        }

        const nodes = data.nodes ? Object.values(data.nodes) : [];
        if (nodes.length > 0) {
          const firstNode = nodes[0];
          if (elState) {
            elState.textContent = firstNode.event_state || "NORMAL";
            elState.style.color = riskColor;
          }
          if (elPersist) {
            elPersist.textContent = `Persist: ${firstNode.persistence_cycles || 0} cyc`;
          }
        }

        if (elNodesList && nodes.length > 0) {
          elNodesList.innerHTML = nodes.map(n => `
            <div style="display: flex; justify-content: space-between; align-items: center; background: #ffffff; border: 1px solid var(--border, #d3e1f5); padding: 6px 10px; border-radius: 6px; font-size: 11px;">
              <span style="font-weight: 700; color: var(--ink);">${escapeHtml(n.node_id)}</span>
              <span>💧 ${n.soil_moisture_pct.toFixed(1)}% <span style="color:var(--ink-dim);">(${escapeHtml(n.moisture_trend)})</span></span>
              <span>📐 ${n.tilt_angle_deg.toFixed(2)}° <span style="color:var(--ink-dim);">(${escapeHtml(n.tilt_trend)})</span></span>
              <span class="badge" style="background: ${n.risk_level === 'CRITICAL' ? '#ef444422' : '#22c55e22'}; color: ${n.risk_level === 'CRITICAL' ? '#ef4444' : '#16a34a'}; font-size: 10px; padding: 1px 6px; border: 1px solid ${n.risk_level === 'CRITICAL' ? '#ef444455' : '#22c55e55'};">${n.landslide_risk_score}</span>
            </div>
          `).join("");
        }

        if (elFactorsList) {
          const factors = [];
          for (const n of nodes) {
            if (n.contributing_factors) {
              for (const f of n.contributing_factors) {
                if (!factors.includes(f)) factors.push(f);
              }
            }
          }
          if (factors.length === 0) {
            elFactorsList.innerHTML = `<li class="empty-note">Stable slope equilibrium within nominal thresholds.</li>`;
          } else {
            elFactorsList.innerHTML = factors.map(f => `
              <li style="display: flex; align-items: center; gap: 6px; color: var(--ink);">
                <span style="color: ${riskColor};">⚠️</span> ${escapeHtml(f)}
              </li>
            `).join("");
          }
        }
      }
    } catch (err) {
      /* ignore transient polling errors */
    }
  }

  async function pollCameraThermalTelemetry() {
    try {
      const camRes = await fetch(`${apiBase}/sensors/camera/current`);
      const thmRes = await fetch(`${apiBase}/sensors/thermal/current`);
      const corrRes = await fetch(`${apiBase}/sensors/camera-thermal/correlation?victim_id=V1`);

      if (camRes.ok) {
        const camData = await camRes.json();
        const cam = camData.camera || {};
        const elCamState = document.getElementById("cmdCameraState");
        const elCamConf = document.getElementById("cmdCameraConfBadge");
        const elCamPers = document.getElementById("cmdCameraPersonsBadge");
        const elCamSub = document.getElementById("cmdCameraSub");

        if (elCamState) elCamState.textContent = cam.detection_state || "NO_DETECTION";
        if (elCamConf) elCamConf.textContent = `Conf: ${Math.round((cam.confidence || 0) * 100)}%`;
        if (elCamPers) elCamPers.textContent = `${cam.person_count || 0} Pers`;
        if (elCamSub) elCamSub.textContent = `Visibility: ${Math.round((cam.visibility || 1) * 100)}% · Occlusion: ${Math.round((cam.occlusion || 0) * 100)}%`;
      }

      if (thmRes.ok) {
        const thmData = await thmRes.json();
        const thm = thmData.thermal || {};
        const elThmTemp = document.getElementById("cmdThermalTemp");
        const elThmDelta = document.getElementById("cmdThermalDelta");
        const elThmType = document.getElementById("cmdThermalTypeBadge");
        const elThmConf = document.getElementById("cmdThermalConfBadge");
        const elThmSub = document.getElementById("cmdThermalSub");

        if (elThmTemp) elThmTemp.textContent = `${thm.estimated_temperature ? thm.estimated_temperature.toFixed(1) : '20.0'} °C`;
        if (elThmDelta) elThmDelta.textContent = `(Δ ${thm.temperature_delta ? thm.temperature_delta.toFixed(1) : '0.0'}°C)`;
        if (elThmType) {
          elThmType.textContent = thm.detection_type || "NO_HEAT";
          elThmType.style.background = thm.human_signature ? "rgba(34,197,94,0.15)" : (thm.fire_hotspot ? "rgba(239,68,68,0.15)" : "rgba(244,63,94,0.15)");
          elThmType.style.color = thm.human_signature ? "#22c55e" : (thm.fire_hotspot ? "#ef4444" : "#f43f5e");
        }
        if (elThmConf) elThmConf.textContent = `Conf: ${Math.round((thm.thermal_confidence || 0) * 100)}%`;
        if (elThmSub) elThmSub.textContent = `Smoke Penetration: High · Contrast: ${thm.thermal_contrast ? thm.thermal_contrast.toFixed(1) : '1.0'}x`;
      }

      if (corrRes.ok) {
        const corrData = await corrRes.json();
        const corr = corrData.correlation || {};
        const elCase = document.getElementById("cmdCorrelationCase");
        const elNarrative = document.getElementById("cmdCorrelationNarrative");
        const elTokens = document.getElementById("cmdCorrelationTokens");

        const caseColor = corr.correlation_case === "CASE_4_QUAD_SENSOR_CORROBORATED" ? "#22c55e" :
          corr.correlation_case === "CASE_1_STRONG_SURVIVOR" ? "#38bdf8" :
            corr.correlation_case === "CASE_2_POSSIBLE_FALSE_POSITIVE" ? "#f97316" :
              corr.correlation_case === "CASE_3_HIDDEN_OBSCURED_SURVIVOR" ? "#a855f7" : "#64748b";

        if (elCase) {
          elCase.textContent = `${corr.correlation_case || "CORRELATION_ANALYZING"} (${Math.round((corr.combined_confidence || 0) * 100)}%)`;
          elCase.style.color = caseColor;
        }
        if (elNarrative) elNarrative.textContent = corr.explainable_summary || "Cross-modal sensor synergy nominal.";
        if (elTokens) {
          elTokens.innerHTML = (corr.evidence_tokens || []).map(t => `<span class="badge" style="font-size: 10px; background: rgba(56,189,248,0.15); color: #38bdf8; padding: 2px 6px; border-radius: 4px;">${escapeHtml(t)}</span>`).join("");
        }
      }
    } catch (err) {
      /* ignore transient errors */
    }
  }

  async function pollRainfallTelemetry() {
    try {
      const rainRes = await fetch(`${apiBase}/sensors/rainfall/current`);
      if (rainRes.ok) {
        const data = await rainRes.json();
        const r = data.rainfall || {};
        const rate = r.rainfall_rate_mm_h != null ? r.rainfall_rate_mm_h : 0.0;
        const cumul = r.cumulative_rainfall_mm != null ? r.cumulative_rainfall_mm : 0.0;
        const cls = r.classification || "NO_RAIN";
        const trend = r.trend || "STABLE";

        const clsColor = cls === "EXTREME" ? "#ef4444" :
          cls === "VERY_HEAVY" ? "#f43f5e" :
            cls === "HEAVY" ? "#f97316" :
              cls === "MODERATE" ? "#eab308" :
                cls === "LIGHT" ? "#38bdf8" : "#94a3b8";

        const elRate = document.getElementById("cmdRainfallRate");
        const elRiskBadge = document.getElementById("cmdRainfallRiskBadge");
        const elClassBadge = document.getElementById("cmdRainfallClassBadge");
        const elTrendBadge = document.getElementById("cmdRainfallTrendBadge");
        const elSummary = document.getElementById("cmdRainfallSummary");
        const elCumul = document.getElementById("cmdRainfallCumul");
        const elRoc = document.getElementById("cmdRainfallRoc");
        const elStatus = document.getElementById("cmdRainfallStatusBadge");
        const elConf = document.getElementById("cmdRainfallConfBadge");
        const elFlood = document.getElementById("cmdRainfallCompoundFlood");
        const elLandslide = document.getElementById("cmdRainfallCompoundLandslide");
        const elBadges = document.getElementById("cmdRainfallEvidenceBadges");

        if (elRate) {
          elRate.textContent = rate.toFixed(1);
          elRate.style.color = clsColor;
        }
        if (elRiskBadge) {
          elRiskBadge.textContent = `${cls} (${rate.toFixed(1)} mm/h)`;
          elRiskBadge.style.background = `${clsColor}22`;
          elRiskBadge.style.color = clsColor;
          elRiskBadge.style.borderColor = `${clsColor}66`;
        }
        if (elClassBadge) {
          elClassBadge.textContent = cls;
          elClassBadge.style.background = `${clsColor}22`;
          elClassBadge.style.color = clsColor;
          elClassBadge.style.borderColor = `${clsColor}66`;
        }
        if (elTrendBadge) {
          elTrendBadge.textContent = trend;
        }
        if (elSummary) {
          elSummary.textContent = `Precipitation intensity is ${cls} (${rate.toFixed(1)} mm/h). Cumulative: ${cumul.toFixed(1)} mm.`;
        }
        if (elCumul) {
          elCumul.textContent = `${cumul.toFixed(1)} mm`;
          elCumul.style.color = cumul >= 100.0 ? "#ef4444" : "#38bdf8";
        }
        if (elRoc) {
          elRoc.textContent = `(Δ ${(r.rate_of_change || 0.0).toFixed(1)} mm/h/cyc)`;
        }
        if (elStatus) {
          elStatus.textContent = r.status || "ONLINE";
          elStatus.style.color = r.status === "ONLINE" ? "#22c55e" : "#ef4444";
        }
        if (elConf) {
          elConf.textContent = `${Math.round((r.confidence || 0.98) * 100)}% Conf`;
        }

        if (elFlood) {
          if (rate >= 30.0) {
            elFlood.innerHTML = '🌊 Flash Flood Driver: <span style="color:#ef4444; font-weight:800;">ACTIVE CRITICAL</span>';
          } else {
            elFlood.innerHTML = '🌊 Flash Flood Driver: <span style="color:#94a3b8;">INACTIVE</span>';
          }
        }

        if (elLandslide) {
          if (rate >= 25.0) {
            elLandslide.innerHTML = '⛰️ Landslide Driver: <span style="color:#f97316; font-weight:800;">ACTIVE ELEVATED</span>';
          } else {
            elLandslide.innerHTML = '⛰️ Landslide Driver: <span style="color:#94a3b8;">INACTIVE</span>';
          }
        }

        if (elBadges) {
          const badges = [];
          if (rate >= 100.0) badges.push('<span class="badge" style="font-size:10px; background:rgba(239,68,68,0.2); color:#ef4444; font-weight:700;">🚨 CLOUDBURST</span>');
          if (rate >= 50.0) badges.push('<span class="badge" style="font-size:10px; background:rgba(244,63,94,0.2); color:#f43f5e; font-weight:700;">⚠️ DOWNPOUR</span>');
          if (cumul >= 100.0) badges.push('<span class="badge" style="font-size:10px; background:rgba(239,68,68,0.2); color:#ef4444; font-weight:700;">⚠️ CRITICAL ACCUMULATION</span>');
          elBadges.innerHTML = badges.join(" ");
        }
      }
    } catch (err) {
      /* ignore transient errors */
    }
  }

  // ------------------------------------------------------------------ //
  // Subsurface UWB Bioradar Simulation Handler
  // ------------------------------------------------------------------ //
  let subsurfaceConfig = {
    preset_id: "preset_2",
    soil_type: "wet_soil",
    soil_moisture_pct: 55,
    burial_depth_m: 1.2,
    survivor_mode: "one",
    survivor_alive: true,
  };
  let subsurfaceTelemetry = null;
  let selectedSubsurfaceTargetId = null;

  async function pollSubsurfaceTelemetry() {
    try {
      const res = await fetch(`${apiBase}/api/subsurface/status`);
      if (res.ok) {
        const data = await res.json();
        subsurfaceTelemetry = data.telemetry;
        subsurfaceConfig = data.config || subsurfaceConfig;
        renderSubsurfaceUI(data);
      }
    } catch (err) {
      /* ignore transient error */
    }
  }

  function renderSubsurfaceUI(data) {
    const tel = data.telemetry || {};
    const targets = tel.targets || [];
    const humanTargets = targets.filter(t => t.is_human);

    // Resolve selectedTarget: match selectedSubsurfaceTargetId, or primary_target, or first human target
    let selectedTarget = null;
    if (selectedSubsurfaceTargetId && humanTargets.length > 0) {
      selectedTarget = humanTargets.find(t => t.target_id === selectedSubsurfaceTargetId) || null;
    }
    if (!selectedTarget) {
      selectedTarget = tel.primary_target || humanTargets[0] || targets[0] || null;
      if (selectedTarget && selectedTarget.target_id) {
        selectedSubsurfaceTargetId = selectedTarget.target_id;
      }
    }

    const status = tel.status || "SCANNING";
    const sigQuality = tel.signal_quality || "GOOD";

    // Status Badge
    const elBadge = document.getElementById("cmdUwbStatusBadge");
    if (elBadge) {
      elBadge.textContent = status.replace("_", " ");
      if (status === "TARGET_DETECTED") {
        elBadge.style.background = "rgba(34, 197, 94, 0.25)";
        elBadge.style.color = "#4ade80";
        elBadge.style.borderColor = "rgba(34, 197, 94, 0.5)";
      } else if (status === "NO_TARGET") {
        elBadge.style.background = "rgba(148, 163, 184, 0.2)";
        elBadge.style.color = "#94a3b8";
        elBadge.style.borderColor = "#64748b";
      } else {
        elBadge.style.background = "rgba(56, 189, 248, 0.2)";
        elBadge.style.color = "#38bdf8";
        elBadge.style.borderColor = "rgba(56, 189, 248, 0.4)";
      }
    }

    // Signal Quality Badge
    const elSigBadge = document.getElementById("cmdUwbSignalQualityBadge");
    if (elSigBadge) {
      elSigBadge.textContent = `QUALITY: ${sigQuality}`;
      if (sigQuality === "EXCELLENT") {
        elSigBadge.style.background = "rgba(16, 185, 129, 0.25)";
        elSigBadge.style.color = "#34d399";
        elSigBadge.style.borderColor = "rgba(16, 185, 129, 0.5)";
      } else if (sigQuality === "GOOD") {
        elSigBadge.style.background = "rgba(56, 189, 248, 0.2)";
        elSigBadge.style.color = "#38bdf8";
        elSigBadge.style.borderColor = "rgba(56, 189, 248, 0.4)";
      } else if (sigQuality === "DEGRADED") {
        elSigBadge.style.background = "rgba(234, 179, 8, 0.2)";
        elSigBadge.style.color = "#facc15";
        elSigBadge.style.borderColor = "rgba(234, 179, 8, 0.4)";
      } else if (sigQuality === "POOR") {
        elSigBadge.style.background = "rgba(249, 115, 22, 0.2)";
        elSigBadge.style.color = "#fb923c";
        elSigBadge.style.borderColor = "rgba(249, 115, 22, 0.4)";
      } else {
        elSigBadge.style.background = "rgba(239, 68, 68, 0.2)";
        elSigBadge.style.color = "#f87171";
        elSigBadge.style.borderColor = "rgba(239, 68, 68, 0.4)";
      }
    }

    // Simulation Seed Badge
    const elSeedBadge = document.getElementById("subSeedBadge");
    if (elSeedBadge && tel.simulation_seed !== undefined) {
      elSeedBadge.textContent = `Seed: #${tel.simulation_seed}`;
    }

    // Render Dynamic Soil Layer Strata Bar
    renderSubsurfaceLayerBar(tel.layer_strata || []);

    // Multi-Survivor Target Selector rendering
    const elMultiContainer = document.getElementById("subMultiTargetSelectorContainer");
    const elTargetCount = document.getElementById("subTargetCount");
    const elChipsList = document.getElementById("subTargetChipsList");

    if (elMultiContainer && elChipsList) {
      if (humanTargets.length > 1) {
        elMultiContainer.style.display = "flex";
        if (elTargetCount) elTargetCount.textContent = humanTargets.length;
        elChipsList.innerHTML = "";

        humanTargets.forEach(t => {
          const isSelected = selectedTarget && (t.target_id === selectedTarget.target_id);
          const triageCls = t.triage_class || "HIGH";
          const isCritOrHigh = triageCls === "CRITICAL" || triageCls === "HIGH";
          const isMed = triageCls === "MEDIUM";
          const triageBg = isCritOrHigh ? "rgba(220,38,38,0.1)" : (isMed ? "rgba(217,119,6,0.1)" : "rgba(22,163,74,0.1)");
          const triageCol = isCritOrHigh ? "#dc2626" : (isMed ? "#d97706" : "#16a34a");
          const triageBrd = isCritOrHigh ? "rgba(220,38,38,0.3)" : (isMed ? "rgba(217,119,6,0.3)" : "rgba(22,163,74,0.3)");

          const card = document.createElement("div");
          card.className = "sub-target-card";
          card.style.padding = "6px 8px";
          card.style.borderRadius = "6px";
          card.style.cursor = "pointer";
          card.style.transition = "all 0.15s ease";
          card.style.fontSize = "10px";
          card.style.fontFamily = "var(--font-mono, monospace)";

          if (isSelected) {
            card.style.background = "#eff6ff";
            card.style.border = "2px solid #2563eb";
            card.style.boxShadow = "0 1px 4px rgba(37,99,235,0.2)";
          } else {
            card.style.background = "#ffffff";
            card.style.border = "1px solid var(--border, #d3e1f5)";
            card.style.boxShadow = "0 1px 2px rgba(15,37,71,0.03)";
          }

          card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">
              <strong style="color: ${isSelected ? '#1d4ed8' : '#0f2547'}; font-size: 11px;">${isSelected ? '▶ ' : ''}${t.target_id}</strong>
              <span style="padding: 1px 4px; border-radius: 3px; font-size: 8px; font-weight: 700; color: ${triageCol}; background: ${triageBg}; border: 1px solid ${triageBrd};">${triageCls}</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2px 4px; font-size: 9px; color: var(--ink-dim, #4d5f80);">
              <div>Depth: <strong style="color: #2563eb;">${t.estimated_depth_m.toFixed(1)}m</strong></div>
              <div>Resp: <strong style="color: #16a34a;">${t.respiration_rate_rpm > 0 ? t.respiration_rate_rpm.toFixed(1) : '--'}</strong></div>
              <div>HR: <strong style="color: #dc2626;">${t.heart_rate_bpm > 0 ? t.heart_rate_bpm.toFixed(1) : '--'}</strong></div>
              <div>SNR: <strong style="color: #2563eb;">+${t.snr_db.toFixed(1)}dB</strong></div>
            </div>
            <div style="margin-top: 3px; font-size: 8px; color: var(--ink-faint, #64748b); display: flex; justify-content: space-between; align-items: center;">
              <span>Conf: ${Math.round((t.survivor_confidence || 0) * 100)}%</span>
              <span style="color: ${isSelected ? '#2563eb' : '#64748b'}; font-weight: ${isSelected ? '700' : '500'};">${isSelected ? '● ACTIVE' : 'Click to View'}</span>
            </div>
          `;

          card.addEventListener("click", () => {
            selectedSubsurfaceTargetId = t.target_id;
            if (subsurfaceTelemetry) {
              renderSubsurfaceUI({ telemetry: subsurfaceTelemetry, config: subsurfaceConfig });
            }
          });
          elChipsList.appendChild(card);
        });
      } else {
        elMultiContainer.style.display = "none";
        elChipsList.innerHTML = "";
      }
    }

    // Selected Survivor Banner Elements
    const elSelectedTargetId = document.getElementById("subSelectedTargetId");
    const elSelectedTargetType = document.getElementById("subSelectedTargetType");
    const elSelectedTargetTriage = document.getElementById("subSelectedTargetTriage");
    const elWaveformTargetLabel = document.getElementById("subWaveformTargetLabel");

    // Key Metrics Elements
    const elEstDepth = document.getElementById("subEstDepth");
    const elDepthUncert = document.getElementById("subDepthUncert");
    const elTrueDepth = document.getElementById("subTrueDepth");
    const elRespRate = document.getElementById("subRespRate");
    const elHeartRate = document.getElementById("subHeartRate");
    const elSnrDb = document.getElementById("subSnrDb");
    const elConfPct = document.getElementById("subConfPct");
    const elTriageBadge = document.getElementById("subTriageBadge");
    const elSpsVal = document.getElementById("subSpsVal");
    const elMicroMotion = document.getElementById("subMicroMotion");
    const elDepthGaugeText = document.getElementById("subDepthGaugeText");

    if (selectedTarget && selectedTarget.is_human && selectedTarget.survivor_confidence > 0.20) {
      if (elSelectedTargetId) elSelectedTargetId.textContent = selectedTarget.target_id;
      if (elSelectedTargetType) elSelectedTargetType.textContent = "MONITORED SURVIVOR";
      if (elSelectedTargetTriage) {
        const trClass = selectedTarget.triage_class || "HIGH";
        elSelectedTargetTriage.textContent = trClass;
        elSelectedTargetTriage.style.color = (trClass === "HIGH" || trClass === "CRITICAL") ? "#dc2626" : (trClass === "MEDIUM" ? "#d97706" : "#16a34a");
        elSelectedTargetTriage.style.background = (trClass === "HIGH" || trClass === "CRITICAL") ? "rgba(220, 38, 38, 0.1)" : (trClass === "MEDIUM" ? "rgba(217, 119, 6, 0.1)" : "rgba(22, 163, 74, 0.1)");
        elSelectedTargetTriage.style.borderColor = (trClass === "HIGH" || trClass === "CRITICAL") ? "rgba(220, 38, 38, 0.25)" : (trClass === "MEDIUM" ? "rgba(217, 119, 6, 0.25)" : "rgba(22, 163, 74, 0.25)");
      }
      if (elWaveformTargetLabel) elWaveformTargetLabel.textContent = selectedTarget.target_id;

      if (elEstDepth) elEstDepth.textContent = `${selectedTarget.estimated_depth_m.toFixed(2)} m`;
      if (elDepthUncert) elDepthUncert.textContent = `(±${selectedTarget.depth_uncertainty_m.toFixed(2)}m)`;
      if (elTrueDepth) elTrueDepth.textContent = `${selectedTarget.ground_truth_depth_m.toFixed(2)} m`;
      if (elRespRate) elRespRate.textContent = selectedTarget.respiration_rate_rpm > 0 ? selectedTarget.respiration_rate_rpm.toFixed(1) : "--";
      if (elHeartRate) elHeartRate.textContent = selectedTarget.heart_rate_bpm > 0 ? selectedTarget.heart_rate_bpm.toFixed(1) : "--";
      if (elMicroMotion) {
        elMicroMotion.textContent = selectedTarget.micro_motion_detected ? "● Micro-Motion Active" : "○ Low Motion";
        elMicroMotion.style.color = selectedTarget.micro_motion_detected ? "#16a34a" : "#94a3b8";
      }
      if (elDepthGaugeText) {
        elDepthGaugeText.textContent = `Est: ${selectedTarget.estimated_depth_m.toFixed(2)}m ±${selectedTarget.depth_uncertainty_m.toFixed(2)}m (${selectedTarget.target_id})`;
      }
      if (elSnrDb) elSnrDb.textContent = `+${(selectedTarget.snr_db !== undefined ? selectedTarget.snr_db : (tel.snr_db || 0)).toFixed(1)} dB`;
      if (elConfPct) elConfPct.textContent = `${Math.round((selectedTarget.survivor_confidence !== undefined ? selectedTarget.survivor_confidence * 100 : (tel.overall_confidence_pct || 0)))}%`;
      if (elTriageBadge) {
        elTriageBadge.textContent = selectedTarget.triage_class || tel.triage_class || "HIGH";
        const cls = selectedTarget.triage_class || tel.triage_class || "LOW";
        elTriageBadge.style.color = (cls === "HIGH" || cls === "CRITICAL") ? "#dc2626" : (cls === "MEDIUM" ? "#d97706" : "#16a34a");
        elTriageBadge.style.background = (cls === "HIGH" || cls === "CRITICAL") ? "rgba(220, 38, 38, 0.1)" : (cls === "MEDIUM" ? "rgba(217, 119, 6, 0.1)" : "rgba(22, 163, 74, 0.1)");
        elTriageBadge.style.borderColor = (cls === "HIGH" || cls === "CRITICAL") ? "rgba(220, 38, 38, 0.25)" : (cls === "MEDIUM" ? "rgba(217, 119, 6, 0.25)" : "rgba(22, 163, 74, 0.25)");
      }
    } else {
      if (elSelectedTargetId) elSelectedTargetId.textContent = "NO TARGET";
      if (elSelectedTargetType) elSelectedTargetType.textContent = "STANDBY";
      if (elSelectedTargetTriage) {
        elSelectedTargetTriage.textContent = "NO DETECTION";
        elSelectedTargetTriage.style.color = "#94a3b8";
        elSelectedTargetTriage.style.background = "rgba(148, 163, 184, 0.1)";
        elSelectedTargetTriage.style.borderColor = "rgba(148, 163, 184, 0.2)";
      }
      if (elWaveformTargetLabel) elWaveformTargetLabel.textContent = "NO TARGET";

      if (elEstDepth) elEstDepth.textContent = "NO TARGET";
      if (elDepthUncert) elDepthUncert.textContent = "";
      if (elTrueDepth) elTrueDepth.textContent = "--";
      if (elRespRate) elRespRate.textContent = "--";
      if (elHeartRate) elHeartRate.textContent = "--";
      if (elMicroMotion) elMicroMotion.textContent = "○ No Coherent Vitals";
      if (elDepthGaugeText) elDepthGaugeText.textContent = "NO RELIABLE SURVIVOR DETECTION";
      if (elSnrDb) elSnrDb.textContent = `+${(tel.snr_db || 0).toFixed(1)} dB`;
      if (elConfPct) elConfPct.textContent = `${Math.round(tel.overall_confidence_pct || 0)}%`;
      if (elTriageBadge) {
        elTriageBadge.textContent = tel.triage_class || "NO_VITAL_SIGNS";
        elTriageBadge.style.color = "#94a3b8";
        elTriageBadge.style.background = "rgba(148, 163, 184, 0.1)";
        elTriageBadge.style.borderColor = "rgba(148, 163, 184, 0.2)";
      }
    }

    if (elSpsVal) elSpsVal.textContent = (tel.sps_score || 0).toFixed(1);

    // Render Canvas Visualizations
    renderSubsurfaceRadargram(tel.radargram_profile || [], selectedTarget, humanTargets, tel.obstacles_detected || []);
    renderSubsurfaceDepthGauge(humanTargets, selectedTarget, tel.obstacles_detected || []);
    renderSubsurfaceWaveforms(tel.respiration_waveform || [], tel.cardiac_waveform || [], selectedTarget);
  }

  function renderSubsurfaceLayerBar(strata) {
    const bar = document.getElementById("subLayerStrataBar");
    if (!bar) return;
    if (!strata || strata.length === 0) {
      bar.innerHTML = `<div style="flex: 1; background: #334155; color: #cbd5e1; display: flex; align-items: center; justify-content: center;">0–6m UNIFORM MEDIUM</div>`;
      return;
    }
    const colorMap = {
      dry_soil: { bg: "#854d0e", text: "#fef08a" },
      sandy_soil: { bg: "#78350f", text: "#fde68a" },
      clay_soil: { bg: "#701a75", text: "#f5d0fe" },
      wet_soil: { bg: "#1e3a8a", text: "#93c5fd" },
      saturated_mud: { bg: "#14532d", text: "#86efac" },
      mixed_debris_soil: { bg: "#374151", text: "#e5e7eb" },
    };

    let html = "";
    strata.forEach((s, idx) => {
      const c = colorMap[s.soil_type] || { bg: "#1e293b", text: "#94a3b8" };
      const flexVal = Math.max(0.5, s.thickness_m);
      const borderLeft = idx > 0 ? "border-left: 1px solid #0f172a;" : "";
      html += `<div style="flex: ${flexVal}; background: ${c.bg}; color: ${c.text}; display: flex; align-items: center; justify-content: center; ${borderLeft}" title="${s.name} (${s.depth_start_m}m to ${s.depth_end_m}m)">${s.depth_start_m}–${s.depth_end_m}m ${s.soil_type.replace('_', ' ').toUpperCase()}</div>`;
    });
    bar.innerHTML = html;
  }

  function renderSubsurfaceRadargram(profile, selectedTarget, allTargets, obstacles) {
    const canvas = document.getElementById("subRadargramCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Grid lines (0 to 6.0 m)
    ctx.strokeStyle = "#e2ecfa";
    ctx.lineWidth = 1;
    for (let d = 1.0; d <= 6.0; d += 1.0) {
      const x = (d / 6.0) * w;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }

    // Selected Target Region Indicator (Subtle shaded column)
    if (selectedTarget && selectedTarget.estimated_depth_m > 0) {
      const xStart = Math.max(0, ((selectedTarget.estimated_depth_m - 0.25) / 6.0) * w);
      const xWidth = (0.5 / 6.0) * w;
      ctx.fillStyle = "rgba(37, 99, 235, 0.08)";
      ctx.fillRect(xStart, 0, xWidth, h);
    }

    ctx.strokeStyle = "#cbd5e1";
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();

    if (!profile || profile.length === 0) return;

    // Draw Raw Fast-Time Signal (Blue wave across 0-6m)
    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    for (let i = 0; i < profile.length; i++) {
      const p = profile[i];
      const x = (p.depth_m / 6.0) * w;
      const y = (h / 2) - p.raw_amplitude * (h * 0.4);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Draw Processed Envelope (Green curve across 0-6m)
    ctx.strokeStyle = "#16a34a";
    ctx.lineWidth = 2.0;
    ctx.beginPath();
    for (let i = 0; i < profile.length; i++) {
      const p = profile[i];
      const x = (p.depth_m / 6.0) * w;
      const y = h - 10 - p.processed_envelope * (h * 0.75);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Draw Obstacle Clutter Markers (Amber vertical dotted lines)
    if (obstacles && obstacles.length > 0) {
      obstacles.forEach(obs => {
        const ox = (obs.depth_m / 6.0) * w;
        ctx.strokeStyle = obs.is_metallic ? "#d97706" : "#64748b";
        ctx.lineWidth = 1.0;
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(ox, h / 2 - 25);
        ctx.lineTo(ox, h - 10);
        ctx.stroke();
        ctx.setLineDash([]);
      });
    }

    // Draw Secondary Target Echo Markers if multiple targets
    if (allTargets && allTargets.length > 1) {
      allTargets.forEach(t => {
        if (!selectedTarget || t.target_id !== selectedTarget.target_id) {
          const tx = (t.estimated_depth_m / 6.0) * w;
          ctx.strokeStyle = "#93c5fd";
          ctx.lineWidth = 1.2;
          ctx.setLineDash([2, 2]);
          ctx.beginPath();
          ctx.moveTo(tx, 0);
          ctx.lineTo(tx, h);
          ctx.stroke();
          ctx.setLineDash([]);

          ctx.fillStyle = "#64748b";
          ctx.font = "bold 9px JetBrains Mono, monospace";
          ctx.fillText(`${t.target_id}`, Math.min(w - 65, Math.max(4, tx - 15)), 28);
        }
      });
    }

    // Draw Selected Target Echo Peak Marker (Bold Red marker)
    if (selectedTarget && selectedTarget.is_human && selectedTarget.estimated_depth_m > 0) {
      const tx = (selectedTarget.estimated_depth_m / 6.0) * w;
      ctx.strokeStyle = "#dc2626";
      ctx.lineWidth = 2.0;
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      ctx.moveTo(tx, 0);
      ctx.lineTo(tx, h);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = "#dc2626";
      ctx.font = "bold 10px JetBrains Mono, monospace";
      ctx.fillText(`TARGET [${selectedTarget.target_id}]: ${selectedTarget.estimated_depth_m.toFixed(2)}m`, Math.min(w - 140, Math.max(4, tx - 30)), 14);
    }
  }

  function renderSubsurfaceDepthGauge(allTargets, selectedTarget, obstacles) {
    const canvas = document.getElementById("subDepthGaugeCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Soil column background gradient (0 to 6.0 m)
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "#f8fafc");
    grad.addColorStop(0.3, "#f1f5f9");
    grad.addColorStop(0.8, "#e2e8f0");
    grad.addColorStop(1, "#cbd5e1");
    ctx.fillStyle = grad;
    ctx.fillRect(40, 10, 36, h - 20);
    ctx.strokeStyle = "#94a3b8";
    ctx.strokeRect(40, 10, 36, h - 20);

    // Surface line (0m)
    ctx.fillStyle = "#16a34a";
    ctx.fillRect(38, 10, 40, 3);

    // Depth ticks (0m to 6.0m)
    ctx.fillStyle = "#475569";
    ctx.font = "9px JetBrains Mono, monospace";
    ctx.textAlign = "right";
    for (let d = 0.0; d <= 6.0; d += 1.0) {
      const y = 10 + (d / 6.0) * (h - 20);
      ctx.fillText(`${d.toFixed(0)}m`, 34, y + 3);
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(38, y);
      ctx.lineTo(44, y);
      ctx.stroke();
    }

    // Render Obstacles on Depth Gauge
    if (obstacles && obstacles.length > 0) {
      obstacles.forEach(obs => {
        const oy = 10 + (obs.depth_m / 6.0) * (h - 20);
        ctx.fillStyle = obs.is_metallic ? "#d97706" : "#64748b";
        ctx.beginPath();
        ctx.arc(58, Math.min(h - 12, Math.max(12, oy)), 2.5, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // Render other targets on depth gauge
    if (allTargets && allTargets.length > 0) {
      allTargets.forEach(t => {
        if (!selectedTarget || t.target_id !== selectedTarget.target_id) {
          const ty = 10 + (t.estimated_depth_m / 6.0) * (h - 20);
          ctx.fillStyle = "#93c5fd";
          ctx.beginPath();
          ctx.arc(58, Math.min(h - 12, Math.max(12, ty)), 3.5, 0, Math.PI * 2);
          ctx.fill();
        }
      });
    }

    if (selectedTarget && selectedTarget.is_human && selectedTarget.survivor_confidence > 0.20) {
      // Ground Truth Marker (Amber circle)
      const gtY = 10 + (selectedTarget.ground_truth_depth_m / 6.0) * (h - 20);
      ctx.fillStyle = "#d97706";
      ctx.beginPath();
      ctx.arc(58, Math.min(h - 12, Math.max(12, gtY)), 4, 0, Math.PI * 2);
      ctx.fill();

      // Estimated Depth Marker + Uncertainty Error Bar (Blue)
      const estY = 10 + (selectedTarget.estimated_depth_m / 6.0) * (h - 20);
      const uncertPx = (selectedTarget.depth_uncertainty_m / 6.0) * (h - 20);

      ctx.strokeStyle = "#2563eb";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(58, Math.max(10, estY - uncertPx));
      ctx.lineTo(58, Math.min(h - 10, estY + uncertPx));
      ctx.moveTo(50, Math.max(10, estY - uncertPx));
      ctx.lineTo(66, Math.max(10, estY - uncertPx));
      ctx.moveTo(50, Math.min(h - 10, estY + uncertPx));
      ctx.lineTo(66, Math.min(h - 10, estY + uncertPx));
      ctx.stroke();

      ctx.fillStyle = "#2563eb";
      ctx.beginPath();
      ctx.arc(58, Math.min(h - 12, Math.max(12, estY)), 5, 0, Math.PI * 2);
      ctx.fill();

      // Legend / Tag on right
      ctx.textAlign = "left";
      ctx.font = "bold 9px JetBrains Mono, monospace";
      ctx.fillStyle = "#2563eb";
      ctx.fillText(`● ${selectedTarget.target_id}`, 78, Math.min(h - 12, Math.max(12, estY - 2)));
      ctx.fillStyle = "#d97706";
      ctx.fillText(`★ GT`, 78, Math.min(h - 6, Math.max(20, gtY + 8)));
    }
  }

  function renderSubsurfaceWaveforms(respWave, cardWave, selectedTarget) {
    const canvas = document.getElementById("subWaveformsCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Center divider
    ctx.strokeStyle = "#e2ecfa";
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();

    // Respiration Waveform (Top half, green)
    if (respWave && respWave.length > 1) {
      ctx.strokeStyle = "#16a34a";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i < respWave.length; i++) {
        const x = (i / (respWave.length - 1)) * w;
        const y = (h * 0.25) - respWave[i] * (h * 0.22);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Cardiac Pulse Waveform (Bottom half, red)
    if (cardWave && cardWave.length > 1) {
      ctx.strokeStyle = "#dc2626";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i < cardWave.length; i++) {
        const x = (i / (cardWave.length - 1)) * w;
        const y = (h * 0.75) - cardWave[i] * (h * 0.22);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }

  function setupSubsurfaceControls() {
    const presetSelect = document.getElementById("subPresetSelect");
    const soilSelect = document.getElementById("subSoilTypeSelect");
    const moistureSlider = document.getElementById("subMoistureSlider");
    const moistureVal = document.getElementById("subMoistureVal");
    const depthSlider = document.getElementById("subDepthSlider");
    const depthVal = document.getElementById("subDepthVal");
    const btnDispatch = document.getElementById("subBtnDispatchRescue");

    if (presetSelect) {
      presetSelect.addEventListener("change", async () => {
        selectedSubsurfaceTargetId = null; // Reset selection so it defaults to primary of new preset
        const res = await apiPost("/api/subsurface/simulate", { preset_id: presetSelect.value });
        if (res) {
          if (moistureSlider) moistureSlider.value = res.config.soil_moisture_pct;
          if (moistureVal) moistureVal.textContent = `${res.config.soil_moisture_pct}%`;
          if (depthSlider) depthSlider.value = res.config.burial_depth_m;
          if (depthVal) depthVal.textContent = `${res.config.burial_depth_m.toFixed(1)} m`;
          if (soilSelect) soilSelect.value = res.config.soil_type;
          subsurfaceTelemetry = res.telemetry;
          subsurfaceConfig = res.config || subsurfaceConfig;
          renderSubsurfaceUI(res);
        }
      });
    }

    if (soilSelect) {
      soilSelect.addEventListener("change", async () => {
        const res = await apiPost("/api/subsurface/config", { soil_type: soilSelect.value });
        if (res) {
          subsurfaceTelemetry = res.telemetry;
          subsurfaceConfig = res.config || subsurfaceConfig;
          renderSubsurfaceUI(res);
        }
      });
    }

    if (moistureSlider) {
      moistureSlider.addEventListener("input", () => {
        if (moistureVal) moistureVal.textContent = `${moistureSlider.value}%`;
      });
      moistureSlider.addEventListener("change", async () => {
        const res = await apiPost("/api/subsurface/config", { soil_moisture_pct: parseFloat(moistureSlider.value) });
        if (res) {
          subsurfaceTelemetry = res.telemetry;
          subsurfaceConfig = res.config || subsurfaceConfig;
          renderSubsurfaceUI(res);
        }
      });
    }

    if (depthSlider) {
      depthSlider.addEventListener("input", () => {
        if (depthVal) depthVal.textContent = `${parseFloat(depthSlider.value).toFixed(1)} m`;
      });
      depthSlider.addEventListener("change", async () => {
        const res = await apiPost("/api/subsurface/config", { burial_depth_m: parseFloat(depthSlider.value) });
        if (res) {
          subsurfaceTelemetry = res.telemetry;
          subsurfaceConfig = res.config || subsurfaceConfig;
          renderSubsurfaceUI(res);
        }
      });
    }

    if (btnDispatch) {
      btnDispatch.addEventListener("click", () => {
        const assignSection = document.getElementById("cmdAssignFormPanel");
        if (assignSection) {
          assignSection.scrollIntoView({ behavior: "smooth" });
          showArrivalToast("🚨 Subsurface survivor prioritized for extraction. Select rescue team member below.");
        }
      });
    }
  }

  // ------------------------------------------------------------------ //
  // Commander Manual Assignment Form Handler (POST /commander/assign)
  // ------------------------------------------------------------------ //
  let cachedTeamMembers = [];
  let cachedVictims = [];

  const formScenario = document.getElementById("cmdFormScenario");
  const formTeam = document.getElementById("cmdFormTeam");
  const formMember = document.getElementById("cmdFormMember");
  const formVictim = document.getElementById("cmdFormVictim");
  const formAssignBtn = document.getElementById("cmdFormAssignBtn");
  const formResult = document.getElementById("cmdFormResult");
  const confirmBanner = document.getElementById("cmdConfirmBanner");
  const confirmText = document.getElementById("cmdConfirmText");

  function populateTeamDropdown(members, victims = []) {
    cachedTeamMembers = members || [];
    if (victims && victims.length > 0) cachedVictims = victims;

    if (formScenario) {
      formScenario.value = scenarioName || (mapState.scenarioMeta && mapState.scenarioMeta.scenario_name) || "Active Operation";
    }

    if (!formTeam) return;

    // Collect unique team IDs
    const teamsSet = new Set();
    cachedTeamMembers.forEach(m => { if (m.team_id) teamsSet.add(m.team_id); });
    const teams = Array.from(teamsSet);

    const currentTeamVal = formTeam.value;
    formTeam.innerHTML = '<option value="">Select team…</option>';
    teams.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t;
      const teamLabel = t === "ALPHA" ? "Rescue Team Alpha" : t === "BRAVO" ? "Rescue Team Bravo" : t === "CHARLIE" ? "Rescue Team Charlie" : `Rescue Team ${t}`;
      opt.textContent = teamLabel;
      formTeam.appendChild(opt);
    });

    if (currentTeamVal && teams.includes(currentTeamVal)) {
      formTeam.value = currentTeamVal;
    }
  }

  function setupAssignFormListeners() {
    if (!formTeam || !formMember || !formVictim || !formAssignBtn) return;

    formTeam.addEventListener("change", () => {
      const selectedTeam = formTeam.value;
      formMember.innerHTML = '<option value="">Select member…</option>';
      formVictim.innerHTML = '<option value="">Select member first…</option>';
      formVictim.disabled = true;
      formAssignBtn.disabled = true;
      if (confirmBanner) confirmBanner.hidden = true;

      if (!selectedTeam) {
        formMember.disabled = true;
        return;
      }

      const teamMems = cachedTeamMembers.filter(m => m.team_id === selectedTeam);
      teamMems.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.member_id;
        opt.textContent = `${m.callsign || m.name} (${(m.status || "").toUpperCase()})`;
        opt.dataset.status = m.status;
        formMember.appendChild(opt);
      });
      formMember.disabled = false;
    });

    formMember.addEventListener("change", () => {
      const selectedMemberId = formMember.value;
      formVictim.innerHTML = '<option value="">Select survivor / victim…</option>';
      formAssignBtn.disabled = true;

      if (!selectedMemberId) {
        formVictim.disabled = true;
        if (confirmBanner) confirmBanner.hidden = true;
        return;
      }

      const mem = cachedTeamMembers.find(m => m.member_id === selectedMemberId);
      if (mem && mem.status !== "hold") {
        if (confirmBanner) {
          confirmBanner.hidden = false;
          if (confirmText) confirmText.textContent = `Member ${mem.callsign} is currently ${mem.status.toUpperCase()}. Assigning will override active task.`;
        }
      } else {
        if (confirmBanner) confirmBanner.hidden = true;
      }

      // Populate victims
      const availableVictims = mapState.lastVictims || cachedVictims || [];
      availableVictims.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.victim_id;
        opt.textContent = `${v.label || v.victim_id} (${v.priority || v.triage_category || 'URGENT'})`;
        formVictim.appendChild(opt);
      });
      formVictim.disabled = false;
    });

    formVictim.addEventListener("change", () => {
      const hasMember = Boolean(formMember.value);
      const hasVictim = Boolean(formVictim.value);
      formAssignBtn.disabled = !(hasMember && hasVictim);
    });

    formAssignBtn.addEventListener("click", async () => {
      const memberId = formMember.value;
      const victimId = formVictim.value;
      if (!memberId || !victimId) return;

      formAssignBtn.disabled = true;
      formAssignBtn.textContent = "⏳ Dispatching GO Command…";
      if (formResult) {
        formResult.textContent = "Creating backend rescue command...";
        formResult.className = "admin-result";
      }

      try {
        const res = await apiPost("/commander/assign", {
          member_id: memberId,
          victim_id: victimId,
        });

        if (formResult) {
          formResult.textContent = `✅ Rescue command dispatched: ${res.callsign || memberId} ➔ ${victimId} (Status: ${res.status.toUpperCase()})`;
          formResult.className = "admin-result success";
        }
        formAssignBtn.textContent = "✅ Confirm & Assign";
        formAssignBtn.disabled = false;

        // Immediate refresh
        poll();
      } catch (err) {
        if (formResult) {
          formResult.textContent = `❌ Assignment failed: ${err.message}`;
          formResult.className = "admin-result error";
        }
        formAssignBtn.textContent = "✅ Confirm & Assign";
        formAssignBtn.disabled = false;
      }
    });
  }

  // ------------------------------------------------------------------ //
  // Main Polling Loop
  // ------------------------------------------------------------------ //

  async function poll() {
    try {
      const res = await fetch(`${apiBase}/commander/overview`);
      if (res.ok) {
        const data = await res.json();
        if (data.scenario && data.scenario.site_origin) {
          SITE_ORIGIN = data.scenario.site_origin;
        }
        scenarioName = (data.scenario && data.scenario.scenario_name) || null;
        mapState.scenarioMeta = data.scenario || null;

        renderMap(data.victims || [], data.team_members || [], data.jobs || []);
        renderMemberList(data.team_members || []);
        populateTeamDropdown(data.team_members || [], data.victims || []);

        // Update Live Alpha Member 1 HUD status & dedicated telemetry card
        const a1 = (data.team_members || []).find(m => m.member_id === "ALPHA-M001");
        updateAlpha1LiveCard(a1);

        const navEl = document.getElementById("cmdAlpha1GpsNavText");
        if (navEl) {
          if (a1 && (a1.location_source === "PHONE_GPS" || a1.member_id === "ALPHA-M001")) {
            const gpsStatus = a1.gps_status || "STANDBY";
            const navStatus = a1.navigation_status || (a1.status === "arrived" ? "ARRIVED" : (a1.status === "en_route" ? "ON_TRACK" : "EN_ROUTE"));
            const distStr = a1.distance_to_target_m != null ? `${a1.distance_to_target_m.toFixed(0)}m` : "--";
            const statusColor = gpsStatus === "STALE" ? "#f59e0b" : (navStatus === "ARRIVED" ? "#22c55e" : (navStatus === "WRONG_DIRECTION" ? "#ef4444" : "#00f0ff"));
            navEl.textContent = `Alpha 1 [REAL GPS]: ${gpsStatus} | 🧭 ${a1.heading_deg != null ? a1.heading_deg.toFixed(0) + "°" : "--"} | 🎯 ${navStatus} (${distStr})`;
            navEl.style.color = statusColor;
          } else {
            navEl.textContent = "Alpha 1: GPS STANDBY";
            navEl.style.color = "#94a3b8";
          }
        }

        for (const arrived of (data.newly_arrived || [])) {
          showArrivalToast(`✅ ${arrived.callsign} reached ${arrived.assigned_victim_id}!`);
        }
      }

      await pollPressureTelemetry();
      await pollLandslideTelemetry();
      await pollCameraThermalTelemetry();
      await pollRainfallTelemetry();
      await pollSubsurfaceTelemetry();
      await pollWearableBadges();
    } catch (e) {
      /* transient poll failure — retry next cycle */
    }
    setTimeout(poll, POLL_MS);
  }

  async function pollWearableBadges() {
    try {
      const res = await fetch(`${apiBase}/api/wearable/devices`);
      if (!res.ok) return;
      const data = await res.json();
      const bBridge = document.getElementById("badgeCmdBridge");
      const bCallPlus = document.getElementById("badgeCmdCallPlus");
      if (bBridge) {
        bBridge.textContent = "📲 BRIDGE: ONLINE";
        bBridge.style.color = "#38bdf8";
      }
      if (data.devices && bCallPlus) {
        const dev = data.devices.find((d) => d.device_id === "DEV-WEARABLE-CALLPLUS") || data.devices[0];
        if (dev) {
          const isConn = dev.connection_status === "CONNECTED";
          bCallPlus.textContent = `⌚ WAVE CALL PLUS: ${dev.connection_status || "STANDBY"}`;
          bCallPlus.style.color = isConn ? "#34d399" : "#94a3b8";
        }
      }
    } catch (e) {
      const bBridge = document.getElementById("badgeCmdBridge");
      if (bBridge) {
        bBridge.textContent = "📲 BRIDGE: OFFLINE";
        bBridge.style.color = "#ef4444";
      }
    }
  }

  // Initialize interactivity and start polling
  setupMapInteractivity();
  setupAssignFormListeners();
  setupSubsurfaceControls();
  poll();
})();
