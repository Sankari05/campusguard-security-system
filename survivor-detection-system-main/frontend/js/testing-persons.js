/* ==========================================================================
   RIDGEWATCH Testing Module — Persons Ledger Controller (View-Only)
   ========================================================================== */

(() => {
  "use strict";

  const personsTableBody = document.getElementById("personsTableBody");
  const personnelTotalCount = document.getElementById("personnelTotalCount");
  const ledgerSearchInput = document.getElementById("ledgerSearchInput");

  let allPersonnel = [];

  async function loadPersonnelLedger() {
    try {
      const data = await TestingCommon.testingFetch("/admin/personnel");
      allPersonnel = data.personnel || [];
      renderTable();
    } catch (err) {
      if (personsTableBody) {
        personsTableBody.innerHTML = `
          <tr>
            <td colspan="8" style="text-align: center; color: var(--tri-high); padding: 32px;">
              ⚠️ Failed to load persons ledger: ${escapeHtml(err.message)}
            </td>
          </tr>
        `;
      }
    }
  }

  function renderTable() {
    if (!personsTableBody) return;
    const query = (ledgerSearchInput ? ledgerSearchInput.value : "").toLowerCase().trim();

    const filtered = allPersonnel.filter(p => {
      const nameMatch = (p.full_name || "").toLowerCase().includes(query);
      const roleMatch = (p.role || "").toLowerCase().includes(query);
      const idMatch = (p.person_id || "").toLowerCase().includes(query);
      const phoneMatch = (p.phone || "").toLowerCase().includes(query);
      return nameMatch || roleMatch || idMatch || phoneMatch;
    });

    if (personnelTotalCount) {
      personnelTotalCount.textContent = allPersonnel.length;
    }

    if (filtered.length === 0) {
      personsTableBody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; color: var(--ink-faint); padding: 32px;">
            ${allPersonnel.length === 0 ? "No personnel records registered yet." : "No matching records found."}
          </td>
        </tr>
      `;
      return;
    }

    // Records are already sorted newest first by backend query (ORDER BY created_at DESC)
    const rows = filtered.map(p => {
      const roleClass = (p.role || "").toLowerCase().replace(/\s+/g, "");
      const createdDate = TestingCommon.formatDate(p.created_at);
      const createdTime = TestingCommon.formatTime(p.created_at);
      const isStatusActive = (p.status || "").toLowerCase() === "active";

      return `
        <tr>
          <td><span class="id-badge">${escapeHtml(p.person_id)}</span></td>
          <td><strong>${escapeHtml(p.full_name)}</strong></td>
          <td><span class="role-badge role-badge-${roleClass}">${escapeHtml(p.role || 'Rescuer')}</span></td>
          <td>
            <span class="status-pill ${isStatusActive ? 'status-pill-active' : 'status-pill-hold'}">
              ${escapeHtml(p.status || 'Active')}
            </span>
          </td>
          <td style="font-family: var(--font-mono); font-size: 12px; color: var(--ink-dim);">${escapeHtml(p.phone || p.email || '—')}</td>
          <td><span style="font-family: var(--font-mono); font-size: 11px; color: var(--ink-faint);">${escapeHtml(p.badge_id || '—')}</span></td>
          <td class="datetime-cell"><span class="datetime-date">${escapeHtml(createdDate)}</span></td>
          <td class="datetime-cell"><span class="datetime-time">${escapeHtml(createdTime)}</span></td>
        </tr>
      `;
    }).join("");

    personsTableBody.innerHTML = rows;
  }

  if (ledgerSearchInput) {
    ledgerSearchInput.addEventListener("input", renderTable);
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
  loadPersonnelLedger();
})();
