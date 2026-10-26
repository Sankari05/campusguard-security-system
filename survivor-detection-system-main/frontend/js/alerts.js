/* ==========================================================================
   RIDGEWATCH Emergency Rescue Operations Alert Center Client
   Real-time events, triage notifications, dispatch tracking & safety warnings.
   ========================================================================== */

(() => {
  "use strict";

  const READ_STATE_KEY = "ridgewatch.alerts.readIds";
  const POLL_MS = 4000;

  function apiBase() {
    return RidgeWatchConfig.getApiBase();
  }

  // ------------------------------------------------------------------ //
  // Persistence Helpers
  // ------------------------------------------------------------------ //

  function loadReadIds() {
    try {
      return new Set(JSON.parse(localStorage.getItem(READ_STATE_KEY) || "[]"));
    } catch (e) {
      return new Set();
    }
  }

  function saveReadIds(set) {
    try {
      localStorage.setItem(READ_STATE_KEY, JSON.stringify([...set]));
    } catch (e) {}
  }

  let readIds = loadReadIds();

  // ------------------------------------------------------------------ //
  // Module State
  // ------------------------------------------------------------------ //

  let rawEvents = [];
  let currentSummary = null;
  let currentOperationStatus = null;
  let currentActivities = [];
  let currentFilter = "all";
  let searchQuery = "";
  let selectedAlertId = null;
  let isFetching = false;
  let pollInterval = null;

  // ------------------------------------------------------------------ //
  // DOM Elements
  // ------------------------------------------------------------------ //

  const el = {
    // Topbar
    liveStatusText: document.getElementById("alertsLiveStatusText"),
    refreshBtn: document.getElementById("alertsRefreshBtn"),
    bellBtn: document.getElementById("alertsBellBtn"),
    bellDot: document.getElementById("alertsBellDot"),

    // KPI Cards
    kpiUnread: document.getElementById("kpiUnreadCount"),
    kpiCritical: document.getElementById("kpiCriticalCount"),
    kpiWarning: document.getElementById("kpiWarningCount"),
    kpiInfo: document.getElementById("kpiInfoCount"),
    kpiTotal: document.getElementById("kpiTotalCount"),
    cardUnread: document.getElementById("cardUnread"),
    cardCritical: document.getElementById("cardCritical"),
    cardWarning: document.getElementById("cardWarning"),
    cardInfo: document.getElementById("cardInfo"),
    cardTotal: document.getElementById("cardTotal"),

    // Filter toolbar
    filterPills: document.querySelectorAll(".filter-pill"),
    filterCountAll: document.getElementById("filterCountAll"),
    filterCountCritical: document.getElementById("filterCountCritical"),
    filterCountWarning: document.getElementById("filterCountWarning"),
    filterCountDispatch: document.getElementById("filterCountDispatch"),
    filterCountSafety: document.getElementById("filterCountSafety"),
    filterCountArrival: document.getElementById("filterCountArrival"),
    filterCountSystem: document.getElementById("filterCountSystem"),
    searchInput: document.getElementById("alertsSearchInput"),
    searchClear: document.getElementById("alertsSearchClear"),
    markAllReadBtn: document.getElementById("alertsMarkAllReadBtn"),

    // Table
    tableBody: document.getElementById("alertsTableBody"),
    tableVisibleCount: document.getElementById("tableVisibleCount"),
    emptyMsg: document.getElementById("alertsEmptyMsg"),
    emptySubText: document.getElementById("alertsEmptySubText"),

    // Details Panel
    detailPanel: document.getElementById("alertDetailPanel"),
    detailStatusPill: document.getElementById("detailStatusPill"),
    detailPlaceholder: document.getElementById("detailPlaceholder"),
    detailBody: document.getElementById("detailBody"),
    detailSeverityBadge: document.getElementById("detailSeverityBadge"),
    detailType: document.getElementById("detailType"),
    detailMsgBox: document.getElementById("detailMsgBox"),
    detailVictimWrap: document.getElementById("metaVictimWrap"),
    detailVictimId: document.getElementById("detailVictimId"),
    detailPriorityWrap: document.getElementById("metaPriorityWrap"),
    detailPriority: document.getElementById("detailPriority"),
    detailTeamWrap: document.getElementById("metaTeamWrap"),
    detailTeam: document.getElementById("detailTeam"),
    detailLocationWrap: document.getElementById("metaLocationWrap"),
    detailLocation: document.getElementById("detailLocation"),
    detailTime: document.getElementById("detailTime"),
    detailSource: document.getElementById("detailSource"),
    detailTarget: document.getElementById("detailTarget"),
    detailActionBtn: document.getElementById("detailActionBtn"),

    // Severity Breakdown
    sevBarCountCritical: document.getElementById("sevBarCountCritical"),
    sevBarFillCritical: document.getElementById("sevBarFillCritical"),
    sevBarCountWarning: document.getElementById("sevBarCountWarning"),
    sevBarFillWarning: document.getElementById("sevBarFillWarning"),
    sevBarCountDispatch: document.getElementById("sevBarCountDispatch"),
    sevBarFillDispatch: document.getElementById("sevBarFillDispatch"),
    sevBarCountInfo: document.getElementById("sevBarCountInfo"),
    sevBarFillInfo: document.getElementById("sevBarFillInfo"),

    // Activities
    activitiesTimeline: document.getElementById("activitiesTimeline"),

    // Bottom Operation Status
    opActiveTeams: document.getElementById("opActiveTeams"),
    opActiveTeamsSub: document.getElementById("opActiveTeamsSub"),
    opActiveMissions: document.getElementById("opActiveMissions"),
    opActiveMissionsSub: document.getElementById("opActiveMissionsSub"),
    opHighVictims: document.getElementById("opHighVictims"),
    opHighVictimsSub: document.getElementById("opHighVictimsSub"),
    opSystemStatus: document.getElementById("opSystemStatus"),
    opSystemStatusSub: document.getElementById("opSystemStatusSub"),
    opCommStatus: document.getElementById("opCommStatus"),
    opCommStatusSub: document.getElementById("opCommStatusSub"),
  };

  // ------------------------------------------------------------------ //
  // Utility Functions
  // ------------------------------------------------------------------ //

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  function formatTime(isoStr) {
    if (!isoStr) return "—";
    try {
      const date = new Date(isoStr);
      if (isNaN(date.getTime())) return isoStr;
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
    } catch (e) {
      return isoStr;
    }
  }

  function getSeverityClass(sev) {
    const s = String(sev || "").toUpperCase();
    if (s === "CRITICAL") return "severity-critical";
    if (s === "WARNING") return "severity-warning";
    if (s === "DISPATCH") return "severity-dispatch";
    if (s === "SAFETY") return "severity-safety";
    if (s === "ARRIVAL" || s === "SUCCESS") return "severity-arrival";
    if (s === "SYSTEM") return "severity-system";
    return "severity-info";
  }

  // ------------------------------------------------------------------ //
  // Data Fetching & Polling
  // ------------------------------------------------------------------ //

  async function loadAlertsData() {
    if (isFetching) return;
    isFetching = true;
    if (el.refreshBtn) el.refreshBtn.classList.add("is-spinning");

    try {
      const res = await fetch(`${apiBase()}/alerts`);
      if (res.ok) {
        const data = await res.json();
        rawEvents = data.events || [];
        currentSummary = data.summary || {};
        currentOperationStatus = data.operation_status || {};
        currentActivities = data.recent_activities || [];

        if (el.liveStatusText) el.liveStatusText.textContent = "LIVE STREAM";
      } else if (res.status === 409) {
        // Scenario not started yet
        rawEvents = [];
        currentSummary = { critical: 0, warning: 0, info: 0, dispatch: 0, safety: 0, arrival: 0, system: 0, total: 0 };
        currentOperationStatus = {
          active_teams_count: 0,
          teams_en_route: 0,
          teams_available: 0,
          teams_arrived: 0,
          active_missions_count: 0,
          high_priority_victims_count: 0,
          system_status: "Standby",
          communication_status: "Awaiting Scenario",
        };
        currentActivities = [];
        if (el.liveStatusText) el.liveStatusText.textContent = "STANDBY";
      }
    } catch (err) {
      if (el.liveStatusText) el.liveStatusText.textContent = "LINK DOWN";
    } finally {
      isFetching = false;
      if (el.refreshBtn) el.refreshBtn.classList.remove("is-spinning");
      renderAll();
    }
  }

  // ------------------------------------------------------------------ //
  // Filtering & Search
  // ------------------------------------------------------------------ //

  function getFilteredEvents() {
    const q = searchQuery.trim().toLowerCase();

    return rawEvents.filter(ev => {
      // Category filter
      if (currentFilter === "unread") {
        if (readIds.has(ev.id)) return false;
      } else if (currentFilter === "critical") {
        if (ev.severity !== "CRITICAL" && ev.category !== "critical") return false;
      } else if (currentFilter === "warning") {
        if (ev.severity !== "WARNING" && ev.category !== "warning") return false;
      } else if (currentFilter === "dispatch") {
        if (ev.severity !== "DISPATCH" && ev.category !== "dispatch") return false;
      } else if (currentFilter === "safety") {
        if (ev.category !== "safety" && !String(ev.type || "").toLowerCase().includes("safety")) return false;
      } else if (currentFilter === "arrival") {
        if (ev.category !== "arrival" && ev.severity !== "ARRIVAL") return false;
      } else if (currentFilter === "system") {
        if (ev.category !== "system" && ev.severity !== "SYSTEM") return false;
      }

      // Search filter
      if (q) {
        const text = [
          ev.message,
          ev.type,
          ev.source,
          ev.target,
          ev.victim_id,
          ev.callsign,
          ev.team_id,
          ev.priority,
          ev.severity,
        ].filter(Boolean).join(" ").toLowerCase();

        if (!text.includes(q)) return false;
      }

      return true;
    });
  }

  // ------------------------------------------------------------------ //
  // Rendering Routines
  // ------------------------------------------------------------------ //

  function renderAll() {
    renderSummaryCards();
    renderFilterPills();
    renderTable();
    renderDetailsPanel();
    renderSeverityBreakdown();
    renderRecentActivities();
    renderOperationStatus();
  }

  function renderSummaryCards() {
    const unreadCount = rawEvents.filter(e => !readIds.has(e.id)).length;
    const criticalCount = rawEvents.filter(e => e.severity === "CRITICAL" || e.category === "critical").length;
    const warningCount = rawEvents.filter(e => e.severity === "WARNING" || e.category === "warning").length;
    const infoCount = rawEvents.filter(e => e.severity === "INFO" || e.category === "info").length;
    const totalCount = rawEvents.length;

    if (el.kpiUnread) el.kpiUnread.textContent = unreadCount;
    if (el.kpiCritical) el.kpiCritical.textContent = criticalCount;
    if (el.kpiWarning) el.kpiWarning.textContent = warningCount;
    if (el.kpiInfo) el.kpiInfo.textContent = infoCount;
    if (el.kpiTotal) el.kpiTotal.textContent = totalCount;

    if (el.bellDot) el.bellDot.hidden = unreadCount === 0;
  }

  function renderFilterPills() {
    const total = rawEvents.length;
    const critical = rawEvents.filter(e => e.severity === "CRITICAL" || e.category === "critical").length;
    const warning = rawEvents.filter(e => e.severity === "WARNING" || e.category === "warning").length;
    const dispatch = rawEvents.filter(e => e.severity === "DISPATCH" || e.category === "dispatch").length;
    const safety = rawEvents.filter(e => e.category === "safety" || String(e.type || "").toLowerCase().includes("safety")).length;
    const arrival = rawEvents.filter(e => e.category === "arrival" || e.severity === "ARRIVAL").length;
    const system = rawEvents.filter(e => e.category === "system" || e.severity === "SYSTEM").length;

    if (el.filterCountAll) el.filterCountAll.textContent = total;
    if (el.filterCountCritical) el.filterCountCritical.textContent = critical;
    if (el.filterCountWarning) el.filterCountWarning.textContent = warning;
    if (el.filterCountDispatch) el.filterCountDispatch.textContent = dispatch;
    if (el.filterCountSafety) el.filterCountSafety.textContent = safety;
    if (el.filterCountArrival) el.filterCountArrival.textContent = arrival;
    if (el.filterCountSystem) el.filterCountSystem.textContent = system;

    el.filterPills.forEach(pill => {
      pill.classList.toggle("is-active", pill.dataset.filter === currentFilter);
    });
  }

  function renderTable() {
    const events = getFilteredEvents();
    if (el.tableVisibleCount) el.tableVisibleCount.textContent = `${events.length} event${events.length === 1 ? "" : "s"}`;

    if (!events.length) {
      if (el.tableBody) el.tableBody.innerHTML = "";
      if (el.emptyMsg) {
        el.emptyMsg.hidden = false;
        if (el.emptySubText) {
          el.emptySubText.textContent = rawEvents.length === 0
            ? "No events logged in the system yet. Start a scenario to view incoming telemetry and operational dispatches."
            : "No events match the selected filter or search keyword.";
        }
      }
      return;
    }

    if (el.emptyMsg) el.emptyMsg.hidden = true;

    if (el.tableBody) {
      el.tableBody.innerHTML = events.map(ev => {
        const isRead = readIds.has(ev.id);
        const isSelected = selectedAlertId === ev.id;
        const sevClass = getSeverityClass(ev.severity);
        const timeStr = formatTime(ev.timestamp || ev.time);
        const statusDotHtml = isRead ? `<span class="alert-dot-read"></span>` : `<span class="alert-dot-unread" title="Unread"></span>`;
        const actionLabel = ev.action_label || "View";
        const actionUrl = ev.action_url || "#";

        return `
          <tr class="${isRead ? "alerts-row-read" : "alerts-row-unread"} ${isSelected ? "alerts-row-selected" : ""}" data-alert-id="${escapeHtml(ev.id)}">
            <td class="alerts-status-dot-cell">${statusDotHtml}</td>
            <td class="time-cell">${escapeHtml(timeStr)}</td>
            <td><span class="severity-badge ${sevClass}">${escapeHtml(ev.severity || "INFO")}</span></td>
            <td class="type-cell">${escapeHtml(ev.type || "System")}</td>
            <td class="msg-cell" title="${escapeHtml(ev.message)}">${escapeHtml(ev.message)}</td>
            <td class="source-cell">${escapeHtml(ev.source || "System")}</td>
            <td class="target-cell">${escapeHtml(ev.target || "All")}</td>
            <td><span class="detail-status-pill">${isRead ? "Read" : "Unread"}</span></td>
            <td>
              <a href="${escapeHtml(actionUrl)}" class="table-act-btn" data-prevent-select="true">
                ${escapeHtml(actionLabel)}
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>
              </a>
            </td>
          </tr>
        `;
      }).join("");

      // Bind row clicks
      el.tableBody.querySelectorAll("tr").forEach(row => {
        row.addEventListener("click", (e) => {
          if (e.target.closest("a") || e.target.closest("button")) return;
          const id = row.dataset.alertId;
          selectAlert(id);
        });
      });
    }
  }

  function selectAlert(id) {
    selectedAlertId = id;
    if (id && !readIds.has(id)) {
      readIds.add(id);
      saveReadIds(readIds);
      renderSummaryCards();
    }
    renderTable();
    renderDetailsPanel();
  }

  function renderDetailsPanel() {
    const alert = rawEvents.find(e => e.id === selectedAlertId);

    if (!alert) {
      if (el.detailPlaceholder) el.detailPlaceholder.hidden = false;
      if (el.detailBody) el.detailBody.hidden = true;
      if (el.detailStatusPill) el.detailStatusPill.textContent = "No Selection";
      return;
    }

    if (el.detailPlaceholder) el.detailPlaceholder.hidden = true;
    if (el.detailBody) el.detailBody.hidden = false;

    const isRead = readIds.has(alert.id);
    if (el.detailStatusPill) {
      el.detailStatusPill.textContent = isRead ? "Status: Read" : "Status: Unread";
      el.detailStatusPill.style.color = isRead ? "var(--ink-dim)" : "#2563eb";
    }

    if (el.detailSeverityBadge) {
      el.detailSeverityBadge.className = `severity-badge ${getSeverityClass(alert.severity)}`;
      el.detailSeverityBadge.textContent = alert.severity || "INFO";
    }

    if (el.detailType) el.detailType.textContent = alert.type || "Event Details";
    if (el.detailMsgBox) el.detailMsgBox.textContent = alert.message || "—";

    // Victim ID
    if (el.detailVictimWrap) {
      if (alert.victim_id) {
        el.detailVictimWrap.hidden = false;
        if (el.detailVictimId) el.detailVictimId.textContent = alert.victim_id;
      } else {
        el.detailVictimWrap.hidden = true;
      }
    }

    // Priority / SPS
    if (el.detailPriorityWrap) {
      if (alert.priority || alert.sps != null) {
        el.detailPriorityWrap.hidden = false;
        if (el.detailPriority) {
          el.detailPriority.textContent = `${alert.priority || "—"}${alert.sps != null ? ` (SPS ${alert.sps})` : ""}`;
        }
      } else {
        el.detailPriorityWrap.hidden = true;
      }
    }

    // Team / Callsign
    if (el.detailTeamWrap) {
      if (alert.callsign || alert.team_id) {
        el.detailTeamWrap.hidden = false;
        if (el.detailTeam) el.detailTeam.textContent = alert.callsign || alert.team_id;
      } else {
        el.detailTeamWrap.hidden = true;
      }
    }

    // Location
    if (el.detailLocationWrap) {
      if (alert.location && alert.location.latitude != null) {
        el.detailLocationWrap.hidden = false;
        if (el.detailLocation) {
          el.detailLocation.textContent = `${alert.location.latitude.toFixed(4)}°, ${alert.location.longitude.toFixed(4)}°`;
        }
      } else {
        el.detailLocationWrap.hidden = true;
      }
    }

    if (el.detailTime) el.detailTime.textContent = formatTime(alert.timestamp || alert.time);
    if (el.detailSource) el.detailSource.textContent = alert.source || "RIDGEWATCH Core";
    if (el.detailTarget) el.detailTarget.textContent = alert.target || "Commander / Field";

    // Action button
    if (el.detailActionBtn) {
      el.detailActionBtn.href = alert.action_url || "#";
      el.detailActionBtn.querySelector("span").textContent = alert.action_label || "View Related Record";
    }
  }

  function renderSeverityBreakdown() {
    const total = rawEvents.length || 1;
    const critical = rawEvents.filter(e => e.severity === "CRITICAL" || e.category === "critical").length;
    const warning = rawEvents.filter(e => e.severity === "WARNING" || e.category === "warning").length;
    const dispatch = rawEvents.filter(e => e.severity === "DISPATCH" || e.category === "dispatch").length;
    const info = rawEvents.filter(e => e.severity === "INFO" || e.category === "info").length;

    if (el.sevBarCountCritical) el.sevBarCountCritical.textContent = critical;
    if (el.sevBarFillCritical) el.sevBarFillCritical.style.width = `${Math.round((critical / total) * 100)}%`;

    if (el.sevBarCountWarning) el.sevBarCountWarning.textContent = warning;
    if (el.sevBarFillWarning) el.sevBarFillWarning.style.width = `${Math.round((warning / total) * 100)}%`;

    if (el.sevBarCountDispatch) el.sevBarCountDispatch.textContent = dispatch;
    if (el.sevBarFillDispatch) el.sevBarFillDispatch.style.width = `${Math.round((dispatch / total) * 100)}%`;

    if (el.sevBarCountInfo) el.sevBarCountInfo.textContent = info;
    if (el.sevBarFillInfo) el.sevBarFillInfo.style.width = `${Math.round((info / total) * 100)}%`;
  }

  function renderRecentActivities() {
    if (!el.activitiesTimeline) return;

    if (!currentActivities || !currentActivities.length) {
      el.activitiesTimeline.innerHTML = `<div class="activities-empty dim">No team activities logged yet.</div>`;
      return;
    }

    el.activitiesTimeline.innerHTML = currentActivities.map(act => {
      const timeStr = formatTime(act.timestamp || act.time);
      const sevClass = getSeverityClass(act.severity);
      return `
        <div class="activity-item">
          <span class="activity-dot"></span>
          <span class="activity-time">${escapeHtml(timeStr)}</span>
          <div class="activity-msg">
            ${escapeHtml(act.message)}
          </div>
          <span class="activity-badge ${sevClass}">${escapeHtml(act.severity || "DISPATCH")}</span>
        </div>
      `;
    }).join("");
  }

  function renderOperationStatus() {
    const st = currentOperationStatus || {};

    if (el.opActiveTeams) el.opActiveTeams.textContent = st.active_teams_count != null ? st.active_teams_count : 0;
    if (el.opActiveTeamsSub) {
      const enRoute = st.teams_en_route || 0;
      const avail = st.teams_available || 0;
      el.opActiveTeamsSub.textContent = `${enRoute} En-route • ${avail} Available`;
    }

    if (el.opActiveMissions) el.opActiveMissions.textContent = st.active_missions_count != null ? st.active_missions_count : 0;
    if (el.opActiveMissionsSub) {
      el.opActiveMissionsSub.textContent = (st.active_missions_count || 0) > 0 ? "In Progress" : "Standby";
    }

    if (el.opHighVictims) el.opHighVictims.textContent = st.high_priority_victims_count != null ? st.high_priority_victims_count : 0;
    if (el.opHighVictimsSub) {
      const highCount = st.high_priority_victims_count || 0;
      el.opHighVictimsSub.textContent = highCount > 0 ? "Needs immediate attention" : "No critical survivors";
    }

    if (el.opSystemStatus) el.opSystemStatus.textContent = st.system_status || "Operational";
    if (el.opSystemStatusSub) el.opSystemStatusSub.textContent = (st.system_status || "").includes("Degradation") ? "Active Stress Mode" : "All Telemetry Normal";

    if (el.opCommStatus) el.opCommStatus.textContent = st.communication_status || "Good";
    if (el.opCommStatusSub) el.opCommStatusSub.textContent = "Network Healthy";
  }

  // ------------------------------------------------------------------ //
  // Event Bindings
  // ------------------------------------------------------------------ //

  function bindEvents() {
    // Filter Pills
    el.filterPills.forEach(pill => {
      pill.addEventListener("click", () => {
        currentFilter = pill.dataset.filter || "all";
        renderFilterPills();
        renderTable();
      });
    });

    // KPI Card click filters
    const kpiBindings = [
      { card: el.cardUnread, filter: "unread" },
      { card: el.cardCritical, filter: "critical" },
      { card: el.cardWarning, filter: "warning" },
      { card: el.cardInfo, filter: "info" },
      { card: el.cardTotal, filter: "all" },
    ];
    kpiBindings.forEach(({ card, filter }) => {
      if (card) {
        card.addEventListener("click", () => {
          currentFilter = filter;
          renderFilterPills();
          renderTable();
        });
      }
    });

    // Search Input
    if (el.searchInput) {
      el.searchInput.addEventListener("input", () => {
        searchQuery = el.searchInput.value;
        if (el.searchClear) el.searchClear.hidden = !searchQuery;
        renderTable();
      });
    }

    if (el.searchClear) {
      el.searchClear.addEventListener("click", () => {
        if (el.searchInput) el.searchInput.value = "";
        searchQuery = "";
        el.searchClear.hidden = true;
        renderTable();
      });
    }

    // Refresh Button
    if (el.refreshBtn) {
      el.refreshBtn.addEventListener("click", () => {
        loadAlertsData();
      });
    }

    // Bell Button
    if (el.bellBtn) {
      el.bellBtn.addEventListener("click", () => {
        currentFilter = currentFilter === "unread" ? "all" : "unread";
        renderFilterPills();
        renderTable();
      });
    }

    // Mark All As Read
    if (el.markAllReadBtn) {
      el.markAllReadBtn.addEventListener("click", () => {
        rawEvents.forEach(e => readIds.add(e.id));
        saveReadIds(readIds);
        renderSummaryCards();
        renderTable();
        renderDetailsPanel();
      });
    }
  }

  // ------------------------------------------------------------------ //
  // Initialization
  // ------------------------------------------------------------------ //

  bindEvents();
  loadAlertsData();
  pollInterval = setInterval(loadAlertsData, POLL_MS);
})();
