/**
 * notification.js
 * ----------------
 * Dedicated Frontend Controller for RidgeWatch Notification Center.
 * Handles live notification monitoring: SMS and Watch Delivery.
 */

(function () {
  "use strict";

  const apiBase = (typeof RidgeWatchConfig !== "undefined" && RidgeWatchConfig.getApiBase)
    ? RidgeWatchConfig.getApiBase()
    : "http://127.0.0.1:8000";
  let notificationsList = [];
  let activeFilter = "all";
  let activeSearch = "";
  let pollInterval = null;

  // DOM Elements
  const el = {
    totalCount: document.getElementById("kpiTotalCount"),
    smsCount: document.getElementById("kpiSmsCount"),
    failedCount: document.getElementById("kpiFailedCount"),
    tableBody: document.getElementById("notifTableBody"),
    searchInput: document.getElementById("notifSearchInput"),
    refreshBtn: document.getElementById("notifRefreshBtn"),
    filterBtns: document.querySelectorAll(".notif-filter-btn"),
    drawerOverlay: document.getElementById("notifDrawerOverlay"),
    drawer: document.getElementById("notifDrawer"),
    drawerClose: document.getElementById("drawerCloseBtn"),
    // Drawer Fields
    dTitle: document.getElementById("drawerTitle"),
    dSub: document.getElementById("drawerSub"),
    dPriority: document.getElementById("drawerPriority"),
    dNotifId: document.getElementById("drawerNotifId"),
    dCommandId: document.getElementById("drawerCommandId"),
    dMissionId: document.getElementById("drawerMissionId"),
    dTimestamp: document.getElementById("drawerTimestamp"),
    dTeam: document.getElementById("drawerTeam"),
    dMember: document.getElementById("drawerMember"),
    dRecipient: document.getElementById("drawerRecipient"),
    dSurvivor: document.getElementById("drawerSurvivor"),
    dSps: document.getElementById("drawerSps"),
    dDistance: document.getElementById("drawerDistance"),
    dCoords: document.getElementById("drawerCoords"),
    dGmaps: document.getElementById("drawerGmapsLink"),
    dAction: document.getElementById("drawerAction"),
    dSmsBadge: document.getElementById("drawerSmsBadge"),
    dSmsSub: document.getElementById("drawerSmsSub"),
    dWatchBadge: document.getElementById("drawerWatchBadge"),
    dWatchSub: document.getElementById("drawerWatchSub"),
  };

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  /**
   * Format ISO Timestamp
   */
  function formatTime(isoString) {
    if (!isoString) return "-";
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return isoString;
      return d.toLocaleDateString(undefined, {
        month: "short",
        day: "2-digit",
        year: "numeric",
      }) + " " + d.toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    } catch (e) {
      return isoString;
    }
  }

  /**
   * Channel Status Badge Generator
   */
  function getChannelBadge(channel, status) {
    const s = (status || "QUEUED").toUpperCase();
    if (channel === "sms") {
      if (s === "SENT") return `<span class="badge-channel badge-sent">🟢 SENT</span>`;
      if (s === "FAILED") return `<span class="badge-channel badge-failed">🔴 FAILED</span>`;
      return `<span class="badge-channel badge-queued">🟡 QUEUED</span>`;
    }

    if (channel === "watch") {
      if (s === "DELIVERED" || s === "DELIVERED_TO_BRIDGE" || s === "ACCEPTED") {
        return `<span class="badge-channel badge-sent">🟢 ${escapeHtml(s)}</span>`;
      }
      if (s === "WATCH_DISCONNECTED" || s === "FAILED") {
        return `<span class="badge-channel badge-failed">🔴 ${escapeHtml(s)}</span>`;
      }
      return `<span class="badge-channel badge-queued">🟡 ${escapeHtml(s)}</span>`;
    }

    return `<span class="badge-channel badge-mock">${escapeHtml(status)}</span>`;
  }

  /**
   * Priority Badge Generator
   */
  function getPriorityBadge(priority) {
    const p = (priority || "HIGH").toUpperCase();
    let cls = "priority-high";
    if (p === "CRITICAL") cls = "priority-critical";
    else if (p === "MEDIUM") cls = "priority-medium";
    else if (p === "LOW") cls = "priority-low";
    return `<span class="badge-priority ${cls}">${escapeHtml(p)}</span>`;
  }

  /**
   * Fetch Notifications from Backend
   */
  async function fetchNotifications() {
    try {
      const res = await fetch(`${apiBase}/notifications?limit=100`);
      if (!res.ok) {
        // Fallback endpoint check
        const fallbackRes = await fetch(`${apiBase}/api/notifications?limit=100`);
        if (!fallbackRes.ok) throw new Error("Failed to load notifications");
        const data = await fallbackRes.json();
        notificationsList = data.notifications || [];
      } else {
        const data = await res.json();
        notificationsList = data.notifications || [];
      }
      updateKpis();
      renderTable();
    } catch (err) {
      console.warn("Notifications fetch error:", err);
    }
  }

  /**
   * Update KPI Cards
   */
  function updateKpis() {
    const total = notificationsList.length;
    let smsSent = 0;
    let failedCount = 0;

    notificationsList.forEach((n) => {
      const sms = (n.sms_status || "").toUpperCase();
      if (sms === "SENT") smsSent++;
      if (sms === "FAILED" || (n.sms_error && sms !== "SENT")) failedCount++;
    });

    if (el.totalCount) el.totalCount.textContent = total;
    if (el.smsCount) el.smsCount.textContent = smsSent;
    if (el.failedCount) el.failedCount.textContent = failedCount;
  }

  /**
   * Filter & Search Notifications
   */
  function getFilteredNotifications() {
    return notificationsList.filter((n) => {
      // Filter tab
      if (activeFilter === "sms_sent" && (n.sms_status || "").toUpperCase() !== "SENT") return false;
      if (activeFilter === "failed") {
        const smsF = (n.sms_status || "").toUpperCase() === "FAILED" || (n.sms_error && (n.sms_status || "").toUpperCase() !== "SENT");
        if (!smsF) return false;
      }

      // Search term
      if (activeSearch) {
        const q = activeSearch.toLowerCase();
        const cmdId = (n.rescue_command_id || n.alert_id || "").toLowerCase();
        const mem = (n.member_id || "").toLowerCase();
        const phone = (n.phone_number_masked || n.phone_number || "").toLowerCase();
        const vic = (n.victim_id || "").toLowerCase();
        const pri = (n.priority || "").toLowerCase();
        return cmdId.includes(q) || mem.includes(q) || phone.includes(q) || vic.includes(q) || pri.includes(q);
      }

      return true;
    });
  }

  /**
   * Render History Table
   */
  function renderTable() {
    if (!el.tableBody) return;
    const items = getFilteredNotifications();

    if (items.length === 0) {
      el.tableBody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align:center; padding: 36px; color: var(--ink-faint);">
            No rescue command notifications found.
          </td>
        </tr>
      `;
      return;
    }

    el.tableBody.innerHTML = items.map((n) => {
      const cmdId = n.rescue_command_id || (n.alert_id ? n.alert_id.replace("ALT-", "") : "RC-GEN");
      const maskedPhone = n.phone_number_masked || (n.phone_number ? n.phone_number.slice(0, 5) + "****" + n.phone_number.slice(-2) : "+91 80988****66");
      const memberDisp = n.member_id === "ALPHA-M001" ? "Alpha Member 1" : (n.member_id || "Rescuer");

      return `
        <tr data-notif-id="${escapeHtml(n.id || n.alert_id)}">
          <td style="font-family: var(--font-mono); font-size: 0.75rem; white-space: nowrap;">
            ${escapeHtml(formatTime(n.timestamp))}
          </td>
          <td style="font-family: var(--font-mono); font-weight: 700; color: var(--accent-ice);">
            ${escapeHtml(cmdId)}
          </td>
          <td style="font-weight: 600;">
            ${escapeHtml(memberDisp)}
          </td>
          <td>
            <span class="phone-masked">${escapeHtml(maskedPhone)}</span>
          </td>
          <td style="font-weight: 600;">
            ${escapeHtml(n.victim_id || "Survivor")}
          </td>
          <td>
            ${getPriorityBadge(n.priority)}
          </td>
          <td>
            ${getChannelBadge("sms", n.sms_status)}
          </td>
          <td>
            ${getChannelBadge("watch", n.watch_delivery_status)}
          </td>
          <td style="text-align: right;">
            <button type="button" class="btn btn-secondary btn-small notif-view-btn" data-notif-id="${escapeHtml(n.id || n.alert_id)}" style="padding: 3px 8px; font-size: 0.72rem;">
              Details ➔
            </button>
          </td>
        </tr>
      `;
    }).join("");

    // Attach row click events
    el.tableBody.querySelectorAll("tr").forEach((row) => {
      row.addEventListener("click", () => {
        const id = row.getAttribute("data-notif-id");
        if (id) openDetailDrawer(id);
      });
    });
  }

  /**
   * Open Detail Drawer
   */
  function openDetailDrawer(notifId) {
    const item = notificationsList.find((n) => (n.id === notifId || n.alert_id === notifId));
    if (!item) return;

    const cmdId = item.rescue_command_id || (item.alert_id ? item.alert_id.replace("ALT-", "") : "RC-GEN");
    const maskedPhone = item.phone_number_masked || "+91 80988****66";
    const memberDisp = item.member_id === "ALPHA-M001" ? "Alpha Member 1" : (item.member_id || "Alpha Team Member");
    const lat = item.latitude || 34.22564;
    const lon = item.longitude || 77.56142;

    if (el.dTitle) el.dTitle.textContent = `Notification · ${cmdId}`;
    if (el.dSub) el.dSub.textContent = `Mission Multi-Channel Dispatch · Dispatched ${formatTime(item.timestamp)}`;
    if (el.dPriority) {
      el.dPriority.textContent = (item.priority || "HIGH").toUpperCase();
      el.dPriority.className = `badge-priority priority-${(item.priority || "high").toLowerCase()}`;
    }
    if (el.dNotifId) el.dNotifId.textContent = item.id || `NOTIF-${cmdId}`;
    if (el.dCommandId) el.dCommandId.textContent = cmdId;
    if (el.dMissionId) el.dMissionId.textContent = item.mission_id || `MSN-${cmdId}`;
    if (el.dTimestamp) el.dTimestamp.textContent = formatTime(item.timestamp);
    if (el.dTeam) el.dTeam.textContent = item.team_id || "ALPHA";
    if (el.dMember) el.dMember.textContent = `${memberDisp} (${item.member_id || "ALPHA-M001"})`;
    if (el.dRecipient) el.dRecipient.textContent = maskedPhone;
    if (el.dSurvivor) el.dSurvivor.textContent = item.victim_id || "Survivor";
    if (el.dSps) el.dSps.textContent = `${item.sps || 88.5}%`;
    if (el.dDistance) el.dDistance.textContent = item.distance_label || `${item.distance_m || 62} m`;
    if (el.dCoords) el.dCoords.textContent = `${Number(lat).toFixed(5)}, ${Number(lon).toFixed(5)}`;
    if (el.dGmaps) el.dGmaps.href = `https://www.google.com/maps?q=${lat},${lon}`;
    if (el.dAction) el.dAction.textContent = item.required_action || item.message || `Proceed to rescue ${item.victim_id}`;

    // Channel details
    if (el.dSmsBadge) el.dSmsBadge.outerHTML = getChannelBadge("sms", item.sms_status);
    el.dSmsBadge = document.getElementById("drawerSmsBadge");
    if (el.dSmsSub) {
      const smsStatus = (item.sms_status || "").toUpperCase();
      const prov = (item.sms_provider || "").toUpperCase();
      if (item.sms_error) {
        el.dSmsSub.textContent = `Error: ${item.sms_error}`;
      } else if (smsStatus === "SENT") {
        el.dSmsSub.textContent = "SMSGate Android gateway delivered";
      } else if (smsStatus === "FAILED") {
        el.dSmsSub.textContent = "SMS delivery failed";
      } else if (smsStatus === "QUEUED") {
        el.dSmsSub.textContent = "SMS queued for delivery";
      } else {
        el.dSmsSub.textContent = "Emergency Carrier SMS Alert";
      }
    }

    if (el.dWatchBadge) el.dWatchBadge.outerHTML = getChannelBadge("watch", item.watch_delivery_status);
    el.dWatchBadge = document.getElementById("drawerWatchBadge");
    if (el.dWatchSub) {
      let ackText = `Wave Call Plus (CALLPLUS_7F1B) · State: ${item.watch_delivery_status || "PENDING"}`;
      if (item.acceptance_source) {
        ackText += ` · Accepted via ${item.acceptance_source}`;
      }
      el.dWatchSub.textContent = ackText;
    }

    if (el.drawerOverlay) el.drawerOverlay.classList.add("is-open");
    if (el.drawer) el.drawer.classList.add("is-open");
  }

  /**
   * Close Detail Drawer
   */
  function closeDetailDrawer() {
    if (el.drawerOverlay) el.drawerOverlay.classList.remove("is-open");
    if (el.drawer) el.drawer.classList.remove("is-open");
  }

  /**
   * Setup Event Listeners
   */
  function setupListeners() {
    if (el.refreshBtn) {
      el.refreshBtn.addEventListener("click", () => {
        fetchNotifications();
      });
    }

    if (el.searchInput) {
      el.searchInput.addEventListener("input", (e) => {
        activeSearch = e.target.value.trim();
        renderTable();
      });
    }

    el.filterBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        el.filterBtns.forEach((b) => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        activeFilter = btn.getAttribute("data-filter") || "all";
        renderTable();
      });
    });

    document.querySelectorAll(".notif-kpi-card").forEach((card) => {
      card.addEventListener("click", () => {
        const filter = card.getAttribute("data-filter");
        el.filterBtns.forEach((b) => {
          if (b.getAttribute("data-filter") === filter || (filter === "all" && b.getAttribute("data-filter") === "all")) {
            b.click();
          }
        });
      });
    });

    if (el.drawerClose) el.drawerClose.addEventListener("click", closeDetailDrawer);
    if (el.drawerOverlay) el.drawerOverlay.addEventListener("click", closeDetailDrawer);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeDetailDrawer();
    });

    // Offline Subsystem UI Handlers
    const syncBtn = document.getElementById("offlineSyncBtn");
    if (syncBtn) {
      syncBtn.addEventListener("click", triggerOfflineSync);
    }

    const simSendBtn = document.getElementById("simSendBtn");
    if (simSendBtn) {
      simSendBtn.addEventListener("click", sendSimulatedLoRaPacket);
    }
  }

  // -------------------------------------------------------------------------
  // Offline Communication Subsystem Logic
  // -------------------------------------------------------------------------

  async function fetchOfflineStatusAndQueue() {
    try {
      // 1. Fetch Status
      const statusRes = await fetch(`${apiBase}/api/offline/status`);
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        updateOfflineStatusUI(statusData);
      }

      // 2. Fetch Queue
      const queueRes = await fetch(`${apiBase}/api/offline/queue?limit=50`);
      if (queueRes.ok) {
        const queueData = await queueRes.json();
        renderOfflineQueueTable(queueData.messages || []);
      }
    } catch (err) {
      console.warn("[Offline UI] Could not fetch offline subsystem metrics:", err);
    }
  }

  function updateOfflineStatusUI(data) {
    const netBadge = document.getElementById("offlineNetBadge");
    const netDot = document.getElementById("offlineNetDot");
    const netText = document.getElementById("offlineNetText");
    const kpiPending = document.getElementById("kpiOfflineQueuePending");
    const kpiSynced = document.getElementById("kpiOfflineQueueSynced");
    const kpiLastSync = document.getElementById("kpiOfflineLastSyncTime");
    const kpiLoraMode = document.getElementById("kpiLoraMode");
    const kpiNodes = document.getElementById("kpiRegisteredNodes");

    const isOnline = !!data.internet_available;

    if (netBadge && netDot && netText) {
      if (isOnline) {
        netBadge.style.background = "rgba(16, 185, 129, 0.15)";
        netBadge.style.color = "#10b981";
        netBadge.style.border = "1px solid rgba(16, 185, 129, 0.3)";
        netDot.style.background = "#10b981";
        netText.textContent = "INTERNET ONLINE";
      } else {
        netBadge.style.background = "rgba(239, 68, 68, 0.15)";
        netBadge.style.color = "#ef4444";
        netBadge.style.border = "1px solid rgba(239, 68, 68, 0.3)";
        netDot.style.background = "#ef4444";
        netText.textContent = "OFFLINE (EDGE MODE)";
      }
    }

    if (kpiPending) kpiPending.textContent = data.pending_messages || 0;
    if (kpiSynced) kpiSynced.textContent = data.synced_messages || 0;
    if (kpiLastSync) {
      kpiLastSync.textContent = data.last_synchronization_time ? `Last: ${formatTime(new Date(data.last_synchronization_time * 1000).toISOString())}` : "Last: Never";
    }
    if (kpiLoraMode) kpiLoraMode.textContent = (data.lora_mode || "SIMULATOR").toUpperCase();
    if (kpiNodes) kpiNodes.textContent = data.registered_nodes_count || 1;
  }

  function renderOfflineQueueTable(messages) {
    const tbody = document.getElementById("offlineQueueTableBody");
    const countEl = document.getElementById("offlineQueueCount");
    if (!tbody) return;

    if (countEl) countEl.textContent = `${messages.length} records`;

    if (!messages || messages.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; padding: 24px; color: var(--ink-faint);">
            Local offline message buffer is currently empty.
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = messages.map(m => {
      let statusColor = "#f59e0b"; // Pending
      if (m.status === "SYNCED" || m.status === "ACKNOWLEDGED") statusColor = "#10b981";
      if (m.status === "FAILED" || m.status === "EXPIRED") statusColor = "#ef4444";

      return `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 600; color: var(--accent-ice);" title="${escapeHtml(m.message_id)}">
            ${escapeHtml(m.message_id.length > 18 ? m.message_id.substring(0, 18) + '…' : m.message_id)}
          </td>
          <td><span style="font-weight: 600;">${escapeHtml(m.message_type)}</span></td>
          <td>
            <span style="font-size: 0.7rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; background: rgba(59, 130, 246, 0.12); color: var(--accent-ice);">
              ${escapeHtml(m.priority)}
            </span>
          </td>
          <td style="font-family: var(--font-mono);">${m.hop_count}/${m.max_hops}</td>
          <td>
            <span style="font-size: 0.72rem; font-weight: 700; color: ${statusColor};">
              ● ${escapeHtml(m.status)}
            </span>
          </td>
          <td style="font-family: var(--font-mono);">${m.retry_count}</td>
        </tr>`;
    }).join("");
  }

  async function triggerOfflineSync() {
    const syncBtn = document.getElementById("offlineSyncBtn");
    if (syncBtn) {
      syncBtn.disabled = true;
      syncBtn.textContent = "⏳ Syncing...";
    }
    try {
      const res = await fetch(`${apiBase}/api/offline/sync`, { method: "POST" });
      const data = await res.json();
      console.log("[Offline Sync Result]", data);
      await fetchOfflineStatusAndQueue();
    } catch (err) {
      console.error("[Offline Sync Error]", err);
    } finally {
      if (syncBtn) {
        syncBtn.disabled = false;
        syncBtn.textContent = "🔄 Sync Queue Now";
      }
    }
  }

  async function sendSimulatedLoRaPacket() {
    const sourceNode = document.getElementById("simSourceNode")?.value || "NODE-SURVIVOR-ALPHA";
    const destNode = document.getElementById("simDestNode")?.value || "GATEWAY-01";
    const messageType = document.getElementById("simMessageType")?.value || "SURVIVOR_DETECTED";
    const distanceM = parseFloat(document.getElementById("simDistanceM")?.value || "450");
    const rawPayload = document.getElementById("simPayloadText")?.value || "{}";
    const outputLog = document.getElementById("simOutputLog");

    let parsedPayload = {};
    try {
      parsedPayload = JSON.parse(rawPayload);
    } catch (e) {
      parsedPayload = { text: rawPayload };
    }

    if (outputLog) {
      outputLog.innerHTML += `<br><span style="color: #fbbf24;">[TX INITIATED]</span> ${sourceNode} -> ${destNode} (${messageType})...`;
      outputLog.scrollTop = outputLog.scrollHeight;
    }

    try {
      const res = await fetch(`${apiBase}/api/offline/simulator/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_id: sourceNode,
          destination_id: destNode,
          message_type: messageType,
          payload: parsedPayload,
          simulated_distance_m: distanceM,
          priority: "HIGH",
        }),
      });

      const data = await res.json();
      if (outputLog) {
        if (data.success) {
          const tx = data.tx_result || {};
          outputLog.innerHTML += `<br><span style="color: #4ade80;">[TX SUCCESS]</span> Packet: ${data.packet.packet_id} | RSSI: ${tx.rssi_dbm} dBm | SNR: ${tx.snr_db} dB | ToA: ${tx.time_on_air_ms} ms`;
        } else {
          outputLog.innerHTML += `<br><span style="color: #f87171;">[TX FAILED]</span> Error: ${data.error || "Simulation packet dropped"}`;
        }
        outputLog.scrollTop = outputLog.scrollHeight;
      }

      await fetchOfflineStatusAndQueue();
    } catch (err) {
      if (outputLog) {
        outputLog.innerHTML += `<br><span style="color: #f87171;">[TX ERROR]</span> Network error: ${err.message}`;
        outputLog.scrollTop = outputLog.scrollHeight;
      }
    }
  }

  // Initialize
  setupListeners();
  fetchNotifications();
  fetchOfflineStatusAndQueue();

  // Real-time live polling every 4 seconds
  pollInterval = setInterval(() => {
    fetchNotifications();
    fetchOfflineStatusAndQueue();
  }, 4000);
})();
