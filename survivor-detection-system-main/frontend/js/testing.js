/* ==========================================================================
   RIDGEWATCH Testing Console Controller
   Direct access controller for creation hub & live simulation controls.
   ========================================================================== */

(() => {
  "use strict";

  const apiBase = TestingCommon.apiBase();

  // Metrics DOM
  const statPersonnelCount = document.getElementById("statPersonnelCount");
  const statScenariosCount = document.getElementById("statScenariosCount");
  const statTeamsCount = document.getElementById("statTeamsCount");

  // Live rescue simulation DOM
  const rcCurrentTarget = document.getElementById("rcCurrentTarget");
  const rcDistance = document.getElementById("rcDistance");
  const rcEta = document.getElementById("rcEta");
  const rcMode = document.getElementById("rcMode");
  const rcTargetSelect = document.getElementById("rcTargetSelect");
  const setTargetForm = document.getElementById("setTargetForm");
  const setTargetMsg = document.getElementById("setTargetMsg");
  const rcClearOverrideBtn = document.getElementById("rcClearOverrideBtn");
  const manualMoveForm = document.getElementById("manualMoveForm");
  const manualMoveMsg = document.getElementById("manualMoveMsg");

  // Live injection & roster DOM
  const addVictimForm = document.getElementById("addVictimForm");
  const addVictimMsg = document.getElementById("addVictimMsg");
  const rosterForm = document.getElementById("rosterForm");
  const rosterTeamSelect = document.getElementById("rosterTeamSelect");
  const rosterResult = document.getElementById("rosterResult");

  function showMessage(el, text, isError = false) {
    if (!el) return;
    el.className = isError ? "admin-msg-box is-error" : "admin-msg-box is-success";
    el.innerHTML = isError ? `<span>⚠️</span> <span>${text}</span>` : `<span>✅</span> <span>${text}</span>`;
    el.style.display = "flex";
  }

  function hideMessage(el) {
    if (!el) return;
    el.style.display = "none";
    el.innerHTML = "";
  }

  // ------------------------------------------------------------------ //
  // Load Stats
  // ------------------------------------------------------------------ //

  async function fetchTestingStats() {
    try {
      const [personnelRes, scenariosRes, teamsRes] = await Promise.allSettled([
        TestingCommon.testingFetch("/admin/personnel"),
        TestingCommon.testingFetch("/admin/scenarios"),
        TestingCommon.testingFetch("/admin/teams"),
      ]);

      if (personnelRes.status === "fulfilled" && statPersonnelCount) {
        statPersonnelCount.textContent = (personnelRes.value.personnel || []).length;
      }
      if (scenariosRes.status === "fulfilled" && statScenariosCount) {
        statScenariosCount.textContent = (scenariosRes.value.scenarios || []).length;
      }
      if (teamsRes.status === "fulfilled" && statTeamsCount) {
        statTeamsCount.textContent = (teamsRes.value.teams || []).length;
      }
    } catch (_) {}
  }

  // ------------------------------------------------------------------ //
  // Rescue Team Status Polling (Every 3.5s)
  // ------------------------------------------------------------------ //

  async function pollRescueStatus() {
    try {
      const res = await fetch(`${apiBase}/rescue-team/status`);
      if (!res.ok) return;
      const status = await res.json();
      const sim = status.dispatch_sim || {};

      if (rcCurrentTarget) rcCurrentTarget.textContent = sim.current_target || "—";
      if (rcDistance) {
        rcDistance.textContent = sim.distance_remaining_m != null
          ? (sim.distance_remaining_m >= 1000 ? `${(sim.distance_remaining_m / 1000).toFixed(2)} km` : `${Math.round(sim.distance_remaining_m)} m`)
          : "—";
      }
      if (rcEta) {
        rcEta.textContent = sim.eta_minutes_to_target != null ? `${sim.eta_minutes_to_target.toFixed(1)} min` : "—";
      }
      if (rcMode) {
        rcMode.textContent = sim.manual_override_active ? "🎯 Manual" : "Auto";
      }

      // Populate target dropdown
      if (rcTargetSelect) {
        const remaining = sim.remaining || [];
        const prevValue = rcTargetSelect.value;
        rcTargetSelect.innerHTML = remaining.map(vid => `<option value="${vid}">${vid}</option>`).join("");
        if (remaining.includes(prevValue)) rcTargetSelect.value = prevValue;
      }

      // Populate live team roster select
      if (rosterTeamSelect && status.teams) {
        const teams = status.teams || [];
        const prevRosterVal = rosterTeamSelect.value;
        rosterTeamSelect.innerHTML = teams.map(t => `<option value="${t.team_id}">${t.team_name} (${t.members} members)</option>`).join("");
        if (teams.some(t => t.team_id === prevRosterVal)) rosterTeamSelect.value = prevRosterVal;
      }

    } catch (_) {}
  }

  // ------------------------------------------------------------------ //
  // Rescue Simulation Actions
  // ------------------------------------------------------------------ //

  if (setTargetForm) {
    setTargetForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const victim_id = rcTargetSelect.value;
      if (!victim_id) return;
      try {
        await TestingCommon.testingFetch("/rescue-team/set-target", {
          method: "POST",
          body: JSON.stringify({ victim_id }),
        });
        showMessage(setTargetMsg, `Rescue team redirected to ${victim_id}`);
        pollRescueStatus();
      } catch (err) {
        showMessage(setTargetMsg, err.message, true);
      }
    });
  }

  if (rcClearOverrideBtn) {
    rcClearOverrideBtn.addEventListener("click", async () => {
      try {
        await TestingCommon.testingFetch("/rescue-team/clear-target", {
          method: "POST",
          body: JSON.stringify({}),
        });
        showMessage(setTargetMsg, "Resumed automated prioritization route");
        pollRescueStatus();
      } catch (err) {
        showMessage(setTargetMsg, err.message, true);
      }
    });
  }

  if (manualMoveForm) {
    manualMoveForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const bearing_deg = parseFloat(document.getElementById("rcBearing").value);
      const distance_m = parseFloat(document.getElementById("rcDistanceInput").value);
      try {
        await TestingCommon.testingFetch("/rescue-team/move", {
          method: "POST",
          body: JSON.stringify({ bearing_deg, distance_m }),
        });
        showMessage(manualMoveMsg, `Team moved ${distance_m}m @ ${bearing_deg}° bearing`);
        pollRescueStatus();
      } catch (err) {
        showMessage(manualMoveMsg, err.message, true);
      }
    });
  }

  // ------------------------------------------------------------------ //
  // Live Injection & Roster Handlers
  // ------------------------------------------------------------------ //

  if (addVictimForm) {
    addVictimForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const victim_id = document.getElementById("avVictimId").value.trim();
      const label = document.getElementById("avLabel").value.trim();
      const status = document.getElementById("avStatus").value;
      const latitude = parseFloat(document.getElementById("avLat").value);
      const longitude = parseFloat(document.getElementById("avLng").value);
      const altRaw = document.getElementById("avAlt").value;
      const altitude_m = altRaw === "" ? null : parseFloat(altRaw);

      try {
        await TestingCommon.testingFetch("/admin/victims/add", {
          method: "POST",
          body: JSON.stringify({ victim_id, label, status, latitude, longitude, altitude_m }),
        });
        showMessage(addVictimMsg, `Injected ${victim_id} (${label}) into active scenario!`);
        addVictimForm.reset();
        pollRescueStatus();
      } catch (err) {
        showMessage(addVictimMsg, err.message, true);
      }
    });
  }

  if (rosterForm) {
    rosterForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const teamId = rosterTeamSelect.value;
      const memberCount = parseInt(document.getElementById("rosterMemberCount").value, 10);
      if (!teamId || isNaN(memberCount)) return;

      try {
        const res = await TestingCommon.testingFetch(`/admin/teams/${teamId}/roster`, {
          method: "POST",
          body: JSON.stringify({ member_count: memberCount }),
        });
        showMessage(rosterResult, `${res.team.team_name} updated to ${res.team.members} members (${res.tracked_members.length} tracked live).`);
        pollRescueStatus();
      } catch (err) {
        showMessage(rosterResult, err.message, true);
      }
    });
  }

  // ------------------------------------------------------------------ //
  // Barometric Pressure Testing Handlers
  // ------------------------------------------------------------------ //

  const pressureProfileForm = document.getElementById("pressureProfileForm");
  const pressureProfileSelect = document.getElementById("pressureProfileSelect");
  const pressureProfileMsg = document.getElementById("pressureProfileMsg");
  const manualPressureForm = document.getElementById("manualPressureForm");
  const manualPressureMsg = document.getElementById("manualPressureMsg");

  if (pressureProfileForm) {
    pressureProfileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const profile = pressureProfileSelect.value;
      try {
        await TestingCommon.testingFetch("/sensors/pressure/profile", {
          method: "POST",
          body: JSON.stringify({ profile }),
        });
        showMessage(pressureProfileMsg, `Applied meteorological profile: ${profile}`);
      } catch (err) {
        showMessage(pressureProfileMsg, err.message, true);
      }
    });
  }

  if (manualPressureForm) {
    manualPressureForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const pressure_hpa = parseFloat(document.getElementById("manPressureVal").value);
      const status = document.getElementById("manPressureStatus").value;
      try {
        const res = await TestingCommon.testingFetch("/sensors/pressure/readings", {
          method: "POST",
          body: JSON.stringify({ pressure_hpa, status }),
        });
        showMessage(manualPressureMsg, `Ingested ${pressure_hpa} hPa (Status: ${status}, Trend: ${res.reading.trend})`);
      } catch (err) {
        showMessage(manualPressureMsg, err.message, true);
      }
    });
  }

  // Landslide & Geotechnical Simulation Forms
  const landslideProfileForm = document.getElementById("landslideProfileForm");
  const landslideProfileSelect = document.getElementById("landslideProfileSelect");
  const landslideProfileMsg = document.getElementById("landslideProfileMsg");

  if (landslideProfileForm) {
    landslideProfileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const profile = landslideProfileSelect.value;
      try {
        await TestingCommon.testingFetch("/hazards/landslide/profile", {
          method: "POST",
          body: JSON.stringify({ profile }),
        });
        showMessage(landslideProfileMsg, `Applied landslide profile: ${profile}`);
      } catch (err) {
        showMessage(landslideProfileMsg, err.message, true);
      }
    });
  }

  const manualLandslideForm = document.getElementById("manualLandslideForm");
  const manSoilVal = document.getElementById("manSoilVal");
  const manTiltVal = document.getElementById("manTiltVal");
  const manSlopeNode = document.getElementById("manSlopeNode");
  const manualLandslideMsg = document.getElementById("manualLandslideMsg");

  if (manualLandslideForm) {
    manualLandslideForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const soil_moisture_pct = parseFloat(manSoilVal.value);
      const tilt_angle_deg = parseFloat(manTiltVal.value);
      const node_id = manSlopeNode.value;

      try {
        await TestingCommon.testingFetch("/sensors/soil-moisture/readings", {
          method: "POST",
          body: JSON.stringify({ node_id, soil_moisture_pct }),
        });
        await TestingCommon.testingFetch("/sensors/tilt/readings", {
          method: "POST",
          body: JSON.stringify({ node_id, tilt_angle_deg }),
        });
        showMessage(manualLandslideMsg, `Ingested ${node_id}: Moisture ${soil_moisture_pct}%, Tilt ${tilt_angle_deg}°`);
      } catch (err) {
        showMessage(manualLandslideMsg, err.message, true);
      }
    });
  }

  // Optical Camera Simulation Handlers
  const cameraProfileForm = document.getElementById("cameraProfileForm");
  const cameraProfileSelect = document.getElementById("cameraProfileSelect");
  const cameraProfileMsg = document.getElementById("cameraProfileMsg");
  const manualCameraForm = document.getElementById("manualCameraForm");
  const manualCameraMsg = document.getElementById("manualCameraMsg");

  if (cameraProfileForm) {
    cameraProfileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const profile = cameraProfileSelect.value;
      try {
        await TestingCommon.testingFetch("/sensors/camera/simulate", {
          method: "POST",
          body: JSON.stringify({ profile }),
        });
        showMessage(cameraProfileMsg, `Applied optical camera profile: ${profile}`);
      } catch (err) {
        showMessage(cameraProfileMsg, err.message, true);
      }
    });
  }

  if (manualCameraForm) {
    manualCameraForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const confidence = parseFloat(document.getElementById("manCamConfidence").value);
      const person_count = parseInt(document.getElementById("manCamPersons").value, 10);
      const detection_state = document.getElementById("manCamState").value;
      try {
        await TestingCommon.testingFetch("/sensors/camera/readings", {
          method: "POST",
          body: JSON.stringify({ confidence, person_count, detection_state }),
        });
        showMessage(manualCameraMsg, `Ingested Camera: ${detection_state} (${Math.round(confidence * 100)}% conf, ${person_count} persons)`);
      } catch (err) {
        showMessage(manualCameraMsg, err.message, true);
      }
    });
  }

  // Thermal Infrared Simulation Handlers
  const thermalProfileForm = document.getElementById("thermalProfileForm");
  const thermalProfileSelect = document.getElementById("thermalProfileSelect");
  const thermalProfileMsg = document.getElementById("thermalProfileMsg");
  const manualThermalForm = document.getElementById("manualThermalForm");
  const manualThermalMsg = document.getElementById("manualThermalMsg");

  if (thermalProfileForm) {
    thermalProfileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const profile = thermalProfileSelect.value;
      try {
        await TestingCommon.testingFetch("/sensors/thermal/simulate", {
          method: "POST",
          body: JSON.stringify({ profile }),
        });
        showMessage(thermalProfileMsg, `Applied thermal infrared profile: ${profile}`);
      } catch (err) {
        showMessage(thermalProfileMsg, err.message, true);
      }
    });
  }

  if (manualThermalForm) {
    manualThermalForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const estimated_temperature = parseFloat(document.getElementById("manThmTemp").value);
      const thermal_confidence = parseFloat(document.getElementById("manThmConf").value);
      const detection_type = document.getElementById("manThmType").value;
      try {
        await TestingCommon.testingFetch("/sensors/thermal/readings", {
          method: "POST",
          body: JSON.stringify({ estimated_temperature, thermal_confidence, detection_type }),
        });
        showMessage(manualThermalMsg, `Ingested Thermal: ${detection_type} (${estimated_temperature}°C, ${Math.round(thermal_confidence * 100)}% conf)`);
      } catch (err) {
        showMessage(manualThermalMsg, err.message, true);
      }
    });
  }

  // Rainfall Simulation Handlers
  const rainfallProfileForm = document.getElementById("rainfallProfileForm");
  const rainfallProfileSelect = document.getElementById("rainfallProfileSelect");
  const rainfallProfileMsg = document.getElementById("rainfallProfileMsg");
  const manualRainfallForm = document.getElementById("manualRainfallForm");
  const manualRainfallMsg = document.getElementById("manualRainfallMsg");

  if (rainfallProfileForm) {
    rainfallProfileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const profile = rainfallProfileSelect.value;
      try {
        await TestingCommon.testingFetch("/sensors/rainfall/simulate", {
          method: "POST",
          body: JSON.stringify({ profile }),
        });
        showMessage(rainfallProfileMsg, `Applied rainfall simulation profile: ${profile}`);
      } catch (err) {
        showMessage(rainfallProfileMsg, err.message, true);
      }
    });
  }

  if (manualRainfallForm) {
    manualRainfallForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const rainfall_rate_mm_h = parseFloat(document.getElementById("manRainRate").value);
      const cumulative_rainfall_mm = parseFloat(document.getElementById("manRainCumul").value);
      const classification = document.getElementById("manRainClass").value;
      try {
        await TestingCommon.testingFetch("/sensors/rainfall/readings", {
          method: "POST",
          body: JSON.stringify({
            rainfall_rate_mm_h,
            cumulative_rainfall_mm,
            classification,
            unit: "mm/h",
          }),
        });
        showMessage(manualRainfallMsg, `Ingested Rainfall: ${classification} (${rainfall_rate_mm_h} mm/h, ${cumulative_rainfall_mm} mm cumulative)`);
      } catch (err) {
        showMessage(manualRainfallMsg, err.message, true);
      }
    });
  }

  // Temperature & Humidity Profile and Ingestion Handlers
  const tempProfileForm = document.getElementById("tempProfileForm");
  const tempProfileSelect = document.getElementById("tempProfileSelect");
  const tempProfileMsg = document.getElementById("tempProfileMsg");

  if (tempProfileForm) {
    tempProfileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const profile = tempProfileSelect.value;
      try {
        await TestingCommon.testingFetch("/sensors/temperature/simulate", {
          method: "POST",
          body: JSON.stringify({ profile }),
        });
        showMessage(tempProfileMsg, `Applied temperature profile: ${profile}`);
      } catch (err) {
        showMessage(tempProfileMsg, err.message, true);
      }
    });
  }

  const humidProfileForm = document.getElementById("humidProfileForm");
  const humidProfileSelect = document.getElementById("humidProfileSelect");
  const humidProfileMsg = document.getElementById("humidProfileMsg");

  if (humidProfileForm) {
    humidProfileForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const profile = humidProfileSelect.value;
      try {
        await TestingCommon.testingFetch("/sensors/humidity/simulate", {
          method: "POST",
          body: JSON.stringify({ profile }),
        });
        showMessage(humidProfileMsg, `Applied humidity profile: ${profile}`);
      } catch (err) {
        showMessage(humidProfileMsg, err.message, true);
      }
    });
  }

  const manualTempHumidForm = document.getElementById("manualTempHumidForm");
  const manualTempHumidMsg = document.getElementById("manualTempHumidMsg");

  if (manualTempHumidForm) {
    manualTempHumidForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const temp_c = parseFloat(document.getElementById("manTempC").value);
      const humid_pct = parseFloat(document.getElementById("manHumidPct").value);
      try {
        await Promise.all([
          TestingCommon.testingFetch("/sensors/temperature/readings", {
            method: "POST",
            body: JSON.stringify({
              temperature_c: temp_c,
              ambient_temp_c: temp_c,
              unit: "°C",
            }),
          }),
          TestingCommon.testingFetch("/sensors/humidity/readings", {
            method: "POST",
            body: JSON.stringify({
              humidity_pct: humid_pct,
              unit: "%",
            }),
          })
        ]);
        showMessage(manualTempHumidMsg, `Ingested Temp: ${temp_c}°C, Humidity: ${humid_pct}%`);
      } catch (err) {
        showMessage(manualTempHumidMsg, err.message, true);
      }
    });
  }

  // Initialize
  fetchTestingStats();
  pollRescueStatus();
  setInterval(pollRescueStatus, 3500);
})();
