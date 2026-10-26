/* ==========================================================================
   RIDGEWATCH Add Person Controller
   ========================================================================== */

(() => {
  "use strict";

  const addPersonForm = document.getElementById("addPersonForm");
  const addPersonMsg = document.getElementById("addPersonMsg");
  const savePersonBtn = document.getElementById("savePersonBtn");

  function showMessage(el, text, isError = false) {
    if (!el) return;
    el.className = isError ? "admin-msg-box is-error" : "admin-msg-box is-success";
    el.innerHTML = isError ? `<span>⚠️</span> <span>${text}</span>` : `<span>✅</span> <span>${text}</span>`;
    el.style.display = "flex";
  }

  if (addPersonForm) {
    addPersonForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const fullName = document.getElementById("personFullName").value.trim();
      const role = document.getElementById("personRole").value;
      const badgeId = document.getElementById("personBadge").value.trim() || null;
      const phone = document.getElementById("personPhone").value.trim() || null;
      const email = document.getElementById("personEmail").value.trim() || null;
      const dob = document.getElementById("personDob").value || null;
      const gender = document.getElementById("personGender").value || null;
      const status = document.getElementById("personStatus").value || "Active";
      const address = document.getElementById("personAddress").value.trim() || null;

      if (!fullName || !role) {
        showMessage(addPersonMsg, "Please fill in all required fields (*).", true);
        return;
      }

      savePersonBtn.disabled = true;
      savePersonBtn.innerHTML = `<span>⏳</span> <span>Saving…</span>`;

      try {
        const payload = {
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

        const res = await AdminCommon.adminFetch("/admin/personnel/add", {
          method: "POST",
          body: JSON.stringify(payload),
        });

        showMessage(addPersonMsg, `Personnel ${res.person_id} (${fullName}) registered successfully! Redirecting to ledger…`);
        addPersonForm.reset();

        setTimeout(() => {
          window.location.href = "admin-persons.html";
        }, 1200);

      } catch (err) {
        showMessage(addPersonMsg, err.message, true);
        savePersonBtn.disabled = false;
        savePersonBtn.innerHTML = `<span>💾</span> <span>Save Person</span>`;
      }
    });
  }
})();
