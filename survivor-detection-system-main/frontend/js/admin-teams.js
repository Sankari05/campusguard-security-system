/* ==========================================================================
   RIDGEWATCH Rescue Teams Ledger Controller (View-Only)
   ========================================================================== */

(() => {
  "use strict";

  const teamsCardsList = document.getElementById("teamsCardsList");
  const teamsTotalCount = document.getElementById("teamsTotalCount");
  const teamsSearchInput = document.getElementById("teamsSearchInput");

  let allTeams = [];
  let expandedTeamIds = new Set();

  async function loadTeamsLedger() {
    try {
      const data = await AdminCommon.adminFetch("/admin/teams");
      allTeams = data.teams || [];
      // Default first team expanded if available
      if (allTeams.length > 0) {
        expandedTeamIds.add(allTeams[0].team_ref_id);
      }
      renderCards();
    } catch (err) {
      if (teamsCardsList) {
        teamsCardsList.innerHTML = `
          <div class="admin-card" style="text-align: center; color: var(--tri-high); padding: 32px;">
            ⚠️ Failed to load rescue teams ledger: ${escapeHtml(err.message)}
          </div>
        `;
      }
    }
  }

  function renderCards() {
    if (!teamsCardsList) return;
    const query = (teamsSearchInput ? teamsSearchInput.value : "").toLowerCase().trim();

    const filtered = allTeams.filter(t => {
      const nameMatch = (t.team_name || "").toLowerCase().includes(query);
      const typeMatch = (t.team_type || "").toLowerCase().includes(query);
      const idMatch = (t.team_ref_id || "").toLowerCase().includes(query);
      const descMatch = (t.description || "").toLowerCase().includes(query);
      const memberMatch = (t.members || []).some(m => 
        (m.full_name || "").toLowerCase().includes(query) ||
        (m.person_id || "").toLowerCase().includes(query) ||
        (m.role_on_team || "").toLowerCase().includes(query)
      );
      return nameMatch || typeMatch || idMatch || descMatch || memberMatch;
    });

    if (teamsTotalCount) {
      teamsTotalCount.textContent = allTeams.length;
    }

    if (filtered.length === 0) {
      teamsCardsList.innerHTML = `
        <div class="admin-card" style="text-align: center; color: var(--ink-faint); padding: 32px;">
          ${allTeams.length === 0 ? "No rescue teams registered yet." : "No matching teams found."}
        </div>
      `;
      return;
    }

    const cardsHtml = filtered.map(t => {
      const isExpanded = expandedTeamIds.has(t.team_ref_id);
      const createdDate = AdminCommon.formatDate(t.created_at);
      const createdTime = AdminCommon.formatTime(t.created_at);
      const members = t.members || [];

      let membersContent = "";
      if (members.length === 0) {
        membersContent = `
          <div style="padding: 14px; text-align: center; color: var(--ink-faint); font-size: 12px;">
            No personnel assigned to this team yet.
          </div>
        `;
      } else {
        const memberRows = members.map(m => {
          const roleClass = (m.role_on_team || "").toLowerCase().replace(/\s+/g, "");
          return `
            <tr>
              <td style="width: 100px;"><span class="id-badge">${escapeHtml(m.person_id)}</span></td>
              <td><strong>${escapeHtml(m.full_name)}</strong></td>
              <td><span class="role-badge role-badge-${roleClass}">${escapeHtml(m.role_on_team || 'Member')}</span></td>
              <td style="font-family: var(--font-mono); font-size: 11.5px; color: var(--ink-dim);">${escapeHtml(m.phone || '—')}</td>
              <td class="datetime-cell"><span class="datetime-time">${escapeHtml(AdminCommon.formatDateTime(m.added_at))}</span></td>
            </tr>
          `;
        }).join("");

        membersContent = `
          <table class="team-members-mini-table">
            <thead>
              <tr>
                <th>Person ID</th>
                <th>Staff Member</th>
                <th>Role on Team</th>
                <th>Contact</th>
                <th>Assigned At</th>
              </tr>
            </thead>
            <tbody>
              ${memberRows}
            </tbody>
          </table>
        `;
      }

      return `
        <div class="team-item-card ${isExpanded ? 'is-expanded' : ''}" id="card-${t.team_ref_id}">
          <div class="team-item-header" data-id="${t.team_ref_id}">
            <div class="team-main-info">
              <span class="id-badge">${escapeHtml(t.team_ref_id)}</span>
              <h3 class="team-title">${escapeHtml(t.team_name)}</h3>
              <span class="team-type-chip">${escapeHtml(t.team_type || 'Search & Rescue')}</span>
              ${t.description ? `<span style="font-size: 12px; color: var(--ink-dim); max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">— ${escapeHtml(t.description)}</span>` : ''}
            </div>
            <div class="team-meta-info">
              <span class="team-member-count-pill">
                <span>👥</span> <span>${t.member_count || members.length} members</span>
              </span>
              <div class="datetime-cell" style="text-align: right;">
                <div class="datetime-date">${escapeHtml(createdDate)}</div>
                <div class="datetime-time">${escapeHtml(createdTime)}</div>
              </div>
              <span class="team-expand-arrow">▼</span>
            </div>
          </div>
          <div class="team-members-drawer">
            <div class="team-drawer-title">Assigned Rescue Personnel (${members.length})</div>
            ${membersContent}
          </div>
        </div>
      `;
    }).join("");

    teamsCardsList.innerHTML = cardsHtml;

    // Wire accordion toggling
    teamsCardsList.querySelectorAll(".team-item-header").forEach(header => {
      header.addEventListener("click", () => {
        const id = header.dataset.id;
        if (expandedTeamIds.has(id)) {
          expandedTeamIds.delete(id);
        } else {
          expandedTeamIds.add(id);
        }
        const card = document.getElementById(`card-${id}`);
        if (card) {
          card.classList.toggle("is-expanded", expandedTeamIds.has(id));
        }
      });
    });
  }

  if (teamsSearchInput) {
    teamsSearchInput.addEventListener("input", renderCards);
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
  loadTeamsLedger();
})();
