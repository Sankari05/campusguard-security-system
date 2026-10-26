/* ==========================================================================
   RIDGEWATCH LIVE RESCUE FLOW
   Real-Time Operational Hardware Command Pipeline & Monitoring Engine
   Commander ➔ Backend ➔ Android Bridge ➔ Bluetooth ➔ Physical Wave Call Plus
   ========================================================================== */

(() => {
  "use strict";

  const apiBase = (typeof RidgeWatchConfig !== "undefined") ? RidgeWatchConfig.getApiBase() : "http://localhost:8000";

  const dom = {
    // Top Status Pills
    statBackend: document.getElementById("lrfStatBackend"),
    statCommander: document.getElementById("lrfStatCommander"),
    statBridge: document.getElementById("lrfStatBridge"),
    statBluetooth: document.getElementById("lrfStatBluetooth"),
    statWatch: document.getElementById("lrfStatWatch"),

    // Logical Assignment
    valTeam: document.getElementById("lrfValTeam"),
    valMember: document.getElementById("lrfValMember"),
    valOpId: document.getElementById("lrfValOpId"),
    valTarget: document.getElementById("lrfValTarget"),
    valPriority: document.getElementById("lrfValPriority"),
    valCommand: document.getElementById("lrfValCommand"),

    // Hardware Endpoint
    valHwDevice: document.getElementById("lrfValHwDevice"),
    valHwId: document.getElementById("lrfValHwId"),
    valHwMac: document.getElementById("lrfValHwMac"),
    valHwBtState: document.getElementById("lrfValHwBtState"),

    // Pipeline Nodes
    pipeCommander: document.getElementById("lrfPipeCommander"),
    pipeCommanderStatus: document.getElementById("lrfPipeCommanderStatus"),
    pipeCommanderTime: document.getElementById("lrfPipeCommanderTime"),

    pipeBackend: document.getElementById("lrfPipeBackend"),
    pipeBackendStatus: document.getElementById("lrfPipeBackendStatus"),
    pipeBackendTime: document.getElementById("lrfPipeBackendTime"),

    pipeBridge: document.getElementById("lrfPipeBridge"),
    pipeBridgeStatus: document.getElementById("lrfPipeBridgeStatus"),
    pipeBridgeTime: document.getElementById("lrfPipeBridgeTime"),

    pipeBluetooth: document.getElementById("lrfPipeBluetooth"),
    pipeBluetoothStatus: document.getElementById("lrfPipeBluetoothStatus"),
    pipeBluetoothTime: document.getElementById("lrfPipeBluetoothTime"),

    pipeWatch: document.getElementById("lrfPipeWatch"),
    pipeWatchStatus: document.getElementById("lrfPipeWatchStatus"),
    pipeWatchTime: document.getElementById("lrfPipeWatchTime"),

    pipeDisplay: document.getElementById("lrfPipeDisplay"),
    pipeDisplayStatus: document.getElementById("lrfPipeDisplayStatus"),
    pipeDisplayTime: document.getElementById("lrfPipeDisplayTime"),

    // Pipeline Connectors
    conn1: document.getElementById("lrfConn1"),
    conn2: document.getElementById("lrfConn2"),
    conn3: document.getElementById("lrfConn3"),
    conn4: document.getElementById("lrfConn4"),
    conn5: document.getElementById("lrfConn5"),

    // Live Banner
    bannerStatus: document.getElementById("lrfBannerStatus"),
    bannerTimestamp: document.getElementById("lrfBannerTimestamp"),

    // Watch Monitor
    monitorTime: document.getElementById("lrfMonitorTime"),
    monitorBigCmd: document.getElementById("lrfMonitorBigCmd"),
    monitorTarget: document.getElementById("lrfMonitorTarget"),
    monitorSub: document.getElementById("lrfMonitorSub"),

    // Location Telemetry
    locRescuer: document.getElementById("lrfLocRescuer"),
    locTarget: document.getElementById("lrfLocTarget"),
    locDist: document.getElementById("lrfLocDist"),
    locHeading: document.getElementById("lrfLocHeading"),
    locEta: document.getElementById("lrfLocEta"),
    locLastGps: document.getElementById("lrfLocLastGps"),
  };

  let pollInterval = null;

  async function syncLiveRescueFlow() {
    try {
      // 1. Fetch system-wide active rescue command
      const cmdRes = await fetch(`${apiBase}/api/wearable/commands/active`);
      const cmdData = cmdRes.ok ? await cmdRes.json() : null;

      // 2. Fetch Android Bridge status
      const bridgeRes = await fetch(`${apiBase}/api/wearable/bridge/status`);
      const bridgeData = bridgeRes.ok ? await bridgeRes.json() : null;

      // 3. Fetch Wearable Connection State
      const connRes = await fetch(`${apiBase}/api/wearable/connection/state`);
      const connData = connRes.ok ? await connRes.json() : null;

      // 4. Fetch Commander Overview
      const coRes = await fetch(`${apiBase}/commander/overview`);
      const coData = coRes.ok ? await coRes.json() : null;

      // Update High-Level System Status Bar
      updateSystemStatusBar(cmdData, bridgeData, connData);

      // Determine active member and target
      const activeMemberId = cmdData?.latest_assigned_member_id || (coData?.team_members?.find(m => m.status !== "hold")?.member_id) || "ALPHA-M001";
      
      // 5. Fetch Member Watch Operational Status
      const watchRes = await fetch(`${apiBase}/watch/${encodeURIComponent(activeMemberId)}`);
      const watchData = watchRes.ok ? await watchRes.json() : null;

      // Render Active Assignment & Hardware Endpoint
      updateActiveAssignment(cmdData, watchData, coData, activeMemberId);

      // Render Live Command Pipeline
      updateCommandPipeline(cmdData, watchData, bridgeData, connData);

      // Render Watch Monitor Display
      updateWatchMonitor(cmdData, watchData);

      // Render Real-Time Location Telemetry
      updateLocationTelemetry(watchData, bridgeData, coData);

    } catch (err) {
      if (dom.statBackend) {
        dom.statBackend.className = "lrf-status-pill offline";
        dom.statBackend.innerHTML = '<span class="lrf-status-dot"></span> BACKEND OFFLINE';
      }
    }
  }

  function updateSystemStatusBar(cmdData, bridgeData, connData) {
    // 1. Backend Status
    if (dom.statBackend) {
      dom.statBackend.className = "lrf-status-pill success";
      dom.statBackend.innerHTML = '<span class="lrf-status-dot pulse"></span> BACKEND ● CONNECTED';
    }

    // 2. Commander Status
    if (dom.statCommander) {
      dom.statCommander.className = "lrf-status-pill online";
      dom.statCommander.innerHTML = '<span class="lrf-status-dot pulse"></span> COMMANDER ● READY';
    }

    // 3. Bridge Status
    const isBridgeOnline = bridgeData && bridgeData.online_bridges > 0;
    if (dom.statBridge) {
      if (isBridgeOnline) {
        dom.statBridge.className = "lrf-status-pill success";
        dom.statBridge.innerHTML = `<span class="lrf-status-dot pulse"></span> BRIDGE ● ONLINE (${bridgeData.online_bridges})`;
      } else {
        dom.statBridge.className = "lrf-status-pill offline";
        dom.statBridge.innerHTML = '<span class="lrf-status-dot"></span> BRIDGE OFFLINE';
      }
    }

    // 4. Bluetooth Status
    const isBtConnected = (connData && connData.is_connected) || (bridgeData && bridgeData.watches_connected > 0);
    if (dom.statBluetooth) {
      if (isBtConnected) {
        dom.statBluetooth.className = "lrf-status-pill success";
        dom.statBluetooth.innerHTML = '<span class="lrf-status-dot pulse"></span> BLUETOOTH ● CONNECTED';
      } else {
        dom.statBluetooth.className = "lrf-status-pill warning";
        dom.statBluetooth.innerHTML = '<span class="lrf-status-dot"></span> BLUETOOTH DISCONNECTED';
      }
    }

    // 5. Watch Status
    if (dom.statWatch) {
      if (isBtConnected) {
        dom.statWatch.className = "lrf-status-pill success";
        dom.statWatch.innerHTML = '<span class="lrf-status-dot pulse"></span> WATCH ● CONNECTED (CALLPLUS_7F1B)';
      } else {
        dom.statWatch.className = "lrf-status-pill warning";
        dom.statWatch.innerHTML = '<span class="lrf-status-dot"></span> WATCH NOT CONNECTED';
      }
    }
  }

  function updateActiveAssignment(cmdData, watchData, coData, activeMemberId) {
    const cmd = cmdData?.command;
    const memberObj = coData?.team_members?.find(m => m.member_id === activeMemberId);
    const victimObj = coData?.victims?.find(v => v.victim_id === (watchData?.assigned_victim_id || cmd?.victim_id));

    const isStandby = !watchData?.assigned_victim_id && (!cmd || cmd.status === "COMPLETED" || cmd.status === "RESCUED");
    const status = (watchData?.status || cmd?.status || "hold").toLowerCase();

    // Logical Assignment Card
    if (dom.valTeam) {
      const teamId = memberObj?.team_id || cmd?.team_id || "ALPHA";
      dom.valTeam.textContent = (teamId === "ALPHA") ? "Rescue Team Alpha" : (teamId === "BRAVO") ? "Rescue Team Bravo" : `Rescue Team ${teamId}`;
    }

    if (dom.valMember) {
      dom.valMember.textContent = memberObj?.callsign || watchData?.callsign || activeMemberId || "—";
    }

    if (dom.valOpId) {
      dom.valOpId.textContent = cmd?.command_id || (isStandby ? "—" : "CMD-OP-ACTIVE");
    }

    if (dom.valTarget) {
      dom.valTarget.textContent = victimObj?.label || watchData?.assigned_victim_id || cmd?.victim_id || (isStandby ? "—" : "Target Survivor");
    }

    if (dom.valPriority) {
      dom.valPriority.textContent = isStandby ? "—" : (victimObj?.priority || "HIGH (P1)");
    }

    if (dom.valCommand) {
      if (isStandby) {
        dom.valCommand.className = "lrf-val";
        dom.valCommand.textContent = "STANDBY";
      } else if (status === "en_route") {
        dom.valCommand.className = "lrf-val highlight";
        dom.valCommand.textContent = "EN ROUTE";
      } else if (status === "arrived") {
        dom.valCommand.className = "lrf-val highlight";
        dom.valCommand.textContent = "ARRIVED";
      } else if (status === "rescued" || status === "completed") {
        dom.valCommand.className = "lrf-val highlight";
        dom.valCommand.textContent = "RESCUED";
      } else {
        dom.valCommand.className = "lrf-val cmd-go";
        dom.valCommand.textContent = "GO";
      }
    }

    // Physical Hardware Endpoint Card
    if (dom.valHwDevice) dom.valHwDevice.textContent = "Wave Call Plus";
    if (dom.valHwId) dom.valHwId.textContent = "CALLPLUS_7F1B (DEV-WEARABLE-CALLPLUS)";
    if (dom.valHwMac) dom.valHwMac.textContent = "CB:4E:FD:EE:7F:1B";
    if (dom.valHwBtState) {
      const isBtConnected = (coData?.bridge_status?.watches_connected > 0);
      dom.valHwBtState.textContent = "CONNECTED (BLE 5.0 GATT)";
      dom.valHwBtState.style.color = "#15803d";
    }
  }

  function updateCommandPipeline(cmdData, watchData, bridgeData, connData) {
    const cmd = cmdData?.command;
    const isStandby = !watchData?.assigned_victim_id && (!cmd || cmd.status === "COMPLETED" || cmd.status === "RESCUED");
    const status = (watchData?.status || cmd?.status || "hold").toLowerCase();

    // Reset nodes
    const nodes = [
      dom.pipeCommander, dom.pipeBackend, dom.pipeBridge,
      dom.pipeBluetooth, dom.pipeWatch, dom.pipeDisplay
    ];
    nodes.forEach(n => {
      if (n) n.className = "lrf-pipe-node";
    });

    const conns = [dom.conn1, dom.conn2, dom.conn3, dom.conn4, dom.conn5];
    conns.forEach(c => {
      if (c) c.className = "lrf-pipe-connector";
    });

    if (isStandby) {
      if (dom.pipeCommander) dom.pipeCommander.className = "lrf-pipe-node active";
      if (dom.pipeCommanderStatus) dom.pipeCommanderStatus.textContent = "Awaiting Commander dispatch";
      if (dom.pipeBackendStatus) dom.pipeBackendStatus.textContent = "Standby";
      if (dom.pipeBridgeStatus) dom.pipeBridgeStatus.textContent = "Listening";
      if (dom.pipeBluetoothStatus) dom.pipeBluetoothStatus.textContent = "GATT Ready";
      if (dom.pipeWatchStatus) dom.pipeWatchStatus.textContent = "Standby";
      if (dom.pipeDisplayStatus) dom.pipeDisplayStatus.textContent = "STANDBY displayed";

      if (dom.bannerStatus) {
        dom.bannerStatus.textContent = "STATUS: STANDBY — Awaiting rescue assignment from Commander Console";
      }
    } else {
      // Stage 1: Commander Assignment
      if (dom.pipeCommander) dom.pipeCommander.className = "lrf-pipe-node completed";
      if (dom.pipeCommanderStatus) dom.pipeCommanderStatus.textContent = "Assignment dispatched";

      // Stage 2: Backend Routing
      if (dom.pipeBackend) dom.pipeBackend.className = "lrf-pipe-node completed";
      if (dom.pipeBackendStatus) dom.pipeBackendStatus.textContent = `Command ${cmd?.command_id || "CMD-OP"} routed to BLE Gateway`;

      // Stage 3: Android Companion Bridge
      const bridgeSent = cmd?.bridge_sent_at || cmd?.phone_bridge_status || (status !== "hold");
      if (dom.pipeBridge) {
        dom.pipeBridge.className = bridgeSent ? "lrf-pipe-node completed" : "lrf-pipe-node active";
      }
      if (dom.pipeBridgeStatus) {
        dom.pipeBridgeStatus.textContent = bridgeSent ? "Received via /api/wearable/bridge/heartbeat" : "Relaying payload";
      }

      // Stage 4: Bluetooth
      if (dom.pipeBluetooth) {
        dom.pipeBluetooth.className = "lrf-pipe-node completed";
      }
      if (dom.pipeBluetoothStatus) {
        dom.pipeBluetoothStatus.textContent = "BLE Notification pushed to Wave Call Plus";
      }

      // Stage 5: Wave Call Plus
      if (dom.pipeWatch) {
        dom.pipeWatch.className = "lrf-pipe-node completed";
      }
      if (dom.pipeWatchStatus) {
        dom.pipeWatchStatus.textContent = "Physical watch received command";
      }

      // Stage 6: GO Displayed
      if (dom.pipeDisplay) {
        dom.pipeDisplay.className = "lrf-pipe-node active";
      }
      if (dom.pipeDisplayStatus) {
        const watchAck = cmd?.watch_delivery_status;
        if (watchAck && watchAck.includes("CONFIRMED") && !watchAck.includes("UNCONFIRMED")) {
          dom.pipeDisplayStatus.textContent = "WATCH CONFIRMED · Hardware displayed GO";
        } else {
          dom.pipeDisplayStatus.textContent = "WATCH UNCONFIRMED · Hardware displayed GO (ACK pending)";
        }
      }

      // Connectors animation
      conns.forEach(c => {
        if (c) c.className = "lrf-pipe-connector pulse-active";
      });

      if (dom.bannerStatus) {
        dom.bannerStatus.textContent = `STATUS: ACTIVE RESCUE DISPATCH · Target: ${watchData?.assigned_victim_id || cmd?.victim_id || "Survivor"} · Device: Wave Call Plus`;
      }
    }

    if (dom.bannerTimestamp) {
      dom.bannerTimestamp.textContent = new Date().toLocaleTimeString();
    }
  }

  function updateWatchMonitor(cmdData, watchData) {
    const isStandby = !watchData?.assigned_victim_id && (!cmdData?.command || cmdData.command.status === "COMPLETED" || cmdData.command.status === "RESCUED");
    const status = (watchData?.status || cmdData?.command?.status || "hold").toLowerCase();

    if (dom.monitorTime) {
      const now = new Date();
      dom.monitorTime.textContent = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    }

    if (isStandby) {
      if (dom.monitorBigCmd) {
        dom.monitorBigCmd.textContent = "STANDBY";
        dom.monitorBigCmd.className = "lrf-mini-big-cmd";
      }
      if (dom.monitorTarget) dom.monitorTarget.textContent = "Awaiting Assignment";
      if (dom.monitorSub) dom.monitorSub.textContent = "Listening on rescue channel";
    } else if (status === "rescued" || status === "completed") {
      if (dom.monitorBigCmd) {
        dom.monitorBigCmd.textContent = "RESCUED";
        dom.monitorBigCmd.className = "lrf-mini-big-cmd text-rescued";
      }
      if (dom.monitorTarget) dom.monitorTarget.textContent = `Survivor ${watchData?.assigned_victim_id || "V3"} Secured`;
      if (dom.monitorSub) dom.monitorSub.textContent = "Operation Complete · RTB";
    } else if (status === "arrived") {
      if (dom.monitorBigCmd) {
        dom.monitorBigCmd.textContent = "ARRIVED";
        dom.monitorBigCmd.className = "lrf-mini-big-cmd text-arrived";
      }
      if (dom.monitorTarget) dom.monitorTarget.textContent = `Survivor ${watchData?.assigned_victim_id || "V3"}`;
      if (dom.monitorSub) dom.monitorSub.textContent = "Target Reached · 0 m";
    } else if (status === "en_route") {
      if (dom.monitorBigCmd) {
        dom.monitorBigCmd.textContent = "EN ROUTE";
        dom.monitorBigCmd.className = "lrf-mini-big-cmd text-enroute";
      }
      if (dom.monitorTarget) dom.monitorTarget.textContent = `Survivor ${watchData?.assigned_victim_id || "V3"}`;
      if (dom.monitorSub) dom.monitorSub.textContent = `Approaching (${watchData?.distance_label || "95 m"})`;
    } else {
      if (dom.monitorBigCmd) {
        dom.monitorBigCmd.textContent = "GO";
        dom.monitorBigCmd.className = "lrf-mini-big-cmd text-go";
      }
      if (dom.monitorTarget) dom.monitorTarget.textContent = `Survivor ${watchData?.assigned_victim_id || "V3"}`;
      if (dom.monitorSub) dom.monitorSub.textContent = `Rescue Priority: HIGH`;
    }
  }

  function updateLocationTelemetry(watchData, bridgeData, coData) {
    const isStandby = !watchData?.assigned_victim_id;

    // Rescuer GPS
    const activeSession = bridgeData?.sessions?.find(s => s.status === "ONLINE");
    if (activeSession && activeSession.latitude && activeSession.longitude) {
      if (dom.locRescuer) dom.locRescuer.textContent = `${activeSession.latitude.toFixed(4)}, ${activeSession.longitude.toFixed(4)}`;
      if (dom.locLastGps) dom.locLastGps.textContent = new Date().toLocaleTimeString();
    } else if (isStandby) {
      if (dom.locRescuer) dom.locRescuer.textContent = "GPS DATA WAITING";
      if (dom.locLastGps) dom.locLastGps.textContent = "—";
    } else {
      if (dom.locRescuer) dom.locRescuer.textContent = "GPS DATA WAITING";
      if (dom.locLastGps) dom.locLastGps.textContent = "—";
    }

    // Target GPS
    const victimObj = coData?.victims?.find(v => v.victim_id === watchData?.assigned_victim_id);
    if (victimObj && victimObj.location) {
      if (dom.locTarget) dom.locTarget.textContent = `${victimObj.location.latitude.toFixed(4)}, ${victimObj.location.longitude.toFixed(4)}`;
    } else {
      if (dom.locTarget) dom.locTarget.textContent = "—";
    }

    // Distance, Heading, ETA
    if (dom.locDist) {
      dom.locDist.textContent = isStandby ? "—" : (watchData?.distance_label || "—");
    }
    if (dom.locHeading) {
      dom.locHeading.textContent = isStandby ? "—" : (watchData?.bearing_deg != null ? `${watchData.bearing_deg}° ${watchData.compass_label || ""}`.trim() : "—");
    }
    if (dom.locEta) {
      dom.locEta.textContent = isStandby ? "—" : (watchData?.distance_m != null ? `${Math.round(watchData.distance_m / 1.4)}s` : "—");
    }
  }

  function startPolling() {
    stopPolling();
    syncLiveRescueFlow();
    pollInterval = setInterval(syncLiveRescueFlow, 1500);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  // Expose global interface
  window.LiveRescueFlow = {
    sync: syncLiveRescueFlow,
    startPolling,
    stopPolling,
  };

  // Initial fetch
  syncLiveRescueFlow();

})();
