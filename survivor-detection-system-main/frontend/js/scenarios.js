/* ==========================================================================
   RIDGEWATCH Scenarios page client
   Lists every available disaster template from GET /scenarios (public, no
   login needed - same pattern as Dashboard/Hardware) and lets the user
   start one via POST /scenario/start, then jumps to the Dashboard to watch
   it run. Self-contained page script, same convention as watch.js/commander.js.
   ========================================================================== */

(() => {
  "use strict";

  const apiBase = RidgeWatchConfig.getApiBase();

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str == null ? "" : str;
    return d.innerHTML;
  }

  async function load() {
    const tbody = document.getElementById("scenariosTableBody");
    try {
      const res = await fetch(`${apiBase}/scenarios`).then(r => r.json());
      const allScenarios = res.scenarios || [];
      const scenarios = allScenarios.filter(s => (s.status || "Active").toLowerCase() === "active");

      if (scenarios.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty-note">No active scenarios available.</td></tr>`;
        return;
      }

      tbody.innerHTML = scenarios.map(s => `
        <tr>
          <td>${escapeHtml(s.name)}</td>
          <td>${escapeHtml(s.site_label || "—")}</td>
          <td>${s.victim_count ?? "—"}</td>
          <td>${escapeHtml(s.hazard_type || "—")}</td>
          <td><button data-scenario-id="${escapeHtml(s.scenario_id)}" class="start-scenario-btn">▶ Start</button></td>
        </tr>
      `).join("");

      document.querySelectorAll(".start-scenario-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          btn.disabled = true;
          btn.textContent = "Starting…";
          try {
            await fetch(`${apiBase}/scenario/start`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ scenario: btn.dataset.scenarioId }),
            });
            window.location.href = "index.html";   // jump to Dashboard to watch it run
          } catch (e) {
            btn.disabled = false;
            btn.textContent = "▶ Start";
          }
        });
      });
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-note">Could not reach ${escapeHtml(apiBase)}. Confirm the backend is running.</td></tr>`;
    }
  }

  load();
})();
