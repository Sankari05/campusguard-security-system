/* ==========================================================================
   RIDGEWATCH Testing Module — Scenarios Ledger Controller
   Custom scenarios can be toggled Active/Inactive here; only Active ones
   are offered in the Dashboard's "Start Scenario" picker.
   ========================================================================== */

(() => {
  "use strict";

  const scenariosTableBody = document.getElementById("scenariosTableBody");
  const scenariosTotalCount = document.getElementById("scenariosTotalCount");
  const scenariosSearchInput = document.getElementById("scenariosSearchInput");

  let allScenarios = [];
  let pendingToggleId = null; // scenario_ref_id currently mid-request, to disable its button

  async function loadScenariosLedger() {
    try {
      const data = await TestingCommon.testingFetch("/admin/scenarios");
      allScenarios = data.scenarios || [];
      renderTable();
    } catch (err) {
      if (scenariosTableBody) {
        scenariosTableBody.innerHTML = `
          <tr>
            <td colspan="8" style="text-align: center; color: var(--tri-high); padding: 32px;">
              ⚠️ Failed to load scenarios ledger: ${escapeHtml(err.message)}
            </td>
          </tr>
        `;
      }
    }
  }

  async function toggleStatus(scenarioRefId, currentStatus) {
    const nextStatus = (currentStatus || "Active").toLowerCase() === "active" ? "Inactive" : "Active";
    pendingToggleId = scenarioRefId;
    renderTable();
    try {
      await TestingCommon.testingFetch(`/admin/scenarios/${encodeURIComponent(scenarioRefId)}/status`, {
        method: "POST",
        body: JSON.stringify({ status: nextStatus }),
      });
      const s = allScenarios.find(x => x.scenario_ref_id === scenarioRefId);
      if (s) s.status = nextStatus;
    } catch (err) {
      alert(`Failed to update status: ${err.message}`);
    } finally {
      pendingToggleId = null;
      renderTable();
    }
  }

  function renderTable() {
    if (!scenariosTableBody) return;
    const query = (scenariosSearchInput ? scenariosSearchInput.value : "").toLowerCase().trim();

    const filtered = allScenarios.filter(s => {
      const nameMatch = (s.scenario_name || "").toLowerCase().includes(query);
      const hazardMatch = (s.hazard_type || "").toLowerCase().includes(query);
      const idMatch = (s.scenario_ref_id || "").toLowerCase().includes(query);
      return nameMatch || hazardMatch || idMatch;
    });

    if (scenariosTotalCount) {
      scenariosTotalCount.textContent = allScenarios.length;
    }

    if (filtered.length === 0) {
      scenariosTableBody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; color: var(--ink-faint); padding: 32px;">
            ${allScenarios.length === 0 ? "No disaster scenarios created yet." : "No matching scenarios found."}
          </td>
        </tr>
      `;
      return;
    }

    // Records are sorted newest first by SQLite created_at DESC
    const rows = filtered.map(s => {
      const hazardClass = (s.hazard_type || "").toLowerCase().replace(/\s+/g, "");
      const createdDate = TestingCommon.formatDate(s.created_at);
      const createdTime = TestingCommon.formatTime(s.created_at);

      const lat = s.latitude != null ? Number(s.latitude).toFixed(4) : "—";
      const lng = s.longitude != null ? Number(s.longitude).toFixed(4) : "—";
      const locStr = lat !== "—" && lng !== "—" ? `${lat}, ${lng}` : "—";

      const status = s.status || "Active";
      const isActive = status.toLowerCase() === "active";
      const pillClass = isActive ? "status-pill-active" : "status-pill-inactive";
      const isPending = pendingToggleId === s.scenario_ref_id;
      const nextLabel = isActive ? "Deactivate" : "Activate";

      return `
        <tr>
          <td><span class="id-badge">${escapeHtml(s.scenario_ref_id)}</span></td>
          <td><strong>${escapeHtml(s.scenario_name || 'Custom Scenario')}</strong></td>
          <td>
            <span class="hazard-badge hazard-${hazardClass}">
              ${hazardIcon(hazardClass)} ${escapeHtml(s.hazard_type || 'Unknown')}
            </span>
          </td>
          <td><span style="font-weight: 600;">${s.victim_count || 0}</span> <span style="color: var(--ink-dim); font-size: 11px;">victims</span></td>
          <td class="coord-cell">${escapeHtml(locStr)}</td>
          <td>
            <span class="status-pill ${pillClass}">
              <span class="status-pill-toggle-dot" aria-hidden="true"></span>
              ${escapeHtml(status)}
            </span>
          </td>
          <td>
            <button
              type="button"
              class="btn btn-xs ${isActive ? 'btn-secondary' : 'btn-primary'} scenario-action-btn"
              data-scenario-ref-id="${escapeHtml(s.scenario_ref_id)}"
              data-current-status="${escapeHtml(status)}"
              title="Click to ${nextLabel.toLowerCase()} this scenario."
              ${isPending ? "disabled" : ""}
            >
              ${isPending ? "Updating…" : nextLabel}
            </button>
          </td>
          <td class="datetime-cell"><span class="datetime-date">${escapeHtml(createdDate)}</span></td>
          <td class="datetime-cell"><span class="datetime-time">${escapeHtml(createdTime)}</span></td>
        </tr>
      `;
    }).join("");

    scenariosTableBody.innerHTML = rows;

    scenariosTableBody.querySelectorAll(".scenario-action-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        toggleStatus(btn.dataset.scenarioRefId, btn.dataset.currentStatus);
      });
    });
  }

  function hazardIcon(type) {
    if (type.includes("earthquake")) return "🌋";
    if (type.includes("flood")) return "🌊";
    if (type.includes("avalanche")) return "❄️";
    return "⚠️";
  }

  if (scenariosSearchInput) {
    scenariosSearchInput.addEventListener("input", renderTable);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initialize
  loadScenariosLedger();
})();
