/* ==========================================================================
   RIDGEWATCH Testing Module — Add Rescue Team Controller
   ========================================================================== */

(() => {
  "use strict";

  const createTeamForm = document.getElementById("createTeamForm");
  const createTeamMsg = document.getElementById("createTeamMsg");
  const createTeamSubmitBtn = document.getElementById("createTeamSubmitBtn");

  const personnelPickerGrid = document.getElementById("personnelPickerGrid");
  const personnelSearchInput = document.getElementById("personnelSearchInput");
  const selectedMembersTableBody = document.getElementById("selectedMembersTableBody");
  const selectedCount = document.getElementById("selectedCount");

  let allPersonnel = [];
  let selectedMembers = new Map();

  function showMessage(el, text, isError = false) {
    if (!el) return;
    el.className = isError ? "admin-msg-box is-error" : "admin-msg-box is-success";
    el.innerHTML = isError ? `<span>⚠️</span> <span>${text}</span>` : `<span>✅</span> <span>${text}</span>`;
    el.style.display = "flex";
  }

  // ------------------------------------------------------------------ //
  // Load registered personnel
  // ------------------------------------------------------------------ //

  async function loadPersonnel() {
    try {
      const data = await TestingCommon.testingFetch("/admin/personnel");
      allPersonnel = data.personnel || [];
      renderPicker();
    } catch (err) {
      if (personnelPickerGrid) {
        personnelPickerGrid.innerHTML = `
          <div style="padding: 12px; text-align: center; color: var(--tri-high); grid-column: 1/-1;">
            Failed to load personnel: ${err.message}
          </div>
        `;
      }
    }
  }

  // ------------------------------------------------------------------ //
  // Render Personnel Picker
  // ------------------------------------------------------------------ //

  function renderPicker() {
    if (!personnelPickerGrid) return;
    const query = (personnelSearchInput ? personnelSearchInput.value : "").toLowerCase().trim();

    const filtered = allPersonnel.filter(p => {
      const nameMatch = (p.full_name || "").toLowerCase().includes(query);
      const roleMatch = (p.role || "").toLowerCase().includes(query);
      const idMatch = (p.person_id || "").toLowerCase().includes(query);
      return nameMatch || roleMatch || idMatch;
    });

    if (filtered.length === 0) {
      personnelPickerGrid.innerHTML = `
        <div style="padding: 14px; text-align: center; color: var(--ink-faint); grid-column: 1/-1;">
          ${allPersonnel.length === 0 ? "No personnel registered yet. Please create personnel first." : "No matching personnel found."}
        </div>
      `;
      return;
    }

    personnelPickerGrid.innerHTML = filtered.map(p => {
      const isSelected = selectedMembers.has(p.person_id);
      return `
        <div class="member-pick-item" style="${isSelected ? 'background: #f0fdf4; border-color: #86efac;' : ''}">
          <div class="member-pick-info">
            <span class="member-pick-name">${escapeHtml(p.full_name)}</span>
            <span class="member-pick-sub">${p.person_id} · <span class="role-badge role-badge-${(p.role || '').toLowerCase().replace(/\s+/g, '')}">${escapeHtml(p.role || 'Staff')}</span></span>
          </div>
          <button type="button" class="btn-add-member" data-id="${p.person_id}" ${isSelected ? 'disabled style="opacity: 0.5; cursor: default;"' : ''}>
            ${isSelected ? '✓ Added' : '+ Add'}
          </button>
        </div>
      `;
    }).join("");

    // Wire add buttons
    personnelPickerGrid.querySelectorAll(".btn-add-member").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        const person = allPersonnel.find(p => p.person_id === id);
        if (person && !selectedMembers.has(id)) {
          selectedMembers.set(id, {
            person_id: person.person_id,
            full_name: person.full_name,
            role: person.role,
            phone: person.phone || "—",
            role_on_team: person.role || "Member",
          });
          renderPicker();
          renderSelectedTable();
        }
      });
    });
  }

  // ------------------------------------------------------------------ //
  // Render Selected Members Preview Table
  // ------------------------------------------------------------------ //

  function renderSelectedTable() {
    if (!selectedMembersTableBody) return;
    if (selectedCount) selectedCount.textContent = selectedMembers.size;

    if (selectedMembers.size === 0) {
      selectedMembersTableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--ink-faint); padding: 24px;">
            No personnel selected yet. Choose staff members from the list above.
          </td>
        </tr>
      `;
      return;
    }

    const rows = Array.from(selectedMembers.values()).map(m => {
      return `
        <tr data-id="${m.person_id}">
          <td><span class="id-badge">${escapeHtml(m.person_id)}</span></td>
          <td><strong>${escapeHtml(m.full_name)}</strong></td>
          <td><span class="role-badge role-badge-${(m.role || '').toLowerCase().replace(/\s+/g, '')}">${escapeHtml(m.role)}</span></td>
          <td>
            <select class="form-select role-on-team-select" data-id="${m.person_id}" style="padding: 5px 8px; font-size: 12px;">
              <option value="Team Leader" ${m.role_on_team === 'Team Leader' ? 'selected' : ''}>Team Leader</option>
              <option value="Search Specialist" ${m.role_on_team === 'Search Specialist' ? 'selected' : ''}>Search Specialist</option>
              <option value="Field Medic" ${m.role_on_team === 'Field Medic' ? 'selected' : ''}>Field Medic</option>
              <option value="Comms Technician" ${m.role_on_team === 'Comms Technician' ? 'selected' : ''}>Comms Technician</option>
              <option value="Rescue Operator" ${m.role_on_team === 'Rescue Operator' ? 'selected' : ''}>Rescue Operator</option>
              <option value="Rescuer" ${m.role_on_team === 'Rescuer' ? 'selected' : ''}>Rescuer</option>
              <option value="Member" ${m.role_on_team === 'Member' ? 'selected' : ''}>Member</option>
            </select>
          </td>
          <td style="font-family: var(--font-mono); font-size: 12px; color: var(--ink-dim);">${escapeHtml(m.phone)}</td>
          <td style="text-align: center;">
            <button type="button" class="btn btn-small btn-danger remove-member-btn" data-id="${m.person_id}" title="Remove member">
              ✕
            </button>
          </td>
        </tr>
      `;
    }).join("");

    selectedMembersTableBody.innerHTML = rows;

    // Wire role selects
    selectedMembersTableBody.querySelectorAll(".role-on-team-select").forEach(sel => {
      sel.addEventListener("change", (e) => {
        const id = e.target.dataset.id;
        if (selectedMembers.has(id)) {
          selectedMembers.get(id).role_on_team = e.target.value;
        }
      });
    });

    // Wire remove buttons
    selectedMembersTableBody.querySelectorAll(".remove-member-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        selectedMembers.delete(id);
        renderPicker();
        renderSelectedTable();
      });
    });
  }

  if (personnelSearchInput) {
    personnelSearchInput.addEventListener("input", renderPicker);
  }

  // ------------------------------------------------------------------ //
  // Form submission
  // ------------------------------------------------------------------ //

  if (createTeamForm) {
    createTeamForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const teamName = document.getElementById("teamName").value.trim();
      const teamType = document.getElementById("teamType").value;
      const description = document.getElementById("teamDesc").value.trim() || null;

      if (!teamName) {
        showMessage(createTeamMsg, "Please enter a team name.", true);
        return;
      }

      createTeamSubmitBtn.disabled = true;
      createTeamSubmitBtn.innerHTML = `<span>⏳</span> <span>Creating Team…</span>`;

      try {
        const membersList = Array.from(selectedMembers.values()).map(m => ({
          person_id: m.person_id,
          role_on_team: m.role_on_team || m.role || "Member",
        }));

        const payload = {
          team_name: teamName,
          team_type: teamType,
          description,
          members: membersList,
        };

        const res = await TestingCommon.testingFetch("/admin/teams/create", {
          method: "POST",
          body: JSON.stringify(payload),
        });

        showMessage(createTeamMsg, `Rescue Team "${teamName}" (${res.team_ref_id}) formed with ${membersList.length} members! Redirecting to teams ledger…`);
        createTeamForm.reset();
        selectedMembers.clear();

        setTimeout(() => {
          window.location.href = "testing-teams.html";
        }, 1100);

      } catch (err) {
        showMessage(createTeamMsg, err.message, true);
        createTeamSubmitBtn.disabled = false;
        createTeamSubmitBtn.innerHTML = `<span>👥</span> <span>Create Rescue Team</span>`;
      }
    });
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
  loadPersonnel();
})();
