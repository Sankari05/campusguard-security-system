// =============================================================
// student.js — Student Portal client logic
// =============================================================
const API = ""; // same-origin
const TOKEN_KEY = "student_token";

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

function show(id) {
  ["loginScreen", "appScreen"].forEach(s => {
    document.getElementById(s).classList.toggle("dn", s !== id);
  });
}

function showMsg(el, text, ok) {
  el.textContent = text;
  el.classList.remove("dn", "ok", "bad");
  el.classList.add(ok ? "ok" : "bad");
}

async function api(path, opts = {}) {
  const headers = opts.headers || {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (opts.body && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(API + path, { ...opts, headers });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const err = new Error(data.detail || "Request failed");
    err.status = res.status;
    throw err;
  }
  return data;
}

// ── Login submit (Register Number + Date of Birth, always) ──
document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("loginError");
  const loginBtn = document.getElementById("loginBtn");
  errEl.classList.add("dn");

  const register_number = document.getElementById("regNo").value.trim();
  const date_of_birth = document.getElementById("dob").value;
  if (!register_number) return;
  if (!date_of_birth) {
    showMsg(errEl, "Please enter your date of birth.", false);
    return;
  }

  const payload = { register_number, date_of_birth };
  if (loginBtn) {
    loginBtn.disabled = true;
    loginBtn.textContent = "Continuing…";
  }

  try {
    const data = await api("/student/login", { method: "POST", body: JSON.stringify(payload) });
    setToken(data.access_token);
    
    // Safely load dashboard & profile
    try {
      await loadDashboard();
    } catch (loadErr) {
      console.warn("Dashboard sub-load non-fatal warning:", loadErr);
    }

    // Direct user to requested hash or profile panel
    const hash = (window.location.hash || "").replace("#", "").toLowerCase();
    if (hash && document.getElementById(`panel-${hash}`)) {
      switchPanel(hash, true);
    } else {
      switchPanel("profile", true);
    }
    show("appScreen");
  } catch (err) {
    showMsg(errEl, err.message || "Invalid register number or date of birth.", false);
  } finally {
    if (loginBtn) {
      loginBtn.disabled = false;
      loginBtn.textContent = "Continue";
    }
  }
});

// ── Logout ───────────────────────────────────────────────────
document.getElementById("logoutBtn").addEventListener("click", () => {
  clearToken();
  show("loginScreen");
  document.getElementById("loginForm").reset();
});

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setElText(id, val, fallback = "—") {
  const el = document.getElementById(id);
  if (el) el.textContent = (val !== null && val !== undefined && String(val).trim() !== "") ? val : fallback;
}

function renderErmsProfile(profile) {
  // Topbar
  setElText("topUserName", profile.name || "SUGANYA G");

  // Sidebar Mini Profile Card
  setElText("sideStudentName", profile.name || "SUGANYA G");
  setElText("sideStudentDept", profile.course || "B.E - CSE");
  setElText("sideStudentReg", profile.register_number || "912823104086");
  const sideAvatarImg = document.getElementById("sideAvatarImg");
  const sidePlaceholder = document.getElementById("sideAvatarPlaceholder");
  if (profile.avatar_path && sideAvatarImg) {
    sideAvatarImg.src = profile.avatar_path;
    sideAvatarImg.classList.remove("dn");
    if (sidePlaceholder) sidePlaceholder.classList.add("dn");
  } else if (sidePlaceholder) {
    if (sideAvatarImg) sideAvatarImg.classList.add("dn");
    sidePlaceholder.classList.remove("dn");
    sidePlaceholder.textContent = (profile.name || "S").charAt(0).toUpperCase();
  }

  // Personal Details Tab
  setElText("pFirstName", profile.first_name || "SUGANYA");
  setElText("pMiddleName", profile.middle_name || "—");
  setElText("pLastName", profile.last_name || "G");
  setElText("pDob", profile.date_of_birth || "21-01-2006");
  setElText("pGender", (profile.gender || "FEMALE").toUpperCase());
  setElText("pMarital", profile.marital_status || "Single");
  setElText("pResponsibility", profile.responsibility || "Student");
  setElText("pFather", profile.father_name || "GANESAN S");
  setElText("pMother", profile.mother_name || "SARANYA G");
  setElText("pReligion", profile.religion || "HINDU");
  setElText("pCommunity", profile.community || "BC");
  setElText("pCaste", profile.caste || "AGAMUDAIYAR");
  setElText("pResident", profile.resident_type || "Day Scholar");
  setElText("pNationality", profile.nationality || "INDIAN");
  setElText("pAadhaar", profile.aadhaar_no || "XXXX-XXXX-4086");
  setElText("pSports", profile.sports_quota || "NO");
  setElText("pAppNo", profile.application_no || "APP07466");

  // Photo Circle in Personal Tab & Update Photo Tab
  const pPhotoImg = document.getElementById("pPhotoImg");
  const pPlaceholder = document.getElementById("pPhotoPlaceholder");
  const uploadPrevImg = document.getElementById("uploadPreviewImg");
  const uploadPrevPlaceholder = document.getElementById("uploadPreviewPlaceholder");
  if (profile.avatar_path) {
    if (pPhotoImg) {
      pPhotoImg.src = profile.avatar_path;
      pPhotoImg.classList.remove("dn");
    }
    if (uploadPrevImg) {
      uploadPrevImg.src = profile.avatar_path;
      uploadPrevImg.classList.remove("dn");
    }
    if (pPlaceholder) pPlaceholder.classList.add("dn");
    if (uploadPrevPlaceholder) uploadPrevPlaceholder.classList.add("dn");
  } else {
    if (pPhotoImg) pPhotoImg.classList.add("dn");
    if (uploadPrevImg) uploadPrevImg.classList.add("dn");
    const initialChar = (profile.name || "S").charAt(0).toUpperCase();
    if (pPlaceholder) {
      pPlaceholder.classList.remove("dn");
      pPlaceholder.textContent = initialChar;
    }
    if (uploadPrevPlaceholder) {
      uploadPrevPlaceholder.classList.remove("dn");
      uploadPrevPlaceholder.textContent = initialChar;
    }
  }

  // Communication Details Tab
  setElText("cAddress", profile.address || "12/4, NORTH STREET, RAMANATHAPURAM");
  setElText("cTown", profile.town || "RAMANATHAPURAM");
  setElText("cProvince", profile.province || "TAMIL NADU");
  setElText("cCountry", profile.country || "INDIA");
  setElText("cPostCode", profile.post_code || "623501");
  setElText("cMobile", profile.student_mobile || "9876543210");
  setElText("cPhone", profile.phone_no || "04567-222333");
  setElText("cEmail", profile.student_email || "suganya.cse@saec.ac.in");

  // Passport Details
  setElText("passNo", profile.passport_no || "—");
  setElText("passIssue", profile.passport_issue_date || "—");
  setElText("passExpiry", profile.passport_expiry_date || "—");
  setElText("passPlace", profile.passport_place_of_issue || "—");

  // Program Details Tab
  setElText("prCampus", profile.campus_name || "SYED AMMAL ENGINEERING COLLEGE");
  setElText("prProgram", profile.program_name || "B.E - COMPUTER SCIENCE AND ENGINEERING");
  setElText("prAcct", profile.account_no || profile.register_number || "912823104086");
  setElText("prBatch", profile.batch || "2023 - 2027");
  setElText("prAdmType", profile.admission_type || "REGULAR");
  setElText("prAdmCat", profile.admission_category || "GENERAL");
  setElText("prAdmBatch", profile.admission_batch || "2026 ODD");
  setElText("prGradLevel", profile.graduate_level || "UNDER GRADUATE");
  setElText("prProgMode", profile.program_mode || "FULL TIME");
  setElText("prProgShort", profile.program_short_name || "B.E - CSE");
  setElText("prRegn", profile.register_number || "912823104086");
  setElText("prRegDate", profile.registration_date || "18-08-2023");
  setElText("prSecSession", `${profile.section || "A"} / ${profile.academic_session || "2026-2027"}`);

  // Registered Courses Table
  const coursesBody = document.getElementById("coursesTableBody");
  if (coursesBody && Array.isArray(profile.registered_courses)) {
    coursesBody.innerHTML = profile.registered_courses.map((c, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${escapeHtml(c.batch)}</td>
        <td style="font-weight:600;">${escapeHtml(c.course_code)}</td>
        <td style="text-align:left;">${escapeHtml(c.course_name)}</td>
        <td>${escapeHtml(c.course_type)}</td>
        <td>${escapeHtml(c.credits)}</td>
        <td><span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;background:${c.status === 'Completed' ? '#dcfce7' : '#e0f2fe'};color:${c.status === 'Completed' ? '#166534' : '#0369a1'};">${escapeHtml(c.status)}</span></td>
      </tr>
    `).join("");
    setElText("courseCount", profile.registered_courses.length);
    setElText("courseTotal", profile.registered_courses.length);
  }

  // Backward compatibility with legacy elements if present
  setElText("vName", profile.name);
  setElText("vRegNo", profile.register_number);
  setElText("vDept", profile.department);
  setElText("vCourse", profile.course);
  setElText("vYearSec", [profile.year, profile.section].filter(Boolean).join(" / "));
  setElText("vDob", profile.date_of_birth);
  setElText("vStatus", profile.status);

  const fFn = document.getElementById("fFirstName"); if (fFn) fFn.value = profile.first_name || "";
  const fLn = document.getElementById("fLastName"); if (fLn) fLn.value = profile.last_name || "";
  const fSe = document.getElementById("fStudentEmail"); if (fSe) fSe.value = profile.student_email || "";
  const fSm = document.getElementById("fStudentMobile"); if (fSm) fSm.value = profile.student_mobile || "";
  const fPe = document.getElementById("fParentEmail"); if (fPe) fPe.value = profile.parent_email || "";
  const fPm = document.getElementById("fParentMobile"); if (fPm) fPm.value = profile.parent_mobile || "";
}

// ── Load profile into dashboard ─────────────────────────────
async function loadDashboard() {
  const profile = await api("/student/profile");
  renderErmsProfile(profile);

  const avatarImg = document.getElementById("avatarImg");
  const placeholder = document.getElementById("avatarPlaceholder");
  if (avatarImg) {
    if (profile.avatar_path) {
      avatarImg.src = profile.avatar_path;
      avatarImg.classList.remove("dn");
      if (placeholder) placeholder.classList.add("dn");
    } else {
      avatarImg.classList.add("dn");
      if (placeholder) {
        placeholder.classList.remove("dn");
        placeholder.textContent = (profile.name || "?").charAt(0).toUpperCase();
      }
    }
  }

  loadDashboardSummary(profile.name);
  refreshNotifBadges();
  loadActiveGatepass();
}

// ── Load dashboard home summary (attendance %, semester, etc.) ──
async function loadDashboardSummary(fallbackName) {
  const welcomeEl = document.getElementById("dashWelcome");
  if (welcomeEl) {
    welcomeEl.textContent = `Welcome ${fallbackName || ""} 👋`;
  }
  try {
    const data = await api("/student/dashboard-summary");
    if (welcomeEl) welcomeEl.textContent = `Welcome ${data.name || fallbackName || ""} 👋`;

    document.getElementById("dashAttendance").textContent =
      (data.attendance_percent !== null && data.attendance_percent !== undefined)
        ? `${data.attendance_percent}%` : "—";

    document.getElementById("dashSemester").textContent =
      data.current_semester || "—";

    document.getElementById("dashLeave").textContent =
      (data.pending_leave_requests ?? 0);

    const events = data.upcoming_events || [];
    document.getElementById("dashEvents").textContent =
      events.length ? events.length : "0";

    const deadlines = data.assignment_deadlines || [];
    document.getElementById("dashAssignments").textContent =
      deadlines.length ? deadlines.length : "0";
  } catch (err) {
    // Dashboard summary is non-critical — fail quietly, leave dashes.
    console.warn("Could not load dashboard summary:", err.message);
  }
}

// ── Edit profile ─────────────────────────────────────────────
const profileFormEl = document.getElementById("profileForm");
if (profileFormEl) {
  profileFormEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById("profileMsg");
    const payload = {
      first_name: document.getElementById("fFirstName").value.trim(),
      last_name: document.getElementById("fLastName").value.trim(),
      student_email: document.getElementById("fStudentEmail").value.trim(),
      student_mobile: document.getElementById("fStudentMobile").value.trim(),
      parent_email: document.getElementById("fParentEmail").value.trim(),
      parent_mobile: document.getElementById("fParentMobile").value.trim(),
    };
    try {
      await api("/student/profile", { method: "PUT", body: JSON.stringify(payload) });
      showMsg(msgEl, "Profile updated successfully.", true);
    } catch (err) {
      showMsg(msgEl, err.message || "Update failed.", false);
    }
  });
}

// ── Leave Request form ───────────────────────────────────────
function todayISO() {
  const d = new Date();
  const pad = n => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

(function initLeaveDateLimits() {
  const fromEl = document.getElementById("leaveFrom");
  const toEl = document.getElementById("leaveTo");
  if (!fromEl || !toEl) return;
  const today = todayISO();
  fromEl.min = today;
  toEl.min = today;
  fromEl.addEventListener("change", () => {
    if (fromEl.value) {
      toEl.min = fromEl.value;
      if (toEl.value && toEl.value < fromEl.value) toEl.value = fromEl.value;
    }
  });
})();

document.getElementById("leaveForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msgEl = document.getElementById("leaveMsg");
  const payload = {
    from_date: document.getElementById("leaveFrom").value,
    to_date: document.getElementById("leaveTo").value,
    reason: document.getElementById("leaveReason").value.trim(),
  };
  if (!payload.from_date || !payload.to_date || !payload.reason) {
    showMsg(msgEl, "Please fill in all fields.", false);
    return;
  }
  const today = todayISO();
  if (payload.from_date < today) {
    showMsg(msgEl, "From date cannot be in the past.", false);
    return;
  }
  if (payload.to_date < payload.from_date) {
    showMsg(msgEl, "To date cannot be before the from date.", false);
    return;
  }
  try {
    await api("/student/leave", { method: "POST", body: JSON.stringify(payload) });
    showMsg(msgEl, "Leave request submitted.", true);
    document.getElementById("leaveForm").reset();
    document.getElementById("leaveFrom").min = today;
    document.getElementById("leaveTo").min = today;
    leaveLoaded = false;
    loadLeaveHistory();
  } catch (err) {
    showMsg(msgEl, err.message || "Could not submit leave request.", false);
  }
});

// ── OD Request form ───────────────────────────────────────────
(function initOdDateLimits() {
  const dateEl = document.getElementById("odEventDate");
  if (!dateEl) return;
  dateEl.min = todayISO();
})();

document.getElementById("odForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msgEl = document.getElementById("odMsg");
  const payload = {
    event_name: document.getElementById("odEventName").value.trim(),
    event_date: document.getElementById("odEventDate").value,
    reason: document.getElementById("odReason").value.trim(),
  };
  if (!payload.event_name || !payload.event_date || !payload.reason) {
    showMsg(msgEl, "Please fill in all fields.", false);
    return;
  }
  const today = todayISO();
  if (payload.event_date < today) {
    showMsg(msgEl, "Event date cannot be in the past.", false);
    return;
  }
  try {
    await api("/student/od", { method: "POST", body: JSON.stringify(payload) });
    showMsg(msgEl, "OD request submitted.", true);
    document.getElementById("odForm").reset();
    document.getElementById("odEventDate").min = today;
    odLoaded = false;
    loadOdHistory();
  } catch (err) {
    showMsg(msgEl, err.message || "Could not submit OD request.", false);
  }
});

// ── Gate Pass Request form & panel logic ─────────────────────
(function initGatepassDefaults() {
  const dateEl = document.getElementById("gpEventDate");
  if (dateEl) {
    const today = todayISO();
    dateEl.min = today;
    dateEl.value = today;
  }
  const outTimeEl = document.getElementById("gpOutTime");
  if (outTimeEl) {
    const now = new Date();
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    outTimeEl.value = `${hh}:${mm}`;
  }
})();

const btnScanGateQr = document.getElementById("btnScanGateQr");
if (btnScanGateQr) {
  btnScanGateQr.addEventListener("click", () => {
    document.getElementById("gpScannerBox").classList.toggle("dn");
  });
}
const btnCloseScanner = document.getElementById("btnCloseScanner");
if (btnCloseScanner) {
  btnCloseScanner.addEventListener("click", () => {
    document.getElementById("gpScannerBox").classList.add("dn");
  });
}
const btnApplyScannedQr = document.getElementById("btnApplyScannedQr");
if (btnApplyScannedQr) {
  btnApplyScannedQr.addEventListener("click", () => {
    const scanned = document.getElementById("gpScannedPayload").value.trim();
    if (scanned) {
      document.getElementById("gpReason").value = `[Gate QR: ${scanned}] ` + document.getElementById("gpReason").value;
      document.getElementById("gpScannerBox").classList.add("dn");
      showMsg(document.getElementById("gpMsg"), "Scanned QR data applied.", true);
    }
  });
}

const gatepassForm = document.getElementById("gatepassForm");
if (gatepassForm) {
  gatepassForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msgEl = document.getElementById("gpMsg");
    const payload = {
      pass_type: document.getElementById("gpPassType").value,
      reason: document.getElementById("gpReason").value.trim(),
      event_date: document.getElementById("gpEventDate").value,
      out_time: document.getElementById("gpOutTime").value,
      expected_in_time: document.getElementById("gpExpectedInTime").value,
      qr_payload: document.getElementById("gpScannedPayload") ? document.getElementById("gpScannedPayload").value.trim() : "",
    };
    if (!payload.reason || !payload.event_date || !payload.out_time) {
      showMsg(msgEl, "Please fill in all required fields (*).", false);
      return;
    }
    const today = todayISO();
    if (payload.event_date < today) {
      showMsg(msgEl, "Event date cannot be in the past.", false);
      return;
    }
    try {
      await api("/api/student/gatepass", { method: "POST", body: JSON.stringify(payload) });
      showMsg(msgEl, "✅ Gate Pass request submitted! Sent to Class Incharge for approval.", true);
      document.getElementById("gpReason").value = "";
      loadGatepassPanel();
    } catch (err) {
      showMsg(msgEl, err.message || "Could not submit Gate Pass request.", false);
    }
  });
}

async function loadGatepassPanel() {
  await loadActiveGatepass();
  await loadGatepassHistory();
}

async function loadActiveGatepass() {
  const activeCard = document.getElementById("gpActiveCard");
  const badge = document.getElementById("navGatepassBadge");
  try {
    const res = await api("/api/student/gatepass/active");
    if (res && res.has_active && res.pass) {
      const p = res.pass;
      if (activeCard) activeCard.classList.remove("dn");
      if (badge) badge.classList.remove("dn");
      document.getElementById("gpActiveReason").textContent = `${p.pass_type || 'Gate Pass'}: ${p.reason}`;
      document.getElementById("gpActiveDate").textContent = `${p.event_date} (Out: ${p.out_time})`;
      document.getElementById("gpActiveOtp").textContent = p.otp || "------";
      document.getElementById("gpActiveFaculty").textContent = p.faculty_decided_by ? `${p.faculty_decided_by} (${p.faculty_decided_at || 'Approved'})` : "Approved";
      document.getElementById("gpActiveHod").textContent = p.hod_decided_by ? `${p.hod_decided_by} (${p.hod_decided_at || 'Approved'})` : "Approved";
      document.getElementById("gpActiveOutTime").textContent = `${p.out_time} (Expected Return: ${p.expected_in_time || 'N/A'})`;

      renderQrCanvas("gpQrCanvas", `GP:${p.id}:${p.otp}`);
    } else {
      if (activeCard) activeCard.classList.add("dn");
      if (badge) badge.classList.add("dn");
    }
  } catch (err) {
    console.warn("loadActiveGatepass:", err);
  }
}

function renderQrCanvas(targetId, text) {
  const el = document.getElementById(targetId);
  if (!el) return;
  el.innerHTML = `
    <svg width="74" height="74" viewBox="0 0 25 25" shape-rendering="crispEdges">
      <rect width="25" height="25" fill="#ffffff"/>
      <rect x="2" y="2" width="7" height="7" fill="#065f46"/>
      <rect x="3" y="3" width="5" height="5" fill="#ffffff"/>
      <rect x="4" y="4" width="3" height="3" fill="#065f46"/>
      <rect x="16" y="2" width="7" height="7" fill="#065f46"/>
      <rect x="17" y="3" width="5" height="5" fill="#ffffff"/>
      <rect x="18" y="4" width="3" height="3" fill="#065f46"/>
      <rect x="2" y="16" width="7" height="7" fill="#065f46"/>
      <rect x="3" y="17" width="5" height="5" fill="#ffffff"/>
      <rect x="4" y="18" width="3" height="3" fill="#065f46"/>
      <rect x="11" y="4" width="2" height="2" fill="#065f46"/>
      <rect x="11" y="9" width="3" height="3" fill="#065f46"/>
      <rect x="10" y="16" width="2" height="4" fill="#065f46"/>
      <rect x="15" y="11" width="3" height="2" fill="#065f46"/>
      <rect x="16" y="16" width="5" height="5" fill="#065f46"/>
      <rect x="18" y="18" width="2" height="2" fill="#ffffff"/>
    </svg>
  `;
}

async function loadGatepassHistory() {
  const container = document.getElementById("gpHistory");
  if (!container) return;
  try {
    const data = await api("/api/student/gatepass");
    const requests = data.requests || [];
    if (!requests.length) {
      container.innerHTML = `<p class="placeholder-text">No Gate Pass requests found.</p>`;
      return;
    }
    container.innerHTML = requests.map(r => {
      let badgeClass = "badge-pending";
      let statusLabel = r.status;
      if (r.status === "Approved") {
        badgeClass = "badge-approved";
        statusLabel = `Approved (OTP: ${r.otp})`;
      } else if (r.status === "Forwarded") {
        badgeClass = "badge-pending";
        statusLabel = "Under HOD Review";
      } else if (r.status === "Exited") {
        badgeClass = "badge-approved";
        statusLabel = `Exited Gate (${r.exited_at ? (r.exited_at.split('T')[1] || r.exited_at) : 'Done'})`;
      } else if (r.status === "Rejected") {
        badgeClass = "badge-rejected";
      }
      return `
        <div class="request-item" style="border-left: 4px solid ${r.status === 'Approved' ? '#10b981' : r.status === 'Exited' ? '#3b82f6' : r.status === 'Rejected' ? '#ef4444' : '#f59e0b'}; margin-bottom:12px; padding:12px 14px; background:#fff; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.04); min-width:0; max-width:100%; box-sizing:border-box; word-break:break-word; overflow-wrap:anywhere;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px; gap:12px; width:100%; min-width:0;">
            <div style="font-weight:700; font-size:0.95rem; color:var(--text); min-width:0; flex:1; word-break:break-word; overflow-wrap:anywhere; line-height:1.4;">
              <span style="color:var(--text2); font-weight:600;">${escapeHtml(r.pass_type || 'Gate Pass')} — </span><span>${escapeHtml(r.reason)}</span>
            </div>
            <span class="badge ${badgeClass}" style="font-size:0.75rem; padding:3px 8px; border-radius:4px; font-weight:700; flex-shrink:0; white-space:nowrap;">${statusLabel}</span>
          </div>
          <div style="font-size:0.8rem; color:var(--text2); display:flex; gap:16px; flex-wrap:wrap; min-width:0; word-break:break-word;">
            <span>📅 Date: <strong>${escapeHtml(r.event_date)}</strong></span>
            <span>⏰ Out: <strong>${escapeHtml(r.out_time)}</strong></span>
            <span>Applied: ${r.applied_at ? escapeHtml(r.applied_at.replace('T', ' ')) : ''}</span>
            ${r.otp && r.status === 'Approved' ? `<span style="color:#059669; font-weight:800; font-family:monospace; background:#ecfdf5; padding:2px 8px; border-radius:4px;">OTP: ${escapeHtml(r.otp)}</span>` : ''}
          </div>
          ${r.hod_remarks || r.faculty_remarks ? `
            <div style="font-size:0.76rem; color:#6b7280; margin-top:6px; font-style:italic; min-width:0; word-break:break-word; overflow-wrap:anywhere;">
              ${r.faculty_remarks ? `Class Incharge: "${escapeHtml(r.faculty_remarks)}" ` : ''}
              ${r.hod_remarks ? `HOD: "${escapeHtml(r.hod_remarks)}"` : ''}
            </div>
          ` : ''}
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<p class="placeholder-text" style="color:#ef4444">Error loading Gate Pass history.</p>`;
  }
}

// ── Avatar upload (safe guards) ──────────────────────────────
const changePhotoBtn = document.getElementById("changePhotoBtn");
if (changePhotoBtn) {
  changePhotoBtn.addEventListener("click", () => {
    const pi = document.getElementById("photoInput");
    if (pi) pi.click();
  });
}
const photoInput = document.getElementById("photoInput");
if (photoInput) {
  photoInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const msgEl = document.getElementById("photoMsg");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const data = await api("/student/profile/photo", { method: "POST", body: fd });
      if (msgEl) showMsg(msgEl, "Photo updated.", true);
      const avatarImg = document.getElementById("avatarImg");
      if (avatarImg) {
        avatarImg.src = data.avatar_path + "?t=" + Date.now();
        avatarImg.classList.remove("dn");
      }
      const pPhotoImg = document.getElementById("pPhotoImg");
      if (pPhotoImg) {
        pPhotoImg.src = data.avatar_path + "?t=" + Date.now();
        pPhotoImg.classList.remove("dn");
      }
      const sideAvatarImg = document.getElementById("sideAvatarImg");
      if (sideAvatarImg) {
        sideAvatarImg.src = data.avatar_path + "?t=" + Date.now();
        sideAvatarImg.classList.remove("dn");
      }
      const ap = document.getElementById("avatarPlaceholder");
      if (ap) ap.classList.add("dn");
    } catch (err) {
      if (msgEl) showMsg(msgEl, err.message || "Upload failed.", false);
    }
  });
}

// ── Update Profile Photo Tab Handler (Unrestricted Anytime Upload) ──
const saPhotoFile = document.getElementById("saPhotoFile");
const saUploadBtn = document.getElementById("saUploadPhotoBtn");
const saPhotoMsg = document.getElementById("saPhotoMsg");

if (saPhotoFile) {
  saPhotoFile.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (re) => {
        const prevImg = document.getElementById("uploadPreviewImg");
        const prevPlaceholder = document.getElementById("uploadPreviewPlaceholder");
        if (prevImg) {
          prevImg.src = re.target.result;
          prevImg.classList.remove("dn");
        }
        if (prevPlaceholder) prevPlaceholder.classList.add("dn");
      };
      reader.readAsDataURL(file);
    }
  });
}

if (saUploadBtn) {
  saUploadBtn.addEventListener("click", async () => {
    if (!saPhotoFile || !saPhotoFile.files.length) {
      if (saPhotoMsg) showMsg(saPhotoMsg, "Please select an image file first.", false);
      return;
    }
    const file = saPhotoFile.files[0];
    const fd = new FormData();
    fd.append("file", file);
    saUploadBtn.disabled = true;
    saUploadBtn.textContent = "Uploading...";
    try {
      const data = await api("/student/profile/photo", { method: "POST", body: fd });
      if (saPhotoMsg) showMsg(saPhotoMsg, "Profile photo updated successfully!", true);
      const newUrl = data.avatar_path + "?t=" + Date.now();
      const pPhotoImg = document.getElementById("pPhotoImg");
      if (pPhotoImg) {
        pPhotoImg.src = newUrl;
        pPhotoImg.classList.remove("dn");
      }
      const pPlaceholder = document.getElementById("pPhotoPlaceholder");
      if (pPlaceholder) pPlaceholder.classList.add("dn");

      const prevImg = document.getElementById("uploadPreviewImg");
      if (prevImg) {
        prevImg.src = newUrl;
        prevImg.classList.remove("dn");
      }
      const prevPlaceholder = document.getElementById("uploadPreviewPlaceholder");
      if (prevPlaceholder) prevPlaceholder.classList.add("dn");
    } catch (err) {
      if (saPhotoMsg) showMsg(saPhotoMsg, err.message || "Upload failed. Please try again.", false);
    } finally {
      saUploadBtn.disabled = false;
      saUploadBtn.textContent = "Upload Photo";
    }
// ── Edit Communication Details Form Handler ─────────────────
const btnToggleCommEdit = document.getElementById("btnToggleCommEdit");
const btnCancelCommEdit = document.getElementById("btnCancelCommEdit");
const commEditFormBox = document.getElementById("commEditFormBox");
const commEditForm = document.getElementById("commEditForm");
const commEditMsg = document.getElementById("commEditMsg");

if (btnToggleCommEdit) {
  btnToggleCommEdit.addEventListener("click", () => {
    if (!commEditFormBox) return;
    const isClosed = commEditFormBox.classList.contains("dn");
    commEditFormBox.classList.toggle("dn", !isClosed);
    if (isClosed) {
      const em = document.getElementById("editMobile"); if (em) em.value = document.getElementById("cMobile")?.textContent || "";
      const ee = document.getElementById("editEmail"); if (ee) ee.value = document.getElementById("cEmail")?.textContent || "";
      const ea = document.getElementById("editAddress"); if (ea) ea.value = document.getElementById("cAddress")?.textContent || "";
      const et = document.getElementById("editTown"); if (et) et.value = document.getElementById("cTown")?.textContent || "";
    }
  });
}

if (btnCancelCommEdit) {
  btnCancelCommEdit.addEventListener("click", () => {
    if (commEditFormBox) commEditFormBox.classList.add("dn");
  });
}

if (commEditForm) {
  commEditForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      student_mobile: document.getElementById("editMobile")?.value.trim() || "",
      student_email: document.getElementById("editEmail")?.value.trim() || "",
      address: document.getElementById("editAddress")?.value.trim() || "",
      town: document.getElementById("editTown")?.value.trim() || "",
    };
    try {
      await api("/student/profile", { method: "PUT", body: JSON.stringify(payload) });
      if (commEditMsg) showMsg(commEditMsg, "Contact details updated successfully!", true);
      setElText("cMobile", payload.student_mobile);
      setElText("cEmail", payload.student_email);
      setElText("cAddress", payload.address);
      setElText("cTown", payload.town);
      setTimeout(() => {
        if (commEditFormBox) commEditFormBox.classList.add("dn");
        if (commEditMsg) commEditMsg.classList.add("dn");
      }, 1500);
    } catch (err) {
      if (commEditMsg) showMsg(commEditMsg, err.message || "Failed to update contact details.", false);
    }
  });
}

// ── Sidebar navigation (panel switching, no page reload) ────
const navItems = document.querySelectorAll(".nav-item");
const panels = document.querySelectorAll(".panel");
let attendanceLoaded = false;
let marksLoaded = false;
let resultsLoaded = false;
let timetableLoaded = false;
let leaveLoaded = false;
let odLoaded = false;
let trackerLoaded = false;

function switchPanel(panelName, skipPush = false) {
  if (!panelName) panelName = "profile";
  panels.forEach(p => p.classList.toggle("dn", p.id !== `panel-${panelName}`));
  navItems.forEach(n => n.classList.toggle("active", n.dataset.panel === panelName));
  
  // Highlight sub-item if applicable and expand accordion
  document.querySelectorAll(".nav-sub-item").forEach(si => {
    si.classList.toggle("active", si.dataset.panel === panelName);
  });
  const activeSub = document.querySelector(`.nav-sub-item[data-panel="${panelName}"]`);
  if (activeSub) {
    const parentAcc = activeSub.closest(".nav-accordion");
    if (parentAcc) {
      parentAcc.classList.add("open");
      const subMenu = parentAcc.querySelector(".nav-sub-menu");
      if (subMenu) subMenu.classList.remove("dn");
    }
  }

  const sb = document.getElementById("sidebar");
  if (sb) sb.classList.remove("open");

  if (!skipPush) {
    try {
      if (window.location.hash !== `#${panelName}`) {
        window.location.hash = panelName;
      }
    } catch (_) {}
  }

  if (panelName === "attendance-overall" || panelName === "attendance") {
    loadAttendanceOverall();
  }
  if (panelName === "attendance-monthwise") {
    loadAttendanceMonthwise("2026-07");
  }
  if (panelName === "marks" && !marksLoaded) {
    loadMarksPanel();
  }
  if (panelName === "results" && !resultsLoaded) {
    loadResultsPanel();
  }
  if (panelName === "timetable" && !timetableLoaded) {
    loadTimetablePanel();
  }
  if (panelName === "leave" && !leaveLoaded) {
    loadLeaveHistory();
  }
  if (panelName === "od" && !odLoaded) {
    loadOdHistory();
  }
  if (panelName === "gatepass") {
    loadGatepassPanel();
  }
  if (panelName === "tracker" && !trackerLoaded) {
    loadRequestTracker();
  }
  if (panelName === "notifications") {
    loadNotificationsPanel();
  }
}

window.addEventListener("hashchange", () => {
  const p = window.location.hash ? window.location.hash.replace("#", "") : "profile";
  if (p && document.getElementById(`panel-${p}`)) {
    switchPanel(p, true);
  }
});

navItems.forEach(btn => {
  btn.addEventListener("click", () => {
    if (btn.dataset.panel) switchPanel(btn.dataset.panel);
  });
});

// Accordion toggle handlers
document.querySelectorAll(".nav-accordion-btn").forEach(btn => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    const parent = btn.closest(".nav-accordion");
    if (!parent) return;
    const sub = parent.querySelector(".nav-sub-menu");
    if (!sub) return;
    const isClosed = sub.classList.contains("dn");
    sub.classList.toggle("dn", !isClosed);
    parent.classList.toggle("open", isClosed);
    if (isClosed && btn.id === "navAttendanceBtn") {
      const currentActiveSub = sub.querySelector(".nav-sub-item.active");
      if (!currentActiveSub) {
        switchPanel("attendance-overall");
      }
    }
  });
});

// Sub-menu item click handlers
document.querySelectorAll(".nav-sub-item").forEach(item => {
  item.addEventListener("click", (e) => {
    e.preventDefault();
    if (item.dataset.panel) {
      switchPanel(item.dataset.panel);
    }
  });
});

// Profile Tab Click Handlers
document.querySelectorAll(".sa-tab-item").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".sa-tab-item").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".sa-tab-pane").forEach(p => p.classList.add("dn"));
    btn.classList.add("active");
    const target = document.getElementById(`ptab-${btn.dataset.ptab}`);
    if (target) target.classList.remove("dn");
  });
});

// Month Tab Click Handlers
document.querySelectorAll(".sa-mtab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".sa-mtab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    loadAttendanceMonthwise(btn.dataset.month);
  });
});

// Search filters
const courseSearch = document.getElementById("courseSearchInput");
if (courseSearch) {
  courseSearch.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll("#coursesTableBody tr").forEach(tr => {
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  });
}
const mSubjSearch = document.getElementById("mSubjSearch");
if (mSubjSearch) {
  mSubjSearch.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll("#monthSubjectBody tr").forEach(tr => {
      tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none";
    });
  });
}

// ── Over All Attendance Loader ──────────────────────────────
async function loadAttendanceOverall() {
  try {
    const data = await api("/student/attendance/overall");
    if (data.kpi) {
      setElText("ovPercentage", data.kpi.percentage);
      setElText("ovTotal", data.kpi.total_working_days);
      setElText("ovPresent", data.kpi.present);
      setElText("ovAbsent", data.kpi.absent);
      setElText("ovOd", data.kpi.on_duty);
      setElText("ovLeave", data.kpi.leave);
    }
    const tbody = document.getElementById("attOverallSubjectBody");
    if (tbody && Array.isArray(data.subjects)) {
      tbody.innerHTML = data.subjects.map(s => `
        <tr>
          <td style="text-align:left;font-weight:600;">${escapeHtml(s.course_code_name)}</td>
          <td style="text-align:left;">${escapeHtml(s.staff_code_name)}</td>
          <td>${escapeHtml(s.total_hours)}</td>
          <td>${escapeHtml(s.attended_hours)}</td>
          <td style="font-weight:700;color:#0e8345;">${escapeHtml(s.percentage)}</td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.error("Failed to load overall attendance:", err);
  }
}

// ── Month wise Attendance Loader ────────────────────────────
async function loadAttendanceMonthwise(month = "2026-07") {
  try {
    const data = await api(`/student/attendance/monthwise?month=${encodeURIComponent(month)}`);
    const label = data.month_label || month;
    setElText("calHeaderMonth", label);
    setElText("repHeaderMonth", label);
    setElText("subjHeaderMonth", label);

    if (data.kpi) {
      setElText("mPercentage", data.kpi.percentage);
      setElText("mTotal", data.kpi.total_working_days);
      setElText("mPresent", data.kpi.present);
      setElText("mAbsent", data.kpi.absent);
      setElText("mOd", data.kpi.on_duty);
      setElText("mLeave", data.kpi.leave);
    }

    // Render calendar
    const calBody = document.getElementById("calBody");
    if (calBody && Array.isArray(data.calendar_grid)) {
      calBody.innerHTML = data.calendar_grid.map(row => {
        const cells = row.map(cell => {
          let cls = "";
          let text = cell.label || (cell.day !== null ? String(cell.day).padStart(2, "0") : "");
          if (cell.type === "present") cls = "cal-day-present";
          else if (cell.type === "absent") cls = "cal-day-absent";
          else if (cell.type === "sunday") cls = "cal-day-sunday";
          else if (cell.type === "holiday") cls = "cal-day-holiday";
          else cls = "cal-day-empty";
          return `<td class="${cls}">${escapeHtml(text)}</td>`;
        }).join("");
        return `<tr>${cells}</tr>`;
      }).join("");
    }

    // Render month subjects
    const subjBody = document.getElementById("monthSubjectBody");
    if (subjBody && Array.isArray(data.subjects)) {
      subjBody.innerHTML = data.subjects.map(s => `
        <tr>
          <td style="text-align:left;font-weight:600;">${escapeHtml(s.course_code)}</td>
          <td style="text-align:left;">${escapeHtml(s.course_name)}</td>
          <td>${escapeHtml(s.total_working_hours)}</td>
          <td style="color:#0e8345;font-weight:700;">${escapeHtml(s.present)}</td>
          <td style="color:${parseFloat(s.absent) > 0 ? '#dc2626' : 'inherit'};font-weight:700;">${escapeHtml(s.absent)}</td>
          <td>${escapeHtml(s.on_duty)}</td>
          <td>${escapeHtml(s.leave)}</td>
        </tr>
      `).join("");
    }
  } catch (err) {
    console.error("Failed to load monthwise attendance:", err);
  }
}

// ── Attendance panel ─────────────────────────────────────────
async function loadAttendancePanel() {
  const barsEl = document.getElementById("attBars");
  const overallEl = document.getElementById("attOverallValue");
  const presentEl = document.getElementById("attPresentCount");
  const absentEl = document.getElementById("attAbsentCount");
  const totalEl = document.getElementById("attTotalCount");
  const detailBody = document.getElementById("attDetailBody");

  try {
    // ── 1. Summary (overall % + subject bars) ──
    const data = await api("/student/attendance");

    const pctVal = (data.overall_percent !== null && data.overall_percent !== undefined)
      ? data.overall_percent : null;
    overallEl.textContent = pctVal !== null ? `${pctVal}%` : "No data yet";
    if (pctVal !== null && pctVal < 75) overallEl.classList.add("att-warn-pct");

    const subjects = data.subjects || [];
    if (!subjects.length) {
      barsEl.innerHTML = `<p class="placeholder-text">No attendance records found yet.</p>`;
    } else {
      barsEl.innerHTML = subjects.map(s => {
        const pct = Math.max(0, Math.min(100, s.percent));
        const barColor = pct >= 75 ? "var(--mint)" : pct >= 50 ? "var(--amber)" : "var(--coral)";
        const warnClass = pct < 75 ? "att-warn-pct" : "";
        return `
          <div class="att-bar-row">
            <div class="att-bar-label">
              <span>${escapeHtml(s.subject_name)}</span>
              <span class="att-bar-pct ${warnClass}">${s.percent}% (${s.present}/${s.total})</span>
            </div>
            <div class="att-bar-track">
              <div class="att-bar-fill" style="width:${pct}%;background:${barColor}"></div>
            </div>
          </div>`;
      }).join("");
    }

    // ── 2. Detail log (date-wise records) ──
    const detail = await api("/student/attendance/detail");
    attendanceLoaded = true;

    presentEl.textContent = detail.present ?? "—";
    absentEl.textContent = detail.absent ?? "—";
    totalEl.textContent = detail.total ?? "—";

    const records = detail.records || [];
    if (!records.length) {
      detailBody.innerHTML = `<tr><td colspan="5" class="placeholder-text">No attendance records yet.</td></tr>`;
    } else {
      detailBody.innerHTML = records.map(r => {
        const isPresent = r.status === "Present";
        const badgeCls = isPresent ? "att-badge-present" : "att-badge-absent";
        return `<tr>
          <td>${escapeHtml(r.date || "—")}</td>
          <td>${escapeHtml(r.period || "—")}</td>
          <td>${escapeHtml(r.subject_name || "—")}</td>
          <td>${escapeHtml(r.time || "—")}</td>
          <td><span class="att-badge ${badgeCls}">${escapeHtml(r.status)}</span></td>
        </tr>`;
      }).join("");
    }

  } catch (err) {
    barsEl.innerHTML = `<p class="placeholder-text">Could not load attendance: ${escapeHtml(err.message || "")}</p>`;
    if (detailBody) detailBody.innerHTML = `<tr><td colspan="5" class="placeholder-text">Could not load log.</td></tr>`;
    attendanceLoaded = true;
  }
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// ── Marks panel ───────────────────────────────────────────────
async function loadMarksPanel() {
  const tbody = document.getElementById("marksTableBody");
  const barsEl = document.getElementById("marksBars");
  try {
    const data = await api("/student/marks");
    marksLoaded = true;
    const subjects = data.subjects || [];

    if (!subjects.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="placeholder-text">No marks have been entered yet.</td></tr>`;
      barsEl.innerHTML = `<p class="placeholder-text">No marks have been entered yet.</p>`;
      return;
    }

    tbody.innerHTML = subjects.map(s => `
      <tr>
        <td>${escapeHtml(s.subject_name)}</td>
        <td>${s.cia1}</td>
        <td>${s.cia2}</td>
        <td>${s.cia3}</td>
        <td>${s.model_exam}</td>
        <td><b>${s.total}</b></td>
      </tr>`).join("");

    const maxTotal = Math.max(...subjects.map(s => s.total), 1);
    barsEl.innerHTML = subjects.map(s => {
      const pct = Math.max(2, Math.min(100, (s.total / maxTotal) * 100));
      return `
        <div class="att-bar-row">
          <div class="att-bar-label">
            <span>${escapeHtml(s.subject_name)}</span>
            <span class="att-bar-pct">${s.total}</span>
          </div>
          <div class="att-bar-track">
            <div class="att-bar-fill" style="width:${pct}%;background:var(--lavender)"></div>
          </div>
        </div>`;
    }).join("");
  } catch (err) {
    const msg = `Could not load marks: ${escapeHtml(err.message || "")}`;
    tbody.innerHTML = `<tr><td colspan="6" class="placeholder-text">${msg}</td></tr>`;
    barsEl.innerHTML = `<p class="placeholder-text">${msg}</p>`;
  }
}

// ── Semester Results panel ───────────────────────────────────
async function loadResultsPanel() {
  const tbody = document.getElementById("resultsTableBody");
  const cgpaEl = document.getElementById("cgpaValue");
  try {
    const data = await api("/student/results");
    resultsLoaded = true;

    cgpaEl.textContent = (data.cgpa !== null && data.cgpa !== undefined) ? data.cgpa : "—";

    const semesters = data.semesters || [];
    if (!semesters.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="placeholder-text">No semester results found yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = semesters.map(s => {
      const backlogs = (s.backlog_subjects || []);
      const backlogText = backlogs.length ? backlogs.join(", ") : "—";
      return `
        <tr>
          <td>Semester ${escapeHtml(s.semester)}</td>
          <td>${s.sgpa ?? "—"}</td>
          <td>${s.cgpa ?? "—"}</td>
          <td>${escapeHtml(backlogText)}</td>
        </tr>`;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="placeholder-text">Could not load results: ${escapeHtml(err.message || "")}</td></tr>`;
  }
}

// ── Timetable panel ───────────────────────────────────────────
const DAY_LABELS = { MON: "Monday", TUE: "Tuesday", WED: "Wednesday", THU: "Thursday", FRI: "Friday", SAT: "Saturday" };

async function loadTimetablePanel() {
  const gridEl = document.getElementById("timetableGrid");
  try {
    const data = await api("/student/timetable");
    timetableLoaded = true;

    const days = data.days || [];
    const today = data.today;
    const hasAny = days.some(d => (d.periods || []).length);

    if (!hasAny) {
      gridEl.className = "placeholder-card";
      gridEl.innerHTML = `<p class="placeholder-text">No timetable has been set up yet.</p>`;
      return;
    }

    gridEl.className = "timetable-grid";
    gridEl.innerHTML = days.map(d => {
      const isToday = d.day === today;
      const periods = d.periods || [];
      const periodsHtml = periods.length
        ? periods.map(p => `
            <div class="tt-period">
              <span class="tt-period-no">P${p.period_no}</span>
              <span class="tt-subject">${escapeHtml(p.course_name || p.course_code || "")}</span>
              ${p.room ? `<span class="tt-room">${escapeHtml(p.room)}</span>` : ""}
            </div>`).join("")
        : `<p class="placeholder-text">No classes</p>`;

      return `
        <div class="tt-day-col ${isToday ? "tt-today" : ""}">
          <div class="tt-day-header">${DAY_LABELS[d.day] || d.day}${isToday ? ' <span class="tt-today-badge">Today</span>' : ""}</div>
          <div class="tt-day-body">${periodsHtml}</div>
        </div>`;
    }).join("");
  } catch (err) {
    gridEl.className = "placeholder-card";
    gridEl.innerHTML = `<p class="placeholder-text">Could not load timetable: ${escapeHtml(err.message || "")}</p>`;
  }
}

// Mobile sidebar toggle
const sidebarToggleBtn = document.getElementById("sidebarToggle");
if (sidebarToggleBtn) {
  sidebarToggleBtn.addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });
}

// ── Notification bell (topbar) ───────────────────────────────
const bellBtn = document.getElementById("bellBtn");
if (bellBtn) {
  bellBtn.addEventListener("click", () => switchPanel("notifications"));
}

// ── Leave Request history ────────────────────────────────────
function fmtDate(d) {
  if (!d) return "—";
  const dt = new Date(d);
  return isNaN(dt) ? d : dt.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
}

function statusTagHtml(status) {
  const cls = status === "Approved" ? "status-approved"
            : status === "Rejected" ? "status-rejected"
            : "status-pending";
  return `<span class="status-tag ${cls}">${escapeHtml(status || "Pending")}</span>`;
}

async function loadLeaveHistory() {
  const listEl = document.getElementById("leaveHistory");
  try {
    const data = await api("/student/leave");
    leaveLoaded = true;
    const requests = data.requests || [];

    if (!requests.length) {
      listEl.innerHTML = `<p class="placeholder-text">No leave requests yet.</p>`;
      return;
    }

    listEl.innerHTML = requests.map(r => `
      <div class="request-item">
        <div class="request-item-main">
          <div class="request-dates">${fmtDate(r.from_date)} → ${fmtDate(r.to_date)}</div>
          <div class="request-reason">${escapeHtml(r.reason)}</div>
          <div class="request-applied">Applied ${fmtDate(r.applied_at)}</div>
        </div>
        ${statusTagHtml(r.status)}
      </div>`).join("");
  } catch (err) {
    listEl.innerHTML = `<p class="placeholder-text">Could not load leave history: ${escapeHtml(err.message || "")}</p>`;
  }
}

async function loadOdHistory() {
  const listEl = document.getElementById("odHistory");
  try {
    const data = await api("/student/od");
    odLoaded = true;
    const requests = data.requests || [];

    if (!requests.length) {
      listEl.innerHTML = `<p class="placeholder-text">No OD requests yet.</p>`;
      return;
    }

    listEl.innerHTML = requests.map(r => `
      <div class="request-item">
        <div class="request-item-main">
          <div class="request-dates">${escapeHtml(r.event_name)} — ${fmtDate(r.event_date)}</div>
          <div class="request-reason">${escapeHtml(r.reason)}</div>
          <div class="request-applied">Applied ${fmtDate(r.applied_at)}</div>
        </div>
        ${statusTagHtml(r.status)}
      </div>`).join("");
  } catch (err) {
    listEl.innerHTML = `<p class="placeholder-text">Could not load OD history: ${escapeHtml(err.message || "")}</p>`;
  }
}

// ── Request Tracker panel (📌) ───────────────────────────────
// Renders a stepper/timeline per request: Submitted -> Reviewed ->
// Approved/Rejected, fed by GET /student/requests/tracker (merges
// student_leave_requests + od_requests server-side).
function trackerStageIcon(state) {
  if (state === "done") return "✓";
  if (state === "rejected") return "✕";
  if (state === "active") return "•";
  return "○";
}

function trackerStepperHtml(stages) {
  return `
    <div class="tracker-stepper">
      ${stages.map((s, i) => `
        <div class="tracker-step tracker-step-${s.state}">
          <div class="tracker-step-node">
            <span class="tracker-step-icon">${trackerStageIcon(s.state)}</span>
          </div>
          <div class="tracker-step-body">
            <div class="tracker-step-label">${escapeHtml(s.label)}</div>
            ${s.date ? `<div class="tracker-step-date">${fmtDateTime(s.date)}</div>` : ""}
            ${s.detail ? `<div class="tracker-step-detail">${escapeHtml(s.detail)}</div>` : ""}
          </div>
          ${i < stages.length - 1 ? `<div class="tracker-step-connector tracker-connector-${s.state === "done" ? "done" : "pending"}"></div>` : ""}
        </div>`).join("")}
    </div>`;
}

function trackerCardHtml(r) {
  let typeBadge = `<span class="tracker-type-badge tracker-type-leave">🏖️ Leave</span>`;
  let subline = `${fmtDate(r.from_date)} → ${fmtDate(r.to_date)}`;

  if (r.type === "od") {
    typeBadge = `<span class="tracker-type-badge tracker-type-od">🆔 OD</span>`;
    subline = `${escapeHtml(r.event_name)} — ${fmtDate(r.event_date)}`;
  } else if (r.type === "gatepass") {
    typeBadge = `<span class="tracker-type-badge" style="background:#ede9fe;color:#6d28d9">🚪 ${escapeHtml(r.pass_type || 'Gate Pass')}</span>`;
    subline = `📅 ${escapeHtml(r.event_date)} | ⏰ Out: <strong>${escapeHtml(r.out_time)}</strong>${r.expected_in_time ? ` (Return: ${escapeHtml(r.expected_in_time)})` : ''}`;
  }

  return `
    <div class="tracker-card">
      <div class="tracker-card-head">
        <div class="tracker-card-head-l">
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            ${typeBadge}
            ${r.otp && r.status === 'Approved' ? `<span style="color:#059669; font-weight:800; font-family:monospace; background:#ecfdf5; padding:2px 8px; border-radius:4px; font-size:12px;">OTP: ${escapeHtml(r.otp)}</span>` : ''}
          </div>
          <div class="tracker-card-sub">${subline}</div>
        </div>
        ${statusTagHtml(r.status)}
      </div>
      <div class="tracker-card-reason">${escapeHtml(r.reason)}</div>
      ${trackerStepperHtml(r.stages)}
    </div>`;
}

async function loadRequestTracker() {
  const listEl = document.getElementById("trackerList");
  listEl.innerHTML = `<p class="placeholder-text">Loading requests…</p>`;
  try {
    const data = await api("/student/requests/tracker");
    trackerLoaded = true;
    const requests = data.requests || [];

    if (!requests.length) {
      listEl.innerHTML = `<p class="placeholder-text">No requests submitted yet.</p>`;
      return;
    }

    listEl.innerHTML = requests.map(trackerCardHtml).join("");
  } catch (err) {
    listEl.innerHTML = `<p class="placeholder-text">Could not load request tracker: ${escapeHtml(err.message || "")}</p>`;
  }
}

// ── Notifications panel (🔔) ─────────────────────────────────
function fmtDateTime(d) {
  if (!d) return "—";
  const dt = new Date(d);
  return isNaN(dt) ? d : dt.toLocaleString(undefined, {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function setBellBadge(count) {
  const bellBadge = document.getElementById("bellBadge");
  const navBadge = document.getElementById("navNotifBadge");
  [bellBadge, navBadge].forEach(el => {
    if (!el) return;
    if (count > 0) {
      el.textContent = count > 99 ? "99+" : String(count);
      el.classList.remove("dn");
    } else {
      el.classList.add("dn");
    }
  });
}

// Lightweight: just fetches the unread count to keep the bell/nav
// badges current (used right after login, without rendering the list).
async function refreshNotifBadges() {
  try {
    const data = await api("/student/notifications");
    setBellBadge(data.unread_count || 0);
  } catch (err) {
    // Non-critical — fail quietly, leave badge as-is.
    console.warn("Could not refresh notification badges:", err.message);
  }
}

async function loadNotificationsPanel() {
  const listEl = document.getElementById("notifList");
  listEl.innerHTML = `<p class="placeholder-text">Loading notifications…</p>`;
  try {
    const data = await api("/student/notifications");
    const notifications = data.notifications || [];
    setBellBadge(data.unread_count || 0);

    if (!notifications.length) {
      listEl.innerHTML = `<p class="placeholder-text">No notifications yet.</p>`;
      return;
    }

    listEl.innerHTML = notifications.map(n => `
      <div class="notif-item ${n.is_read ? "read" : "unread"}" data-notif-id="${n.id}">
        <span class="notif-dot"></span>
        <div class="notif-item-main">
          <div class="notif-message">${escapeHtml(n.message)}</div>
          <div class="notif-time">${fmtDateTime(n.created_at)}</div>
        </div>
        ${n.is_read ? "" : `<button class="notif-mark-btn" onclick="markNotificationRead(${n.id})">Mark as read</button>`}
      </div>`).join("");
  } catch (err) {
    listEl.innerHTML = `<p class="placeholder-text">Could not load notifications: ${escapeHtml(err.message || "")}</p>`;
  }
}

async function markNotificationRead(id) {
  try {
    await api(`/student/notifications/${id}/read`, { method: "POST" });
    loadNotificationsPanel();
  } catch (err) {
    console.warn("Could not mark notification as read:", err.message);
  }
}

const markAllReadBtn = document.getElementById("markAllReadBtn");
if (markAllReadBtn) {
  markAllReadBtn.addEventListener("click", async () => {
    const unreadIds = Array.from(document.querySelectorAll(".notif-item.unread"))
      .map(el => el.dataset.notifId);
    if (!unreadIds.length) return;
    markAllReadBtn.disabled = true;
    try {
      await Promise.all(unreadIds.map(id =>
        api(`/student/notifications/${id}/read`, { method: "POST" })
      ));
    } catch (err) {
      console.warn("Could not mark all notifications as read:", err.message);
    } finally {
      markAllReadBtn.disabled = false;
      loadNotificationsPanel();
    }
  });
}

// ── Boot: resume session if token already present ───────────
(async function boot() {
  const token = getToken();
  if (!token) { show("loginScreen"); return; }
  try {
    await loadDashboard();
    show("appScreen");
    // Resume current panel from URL or hash if provided
    const path = window.location.pathname.replace(/\/+$/, '');
    const parts = path.split('/').filter(Boolean);
    const sub = (parts.length >= 2 ? parts[parts.length - 1].toLowerCase() : '') || (window.location.hash ? window.location.hash.replace('#', '').toLowerCase() : '');
    if (sub && document.getElementById(`panel-${sub}`)) {
      switchPanel(sub, true);
    } else {
      switchPanel("profile", true);
    }
  } catch (_) {
    clearToken();
    show("loginScreen");
  }
})();
