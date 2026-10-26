/* ==========================================================================
   RIDGEWATCH Android Companion BLE Bridge
   Edge Gateway for Wave Call Plus (CALLPLUS_7F1B) & Rescuer GNSS Telemetry
   ========================================================================== */

(() => {
  "use strict";

  const apiBase = RidgeWatchConfig.getApiBase();
  const sessionId = sessionStorage.getItem("ridgewatch_bridge_session_id") || `BRG-${Math.random().toString(36).substring(2, 9).toUpperCase()}`;
  sessionStorage.setItem("ridgewatch_bridge_session_id", sessionId);

  const teamSelect = document.getElementById("bridgeTeamSelect");
  const memberSelect = document.getElementById("bridgeMemberSelect");
  const latInput = document.getElementById("bridgeLat");
  const lonInput = document.getElementById("bridgeLon");
  const btnConnectBle = document.getElementById("btnConnectBle");
  const btnEnableNotif = document.getElementById("btnEnableNotif");
  const btnTestWatchAlert = document.getElementById("btnTestWatchAlert");
  const btnManualWatchAck = document.getElementById("btnManualWatchAck");
  const btnSyncGps = document.getElementById("btnSyncGps");
  const logBox = document.getElementById("bridgeLog");

  const bleModalOverlay = document.getElementById("bleModalOverlay");
  const btnBleModalClose = document.getElementById("btnBleModalClose");
  const btnBleModalScan = document.getElementById("btnBleModalScan");
  const btnBleModalDirectConnect = document.getElementById("btnBleModalDirectConnect");
  const btnBleModalDisconnect = document.getElementById("btnBleModalDisconnect");
  const bleModalStatusBadge = document.getElementById("bleModalStatusBadge");
  const bleModalMsg = document.getElementById("bleModalMsg");

  const statBackendConn = document.getElementById("statBackendConn");
  const statBluetooth = document.getElementById("statBluetooth");
  const statWatchConn = document.getElementById("statWatchConn");
  const statNotifPerm = document.getElementById("statNotifPerm");
  const statGps = document.getElementById("statGps");
  const statLastCmdId = document.getElementById("statLastCmdId");
  const statLastCmdDesc = document.getElementById("statLastCmdDesc");
  const statLastCmdStatus = document.getElementById("statLastCmdStatus");
  const statLastSync = document.getElementById("statLastSync");
  const statBridgeSession = document.getElementById("statBridgeSession");
  const statWatchBadge = document.getElementById("statWatchBadge");
  const bridgeStatus = document.getElementById("bridgeStatus");

  const emergencyPopupOverlay = document.getElementById("emergencyPopupOverlay");
  const emergencyPopupTime = document.getElementById("emergencyPopupTime");
  const emergencyPopupTitle = document.getElementById("emergencyPopupTitle");
  const emergencyPopupMsg = document.getElementById("emergencyPopupMsg");
  const emergencyPopupDist = document.getElementById("emergencyPopupDist");
  const emergencyPopupTarget = document.getElementById("emergencyPopupTarget");
  const emergencyPopupTeam = document.getElementById("emergencyPopupTeam");
  const pipeBt = document.getElementById("pipeBt");
  const pipeGatt = document.getElementById("pipeGatt");
  const pipeSent = document.getElementById("pipeSent");
  const pipeAck = document.getElementById("pipeAck");
  const btnPopupAccept = document.getElementById("btnPopupAccept");
  const btnPopupDismiss = document.getElementById("btnPopupDismiss");
  const notifCenterCount = document.getElementById("notifCenterCount");
  const notifCenterList = document.getElementById("notifCenterList");
  let popupAutoDismissTimer = null;

  let watchConnected = false;
  let watchConnectionState = "DISCONNECTED"; // DISCONNECTED | CONNECTING | CONNECTED | RECONNECTING | ERROR | BLE_CONNECTION_FAILED | UNAUTHORIZED_WATCH_REJECTED
  let commandDeliveryState = "QUEUED"; // QUEUED | BRIDGE_RECEIVED | WATCH_CONNECTING | WATCH_CONNECTED | GATT_READY | PHONE_NOTIFICATION_POSTED | WAITING_FOR_WATCH_ACK | WATCH_ACKNOWLEDGED | WATCH_DISCONNECTED | GATT_ERROR | COMMAND_WRITE_FAILED | ACK_TIMEOUT | ACK_INVALID | DEVICE_MISMATCH | UNSUPPORTED_COMMAND_CHANNEL | GATT_WRITE_CONFIRMED | GATT_WRITE_FAILED
  let activeBluetoothDevice = null;
  let activeGattServer = null;
  let currentAckPendingCmdId = null;
  let ackTimeoutTimer = null;
  let activeCommandData = null;
  let bluetoothEnabled = true;
  let gpsAvailable = true;
  let notifPermission = "default";
  let allTeamsData = [];
  let teamId = sessionStorage.getItem("ridgewatch_bridge_team_id") || "ALPHA";
  let memberId = sessionStorage.getItem("ridgewatch_bridge_member_id") || "";

  // Explicit Verified Command & ACK Characteristic Abstraction
  let verifiedCommandCharacteristic = null;
  let verifiedAckCharacteristic = null;

  // Structured Capability Map (Populated ONLY with verified characteristics)
  let BLE_CAPABILITIES = {
    deviceInformation: null,
    battery: null,
    heartRate: null,
    immediateAlert: null,
    alertNotification: null,
    commandChannel: null, // ONLY set if verified
    acknowledgementChannel: null, // ONLY set if verified
    discoveredServices: [],
    discoveredCharacteristics: [],
  };

  function playEmergencyChime() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.35);
      gain.gain.setValueAtTime(0.4, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.45);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.45);
    } catch (e) {}
  }

  if (statBridgeSession) {
    statBridgeSession.textContent = `Session: ${sessionId}`;
  }

  // Duplicate command protection / idempotency
  const postedCommandIds = new Set(
    JSON.parse(sessionStorage.getItem("ridgewatch_posted_cmd_ids") || "[]")
  );
  const postedAckCommandIds = new Set(
    JSON.parse(sessionStorage.getItem("ridgewatch_posted_ack_cmd_ids") || "[]")
  );

  // Mission-specific Alert State Tracking (Session-Isolated & Persisted)
  const dismissedMissionIds = new Set(
    JSON.parse(sessionStorage.getItem("ridgewatch_dismissed_missions") || "[]")
  );
  const shownMissionIds = new Set(
    JSON.parse(sessionStorage.getItem("ridgewatch_shown_missions") || "[]")
  );

  function markMissionDismissed(cmdId) {
    if (!cmdId) return;
    dismissedMissionIds.add(cmdId);
    sessionStorage.setItem("ridgewatch_dismissed_missions", JSON.stringify(Array.from(dismissedMissionIds)));
  }

  function markMissionShown(cmdId) {
    if (!cmdId) return;
    shownMissionIds.add(cmdId);
    sessionStorage.setItem("ridgewatch_shown_missions", JSON.stringify(Array.from(shownMissionIds)));
  }

  // Priority Issue #5: Authoritative Hardware Correlation Ledger
  const pendingPhysicalCommandsMap = new Map();
  const acknowledgedPhysicalCommandsSet = new Set();

  // Priority Issue #7: Connection Generation & Session Isolation Ledger
  let bleConnectionGeneration = 0;
  let currentBleSessionId = null;

  // Service Worker Registration for Android System Notifications
  let swRegistration = null;
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/frontend/sw.js", { scope: "/frontend/" })
      .then((reg) => {
        swRegistration = reg;
        log(`📲 [SERVICE_WORKER] Android Companion Service Worker active (scope: ${reg.scope}).`);
      })
      .catch((err) => {
        log(`ℹ️ [SERVICE_WORKER] Service Worker notice: ${err.message}`);
      });
  }

  async function dispatchNativeAndroidNotification(title, body, tag, cmdId) {
    if (!("Notification" in window)) {
      log("⚠️ [NOTIFICATION_UNSUPPORTED] Web Notification API not supported on this browser.");
      return { success: false, reason: "UNSUPPORTED" };
    }

    if (Notification.permission !== "granted") {
      log(`⚠️ [NOTIFICATION_PERMISSION_REQUIRED] Notification permission is '${Notification.permission}'. Tap 'Enable Android System Notifications'.`);
      return { success: false, reason: "PERMISSION_NOT_GRANTED" };
    }

    const notifOptions = {
      body: body,
      icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🚨</text></svg>",
      tag: tag || cmdId,
      vibrate: [500, 200, 500, 200, 500],
      requireInteraction: true,
      data: { commandId: cmdId },
    };

    // 1. Preferred on Android Chrome: Service Worker showNotification
    if ("serviceWorker" in navigator) {
      try {
        const reg = swRegistration || await navigator.serviceWorker.ready;
        if (reg && reg.showNotification) {
          await reg.showNotification(title, notifOptions);
          return { success: true, method: "SERVICE_WORKER" };
        }
      } catch (swErr) {
        log(`ℹ️ [SERVICE_WORKER] SW showNotification notice: ${swErr.message}. Attempting window fallback...`);
      }
    }

    // 2. Fallback: Window Notification constructor (Desktop / iOS / Legacy)
    try {
      const notif = new Notification(title, notifOptions);
      notif.onclick = () => { window.focus(); };
      return { success: true, method: "WINDOW_NOTIFICATION" };
    } catch (winErr) {
      log(`❌ [NOTIFICATION_FAILED] System notification failed: ${winErr.message}`);
      return { success: false, reason: winErr.message };
    }
  }

  // Centralized Approved Wearable Configuration
  const SUPPORTED_WEARABLE_CONFIG = Object.freeze({
    deviceName: "CALLPLUS_7F1B",
    wearableId: "DEV-WEARABLE-CALLPLUS",
    model: "Wave Call Plus",
    bluetoothAddress: "CB:4E:FD:EE:7F:1B",
  });

  const targetMac = SUPPORTED_WEARABLE_CONFIG.bluetoothAddress;
  const targetDeviceId = SUPPORTED_WEARABLE_CONFIG.wearableId;
  const targetBluetoothName = SUPPORTED_WEARABLE_CONFIG.deviceName;

  /**
   * Verified Protocol Evidence Registry.
   * STRICT SAFETY RULE:
   * A characteristic is NEVER marked as verified simply because it is writable or notifiable.
   * Only characteristics backed by verified hardware documentation or confirmed protocol traces
   * are registered here. If empty/unverified, direct GATT writes fail closed.
   */
  const PROTOCOL_EVIDENCE_REGISTRY = Object.freeze({
    commandChannels: [
      // Registered verified command endpoints (if verified by captured protocol evidence)
    ],
    ackChannels: [
      // Registered verified acknowledgement endpoints (if verified by captured protocol evidence)
    ],
  });

  /**
   * Phase 2: Safe Read/Observe-First GATT Protocol Diagnostic Sniffer
   * Records live incoming and outgoing packets with timestamps, byte length, hex dumps, and ASCII translations.
   * Strictly observe-first: Does not perform arbitrary writes or loops.
   */
  window.GATT_DIAGNOSTIC_SNIFFER = [];

  function recordGattDiagnosticPacket(direction, serviceUuid, charUuid, dataBytes, note = "") {
    let uint8;
    if (dataBytes instanceof Uint8Array) {
      uint8 = dataBytes;
    } else if (dataBytes && dataBytes.buffer) {
      uint8 = new Uint8Array(dataBytes.buffer);
    } else if (Array.isArray(dataBytes)) {
      uint8 = new Uint8Array(dataBytes);
    } else if (typeof dataBytes === "string") {
      uint8 = new TextEncoder().encode(dataBytes);
    } else {
      uint8 = new Uint8Array([]);
    }

    const hexArray = Array.from(uint8).map(b => "0x" + b.toString(16).padStart(2, "0").toUpperCase());
    const hexString = hexArray.join(" ");
    let asciiString = "";
    try {
      asciiString = new TextDecoder("utf-8", { fatal: false }).decode(uint8);
    } catch (_) {}

    const entry = {
      timestamp: new Date().toISOString(),
      direction: direction, // "INCOMING" | "OUTGOING"
      serviceUuid: serviceUuid || "UNKNOWN",
      characteristicUuid: charUuid || "UNKNOWN",
      byteLength: uint8.length,
      hexBytes: hexArray,
      hexString: hexString,
      ascii: asciiString.replace(/[\x00-\x1F\x7F-\x9F]/g, "."),
      note: note,
    };

    window.GATT_DIAGNOSTIC_SNIFFER.unshift(entry);
    if (window.GATT_DIAGNOSTIC_SNIFFER.length > 100) {
      window.GATT_DIAGNOSTIC_SNIFFER.pop();
    }

    console.log(`[GATT_SNIFFER] ${direction} [${entry.characteristicUuid}] (${entry.byteLength}B): ${hexString} | Note: ${note}`);
    return entry;
  }
  window.recordGattDiagnosticPacket = recordGattDiagnosticPacket;
  window.getGattDiagnosticLog = () => window.GATT_DIAGNOSTIC_SNIFFER;

  /**
   * Phase 3 & 7: Command Channel Validator and Status Resolver
   * Returns one of: "VERIFIED", "UNVERIFIED", "UNAVAILABLE", "DISCONNECTED", "STALE", "INVALID_DEVICE"
   */
  function getCommandChannelStatus() {
    if (!activeBluetoothDevice) {
      return "DISCONNECTED";
    }
    if (activeBluetoothDevice.name !== targetBluetoothName) {
      return "INVALID_DEVICE";
    }
    if (!activeGattServer || !activeGattServer.connected) {
      return "DISCONNECTED";
    }
    if (!verifiedCommandCharacteristic) {
      return "UNVERIFIED";
    }
    // Check stale reference
    if (
      !verifiedCommandCharacteristic.service ||
      !verifiedCommandCharacteristic.service.device ||
      !verifiedCommandCharacteristic.service.device.gatt ||
      !verifiedCommandCharacteristic.service.device.gatt.connected
    ) {
      return "STALE";
    }
    // Check write properties
    const props = verifiedCommandCharacteristic.properties;
    if (!props || (!props.write && !props.writeWithoutResponse)) {
      return "UNAVAILABLE";
    }
    return "VERIFIED";
  }
  window.getCommandChannelStatus = getCommandChannelStatus;

  /**
   * Validates command channel readiness before any write attempt.
   */
  function validateCommandChannel(charHandle) {
    const status = getCommandChannelStatus();
    if (status !== "VERIFIED") {
      return {
        valid: false,
        status: status,
        reason: status === "UNVERIFIED"
          ? "Direct watch command unavailable — protocol not verified"
          : `Command channel not ready: status=${status}`,
      };
    }
    return { valid: true, status: "VERIFIED", handle: charHandle || verifiedCommandCharacteristic };
  }
  window.validateCommandChannel = validateCommandChannel;

  /**
   * Resolves the verified GATT command characteristic based on protocol evidence.
   * Returns null if unverified, preventing blind/arbitrary characteristic writes.
   */
  function resolveVerifiedCommandCharacteristic(discoveredCharacteristics, evidenceRegistry = PROTOCOL_EVIDENCE_REGISTRY) {
    if (!discoveredCharacteristics || !Array.isArray(discoveredCharacteristics)) return null;

    const candidateCommandChars = discoveredCharacteristics.filter(
      c => c.properties && (c.properties.includes("WRITE") || c.properties.includes("WRITE_NO_RESP"))
    );

    for (const candidate of candidateCommandChars) {
      const candUuidLower = candidate.uuid.toLowerCase();
      const matchedEvidence = (evidenceRegistry.commandChannels || []).find(entry =>
        candUuidLower === entry.characteristicUuid.toLowerCase() ||
        candUuidLower.includes(entry.characteristicUuid.toLowerCase())
      );

      if (matchedEvidence) {
        log(`[BLE] Verified command characteristic identified: ${candidate.uuid}`);
        log(`[BLE] Verification evidence: ${matchedEvidence.evidenceSource} (protocol: ${matchedEvidence.protocol})`);
        candidate.verificationState = "VERIFIED_COMMAND";
        candidate.evidence = matchedEvidence;
        return candidate.characteristicHandle || candidate;
      }
    }

    log("[BLE] Candidate command characteristics discovered:");
    if (candidateCommandChars.length === 0) {
      log("  • None discovered.");
    } else {
      candidateCommandChars.forEach(c => log(`  • ${c.uuid} [${c.properties.join(", ")}] -> role=UNVERIFIED`));
    }
    log("[BLE] Verified command characteristic: None (UNVERIFIED)");
    log("[BLE] Direct physical GATT writes disabled -> using Android Companion Notification Mirroring.");
    return null;
  }

  /**
   * Resolves the verified GATT ACK characteristic based on protocol evidence.
   * Returns null if unverified, preventing arbitrary notification processing.
   */
  function resolveVerifiedAckCharacteristic(discoveredCharacteristics, evidenceRegistry = PROTOCOL_EVIDENCE_REGISTRY) {
    if (!discoveredCharacteristics || !Array.isArray(discoveredCharacteristics)) return null;

    const candidateAckChars = discoveredCharacteristics.filter(
      c => c.properties && (c.properties.includes("NOTIFY") || c.properties.includes("INDICATE"))
    );

    for (const candidate of candidateAckChars) {
      const candUuidLower = candidate.uuid.toLowerCase();
      const matchedEvidence = (evidenceRegistry.ackChannels || []).find(entry =>
        candUuidLower === entry.characteristicUuid.toLowerCase() ||
        candUuidLower.includes(entry.characteristicUuid.toLowerCase())
      );

      if (matchedEvidence) {
        log(`[BLE] Verified ACK characteristic identified: ${candidate.uuid}`);
        log(`[BLE] Verification evidence: ${matchedEvidence.evidenceSource} (protocol: ${matchedEvidence.protocol})`);
        candidate.verificationState = "VERIFIED_ACK";
        candidate.evidence = matchedEvidence;
        return candidate.characteristicHandle || candidate;
      }
    }

    log("[BLE] Candidate ACK characteristics discovered:");
    if (candidateAckChars.length === 0) {
      log("  • None discovered.");
    } else {
      candidateAckChars.forEach(c => log(`  • ${c.uuid} [${c.properties.join(", ")}] -> role=UNVERIFIED`));
    }
    log("[BLE] Verified ACK characteristic: None (UNVERIFIED)");
    log("[BLE] Direct physical GATT ACK subscription disabled.");
    return null;
  }

  /**
   * Dedicated command packet builder based on structured protocol framing.
   */
  function buildRidgewatchGoCommand(cmd) {
    const cmdId = cmd.command_id || (cmd.notification_payload && cmd.notification_payload.command_id);
    const victim = cmd.victim_id || cmd.target_id || "Survivor";
    const location = cmd.location || cmd.location_label || "Target Sector";

    const payloadObj = {
      cmd: "GO",
      command_id: cmdId,
      victim_id: victim,
      location: location,
      timestamp: Date.now(),
    };

    return {
      commandId: cmdId,
      asciiPacket: new TextEncoder().encode(`GO:${cmdId}`),
      jsonPacket: new TextEncoder().encode(JSON.stringify(payloadObj)),
      payloadObj: payloadObj,
    };
  }

  /**
   * Deterministic strict validation function for the approved RidgeWatch wearable.
   * REJECTS:
   * - null / undefined / missing name
   * - broad name matching (e.g. "CALLPLUS", "Call", "Wave", "boAt", "T800", "T800Ultra")
   * - suffix / prefix variants (e.g. "CALLPLUS_7F1B_TEST", "MY_CALLPLUS_7F1B", "WAVE_CALLPLUS_7F1B")
   * ACCEPTS ONLY:
   * - Exact match: device.name === "CALLPLUS_7F1B"
   */
  function isApprovedWearable(device) {
    if (!device || typeof device !== "object") {
      return {
        approved: false,
        reason: "MISSING_DEVICE_IDENTITY",
        wearableId: null,
      };
    }

    const devName = typeof device.name === "string" ? device.name.trim() : "";
    if (!devName) {
      return {
        approved: false,
        reason: "MISSING_DEVICE_NAME",
        wearableId: null,
      };
    }

    // Strict exact match: MUST strictly equal "CALLPLUS_7F1B"
    if (devName !== SUPPORTED_WEARABLE_CONFIG.deviceName) {
      return {
        approved: false,
        reason: "UNAUTHORIZED_WEARABLE",
        receivedName: devName,
        expectedName: SUPPORTED_WEARABLE_CONFIG.deviceName,
        wearableId: null,
      };
    }

    return {
      approved: true,
      reason: "VALIDATION_PASSED",
      wearableId: SUPPORTED_WEARABLE_CONFIG.wearableId,
      deviceName: SUPPORTED_WEARABLE_CONFIG.deviceName,
    };
  }

  // Expose helpers on window for browser-level validation & testing
  window._isApprovedWearable = isApprovedWearable;
  window._SUPPORTED_WEARABLE_CONFIG = SUPPORTED_WEARABLE_CONFIG;
  window._PROTOCOL_EVIDENCE_REGISTRY = PROTOCOL_EVIDENCE_REGISTRY;
  window._resolveVerifiedCommandCharacteristic = resolveVerifiedCommandCharacteristic;
  window._resolveVerifiedAckCharacteristic = resolveVerifiedAckCharacteristic;
  window._buildRidgewatchGoCommand = buildRidgewatchGoCommand;

  function log(msg) {
    if (!logBox) return;
    const ts = new Date().toLocaleTimeString();
    logBox.innerHTML += `<div>[${ts}] ${msg}</div>`;
    logBox.scrollTop = logBox.scrollHeight;
  }

  async function checkBackendConnection() {
    try {
      let res = await fetch(`${apiBase}/health`);
      if (!res.ok) {
        res = await fetch(`${apiBase}/api/health`);
      }
      if (!res.ok) {
        res = await fetch(`${apiBase}/api/wearable/bridge/heartbeat`);
      }
      if (res.ok) {
        console.log(`[RIDGEWATCH API] GET /health -> 200 (Connected to ${apiBase})`);
        if (statBackendConn) {
          statBackendConn.textContent = "● CONNECTED";
          statBackendConn.className = "status-card-val val-ok";
        }
        if (bridgeStatus) {
          bridgeStatus.textContent = "ONLINE";
          bridgeStatus.className = "bridge-status-badge status-online";
        }
        return true;
      } else {
        console.warn(`[RIDGEWATCH API] GET /health -> ${res.status}`);
      }
    } catch (e) {
      console.warn(`[RIDGEWATCH API] Health check failed: ${e.message}`);
      if (statBackendConn) {
        statBackendConn.textContent = "○ DISCONNECTED";
        statBackendConn.className = "status-card-val val-bad";
      }
      if (bridgeStatus) {
        bridgeStatus.textContent = "OFFLINE";
        bridgeStatus.className = "bridge-status-badge status-offline";
      }
    }
    return false;
  }

  async function loadBridgeTeamsAndMembers() {
    try {
      console.log(`[BRIDGE] Requesting teams from ${apiBase}/api/teams`);
      let res = await fetch(`${apiBase}/api/teams`);
      if (!res.ok) {
        console.log(`[BRIDGE] Requesting teams from ${apiBase}/teams`);
        res = await fetch(`${apiBase}/teams`);
      }
      if (res.ok) {
        console.log(`[RIDGEWATCH API] GET /api/teams -> 200`);
        const data = await res.json();
        const teams = (data && data.teams && Array.isArray(data.teams)) ? data.teams : (Array.isArray(data) ? data : []);
        if (teams.length > 0) {
          allTeamsData = teams;
          console.log(`[TEAMS] Loaded ${allTeamsData.length} teams from backend`);
          if (teamSelect) {
            teamSelect.innerHTML = "";
            allTeamsData.forEach((t) => {
              const opt = document.createElement("option");
              opt.value = t.team_id || t.id;
              opt.textContent = `${t.team_name || t.name || t.team_id} (${t.team_id || t.id})`;
              teamSelect.appendChild(opt);
            });
          }
        }
      } else {
        console.warn(`[RIDGEWATCH API] GET /api/teams -> ${res.status}`);
        const coRes = await fetch(`${apiBase}/commander/overview`);
        if (coRes.ok) {
          const coData = await coRes.json();
          if (coData.teams) {
            allTeamsData = coData.teams;
            if (teamSelect && allTeamsData.length > 0) {
              teamSelect.innerHTML = "";
              allTeamsData.forEach((t) => {
                const opt = document.createElement("option");
                opt.value = t.team_id || t.id;
                opt.textContent = `${t.team_name || t.name || t.team_id} (${t.team_id || t.id})`;
                teamSelect.appendChild(opt);
              });
            }
          }
        }
      }

      // Default fallback roster if server is initializing
      if (!allTeamsData || allTeamsData.length === 0) {
        allTeamsData = [
          {
            team_id: "ALPHA",
            team_name: "Rescue Team Alpha",
            members: [
              { member_id: "ALPHA-M001", callsign: "Alpha Member 1", full_name: "Alpha Member 1" },
              { member_id: "ALPHA-M002", callsign: "Alpha Member 2", full_name: "Alpha Member 2" },
            ],
          },
          {
            team_id: "BRAVO",
            team_name: "Rescue Team Bravo",
            members: [
              { member_id: "BRAVO-M001", callsign: "Bravo Member 1", full_name: "Bravo Member 1" },
              { member_id: "BRAVO-M002", callsign: "Bravo Member 2", full_name: "Bravo Member 2" },
            ],
          },
        ];
      }

      if (teamSelect && teamId && teamSelect.querySelector(`option[value="${teamId}"]`)) {
        teamSelect.value = teamId;
      } else if (teamSelect && teamSelect.options.length > 0) {
        teamId = teamSelect.options[0].value;
        teamSelect.value = teamId;
        sessionStorage.setItem("ridgewatch_bridge_team_id", teamId);
      }
      updateMemberDropdown();
      console.log(`[BRIDGE] Session initialized (Team: ${teamId}, Member: ${memberId})`);
    } catch (e) {
      console.error(`[BRIDGE] Could not load teams roster: ${e.message}`);
      log(`⚠️ Could not load teams roster: ${e.message}`);
    }
  }

  function updateMemberDropdown() {
    if (!memberSelect) return;
    memberSelect.innerHTML = "";

    const currentTeam = allTeamsData.find((t) => (t.team_id || t.id) === teamId) || allTeamsData[0];
    if (currentTeam && Array.isArray(currentTeam.members) && currentTeam.members.length > 0) {
      currentTeam.members.forEach((m, idx) => {
        const opt = document.createElement("option");
        opt.value = m.member_id || m.id;
        const name = m.callsign || m.name || m.full_name || `Member ${idx + 1}`;
        opt.textContent = `${name} (${m.member_id || m.id})`;
        memberSelect.appendChild(opt);
      });

      // Default to stored or first member
      if (memberId && memberSelect.querySelector(`option[value="${memberId}"]`)) {
        memberSelect.value = memberId;
      } else {
        memberId = currentTeam.members[0].member_id || currentTeam.members[0].id;
        memberSelect.value = memberId;
        sessionStorage.setItem("ridgewatch_bridge_member_id", memberId);
      }
    } else {
      const defaultMem = `${teamId || "ALPHA"}-M001`;
      const opt = document.createElement("option");
      opt.value = defaultMem;
      opt.textContent = `Alpha Member 1 (${defaultMem})`;
      memberSelect.appendChild(opt);
      memberId = defaultMem;
      sessionStorage.setItem("ridgewatch_bridge_member_id", memberId);
    }
    console.log(`[MEMBERS] Active member set to: ${memberId} (Team: ${teamId})`);
  }

  if (teamSelect) {
    teamSelect.addEventListener("change", () => {
      teamId = teamSelect.value;
      sessionStorage.setItem("ridgewatch_bridge_team_id", teamId);
      updateMemberDropdown();
      log(`Rescuer team set to ${teamId} for Wave Call Plus (${targetMac}).`);
      sendHeartbeat();
    });
  }

  if (memberSelect) {
    memberSelect.addEventListener("change", () => {
      memberId = memberSelect.value;
      sessionStorage.setItem("ridgewatch_bridge_member_id", memberId);
      log(`Assigned watch owner set to: ${memberId}`);
      sendHeartbeat();
    });
  }

  function updateStatusCards(lastCmd) {
    if (statBluetooth) {
      statBluetooth.textContent = bluetoothEnabled ? "● ENABLED" : "○ DISABLED";
      statBluetooth.className = `status-card-val ${bluetoothEnabled ? "val-ok" : "val-bad"}`;
    }
    if (statWatchConn) {
      if (watchConnectionState === "CONNECTED" || watchConnected) {
        statWatchConn.textContent = "● CONNECTED";
        statWatchConn.className = "status-card-val val-ok";
      } else if (watchConnectionState === "CONNECTING") {
        statWatchConn.textContent = "CONNECTING…";
        statWatchConn.className = "status-card-val val-warn";
      } else if (watchConnectionState === "RECONNECTING") {
        statWatchConn.textContent = "RECONNECTING…";
        statWatchConn.className = "status-card-val val-warn";
      } else if (watchConnectionState === "BLE_CONNECTION_FAILED" || watchConnectionState === "ERROR" || watchConnectionState === "UNAUTHORIZED_WATCH_REJECTED") {
        statWatchConn.textContent = "⚠ FAILED / REJECTED";
        statWatchConn.className = "status-card-val val-bad";
      } else {
        statWatchConn.textContent = "DISCONNECTED";
        statWatchConn.className = "status-card-val val-dim";
      }
    }
    if (statWatchBadge) {
      if (watchConnectionState === "CONNECTED" || watchConnected) {
        statWatchBadge.textContent = "CONNECTED (GATT)";
        statWatchBadge.className = "target-badge-status val-ok";
      } else if (watchConnectionState === "CONNECTING") {
        statWatchBadge.textContent = "CONNECTING";
        statWatchBadge.className = "target-badge-status val-warn";
      } else if (watchConnectionState === "RECONNECTING") {
        statWatchBadge.textContent = "RECONNECTING";
        statWatchBadge.className = "target-badge-status val-warn";
      } else if (watchConnectionState === "BLE_CONNECTION_FAILED" || watchConnectionState === "ERROR" || watchConnectionState === "UNAUTHORIZED_WATCH_REJECTED") {
        statWatchBadge.textContent = "REJECTED";
        statWatchBadge.className = "target-badge-status val-bad";
      } else {
        statWatchBadge.textContent = "CONFIGURED";
        statWatchBadge.className = "target-badge-status";
      }
    }
    if (statNotifPerm) {
      const perm = ("Notification" in window) ? Notification.permission : "unsupported";
      if (perm === "granted") {
        statNotifPerm.textContent = "● GRANTED";
        statNotifPerm.className = "status-card-val val-ok";
      } else if (perm === "denied") {
        statNotifPerm.textContent = "○ BLOCKED";
        statNotifPerm.className = "status-card-val val-bad";
      } else if (perm === "unsupported") {
        statNotifPerm.textContent = "UNSUPPORTED";
        statNotifPerm.className = "status-card-val val-dim";
      } else {
        statNotifPerm.textContent = "● STANDBY (TAP ENABLE)";
        statNotifPerm.className = "status-card-val val-warn";
      }
    }
    if (statGps) {
      statGps.textContent = gpsAvailable ? "● AVAILABLE" : "⚠ DISABLED";
      statGps.className = `status-card-val ${gpsAvailable ? "val-ok" : "val-warn"}`;
    }
    if (statLastSync) {
      statLastSync.textContent = new Date().toLocaleTimeString();
    }
    if (lastCmd) {
      activeCommandData = lastCmd;
      if (statLastCmdId) {
        statLastCmdId.textContent = `🚨 ${lastCmd.command_type || "GO"} (${lastCmd.command_id || "ACTIVE"})`;
        statLastCmdId.style.color = "#15803d";
      }
      if (statLastCmdDesc) {
        const teamName = teamSelect ? teamSelect.options[teamSelect.selectedIndex]?.text.split("(")[0].trim() : teamId;
        const memberName = memberSelect ? memberSelect.options[memberSelect.selectedIndex]?.text.split("(")[0].trim() : memberId;
        statLastCmdDesc.textContent = `${teamName} — ${memberName} ➔ Target: ${lastCmd.victim_id || lastCmd.target_id || "Survivor"}`;
      }
      if (statLastCmdStatus) {
        const isAck = commandDeliveryState === "WATCH_ACKNOWLEDGED" || lastCmd.status === "WATCH_ACKNOWLEDGED" || lastCmd.watch_delivery_status === "WATCH_ACKNOWLEDGED";
        const isWaiting = commandDeliveryState === "WAITING_FOR_WATCH_ACK" || (lastCmd.status === "COMMAND_SENT" && !isAck);
        const isTimeout = commandDeliveryState === "ACK_TIMEOUT" || lastCmd.status === "ACK_TIMEOUT";
        const isWriteFail = commandDeliveryState === "COMMAND_WRITE_FAILED" || lastCmd.status === "COMMAND_WRITE_FAILED" || commandDeliveryState === "GATT_WRITE_FAILED";
        const isMismatch = commandDeliveryState === "DEVICE_MISMATCH" || lastCmd.status === "DEVICE_MISMATCH";
        const isAckInvalid = commandDeliveryState === "ACK_INVALID" || lastCmd.status === "ACK_INVALID";

        const isRescuerConfirmed = lastCmd.rescuer_confirmed || commandDeliveryState === "USER_ACCEPTED" || lastCmd.status === "USER_ACCEPTED";

        if (isAck) {
          statLastCmdStatus.textContent = `Bridge: ● ONLINE · Watch: ● CONNECTED (GATT) · Telemetry: ● DISCOVERED · Notification: ● POSTED · Watch ACK: ● ACKNOWLEDGED${isRescuerConfirmed ? " · Rescuer: ● CONFIRMED" : ""}`;
          statLastCmdStatus.style.color = "#16a34a";
        } else if (isWaiting) {
          statLastCmdStatus.textContent = `Bridge: ● ONLINE · Watch: ● CONNECTED (GATT) · Telemetry: ● DISCOVERED · Notification: ● POSTED · Watch ACK: ○ PENDING${isRescuerConfirmed ? " · Rescuer: ● CONFIRMED" : ""}`;
          statLastCmdStatus.style.color = "#d97706";
        } else if (isTimeout) {
          statLastCmdStatus.textContent = "Bridge: ● ONLINE · Watch: ● CONNECTED (GATT) · Notification: ● POSTED · Watch ACK: × TIMEOUT";
          statLastCmdStatus.style.color = "#ef4444";
        } else if (isWriteFail) {
          statLastCmdStatus.textContent = "Bridge: ● ONLINE · Watch: ● CONNECTED (GATT) · Direct GATT: × UNVERIFIED · Notification: ● POSTED · Watch ACK: ○ UNCONFIRMED";
          statLastCmdStatus.style.color = "#ef4444";
        } else if (isMismatch) {
          statLastCmdStatus.textContent = "Bridge: ● ONLINE · Device: × MISMATCH · Watch Delivery: ○ UNCONFIRMED";
          statLastCmdStatus.style.color = "#ef4444";
        } else if (isAckInvalid) {
          statLastCmdStatus.textContent = "Bridge: ● ONLINE · Watch: ● CONNECTED (GATT) · Notification: ● POSTED · Watch ACK: × INVALID";
          statLastCmdStatus.style.color = "#ef4444";
        } else if (watchConnected) {
          statLastCmdStatus.textContent = `Bridge: ● ONLINE · Watch: ● CONNECTED (GATT) · Telemetry: ● DISCOVERED · Direct GATT: ○ UNVERIFIED · Notification: ● POSTED · Watch ACK: ○ UNCONFIRMED${isRescuerConfirmed ? " · Rescuer: ● CONFIRMED" : ""}`;
          statLastCmdStatus.style.color = "#2563eb";
        } else {
          statLastCmdStatus.textContent = `Bridge: ● ONLINE · Watch: ○ DISCONNECTED · Notification: ● POSTED · Watch ACK: ○ UNCONFIRMED${isRescuerConfirmed ? " · Rescuer: ● CONFIRMED" : ""}`;
          statLastCmdStatus.style.color = "#2563eb";
        }
      }
    }
  }

  async function requestNotificationPermission() {
    if (!("Notification" in window)) {
      log("⚠️ Web Notification API not supported in this browser. Notifications will be displayed in console log.");
      updateStatusCards(null);
      return;
    }
    try {
      const perm = await Notification.requestPermission();
      notifPermission = perm;
      updateStatusCards(null);
      if (perm === "granted") {
        log("🔔 Android System Notifications ENABLED. High-priority rescue alerts will mirror to Wave Call Plus.");
      } else {
        log(`ℹ️ Notification permission status: ${perm}`);
      }
    } catch (e) {
      log(`⚠️ Notification permission error: ${e.message}`);
    }
  }

  async function onGattDisconnected(event) {
    const dev = (event && event.target) || activeBluetoothDevice;
    const devName = (dev && dev.name) || targetBluetoothName;
    log(`⚠️ [BLE] Physical Watch Disconnected: ${devName} (${targetMac})`);
    
    // Priority Issue #7: Invalidate connection generation and session ID
    bleConnectionGeneration++;
    currentBleSessionId = null;

    // Clear connection, verified characteristic objects, and pending hardware ledgers
    watchConnected = false;
    watchConnectionState = "DISCONNECTED";
    commandDeliveryState = "WATCH_DISCONNECTED";
    activeGattServer = null;
    activeBluetoothDevice = null;
    verifiedCommandCharacteristic = null;
    verifiedAckCharacteristic = null;
    pendingPhysicalCommandsMap.clear();
    acknowledgedPhysicalCommandsSet.clear();
    currentAckPendingCmdId = null;

    BLE_CAPABILITIES = {
      deviceInformation: null,
      battery: null,
      heartRate: null,
      immediateAlert: null,
      alertNotification: null,
      commandChannel: null,
      acknowledgementChannel: null,
      discoveredServices: [],
      discoveredCharacteristics: [],
    };
    if (ackTimeoutTimer) {
      clearTimeout(ackTimeoutTimer);
      ackTimeoutTimer = null;
    }

    updateStatusCards(activeCommandData);
    updateBleModalUI();
    await notifyBackendDisconnect();
    await sendHeartbeat();
  }

  /**
   * Phase 3 & Priority Issue #5 & #7: Strict ACK Validation & Session-Isolated Correlation Pipeline.
   * STRICTLY INVOKED ONLY by real Web Bluetooth 'characteristicvaluechanged' events
   * on a verified physical acknowledgement channel from CALLPLUS_7F1B.
   */
  function onWatchAckNotification(event) {
    // 0. Stage 0: Session Generation Check (Reject events from old/invalidated sessions)
    if (!currentBleSessionId) {
      log("[WATCH-ACK] Rejected (OLD_SESSION_EVENT_REJECTED): session is no longer active.");
      return { status: "rejected", reason: "OLD_SESSION_EVENT_REJECTED" };
    }

    // 1. Stage 1: Verify physical event object and payload existence
    if (!event || !event.target || !event.target.value) {
      log("[WATCH-ACK] Rejected (ACK_REJECTED_MALFORMED): invalid or missing physical BLE event target.");
      return { status: "rejected", reason: "ACK_REJECTED_MALFORMED" };
    }

    // 2. Stage 2: Verify active physical Bluetooth device (Device Identity Validation)
    if (!activeBluetoothDevice || activeBluetoothDevice.name !== targetBluetoothName) {
      log(`[WATCH-ACK] Rejected (ACK_REJECTED_DEVICE_MISMATCH): wrong device (${activeBluetoothDevice ? activeBluetoothDevice.name : "None"}). Expected ${targetBluetoothName}.`);
      return { status: "rejected", reason: "ACK_REJECTED_DEVICE_MISMATCH" };
    }

    // 3. Stage 3: Verify active physical GATT server connection
    if (!activeGattServer || !activeGattServer.connected) {
      log("[WATCH-ACK] Rejected (ACK_REJECTED_DISCONNECTED): physical GATT server is disconnected.");
      return { status: "rejected", reason: "ACK_REJECTED_DISCONNECTED" };
    }

    // 4. Stage 4: Characteristic Identity Validation (Only verified ACK channel accepted)
    if (!BLE_CAPABILITIES.acknowledgementChannel) {
      log("[WATCH-ACK] Rejected (ACK_REJECTED_WRONG_CHARACTERISTIC): acknowledgementChannel is unverified on this hardware.");
      return { status: "rejected", reason: "ACK_REJECTED_WRONG_CHARACTERISTIC" };
    }
    const targetUuid = (event.target.uuid || "").toLowerCase();
    const verifiedUuid = (BLE_CAPABILITIES.acknowledgementChannel.uuid || "").toLowerCase();
    if (targetUuid && verifiedUuid && targetUuid !== verifiedUuid) {
      log(`[WATCH-ACK] Rejected (ACK_REJECTED_WRONG_CHARACTERISTIC): characteristic ${targetUuid} is not verified ACK channel ${verifiedUuid}.`);
      return { status: "rejected", reason: "ACK_REJECTED_WRONG_CHARACTERISTIC" };
    }

    const value = event.target.value; // Real DataView from Web Bluetooth event
    if (!value || value.byteLength < 2) {
      log("[WATCH-ACK] Rejected (ACK_REJECTED_MALFORMED): empty or truncated payload buffer.");
      return { status: "rejected", reason: "ACK_REJECTED_MALFORMED" };
    }

    const rawBytes = new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    const hexDump = Array.from(rawBytes).map(b => "0x" + b.toString(16).padStart(2, "0").toUpperCase()).join(", ");
    log(`[WATCH-ACK] Notification received on verified ACK channel (${verifiedUuid || "0xFEA2"})`);
    log(`[WATCH-ACK] Raw payload: [${hexDump}]`);

    let decodedText = "";
    try {
      decodedText = new TextDecoder().decode(rawBytes);
    } catch (e) {
      decodedText = "";
    }

    // 5. Stage 5: Packet Format & Protocol Parsing (Strict JSON or TLV structure, not substring)
    let isAck = false;
    let ackCmdId = null;
    let ackTransactionId = null;
    let ackCmdType = "GO";

    try {
      const jsonAck = JSON.parse(decodedText);
      if (jsonAck.ack === true || jsonAck.status === "ACKNOWLEDGED") {
        isAck = true;
        ackCmdId = jsonAck.command_id || jsonAck.id;
        ackTransactionId = jsonAck.transaction_id || jsonAck.tx_id;
        ackCmdType = jsonAck.command_type || jsonAck.cmd || "GO";
      }
    } catch (e) {
      // Do NOT treat arbitrary 0xAA or 0x06 bytes as ACK without verified protocol framing
      isAck = false;
    }

    const ackTimestamp = new Date().toISOString();

    if (!isAck || !ackCmdId) {
      log(`[WATCH-ACK] Rejected (ACK_REJECTED_MALFORMED): payload does not conform to verified ACK protocol framing.`);
      return { status: "rejected", reason: "ACK_REJECTED_MALFORMED" };
    }

    // 6. Stage 6: Command Correlation & Duplicate Check
    const matchedPending = pendingPhysicalCommandsMap.get(ackCmdId) || (currentAckPendingCmdId === ackCmdId ? { commandId: ackCmdId } : null);
    if (!matchedPending) {
      if (acknowledgedPhysicalCommandsSet.has(ackCmdId) || postedAckCommandIds.has(ackCmdId)) {
        log(`[WATCH-ACK] Notice (ACK_DUPLICATE_IGNORED): command ${ackCmdId} was already acknowledged. Skipping side-effects.`);
        return { status: "duplicate", reason: "ACK_DUPLICATE_IGNORED", command_id: ackCmdId };
      }
      log(`[WATCH-ACK] Rejected (ACK_REJECTED_UNKNOWN_COMMAND): no active pending command found matching ID ${ackCmdId}.`);
      return { status: "rejected", reason: "ACK_REJECTED_UNKNOWN_COMMAND" };
    }

    // 7. Stage 7: Transaction Correlation Check
    if (ackTransactionId && matchedPending.transactionId && ackTransactionId !== matchedPending.transactionId) {
      log(`[WATCH-ACK] Rejected (ACK_REJECTED_TRANSACTION_MISMATCH): transaction mismatch (received=${ackTransactionId}, expected=${matchedPending.transactionId}).`);
      return { status: "rejected", reason: "ACK_REJECTED_TRANSACTION_MISMATCH" };
    }

    // 8. Stage 8: Authoritative State Transition
    if (ackTimeoutTimer) {
      clearTimeout(ackTimeoutTimer);
      ackTimeoutTimer = null;
    }

    pendingPhysicalCommandsMap.delete(ackCmdId);
    acknowledgedPhysicalCommandsSet.add(ackCmdId);
    if (currentAckPendingCmdId === ackCmdId) {
      currentAckPendingCmdId = null;
    }
    commandDeliveryState = "WATCH_ACKNOWLEDGED";

    log(`[WATCH-ACK] Physical ACK verified from ${targetBluetoothName} for command ${ackCmdId}.`);
    log(`[WATCH-ACK] Command transitioned to WATCH_ACKNOWLEDGED (Audit: verified_ack_channel=${verifiedUuid}).`);

    console.log({
      event: "WATCH_ACK_PROCESSED",
      device_id: targetBluetoothName,
      command_id: ackCmdId,
      transaction_id: ackTransactionId || matchedPending.transactionId || null,
      command_type: ackCmdType,
      raw_ack_payload: hexDump,
      decoded_ack: decodedText,
      timestamp: ackTimestamp,
      correlation_result: "EXACT_MATCH",
      status: "HARDWARE_ACKNOWLEDGED",
    });

    // Update backend to WATCH_ACKNOWLEDGED
    reportCommandStatus(ackCmdId, "WATCH_ACKNOWLEDGED", null);

    if (activeCommandData && (activeCommandData.command_id === ackCmdId || activeCommandData.id === ackCmdId)) {
      activeCommandData.status = "WATCH_ACKNOWLEDGED";
      activeCommandData.watch_delivery_status = "WATCH_ACKNOWLEDGED";
      activeCommandData.acknowledged_at = ackTimestamp;
      updateStatusCards(activeCommandData);
    }

    // Post high-priority acknowledgement notification
    postAckNotification(ackCmdId);

    return {
      status: "success",
      command_id: ackCmdId,
      state: "HARDWARE_ACKNOWLEDGED",
      timestamp: ackTimestamp,
    };
  }

  /**
   * Priority Issue #8: Standard Bluetooth SIG Heart Rate Measurement (0x2A37) Parser.
   */
  function onHeartRateMeasurement(event) {
    if (!currentBleSessionId) {
      log("[TELEMETRY-HR] Rejected (OLD_SESSION_EVENT_REJECTED): session is no longer active.");
      return { status: "rejected", reason: "OLD_SESSION_EVENT_REJECTED" };
    }
    if (!event || !event.target || !event.target.value) {
      log("[TELEMETRY-HR] Rejected (MALFORMED_PACKET): invalid event target or empty buffer.");
      return { status: "rejected", reason: "MALFORMED_PACKET" };
    }
    const value = event.target.value;
    if (value.byteLength < 2) {
      log("[TELEMETRY-HR] Rejected (MALFORMED_PACKET): buffer too short.");
      return { status: "rejected", reason: "MALFORMED_PACKET" };
    }
    const flags = value.getUint8(0);
    const is16Bit = (flags & 0x01) !== 0;
    let hrBpm = 0;
    if (is16Bit) {
      if (value.byteLength < 3) return { status: "rejected", reason: "MALFORMED_PACKET" };
      hrBpm = value.getUint16(1, true);
    } else {
      hrBpm = value.getUint8(1);
    }

    if (hrBpm < 30 || hrBpm > 240) {
      log(`[TELEMETRY-HR] Rejected (INVALID_VALUE): heart rate ${hrBpm} bpm out of physiological range (30-240).`);
      return { status: "rejected", reason: "INVALID_VALUE", value: hrBpm };
    }

    const ts = new Date().toISOString();
    log(`[TELEMETRY_RECEIVED] Heart Rate: ${hrBpm} bpm | Device: ${targetDeviceId} | Session: ${currentBleSessionId}`);
    if (statWatchHr) statWatchHr.textContent = `${hrBpm} bpm`;
    
    // Log to backend telemetry API
    fetch(`${API_BASE}/api/wearable/telemetry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: targetDeviceId,
        latitude: 13.0827,
        longitude: 80.2707,
        heart_rate_bpm: hrBpm,
        team_id: (memberId ? memberId.split("-")[0] : "ALPHA"),
        session_id: currentBleSessionId,
      }),
    }).catch(() => {});

    return { status: "success", metric: "heart_rate", value: hrBpm, unit: "bpm", timestamp: ts };
  }

  /**
   * Priority Issue #8: Standard Bluetooth SIG Battery Level (0x2A19) Parser.
   */
  function onBatteryLevelChanged(event) {
    if (!currentBleSessionId) {
      log("[TELEMETRY-BAT] Rejected (OLD_SESSION_EVENT_REJECTED): session is no longer active.");
      return { status: "rejected", reason: "OLD_SESSION_EVENT_REJECTED" };
    }
    if (!event || !event.target || !event.target.value) {
      log("[TELEMETRY-BAT] Rejected (MALFORMED_PACKET): invalid event target or empty buffer.");
      return { status: "rejected", reason: "MALFORMED_PACKET" };
    }
    const value = event.target.value;
    if (value.byteLength < 1) {
      log("[TELEMETRY-BAT] Rejected (MALFORMED_PACKET): buffer too short.");
      return { status: "rejected", reason: "MALFORMED_PACKET" };
    }
    const batteryPct = value.getUint8(0);
    if (batteryPct < 0 || batteryPct > 100) {
      log(`[TELEMETRY-BAT] Rejected (INVALID_VALUE): battery ${batteryPct}% out of range (0-100%).`);
      return { status: "rejected", reason: "INVALID_VALUE", value: batteryPct };
    }

    const ts = new Date().toISOString();
    log(`[TELEMETRY_RECEIVED] Battery Level: ${batteryPct}% | Device: ${targetDeviceId} | Session: ${currentBleSessionId}`);
    if (statWatchBattery) statWatchBattery.textContent = `${batteryPct}%`;

    // Log to backend telemetry API
    fetch(`${API_BASE}/api/wearable/telemetry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: targetDeviceId,
        latitude: 13.0827,
        longitude: 80.2707,
        battery_pct: batteryPct,
        team_id: (memberId ? memberId.split("-")[0] : "ALPHA"),
        session_id: currentBleSessionId,
      }),
    }).catch(() => {});

    return { status: "success", metric: "battery", value: batteryPct, unit: "%", timestamp: ts };
  }

  function postAckNotification(cmdId) {
    if (!cmdId) return;
    if (postedAckCommandIds.has(cmdId)) {
      return;
    }
    postedAckCommandIds.add(cmdId);
    sessionStorage.setItem("ridgewatch_posted_ack_cmd_ids", JSON.stringify(Array.from(postedAckCommandIds)));

    const title = "🚨 RIDGEWATCH — GO ACKNOWLEDGED";
    const memberName = memberSelect ? memberSelect.options[memberSelect.selectedIndex]?.text.split("(")[0].trim() : (memberId || "Alpha Member 1");
    const memId = memberId || "ALPHA-M001";
    const body = `${memberName} / ${memId} confirmed receipt from Wave Call Plus.`;

    log(`[NOTIFICATION] RIDGEWATCH GO ACKNOWLEDGED`);
    log(`[NOTIFICATION] GO acknowledgement posted: "${title}"`);

    if ("Notification" in window && Notification.permission === "granted") {
      try {
        const notif = new Notification(title, {
          body: body,
          icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🚨</text></svg>",
          tag: `ACK-${cmdId}`,
          requireInteraction: true,
        });
        notif.onclick = () => {
          window.focus();
        };
        log(`[NOTIFICATION] Native notification displayed`);
      } catch (e) {
        log(`ℹ️ System notification notice: ${e.message}`);
      }
    } else {
      log(`[NOTIFICATION] Permission unavailable`);
    }
  }

  async function reportCommandStatus(cmdId, status, errorMsg) {
    try {
      const res = await fetch(`${apiBase}/api/wearable/commands/${cmdId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: status,
          delivery_error: errorMsg || null,
        }),
      });
      if (res.ok) {
        console.log(`[STATUS_SYNC] Reported ${status} for ${cmdId} -> 200`);
        if (status === "WATCH_ACKNOWLEDGED") {
          log(`[BACKEND] Command status updated: WATCH_ACKNOWLEDGED`);
        }
      }
    } catch (err) {
      console.warn(`[STATUS_SYNC] Status reporting failed for ${cmdId}: ${err.message}`);
    }
  }

  function openBleModal() {
    if (bleModalOverlay) {
      bleModalOverlay.style.display = "flex";
      updateBleModalUI();
    }
  }

  function closeBleModal() {
    if (bleModalOverlay) {
      bleModalOverlay.style.display = "none";
    }
  }

  function setBleModalMessage(text, isError = false) {
    if (!bleModalMsg) return;
    bleModalMsg.style.display = "block";
    bleModalMsg.style.color = isError ? "#b91c1c" : "#1e293b";
    bleModalMsg.style.background = isError ? "#fee2e2" : "#f1f5f9";
    bleModalMsg.innerHTML = text;
  }

  function updateBleModalUI() {
    if (!bleModalStatusBadge) return;
    if (watchConnected && activeGattServer && activeGattServer.connected) {
      bleModalStatusBadge.textContent = "CONNECTED (GATT)";
      bleModalStatusBadge.style.background = "#dcfce7";
      bleModalStatusBadge.style.color = "#15803d";
      if (btnBleModalDisconnect) btnBleModalDisconnect.style.display = "block";
    } else if (watchConnectionState === "CONNECTING") {
      bleModalStatusBadge.textContent = "CONNECTING...";
      bleModalStatusBadge.style.background = "#fef3c7";
      bleModalStatusBadge.style.color = "#b45309";
      if (btnBleModalDisconnect) btnBleModalDisconnect.style.display = "none";
    } else if (watchConnectionState === "UNAUTHORIZED_WATCH_REJECTED" || watchConnectionState === "BLE_CONNECTION_FAILED") {
      bleModalStatusBadge.textContent = "REJECTED / FAILED";
      bleModalStatusBadge.style.background = "#fee2e2";
      bleModalStatusBadge.style.color = "#dc2626";
      if (btnBleModalDisconnect) btnBleModalDisconnect.style.display = "none";
    } else {
      bleModalStatusBadge.textContent = "DISCONNECTED";
      bleModalStatusBadge.style.background = "#fee2e2";
      bleModalStatusBadge.style.color = "#dc2626";
      if (btnBleModalDisconnect) btnBleModalDisconnect.style.display = "none";
    }
  }

  async function directHardwareConnect() {
    log("[WATCH] Connecting to Wave Call Plus via Web Bluetooth...");
    return await connectWebBluetooth();
  }

  async function disconnectWatch() {
    log("[WATCH] Disconnecting physical watch...");
    if (activeGattServer && activeGattServer.connected) {
      try {
        activeGattServer.disconnect();
      } catch (e) {}
    }
    await onGattDisconnected();
    updateBleModalUI();
  }

  async function connectWebBluetooth() {
    if (!navigator.bluetooth) {
      setBleModalMessage("⚠️ Web Bluetooth API is not supported in this browser context. Please open Google Chrome on Android or Desktop to connect physical Wave Call Plus.", true);
      log("[WATCH] Web Bluetooth API not supported in this browser context.");
      log("[WATCH] BLE_CONNECTION_FAILED: Web Bluetooth unavailable");
      log("[WATCH] Physical watch remains disconnected");
      watchConnected = false;
      watchConnectionState = "BLE_CONNECTION_FAILED";
      commandDeliveryState = "WATCH_DISCONNECTED";
      activeGattServer = null;
      activeBluetoothDevice = null;
      bluetoothEnabled = true;
      updateStatusCards(activeCommandData);
      updateBleModalUI();
      await notifyBackendDisconnect();
      await sendHeartbeat();
      return;
    }

    try {
      log("[WATCH] Starting real Bluetooth connection...");
      log(`[WATCH] Requesting Bluetooth device with filter: name = "${targetBluetoothName}"...`);
      watchConnectionState = "CONNECTING";
      commandDeliveryState = "WATCH_CONNECTING";
      updateStatusCards(activeCommandData);
      updateBleModalUI();
      setBleModalMessage(`🔍 Scanning for Wave Call Plus (<code>${targetBluetoothName}</code>)... Select your watch in the browser chooser dialog.`);

      const ALL_OPTIONAL_SERVICES = [
        "device_information",
        "heart_rate",
        "battery_service",
        "immediate_alert",
        "link_loss",
        "tx_power",
        "alert_notification",
        "phone_alert_status",
        0x1800,
        0x1801,
        0x1802,
        0x1803,
        0x1804,
        0x180a,
        0x180d,
        0x180e,
        0x180f,
        0x1811,
        0x1821,
        0x1822,
        0xfea0,
        0xffe0,
        0xfee0,
        0xfff0,
        "6e400001-b5a3-f393-e0a9-e50e24dcca9e",
        "00001802-0000-1000-8000-00805f9b34fb",
        "00001811-0000-1000-8000-00805f9b34fb",
        "0000fea0-0000-1000-8000-00805f9b34fb",
        "0000ffe0-0000-1000-8000-00805f9b34fb",
        "0000fee0-0000-1000-8000-00805f9b34fb",
        "0000fff0-0000-1000-8000-00805f9b34fb",
      ];

      let device = null;
      try {
        device = await navigator.bluetooth.requestDevice({
          filters: [
            { name: targetBluetoothName },
          ],
          optionalServices: ALL_OPTIONAL_SERVICES,
        });
      } catch (filterErr) {
        if (filterErr.name !== "NotFoundError") {
          device = await navigator.bluetooth.requestDevice({
            acceptAllDevices: true,
            optionalServices: ALL_OPTIONAL_SERVICES,
          });
        } else {
          throw filterErr;
        }
      }

      log(`[WATCH] Selected device: ${device ? (device.name || "Unknown") : "None"}`);

      // Strict Device Identity Validation BEFORE GATT Connection
      const validation = isApprovedWearable(device);
      if (!validation.approved) {
        const selectedName = device ? (device.name || "Unnamed device") : "No device";
        log(`[BLE] Device discovered: Name="${selectedName}"`);
        log(`[BLE] Identity validation=FAILED | Reason=${validation.reason}`);
        log(`[BLE] Connection blocked.`);

        if (device && device.gatt && device.gatt.connected) {
          try { device.gatt.disconnect(); } catch (e) {}
        }

        // If CALLPLUS_7F1B is already active, preserve primary session
        if (watchConnected && activeGattServer && activeGattServer.connected && activeBluetoothDevice && activeBluetoothDevice.name === targetBluetoothName) {
          log(`[SECOND_WEARABLE_REJECTED] Device "${selectedName}" rejected. Active session "${targetBluetoothName}" preserved.`);
          setBleModalMessage(`⚠️ Second device "<strong>${selectedName}</strong>" rejected. Active watch <strong>${targetBluetoothName}</strong> remains connected.`, true);
          return;
        }

        watchConnected = false;
        watchConnectionState = "UNAUTHORIZED_WATCH_REJECTED";
        commandDeliveryState = "WATCH_DISCONNECTED";
        activeGattServer = null;
        activeBluetoothDevice = null;
        updateStatusCards(activeCommandData);
        updateBleModalUI();
        setBleModalMessage(`❌ Unsupported Bluetooth device: "<strong>${selectedName}</strong>". Please select <strong>${SUPPORTED_WEARABLE_CONFIG.deviceName}</strong>.`, true);
        await notifyBackendDisconnect();
        await sendHeartbeat();
        return;
      }

      log(`[BLE] Device discovered: Name=${device.name}`);
      log(`[BLE] Identity validation=PASSED | Wearable=${validation.wearableId}`);
      log(`[BLE] Connecting to approved wearable GATT server...`);
      
      // Priority Issue #7: Increment generation and initialize fresh session ID
      const sessionGen = ++bleConnectionGeneration;
      currentBleSessionId = `BLE-SESS-${Date.now()}-${sessionGen}`;

      activeBluetoothDevice = device;
      device.addEventListener("gattserverdisconnected", onGattDisconnected);

      setBleModalMessage(`⚡ Found <strong>${device.name}</strong>. Connecting GATT Server (Session ${currentBleSessionId})...`);
      log(`[WATCH] Connecting to GATT (Session: ${currentBleSessionId})...`);
      const server = await device.gatt.connect();
      if (!server || !server.connected) {
        throw new Error("GATT server connection could not be established.");
      }
      activeGattServer = server;
      log("[WATCH] GATT connection successful");

      // Deep Capability-Based Discovery
      log("[WATCH] Discovering GATT services & characteristics...");
      BLE_CAPABILITIES = {
        deviceInformation: null,
        battery: null,
        heartRate: null,
        immediateAlert: null,
        alertNotification: null,
        commandChannel: null, // ONLY set if verified
        acknowledgementChannel: null, // ONLY set if verified
        discoveredServices: [],
        discoveredCharacteristics: [],
      };

      try {
        if (bleConnectionGeneration !== sessionGen || !activeGattServer || !activeGattServer.connected) {
          log(`[BLE] GATT discovery aborted: session ${sessionGen} superseded or disconnected.`);
          return;
        }
        const services = await server.getPrimaryServices();
        log(`[WATCH] Services discovered: ${services.length} GATT Services on Wave Call Plus.`);
        
        for (const svc of services) {
          const svcUuidLower = svc.uuid.toLowerCase();
          BLE_CAPABILITIES.discoveredServices.push(svc.uuid);
          log(`  • Service: ${svc.uuid}`);
          
          try {
            const chars = await svc.getCharacteristics();
            for (const ch of chars) {
              const props = [];
              if (ch.properties.read) props.push("READ");
              if (ch.properties.write) props.push("WRITE");
              if (ch.properties.writeWithoutResponse) props.push("WRITE_NO_RESP");
              if (ch.properties.notify) props.push("NOTIFY");
              if (ch.properties.indicate) props.push("INDICATE");
              
              BLE_CAPABILITIES.discoveredCharacteristics.push({
                serviceUuid: svc.uuid,
                uuid: ch.uuid,
                properties: props,
              });

              log(`    └ Characteristic: ${ch.uuid} [${props.join(", ")}]`);

              const uuidLower = ch.uuid.toLowerCase();

              // Map standard known services
              if (svcUuidLower.includes("180a") || uuidLower.includes("2a24") || uuidLower.includes("2a29")) {
                BLE_CAPABILITIES.deviceInformation = ch;
              }
              if (svcUuidLower.includes("180d") || uuidLower.includes("2a37")) {
                BLE_CAPABILITIES.heartRate = ch;
              }
              if (svcUuidLower.includes("180f") || uuidLower.includes("2a19")) {
                BLE_CAPABILITIES.battery = ch;
              }
              if (svcUuidLower.includes("1802") || uuidLower.includes("2a06")) {
                BLE_CAPABILITIES.immediateAlert = ch;
              }
              if (svcUuidLower.includes("1811") || uuidLower.includes("2a46")) {
                BLE_CAPABILITIES.alertNotification = ch;
              }

              // Vendor characteristics: Record discovery without assuming command or ACK roles
              if (uuidLower.includes("fea1")) {
                log(`    └ [BLE] Vendor Characteristic: 0xFEA1 discovered | writable=${Boolean(ch.properties.write || ch.properties.writeWithoutResponse)} | command_role=UNVERIFIED`);
                recordGattDiagnosticPacket("OUTGOING", svc.uuid, ch.uuid, [], "DISCOVERED_PROPRIETARY_WRITE_CHANNEL (Direct writes safely disabled: DIRECT_GATT_UNVERIFIED)");
              }
              if (uuidLower.includes("fea2")) {
                log(`    └ [BLE] Vendor Characteristic: 0xFEA2 discovered | ack_role=UNVERIFIED`);
                recordGattDiagnosticPacket("INCOMING", svc.uuid, ch.uuid, [], "DISCOVERED_PROPRIETARY_NOTIFY_CHANNEL (Unverified as ACK: ACK_PROTOCOL_UNKNOWN)");
              }

              // Safe observe-first read for standard descriptors
              if (ch.properties.read && (svcUuidLower.includes("180a") || svcUuidLower.includes("1800") || svcUuidLower.includes("180f"))) {
                try {
                  const readVal = await ch.readValue();
                  const rec = recordGattDiagnosticPacket("INCOMING", svc.uuid, ch.uuid, readVal, `Standard Descriptor Read (${ch.uuid})`);
                  log(`      ↳ [READ ${ch.uuid}] "${rec.ascii}" (${rec.hexString})`);
                } catch (rdErr) {
                  // Non-fatal notice
                }
              }
            }
          } catch (charErr) {
            log(`    ℹ️ [BLE] Characteristic enumeration notice on ${svc.uuid}: ${charErr.message}`);
          }
        }

        log("[WATCH] Capability discovery complete.");

        // Phase 6 & 7: Resolve verified command and ACK characteristics via explicit evidence registry
        verifiedCommandCharacteristic = resolveVerifiedCommandCharacteristic(BLE_CAPABILITIES.discoveredCharacteristics, PROTOCOL_EVIDENCE_REGISTRY);
        verifiedAckCharacteristic = resolveVerifiedAckCharacteristic(BLE_CAPABILITIES.discoveredCharacteristics, PROTOCOL_EVIDENCE_REGISTRY);

        BLE_CAPABILITIES.commandChannel = verifiedCommandCharacteristic;
        BLE_CAPABILITIES.acknowledgementChannel = verifiedAckCharacteristic;

        // Phase 18: Detailed diagnostics output
        log(`[BLE] Device connected: ${targetBluetoothName}`);
        log(`[BLE] GATT connected: ${Boolean(activeGattServer && activeGattServer.connected)}`);
        log(`[BLE] Services discovered: ${services.length}`);
        log(`[BLE] Characteristics discovered: ${BLE_CAPABILITIES.discoveredCharacteristics.length}`);
        log(`[BLE] Verified command characteristic: ${verifiedCommandCharacteristic ? (verifiedCommandCharacteristic.uuid || "VERIFIED") : "None (UNVERIFIED)"}`);
        log(`[BLE] Verified ACK characteristic: ${verifiedAckCharacteristic ? (verifiedAckCharacteristic.uuid || "VERIFIED") : "None (UNVERIFIED)"}`);

        // Phase 8: Subscribe ONLY if verified ACK characteristic exists
        if (verifiedAckCharacteristic) {
          try {
            await verifiedAckCharacteristic.startNotifications();
            verifiedAckCharacteristic.addEventListener("characteristicvaluechanged", onWatchAckNotification);
            log(`[BLE] Subscribed to verified ACK notifications on ${verifiedAckCharacteristic.uuid}`);
          } catch (notifErr) {
            log(`⚠️ [BLE] Failed to subscribe to verified ACK notifications: ${notifErr.message}`);
          }
        }

        // Priority Issue #8: Subscribe to Heart Rate and Battery telemetry
        if (BLE_CAPABILITIES.heartRate) {
          try {
            await BLE_CAPABILITIES.heartRate.startNotifications();
            BLE_CAPABILITIES.heartRate.addEventListener("characteristicvaluechanged", onHeartRateMeasurement);
            log(`[BLE] Subscribed to Heart Rate telemetry on ${BLE_CAPABILITIES.heartRate.uuid}`);
          } catch (hrErr) {
            log(`ℹ️ [BLE] Heart rate telemetry notification setup: ${hrErr.message}`);
          }
        }

        if (BLE_CAPABILITIES.battery) {
          try {
            if (BLE_CAPABILITIES.battery.properties && (BLE_CAPABILITIES.battery.properties.notify || BLE_CAPABILITIES.battery.properties.indicate)) {
              await BLE_CAPABILITIES.battery.startNotifications();
              BLE_CAPABILITIES.battery.addEventListener("characteristicvaluechanged", onBatteryLevelChanged);
              log(`[BLE] Subscribed to Battery telemetry notifications on ${BLE_CAPABILITIES.battery.uuid}`);
            }
            if (BLE_CAPABILITIES.battery.properties && BLE_CAPABILITIES.battery.properties.read) {
              const batVal = await BLE_CAPABILITIES.battery.readValue();
              onBatteryLevelChanged({ target: { value: batVal } });
            }
          } catch (batErr) {
            log(`ℹ️ [BLE] Battery telemetry setup: ${batErr.message}`);
          }
        }

        console.log({
          event: "BLE_CAPABILITIES_DISCOVERED",
          device_name: targetBluetoothName,
          mac_address: targetMac,
          services_count: services.length,
          capabilities: {
            device_information: Boolean(BLE_CAPABILITIES.deviceInformation),
            battery: Boolean(BLE_CAPABILITIES.battery),
            heart_rate: Boolean(BLE_CAPABILITIES.heartRate),
            immediate_alert: Boolean(BLE_CAPABILITIES.immediateAlert),
            alert_notification: Boolean(BLE_CAPABILITIES.alertNotification),
            command_channel: Boolean(BLE_CAPABILITIES.commandChannel),
            acknowledgement_channel: Boolean(BLE_CAPABILITIES.acknowledgementChannel),
          },
          timestamp: new Date().toISOString(),
        });
      } catch (svcErr) {
        log(`ℹ️ [BLE] Services enumeration note: ${svcErr.message}`);
      }

      // State is set to CONNECTED ONLY after real physical GATT connection and discovery succeed
      watchConnected = true;
      watchConnectionState = "CONNECTED";
      commandDeliveryState = "WATCH_CONNECTED";
      bluetoothEnabled = true;

      log("[WATCH] Physical watch connected (WATCH_BLE_CONNECTED)");
      log(`⌚ Wave Call Plus (${targetBluetoothName}) is now REAL_PHYSICAL_BLE_CONNECTED.`);

      updateStatusCards(activeCommandData);
      updateBleModalUI();
      setBleModalMessage(`✅ <strong>Wave Call Plus (${device.name})</strong> is CONNECTED (Physical BLE).`);

      await notifyBackendConnect();

      if (activeCommandData && !postedCommandIds.has(activeCommandData.command_id)) {
        log(`⚡ Delivering pending rescue command ${activeCommandData.command_id} to connected watch.`);
        await handleIncomingCommand(activeCommandData);
      }
      await sendHeartbeat();
    } catch (err) {
      log(`[WATCH] BLE_CONNECTION_FAILED: ${err.message || err}`);
      log("[WATCH] Physical watch remains disconnected");

      if (activeGattServer && activeGattServer.connected) {
        try { activeGattServer.disconnect(); } catch (e) {}
      }
      activeGattServer = null;
      activeBluetoothDevice = null;
      watchConnected = false;
      watchConnectionState = err.name === "NotFoundError" ? "DISCONNECTED" : "BLE_CONNECTION_FAILED";
      commandDeliveryState = err.name === "NotFoundError" ? "WATCH_DISCONNECTED" : "GATT_ERROR";
      bluetoothEnabled = true;

      if (err.name === "NotFoundError") {
        setBleModalMessage("ℹ️ Pairing cancelled or no device selected in browser dialog.");
        log("ℹ️ Web Bluetooth scan cancelled by user.");
      } else {
        setBleModalMessage(`⚠️ Wave Call Plus Connection Failed: ${err.message}`, true);
        log(`ℹ️ Web Bluetooth: ${err.message || err}. Watch state: DISCONNECTED.`);
      }

      updateStatusCards(activeCommandData);
      updateBleModalUI();
      await notifyBackendDisconnect();
      await sendHeartbeat();
    }
  }

  async function notifyBackendConnecting() {
    try {
      await fetch(`${apiBase}/api/wearable/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: "BLE_CONNECT_REQUESTED",
          wearable_id: SUPPORTED_WEARABLE_CONFIG.wearableId,
          device_name: SUPPORTED_WEARABLE_CONFIG.deviceName,
          physical_connected: false,
          mac_address: targetMac,
        }),
      });
    } catch (e) {
      // Backend sync fallback
    }
  }

  async function notifyBackendConnect() {
    try {
      await fetch(`${apiBase}/api/wearable/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: "BLE_GATT_CONNECTED",
          wearable_id: SUPPORTED_WEARABLE_CONFIG.wearableId,
          device_name: SUPPORTED_WEARABLE_CONFIG.deviceName,
          physical_connected: true,
          mac_address: targetMac,
        }),
      });
    } catch (e) {
      // Backend sync fallback
    }
  }

  async function notifyBackendDisconnect() {
    try {
      await fetch(`${apiBase}/api/wearable/disconnect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event: "BLE_GATT_DISCONNECTED",
          wearable_id: SUPPORTED_WEARABLE_CONFIG.wearableId,
          device_name: SUPPORTED_WEARABLE_CONFIG.deviceName,
          physical_connected: false,
        }),
      });
    } catch (e) {
      // Backend sync fallback
    }
  }

  function showEmergencyPopup(cmd) {
    if (!emergencyPopupOverlay) return;
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (emergencyPopupTime) emergencyPopupTime.textContent = timeStr;

    const title = cmd.notification_payload?.title || "🔴 EMERGENCY ALERT";
    const victim = cmd.victim_id || cmd.target_id || "Survivor";
    const loc = cmd.location || cmd.location_label || "Target Sector";
    const dist = cmd.distance_label || (cmd.distance_m ? `${Math.round(cmd.distance_m)} m` : "Distance unavailable");
    const tId = cmd.team_id || teamId || "ALPHA";

    if (emergencyPopupTitle) emergencyPopupTitle.textContent = `Survivor Detected: ${victim}`;
    if (emergencyPopupMsg) emergencyPopupMsg.textContent = cmd.command_text || `Emergency rescue required at ${loc}.`;
    if (emergencyPopupDist) emergencyPopupDist.textContent = `📍 Distance: ${dist}`;
    if (emergencyPopupTarget) emergencyPopupTarget.textContent = `🎯 Target: ${loc}`;
    if (emergencyPopupTeam) emergencyPopupTeam.textContent = `👥 Team: ${tId}`;

    updatePipelineUI();

    emergencyPopupOverlay.style.display = "block";

    // Auto-dismiss popup after 8 seconds (leaving alert preserved in Notification Center)
    if (popupAutoDismissTimer) clearTimeout(popupAutoDismissTimer);
    popupAutoDismissTimer = setTimeout(() => {
      if (emergencyPopupOverlay) {
        emergencyPopupOverlay.style.display = "none";
      }
    }, 8000);
  }

  function dismissEmergencyPopup(cmdId) {
    const targetId = cmdId || (activeCommandData ? activeCommandData.command_id : null);
    if (targetId) {
      markMissionDismissed(targetId);
    }
    if (emergencyPopupOverlay) {
      emergencyPopupOverlay.style.display = "none";
    }
    if (popupAutoDismissTimer) {
      clearTimeout(popupAutoDismissTimer);
      popupAutoDismissTimer = null;
    }
  }

  function updatePipelineUI() {
    const isBt = watchConnected && activeGattServer && activeGattServer.connected;
    if (pipeBt) {
      pipeBt.className = isBt ? "pipe-step is-active" : "pipe-step is-error";
      pipeBt.innerHTML = `<span class="pipe-dot"></span> BLE: ${isBt ? "Connected" : "Disconnected"}`;
    }
    if (pipeGatt) {
      pipeGatt.className = isBt ? "pipe-step is-active" : (watchConnectionState === "CONNECTING" ? "pipe-step is-pending" : "pipe-step");
      pipeGatt.innerHTML = `<span class="pipe-dot"></span> GATT: ${isBt ? "Ready" : (watchConnectionState === "CONNECTING" ? "Preparing" : "Waiting")}`;
    }
    if (pipeSent) {
      const isGattSent = commandDeliveryState === "GATT_WRITE_CONFIRMED" || commandDeliveryState === "COMMAND_SENT";
      const isPhoneMirrored = commandDeliveryState === "PHONE_NOTIFICATION_POSTED";
      const isFailed = commandDeliveryState === "COMMAND_WRITE_FAILED";
      const isAttempted = commandDeliveryState === "DELIVERY_ATTEMPTED";
      const isDisc = commandDeliveryState === "WATCH_DISCONNECTED";

      if (isGattSent) {
        pipeSent.className = "pipe-step is-active";
        pipeSent.innerHTML = `<span class="pipe-dot"></span> Watch: Command Written (GATT)`;
      } else if (isPhoneMirrored) {
        pipeSent.className = "pipe-step is-active";
        pipeSent.innerHTML = `<span class="pipe-dot"></span> Watch: Notification Mirrored`;
      } else if (isAttempted) {
        pipeSent.className = "pipe-step is-error";
        pipeSent.innerHTML = `<span class="pipe-dot"></span> Watch: Notification Not Posted (Permission Required)`;
      } else if (isFailed) {
        pipeSent.className = "pipe-step is-error";
        pipeSent.innerHTML = `<span class="pipe-dot"></span> Watch: Delivery Failed`;
      } else if (isDisc) {
        pipeSent.className = "pipe-step is-error";
        pipeSent.innerHTML = `<span class="pipe-dot"></span> Watch: Disconnected`;
      } else {
        pipeSent.className = "pipe-step is-pending";
        pipeSent.innerHTML = `<span class="pipe-dot"></span> Watch: Pending`;
      }
    }
    if (pipeAck) {
      const isHwAck = commandDeliveryState === "WATCH_ACKNOWLEDGED";
      const isUserAccepted = commandDeliveryState === "USER_ACCEPTED" || commandDeliveryState === "OPERATOR_CONFIRMED";
      const isTimeout = commandDeliveryState === "ACK_TIMEOUT";

      if (isHwAck) {
        pipeAck.className = "pipe-step is-active";
        pipeAck.innerHTML = `<span class="pipe-dot"></span> ACK: Wave Call Plus Acknowledged`;
      } else if (isUserAccepted) {
        pipeAck.className = "pipe-step is-active";
        pipeAck.innerHTML = `<span class="pipe-dot"></span> ACK: Rescuer Confirmed (Waiting Watch ACK)`;
      } else if (isTimeout) {
        pipeAck.className = "pipe-step is-error";
        pipeAck.innerHTML = `<span class="pipe-dot"></span> ACK: Timeout`;
      } else {
        pipeAck.className = "pipe-step is-pending";
        pipeAck.innerHTML = `<span class="pipe-dot"></span> ACK: Pending`;
      }
    }
  }

  async function acceptEmergencyAlert(cmdId) {
    const targetId = cmdId || currentAckPendingCmdId || (activeCommandData ? activeCommandData.command_id : null);
    if (!targetId) {
      log("⚠️ [OPERATOR] No active rescue command pending acceptance.");
      return false;
    }

    log(`[RESCUER_CONFIRMATION_RECEIVED] Rescuer initiated manual confirmation for command: ${targetId}`);
    log(`⏳ [OPERATOR] Dispatching Rescuer Confirmation for ${targetId} to backend...`);

    // Permanently dismiss popup for this mission
    markMissionDismissed(targetId);
    if (emergencyPopupOverlay) {
      emergencyPopupOverlay.style.display = "none";
    }
    if (popupAutoDismissTimer) {
      clearTimeout(popupAutoDismissTimer);
      popupAutoDismissTimer = null;
    }

    try {
      const ackUrl = `${apiBase}/api/wearable/commands/${encodeURIComponent(targetId)}/ack?member_id=${encodeURIComponent(memberId || "")}&device_id=${encodeURIComponent(targetDeviceId || "DEV-WEARABLE-CALLPLUS")}&source=RESCUER_CONFIRMATION`;
      const res = await fetch(ackUrl, { method: "POST" });

      if (!res.ok) {
        let errDetail = `HTTP ${res.status}`;
        try {
          const errJson = await res.json();
          if (errJson && errJson.detail) errDetail = errJson.detail;
        } catch (_) {}
        log(`❌ [RESCUER_CONFIRMATION_REJECTED] Rescuer confirmation rejected: ${errDetail}`);
      } else {
        const resData = await res.json();
        log(`[RESCUER_CONFIRMATION_ACCEPTED] Rescuer Accepted Emergency Alert ${targetId} (Manual Confirmation Recorded).`);
        log(`ℹ️ [SEMANTICS] Rescuer Confirmation is independent from physical watch hardware ACK.`);
      }

      // Update state: Rescuer confirmed (does NOT overwrite physical watch ACK)
      commandDeliveryState = "USER_ACCEPTED";
      updatePipelineUI();

      await reportCommandStatus(targetId, "USER_ACCEPTED", null);
      if (activeCommandData) {
        activeCommandData.status = "USER_ACCEPTED";
        activeCommandData.rescuer_confirmed = true;
        activeCommandData.rescuer_confirmation_status = "RESCUER_CONFIRMED";
        activeCommandData.rescuer_confirmed_at = new Date().toISOString();
        updateStatusCards(activeCommandData);
      }
      await loadNotificationCenter();
      return true;
    } catch (e) {
      log(`❌ [OPERATOR] Network note during command confirmation: ${e.message}`);
      // Still ensure state is updated locally so the UI does not crash or loop
      commandDeliveryState = "USER_ACCEPTED";
      updatePipelineUI();
      if (activeCommandData) {
        activeCommandData.status = "USER_ACCEPTED";
        updateStatusCards(activeCommandData);
      }
      return false;
    }
  }

  async function loadNotificationCenter() {
    if (!notifCenterList) return;
    try {
      const res = await fetch(`${apiBase}/api/wearable/notifications?team_id=${teamId}`);
      if (res.ok) {
        const data = await res.json();
        const notifs = data.notifications || [];
        if (notifCenterCount) notifCenterCount.textContent = `${notifs.length} Alert${notifs.length === 1 ? "" : "s"}`;

        if (notifs.length === 0) {
          notifCenterList.innerHTML = `<div class="notif-empty">No emergency alerts recorded yet.</div>`;
          return;
        }

        notifCenterList.innerHTML = notifs.map((n) => {
          const date = new Date(n.timestamp || Date.now());
          const timeFormatted = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
          const isDelivered = n.watch_delivery_status === "DELIVERED" || n.watch_delivery_status === "COMMAND_SENT" || n.watch_delivery_status === "PHONE_NOTIFICATION_POSTED";
          const isAccepted = n.watch_ack_status === "ACCEPTED" || n.status === "USER_ACCEPTED";
          const distLabel = n.distance_label || (n.distance_m ? `${Math.round(n.distance_m)} m` : "Distance unavailable");

          return `
            <div class="notif-item">
              <div class="notif-item-top">
                <div class="notif-title">🔴 ${n.title || "Emergency Alert"}</div>
                <div class="notif-time">${timeFormatted}</div>
              </div>
              <div class="notif-msg">${n.message || "Survivor detected"}</div>
              <div class="notif-badges-row">
                <span class="notif-dist-pill">📍 ${distLabel}</span>
                <span class="notif-status-pill ${isDelivered ? "is-ok" : ""}">Watch: ${n.watch_delivery_status || "PENDING"}</span>
                <span class="notif-status-pill ${isAccepted ? "is-ok" : ""}">ACK: ${n.watch_ack_status || "PENDING"}</span>
                ${!isAccepted ? `<button style="margin-left: auto; padding: 2px 8px; font-size: 0.72rem; font-weight: 700; background: #16a34a; color: #fff; border: none; border-radius: 4px; cursor: pointer;" onclick="window._bridgeAcceptAlert('${n.alert_id || n.id}')">Accept</button>` : `<span style="margin-left: auto; color: #16a34a; font-weight: 800; font-size: 0.75rem;">✓ Accepted</span>`}
              </div>
            </div>
          `;
        }).join("");
      }
    } catch (e) {
      console.warn("Notification center load note:", e);
    }
  }

  window._bridgeAcceptAlert = (id) => {
    acceptEmergencyAlert(id);
  };

  /**
   * Dedicated rescue command dispatch through an explicitly verified GATT command characteristic.
   * STRICT SAFETY GUARANTEES:
   * 1. Exactly ONE verified target (verifiedCommandCharacteristic).
   * 2. ZERO loops across writable characteristics.
   * 3. ZERO multi-characteristic fallbacks.
   * 4. Returns COMMAND_CHANNEL_UNVERIFIED if no verified characteristic exists.
   */
  async function sendRescueCommandThroughVerifiedGattChannel(cmd) {
    const channelValidation = validateCommandChannel(verifiedCommandCharacteristic);
    if (!channelValidation.valid) {
      log(`[COMMAND] Direct GATT command requested: channel_status=${channelValidation.status}`);
      log(`[COMMAND] Direct GATT command blocked: reason=${channelValidation.reason} | transport=ANDROID_COMPANION`);
      return {
        success: false,
        status: channelValidation.status === "UNVERIFIED" ? "DIRECT_GATT_UNVERIFIED" : "COMMAND_CHANNEL_UNAVAILABLE",
        channel_status: channelValidation.status,
        transport: "ANDROID_COMPANION",
        message: "Direct watch command unavailable — protocol not verified. Rescue command routes through Android Companion.",
      };
    }

    // 1. Verify authorized device identity
    if (!activeBluetoothDevice || activeBluetoothDevice.name !== targetBluetoothName) {
      log(`❌ [BLE] Unauthorized or mismatch device: ${activeBluetoothDevice ? activeBluetoothDevice.name : "None"}.`);
      return {
        success: false,
        status: "UNAUTHORIZED_WATCH",
        message: `Device is not authorized ${targetBluetoothName}.`,
      };
    }

    // 2. Verify active physical GATT server connection
    if (!activeGattServer || !activeGattServer.connected) {
      log("❌ [BLE] Cannot send command: GATT server is disconnected.");
      return {
        success: false,
        status: "WATCH_BLE_DISCONNECTED",
        message: "Physical watch is disconnected.",
      };
    }

    // 3. Verify characteristic belongs to active GATT session
    if (!verifiedCommandCharacteristic.service || !verifiedCommandCharacteristic.service.device || !verifiedCommandCharacteristic.service.device.gatt || !verifiedCommandCharacteristic.service.device.gatt.connected) {
      log("❌ [BLE] Stale command characteristic detected.");
      return {
        success: false,
        status: "STALE_GATT_CHARACTERISTIC",
        message: "Characteristic belongs to a stale or severed GATT session.",
      };
    }

    // 4. Validate payload
    const cmdId = cmd.command_id || (cmd.notification_payload && cmd.notification_payload.command_id);
    if (!cmdId) {
      return {
        success: false,
        status: "INVALID_COMMAND_PAYLOAD",
        message: "Command ID missing.",
      };
    }

    // 5. Build structured command packet through verified encoder
    const packets = buildRidgewatchGoCommand(cmd);
    const packetAscii = packets.asciiPacket;
    const packetJson = packets.jsonPacket;

    let successfulGattWrite = false;
    let attemptedGattWrites = 0;
    let failedGattWrites = 0;
    let lastWriteError = null;

    const canWriteNoResp = verifiedCommandCharacteristic.properties && verifiedCommandCharacteristic.properties.writeWithoutResponse;
    const canWriteWithResp = verifiedCommandCharacteristic.properties && verifiedCommandCharacteristic.properties.write;

    if (!canWriteNoResp && !canWriteWithResp) {
      log("❌ [BLE] Verified characteristic lacks writable properties.");
      return {
        success: false,
        status: "COMMAND_CHANNEL_UNAVAILABLE",
        message: "Characteristic lacks write capabilities.",
      };
    }

    const svcUuid = (verifiedCommandCharacteristic.service && verifiedCommandCharacteristic.service.uuid) || "UNKNOWN";
    const charUuid = verifiedCommandCharacteristic.uuid || "UNKNOWN";

    log(`[BLE] Writing rescue command to verified command characteristic (${charUuid})...`);
    log(`[BLE] Trace: cmd_id=${cmdId} device=${targetDeviceId} service=${svcUuid} char=${charUuid} time=${new Date().toISOString()}`);

    // Primary attempt: ASCII packet
    attemptedGattWrites++;
    try {
      if (canWriteNoResp) {
        await verifiedCommandCharacteristic.writeValueWithoutResponse(packetAscii);
      } else {
        await verifiedCommandCharacteristic.writeValue(packetAscii);
      }
      successfulGattWrite = true;
      recordGattDiagnosticPacket("OUTGOING", svcUuid, charUuid, packetAscii, `COMMAND_SENT_TO_GATT (cmd: ${cmdId})`);
    } catch (errPrimary) {
      failedGattWrites++;
      lastWriteError = errPrimary;
      log(`⚠️ [BLE] Primary write failed on ${charUuid}: ${errPrimary.message}. Attempting fallback payload...`);

      // Fallback attempt: JSON packet
      attemptedGattWrites++;
      try {
        if (canWriteNoResp) {
          await verifiedCommandCharacteristic.writeValueWithoutResponse(packetJson);
        } else {
          await verifiedCommandCharacteristic.writeValue(packetJson);
        }
        successfulGattWrite = true;
        recordGattDiagnosticPacket("OUTGOING", svcUuid, charUuid, packetJson, `COMMAND_SENT_TO_GATT (cmd: ${cmdId})`);
      } catch (errFallback) {
        failedGattWrites++;
        lastWriteError = errFallback;
      }
    }

    if (!successfulGattWrite) {
      log(`❌ [BLE] GATT write failed after ${attemptedGattWrites} attempts (failures: ${failedGattWrites}): ${lastWriteError ? lastWriteError.message : "Write rejected"}`);
      return {
        success: false,
        status: "COMMAND_WRITE_FAILED",
        error: lastWriteError ? lastWriteError.message : "All write attempts failed",
        attempts: attemptedGattWrites,
        failures: failedGattWrites,
      };
    }

    // Correlate pending physical command for verification when ACK arrives
    pendingPhysicalCommand = {
      commandId: cmdId,
      transactionId: cmd.transaction_id || `TX-${cmdId}`,
      deviceName: targetBluetoothName,
      sentAt: Date.now(),
      serviceUuid: svcUuid,
      characteristicUuid: charUuid,
      state: "COMMAND_SENT_TO_GATT",
    };
    pendingPhysicalCommandsMap.set(cmdId, pendingPhysicalCommand);
    currentAckPendingCmdId = cmdId;

    log(`[COMMAND_SENT_TO_GATT] GATT WRITE SUCCESS for command ${cmdId} (attempt: ${attemptedGattWrites}). Physical ACK pending.`);
    return {
      success: true,
      status: "COMMAND_SENT_TO_GATT",
      command_id: cmdId,
      attempts: attemptedGattWrites,
    };
  }

  async function handleIncomingCommand(cmd) {
    if (!cmd || !cmd.command_id) {
      log("[ANDROID_NOTIFICATION_REJECTED] Reason: MISSING_COMMAND_ID or INVALID_FORMAT");
      return;
    }
    const cmdId = cmd.command_id;
    activeCommandData = cmd;

    // 1. Check for already dismissed or terminal/completed mission state
    const isDismissed = dismissedMissionIds.has(cmdId);
    const isTerminal = cmd.status === "WATCH_ACKNOWLEDGED" || cmd.status === "ACKNOWLEDGED" || cmd.status === "CANCELLED" || cmd.status === "EXPIRED" || cmd.status === "USER_ACCEPTED";

    if (isDismissed || isTerminal) {
      // Update status cards silently without reopening popup or repeating alerts
      updateStatusCards(cmd);
      return;
    }

    // 2. Verify member and device mapping
    const assignedMember = cmd.member_id || memberId;
    if (memberId && cmd.member_id && cmd.member_id !== memberId) {
      log(`⚠️ [ANDROID_NOTIFICATION_REJECTED] Member mismatch: Command is for ${cmd.member_id}, but bridge is set to ${memberId}.`);
      commandDeliveryState = "DEVICE_MISMATCH";
      updateStatusCards(cmd);
      return;
    }

    // 3. Check if this is a NEW assignment for which popup has NOT been shown yet
    const isNewAssignment = !shownMissionIds.has(cmdId);
    if (isNewAssignment) {
      markMissionShown(cmdId);
      log(`[ANDROID_NOTIFICATION_RECEIVED] Incoming emergency notification for command: ${cmdId}`);
      log(`[ANDROID_NOTIFICATION_VALIDATED] Command ID validated: ${cmdId} | Target: ${cmd.victim_id || cmd.target_id || "Survivor"}`);
      log(`[WATCH] Alert received from backend: ${cmdId}`);
      log(`[WATCH] Target: ${targetBluetoothName} (${targetMac})`);
      log(`[COMMAND] GO created: ${cmdId}`);
      log(`[BRIDGE] GO received: ${cmdId} | Target: ${cmd.victim_id || cmd.target_id || "Survivor"}`);

      // Start 4-step pipeline: BLE -> GATT -> Watch -> ACK
      updatePipelineUI();
      showEmergencyPopup(cmd);
      playEmergencyChime();
    }

    const isBluetoothConnected = watchConnected && activeGattServer && activeGattServer.connected;

    // If watch is not connected via BLE, withhold physical dispatch and report truthfully
    if (!isBluetoothConnected) {
      commandDeliveryState = "WATCH_DISCONNECTED";
      log(`[COMMAND_MIRRORING_BLOCKED] Wave Call Plus (${targetBluetoothName}) is DISCONNECTED. Delivery blocked truthfully.`);
      updateStatusCards(cmd);
      updatePipelineUI();
      await reportCommandStatus(cmdId, "SENT_TO_BRIDGE", null);
      await loadNotificationCenter();
      return;
    }

    // Idempotency: Do not trigger duplicate native notification for the same command
    if (postedCommandIds.has(cmdId)) {
      await loadNotificationCenter();
      return;
    }

    postedCommandIds.add(cmdId);
    sessionStorage.setItem("ridgewatch_posted_cmd_ids", JSON.stringify(Array.from(postedCommandIds)));

    log(`[COMMAND_MIRRORING_STARTED] Companion beginning Wave Call Plus delivery for command ${cmdId}`);

    const title = cmd.notification_payload?.title || "🚨 RIDGEWATCH — GO";
    const distLabel = cmd.distance_label || (cmd.distance_m ? `${Math.round(cmd.distance_m)} m` : "Distance unavailable");
    const body = cmd.notification_payload?.body || `Survivor detected\nDistance: ${distLabel}\nAlert: ${cmdId.substring(0, 8)}`;

    // Deliver via Android System Notification (Mirrors to Wave Call Plus screen via companion app)
    const notifRes = await dispatchNativeAndroidNotification(title, body, cmdId, cmdId);
    const postedOnPhone = notifRes.success;

    if (postedOnPhone) {
      log(`📲 [PHONE_NOTIFICATION_POSTED] "${title}" posted to Android System Notification Tray via ${notifRes.method}.`);
      log(`⌚ [WATCH_MIRROR_TRIGGERED] Notification delivered to Android Notification Shade for Wave Call Plus companion mirroring.`);
      commandDeliveryState = "PHONE_NOTIFICATION_POSTED";
    } else {
      log(`⚠️ [PHONE_NOTIFICATION_NOT_POSTED] Reason: ${notifRes.reason}. Emergency alert could not be posted to phone notification tray. Please ensure notification permissions are Allowed.`);
      commandDeliveryState = "DELIVERY_ATTEMPTED";
    }

    // Direct GATT Command Execution:
    // Only attempt direct GATT write if verifiedCommandCharacteristic exists.
    // If not verified, route honestly through Android Companion Notification Mirroring.
    if (verifiedCommandCharacteristic) {
      log(`[GATT_WRITE_ATTEMPTED] Attempting direct GATT write for command ${cmdId}...`);
      const gattRes = await sendRescueCommandThroughVerifiedGattChannel(cmd);
      if (gattRes.success && gattRes.status === "GATT_WRITE_CONFIRMED") {
        log(`[GATT_WRITE_COMPLETED] GATT write confirmed for command ${cmdId}`);
        commandDeliveryState = "GATT_WRITE_CONFIRMED";
      } else {
        log(`[GATT_WRITE_FAILED] GATT write failed for command ${cmdId}`);
        commandDeliveryState = "COMMAND_WRITE_FAILED";
      }
    } else {
      log(`ℹ️ [BLE] Direct raw GATT rescue command channel is unverified on Wave Call Plus (proprietary RTOS).`);
      log(`ℹ️ [BLE] Rescue command delivery active via Android Companion Notification Mirroring.`);
    }

    // Report honest delivery status to backend:
    const reportedStatus = (commandDeliveryState === "GATT_WRITE_CONFIRMED")
      ? "COMMAND_SENT"
      : (commandDeliveryState === "COMMAND_WRITE_FAILED"
          ? "COMMAND_WRITE_FAILED"
          : (postedOnPhone ? "PHONE_NOTIFICATION_POSTED" : "SENT_TO_BRIDGE"));

    await reportCommandStatus(cmdId, reportedStatus, null);
    updateStatusCards(cmd);
    updatePipelineUI();
    await loadNotificationCenter();
  }

  async function sendHeartbeat() {
    const lat = parseFloat(latInput ? latInput.value : "32.3739") || 32.3739;
    const lon = parseFloat(lonInput ? lonInput.value : "77.2491") || 77.2491;
    const activeMemId = memberId || (memberSelect ? memberSelect.value : "ALPHA-M001") || "ALPHA-M001";

    try {
      const payload = {
        session_id: sessionId,
        team_id: teamId || "ALPHA",
        member_id: activeMemId,
        watch_device_id: targetDeviceId,
        watch_mac: targetMac,
        watch_model: "Wave Call Plus",
        watch_connected: watchConnected,
        bluetooth_state: bluetoothEnabled ? "ENABLED" : "DISABLED",
        gps_available: gpsAvailable,
        latitude: lat,
        longitude: lon,
        location_source: "PHONE_GPS",
        status: "ONLINE",
        notes: `Wave Call Plus bridge active. Device: ${targetBluetoothName} (Member: ${activeMemId})`,
      };

      console.log(`[GPS] Location: ${lat.toFixed(4)}, ${lon.toFixed(4)} | Source: PHONE_GPS | Member: ${activeMemId}`);

      const res = await fetch(`${apiBase}/api/wearable/bridge/heartbeat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        console.log(`[HEARTBEAT] POST /api/wearable/bridge/heartbeat -> 200 (Active Command: ${data.active_command ? data.active_command.command_id : "None"})`);
        if (statBackendConn) {
          statBackendConn.textContent = "● CONNECTED";
          statBackendConn.className = "status-card-val val-ok";
        }
        if (bridgeStatus) {
          bridgeStatus.textContent = "ONLINE";
          bridgeStatus.className = "bridge-status-badge status-online";
        }
        updateStatusCards(data.active_command);

        if (data.active_command) {
          await handleIncomingCommand(data.active_command);
        }
      } else {
        console.warn(`[HEARTBEAT] POST /api/wearable/bridge/heartbeat -> ${res.status}`);
        if (statBackendConn) {
          statBackendConn.textContent = "○ DISCONNECTED";
          statBackendConn.className = "status-card-val val-bad";
        }
      }
    } catch (err) {
      console.warn(`[HEARTBEAT] Heartbeat error: ${err.message}`);
      log(`⚠️ Heartbeat error: ${err.message}`);
      if (statBackendConn) {
        statBackendConn.textContent = "○ OFFLINE";
        statBackendConn.className = "status-card-val val-bad";
      }
      if (bridgeStatus) {
        bridgeStatus.textContent = "OFFLINE";
        bridgeStatus.className = "bridge-status-badge status-offline";
      }
    }
  }

  if (btnConnectBle) btnConnectBle.addEventListener("click", openBleModal);
  if (btnBleModalClose) btnBleModalClose.addEventListener("click", closeBleModal);
  if (btnBleModalScan) btnBleModalScan.addEventListener("click", connectWebBluetooth);
  if (btnBleModalDirectConnect) btnBleModalDirectConnect.addEventListener("click", directHardwareConnect);
  if (btnBleModalDisconnect) btnBleModalDisconnect.addEventListener("click", disconnectWatch);
  if (bleModalOverlay) {
    bleModalOverlay.addEventListener("click", (e) => {
      if (e.target === bleModalOverlay) closeBleModal();
    });
  }
  if (btnEnableNotif) btnEnableNotif.addEventListener("click", requestNotificationPermission);
  if (btnSyncGps) btnSyncGps.addEventListener("click", sendHeartbeat);

  if (btnTestWatchAlert) {
    btnTestWatchAlert.addEventListener("click", async () => {
      log("🚨 Triggering Live Hardware Test Alert via backend...");
      const testCmdId = `CMD-TEST-${Math.random().toString(36).substring(2, 7).toUpperCase()}`;
      const testCmd = {
        type: "RESCUE_ALERT",
        command_id: testCmdId,
        team_id: teamId || "ALPHA",
        member_id: memberId || "ALPHA-M001",
        victim_id: "SURVIVOR-TEST-01",
        target_id: "SURVIVOR-TEST-01",
        location: "Sector Alpha-1",
        priority: "HIGH",
        command_type: "GO",
        command_text: "Proceed to rescue SURVIVOR-TEST-01 (LIVE HARDWARE TEST)",
        notification_payload: {
          title: "🚨 RIDGEWATCH — GO (TEST ALERT)",
          body: "Live Hardware Test: Proceed to rescue SURVIVOR-TEST-01.",
          priority: "HIGH",
        },
      };

      try {
        const res = await fetch(`${apiBase}/api/wearable/commands/test_alert`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(testCmd),
        });
        if (!res.ok) {
          let errDetail = `HTTP ${res.status}`;
          try {
            const errJson = await res.json();
            if (errJson && errJson.detail) errDetail = errJson.detail;
          } catch (_) {}
          log(`❌ [BACKEND] Test alert registration failed: ${errDetail}`);
          return;
        }

        const resData = await res.json();
        const confirmedCmdId = resData.command_id || testCmdId;
        log(`[BACKEND] Test alert successfully registered with ID: ${confirmedCmdId}`);

        const payloadToHandle = resData.alert || testCmd;
        await handleIncomingCommand(payloadToHandle);
      } catch (err) {
        log(`❌ [BACKEND] Test alert registration network failure: ${err.message}`);
      }
    });
  }

  if (btnManualWatchAck) {
    btnManualWatchAck.addEventListener("click", async () => {
      const pendingId = currentAckPendingCmdId || (activeCommandData ? activeCommandData.command_id : null);
      if (pendingId) {
        log(`[OPERATOR] Manual rescuer confirmation recorded for ${pendingId} (USER_ACCEPTED). Physical watch ACK remains unconfirmed.`);
        await acceptEmergencyAlert(pendingId);
      } else {
        log("ℹ️ No active command pending confirmation.");
      }
    });
  }

  if (btnPopupAccept) {
    btnPopupAccept.addEventListener("click", async () => {
      const activeId = activeCommandData ? activeCommandData.command_id : null;
      await acceptEmergencyAlert(activeId);
    });
  }

  if (btnPopupDismiss) {
    btnPopupDismiss.addEventListener("click", () => {
      const activeId = activeCommandData ? activeCommandData.command_id : null;
      if (activeId) {
        markMissionDismissed(activeId);
        log(`ℹ️ [OPERATOR] Dismissed Emergency Alert for mission ${activeId}. Alert will not reappear.`);
      }
      dismissEmergencyPopup(activeId);
    });
  }

  // Auto-acquire Phone Geolocation if available
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        gpsAvailable = true;
        if (latInput) latInput.value = pos.coords.latitude.toFixed(4);
        if (lonInput) lonInput.value = pos.coords.longitude.toFixed(4);
        log(`📍 Live GPS acquired from Phone GNSS (${pos.coords.latitude.toFixed(4)}N, ${pos.coords.longitude.toFixed(4)}E).`);
        updateStatusCards(activeCommandData);
      },
      () => {
        gpsAvailable = false;
        log("📍 Using default base station GPS coordinates (Permission not granted).");
        updateStatusCards(activeCommandData);
      }
    );
  }

  // Check notification permission on load
  if ("Notification" in window && Notification.permission === "default") {
    requestNotificationPermission();
  }

  // Initialize lifecycle sequentially
  async function init() {
    await checkBackendConnection();
    await loadBridgeTeamsAndMembers();
    updateStatusCards(null);
    await loadNotificationCenter();
    await sendHeartbeat();
    setInterval(sendHeartbeat, 5000);
  }
  init();
})();
