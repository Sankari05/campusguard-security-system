/* ==========================================================================
   RIDGEWATCH Victims page client
   Polls GET /victims (public, no login needed) every 4s and renders a
   Risk/Location/Distance-to-nearest-team-member/Status table. Self-contained
   page script, same convention as watch.js/commander.js.
   ========================================================================== */

(() => {
  "use strict";

  const apiBase = RidgeWatchConfig.getApiBase();

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str == null ? "" : str;
    return d.innerHTML;
  }

  function formatDistance(dist) {
    if (dist == null) return "—";
    return dist >= 1000 ? `${(dist / 1000).toFixed(2)} km` : `${Math.round(dist)} m`;
  }

  async function poll() {
    const tbody = document.getElementById("victimsTableBody");
    try {
      const res = await fetch(`${apiBase}/victims`).then(r => r.json());
      const victims = res.victims || [];

      if (victims.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty-note">No victims in the running scenario.</td></tr>`;
      } else {
        tbody.innerHTML = victims.map(v => {
          const triage = v.fusion?.triage_class || "—";
          const distText = formatDistance(v.nearest_team_member_distance_m);
          return `
            <tr class="is-clickable" data-victim-id="${escapeHtml(v.victim_id)}">
              <td>${escapeHtml(v.victim_id)}</td>
              <td><span class="triage-badge triage-${escapeHtml(triage)}">${escapeHtml(triage)}</span></td>
              <td>${v.location.latitude.toFixed(4)}, ${v.location.longitude.toFixed(4)}</td>
              <td>${distText}</td>
              <td>${v.sensor_node_online ? "🟢 online" : "🔴 offline"}</td>
            </tr>`;
        }).join("");
      }
    } catch (e) {
      // scenario not running yet, or backend unreachable - table stays as-is
    }
    setTimeout(poll, 4000);
  }

  // 27b.6 — row-click highlight: clicking a victim row toggles .is-selected.
  // Delegated on the tbody since rows are re-rendered every poll.
  document.getElementById("victimsTableBody")?.addEventListener("click", (e) => {
    const row = e.target.closest("tr.is-clickable");
    if (!row) return;
    const wasSelected = row.classList.contains("is-selected");
    row.parentElement.querySelectorAll("tr.is-selected").forEach((r) => r.classList.remove("is-selected"));
    if (!wasSelected) row.classList.add("is-selected");
  });

  poll();
})();
