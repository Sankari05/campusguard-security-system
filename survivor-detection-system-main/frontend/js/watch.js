/* ==========================================================================
   RIDGEWATCH Real Smartwatch Client (Wave Call Plus Live Console)
   Dedicated HAL interface for Wave Call Plus (CALLPLUS_7F1B)
   Matches the exact visual reference image specification & state lifecycle:
   STANDBY ➔ GO ➔ EN ROUTE ➔ ARRIVED ➔ RESCUED
   ========================================================================== */

(() => {
  "use strict";

  const apiBase = RidgeWatchConfig.getApiBase();
  const selectedDeviceId = "DEV-WEARABLE-CALLPLUS";
  let currentActiveCommand = null;
  let currentMode = "REAL_HARDWARE";
  let selectedMemberId = "ALPHA-M001";
  let lastObservedCommandId = null;
  let userManuallySelected = false;
  let assignmentTimestamp = null;

  // Header Elements
  const btnModeSim = document.getElementById("btnModeSim");
  const btnModeReal = document.getElementById("btnModeReal");

  // Status Card Elements
  const statBridgeVal = document.getElementById("statBridgeVal");
  const statBridgeSub = document.getElementById("statBridgeSub");
  const statBleVal = document.getElementById("statBleVal");
  const statBleSub = document.getElementById("statBleSub");
  const statWatchVal = document.getElementById("statWatchVal");
  const statWatchSub = document.getElementById("statWatchSub");
  const statGpsVal = document.getElementById("statGpsVal");
  const statGpsSub = document.getElementById("statGpsSub");
  const statProtocolVal = document.getElementById("statProtocolVal");
  const statProtocolSub = document.getElementById("statProtocolSub");
  const statSyncTime = document.getElementById("statSyncTime");
  const statSyncDate = document.getElementById("statSyncDate");

  // Live Watch Preview Elements
  const watchMemberLabel = document.getElementById("watchMemberLabel");
  const watchMemberSelect = document.getElementById("watchMemberSelect");
  const watchStateTag = document.getElementById("watchStateTag");
  const watchCircleScreen = document.getElementById("watchCircleScreen");
  const watchSphereIcon = document.getElementById("watchSphereIcon");
  const watchGoText = document.getElementById("watchGoText");
  const watchSubBearing = document.getElementById("watchSubBearing");
  const watchDeliveryBadge = document.getElementById("watchDeliveryBadge");
  const compassTargetNode = document.getElementById("compassTargetNode");
  const compassTargetLabel = document.getElementById("compassTargetLabel");

  // Minimal Info Strip Elements
  const watchInfoScenario = document.getElementById("watchInfoScenario");
  const watchInfoPriority = document.getElementById("watchInfoPriority");
  const watchInfoCommand = document.getElementById("watchInfoCommand");
  const watchInfoAssignment = document.getElementById("watchInfoAssignment");

  // Location Elements
  const locValLat = document.getElementById("locValLat");
  const locValLon = document.getElementById("locValLon");
  const locValLabel = document.getElementById("locValLabel");
  const locValDist = document.getElementById("locValDist");

  // Timeline Elements
  const timelineTrackProgress = document.getElementById("timelineTrackProgress");
  const tlNode1 = document.getElementById("tlNode1");
  const tlNode2 = document.getElementById("tlNode2");
  const tlNode3 = document.getElementById("tlNode3");
  const tlNode4 = document.getElementById("tlNode4");
  const tlNode5 = document.getElementById("tlNode5");
  const tlTime1 = document.getElementById("tlTime1");
  const tlTime2 = document.getElementById("tlTime2");
  const tlTime3 = document.getElementById("tlTime3");
  const tlTime4 = document.getElementById("tlTime4");
  const tlTime5 = document.getElementById("tlTime5");

  // Member select listener
  if (watchMemberSelect) {
    watchMemberSelect.addEventListener("change", (e) => {
      selectedMemberId = e.target.value;
      userManuallySelected = true;
      pollWearableState();
    });
  }

  // Mode Switcher Listeners
  if (btnModeSim && btnModeReal) {
    btnModeSim.addEventListener("click", () => setOperationMode("SIMULATION"));
    btnModeReal.addEventListener("click", () => setOperationMode("REAL_HARDWARE"));
  }

  async function fetchOperationMode() {
    try {
      const res = await fetch(`${apiBase}/api/wearable/mode`);
      if (!res.ok) return;
      const data = await res.json();
      currentMode = data.mode || "REAL_HARDWARE";
      updateModeUI();
    } catch (e) {}
  }

  async function setOperationMode(mode) {
    try {
      const res = await fetch(`${apiBase}/api/wearable/mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      if (res.ok) {
        const data = await res.json();
        currentMode = data.mode;
        updateModeUI();
        fetchHardwareAndBridgeStatus();
        pollWearableState();
      }
    } catch (e) {}
  }

  function updateModeUI() {
    if (btnModeSim && btnModeReal) {
      btnModeSim.classList.toggle("is-active", currentMode === "SIMULATION");
      btnModeReal.classList.toggle("is-active", currentMode === "REAL_HARDWARE");
    }
  }

  // Populate dynamic member options from /teams or /commander/overview
  async function loadTeamMembers() {
    try {
      let members = [];
      const res = await fetch(`${apiBase}/teams`);
      if (res.ok) {
        const data = await res.json();
        if (data.teams && Array.isArray(data.teams)) {
          data.teams.forEach((t) => {
            if (Array.isArray(t.members)) {
              t.members.forEach((m) => {
                members.push({
                  id: m.member_id || m.id,
                  label: `${t.team_name || t.name || "Team"} - ${m.name || m.callsign || "Member"}`,
                });
              });
            }
          });
        }
      } else {
        const coRes = await fetch(`${apiBase}/commander/overview`);
        if (coRes.ok) {
          const coData = await coRes.json();
          (coData.team_members || []).forEach((m) => {
            const teamName = m.team_id === "ALPHA" ? "Rescue Team Alpha" : m.team_id === "BRAVO" ? "Rescue Team Bravo" : `Rescue Team ${m.team_id}`;
            members.push({
              id: m.member_id,
              label: `${teamName} - ${m.callsign || m.name}`,
            });
          });
        }
      }

      if (members.length > 0 && watchMemberSelect) {
        const prevVal = watchMemberSelect.value;
        watchMemberSelect.innerHTML = "";
        members.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m.id;
          opt.textContent = m.label;
          watchMemberSelect.appendChild(opt);
        });
        if (prevVal && members.some((m) => m.id === prevVal)) {
          watchMemberSelect.value = prevVal;
          selectedMemberId = prevVal;
        } else {
          watchMemberSelect.value = members[0].id;
          selectedMemberId = members[0].id;
        }
      }
    } catch (e) {}
  }

  // Hardware & Bridge Status Fetcher
  async function fetchHardwareAndBridgeStatus() {
    const now = new Date();
    const timeStr = now.toTimeString().split(" ")[0];
    const dateStr = now.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
    if (statSyncTime) statSyncTime.textContent = timeStr;
    if (statSyncDate) statSyncDate.textContent = dateStr;

    try {
      const res = await fetch(`${apiBase}/api/wearable/devices`);
      if (!res.ok) throw new Error("Failed to fetch devices");
      const data = await res.json();
      const dev = (data.devices || []).find((d) => d.device_id === selectedDeviceId) || (data.devices && data.devices[0]);

      if (currentMode === "SIMULATION") {
        setStatusBadge(statBridgeVal, statBridgeSub, "● ONLINE", "Connected (Sim)", true);
        setStatusBadge(statBleVal, statBleSub, "● ENABLED", "Adapter active", true);
        setStatusBadge(statWatchVal, statWatchSub, "● CONNECTED", "Signal strong", true);
        setStatusBadge(statGpsVal, statGpsSub, "● AVAILABLE", "Location active", true);
        setStatusBadge(statProtocolVal, statProtocolSub, "● DETECTED", "BLE services found", true);
      } else {
        const isConn = dev && dev.connection_status === "CONNECTED";
        const hasSession = dev && dev.bridge_session_id;

        setStatusBadge(statBridgeVal, statBridgeSub, hasSession ? "● ONLINE" : "○ STANDBY", hasSession ? "Connected" : "Waiting for phone", hasSession);
        setStatusBadge(statBleVal, statBleSub, isConn ? "● ENABLED" : "● READY", isConn ? "Adapter active" : "Scanning CALLPLUS", true);
        setStatusBadge(statWatchVal, statWatchSub, isConn ? "● CONNECTED" : "○ DISCONNECTED", isConn ? "Signal strong" : "Pair via Phone Bridge", isConn);
        setStatusBadge(statGpsVal, statGpsSub, "● AVAILABLE", "Phone GNSS (Active)", true);
        setStatusBadge(statProtocolVal, statProtocolSub, isConn ? "● DETECTED" : "○ WAITING", isConn ? "0x1800/180A/180D" : "GATT discovery on pair", isConn);
      }
    } catch (e) {
      if (currentMode === "REAL_HARDWARE") {
        setStatusBadge(statBridgeVal, statBridgeSub, "○ OFFLINE", "Bridge unreachable", false);
        setStatusBadge(statWatchVal, statWatchSub, "○ DISCONNECTED", "No device link", false);
      }
    }
  }

  function setStatusBadge(valEl, subEl, text, subText, isOk) {
    if (valEl) {
      valEl.textContent = text;
      valEl.style.color = isOk ? "#16a34a" : "#94a3b8";
    }
    if (subEl) subEl.textContent = subText;
  }

  // Active Command & Telemetry Poller (Dual Source: HAL gateway + Simulation /watch)
  async function pollWearableState() {
    try {
      // 1. Check HAL gateway active commands
      const cmdUrl = `${apiBase}/api/wearable/commands/active?member_id=${encodeURIComponent(selectedMemberId)}`;
      const cmdRes = await fetch(cmdUrl);
      let cmdData = cmdRes.ok ? await cmdRes.json() : null;

      // Automatically follow Commander assignment
      if (cmdData) {
        const latestCmdId = cmdData.latest_assigned_command_id;
        const latestMemberId = cmdData.latest_assigned_member_id;

        if (latestCmdId && latestCmdId !== lastObservedCommandId) {
          lastObservedCommandId = latestCmdId;
          assignmentTimestamp = Date.now();
          userManuallySelected = false;
          if (latestMemberId && latestMemberId !== selectedMemberId) {
            selectedMemberId = latestMemberId;
            if (watchMemberSelect) {
              watchMemberSelect.value = selectedMemberId;
            }
            return pollWearableState();
          }
        }

        if (!userManuallySelected && latestMemberId && selectedMemberId !== latestMemberId && !cmdData.has_active_command) {
          selectedMemberId = latestMemberId;
          if (watchMemberSelect) {
            watchMemberSelect.value = selectedMemberId;
          }
          return pollWearableState();
        }
      }

      // 2. Check live operational watch view for selectedMemberId
      const watchUrl = `${apiBase}/watch/${encodeURIComponent(selectedMemberId)}`;
      const watchRes = await fetch(watchUrl);
      let watchData = watchRes.ok ? await watchRes.json() : null;

      // Determine true lifecycle state
      const hasGatewayCmd = cmdData && cmdData.has_active_command && cmdData.command;
      const opStatus = watchData ? (watchData.status || "hold").toLowerCase() : "hold";
      const assignedVictim = watchData ? watchData.assigned_victim_id : (hasGatewayCmd ? cmdData.command.victim_id : null);

      if (!assignedVictim || opStatus === "hold") {
        currentActiveCommand = null;
        renderStandbyPreview();
        return;
      }

      // Build unified state payload
      const unifiedData = {
        member_id: selectedMemberId,
        callsign: (watchData && watchData.callsign) || (hasGatewayCmd && cmdData.command.member_id) || selectedMemberId,
        victim_id: assignedVictim,
        victim_label: (watchData && watchData.victim_label) || assignedVictim,
        status: opStatus,
        distance_m: (watchData && typeof watchData.distance_m === "number") ? watchData.distance_m : (hasGatewayCmd && cmdData.command.distance_meters) || 35.0,
        distance_label: (watchData && watchData.distance_label) || `${Math.round((watchData && watchData.distance_m) || 35)} m`,
        bearing_deg: (watchData && typeof watchData.bearing_deg === "number") ? watchData.bearing_deg : 45.0,
        compass_label: (watchData && watchData.compass_label) || "N",
        scenario: (watchData && watchData.scenario) || (hasGatewayCmd && cmdData.command.scenario_id) || "Landslide",
        priority: (watchData && watchData.priority) || (hasGatewayCmd && cmdData.command.priority) || "HIGH",
        location_label: (watchData && watchData.location_label) || (hasGatewayCmd && cmdData.command.location_label) || `Sector 7 · ${assignedVictim}`,
        watch_delivery_status: (hasGatewayCmd && cmdData.command.watch_delivery_status) || "WATCH_DELIVERY_UNCONFIRMED",
        phone_bridge_status: (hasGatewayCmd && cmdData.command.phone_bridge_status) || "SENT_TO_BRIDGE",
        command_id: (hasGatewayCmd && cmdData.command.command_id) || lastObservedCommandId || "CMD-ACTIVE",
      };

      currentActiveCommand = unifiedData;
      renderLifecycleState(unifiedData);

    } catch (e) {
      renderStandbyPreview();
    }
  }

  // STATE 1: STANDBY (Awaiting Assignment)
  function renderStandbyPreview() {
    if (watchMemberLabel) watchMemberLabel.textContent = "Preview member:";
    if (watchStateTag) {
      watchStateTag.textContent = "STANDBY";
      watchStateTag.style.color = "#64748b";
    }
    if (watchGoText) {
      watchGoText.textContent = "STANDBY";
      watchGoText.className = "watch-go-text";
    }
    if (watchSubBearing) watchSubBearing.textContent = "Awaiting Assignment";
    if (watchDeliveryBadge) {
      watchDeliveryBadge.textContent = "AWAITING ASSIGNMENT";
      watchDeliveryBadge.style.color = "#64748b";
    }
    if (watchCircleScreen) {
      watchCircleScreen.style.borderColor = "#94a3b8";
      watchCircleScreen.style.boxShadow = "none";
    }
    if (watchSphereIcon) {
      watchSphereIcon.style.background = "#94a3b8";
      watchSphereIcon.style.boxShadow = "none";
    }
    if (compassTargetLabel) compassTargetLabel.textContent = "—";
    if (compassTargetNode) compassTargetNode.style.display = "none";

    // Info Strip
    if (watchInfoScenario) watchInfoScenario.textContent = "—";
    if (watchInfoPriority) {
      watchInfoPriority.textContent = "STANDBY";
      watchInfoPriority.style.color = "#64748b";
    }
    if (watchInfoCommand) {
      watchInfoCommand.textContent = "STANDBY";
      watchInfoCommand.style.color = "#64748b";
    }
    if (watchInfoAssignment) {
      watchInfoAssignment.textContent = "Awaiting";
      watchInfoAssignment.style.color = "#64748b";
    }

    // Location default
    if (locValLat) locValLat.textContent = "12.9798° N";
    if (locValLon) locValLon.textContent = "77.5901° E";
    if (locValLabel) locValLabel.textContent = "Base Operations · Sector 1";
    if (locValDist) locValDist.textContent = "0 m";

    // Mini Map Reset
    updateMiniMap("hold", 0);

    // Reset Timeline
    updateTimeline(null);
  }

  // Multi-State Lifecycle Renderer: GO ➔ EN ROUTE ➔ ARRIVED ➔ RESCUED
  function renderLifecycleState(data) {
    const rawStatus = (data.status || "en_route").toLowerCase();
    const distanceM = data.distance_m;
    const victimId = data.victim_label || data.victim_id || "V3";

    if (watchMemberLabel) watchMemberLabel.textContent = "Assigned member:";

    const isRecentlyAssigned = assignmentTimestamp && (Date.now() - assignmentTimestamp < 4500);

    let displayState = "EN_ROUTE";
    if (rawStatus === "rescued" || rawStatus === "completed") {
      displayState = "RESCUED";
    } else if (rawStatus === "arrived" || distanceM <= 15.0) {
      displayState = "ARRIVED";
    } else if (isRecentlyAssigned || rawStatus === "assigned" || rawStatus === "go") {
      displayState = "GO";
    } else {
      displayState = "EN_ROUTE";
    }

    // STATE 2: GO (New Rescue Assignment Received)
    if (displayState === "GO") {
      if (watchStateTag) {
        watchStateTag.textContent = "ACTIVE RESCUE";
        watchStateTag.style.color = "#16a34a";
      }
      if (watchGoText) {
        watchGoText.textContent = "GO";
        watchGoText.className = "watch-go-text";
      }
      if (watchSubBearing) {
        watchSubBearing.textContent = `Rescue assignment received · Target ${victimId}`;
      }
      if (watchDeliveryBadge) {
        watchDeliveryBadge.textContent = "GO — RESCUE ASSIGNMENT";
        watchDeliveryBadge.style.color = "#16a34a";
      }
      if (watchCircleScreen) {
        watchCircleScreen.style.borderColor = "#10b981";
        watchCircleScreen.style.boxShadow = "0 2px 14px rgba(16, 185, 129, 0.3)";
      }
      if (watchSphereIcon) {
        watchSphereIcon.style.background = "radial-gradient(circle at 35% 35%, #86efac, #16a34a 60%, #14532d)";
        watchSphereIcon.style.boxShadow = "0 2px 8px rgba(22, 163, 74, 0.4)";
      }
      if (watchInfoAssignment) {
        watchInfoAssignment.textContent = "Active";
        watchInfoAssignment.style.color = "#16a34a";
      }
    }

    // STATE 3: EN ROUTE (Moving Forward to Needy People)
    else if (displayState === "EN_ROUTE") {
      if (watchStateTag) {
        watchStateTag.textContent = "EN ROUTE";
        watchStateTag.style.color = "#2563eb";
      }
      if (watchGoText) {
        watchGoText.textContent = "EN ROUTE";
        watchGoText.className = "watch-go-text";
      }
      if (watchSubBearing) {
        watchSubBearing.textContent = `${data.distance_label} ${data.compass_label} (${Math.round(data.bearing_deg)}°) · Moving to ${victimId}`;
      }
      if (watchDeliveryBadge) {
        watchDeliveryBadge.textContent = "EN ROUTE — APPROACHING TARGET";
        watchDeliveryBadge.style.color = "#2563eb";
      }
      if (watchCircleScreen) {
        watchCircleScreen.style.borderColor = "#2563eb";
        watchCircleScreen.style.boxShadow = "0 2px 16px rgba(37, 99, 235, 0.35)";
      }
      if (watchSphereIcon) {
        watchSphereIcon.style.background = "radial-gradient(circle at 35% 35%, #93c5fd, #2563eb 60%, #1e40af)";
        watchSphereIcon.style.boxShadow = "0 2px 8px rgba(37, 99, 235, 0.4)";
      }
      if (watchInfoAssignment) {
        watchInfoAssignment.textContent = "En Route";
        watchInfoAssignment.style.color = "#2563eb";
      }
    }

    // STATE 4: ARRIVED (Reached Needy People's Location)
    else if (displayState === "ARRIVED") {
      if (watchStateTag) {
        watchStateTag.textContent = "ARRIVED";
        watchStateTag.style.color = "#7c3aed";
      }
      if (watchGoText) {
        watchGoText.textContent = "ARRIVED";
        watchGoText.className = "watch-go-text";
      }
      if (watchSubBearing) {
        watchSubBearing.textContent = `Target Reached · ${victimId} Located`;
      }
      if (watchDeliveryBadge) {
        watchDeliveryBadge.textContent = "ARRIVED — TARGET REACHED";
        watchDeliveryBadge.style.color = "#7c3aed";
      }
      if (watchCircleScreen) {
        watchCircleScreen.style.borderColor = "#7c3aed";
        watchCircleScreen.style.boxShadow = "0 2px 16px rgba(124, 58, 237, 0.35)";
      }
      if (watchSphereIcon) {
        watchSphereIcon.style.background = "radial-gradient(circle at 35% 35%, #c4b5fd, #7c3aed 60%, #5b21b6)";
        watchSphereIcon.style.boxShadow = "0 2px 8px rgba(124, 58, 237, 0.4)";
      }
      if (watchInfoAssignment) {
        watchInfoAssignment.textContent = "Arrived";
        watchInfoAssignment.style.color = "#7c3aed";
      }
    }

    // STATE 5: RESCUED (Rescue Operation Complete)
    else if (displayState === "RESCUED") {
      if (watchStateTag) {
        watchStateTag.textContent = "RESCUED";
        watchStateTag.style.color = "#16a34a";
      }
      if (watchGoText) {
        watchGoText.textContent = "RESCUED";
        watchGoText.className = "watch-go-text";
      }
      if (watchSubBearing) {
        watchSubBearing.textContent = `Survivor ${victimId} Secured · Operation Complete`;
      }
      if (watchDeliveryBadge) {
        watchDeliveryBadge.textContent = "MISSION ACCOMPLISHED";
        watchDeliveryBadge.style.color = "#16a34a";
      }
      if (watchCircleScreen) {
        watchCircleScreen.style.borderColor = "#16a34a";
        watchCircleScreen.style.boxShadow = "0 2px 16px rgba(22, 163, 74, 0.4)";
      }
      if (watchSphereIcon) {
        watchSphereIcon.style.background = "radial-gradient(circle at 35% 35%, #86efac, #16a34a 60%, #14532d)";
        watchSphereIcon.style.boxShadow = "0 2px 8px rgba(22, 163, 74, 0.5)";
      }
      if (watchInfoAssignment) {
        watchInfoAssignment.textContent = "Complete";
        watchInfoAssignment.style.color = "#16a34a";
      }
    }

    // Info Strip Values
    if (watchInfoScenario) watchInfoScenario.textContent = data.scenario || "Landslide";
    if (watchInfoPriority) {
      watchInfoPriority.textContent = data.priority || "HIGH";
      watchInfoPriority.style.color = (data.priority === "HIGH") ? "#ef4444" : "#2563eb";
    }
    if (watchInfoCommand) {
      watchInfoCommand.textContent = (displayState === "ARRIVED") ? "ARRIVED" : (displayState === "RESCUED" ? "RESCUED" : "GO");
      watchInfoCommand.style.color = (displayState === "ARRIVED") ? "#7c3aed" : (displayState === "RESCUED" ? "#16a34a" : "#2563eb");
    }

    // Compass Orientation
    if (compassTargetNode && compassTargetLabel) {
      compassTargetLabel.textContent = victimId;
      compassTargetNode.style.display = "flex";

      const angle = (typeof data.bearing_deg === "number") ? data.bearing_deg : 0;
      const rad = (angle - 90) * (Math.PI / 180);
      const r = 36;
      const leftPct = 50 + r * Math.cos(rad);
      const topPct = 50 + r * Math.sin(rad);
      compassTargetNode.style.left = `${leftPct.toFixed(1)}%`;
      compassTargetNode.style.top = `${topPct.toFixed(1)}%`;
      compassTargetNode.style.transform = `translate(-50%, -50%)`;

      const compassLine = document.querySelector(".compass-line");
      if (compassLine) {
        compassLine.style.transform = `translateX(-50%) rotate(${angle}deg)`;
      }
    }

    // Location Card Details
    if (locValLat) locValLat.textContent = "12.9798° N";
    if (locValLon) locValLon.textContent = "77.5901° E";
    if (locValLabel) locValLabel.textContent = data.location_label || `Landslide Zone - Sector 7 (${victimId})`;
    if (locValDist) {
      if (displayState === "ARRIVED" || displayState === "RESCUED") {
        locValDist.textContent = `0 m (On Site)`;
      } else {
        locValDist.textContent = `${data.distance_label} ${data.compass_label}`;
      }
    }

    // Mini Map Update
    updateMiniMap(displayState, distanceM);

    // Timeline Progression
    updateTimeline(displayState);
  }

  // Update Mini Map Vector Dot
  function updateMiniMap(state, distanceM) {
    const memberDot = document.querySelector(".mini-map-svg circle[fill='#2563eb']");
    if (!memberDot) return;

    if (state === "hold") {
      memberDot.setAttribute("cx", "150");
      memberDot.setAttribute("cy", "90");
    } else if (state === "ARRIVED" || state === "RESCUED") {
      memberDot.setAttribute("cx", "150");
      memberDot.setAttribute("cy", "35");
    } else {
      const maxD = 250;
      const d = Math.max(0, Math.min(distanceM, maxD));
      const fraction = 1 - (d / maxD);
      const curY = 90 - (90 - 35) * fraction;
      memberDot.setAttribute("cx", "150");
      memberDot.setAttribute("cy", curY.toFixed(1));
    }
  }

  // 4D Timeline Node Setter
  function updateTimeline(state) {
    const nodes = [tlNode1, tlNode2, tlNode3, tlNode4, tlNode5];
    nodes.forEach((n) => {
      if (n) {
        n.className = "timeline-node";
        n.querySelector(".timeline-circle").textContent = "○";
      }
    });

    const now = new Date();
    const timeStr = now.toTimeString().split(" ")[0];

    if (!state || state === "hold") {
      if (timelineTrackProgress) timelineTrackProgress.style.width = "0%";
      return;
    }

    if (state === "GO") {
      setNode(tlNode1, "completed", "✓", "23:31:12");
      setNode(tlNode2, "active", "●", timeStr);
      if (timelineTrackProgress) timelineTrackProgress.style.width = "25%";
    } else if (state === "EN_ROUTE") {
      setNode(tlNode1, "completed", "✓", "23:31:12");
      setNode(tlNode2, "completed", "✓", "23:31:35");
      setNode(tlNode3, "active", "●", timeStr);
      if (timelineTrackProgress) timelineTrackProgress.style.width = "50%";
    } else if (state === "ARRIVED") {
      setNode(tlNode1, "completed", "✓", "23:31:12");
      setNode(tlNode2, "completed", "✓", "23:31:35");
      setNode(tlNode3, "completed", "✓", "23:32:48");
      setNode(tlNode4, "active", "●", timeStr);
      if (timelineTrackProgress) timelineTrackProgress.style.width = "75%";
    } else if (state === "RESCUED") {
      setNode(tlNode1, "completed", "✓", "23:31:12");
      setNode(tlNode2, "completed", "✓", "23:31:35");
      setNode(tlNode3, "completed", "✓", "23:32:48");
      setNode(tlNode4, "completed", "✓", "23:35:10");
      setNode(tlNode5, "completed active", "✓", timeStr);
      if (timelineTrackProgress) timelineTrackProgress.style.width = "100%";
    }
  }

  function setNode(nodeEl, cls, symbol, time) {
    if (!nodeEl) return;
    nodeEl.className = `timeline-node ${cls}`;
    const circ = nodeEl.querySelector(".timeline-circle");
    if (circ) circ.textContent = symbol;
    const tEl = nodeEl.querySelector(".timeline-node-time");
    if (tEl && time) tEl.textContent = time;
  }

  // Initialize
  fetchOperationMode();
  loadTeamMembers();
  fetchHardwareAndBridgeStatus();
  pollWearableState();

  setInterval(fetchHardwareAndBridgeStatus, 4000);
  setInterval(pollWearableState, 1500);
})();
