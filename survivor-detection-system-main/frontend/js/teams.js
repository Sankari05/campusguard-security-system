/* ==========================================================================
   RIDGEWATCH Rescue Teams page client
   Polls GET /rescue-team/members-status (public, no login needed - Step 27)
   every 4s: renders a summary card per team plus a full member roster table
   with full_name/role (Step 29). Self-contained page script, same convention
   as watch.js/commander.js.
   ========================================================================== */

(() => {
  "use strict";

  const apiBase = RidgeWatchConfig.getApiBase();

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str == null ? "" : str;
    return d.innerHTML;
  }

  async function poll() {
    const cardRow = document.getElementById("teamsCardRow");
    const tbody = document.getElementById("membersTableBody");
    try {
      const res = await fetch(`${apiBase}/rescue-team/members-status`).then(r => r.json());
      const members = res.members || [];

      if (members.length === 0) {
        cardRow.innerHTML = `<p class="empty-note">No tracked team members yet.</p>`;
        tbody.innerHTML = `<tr><td colspan="6" class="empty-note">No tracked team members yet.</td></tr>`;
      } else {
        const byTeam = {};
        for (const m of members) (byTeam[m.team_id] ??= []).push(m);

        cardRow.innerHTML = Object.entries(byTeam).map(([teamId, ms]) => `
          <div class="team-card">
            <div class="team-card-name">${escapeHtml(teamId)}</div>
            <div class="team-card-count">${ms.length} tracked</div>
          </div>`).join("");

        tbody.innerHTML = members.map(m => `
          <tr>
            <td>${escapeHtml(m.full_name || "—")}</td>
            <td>${(m.role && m.role.toLowerCase().includes("leader")) ? `⭐ ${escapeHtml(m.role)}` : escapeHtml(m.role || "Rescuer")}</td>
            <td>${escapeHtml(m.callsign)}</td>
            <td>${escapeHtml(m.team_id)}</td>
            <td><span class="status-pill status-pill-${escapeHtml(m.status)} tm-status-${escapeHtml(m.status)}">${escapeHtml((m.status || "").toUpperCase())}</span></td>
            <td>${escapeHtml(m.assigned_victim_id || "—")}</td>
          </tr>`).join("");
      }
    } catch (e) {
      // scenario not running yet, or backend unreachable - leave stale content
    }
    setTimeout(poll, 4000);
  }

  poll();
})();
