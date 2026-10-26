/* ==========================================================================
   RIDGEWATCH 3D / 4D Smartwatch Rescue Concept Visualization & Real-Time Engine
   Modular Presentation Engine for Wave Call Plus Spatial Rescue Flow
   Unified Backend-Driven State Machine with Interactive Two-View Toggle
   
   Architecture:
   1. watchState: Unified single frontend state object for live backend data
   2. WatchStateAdapter: Realtime poll & sync from backend APIs
   3. RescueSimulationEngine: State progression & spatial position interpolation
   4. Concept3DRenderer: Pure presentation layer for 3D watch, map, and timeline
   ========================================================================== */

(() => {
  "use strict";

  const apiBase = (typeof RidgeWatchConfig !== "undefined") ? RidgeWatchConfig.getApiBase() : "http://localhost:8000";

  // ------------------------------------------------------------------ //
  // 1. Unified Frontend Watch State Model
  // ------------------------------------------------------------------ //
  const watchState = {
    mode: "LIVE_BACKEND", // "LIVE_BACKEND" | "SIMULATION"
    operation: {
      id: null,
      scenario: null,
      scenarioId: null,
      priority: null,
    },
    assignment: {
      teamId: null,
      teamName: null,
      memberId: null,
      memberName: null,
      assignedAt: null,
    },
    target: {
      victimId: null,
      victimLabel: null,
      coordinates: null, // { latitude, longitude, altitude_m }
    },
    rescuer: {
      callsign: null,
      status: "hold", // "hold" | "en_route" | "arrived" | "rescued" | "completed"
      coordinates: null, // { latitude, longitude, altitude_m }
    },
    navigation: {
      distanceM: null,
      distanceLabel: null,
      bearingDeg: null,
      compassLabel: null,
      etaSeconds: null,
      etaLabel: null,
      isGpsAvailable: false,
    },
    command: {
      commandId: null,
      commandType: null,
      commandStatus: null,
      bridgeStatus: "ONLINE",
      watchStatus: "STANDBY",
      phoneNotificationPosted: false,
    },
    timeline: [],
    updatedAt: null,
  };

  // ------------------------------------------------------------------ //
  // 2. Simulation Operational Stages (Simulation Mode Only)
  // ------------------------------------------------------------------ //
  const SIM_STAGES = [
    {
      id: "STANDBY",
      timeLabel: "T+00",
      pillClass: "state-standby",
      pillText: "STANDBY",
      watchHeader: "AWAITING ASSIGNMENT",
      watchBigText: "STANDBY",
      watchBigClass: "",
      watchSub: "Listening on rescue channel",
      watchDist: "-- m",
      bearing: "STANDBY",
      activeNodes: ["nodeCommander"],
      signalPulse: false,
      mapProgress: 0.0,
      distanceMeters: 250,
      etaSeconds: 45,
      timelineIndex: 0,
    },
    {
      id: "GO",
      timeLabel: "T+02",
      pillClass: "state-go",
      pillText: "GO ALERT",
      watchHeader: "RESCUE ASSIGNMENT",
      watchBigText: "GO",
      watchBigClass: "text-go",
      watchSub: "Target: Survivor in Sector 7",
      watchDist: "250 m NE",
      bearing: "042° NE",
      activeNodes: ["nodeCommander", "nodeCore", "nodeBridge", "nodeWatch"],
      signalPulse: true,
      mapProgress: 0.05,
      distanceMeters: 250,
      etaSeconds: 45,
      timelineIndex: 1,
    },
    {
      id: "ACCEPTED",
      timeLabel: "T+05",
      pillClass: "state-accepted",
      pillText: "TEAM ACCEPTED",
      watchHeader: "MISSION CONFIRMED",
      watchBigText: "ACCEPTED",
      watchBigClass: "text-accepted",
      watchSub: "Deployment acknowledged",
      watchDist: "230 m NE",
      bearing: "042° NE",
      activeNodes: ["nodeWatch", "nodeBridge"],
      signalPulse: false,
      mapProgress: 0.18,
      distanceMeters: 230,
      etaSeconds: 40,
      timelineIndex: 2,
    },
    {
      id: "EN_ROUTE",
      timeLabel: "T+15",
      pillClass: "state-enroute",
      pillText: "EN ROUTE",
      watchHeader: "ACTIVE NAVIGATION",
      watchBigText: "EN ROUTE",
      watchBigClass: "text-enroute",
      watchSub: "Approaching Target Zone",
      watchDist: "95 m NE",
      bearing: "038° NE",
      activeNodes: ["nodeWatch"],
      signalPulse: false,
      mapProgress: 0.65,
      distanceMeters: 95,
      etaSeconds: 15,
      timelineIndex: 3,
    },
    {
      id: "ARRIVED",
      timeLabel: "T+45",
      pillClass: "state-arrived",
      pillText: "ARRIVED",
      watchHeader: "TARGET REACHED",
      watchBigText: "ARRIVED",
      watchBigClass: "text-arrived",
      watchSub: "Survivor in Proximity",
      watchDist: "0 m (ON SITE)",
      bearing: "ON SITE",
      activeNodes: ["nodeWatch"],
      signalPulse: false,
      mapProgress: 1.0,
      distanceMeters: 0,
      etaSeconds: 0,
      timelineIndex: 4,
    },
    {
      id: "RESCUED",
      timeLabel: "T+60",
      pillClass: "state-rescued",
      pillText: "RESCUE COMPLETE",
      watchHeader: "OPERATION COMPLETE",
      watchBigText: "RESCUED",
      watchBigClass: "text-rescued",
      watchSub: "Survivor Secured · RTB",
      watchDist: "0 m (SECURED)",
      bearing: "BASE RTB",
      activeNodes: ["nodeCommander", "nodeCore", "nodeWatch"],
      signalPulse: false,
      mapProgress: 1.0,
      distanceMeters: 0,
      etaSeconds: 0,
      timelineIndex: 5,
    }
  ];

  // Route Coordinates on 280x250 Vector Grid
  const ROUTE_START_X = 50;
  const ROUTE_START_Y = 200;
  const ROUTE_END_X = 230;
  const ROUTE_END_Y = 55;

  // ------------------------------------------------------------------ //
  // 3. DOM Elements Cache
  // ------------------------------------------------------------------ //
  const dom = {
    // View Switcher (3-View Toggle)
    btnViewConsole: document.getElementById("btnViewConsole"),
    btnViewRescueFlow: document.getElementById("btnViewRescueFlow"),
    btnViewLiveRescueFlow: document.getElementById("btnViewLiveRescueFlow"),
    viewWatchConsole: document.getElementById("viewWatchConsole"),
    viewRescueFlow: document.getElementById("viewRescueFlow"),
    viewLiveRescueFlow: document.getElementById("viewLiveRescueFlow"),

    // Selectors & Controls
    selScenario: document.getElementById("conceptScenarioSelect"),
    selMember: document.getElementById("conceptMemberSelect"),
    btnPlay: document.getElementById("btnConceptPlay"),
    btnPause: document.getElementById("btnConceptPause"),
    btnStep: document.getElementById("btnConceptStep"),
    btnReset: document.getElementById("btnConceptReset"),
    btnSendGo: document.getElementById("btnConceptSendGo"),
    statePill: document.getElementById("conceptStatePill"),

    // Mode Badges
    watchStageModeBadge: document.getElementById("watchStageModeBadge"),
    conceptMapLocationBadge: document.getElementById("conceptMapLocationBadge"),

    // Commander Dispatch Card
    dispOpId: document.getElementById("dispConceptOpId"),
    dispScenario: document.getElementById("dispConceptScenario"),
    dispMember: document.getElementById("dispConceptMember"),
    dispPriority: document.getElementById("dispConceptPriority"),
    dispTarget: document.getElementById("dispConceptTarget"),

    // Signal Pipeline Nodes & Connectors
    nodeCommander: document.getElementById("pipeCommander"),
    nodeCore: document.getElementById("pipeCore"),
    nodeBridge: document.getElementById("pipeBridge"),
    nodeWatch: document.getElementById("pipeWatch"),
    conn1: document.getElementById("pipeConn1"),
    conn2: document.getElementById("pipeConn2"),
    conn3: document.getElementById("pipeConn3"),
    pipeCommanderStatus: document.getElementById("pipeCommanderStatus"),
    pipeCoreStatus: document.getElementById("pipeCoreStatus"),
    pipeBridgeStatus: document.getElementById("pipeBridgeStatus"),
    pipeWatchStatus: document.getElementById("pipeWatchStatus"),

    // 3D Watch Screen
    watch3dWrapper: document.getElementById("watch3dWrapper"),
    watchHapticRipple: document.getElementById("watchHapticRipple"),
    screenTime: document.getElementById("conceptScreenTime"),
    screenStateHeader: document.getElementById("conceptScreenStateHeader"),
    screenBigText: document.getElementById("conceptScreenBigText"),
    screenSubDetail: document.getElementById("conceptScreenSubDetail"),
    screenDistBadge: document.getElementById("conceptScreenDistBadge"),
    screenFooterTeam: document.getElementById("conceptScreenFooterTeam"),

    // Tactical Map & Telemetry
    mapTeamMarker: document.getElementById("conceptMapTeamMarker"),
    mapTeamPulse: document.getElementById("conceptMapTeamPulse"),
    mapRouteLine: document.getElementById("conceptMapRouteLine"),
    mapActivePath: document.getElementById("conceptMapActivePath"),
    mapTargetMarker: document.getElementById("conceptMapTargetMarker"),
    mapTargetLabel: document.getElementById("conceptMapTargetLabel"),
    mapTeamLabel: document.getElementById("conceptMapTeamLabel"),
    telemDist: document.getElementById("conceptTelemDist"),
    telemEta: document.getElementById("conceptTelemEta"),
    telemBearing: document.getElementById("conceptTelemBearing"),
    telemTarget: document.getElementById("conceptTelemTarget"),

    // 4D Timeline
    timelineTitle: document.getElementById("conceptTimelineTitle"),
    timelineDisclaimer: document.getElementById("conceptTimelineDisclaimer"),
    trackProgress: document.getElementById("conceptTrackProgress"),
    timelineNodes: [
      document.getElementById("conceptTl0"),
      document.getElementById("conceptTl1"),
      document.getElementById("conceptTl2"),
      document.getElementById("conceptTl3"),
      document.getElementById("conceptTl4"),
      document.getElementById("conceptTl5"),
    ],
    timelineTimes: [
      document.getElementById("conceptTlTime0"),
      document.getElementById("conceptTlTime1"),
      document.getElementById("conceptTlTime2"),
      document.getElementById("conceptTlTime3"),
      document.getElementById("conceptTlTime4"),
      document.getElementById("conceptTlTime5"),
    ],
    timelineLabels: [
      document.getElementById("conceptTlLabel0"),
      document.getElementById("conceptTlLabel1"),
      document.getElementById("conceptTlLabel2"),
      document.getElementById("conceptTlLabel3"),
      document.getElementById("conceptTlLabel4"),
      document.getElementById("conceptTlLabel5"),
    ],
  };

  // ------------------------------------------------------------------ //
  // 4. Simulation Engine (for Interactive Simulation Playback)
  // ------------------------------------------------------------------ //
  class RescueSimulationEngine {
    constructor() {
      this.currentStageIndex = 0;
      this.isPlaying = false;
      this.playTimer = null;
    }

    setStage(index) {
      watchState.mode = "SIMULATION";
      this.currentStageIndex = Math.max(0, Math.min(index, SIM_STAGES.length - 1));
      const stage = SIM_STAGES[this.currentStageIndex];
      Concept3DRenderer.renderSimulationStage(stage);
    }

    play() {
      watchState.mode = "SIMULATION";
      this.isPlaying = true;
      if (dom.btnPlay) dom.btnPlay.style.opacity = "0.6";
      if (dom.btnPause) dom.btnPause.style.opacity = "1";

      if (this.currentStageIndex >= SIM_STAGES.length - 1) {
        this.currentStageIndex = 0;
        this.setStage(0);
      }

      clearInterval(this.playTimer);
      this.playTimer = setInterval(() => {
        if (this.currentStageIndex < SIM_STAGES.length - 1) {
          this.setStage(this.currentStageIndex + 1);
        } else {
          this.pause();
        }
      }, 2800);
    }

    pause() {
      this.isPlaying = false;
      clearInterval(this.playTimer);
      if (dom.btnPlay) dom.btnPlay.style.opacity = "1";
      if (dom.btnPause) dom.btnPause.style.opacity = "0.6";
    }

    step() {
      this.pause();
      watchState.mode = "SIMULATION";
      const nextIdx = (this.currentStageIndex + 1) % SIM_STAGES.length;
      this.setStage(nextIdx);
    }

    reset() {
      this.pause();
      watchState.mode = "LIVE_BACKEND";
      WatchStateAdapter.syncWithBackend();
    }
  }

  const engine = new RescueSimulationEngine();

  // ------------------------------------------------------------------ //
  // 5. Concept 3D Renderer (Presentation Layer)
  // ------------------------------------------------------------------ //
  class Concept3DRenderer {
    /**
     * Render the Live Backend State (Primary Mode)
     */
    static renderLiveBackend() {
      const isStandby = !watchState.target.victimId || watchState.rescuer.status === "hold";
      const status = (watchState.rescuer.status || "hold").toLowerCase();

      // Mode Badges
      if (dom.watchStageModeBadge) {
        dom.watchStageModeBadge.textContent = "LIVE BACKEND";
        dom.watchStageModeBadge.style.color = "#1d4ed8";
        dom.watchStageModeBadge.style.background = "#eff6ff";
        dom.watchStageModeBadge.style.borderColor = "#bfdbfe";
      }
      if (dom.conceptMapLocationBadge) {
        dom.conceptMapLocationBadge.textContent = watchState.navigation.isGpsAvailable ? "LIVE GNSS LOCATION" : "SIMULATED LOCATION";
      }

      // 1. Commander Dispatch Card
      if (dom.dispOpId) dom.dispOpId.textContent = watchState.operation.id || "—";
      if (dom.dispScenario) dom.dispScenario.textContent = watchState.operation.scenario || "—";
      if (dom.dispPriority) dom.dispPriority.textContent = isStandby ? "—" : (watchState.operation.priority || "HIGH (P1)");
      if (dom.dispTarget) {
        dom.dispTarget.textContent = isStandby ? "—" : (watchState.target.victimLabel || watchState.target.victimId || "—");
      }
      if (dom.dispMember) {
        dom.dispMember.textContent = watchState.assignment.memberName 
          ? `${watchState.assignment.memberName} (${watchState.assignment.memberId})`
          : (watchState.assignment.memberId || "—");
      }

      // 2. Status Pill
      if (dom.statePill) {
        if (isStandby) {
          dom.statePill.className = "sim-state-pill state-standby";
          dom.statePill.textContent = "T+00 · STANDBY";
        } else if (status === "en_route") {
          dom.statePill.className = "sim-state-pill state-enroute";
          dom.statePill.textContent = "T+15 · EN ROUTE";
        } else if (status === "arrived") {
          dom.statePill.className = "sim-state-pill state-arrived";
          dom.statePill.textContent = "T+45 · ARRIVED";
        } else if (status === "rescued" || status === "completed") {
          dom.statePill.className = "sim-state-pill state-rescued";
          dom.statePill.textContent = "T+60 · RESCUE COMPLETE";
        } else {
          dom.statePill.className = "sim-state-pill state-go";
          dom.statePill.textContent = "T+02 · GO ALERT";
        }
      }

      // 3. 3D Watch OLED Display
      if (dom.screenFooterTeam) {
        dom.screenFooterTeam.textContent = watchState.assignment.teamName || "—";
      }

      if (isStandby) {
        if (dom.screenStateHeader) dom.screenStateHeader.textContent = "AWAITING ASSIGNMENT";
        if (dom.screenBigText) {
          dom.screenBigText.textContent = "STANDBY";
          dom.screenBigText.className = "screen-big-text";
        }
        if (dom.screenSubDetail) dom.screenSubDetail.textContent = "Listening on rescue channel";
        if (dom.screenDistBadge) dom.screenDistBadge.style.display = "none";
        if (dom.watchHapticRipple) dom.watchHapticRipple.classList.remove("pulsing");
      } else if (status === "rescued" || status === "completed") {
        if (dom.screenStateHeader) dom.screenStateHeader.textContent = "OPERATION COMPLETE";
        if (dom.screenBigText) {
          dom.screenBigText.textContent = "RESCUED";
          dom.screenBigText.className = "screen-big-text text-rescued";
        }
        if (dom.screenSubDetail) dom.screenSubDetail.textContent = `Survivor ${watchState.target.victimLabel || watchState.target.victimId} Secured · RTB`;
        if (dom.screenDistBadge) {
          dom.screenDistBadge.textContent = "0 m (SECURED)";
          dom.screenDistBadge.style.display = "inline-block";
        }
        if (dom.watchHapticRipple) dom.watchHapticRipple.classList.remove("pulsing");
      } else if (status === "arrived" || (watchState.navigation.distanceM !== null && watchState.navigation.distanceM <= 15.0)) {
        if (dom.screenStateHeader) dom.screenStateHeader.textContent = "TARGET REACHED";
        if (dom.screenBigText) {
          dom.screenBigText.textContent = "ARRIVED";
          dom.screenBigText.className = "screen-big-text text-arrived";
        }
        if (dom.screenSubDetail) dom.screenSubDetail.textContent = "Survivor in Proximity";
        if (dom.screenDistBadge) {
          dom.screenDistBadge.textContent = "0 m (ON SITE)";
          dom.screenDistBadge.style.display = "inline-block";
        }
        if (dom.watchHapticRipple) dom.watchHapticRipple.classList.remove("pulsing");
      } else if (status === "en_route") {
        if (dom.screenStateHeader) dom.screenStateHeader.textContent = "ACTIVE NAVIGATION";
        if (dom.screenBigText) {
          dom.screenBigText.textContent = "EN ROUTE";
          dom.screenBigText.className = "screen-big-text text-enroute";
        }
        if (dom.screenSubDetail) dom.screenSubDetail.textContent = `Approaching ${watchState.target.victimLabel || watchState.target.victimId || "Target"}`;
        if (dom.screenDistBadge) {
          dom.screenDistBadge.textContent = `${watchState.navigation.distanceLabel || "—"} ${watchState.navigation.compassLabel || ""}`.trim();
          dom.screenDistBadge.style.display = "inline-block";
        }
        if (dom.watchHapticRipple) dom.watchHapticRipple.classList.remove("pulsing");
      } else {
        // ASSIGNED / GO
        if (dom.screenStateHeader) dom.screenStateHeader.textContent = "RESCUE ASSIGNMENT";
        if (dom.screenBigText) {
          dom.screenBigText.textContent = "GO";
          dom.screenBigText.className = "screen-big-text text-go";
        }
        if (dom.screenSubDetail) dom.screenSubDetail.textContent = `Target: ${watchState.target.victimLabel || watchState.target.victimId || "Survivor"} in Sector 7`;
        if (dom.screenDistBadge) {
          dom.screenDistBadge.textContent = `${watchState.navigation.distanceLabel || "—"} ${watchState.navigation.compassLabel || ""}`.trim();
          dom.screenDistBadge.style.display = "inline-block";
        }
        if (dom.watchHapticRipple) dom.watchHapticRipple.classList.add("pulsing");
      }

      // 4. Signal Pipeline Nodes
      const nodeMap = {
        nodeCommander: dom.nodeCommander,
        nodeCore: dom.nodeCore,
        nodeBridge: dom.nodeBridge,
        nodeWatch: dom.nodeWatch,
      };
      Object.values(nodeMap).forEach((n) => {
        if (n) n.classList.remove("active", "pulsing");
      });
      if (dom.conn1) dom.conn1.classList.remove("pulse-active");
      if (dom.conn2) dom.conn2.classList.remove("pulse-active");
      if (dom.conn3) dom.conn3.classList.remove("pulse-active");

      if (isStandby) {
        if (dom.nodeCommander) dom.nodeCommander.classList.add("active");
        if (dom.pipeCommanderStatus) dom.pipeCommanderStatus.textContent = "Awaiting dispatch";
        if (dom.pipeCoreStatus) dom.pipeCoreStatus.textContent = "Standby";
        if (dom.pipeBridgeStatus) dom.pipeBridgeStatus.textContent = "Listening";
        if (dom.pipeWatchStatus) dom.pipeWatchStatus.textContent = "Standby";
      } else {
        if (dom.nodeCommander) dom.nodeCommander.classList.add("active");
        if (dom.nodeCore) dom.nodeCore.classList.add("active");
        if (dom.nodeBridge) dom.nodeBridge.classList.add("active");
        if (dom.nodeWatch) dom.nodeWatch.classList.add("active");
        if (dom.conn1) dom.conn1.classList.add("pulse-active");
        if (dom.conn2) dom.conn2.classList.add("pulse-active");
        if (dom.conn3) dom.conn3.classList.add("pulse-active");
        if (dom.nodeWatch) dom.nodeWatch.classList.add("pulsing");

        if (dom.pipeCommanderStatus) dom.pipeCommanderStatus.textContent = "Dispatch active";
        if (dom.pipeCoreStatus) dom.pipeCoreStatus.textContent = `Routed to ${watchState.assignment.teamId || "Team"}`;
        if (dom.pipeBridgeStatus) dom.pipeBridgeStatus.textContent = "BLE Relay Active";
        if (dom.pipeWatchStatus) dom.pipeWatchStatus.textContent = `Receiving (${status.toUpperCase()})`;
      }

      // 5. Tactical Rescue Map Position
      let mapProgress = 0.0;
      if (!isStandby) {
        if (status === "rescued" || status === "completed" || status === "arrived") {
          mapProgress = 1.0;
        } else if (status === "en_route") {
          const dist = watchState.navigation.distanceM !== null ? watchState.navigation.distanceM : 100;
          mapProgress = Math.max(0.1, Math.min(0.95, 1 - (dist / 250)));
        } else {
          mapProgress = 0.05;
        }
      }

      const curX = ROUTE_START_X + (ROUTE_END_X - ROUTE_START_X) * mapProgress;
      const curY = ROUTE_START_Y + (ROUTE_END_Y - ROUTE_START_Y) * mapProgress;

      if (dom.mapTeamMarker) {
        dom.mapTeamMarker.setAttribute("cx", curX);
        dom.mapTeamMarker.setAttribute("cy", curY);
      }
      if (dom.mapTeamPulse) {
        dom.mapTeamPulse.setAttribute("cx", curX);
        dom.mapTeamPulse.setAttribute("cy", curY);
      }
      if (dom.mapActivePath) {
        dom.mapActivePath.setAttribute("x1", ROUTE_START_X);
        dom.mapActivePath.setAttribute("y1", ROUTE_START_Y);
        dom.mapActivePath.setAttribute("x2", curX);
        dom.mapActivePath.setAttribute("y2", curY);
      }

      // Map Telemetry Readout
      if (dom.telemDist) {
        dom.telemDist.textContent = isStandby ? "—" : (watchState.navigation.distanceLabel || "—");
      }
      if (dom.telemEta) {
        dom.telemEta.textContent = isStandby ? "—" : (watchState.navigation.etaLabel || "—");
      }
      if (dom.telemBearing) {
        dom.telemBearing.textContent = isStandby 
          ? "—" 
          : (watchState.navigation.bearingDeg !== null 
              ? `${Math.round(watchState.navigation.bearingDeg)}° ${watchState.navigation.compassLabel || ""}`.trim()
              : "—");
      }
      if (dom.telemTarget) {
        dom.telemTarget.textContent = isStandby ? "—" : (watchState.target.victimLabel || watchState.target.victimId || "—");
      }

      // 6. 4D Operation Timeline (Real Backend Events)
      Concept3DRenderer.renderTimeline(watchState.timeline, status, isStandby);
    }

    /**
     * Render the 4D Operation Timeline based on live events
     */
    static renderTimeline(events, status, isStandby) {
      if (dom.timelineDisclaimer) {
        dom.timelineDisclaimer.textContent = isStandby 
          ? "Awaiting active rescue command from Commander Console" 
          : "Live operation events synchronized with backend state";
      }

      let activeStepIndex = 0;
      if (!isStandby) {
        if (status === "rescued" || status === "completed") activeStepIndex = 5;
        else if (status === "arrived") activeStepIndex = 4;
        else if (status === "en_route") activeStepIndex = 3;
        else activeStepIndex = 1;
      }

      dom.timelineNodes.forEach((nodeEl, idx) => {
        if (!nodeEl) return;
        nodeEl.classList.remove("active", "completed");
        if (isStandby) {
          if (idx === 0) nodeEl.classList.add("active");
        } else {
          if (idx < activeStepIndex) nodeEl.classList.add("completed");
          else if (idx === activeStepIndex) nodeEl.classList.add("active");
        }
      });

      if (dom.trackProgress) {
        const pct = isStandby ? 0 : (activeStepIndex / (dom.timelineNodes.length - 1)) * 100;
        dom.trackProgress.style.width = `${pct}%`;
      }
    }

    /**
     * Render Simulation Stage (Simulation Mode)
     */
    static renderSimulationStage(stage) {
      if (dom.watchStageModeBadge) {
        dom.watchStageModeBadge.textContent = "SIMULATION MODE · ON HOLD";
        dom.watchStageModeBadge.style.color = "#b45309";
        dom.watchStageModeBadge.style.background = "#fffbeb";
        dom.watchStageModeBadge.style.borderColor = "#fde68a";
      }
      if (dom.conceptMapLocationBadge) {
        dom.conceptMapLocationBadge.textContent = "SIMULATED LOCATION";
      }

      const isStandby = stage.id === "STANDBY";

      // 1. Status Pill
      if (dom.statePill) {
        dom.statePill.className = `sim-state-pill ${stage.pillClass}`;
        dom.statePill.textContent = `${stage.timeLabel} · ${stage.pillText}`;
      }

      // 2. 3D Watch Screen
      if (dom.screenStateHeader) dom.screenStateHeader.textContent = stage.watchHeader;
      if (dom.screenBigText) {
        dom.screenBigText.textContent = stage.watchBigText;
        dom.screenBigText.className = `screen-big-text ${stage.watchBigClass}`;
      }
      if (dom.screenSubDetail) dom.screenSubDetail.textContent = stage.watchSub;
      if (dom.screenDistBadge) {
        dom.screenDistBadge.textContent = stage.watchDist;
        dom.screenDistBadge.style.display = isStandby ? "none" : "inline-block";
      }
      if (dom.screenFooterTeam) {
        dom.screenFooterTeam.textContent = watchState.assignment.teamName || "Rescue Team Alpha";
      }

      if (dom.watchHapticRipple) {
        if (stage.id === "GO") dom.watchHapticRipple.classList.add("pulsing");
        else dom.watchHapticRipple.classList.remove("pulsing");
      }

      // 3. Signal Pipeline
      const nodeMap = {
        nodeCommander: dom.nodeCommander,
        nodeCore: dom.nodeCore,
        nodeBridge: dom.nodeBridge,
        nodeWatch: dom.nodeWatch,
      };
      Object.values(nodeMap).forEach((n) => {
        if (n) n.classList.remove("active", "pulsing");
      });
      if (dom.conn1) dom.conn1.classList.remove("pulse-active");
      if (dom.conn2) dom.conn2.classList.remove("pulse-active");
      if (dom.conn3) dom.conn3.classList.remove("pulse-active");

      stage.activeNodes.forEach((nodeKey) => {
        if (nodeMap[nodeKey]) nodeMap[nodeKey].classList.add("active");
      });

      if (stage.signalPulse) {
        if (dom.conn1) dom.conn1.classList.add("pulse-active");
        if (dom.conn2) dom.conn2.classList.add("pulse-active");
        if (dom.conn3) dom.conn3.classList.add("pulse-active");
        if (dom.nodeWatch) dom.nodeWatch.classList.add("pulsing");
      }

      // 4. Tactical Map
      const curX = ROUTE_START_X + (ROUTE_END_X - ROUTE_START_X) * stage.mapProgress;
      const curY = ROUTE_START_Y + (ROUTE_END_Y - ROUTE_START_Y) * stage.mapProgress;

      if (dom.mapTeamMarker) {
        dom.mapTeamMarker.setAttribute("cx", curX);
        dom.mapTeamMarker.setAttribute("cy", curY);
      }
      if (dom.mapTeamPulse) {
        dom.mapTeamPulse.setAttribute("cx", curX);
        dom.mapTeamPulse.setAttribute("cy", curY);
      }
      if (dom.mapActivePath) {
        dom.mapActivePath.setAttribute("x1", ROUTE_START_X);
        dom.mapActivePath.setAttribute("y1", ROUTE_START_Y);
        dom.mapActivePath.setAttribute("x2", curX);
        dom.mapActivePath.setAttribute("y2", curY);
      }

      // Telemetry
      if (dom.telemDist) dom.telemDist.textContent = `${stage.distanceMeters} m`;
      if (dom.telemEta) dom.telemEta.textContent = `${stage.etaSeconds}s`;
      if (dom.telemBearing) dom.telemBearing.textContent = stage.bearing;
      if (dom.telemTarget) dom.telemTarget.textContent = watchState.target.victimLabel || "Target Survivor";

      // 5. Timeline
      dom.timelineNodes.forEach((nd, i) => {
        if (!nd) return;
        nd.classList.remove("active", "completed");
        if (i < stage.timelineIndex) nd.classList.add("completed");
        else if (i === stage.timelineIndex) nd.classList.add("active");
      });

      if (dom.trackProgress) {
        const pct = (stage.timelineIndex / (SIM_STAGES.length - 1)) * 100;
        dom.trackProgress.style.width = `${pct}%`;
      }
    }
  }

  // ------------------------------------------------------------------ //
  // 6. Backend State Adapter (API Sync)
  // ------------------------------------------------------------------ //
  class WatchStateAdapter {
    static async syncLiveBackendTo3DConcept() {
      return WatchStateAdapter.syncWithBackend();
    }

    static async syncWithBackend() {
      try {
        // 1. Discover system-wide latest command or filter by member
        const cmdRes = await fetch(`${apiBase}/api/wearable/commands/active`);
        const cmdData = cmdRes.ok ? await cmdRes.json() : null;

        let activeMemberId = watchState.assignment.memberId || "ALPHA-M001";
        if (cmdData && cmdData.latest_assigned_member_id) {
          activeMemberId = cmdData.latest_assigned_member_id;
          watchState.assignment.memberId = activeMemberId;
          if (dom.selMember && dom.selMember.value !== activeMemberId) {
            dom.selMember.value = activeMemberId;
          }
        }

        // 2. Fetch live watch operational status for activeMemberId
        const watchRes = await fetch(`${apiBase}/watch/${encodeURIComponent(activeMemberId)}`);
        const watchData = watchRes.ok ? await watchRes.json() : null;

        if (!watchData) return;

        // 3. Synchronize unified watchState
        watchState.assignment.memberId = activeMemberId;
        watchState.assignment.memberName = watchData.callsign || dom.selMember?.options[dom.selMember.selectedIndex]?.dataset.member || "Alpha Member 1";
        watchState.assignment.teamId = watchData.team_id || (dom.selMember?.options[dom.selMember.selectedIndex]?.dataset.teamId || "ALPHA");
        watchState.assignment.teamName = dom.selMember?.options[dom.selMember.selectedIndex]?.dataset.team || `Rescue Team ${watchState.assignment.teamId}`;

        watchState.operation.id = watchData.operation_id || (cmdData?.command?.command_id) || "—";
        watchState.operation.scenario = watchData.scenario || "Active Operation";
        watchState.operation.scenarioId = watchData.scenario_id || "SCENARIO-ACTIVE";
        watchState.operation.priority = watchData.priority || "HIGH (P1)";

        watchState.target.victimId = watchData.assigned_victim_id || null;
        watchState.target.victimLabel = watchData.victim_label || (watchData.assigned_victim_id ? `Survivor ${watchData.assigned_victim_id}` : null);
        watchState.target.coordinates = watchData.victim_location || null;

        watchState.rescuer.callsign = watchData.callsign || watchState.assignment.memberName;
        watchState.rescuer.status = watchData.status || "hold";
        watchState.rescuer.coordinates = watchData.member_location || null;

        watchState.navigation.distanceM = watchData.distance_m != null ? watchData.distance_m : null;
        watchState.navigation.distanceLabel = watchData.distance_label || (watchData.distance_m != null ? `${watchData.distance_m} m` : null);
        watchState.navigation.bearingDeg = watchData.bearing_deg != null ? watchData.bearing_deg : null;
        watchState.navigation.compassLabel = watchData.compass_label || null;
        watchState.navigation.etaSeconds = watchData.eta_seconds != null ? watchData.eta_seconds : null;
        watchState.navigation.etaLabel = watchData.eta_seconds != null ? `${watchData.eta_seconds}s` : null;

        watchState.command.commandId = watchData.command?.command_id || cmdData?.command?.command_id || null;
        watchState.command.commandStatus = watchData.command?.status || (watchData.status !== "hold" ? "ASSIGNED" : null);
        watchState.timeline = watchData.timeline || [];
        watchState.updatedAt = new Date().toISOString();

        // If in Live Backend Mode, render live state
        if (watchState.mode === "LIVE_BACKEND" && !engine.isPlaying) {
          Concept3DRenderer.renderLiveBackend();
        }
      } catch (e) {
        // Non-blocking graceful fallback
      }
    }

    static async loadScenariosAndTeams() {
      try {
        const scRes = await fetch(`${apiBase}/scenarios`);
        if (scRes.ok) {
          const scData = await scRes.json();
          const scList = scData.scenarios || [];
          if (dom.selScenario && scList.length > 0) {
            dom.selScenario.innerHTML = "";
            scList.forEach((sc, i) => {
              const opt = document.createElement("option");
              opt.value = sc.id || sc.name;
              opt.textContent = sc.name || sc.id;
              if (i === 0) opt.selected = true;
              dom.selScenario.appendChild(opt);
            });
            watchState.operation.scenario = scList[0].name || scList[0].id;
          }
        }
      } catch (e) {}

      try {
        const coRes = await fetch(`${apiBase}/commander/overview`);
        if (coRes.ok) {
          const coData = await coRes.json();
          const members = coData.team_members || [];
          if (dom.selMember && members.length > 0) {
            dom.selMember.innerHTML = "";
            members.forEach((m, idx) => {
              const opt = document.createElement("option");
              opt.value = m.member_id || m.id;
              const teamLabel = (m.team_id === "ALPHA") ? "Rescue Team Alpha" : (m.team_id === "BRAVO") ? "Rescue Team Bravo" : `Rescue Team ${m.team_id}`;
              opt.textContent = `${teamLabel} — ${m.callsign || m.name} (${m.member_id})`;
              opt.dataset.team = teamLabel;
              opt.dataset.teamId = m.team_id || "ALPHA";
              opt.dataset.member = m.callsign || m.name;
              if (idx === 0) opt.selected = true;
              dom.selMember.appendChild(opt);
            });
            watchState.assignment.memberId = dom.selMember.options[0].value;
            watchState.assignment.memberName = dom.selMember.options[0].dataset.member;
            watchState.assignment.teamName = dom.selMember.options[0].dataset.team;
            watchState.assignment.teamId = dom.selMember.options[0].dataset.teamId;
          }
        }
      } catch (e) {}

      // Initial sync with backend
      WatchStateAdapter.syncWithBackend();
    }

    static async dispatchCommanderGo() {
      try {
        const memberId = watchState.assignment.memberId || "ALPHA-M001";
        const victimId = watchState.target.victimId || "V3";
        const payload = {
          member_id: memberId,
          victim_id: victimId,
        };
        const res = await fetch(`${apiBase}/commander/assign`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.ok) {
          watchState.mode = "LIVE_BACKEND";
          WatchStateAdapter.syncWithBackend();
        }
      } catch (e) {
        // Fallback
      }
    }
  }

  // ------------------------------------------------------------------ //
  // 7. View Switcher Controller (3-View Toggle)
  // ------------------------------------------------------------------ //
  function initViewToggle() {
    function switchView(targetView) {
      const isConsole = targetView === "console";
      const isSim = targetView === "rescue_flow" || targetView === "simulation";
      const isLiveFlow = targetView === "live_rescue_flow";

      // 1. Update button states
      if (dom.btnViewConsole) {
        dom.btnViewConsole.classList.toggle("is-active", isConsole);
        dom.btnViewConsole.setAttribute("aria-selected", String(isConsole));
      }
      if (dom.btnViewRescueFlow) {
        dom.btnViewRescueFlow.classList.toggle("is-active", isSim);
        dom.btnViewRescueFlow.setAttribute("aria-selected", String(isSim));
      }
      if (dom.btnViewLiveRescueFlow) {
        dom.btnViewLiveRescueFlow.classList.toggle("is-active", isLiveFlow);
        dom.btnViewLiveRescueFlow.setAttribute("aria-selected", String(isLiveFlow));
      }

      // 2. Toggle view containers
      if (dom.viewWatchConsole) {
        dom.viewWatchConsole.classList.toggle("is-hidden", !isConsole);
      }
      if (dom.viewRescueFlow) {
        dom.viewRescueFlow.classList.toggle("is-hidden", !isSim);
      }
      if (dom.viewLiveRescueFlow) {
        dom.viewLiveRescueFlow.classList.toggle("is-hidden", !isLiveFlow);
      }

      // 3. Trigger view-specific synchronization
      if (isSim) {
        WatchStateAdapter.syncWithBackend();
      }
      if (isLiveFlow && window.LiveRescueFlow) {
        window.LiveRescueFlow.startPolling();
      } else if (window.LiveRescueFlow) {
        window.LiveRescueFlow.stopPolling();
      }
    }

    if (dom.btnViewConsole) {
      dom.btnViewConsole.addEventListener("click", () => switchView("console"));
    }
    if (dom.btnViewRescueFlow) {
      dom.btnViewRescueFlow.addEventListener("click", () => switchView("rescue_flow"));
    }
    if (dom.btnViewLiveRescueFlow) {
      dom.btnViewLiveRescueFlow.addEventListener("click", () => switchView("live_rescue_flow"));
    }
  }

  function updateClock() {
    const now = new Date();
    const hrs = String(now.getHours()).padStart(2, "0");
    const mins = String(now.getMinutes()).padStart(2, "0");
    if (dom.screenTime) {
      dom.screenTime.textContent = `${hrs}:${mins}`;
    }
  }

  // ------------------------------------------------------------------ //
  // 8. Interactive Parallax & Controls Binding
  // ------------------------------------------------------------------ //
  function setupParallax() {
    const stageEl = document.querySelector(".concept-watch-stage");
    if (stageEl && dom.watch3dWrapper) {
      stageEl.addEventListener("mousemove", (e) => {
        const rect = stageEl.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        const rotY = (x / (rect.width / 2)) * 14;
        const rotX = -(y / (rect.height / 2)) * 14;
        dom.watch3dWrapper.style.transform = `rotateX(${rotX.toFixed(1)}deg) rotateY(${rotY.toFixed(1)}deg) scale(1.02)`;
      });

      stageEl.addEventListener("mouseleave", () => {
        dom.watch3dWrapper.style.transform = "rotateX(8deg) rotateY(-6deg) scale(1)";
      });
    }
  }

  function setupControls() {
    if (dom.btnPlay) dom.btnPlay.addEventListener("click", () => engine.play());
    if (dom.btnPause) dom.btnPause.addEventListener("click", () => engine.pause());
    if (dom.btnStep) dom.btnStep.addEventListener("click", () => engine.step());
    if (dom.btnReset) dom.btnReset.addEventListener("click", () => engine.reset());
    if (dom.btnSendGo) dom.btnSendGo.addEventListener("click", () => WatchStateAdapter.dispatchCommanderGo());

    dom.timelineNodes.forEach((nodeEl, idx) => {
      if (nodeEl) {
        nodeEl.addEventListener("click", () => {
          engine.setStage(idx);
        });
      }
    });

    if (dom.selScenario) {
      dom.selScenario.addEventListener("change", (e) => {
        watchState.operation.scenario = e.target.options[e.target.selectedIndex].text;
        if (watchState.mode === "LIVE_BACKEND") Concept3DRenderer.renderLiveBackend();
      });
    }

    if (dom.selMember) {
      dom.selMember.addEventListener("change", (e) => {
        const opt = e.target.options[e.target.selectedIndex];
        watchState.assignment.teamName = opt.dataset.team || "Rescue Team Alpha";
        watchState.assignment.memberName = opt.dataset.member || opt.text;
        watchState.assignment.memberId = opt.value;
        watchState.assignment.teamId = opt.dataset.teamId || "ALPHA";
        WatchStateAdapter.syncWithBackend();
      });
    }
  }

  // ------------------------------------------------------------------ //
  // 9. Bootstrap & Live Polling
  // ------------------------------------------------------------------ //
  initViewToggle();
  setupParallax();
  setupControls();
  setInterval(updateClock, 1000);
  updateClock();

  WatchStateAdapter.loadScenariosAndTeams();

  // Background polling for backend-driven state sync (every 2s)
  setInterval(() => {
    if (dom.viewRescueFlow && !dom.viewRescueFlow.classList.contains("is-hidden") && watchState.mode === "LIVE_BACKEND") {
      WatchStateAdapter.syncWithBackend();
    }
  }, 2000);

})();
