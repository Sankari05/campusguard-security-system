/* ==========================================================================
   RIDGEWATCH Testing Module — Unified Add Person Controller
   Direct access to add Victims (Medical Needy) or Staff (Rescue Members).
   ========================================================================== */

(() => {
  "use strict";

  const addPersonForm = document.getElementById("addPersonForm");
  const addPersonMsg = document.getElementById("addPersonMsg");
  const savePersonBtn = document.getElementById("savePersonBtn");
  const saveBtnText = document.getElementById("saveBtnText");
  const formCardTitle = document.getElementById("formCardTitle");
  const formCardSubtitle = document.getElementById("formCardSubtitle");

  const personTypeVictim = document.getElementById("personTypeVictim");
  const personTypeStaff = document.getElementById("personTypeStaff");
  const optVictimLabel = document.getElementById("optVictimLabel");
  const optStaffLabel = document.getElementById("optStaffLabel");

  const victimFieldsGroup = document.getElementById("victimFieldsGroup");
  const staffFieldsGroup = document.getElementById("staffFieldsGroup");

  const personFullName = document.getElementById("personFullName");
  const nameFieldText = document.getElementById("nameFieldText");
  const nameFieldHint = document.getElementById("nameFieldHint");

  // Victim inputs
  const victimStatus = document.getElementById("victimStatus");
  const victimBurialDepth = document.getElementById("victimBurialDepth");
  const victimLat = document.getElementById("victimLat");
  const victimLon = document.getElementById("victimLon");
  const victimAlt = document.getElementById("victimAlt");
  const victimConsciousness = document.getElementById("victimConsciousness");
  const victimMobility = document.getElementById("victimMobility");
  const victimAge = document.getElementById("victimAge");
  const victimGender = document.getElementById("victimGender");
  const victimInjuryNotes = document.getElementById("victimInjuryNotes");

  // Staff inputs
  const personRole = document.getElementById("personRole");
  const personBadge = document.getElementById("personBadge");
  const personPhone = document.getElementById("personPhone");
  const personEmail = document.getElementById("personEmail");
  const personDob = document.getElementById("personDob");
  const personGender = document.getElementById("personGender");
  const personStatus = document.getElementById("personStatus");
  const personAddress = document.getElementById("personAddress");

  function showMessage(el, text, isError = false) {
    if (!el) return;
    el.className = isError ? "admin-msg-box is-error" : "admin-msg-box is-success";
    el.innerHTML = isError ? `<span>⚠️</span> <span>${text}</span>` : `<span>✅</span> <span>${text}</span>`;
    el.style.display = "flex";
  }

  // ------------------------------------------------------------------ //
  // Inline recovery: no scenario running yet
  // Rather than dead-ending the user on a 400 with no next step, offer a
  // one-click way to start the default scenario without leaving the page.
  // ------------------------------------------------------------------ //

  function isNoScenarioError(message) {
    return typeof message === "string" && /scenario is not running/i.test(message);
  }

  function showNoScenarioRecovery(el, onStarted) {
    if (!el) return;
    el.className = "admin-msg-box is-error";
    el.innerHTML = `
      <span>⚠️</span>
      <span style="display:flex; flex-direction:column; gap:8px; align-items:flex-start;">
        <span>No scenario is running yet, so there's nothing to add this person to.</span>
        <button type="button" id="quickStartScenarioBtn" class="btn btn-secondary" style="padding:6px 12px;">
          ▶️ Start Default Scenario Now
        </button>
      </span>
    `;
    el.style.display = "flex";

    const btn = document.getElementById("quickStartScenarioBtn");
    if (btn) {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Starting…";
        try {
          await TestingCommon.testingFetch("/scenario/start", {
            method: "POST",
            body: JSON.stringify({}),
          });
          showMessage(el, "Scenario started. Retrying your submission…");
          if (typeof onStarted === "function") await onStarted();
        } catch (startErr) {
          showMessage(el, `Could not start a scenario: ${startErr.message}`, true);
        }
      });
    }
  }

  // ------------------------------------------------------------------ //
  // Toggle workflow view (Victim vs Staff)
  // ------------------------------------------------------------------ //

  function updateWorkflowView() {
    const isVictim = personTypeVictim.checked;

    if (isVictim) {
      optVictimLabel.classList.add("is-selected");
      optStaffLabel.classList.remove("is-selected");
      victimFieldsGroup.style.display = "block";
      staffFieldsGroup.style.display = "none";

      formCardTitle.textContent = "🏥 Add Medical Needy Person (Victim)";
      formCardSubtitle.textContent = "Register a survivor into live AI multi-sensor triage, sensor simulator, and rescue priority queue.";
      nameFieldText.textContent = "Full Name / Victim Label";
      personFullName.placeholder = "e.g. Priya Sharma or Victim-North-Debris";
      nameFieldHint.textContent = "Identifier used for sensor tracking and priority queue display";
      saveBtnText.textContent = "Add Medical Needy Person";

      // Toggle required attributes
      victimLat.required = true;
      victimLon.required = true;
      victimStatus.required = true;
      personRole.required = false;
    } else {
      optStaffLabel.classList.add("is-selected");
      optVictimLabel.classList.remove("is-selected");
      victimFieldsGroup.style.display = "none";
      staffFieldsGroup.style.display = "block";

      formCardTitle.textContent = "👥 Add Rescue Team Personnel (Staff)";
      formCardSubtitle.textContent = "Register a qualified rescue team staff member into the organization ledger and active unassigned pool.";
      nameFieldText.textContent = "Full Name";
      personFullName.placeholder = "e.g. Ravi Kumar";
      nameFieldHint.textContent = "Official name of the rescue specialist for the personnel ledger";
      saveBtnText.textContent = "Register Rescue Staff";

      // Toggle required attributes
      victimLat.required = false;
      victimLon.required = false;
      victimStatus.required = false;
      personRole.required = true;
    }

    if (addPersonMsg) addPersonMsg.style.display = "none";
  }

  if (personTypeVictim && personTypeStaff) {
    personTypeVictim.addEventListener("change", updateWorkflowView);
    personTypeStaff.addEventListener("change", updateWorkflowView);
  }

  // Pre-fill coordinate defaults from active scenario if available
  async function prefillActiveOrigin() {
    try {
      const data = await TestingCommon.testingFetch("/commander/overview");
      if (data && data.scenario && data.scenario.site_origin) {
        const origin = data.scenario.site_origin;
        if (!victimLat.value) victimLat.value = (origin.latitude + (Math.random() * 0.0006 - 0.0003)).toFixed(5);
        if (!victimLon.value) victimLon.value = (origin.longitude + (Math.random() * 0.0006 - 0.0003)).toFixed(5);
        if (!victimAlt.value && origin.altitude_m) victimAlt.value = Math.round(origin.altitude_m);
      }
    } catch (e) {
      // Default fallback coordinates if no scenario running
      if (!victimLat.value) victimLat.value = "32.37420";
      if (!victimLon.value) victimLon.value = "77.24930";
      if (!victimAlt.value) victimAlt.value = "3950";
    }
  }

  // ------------------------------------------------------------------ //
  // Form submission handler
  // ------------------------------------------------------------------ //

  // Extracted so the "start scenario" recovery button can retry the exact
  // same submission after fixing the underlying "no scenario running" cause.
  async function submitVictim(fullName) {
    const lat = parseFloat(victimLat.value);
    const lon = parseFloat(victimLon.value);
    const alt = victimAlt.value ? parseFloat(victimAlt.value) : null;
    const burialDepth = victimBurialDepth.value ? parseFloat(victimBurialDepth.value) : null;
    const status = victimStatus.value;
    const consciousness = victimConsciousness.value;
    const mobility = victimMobility.value;
    const age = victimAge.value ? parseInt(victimAge.value, 10) : null;
    const gender = victimGender.value || null;
    const injuryNotes = victimInjuryNotes.value.trim() || null;

    if (isNaN(lat) || isNaN(lon)) {
      throw new Error("Please enter valid numeric coordinates for Latitude and Longitude.");
    }

    const payload = {
      label: fullName,
      status,
      latitude: lat,
      longitude: lon,
      altitude_m: alt,
      burial_depth_m: burialDepth,
      consciousness,
      mobility,
      injury_notes: injuryNotes,
      age,
      gender,
    };

    const res = await TestingCommon.testingFetch("/admin/victims/add", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    showMessage(
      addPersonMsg,
      `Victim ${res.victim_id} (${fullName}) added to live operation! View it on the <a href="victims.html" style="color: var(--accent-ice); font-weight: 600; text-decoration: underline;">Live Victims</a> page, Dashboard, Commander, or Hardware. (It will not appear on the Persons ledger — that tracks Rescue Staff only.)`
    );

    addPersonForm.reset();
    personTypeVictim.checked = true;
    updateWorkflowView();
    prefillActiveOrigin();
  }

  if (addPersonForm) {
    addPersonForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const fullName = personFullName.value.trim();
      if (!fullName) {
        showMessage(addPersonMsg, "Please provide a valid Full Name or Label.", true);
        return;
      }

      const isVictim = personTypeVictim.checked;

      savePersonBtn.disabled = true;
      savePersonBtn.innerHTML = `<span>⏳</span> <span>Saving…</span>`;

      try {
        if (isVictim) {
          // --- VICTIM FLOW ---
          try {
            await submitVictim(fullName);
          } catch (victimErr) {
            if (isNoScenarioError(victimErr.message)) {
              showNoScenarioRecovery(addPersonMsg, () => submitVictim(fullName));
            } else {
              throw victimErr;
            }
          }

        } else {
          // --- STAFF FLOW ---
          const role = personRole.value;
          const badgeId = personBadge.value.trim() || null;
          const phone = personPhone.value.trim() || null;
          const email = personEmail.value.trim() || null;
          const dob = personDob.value || null;
          const gender = personGender.value || null;
          const status = personStatus.value || "Active";
          const address = personAddress.value.trim() || null;

          if (!role) {
            throw new Error("Please select an Assigned Role for staff personnel.");
          }

          const personnelPayload = {
            full_name: fullName,
            role,
            badge_id: badgeId,
            phone,
            email,
            dob,
            gender,
            status,
            address,
          };

          // 1. Write to persistent SQLite personnel table
          const regRes = await TestingCommon.testingFetch("/admin/personnel/add", {
            method: "POST",
            body: JSON.stringify(personnelPayload),
          });

          const personId = regRes.person_id;

          // 2. Link into live scenario state as unassigned team member
          let liveLinked = false;
          try {
            await TestingCommon.testingFetch("/admin/team-members/add-unassigned", {
              method: "POST",
              body: JSON.stringify({
                person_id: personId,
                full_name: fullName,
                role,
                badge_id: badgeId,
                phone,
                email,
                dob,
                gender,
                status,
                address,
              }),
            });
            liveLinked = true;
          } catch (liveErr) {
            // Graceful non-failure if scenario not running
            liveLinked = false;
          }

          if (liveLinked) {
            showMessage(
              addPersonMsg,
              `Personnel ${personId} (${fullName}) registered & added to live operation (Unassigned Pool) — visible on Dashboard, Commander, and Hardware now!`
            );
          } else {
            showMessage(
              addPersonMsg,
              `Personnel ${personId} (${fullName}) saved to organization roster ledger. (No active operation running — will appear in live pool once a scenario is started).`
            );
          }

          addPersonForm.reset();
          personTypeStaff.checked = true;
          updateWorkflowView();
        }

      } catch (err) {
        showMessage(addPersonMsg, err.message, true);
      } finally {
        savePersonBtn.disabled = false;
        savePersonBtn.innerHTML = `<span>💾</span> <span id="saveBtnText">${isVictim ? 'Add Medical Needy Person' : 'Register Rescue Staff'}</span>`;
      }
    });
  }

  // Initialize view and prefill coordinates
  updateWorkflowView();
  prefillActiveOrigin();

})();
