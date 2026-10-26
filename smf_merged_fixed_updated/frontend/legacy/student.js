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
  errEl.classList.add("dn");

  const register_number = document.getElementById("regNo").value.trim();
  const date_of_birth = document.getElementById("dob").value;
  if (!register_number) return;
  if (!date_of_birth) { showMsg(errEl, "Please enter your date of birth.", false); return; }

  const payload = { register_number, date_of_birth };

  try {
    const data = await api("/student/login", { method: "POST", body: JSON.stringify(payload) });
    setToken(data.access_token);
    await loadDashboard();
    show("appScreen");
  } catch (err) {
    showMsg(errEl, err.message || "Login failed.", false);
  }
});

// ── Logout ───────────────────────────────────────────────────
document.getElementById("logoutBtn").addEventListener("click", () => {
  clearToken();
  show("loginScreen");
  document.getElementById("loginForm").reset();
});

// ── Load profile into dashboard ─────────────────────────────
async function loadDashboard() {
  const profile = await api("/student/profile");
  document.getElementById("topUserName").textContent = profile.name || "";

  document.getElementById("vName").textContent = profile.name || "—";
  document.getElementById("vRegNo").textContent = profile.register_number || "—";
  document.getElementById("vDept").textContent = profile.department || "—";
  document.getElementById("vCourse").textContent = profile.course || "—";
  document.getElementById("vYearSec").textContent =
    [profile.year, profile.section].filter(Boolean).join(" / ") || "—";
  document.getElementById("vDob").textContent = profile.date_of_birth || "—";
  document.getElementById("vStatus").textContent = profile.status || "—";

  document.getElementById("fFirstName").value = profile.first_name || "";
  document.getElementById("fLastName").value = profile.last_name || "";
  document.getElementById("fStudentEmail").value = profile.student_email || "";
  document.getElementById("fStudentMobile").value = profile.student_mobile || "";
  document.getElementById("fParentEmail").value = profile.parent_email || "";
  document.getElementById("fParentMobile").value = profile.parent_mobile || "";

  const avatarImg = document.getElementById("avatarImg");
  const placeholder = document.getElementById("avatarPlaceholder");
  if (profile.avatar_path) {
    avatarImg.src = profile.avatar_path;
    avatarImg.classList.remove("dn");
    placeholder.classList.add("dn");
  } else {
    avatarImg.classList.add("dn");
    placeholder.classList.remove("dn");
    placeholder.textContent = (profile.name || "?").charAt(0).toUpperCase();
  }

  loadDashboardSummary(profile.name);
  refreshNotifBadges();
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
document.getElementById("profileForm").addEventListener("submit", async (e) => {
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

// ── Avatar upload ────────────────────────────────────────────
document.getElementById("changePhotoBtn").addEventListener("click", () => {
  document.getElementById("photoInput").click();
});
document.getElementById("photoInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const msgEl = document.getElementById("photoMsg");
  const fd = new FormData();
  fd.append("file", file);
  try {
    const data = await api("/student/profile/photo", { method: "POST", body: fd });
    showMsg(msgEl, "Photo updated.", true);
    const avatarImg = document.getElementById("avatarImg");
    avatarImg.src = data.avatar_path + "?t=" + Date.now();
    avatarImg.classList.remove("dn");
    document.getElementById("avatarPlaceholder").classList.add("dn");
  } catch (err) {
    showMsg(msgEl, err.message || "Upload failed.", false);
  }
});

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

function switchPanel(panelName) {
  panels.forEach(p => p.classList.toggle("dn", p.id !== `panel-${panelName}`));
  navItems.forEach(n => n.classList.toggle("active", n.dataset.panel === panelName));
  document.getElementById("sidebar").classList.remove("open");

  if (panelName === "attendance" && !attendanceLoaded) {
    loadAttendancePanel();
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
  if (panelName === "tracker" && !trackerLoaded) {
    loadRequestTracker();
  }
  if (panelName === "notifications") {
    loadNotificationsPanel();
  }
}

navItems.forEach(btn => {
  btn.addEventListener("click", () => switchPanel(btn.dataset.panel));
});

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
  const typeBadge = r.type === "leave"
    ? `<span class="tracker-type-badge tracker-type-leave">🏖️ Leave</span>`
    : `<span class="tracker-type-badge tracker-type-od">🆔 OD</span>`;

  const subline = r.type === "leave"
    ? `${fmtDate(r.from_date)} → ${fmtDate(r.to_date)}`
    : `${escapeHtml(r.event_name)} — ${fmtDate(r.event_date)}`;

  return `
    <div class="tracker-card">
      <div class="tracker-card-head">
        <div class="tracker-card-head-l">
          ${typeBadge}
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
  } catch (_) {
    clearToken();
    show("loginScreen");
  }
})();
