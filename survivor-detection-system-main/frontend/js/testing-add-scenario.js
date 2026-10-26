/* ==========================================================================
   RIDGEWATCH Testing Module — Add Scenario Controller
   ========================================================================== */

(() => {
  "use strict";

  const createScenarioForm = document.getElementById("createScenarioForm");
  const createScenarioMsg = document.getElementById("createScenarioMsg");
  const createScenarioBtn = document.getElementById("createScenarioBtn");

  function showMessage(el, text, isError = false) {
    if (!el) return;
    el.className = isError ? "admin-msg-box is-error" : "admin-msg-box is-success";
    el.innerHTML = isError ? `<span>⚠️</span> <span>${text}</span>` : `<span>✅</span> <span>${text}</span>`;
    el.style.display = "flex";
  }

  if (createScenarioForm) {
    createScenarioForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const scenarioName = document.getElementById("scenarioName").value.trim();
      const hazardType = document.getElementById("hazardType").value;
      const victimCount = parseInt(document.getElementById("victimCount").value, 10);
      const lat = parseFloat(document.getElementById("siteLat").value);
      const lng = parseFloat(document.getElementById("siteLng").value);
      const altRaw = document.getElementById("siteAlt").value;
      const altitude = altRaw === "" ? null : parseFloat(altRaw);
      const seedRaw = document.getElementById("scenarioSeed").value.trim();
      const seed = seedRaw === "" ? null : parseInt(seedRaw, 10);
      const enableDegradation = document.getElementById("enableDegradation").checked;

      if (!scenarioName || !hazardType || isNaN(victimCount) || isNaN(lat) || isNaN(lng)) {
        showMessage(createScenarioMsg, "Please fill in all required fields (*).", true);
        return;
      }

      createScenarioBtn.disabled = true;
      createScenarioBtn.innerHTML = `<span>⏳</span> <span>Initializing Scenario…</span>`;

      try {
        const payload = {
          scenario_name: scenarioName,
          hazard_type: hazardType,
          victim_count: victimCount,
          latitude: lat,
          longitude: lng,
          altitude_m: altitude,
          seed,
          enable_degradation: enableDegradation,
        };

        const res = await TestingCommon.testingFetch("/admin/scenario/create", {
          method: "POST",
          body: JSON.stringify(payload),
        });

        showMessage(createScenarioMsg, `Scenario "${scenarioName}" (${hazardType}, ${victimCount} victims) initialized and logged! Redirecting to scenarios ledger…`);
        createScenarioForm.reset();

        setTimeout(() => {
          window.location.href = "testing-scenarios.html";
        }, 1100);

      } catch (err) {
        showMessage(createScenarioMsg, err.message, true);
        createScenarioBtn.disabled = false;
        createScenarioBtn.innerHTML = `<span>🌍</span> <span>Create &amp; Start Scenario</span>`;
      }
    });
  }
})();
