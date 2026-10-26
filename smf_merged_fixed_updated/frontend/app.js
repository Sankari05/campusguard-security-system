

/* ═══════════════════════════════════════════════════════════
   EduTrack Pro — Frontend v9.6
   Connects to the Smart Attendance System backend REST API.
   Base URL: same origin (served by FastAPI at /app)
   All data comes from the SQLite database via /api/* endpoints.
   ═══════════════════════════════════════════════════════════ */

const API_BASE = '';
let _token = null, _role = null, _user = {};

// ── Safe MJPEG error handler stub ──────────────────────────────
// Prevents "handleMjpegError is not defined" crash when the <img>
// fires onerror before attendance.js has loaded.
// attendance.js will overwrite this with the full implementation.
// Stub: attendance.js overrides this. Guard prevents duplicate retries.
var _mjpegRetryTimer = window._mjpegRetryTimer || null;
window.handleMjpegError = window.handleMjpegError || function(img) {
  var base = window._ATT_API_BASE || '';
  if (!base) return;
  if (_mjpegRetryTimer) return;
  _mjpegRetryTimer = setTimeout(function() {
    _mjpegRetryTimer = null;
    if (typeof ATT !== 'undefined' && ATT.active) {
      img.src = base + '/video_feed?' + Date.now();
    }
  }, 1500);
};

async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (_token) headers['Authorization'] = 'Bearer ' + _token;
  const res = await fetch(API_BASE + path, { ...opts, headers: { ...headers, ...(opts.headers||{}) } });
  if (!res.ok) {
    let detail = 'HTTP ' + res.status;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') {
        detail = body.detail;
      } else if (Array.isArray(body.detail)) {
        // Pydantic 422 validation errors — extract field + message
        detail = body.detail.map(e => {
          const field = Array.isArray(e.loc) ? e.loc[e.loc.length-1] : 'field';
          return `${field}: ${e.msg}`;
        }).join(', ');
      } else if (body.detail) {
        detail = JSON.stringify(body.detail);
      }
    } catch(e) {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res;
}

const api = {
  login:         (email, pass, role, facId, portal) => apiFetch('/api/login', { method:'POST', body:JSON.stringify({email, password:pass, role, fac_id:facId||'', portal:portal||role||''}) }),
  students:      ()          => apiFetch('/api/students'),
  addStudent:    (data)      => apiFetch('/api/students', { method:'POST', body:JSON.stringify(data) }),
  deleteStudent: (id)        => apiFetch('/api/students/'+id, { method:'DELETE' }),
  todayAtt:      (period)    => apiFetch('/api/attendance/today'+(period?'?period='+encodeURIComponent(period):'')),
  attSummary:    (days)      => apiFetch('/api/attendance/summary?days='+(days||30)),
  override:      (data)      => apiFetch('/api/attendance/override', { method:'POST', body:JSON.stringify(data) }),
  overrideLog:   (limit)     => apiFetch('/api/override/log?limit='+(limit||200)),
  sessionStart:  (payload)   => apiFetch('/api/role/session/start', { method:'POST', body:JSON.stringify(payload) }),
  sessionStop:   ()          => apiFetch('/api/role/session/stop',  { method:'POST', body:'{}' }),
  sessionStatus: ()          => apiFetch('/api/role/session/status'),
  trainStart:    ()          => apiFetch('/api/train', { method:'POST' }),
  trainStatus:   ()          => apiFetch('/api/train/status'),
  // ── Training Management APIs (admin-only) ─────────────────────────────
  trainStatusAll:  ()             => apiFetch('/api/train/status/all'),
  trainSelective:  (role, id)     => apiFetch('/api/train/selective', { method:'POST', body:JSON.stringify({role, id}) }),
  trainProgress:   ()             => apiFetch('/api/train/progress'),
  trainFull:       ()             => apiFetch('/api/train/full', { method:'POST' }),
  trainFullStatus: ()             => apiFetch('/api/train/full/status'),
  analytics:     ()          => apiFetch('/api/analytics/summary'),
  timetable:     ()          => apiFetch('/api/timetable'),
  courseYears:   (dk,ck)     => apiFetch(`/api/departments/${dk}/courses/${ck}/years`),
  settings:      ()          => apiFetch('/api/settings'),
  saveSettings:  (data)      => apiFetch('/api/settings', { method:'POST', body:JSON.stringify(data) }),
  periodStats:   ()          => apiFetch('/api/analytics/period'),
  exportCsv:     ()          => apiFetch('/api/export/csv'),
  lowAttendance: (thr,days)  => apiFetch('/api/alerts/low-attendance?threshold='+(thr||75)+'&days='+(days||180)),
  sendAlertMail: (data)      => apiFetch('/api/alerts/send-mail', { method:'POST', body:JSON.stringify(data) }),
  autoSendAlerts:()          => apiFetch('/api/alerts/auto-send', { method:'POST' }),
  // ── Override v10.0 (new full-featured endpoints) ──────────
  overrideNew:       (data)           => apiFetch('/api/attendance/override/new', { method:'POST', body:JSON.stringify(data) }),
  overrideHistory:   (params)         => apiFetch('/api/attendance/override/history?' + new URLSearchParams(params||{})),
  overrideFilter:    (params)         => apiFetch('/api/attendance/override/filter?' + new URLSearchParams(params||{})),
  overrideStats:     ()               => apiFetch('/api/attendance/override/stats'),
  facultyPermissions:  (facId)        => apiFetch('/api/faculty/'+facId+'/permissions'),
  // ── Attendance filter cascade (added: were missing, causing yearSections error) ──
  // Root cause: attendance.js calls the bare name `api` which resolves to THIS
  // const api object (app.js), NOT window.api set by attendance.js bootstrap.
  // These keys must exist here for the filter dropdowns to work.
  deptCourses:   (dept)           => apiFetch('/api/departments/'+encodeURIComponent(dept)+'/courses'),
  yearSections:  (dept,course,yr) => apiFetch('/api/departments/'+encodeURIComponent(dept)+'/courses/'+encodeURIComponent(course)+'/years/'+encodeURIComponent(yr)+'/sections'),
  facultyByDept: (dept)           => apiFetch('/api/faculty/by-dept?dept='+encodeURIComponent(dept)),
  hodByDept:     (dept)           => apiFetch('/api/hod/by-dept?dept='+encodeURIComponent(dept)),
  enrollCounts:  ()               => apiFetch('/api/enrollment/counts'),
};


const APP = { role:'admin', currentPage:'dashboard', attPollTimer:null, trainPollTimer:null, charts:{}, alertFilter:'all', localAlerts:[] };

// ── LOGIN ──────────────────────────────────────────────────────
const ADMIN_ROLE_EMAILS = {
  admin: '',
  hod:   ''
};

// ── NAME VALIDATION ────────────────────────────────────────────
// Rules: alphabets + single spaces only, min 3, max 50, no digits/specials.
const NAME_REGEX = /^[A-Za-z]+( [A-Za-z]+)*$/;

/**
 * Validates a name value and returns an error string or '' if valid.
 * @param {string} value - the trimmed name string
 * @param {string} label - 'First Name' or 'Last Name'
 */
function validateNameValue(value, label) {
  if (!value || value.length === 0)        return `${label} is required.`;
  if (value.length < 3)                    return `${label} must be at least 3 characters.`;
  if (value.length > 50)                   return `${label} must not exceed 50 characters.`;
  if (/[0-9]/.test(value))                 return `${label} must not contain numbers.`;
  if (/[^A-Za-z ]/.test(value))            return `${label} must not contain special characters.`;
  if (!NAME_REGEX.test(value))             return `${label} must contain only letters and single spaces between words.`;
  return '';
}

/**
 * Shows or clears an inline error message beneath an input.
 * The error <span> is injected once and reused; no UI structure change.
 */
function _setNameError(inputId, msg) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  let errEl = document.getElementById(inputId + '_name_err');
  if (!errEl) {
    errEl = document.createElement('span');
    errEl.id = inputId + '_name_err';
    errEl.style.cssText = 'display:block;color:#e74c3c;font-size:0.78rem;margin-top:3px;';
    inp.parentNode.appendChild(errEl);
  }
  errEl.textContent = msg;
  inp.style.borderColor = msg ? '#e74c3c' : '';
}

/**
 * Validates a name input by ID, shows inline error, returns true if valid.
 */
function validateNameInput(inputId, label) {
  const inp = document.getElementById(inputId);
  if (!inp) return true;
  const val = inp.value.trim();
  const err = validateNameValue(val, label);
  _setNameError(inputId, err);
  return err === '';
}

// Attach real-time (immediate) validation to all name fields once DOM is ready.
document.addEventListener('DOMContentLoaded', function() {
  const nameFields = [
    { id: 'en_fname', label: 'First Name' },
    { id: 'en_lname', label: 'Last Name'  },
    { id: 'sf_fname', label: 'First Name' },
    { id: 'sf_lname', label: 'Last Name'  },
    { id: 'hf_fname', label: 'First Name' },
    { id: 'hf_lname', label: 'Last Name'  },
  ];
  nameFields.forEach(({ id, label }) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input',  () => validateNameInput(id, label));
    el.addEventListener('blur',   () => validateNameInput(id, label));
    el.addEventListener('change', () => validateNameInput(id, label));
  });
});

// ── DOB VALIDATION ─────────────────────────────────────────────
// Rules (frontend):
//   Step 1 – DOB field not empty
//   Step 2 – Valid calendar date
//   Step 3 – Not a future date
//   Step 4 – Calculate age (years) from DOB to today
//   Step 5 – Determine role  (student | faculty | hod)
//   Step 6 – Apply role-specific age rules
//   Student            : 17 ≤ age ≤ 50
//   Assistant Professor: age ≥ 25
//   Associate Professor: age ≥ 32
//   HOD                : age ≥ 35

/**
 * Calculate age in completed years from a YYYY-MM-DD string to today.
 * Returns -1 if the string is not a valid date.
 */
function _calcAge(dobStr) {
  if (!dobStr) return -1;
  const dob = new Date(dobStr);
  if (isNaN(dob.getTime())) return -1;
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const mDiff = today.getMonth() - dob.getMonth();
  if (mDiff < 0 || (mDiff === 0 && today.getDate() < dob.getDate())) age--;
  return age;
}

/**
 * Show or clear an inline DOB error beneath the given input element.
 */
function _setDobError(inputId, msg) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  let errEl = document.getElementById(inputId + '_dob_err');
  if (!errEl) {
    errEl = document.createElement('span');
    errEl.id = inputId + '_dob_err';
    errEl.style.cssText = 'display:block;color:#e74c3c;font-size:0.78rem;margin-top:3px;';
    inp.parentNode.appendChild(errEl);
  }
  errEl.textContent = msg;
  inp.style.borderColor = msg ? '#e74c3c' : '';
}

/**
 * Core DOB validation logic (pure function – no DOM side effects).
 * @param {string} dobStr  – value from the date input (YYYY-MM-DD or '')
 * @param {string} role    – 'student' | 'faculty' | 'hod'
 * @param {string} designation – designation string (used for faculty sub-rules)
 * @returns {string} error message, or '' if valid
 */
function validateDobValue(dobStr, role, designation) {
  // Step 1 – required
  if (!dobStr || dobStr.trim() === '') return 'Date of Birth is required.';

  // Step 2 – valid date
  const dob = new Date(dobStr);
  if (isNaN(dob.getTime())) return 'Please enter a valid date.';

  // Step 3 – not future
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (dob > today) return 'Future dates are not allowed.';

  // Step 4 – calculate age
  const age = _calcAge(dobStr);
  if (age < 0) return 'Please enter a valid date.';

  // Step 5 & 6 – role-specific rules
  const roleNorm = (role || '').toLowerCase();
  const desigNorm = (designation || '').toLowerCase();

  if (roleNorm === 'student') {
    if (age < 17) return 'Student must be between 17 and 50 years old.';
    if (age > 50) return 'Student must be between 17 and 50 years old.';
  } else if (roleNorm === 'faculty') {
    // Assistant Professor (default if designation is empty)
    if (desigNorm.includes('associate')) {
      if (age < 32) return 'Associate Professor must be at least 32 years old.';
    } else {
      // Covers "assistant professor", plain "professor", empty, etc.
      if (age < 25) return 'Assistant Professor must be at least 25 years old.';
    }
  } else if (roleNorm === 'hod') {
    if (age < 35) return 'HOD must be at least 35 years old.';
  }

  return ''; // all checks passed
}

/**
 * Validates the DOB input for a given enrollment form, shows inline error,
 * and returns true if valid.
 *
 * @param {string} inputId     – DOM id of the date input
 * @param {string} role        – 'student' | 'faculty' | 'hod'
 * @param {string} designationId – DOM id of designation select (may be null)
 * @returns {boolean}
 */
function validateDobInput(inputId, role, designationId) {
  const inp = document.getElementById(inputId);
  if (!inp) return true;                        // field absent → skip
  const dobStr      = inp.value.trim();
  const designation = designationId
    ? (document.getElementById(designationId)?.value || '')
    : '';
  const err = validateDobValue(dobStr, role, designation);
  _setDobError(inputId, err);
  return err === '';
}

// Attach real-time DOB validation to all enrollment date-of-birth fields.
document.addEventListener('DOMContentLoaded', function () {
  const dobFields = [
    { id: 'en_dob',  role: 'student',  desigId: null          },
    { id: 'sf_dob',  role: 'faculty',  desigId: 'sf_designation' },
    { id: 'hf_dob',  role: 'hod',      desigId: null          },
  ];
  dobFields.forEach(({ id, role, desigId }) => {
    const el = document.getElementById(id);
    if (!el) return;
    const revalidate = () => validateDobInput(id, role, desigId);
    el.addEventListener('change', revalidate);
    el.addEventListener('blur',   revalidate);
    // Also re-validate DOB when designation changes (age rule depends on it)
    if (desigId) {
      const desigEl = document.getElementById(desigId);
      if (desigEl) desigEl.addEventListener('change', revalidate);
    }
  });
});

// ── MOBILE VALIDATION ───────────────────────────────────────────
// Rules: digits only, exactly 10, starts with 6/7/8/9, no duplicates.
const MOBILE_REGEX = /^[6-9][0-9]{9}$/;

/**
 * Synchronous format validation for a mobile value.
 * Returns an error string or '' if format is valid.
 */
function validateMobileFormat(value, label) {
  if (!value || value.length === 0)  return `${label} is required.`;
  if (/[A-Za-z]/.test(value))        return `${label} must not contain letters.`;
  if (/[^0-9]/.test(value))          return `${label} must not contain special characters.`;
  if (value.length !== 10)           return `${label} must be exactly 10 digits.`;
  if (!MOBILE_REGEX.test(value))     return `${label} must start with 6, 7, 8, or 9.`;
  return '';
}

/**
 * Shows or clears an inline error beneath a mobile input.
 * Reuses a single injected <span> — no UI structure change.
 */
function _setMobileError(inputId, msg) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  let errEl = document.getElementById(inputId + '_mob_err');
  if (!errEl) {
    errEl = document.createElement('span');
    errEl.id = inputId + '_mob_err';
    errEl.style.cssText = 'display:block;color:#e74c3c;font-size:0.78rem;margin-top:3px;';
    inp.parentNode.appendChild(errEl);
  }
  errEl.textContent = msg;
  inp.style.borderColor = msg ? '#e74c3c' : '';
}

/**
 * Validates format only (sync) for a mobile input.
 * Returns true if valid.
 */
function validateMobileInput(inputId, label) {
  const inp = document.getElementById(inputId);
  if (!inp) return true;
  const val = inp.value.trim();
  const err = validateMobileFormat(val, label);
  _setMobileError(inputId, err);
  return err === '';
}

/**
 * Full validation: format + async duplicate check via API.
 * Returns true if completely valid.
 */
async function validateMobileFull(inputId, label, excludeId = '') {
  if (!validateMobileInput(inputId, label)) return false;
  const inp = document.getElementById(inputId);
  const val = inp.value.trim();
  try {
    const url = `/api/check/mobile/${encodeURIComponent(val)}` +
                (excludeId ? `?exclude_id=${encodeURIComponent(excludeId)}` : '');
    const res = await apiFetch(url);
    if (res && res.exists) {
      const msg = `${label} is already registered to ${res.name || 'another record'} (${res.role || ''}).`;
      _setMobileError(inputId, msg);
      return false;
    }
  } catch (e) {
    // If 409 or network issue, treat as duplicate/error
    if ((e.message || '').includes('409') || (e.message || '').toLowerCase().includes('registered')) {
      _setMobileError(inputId, `${label} is already registered.`);
      return false;
    }
    // Other network errors: skip duplicate check, let backend catch it
  }
  _setMobileError(inputId, '');
  return true;
}

// Attach real-time format validation (immediate, no async) to all mobile fields.
document.addEventListener('DOMContentLoaded', function() {
  const mobileFields = [
    { id: 'en_smob', label: 'Student Mobile' },
    { id: 'en_pmob', label: 'Parent Mobile'  },
    { id: 'sf_mobile', label: 'Mobile Number' },
    { id: 'hf_mobile', label: 'Mobile Number' },
  ];
  mobileFields.forEach(({ id, label }) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input',  () => validateMobileInput(id, label));
    el.addEventListener('blur',   () => validateMobileFull(id, label));
    el.addEventListener('change', () => validateMobileFull(id, label));
  });
});


// ── EMAIL VALIDATION ────────────────────────────────────────────
// Rules: valid format, min 5, max 254, no spaces, allowed chars, no disposable, no duplicates.
const EMAIL_REGEX = /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/;
const DISPOSABLE_EMAIL_DOMAINS = new Set([
  'mailinator.com','tempmail.com','10minutemail.com','guerrillamail.com',
  'throwam.com','yopmail.com','trashmail.com','sharklasers.com',
  'fakeinbox.com','maildrop.cc','dispostable.com','mailnull.com',
  'throwaway.email','discard.email','mailnesia.com','tempinbox.com',
  'burnermail.io','temp-mail.org','getnada.com','anonaddy.com',
]);

/**
 * Synchronous email format/content validation.
 * Returns an error string or '' if valid.
 */
function validateEmailValue(value, label) {
  if (!value || value.length === 0)    return `${label} is required.`;
  if (value.includes(' '))             return `Spaces are not allowed in ${label.toLowerCase()}.`;
  if (value.length < 5)               return `${label} is too short (minimum 5 characters).`;
  if (value.length > 254)             return `${label} is too long (maximum 254 characters).`;
  if (!EMAIL_REGEX.test(value))       return `Please enter a valid ${label.toLowerCase()} address.`;
  const atParts = value.split('@');
  if (atParts.length !== 2 || !atParts[0]) return `Username (before @) is missing in ${label.toLowerCase()}.`;
  const domain = atParts[1];
  if (!domain || domain.startsWith('.') || domain.includes('..'))
    return `Domain (after @) is invalid in ${label.toLowerCase()}.`;
  if (/[^A-Za-z0-9._%+\-]/.test(atParts[0]))
    return `${label} contains invalid characters.`;
  if (DISPOSABLE_EMAIL_DOMAINS.has(domain.toLowerCase()))
    return `Temporary/disposable email addresses are not allowed.`;
  return '';
}

/**
 * Shows or clears an inline error message beneath an email input.
 * Reuses a single injected <span> — no UI structure change.
 */
function _setEmailError(inputId, msg) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  let errEl = document.getElementById(inputId + '_email_err');
  if (!errEl) {
    errEl = document.createElement('span');
    errEl.id = inputId + '_email_err';
    errEl.style.cssText = 'display:block;color:#e74c3c;font-size:0.78rem;margin-top:3px;';
    inp.parentNode.appendChild(errEl);
  }
  errEl.textContent = msg;
  inp.style.borderColor = msg ? '#e74c3c' : '';
}

/**
 * Synchronous format validation for an email input.
 * Returns true if valid.
 */
function validateEmailInput(inputId, label) {
  const inp = document.getElementById(inputId);
  if (!inp) return true;
  const val = inp.value.trim();
  const err = validateEmailValue(val, label);
  _setEmailError(inputId, err);
  return err === '';
}

/**
 * Full validation: format + async duplicate check via API.
 * Returns true if completely valid.
 * @param {string} excludeId - entity ID to exclude from duplicate check (for re-enroll)
 */
async function validateEmailFull(inputId, label, excludeId = '') {
  if (!validateEmailInput(inputId, label)) return false;
  const inp = document.getElementById(inputId);
  if (!inp) return true;
  const val = inp.value.trim();
  try {
    const url = `/api/check/email/${encodeURIComponent(val)}` +
                (excludeId ? `?exclude_id=${encodeURIComponent(excludeId)}` : '');
    const res = await apiFetch(url);
    if (res && res.exists) {
      const msg = `This email address is already registered to ${res.name || 'another record'} (${res.role || ''}).`;
      _setEmailError(inputId, msg);
      return false;
    }
  } catch (e) {
    const emsg = (e.message || '');
    if (emsg.includes('409') || emsg.toLowerCase().includes('registered') || emsg.toLowerCase().includes('already')) {
      _setEmailError(inputId, `This email address is already registered.`);
      return false;
    }
    // Network errors: skip duplicate check, backend will catch it
  }
  _setEmailError(inputId, '');
  return true;
}

// Attach real-time format validation to all email fields once DOM is ready.
// NOTE: en_semail is intentionally excluded — handled by smfOtp controller.
document.addEventListener('DOMContentLoaded', function() {
  const emailFields = [
    // en_semail excluded — OTP controller manages it
    // sf_email excluded — smfOtpFac OTP controller manages it
    // hf_email excluded — smfOtpHod OTP controller manages it
    { id: 'en_pemail', label: 'Parent Email'  },
    { id: 'ef_email',  label: 'Email'         },
  ];
  emailFields.forEach(({ id, label }) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input',  () => validateEmailInput(id, label));
    el.addEventListener('blur',   () => validateEmailFull(id, label));
    el.addEventListener('change', () => validateEmailFull(id, label));
  });
});

// ── PASSWORD TOGGLE HELPER ─────────────────────────────────────
function togglePw(inputId, iconEl) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  if (inp.type === 'password') {
    inp.type = 'text';
    iconEl.classList.replace('fa-eye', 'fa-eye-slash');
  } else {
    inp.type = 'password';
    iconEl.classList.replace('fa-eye-slash', 'fa-eye');
  }
}


function switchPortal(btn, portal) {
  document.querySelectorAll('.ptab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('adminPortal').classList.toggle('dn', portal !== 'admin');
  document.getElementById('facultyPortal').classList.toggle('dn', portal !== 'faculty');
}

// Called when user changes the role dropdown
function onAdminRoleChange() {
  const sel   = document.getElementById('adminRoleSelect');
  const role  = sel ? sel.value : 'admin';
  const emailField = document.getElementById('adminEmailField');
  const hodField   = document.getElementById('hodLoginField');

  if (role === 'hod') {
    // Show custom HOD ID/email input; hide the admin email
    if (emailField) emailField.classList.add('dn');
    if (hodField)   hodField.classList.remove('dn');
  } else {
    if (emailField) emailField.classList.remove('dn');
    if (hodField)   hodField.classList.add('dn');
  }
  // Clear password on role switch for security
  const p1 = document.getElementById('adminPass');
  const p2 = document.getElementById('adminPassFallback');
  if (p1) p1.value = '';
  if (p2) p2.value = '';
}

// facDemoSelect removed — faculty log in with Faculty ID + Password
function pickAdminRole() {} // kept as no-op for any legacy HTML calls

// ── Portal Detection Helper ─────────────────────────────────
function detectPortalMode() {
  const p = window.location.pathname.toLowerCase();
  if (p.includes('admin')) return 'admin';
  if (p.includes('hod')) return 'hod';
  if (p.includes('faculty')) return 'faculty';
  if (p.includes('student')) return 'student';
  return null;
}

async function loginAdmin() {
  const emailInput = document.getElementById('adminEmailInput') || document.getElementById('adminEmail');
  const email = emailInput ? emailInput.value.trim() : '';
  const passInput = document.getElementById('adminPass') || document.getElementById('adminPassFallback');
  const pass = passInput ? passInput.value.trim() : '';

  if (!email) { toast('Please enter your admin email or username', 'warn'); return; }
  if (!pass) { toast('Enter your password', 'warn'); return; }

  const btn = document.getElementById('btnAdminSignIn') || document.querySelector('#adminPortal .btn-signin') || document.querySelector('.btn-signin');
  const oldText = btn ? btn.innerHTML : '';
  if (btn) btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Signing in...';
  try {
    const res = await api.login(email, pass, 'admin', '', 'admin');
    _token = res.access_token;
    _role = res.role || 'admin';
    _user = {
      username: res.username || email,
      role: 'admin',
      name: res.name || 'ADMIN'
    };
    APP.role = 'admin';
    sessionStorage.setItem('_token', _token);
    sessionStorage.setItem('_role', 'admin');
    sessionStorage.setItem('_portal', 'admin');
    sessionStorage.setItem('_user', JSON.stringify(_user));
    sessionStorage.setItem('_lastPage', 'dashboard');
    if (!window.location.pathname.toLowerCase().includes('admin')) {
      window.location.href = '/admin';
    } else {
      startApp();
    }
  } catch(e) {
    toast('Login failed: ' + (e.message || 'Invalid credentials'), 'error');
    if (btn) btn.innerHTML = oldText || '<i class="fa fa-shield-halved"></i> Sign In as Admin';
  }
}

async function loginHod() {
  const idInput = document.getElementById('hodLoginId');
  const email = (idInput ? idInput.value.trim() : '');
  const passInput = document.getElementById('hodPass') || document.getElementById('adminPass');
  const pass = passInput ? passInput.value.trim() : '';

  if (!email) { toast('Enter your HOD ID or registered email', 'warn'); return; }
  if (!pass) { toast('Enter your password', 'warn'); return; }

  const btn = document.getElementById('btnHodSignIn') || document.querySelector('#hodPortal .btn-signin') || document.querySelector('.btn-signin');
  const oldText = btn ? btn.innerHTML : '';
  if (btn) btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Signing in...';
  try {
    const res = await api.login(email, pass, 'hod', '', 'hod');
    _token = res.access_token;
    _role = res.role || 'hod';
    _user = {
      username: res.username || email,
      role: 'hod',
      name: res.name || 'HOD',
      hod_id: res.hod_id || '',
      dept: res.dept || ''
    };
    APP.role = 'hod';
    sessionStorage.setItem('_token', _token);
    sessionStorage.setItem('_role', 'hod');
    sessionStorage.setItem('_portal', 'hod');
    sessionStorage.setItem('_user', JSON.stringify(_user));
    sessionStorage.setItem('_lastPage', 'dashboard');
    if (!window.location.pathname.toLowerCase().includes('hod')) {
      window.location.href = '/hod';
    } else {
      startApp();
    }
  } catch(e) {
    toast('Login failed: ' + (e.message || 'Invalid credentials'), 'error');
    if (btn) btn.innerHTML = oldText || '<i class="fa fa-user-tie"></i> Sign In as HOD';
  }
}

async function loginFaculty() {
  const facIdInput = document.getElementById('facIdInput');
  const facId = facIdInput ? facIdInput.value.trim().toUpperCase() : '';
  const passInput = document.getElementById('facPassText');
  const pass = passInput ? passInput.value.trim() : '';

  if (!facId)  { toast('Enter Faculty ID', 'warn'); return; }
  if (!pass)   { toast('Enter your password', 'warn'); return; }

  const btn = document.getElementById('btnFacSignIn') || document.querySelector('#facultyPortal .btn-signin') || document.querySelector('.btn-signin');
  const oldText = btn ? btn.innerHTML : '';
  if (btn) btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Signing in...';
  try {
    const res = await api.login('', pass, 'faculty', facId, 'faculty');
    _token = res.access_token;
    _role = 'faculty';
    _user = { fac_id: facId, name: res.name || facId, role: 'faculty' };
    APP.role = 'faculty';
    sessionStorage.setItem('_token', _token);
    sessionStorage.setItem('_role', 'faculty');
    sessionStorage.setItem('_portal', 'faculty');
    sessionStorage.setItem('_user', JSON.stringify(_user));
    sessionStorage.setItem('_lastPage', 'fac-dashboard');
    if (!window.location.pathname.toLowerCase().includes('faculty')) {
      window.location.href = '/faculty';
    } else {
      startApp();
    }
  } catch(e) {
    toast('Login failed: ' + (e.message || 'Invalid Faculty ID or password'), 'error');
    if (btn) btn.innerHTML = oldText || '<i class="fa fa-chalkboard-user"></i> Faculty Sign In';
  }
}

function doLogout() {
  const currentPath = window.location.pathname.toLowerCase();
  _token=null; _role=null; _user={};
  // Clear session storage so token is gone on next load
  sessionStorage.removeItem('_token');
  sessionStorage.removeItem('_role');
  sessionStorage.removeItem('_portal');
  sessionStorage.removeItem('_user');
  sessionStorage.removeItem('_lastPage');
  clearInterval(APP.attPollTimer); clearInterval(APP.trainPollTimer);
  stopNotificationPolling();

  if (currentPath.includes('admin')) {
    window.location.href = '/admin';
  } else if (currentPath.includes('hod')) {
    window.location.href = '/hod';
  } else if (currentPath.includes('faculty')) {
    window.location.href = '/faculty';
  } else {
    document.getElementById('appShell').classList.add('dn');
    document.getElementById('loginScreen').style.display = '';
  }
}

function syncPortalTabTitle(portal, role) {
  const currentPath = window.location.pathname.toLowerCase();
  const p = portal || (currentPath.includes('admin') ? 'admin' : (currentPath.includes('hod') ? 'hod' : (currentPath.includes('faculty') ? 'faculty' : (currentPath.includes('student') ? 'student' : ''))));
  const r = role || (window.APP && window.APP.role) || (typeof _role !== 'undefined' ? _role : '');

  if (p === 'admin' || r === 'admin') {
    document.title = 'Admin Portal — EduTrack Pro';
  } else if (p === 'hod' || r === 'hod') {
    document.title = 'HOD Portal — EduTrack Pro';
  } else if (p === 'faculty' || ['faculty', 'teacher', 'classincharge'].includes(r)) {
    document.title = 'Faculty Portal — EduTrack Pro';
  } else if (p === 'student') {
    document.title = 'Student Portal — EduTrack Pro';
  } else {
    document.title = 'EduTrack Pro — Portal Gateway';
  }
}

function startApp() {
  document.getElementById('loginScreen').style.display = 'none';
  document.getElementById('appShell').classList.remove('dn');
  syncPortalTabTitle(null, APP.role);
  populateFacSelect();
  buildSideNav();
  setTopbarProfile();
  startClock();
  const initPage = (typeof getPageFromUrl === 'function' ? getPageFromUrl() : null) || (APP.role==='faculty' ? 'fac-dashboard' : 'dashboard');
  showPage(initPage);
  startNotificationPolling();
  toast('Welcome! Signed in as '+getRoleLabel(), 'success');
}

function getRoleLabel() {
  const adminName = 'ADMIN';
  const hodName   = _user.name && _user.name !== 'HOD' ? _user.name : 'Vimalarani';
  const m={admin:adminName, hod:hodName, classincharge:_user.name||'Class Incharge', teacher:'Teacher', faculty:_user.name||'Faculty'};
  return m[APP.role]||APP.role;
}

function populateFacSelect() {
  // facDemoSelect removed — faculty log in with Faculty ID + Password
}

// ── NAV ───────────────────────────────────────────────────────
const NAV_CFG = {
  admin:[
    {section:'OVERVIEW',links:[{icon:'fa-chart-pie',label:'Dashboard',page:'dashboard'}]},
    {section:'MANAGE',links:[
      {icon:'fa-user-plus',label:'Enroll',page:'students'},
      {icon:'fa-users',label:'Students Management',page:'hod-students'},
      {icon:'fa-graduation-cap',label:'Academics',page:'academics'},
      {icon:'fa-user-tie',label:'Manage HOD',page:'manage-hod'},
      {icon:'fa-chalkboard-teacher',label:'Faculty',page:'faculty'},
      {icon:'fa-building-columns',label:'Departments',page:'departments'},
    ]},
    {section:'ATTENDANCE',links:[
      {icon:'fa-camera',label:'Take Attendance',page:'attendance',pill:'LIVE'},
      {icon:'fa-pen-to-square',label:'Overrides',page:'overrides'},
      {icon:'fa-chart-line',label:'Reports',page:'reports'},
    ]},
    {section:'SYSTEM',links:[
      {icon:'fa-bell',label:'Alerts',page:'alerts',pill:'alert'},
      {icon:'fa-file-shield',label:'Compliance',page:'compliance'},
      {icon:'fa-sliders',label:'Settings',page:'settings'},
      {icon:'fa-brain',label:'Train Model',page:'train'},
      {icon:'fa-clock-rotate-left',label:'Audit Log',page:'audit_log'},
    ]},
  ],
  hod:[
    {section:'OVERVIEW',links:[{icon:'fa-chart-pie',label:'Dashboard',page:'dashboard'}]},
    {section:'DATA',links:[
      {icon:'fa-building-columns',label:'Students',page:'hod-students'},
      {icon:'fa-graduation-cap',label:'Academics',page:'academics'},
      {icon:'fa-chalkboard-teacher',label:'Faculty',page:'faculty'},
      {icon:'fa-chart-line',label:'Reports',page:'reports'},
      {icon:'fa-bell',label:'Alerts',page:'alerts',pill:'alert'},
      {icon:'fa-file-shield',label:'Compliance',page:'compliance'},
      {icon:'fa-circle-check',label:'Pending Approvals',page:'hod_approvals'},
      {icon:'fa-id-badge',label:'OD Approval Queue',page:'hod-od-approvals'},
    ]},
  ],
  classincharge:[
    {section:'MY CLASS',links:[
      {icon:'fa-chart-pie',label:'Dashboard',page:'dashboard'},
      {icon:'fa-camera',label:'Take Attendance',page:'attendance',pill:'LIVE'},
      {icon:'fa-pen-to-square',label:'Overrides',page:'overrides'},
      {icon:'fa-bell',label:'Alerts',page:'alerts',pill:'alert'},
    ]},
  ],
  teacher:[
    {section:'MY CLASSES',links:[
      {icon:'fa-chart-pie',label:'Dashboard',page:'dashboard'},
      {icon:'fa-camera',label:'Take Attendance',page:'attendance',pill:'LIVE'},
      {icon:'fa-pen-to-square',label:'Overrides',page:'overrides'},
    ]},
  ],
  faculty:[
    {section:'MY PORTAL',links:[
      {icon:'fa-chart-pie',label:'My Dashboard',page:'fac-dashboard'},
      {icon:'fa-calendar-week',label:'Faculty Timetable',page:'my-timetable'},
      {icon:'fa-users',label:'Student Timetable',page:'timetable'},
      {icon:'fa-chart-line',label:'My Reports',page:'reports'},
    ]},
    {section:'REQUEST MANAGEMENT',links:[
      {icon:'fa-umbrella-beach',label:'Leave Approvals',page:'fac-leave-approvals'},
      {icon:'fa-id-badge',label:'OD Approvals',page:'fac-od-approvals'},
    ]},
  ],
  student:[
    {section:'MY ATTENDANCE',links:[
      {icon:'fa-chart-pie',label:'Dashboard',page:'dashboard'},
      {icon:'fa-hand-paper',label:'Request Correction',page:'correction'},
    ]},
  ],
};

const PAGE_TITLES = {
  dashboard:'Dashboard',attendance:'Student Attendance',students:'Enrollment Management',
  'hod-students':'Students',
  timetable:'Student Timetable','my-timetable':'Faculty Timetable',overrides:'Attendance Overrides',reports:'Reports & Analytics',
  alerts:'Smart Alerts',settings:'System Settings',train:'Train Models',
  'fac-dashboard':'My Dashboard',
  'fac-leave-approvals':'Leave Approvals','fac-od-approvals':'OD Approvals',
  departments:'Department Analytics',faculty:'Faculty Management',
  courses:'Courses & Electives',
  'manage-hod':'HOD Management',
  'correction':'Request Attendance Correction',
  'hod_approvals':'HOD Approval Dashboard',
  'hod-od-approvals':'OD Approval Queue',
  'audit_log':'Attendance Audit Log',
  'academics':'Academics — CGPA & Backlogs',
  'compliance':'NBA / NAAC Compliance Tracker',
};

// ── SPA URL ROUTING MAPPINGS ─────────────────────────────────
const PAGE_TO_SLUG = {
  'students': 'enroll',
  'hod-students': 'students',
  'dashboard': 'dashboard',
  'fac-dashboard': 'dashboard',
  'academics': 'academics',
  'manage-hod': 'manage-hod',
  'faculty': 'faculty',
  'departments': 'departments',
  'attendance': 'attendance',
  'overrides': 'overrides',
  'reports': 'reports',
  'alerts': 'alerts',
  'compliance': 'compliance',
  'settings': 'settings',
  'train': 'train',
  'audit_log': 'audit-log',
  'timetable': 'timetable',
  'my-timetable': 'my-timetable',
  'fac-leave-approvals': 'leave-approvals',
  'fac-od-approvals': 'od-approvals',
  'hod_approvals': 'approvals',
  'hod-od-approvals': 'od-approvals',
  'correction': 'correction',
  'courses': 'courses'
};

const SLUG_TO_PAGE = {
  'enroll': 'students',
  'students': 'hod-students',
  'students-management': 'hod-students',
  'manage-students': 'hod-students',
  'dashboard': 'dashboard',
  'academics': 'academics',
  'manage-hod': 'manage-hod',
  'faculty': 'faculty',
  'departments': 'departments',
  'attendance': 'attendance',
  'overrides': 'overrides',
  'reports': 'reports',
  'alerts': 'alerts',
  'compliance': 'compliance',
  'settings': 'settings',
  'train': 'train',
  'audit-log': 'audit_log',
  'audit_log': 'audit_log',
  'timetable': 'timetable',
  'my-timetable': 'my-timetable',
  'leave-approvals': 'fac-leave-approvals',
  'od-approvals': 'fac-od-approvals',
  'approvals': 'hod_approvals',
  'correction': 'correction',
  'courses': 'courses'
};

function getPageFromUrl() {
  try {
    const path = window.location.pathname.replace(/\/+$/, '');
    const parts = path.split('/').filter(Boolean);
    if (parts.length >= 2) {
      const slug = parts[parts.length - 1].toLowerCase();
      const portal = parts[0].toLowerCase();

      if (portal === 'faculty' && slug === 'dashboard') return 'fac-dashboard';
      if (portal === 'faculty' && (slug === 'od-approvals' || slug === 'od')) return 'fac-od-approvals';
      if (portal === 'hod' && (slug === 'od-approvals' || slug === 'od')) return 'hod-od-approvals';

      if (SLUG_TO_PAGE[slug]) return SLUG_TO_PAGE[slug];
      if (PAGE_TITLES && PAGE_TITLES[slug]) return slug;
    }
  } catch (err) {
    console.warn('[Routing] getPageFromUrl error:', err);
  }
  return null;
}

function updateBrowserUrl(pid, replace = false) {
  try {
    const slug = PAGE_TO_SLUG[pid] || pid;
    const path = window.location.pathname;
    let base = '/app';
    if (path.includes('/admin')) base = '/admin';
    else if (path.includes('/hod')) base = '/hod';
    else if (path.includes('/faculty')) base = '/faculty';
    else if (path.includes('/student')) base = '/student';

    const targetUrl = `${base}/${slug}`;
    if (window.location.pathname !== targetUrl) {
      if (replace) {
        window.history.replaceState({ page: pid }, '', targetUrl);
      } else {
        window.history.pushState({ page: pid }, '', targetUrl);
      }
    }
  } catch (err) {
    console.warn('[Routing] updateBrowserUrl error:', err);
  }
}

window.addEventListener('popstate', (e) => {
  const p = (e.state && e.state.page) || getPageFromUrl();
  if (p && typeof showPage === 'function') {
    showPage(p, true);
  }
});

function buildSideNav() {
  const nav = document.getElementById('sbNav');
  nav.innerHTML = '';
  (NAV_CFG[APP.role]||NAV_CFG.admin).forEach(grp => {
    const lbl = document.createElement('div');
    lbl.className = 'nav-section-lbl'; lbl.textContent = grp.section;
    nav.appendChild(lbl);
    grp.links.forEach(lnk => {
      const a = document.createElement('a');
      a.className='nav-link'; a.dataset.page=lnk.page;
      a.onclick = () => showPage(lnk.page);
      let pill = lnk.pill==='LIVE' ? '<span class="nav-pill live">LIVE</span>' :
                 lnk.pill==='alert' ? '<span class="nav-pill alert" id="navAlertPill" style="display:none">0</span>' : '';
      a.innerHTML = '<i class="fa '+lnk.icon+'"></i><span>'+lnk.label+'</span>'+pill;
      nav.appendChild(a);
    });
  });
}

function setTopbarProfile() {
  const label = getRoleLabel();
  const roleDisplay = {
    admin: 'Administrator',
    hod: 'Head of Department – CSE',
    classincharge: 'Class Incharge – CSE A 3rd Year',
    teacher: 'Teacher',
    faculty: 'Faculty'
  }[APP.role] || APP.role;
  const deptDisplay = {
    admin: 'Smart Attendance System',
    hod: 'CSE Department',
    classincharge: 'CSE Department',
    teacher: 'Smart Attendance System',
    faculty: 'My Portal'
  }[APP.role] || 'Smart Attendance System';
  setEl('sucAv', label.substring(0,2).toUpperCase());
  setEl('sucName', label);
  setEl('sucRole', roleDisplay);
  setEl('sucDept', deptDisplay);
  setEl('tbpAv', label.substring(0,2).toUpperCase());
  setEl('tbpName', label.split(' ')[0]);
  setEl('tbpRole', roleDisplay);
}

function showPage(pid, skipPush = false) {
  // ── Stop Reports page live timers when leaving it ──
  if (pid !== 'reports' && window._repPollTimer) { clearInterval(window._repPollTimer); window._repPollTimer = null; }
  if (pid !== 'reports' && window._repClockTimer) { clearInterval(window._repClockTimer); window._repClockTimer = null; }
  // ── TRAINING ROUTE GUARD: block non-admin access to train page ──
  if (pid === 'train' && APP.role !== 'admin') {
    console.warn('[RouteGuard] Training page blocked — role:', APP.role);
    toast('Access denied: AI Training is restricted to Admin only.', 'error');
    pid = APP.role === 'faculty' ? 'fac-dashboard' : 'dashboard';
  }
  // ── STUDENT TIMETABLE ROUTE GUARD: faculty must be Class In-Charge ──
  if (pid === 'timetable' && (APP.role === 'faculty' || APP.role === 'teacher')) {
    if (APP._isClassIncharge === false) {
      console.warn('[RouteGuard] Student Timetable blocked — not a Class In-Charge');
      toast('Access denied: Student Timetable is only available to Class In-Charge faculty.', 'error');
      pid = 'fac-dashboard';
    }
  }
  // ── LEAVE / OD APPROVALS ROUTE GUARD: faculty must be Class In-Charge ──
  if ((pid === 'fac-leave-approvals' || pid === 'fac-od-approvals') &&
      (APP.role === 'faculty' || APP.role === 'teacher')) {
    if (APP._isClassIncharge === false) {
      console.warn('[RouteGuard] ' + pid + ' blocked — not a Class In-Charge');
      toast('Access denied: Leave/OD Approvals are only available to Class In-Charge faculty.', 'error');
      pid = 'fac-dashboard';
    }
  }
  // ── ENROLL ROUTE GUARD: only Admin can access Enrollment page ──
  if (pid === 'students' && APP.role !== 'admin') {
    console.warn('[RouteGuard] Enrollment page blocked — role:', APP.role);
    toast('Access denied: Enrollment is restricted to Admin only.', 'error');
    pid = 'dashboard';
  }
  // ── HOD STUDENTS ROUTE GUARD: admin, hod, faculty only ──
  if (pid === 'hod-students' && !['admin','hod','faculty'].includes(APP.role)) {
    console.warn('[RouteGuard] Students Management blocked — role:', APP.role);
    toast('Access denied: Students Management is restricted to Admin, HOD, and Faculty.', 'error');
    pid = APP.role === 'faculty' ? 'fac-dashboard' : 'dashboard';
  }
  // ── HOD OD APPROVAL QUEUE ROUTE GUARD: hod only ──
  if (pid === 'hod-od-approvals' && APP.role !== 'hod') {
    console.warn('[RouteGuard] OD Approval Queue blocked — role:', APP.role);
    toast('Access denied: OD Approval Queue is restricted to HOD.', 'error');
    pid = APP.role === 'faculty' ? 'fac-dashboard' : 'dashboard';
  }

  // ── STRICT CROSS-ROLE PAGE GUARDS ──
  if (APP.role === 'faculty') {
    const facultyPages = ['fac-dashboard', 'my-timetable', 'timetable', 'reports', 'fac-leave-approvals', 'fac-od-approvals'];
    if (!facultyPages.includes(pid)) {
      console.warn('[RouteGuard] Faculty restricted page blocked:', pid);
      toast('Access denied: Page restricted to Admin/HOD.', 'error');
      pid = 'fac-dashboard';
    }
  } else if (APP.role === 'hod') {
    const adminOnlyPages = ['settings', 'train', 'audit_log', 'manage-hod', 'departments', 'students'];
    if (adminOnlyPages.includes(pid)) {
      console.warn('[RouteGuard] HOD restricted page blocked:', pid);
      toast('Access denied: Restricted to System Administrator.', 'error');
      pid = 'dashboard';
    }
  }

  document.querySelectorAll('.page').forEach(p => p.classList.add('dn'));
  document.querySelectorAll('.nav-link').forEach(a => a.classList.remove('active'));
  const pg = document.getElementById('pg-'+pid);
  if (pg) pg.classList.remove('dn');
  document.querySelector('[data-page="'+pid+'"]')?.classList.add('active');
  const tbTitle = (pid === 'departments' && APP.role === 'hod') ? 'Student Analytics' : (PAGE_TITLES[pid]||pid);
  setEl('tbPageTitle', tbTitle);
  syncPortalTabTitle(null, APP.role);
  APP.currentPage = pid;
  if(_token) sessionStorage.setItem("_lastPage", pid);
  if (!skipPush && typeof updateBrowserUrl === 'function') {
    updateBrowserUrl(pid);
  }
  closeSidebar();
  const init={dashboard:renderDashboard,attendance:initAttendancePage,students:renderStudentsPage,
    timetable:renderTimetablePage,overrides:renderOverridesPage,reports:renderReportsPage,
    alerts:renderAlertsPage,settings:renderSettingsPage,train:renderTrainPage,
    'fac-dashboard':renderFacDashboard,'manage-hod':renderManageHodPage,
    'my-timetable':renderMyTeachingTimetable,
    'fac-leave-approvals':renderFacLeaveApprovalsPage,
    'fac-od-approvals':renderFacODApprovalsPage,
    'hod-students':function(){ if (typeof hsRenderPage === 'function') hsRenderPage(); else console.error('[hod-students] hsRenderPage not loaded yet — check that hod_students.js is included.'); },
    departments:initDeptDrill,faculty:renderFacultyPage,
    correction:renderStudentCorrectionPage,
    hod_approvals:renderHODApprovalsPage,
    'hod-od-approvals':renderHODODApprovalsPage,
    audit_log:renderAuditLogPage,
    academics:renderAcademicsPage,
    compliance:renderCompliancePage,
    };
  init[pid]?.();
}

function toggleSidebar(){ document.getElementById('sidebar').classList.toggle('open'); }
function closeSidebar() { document.getElementById('sidebar').classList.remove('open'); }

function startClock() {
  const el = document.getElementById('tbClock');
  const t = () => { if(el) el.textContent = new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'}); };
  t(); setInterval(t,1000);
}

// ── DASHBOARD ─────────────────────────────────────────────────
async function renderDashboard() {
  if (APP.role==='faculty') { renderFacDashboard(); return; }
  const cont = document.getElementById('dashboardContent');
  if (!cont) return;
  cont.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading...</p></div>';
  try {
    const [data, today] = await Promise.all([api.analytics(), api.todayAtt()]);
    const {total_members:total,present_today:present,absent_today:absent,pct_today:pct,avg_attendance:avgAtt,critical_count:crit} = data;
    cont.innerHTML = `
      <div class="page-header">
        <div class="ph-left"><h2>${getRoleLabel()} Dashboard</h2>
        <p>${new Date().toLocaleDateString('en-IN',{weekday:'long',year:'numeric',month:'long',day:'numeric'})}</p></div>
      </div>
      <div class="kpi-strip">
        ${kpi('Total Members',total,'fa-users','#4ecba8')}
        ${kpi('Present Today',present,'fa-circle-check','#4da6f5')}
        ${kpi('Absent Today',absent,'fa-circle-xmark','#ff7070')}
        ${kpi('Today %',pct+'%','fa-percent','#ffb347')}
        ${kpi('30-day Avg',avgAtt+'%','fa-chart-line','#9b87f5')}
        ${kpi('Critical',crit,'fa-radiation','#e05454')}
        <div class="kpi-card" style="--kc:#9b87f5" id="complianceKpiCard"><div class="kpi-icon"><i class="fa fa-file-shield"></i></div><div class="kpi-val" id="complianceKpiVal">…</div><div class="kpi-lbl">Compliance Due (14d)</div></div>
      </div>
      <div class="two-col">
        <div class="card">
          <div class="card-head"><h4><i class="fa fa-list-check"></i> Today's Attendance</h4>
            <button class="btn-sm" onclick="exportTodayCSV()"><i class="fa fa-download"></i> CSV</button>
          </div>
          <div class="table-scroll"><table class="data-tbl">
            <thead><tr><th>Name</th><th>ID</th><th>Period</th><th>Time</th><th>Confidence</th><th>Engine</th></tr></thead>
            <tbody>${today.length?today.map(r=>'<tr><td><strong>'+(r.name||'?')+'</strong></td><td><code>'+(r.student_id||'?')+'</code></td><td>'+(r.period||'—')+'</td><td style="font-family:var(--mono)">'+String(r.time||'').slice(0,8)+'</td><td>'+confBadge(r.confidence)+'</td><td><span class="badge b-lav">'+(r.engine||'—')+'</span></td></tr>').join('')
            :'<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text3)">No attendance today — start a camera session</td></tr>'}</tbody>
          </table></div>
        </div>
        <div class="card">
          <div class="card-head"><h4><i class="fa fa-chart-pie"></i> Today Status</h4></div>
          <div class="chart-pad"><canvas id="dashDonut" height="200"></canvas></div>
        </div>
      </div>`;
    setTimeout(() => mkDonut('dashDonut',['Present','Absent','Critical'],[present,absent-crit,crit],['#4ecba8','#4da6f5','#ff7070']), 60);
    _loadComplianceKpi();
  } catch(e) {
    cont.innerHTML = '<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>'+e.message+'</p><button class="btn-primary" onclick="renderDashboard()"><i class="fa fa-rotate-right"></i> Retry</button></div>';
  }
}

// ── ATTENDANCE ─────────────────────────────────────────────────
//
// MJPEG STREAM DESIGN — read before editing:
//
//  The browser loads the MJPEG feed by pointing an <img> src at
//  /video_feed (a FastAPI StreamingResponse with multipart/x-mixed-replace).
//  The HTTP connection is opened ONCE when img.src is assigned and stays
//  open for the entire session.  The server pushes new JPEG frames down
//  the same connection continuously — the browser just paints each one.
//
//  Rules that must never be broken:
//   1. img.src is assigned EXACTLY ONCE per session (in startAttendance).
//   2. Nothing else touches img.src while the session is live except
//      stopAttendance (sets it to '') or the onerror recovery handler.
//   3. initAttendancePage bails out immediately if a live session is
//      already running so it never destroys the live <img>.
//   4. renderSessionStatus polls /api/session/status for the marked-list
//      sidebar ONLY — it never touches the <img> element.
//   5. The Stop button is the ONLY intentional way to end the stream.
//
// ──────────────────────────────────────────────────────────────

// Internal flag: true while the MJPEG stream is intentionally live.
// Set to true only by startAttendance, false only by stopAttendance
// or the unexpected-death handler in renderSessionStatus.
APP._streamLive = false;

function initAttendancePage() {
  // Delegate to attendance.js role-based logic
  clearInterval(APP.attPollTimer);
  APP.attPollTimer = null;
  if (typeof initAttendancePageRoleBased === 'function') {
    initAttendancePageRoleBased();
  } else {
    renderSessionStatus();
  }
}

// ── startAttendance / stopAttendance ─────────────────────────
// These functions are now implemented in attendance.js which
// provides full role-based attendance logic. The stubs below
// ensure no errors if called before attendance.js loads.
// They delegate immediately to the attendance.js implementations.

async function startAttendance() {
  if (typeof ATT !== 'undefined') {
    // attendance.js is loaded — its startAttendance is defined globally
    // The function is declared in attendance.js scope and overrides this
  }
  // Fallback toast if somehow called before attendance.js
  toast('Attendance module loading...', 'info');
}

async function stopAttendance() {
  if (typeof ATT !== 'undefined') {
    // handled by attendance.js
  }
}

function resetAttSession() {
  if (typeof attPollStatus === 'function') attPollStatus();
  else renderSessionStatus();
}

// ── renderSessionStatus ──────────────────────────────────────
// ── renderSessionStatus ──────────────────────────────────────
// Polls /api/session/status every 2500 ms while a session is live.
// Updates the attendance log panel on the right side of the screen.
// Does NOT touch the camera <img> or its src during normal operation.
//
// Exception: if the backend session thread dies unexpectedly (without
// the user pressing Stop), this function detects running=false while
// APP._streamLive is true, cleans up the UI, and shows an error.
async function renderSessionStatus() {
  try {
    const s = await api.sessionStatus();

    // ── Unexpected session death detection ───────────────────
    // If the backend reports running=false but we are still showing
    // the live camera, the recognition thread crashed or the camera
    // was lost.  Clean up the UI and inform the user.
    if (APP._streamLive && !s.running) {
      APP._streamLive = false;
      clearInterval(APP.attPollTimer);
      APP.attPollTimer = null;

      const img      = document.getElementById('mjpegImg');
      const idle     = document.getElementById('cvIdle');
      const tag      = document.getElementById('cvTag');
      const badge    = document.getElementById('cvLiveBadge');
      const btnStart = document.getElementById('btnStartCam');
      const btnStop  = document.getElementById('btnStopCam');

      if (img)   { img.src = ''; img.classList.add('dn'); }
      if (tag)   { tag.classList.add('dn'); }
      if (badge) { badge.classList.add('dn'); }
      if (idle) {
        idle.classList.remove('dn');
        idle.innerHTML =
          '<div class="cv-idle-icon">' +
            '<i class="fa fa-triangle-exclamation" style="color:var(--coral-d)"></i>' +
          '</div>' +
          '<h4 style="color:var(--coral-d)">Session Ended</h4>' +
          '<p>' + (s.error || 'Session stopped unexpectedly. Check that the camera is free and restart.') + '</p>';
      }
      if (btnStart) btnStart.disabled = false;
      if (btnStop)  btnStop.disabled  = true;

      toast(s.error || 'Session ended unexpectedly \u2014 check camera availability.', 'warn');
      return;
    }

    // ── Normal status update ─────────────────────────────────
    setEl('alcP', s.marked_count + ' Present');
    setEl('alcA', s.absent_count + ' Absent');
    const bar = document.getElementById('alcProgBar');
    if (bar && s.total_students > 0)
      bar.style.width = Math.min(s.marked_count / s.total_students * 100, 100) + '%';

    const body = document.getElementById('alcBody');
    if (!body) return;
    if (!s.already_marked?.length) {
      body.innerHTML = '<div class="alc-empty"><i class="fa fa-inbox"></i><p>No entries yet</p></div>';
    } else {
      body.innerHTML = s.already_marked.map(r =>
        '<div class="log-entry">' +
          '<div class="le-av p">' + initials(r.name) + '</div>' +
          '<div>' +
            '<div class="le-name">' + r.name + '</div>' +
            '<div class="le-meta">' + r.student_id + '</div>' +
          '</div>' +
          '<span class="le-time">' + r.time + '</span>' +
        '</div>'
      ).join('');
    }
  } catch (e) {
    // Silently swallow poll errors — network blip should not crash the UI
  }
}

function resetAttSession() { renderSessionStatus(); }
// openOverrideFromAtt defined in v10.1 block

async function exportTodayCSV() {
  try {
    const res = await api.exportCsv();
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement('a'), {
      href: url,
      download: 'attendance_' + new Date().toISOString().slice(0, 10) + '.csv'
    });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('CSV exported!', 'success');
  } catch(e) { toast('Export failed: ' + e.message, 'error'); }
}

// ── ENROLL HUB (replaces Students page) ──────────────────────
function renderStudentsPage() { renderEnrollPage(); }

function renderEnrollPage() {
  const cont = document.getElementById('pg-students');
  if (!cont) return;

  const DEPTS = ['CSE','IT','ECE','EEE','MECH','CIVIL','AIDS','AIML','CSBS','BME'];
  const DESIG = ['Professor','Associate Professor','Assistant Professor','Senior Lecturer','Lecturer','Lab Instructor'];
  const YEARS = ['1st Year','2nd Year','3rd Year','4th Year'];
  const COURSES = ['B.E','B.Tech','B.Sc','M.E','M.Tech','M.Sc','MBA','MCA','Diploma'];

  const icOptions = DEPTS.map(d=>
    ['1','2','3','4'].map(y=>
      ['A','B','C'].map(s=>`<option value="${d}|${y}|${s}">${d} Year-${y} Sec-${s}</option>`).join('')
    ).join('')
  ).join('');

  cont.innerHTML = `
  <style>
    .enroll-hub-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-bottom:2rem;}
    @media(max-width:700px){.enroll-hub-grid{grid-template-columns:1fr;}}
    .erc{background:var(--card-bg);border:2px solid var(--border);border-radius:16px;padding:2rem 1.5rem;text-align:center;cursor:pointer;transition:all .2s;position:relative;overflow:hidden;}
    .erc:hover{box-shadow:0 8px 32px rgba(79,142,247,.15);transform:translateY(-3px);}
    .erc .erc-icon{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.6rem;margin:0 auto 1rem;}
    .erc h3{font-size:1.1rem;font-weight:700;margin:0 0 .35rem;}
    .erc p{font-size:.82rem;color:var(--text3);margin:0 0 1.2rem;}
    .erc .erc-badge{position:absolute;top:14px;right:14px;font-size:.68rem;font-weight:700;padding:3px 9px;border-radius:20px;}
    .row-action-wrap{position:relative;display:inline-block;}
    .btn-action-trigger{width:32px;height:32px;border-radius:8px;border:1px solid #cbd5e1;background:#fff;color:#64748b;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:.95rem;transition:all .15s ease;}
    .btn-action-trigger:hover,.btn-action-trigger.active{background:#f1f5f9;color:#0f172a;border-color:#94a3b8;box-shadow:0 1px 3px rgba(0,0,0,.08);}
    .action-dropdown-menu{position:absolute;right:0;top:calc(100% + 4px);background:#fff;border:1px solid #e2e8f0;border-radius:10px;box-shadow:0 10px 25px -5px rgba(0,0,0,.12),0 8px 10px -6px rgba(0,0,0,.08);min-width:170px;padding:6px 0;z-index:1050;display:none;text-align:left;}
    .action-dropdown-menu.show{display:block;}
    .action-dropdown-item{display:flex;align-items:center;gap:10px;padding:8px 16px;font-size:.83rem;font-weight:500;color:#334155;cursor:pointer;text-decoration:none;transition:background .12s,color .12s;white-space:nowrap;}
    .action-dropdown-item i{font-size:.88rem;width:18px;text-align:center;}
    .action-dropdown-item:hover{background:#f8fafc;color:#0f172a;}
    .action-dropdown-item.danger{color:#ef4444;}
    .action-dropdown-item.danger:hover{background:#fef2f2;color:#dc2626;}
    .enroll-panel{display:none;animation:epFade .25s ease;}
    .enroll-panel.active{display:block;}
    @keyframes epFade{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
    .ep-back{display:flex;align-items:center;gap:8px;background:var(--bg);border:1.5px solid var(--border);border-radius:10px;padding:8px 16px;cursor:pointer;font-size:.85rem;font-weight:600;color:var(--text2);margin-bottom:1.2rem;width:fit-content;transition:all .15s;}
    .ep-back:hover{border-color:var(--accent);color:var(--accent);}
    .reenroll-banner{border-radius:12px;padding:1rem 1.2rem;margin-bottom:1rem;display:none;}
    .reenroll-banner p{margin:0 0 .6rem;font-size:.88rem;}
    .reenroll-banner .rba{display:flex;gap:8px;flex-wrap:wrap;}
    .er-title{font-size:.75rem;font-weight:700;letter-spacing:.08em;color:#0284c7;text-transform:uppercase;margin:0 0 10px;padding-bottom:6px;border-bottom:2px solid #bae6fd;display:flex;align-items:center;gap:6px;}
    .er-g2{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
    .er-g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;}
    .er-g4{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;}
    .efg{display:flex;flex-direction:column;gap:4px;}
    .efg label{font-size:.78rem;font-weight:600;color:var(--text2);}
    .efg .req{color:#ef4444;}
    .efg input,.efg select{border:1.5px solid var(--border);border-radius:8px;padding:8px 10px;font-size:.875rem;background:var(--card-bg);color:var(--text1);width:100%;box-sizing:border-box;transition:border-color .15s;}
    .efg input:focus,.efg select:focus{outline:none;border-color:#0284c7;box-shadow:0 0 0 3px rgba(2,132,199,.12);}
    .enroll-result{display:none;margin-top:14px;padding:14px;border-radius:10px;font-size:.88rem;}
    @media(max-width:640px){.er-g3,.er-g4{grid-template-columns:1fr 1fr;}.er-g2{grid-template-columns:1fr;}}
    @media(max-width:420px){.er-g3,.er-g4,.er-g2{grid-template-columns:1fr;}}
  </style>

  <!-- PAGE HEADER -->
  <div class="page-header" style="margin-bottom:1.5rem;">
    <div class="ph-left">
      <h2 style="font-size:1.4rem;font-weight:800;color:var(--text1);margin:0;"><i class="fa fa-user-plus" style="color:#0284c7;margin-right:8px"></i>Enrollment Management</h2>
    </div>
  </div>

  <!-- HUB: Tables Container -->
  <div id="enrollHub">
    <!-- Hidden KPI strip to avoid breaking existing code -->
    <div id="enrollKpiStrip" style="display:none;"></div>

    <!-- ══ Enrolled Students Table ══ -->
    <div class="card" style="margin-bottom:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.05);border-radius:14px;overflow:visible;">
      <div class="card-head" style="background:#ffffff;border-bottom:1px solid var(--border);border-radius:14px 14px 0 0;flex-wrap:wrap;gap:12px;padding:1.1rem 1.4rem;">
        <h4 style="color:#0284c7;font-size:1.05rem;font-weight:700;display:flex;align-items:center;gap:8px;margin:0;">
          <i class="fa fa-user-graduate"></i> Enrolled Students
        </h4>
        <div class="ch-actions" style="flex-wrap:wrap;gap:10px;align-items:center;">
          <div style="position:relative;">
            <i class="fa fa-search" style="position:absolute;left:10px;top:50%;transform:translateY(-50%);color:#94a3b8;font-size:.85rem;pointer-events:none;"></i>
            <input id="stuSearch" placeholder="Search name, register no, dept..." oninput="filterStudents()" style="padding-left:32px;padding-right:12px;border-radius:8px;border:1px solid #cbd5e1;padding-top:7px;padding-bottom:7px;font-size:.84rem;min-width:240px;background:#fff;color:var(--text1);outline:none;"/>
          </div>
          <select id="stuDeptFilter" onchange="filterStudents()" style="border:1px solid #cbd5e1;border-radius:8px;padding:7px 12px;font-size:.84rem;background:var(--card-bg,#fff);color:var(--text1);cursor:pointer;">
            <option value="">All Departments</option>
            ${DEPTS.map(d=>`<option value="${d}">${d}</option>`).join('')}
          </select>
          <button class="btn-primary" onclick="openEnrollPanel('student')" style="font-size:.84rem;font-weight:600;background:#0284c7;border-radius:8px;padding:8px 16px;display:flex;align-items:center;gap:6px;box-shadow:0 2px 6px rgba(2,132,199,.25);">
            <i class="fa fa-user-plus"></i> Enroll Student
          </button>
        </div>
      </div>
      <div class="table-scroll" style="overflow-x:auto;padding-bottom:12px;">
        <table class="data-tbl" id="stuTable" style="width:100%;min-width:980px;">
          <thead><tr>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">#</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">REGISTER NO</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">ROLL NO</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">NAME</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">GENDER</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">DEPT</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">COURSE</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">YEAR</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">SECTION</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">MOBILE</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">STATUS</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">ENROLLED ON</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;text-align:center;">ACTIONS</th>
          </tr></thead>
          <tbody id="stuTbody">
            <tr><td colspan="13" style="text-align:center;padding:24px"><i class="fa fa-spinner fa-spin"></i> Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ══ Enrolled Faculty Table ══ -->
    <div class="card" style="margin-bottom:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.05);border-radius:14px;overflow:visible;">
      <div class="card-head" style="background:#ffffff;border-bottom:1px solid var(--border);border-radius:14px 14px 0 0;flex-wrap:wrap;gap:12px;padding:1.1rem 1.4rem;">
        <h4 style="color:#16a34a;font-size:1.05rem;font-weight:700;display:flex;align-items:center;gap:8px;margin:0;">
          <i class="fa fa-chalkboard-user"></i> Enrolled Faculty
        </h4>
        <div class="ch-actions" style="flex-wrap:wrap;gap:10px;align-items:center;">
          <div style="position:relative;">
            <i class="fa fa-search" style="position:absolute;left:10px;top:50%;transform:translateY(-50%);color:#94a3b8;font-size:.85rem;pointer-events:none;"></i>
            <input id="facHubSearch" placeholder="Search name, faculty ID, dept..." oninput="filterFacHub()" style="padding-left:32px;padding-right:12px;border-radius:8px;border:1px solid #cbd5e1;padding-top:7px;padding-bottom:7px;font-size:.84rem;min-width:240px;background:#fff;color:var(--text1);outline:none;"/>
          </div>
          <select id="facHubDeptFilter" onchange="filterFacHub()" style="border:1px solid #cbd5e1;border-radius:8px;padding:7px 12px;font-size:.84rem;background:var(--card-bg,#fff);color:var(--text1);cursor:pointer;">
            <option value="">All Departments</option>
            ${DEPTS.map(d=>`<option value="${d}">${d}</option>`).join('')}
          </select>
          <button class="btn-primary" onclick="openEnrollPanel('faculty')" style="font-size:.84rem;font-weight:600;background:#16a34a;border-radius:8px;padding:8px 16px;display:flex;align-items:center;gap:6px;box-shadow:0 2px 6px rgba(22,163,74,.25);">
            <i class="fa fa-user-plus"></i> Enroll Faculty
          </button>
        </div>
      </div>
      <div class="table-scroll" style="overflow-x:auto;padding-bottom:12px;">
        <table class="data-tbl" id="facHubTable" style="width:100%;min-width:920px;">
          <thead><tr>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">#</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">FACULTY ID</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">NAME</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">DEPARTMENT</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">DESIGNATION</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">EMAIL</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">MOBILE</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">STATUS</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">ENROLLED ON</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;text-align:center;">ACTIONS</th>
          </tr></thead>
          <tbody id="facHubTbody">
            <tr><td colspan="10" style="text-align:center;padding:24px"><i class="fa fa-spinner fa-spin"></i> Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ══ Enrolled HODs Table ══ -->
    <div class="card" style="margin-bottom:1.5rem;box-shadow:0 1px 4px rgba(0,0,0,.05);border-radius:14px;overflow:visible;">
      <div class="card-head" style="background:#ffffff;border-bottom:1px solid var(--border);border-radius:14px 14px 0 0;flex-wrap:wrap;gap:12px;padding:1.1rem 1.4rem;">
        <h4 style="color:#9333ea;font-size:1.05rem;font-weight:700;display:flex;align-items:center;gap:8px;margin:0;">
          <i class="fa fa-user-tie"></i> Enrolled HODs
        </h4>
        <div class="ch-actions" style="flex-wrap:wrap;gap:10px;align-items:center;">
          <div style="position:relative;">
            <i class="fa fa-search" style="position:absolute;left:10px;top:50%;transform:translateY(-50%);color:#94a3b8;font-size:.85rem;pointer-events:none;"></i>
            <input id="hodHubSearch" placeholder="Search name, HOD ID, dept..." oninput="filterHodHub()" style="padding-left:32px;padding-right:12px;border-radius:8px;border:1px solid #cbd5e1;padding-top:7px;padding-bottom:7px;font-size:.84rem;min-width:240px;background:#fff;color:var(--text1);outline:none;"/>
          </div>
          <select id="hodHubDeptFilter" onchange="filterHodHub()" style="border:1px solid #cbd5e1;border-radius:8px;padding:7px 12px;font-size:.84rem;background:var(--card-bg,#fff);color:var(--text1);cursor:pointer;">
            <option value="">All Departments</option>
            ${DEPTS.map(d=>`<option value="${d}">${d}</option>`).join('')}
          </select>
          <button class="btn-primary" onclick="openEnrollPanel('hod')" style="font-size:.84rem;font-weight:600;background:#9333ea;border-radius:8px;padding:8px 16px;display:flex;align-items:center;gap:6px;box-shadow:0 2px 6px rgba(147,51,234,.25);">
            <i class="fa fa-user-plus"></i> Enroll HOD
          </button>
        </div>
      </div>
      <div class="table-scroll" style="overflow-x:auto;padding-bottom:12px;">
        <table class="data-tbl" id="hodHubTable" style="width:100%;min-width:920px;">
          <thead><tr>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">#</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">HOD ID</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">NAME</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">DEPARTMENT</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">DESIGNATION</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">EMAIL</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">MOBILE</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">STATUS</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;">ENROLLED ON</th>
            <th style="font-size:.74rem;letter-spacing:.05em;color:var(--text3);font-weight:700;text-align:center;">ACTIONS</th>
          </tr></thead>
          <tbody id="hodHubTbody">
            <tr><td colspan="10" style="text-align:center;padding:24px"><i class="fa fa-spinner fa-spin"></i> Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

  </div><!-- /enrollHub -->

  <!-- ═══ STUDENT PANEL ═══ -->
  <div id="enrollPanel-student" class="enroll-panel">
    <button class="ep-back" onclick="closeEnrollPanel()"><i class="fa fa-arrow-left"></i> Back to Enroll Hub</button>
    <div class="card" style="max-width:900px;margin:0 auto;">
      <div class="card-head" style="background:linear-gradient(135deg,#e0f2fe,#f0f9ff);border-radius:12px 12px 0 0;">
        <h4 style="color:#0284c7;"><i class="fa fa-user-graduate"></i> Student Enrollment</h4>
        <span style="font-size:.78rem;color:var(--text3)">Fields marked <span style="color:#ef4444">*</span> are required</span>
      </div>
      <div style="padding:1.25rem;">
        <!-- Re-enroll banner -->
        <div class="reenroll-banner" id="stuReBanner" style="background:#fff8e1;border:1.5px solid #f9a825;">
          <p id="stuReMsg"><i class="fa fa-triangle-exclamation"></i> <strong>Student already exists.</strong> Do you want to enroll again?</p>
          <div class="rba">
            <button class="btn-primary" onclick="confirmReenroll('student',true)"><i class="fa fa-camera"></i> Yes — Re-Enroll (Open Camera)</button>
            <button class="btn-secondary" onclick="confirmReenroll('student',false)"><i class="fa fa-xmark"></i> No — Skip Camera</button>
          </div>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:8px 14px;flex-wrap:wrap;gap:8px;">
          <span style="font-size:.82rem;color:#0369a1;font-weight:600;"><i class="fa fa-wand-magic-sparkles" style="margin-right:6px"></i>Smart Fill: Enter Register No to auto-complete or click Voice Fill</span>
          <button type="button" id="btnVoiceFillStu" onclick="startVoiceEnroll('student')" style="background:#0284c7;color:#fff;border-radius:20px;padding:6px 16px;font-size:.78rem;font-weight:700;display:flex;align-items:center;gap:6px;box-shadow:0 2px 6px rgba(2,132,199,.25);cursor:pointer;border:none;">
            <i class="fa fa-microphone"></i> <span>Voice Fill</span>
          </button>
        </div>

        <div class="er-title"><i class="fa fa-id-card"></i> Identity</div>
        <div class="er-g2">
          <div class="efg"><label>Register Number <span class="req">*</span></label>
            <input id="en_reg" placeholder="e.g. 23CS086" oninput="checkEnrollExists('student'); if(window.onStudentRegInput) window.onStudentRegInput(this.value);"/></div>
          <div class="efg"><label>Roll Number <span class="req">*</span></label>
            <input id="en_roll" placeholder="e.g. 23CS086"/></div>
        </div>
        <div class="er-g2" style="margin-top:10px;">
          <div class="efg"><label>First Name <span class="req">*</span></label>
            <input id="en_fname" placeholder="e.g. Suganya"/></div>
          <div class="efg"><label>Last Name <span class="req">*</span></label>
            <input id="en_lname" placeholder="e.g. ADMIN"/></div>
        </div>
        <div class="er-g2" style="margin-top:10px;">
          <div class="efg"><label>Gender <span class="req">*</span></label>
            <select id="en_gender">
              <option value="">Select Gender</option>
              <option>Male</option><option>Female</option><option>Other</option>
            </select></div>
          <div class="efg"><label>Date of Birth <span class="req">*</span></label>
            <input id="en_dob" type="date"/></div>
        </div>

        <div class="er-title" style="margin-top:18px;"><i class="fa fa-building-columns"></i> Academic Details</div>
        <div class="er-g4">
          <div class="efg"><label>Department</label>
            <select id="en_dept">
              <option value="">Select Dept</option>
              ${DEPTS.map(d=>`<option value="${d}">${d}</option>`).join('')}
            </select></div>
          <div class="efg"><label>Course</label>
            <select id="en_course">
              <option value="">Select Course</option>
              ${COURSES.map(c=>`<option value="${c}">${c}</option>`).join('')}
            </select></div>
          <div class="efg"><label>Year <span class="req">*</span></label>
            <select id="en_year">
              <option value="">Select Year</option>
              ${YEARS.map(y=>`<option value="${y}">${y}</option>`).join('')}
            </select></div>
          <div class="efg"><label>Section</label>
            <select id="en_section">
              ${['A','B','C','D'].map(s=>`<option value="${s}">${s}</option>`).join('')}
            </select></div>
        </div>
        <div class="er-g2" style="margin-top:10px;">
          <div class="efg"><label>Twin of (Student ID) <span style="font-size:0.75rem;font-weight:normal;color:var(--text3);">(Optional)</span></label>
            <input id="en_twin" placeholder="e.g. STU_... (leave blank if not a twin)"/></div>
        </div>

        <div class="er-title" style="margin-top:18px;"><i class="fa fa-envelope"></i> Contact Details</div>
        <div class="er-g2">
          <div class="efg">
            <label>Student Email <span class="req">*</span></label>
            <div style="display:flex;gap:6px;align-items:flex-start;">
              <input id="en_semail" type="email" placeholder="student@gmail.com"
                     style="flex:1;" oninput="smfOtp.onEmailInput()"
                     onblur="smfOtp.onEmailBlur()"/>
              <button type="button" id="btnSendOtp"
                      onclick="smfOtp.sendOtp()"
                      style="display:none;white-space:nowrap;padding:8px 14px;
                             background:#0284c7;color:#fff;border:none;border-radius:8px;
                             font-size:.8rem;font-weight:600;cursor:pointer;flex-shrink:0;">
                <i class="fa fa-paper-plane"></i> Send OTP
              </button>
            </div>
            <div id="en_semail_status" style="font-size:.78rem;margin-top:4px;"></div>
            <!-- OTP input section (hidden until OTP sent) -->
            <div id="smfOtpSection" style="display:none;margin-top:10px;">
              <div style="display:flex;gap:6px;align-items:center;">
                <input id="en_otp_input" type="text" inputmode="numeric"
                       maxlength="6" placeholder="Enter 6-digit OTP"
                       style="flex:1;letter-spacing:4px;font-size:1rem;font-weight:700;
                              text-align:center;padding:10px;"
                       oninput="smfOtp.onOtpInput(this.value)"/>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
                <span id="smfOtpTimer" style="font-size:.78rem;color:#64748b;"></span>
                <button type="button" id="btnResendOtp"
                        onclick="smfOtp.resendOtp()"
                        style="display:none;font-size:.78rem;background:none;border:none;
                               color:#0284c7;cursor:pointer;text-decoration:underline;">
                  Resend OTP
                </button>
              </div>
              <div id="smfOtpMsg" style="font-size:.78rem;margin-top:4px;"></div>
            </div>
          </div>
          <div class="efg"><label>Parent Email</label>
            <input id="en_pemail" type="email" placeholder="parent@gmail.com"/></div>
        </div>
        <div class="er-g2" style="margin-top:10px;">
          <div class="efg"><label>Student Mobile</label>
            <input id="en_smob" type="tel" placeholder="10-digit number"/></div>
          <div class="efg"><label>Parent Mobile</label>
            <input id="en_pmob" type="tel" placeholder="10-digit number"/></div>
        </div>

        <div style="margin-top:22px;display:flex;gap:10px;justify-content:flex-end;border-top:1px solid var(--border);padding-top:16px;">
          <button class="btn-secondary" onclick="closeEnrollPanel()"><i class="fa fa-xmark"></i> Cancel</button>
          <button class="btn-primary" id="btnStuEnroll" onclick="doEnrollStudent()"
                  disabled title="Student email must be verified before enrollment.">
            <i class="fa fa-user-plus"></i> Enroll Student
          </button>
        </div>
        <div class="enroll-result" id="stuEnrollResult"></div>
      </div>
    </div>
  </div>

  <!-- ═══ FACULTY PANEL ═══ -->
  <div id="enrollPanel-faculty" class="enroll-panel">
    <button class="ep-back" onclick="closeEnrollPanel()"><i class="fa fa-arrow-left"></i> Back to Enroll Hub</button>
    <div class="card" style="max-width:900px;margin:0 auto;">
      <div class="card-head" style="background:linear-gradient(135deg,#dcfce7,#f0fdf4);border-radius:12px 12px 0 0;">
        <h4 style="color:#16a34a;"><i class="fa fa-chalkboard-user"></i> Faculty Enrollment</h4>
        <span style="font-size:.78rem;color:var(--text3)">Fields marked <span style="color:#ef4444">*</span> are required</span>
      </div>
      <div style="padding:1.25rem;">
        <div class="reenroll-banner" id="facReBanner" style="background:#f0fdf4;border:1.5px solid #16a34a;">
          <p id="facReMsg"><i class="fa fa-triangle-exclamation"></i> <strong>Faculty already exists.</strong> Do you want to enroll again?</p>
          <div class="rba">
            <button class="btn-primary" style="background:#16a34a;" onclick="confirmReenroll('faculty',true)"><i class="fa fa-camera"></i> Yes — Re-Enroll (Open Camera)</button>
            <button class="btn-secondary" onclick="confirmReenroll('faculty',false)"><i class="fa fa-xmark"></i> No — Skip Camera</button>
          </div>
        </div>

        <div class="er-title"><i class="fa fa-id-card"></i> Identity</div>
        <div class="er-g3">
          <div class="efg"><label>Faculty ID <span class="req">*</span></label>
            <input id="sf_id" placeholder="e.g. FAC002" style="font-family:monospace;font-weight:700;text-transform:uppercase"
              oninput="this.value=this.value.toUpperCase();checkEnrollExists('faculty')"/></div>
          <div class="efg"><label>Employee Code</label>
            <input id="sf_empcode" placeholder="e.g. EMP2024001"/></div>
          <div class="efg"><label>Date of Birth <span class="req">*</span></label>
            <input id="sf_dob" type="date"/></div>
        </div>
        <div class="er-g3" style="margin-top:10px;">
          <div class="efg"><label>First Name <span class="req">*</span></label>
            <input id="sf_fname" placeholder="e.g. Ajay"/></div>
          <div class="efg"><label>Last Name <span class="req">*</span></label>
            <input id="sf_lname" placeholder="e.g. Kumar"/></div>
          <div class="efg"><label>Gender <span class="req">*</span></label>
            <select id="sf_gender">
              <option value="">Select</option>
              <option>Male</option><option>Female</option><option>Other</option>
            </select></div>
        </div>

        <div class="er-title" style="margin-top:18px;"><i class="fa fa-building-columns"></i> Academic Details</div>
        <div class="er-g3">
          <div class="efg"><label>Department <span class="req">*</span></label>
            <select id="sf_dept">
              <option value="">Select Dept</option>
              ${DEPTS.map(d=>`<option value="${d}">${d}</option>`).join('')}
            </select></div>
          <div class="efg"><label>Designation</label>
            <select id="sf_designation">
              <option value="">Select</option>
              ${DESIG.map(d=>`<option value="${d}">${d}</option>`).join('')}
            </select></div>
          <div class="efg"><label>Joining Date</label>
            <input id="sf_join" type="date"/></div>
        </div>

        <div class="er-title" style="margin-top:18px;"><i class="fa fa-envelope"></i> Contact</div>
        <div class="er-g3">
          <div class="efg" style="grid-column:1/-1;">
            <label>Email <span class="req">*</span></label>
            <div style="display:flex;gap:6px;align-items:flex-start;">
              <input id="sf_email" type="email" placeholder="faculty@college.edu"
                     style="flex:1;" oninput="smfOtpFac.onEmailInput()"
                     onblur="smfOtpFac.onEmailBlur()"/>
              <button type="button" id="btnSendOtpFac"
                      onclick="smfOtpFac.sendOtp()"
                      style="display:none;white-space:nowrap;padding:8px 14px;
                             background:#0284c7;color:#fff;border:none;border-radius:8px;
                             font-size:.8rem;font-weight:600;cursor:pointer;flex-shrink:0;">
                <i class="fa fa-paper-plane"></i> Send OTP
              </button>
            </div>
            <div id="sf_email_status" style="font-size:.78rem;margin-top:4px;"></div>
            <div id="smfOtpSectionFac" style="display:none;margin-top:10px;">
              <div style="display:flex;gap:6px;align-items:center;">
                <input id="sf_otp_input" type="text" inputmode="numeric"
                       maxlength="6" placeholder="Enter 6-digit OTP"
                       style="flex:1;letter-spacing:4px;font-size:1rem;font-weight:700;
                              text-align:center;padding:10px;"
                       oninput="smfOtpFac.onOtpInput(this.value)"/>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
                <span id="smfOtpTimerFac" style="font-size:.78rem;color:#64748b;"></span>
                <button type="button" id="btnResendOtpFac"
                        onclick="smfOtpFac.resendOtp()"
                        style="display:none;font-size:.78rem;background:none;border:none;
                               color:#0284c7;cursor:pointer;text-decoration:underline;">
                  Resend OTP
                </button>
              </div>
              <div id="smfOtpMsgFac" style="font-size:.78rem;margin-top:4px;"></div>
            </div>
          </div>
          <div class="efg"><label>Mobile</label>
            <input id="sf_mobile" type="tel" placeholder="10-digit number"/></div>
          <div class="efg"><label>Class Incharge Of</label>
            <select id="sf_incharge">
              <option value="">— Not a class incharge —</option>
              ${icOptions}
            </select></div>
        </div>

        <div style="margin-top:22px;display:flex;gap:10px;justify-content:flex-end;border-top:1px solid var(--border);padding-top:16px;">
          <button class="btn-secondary" onclick="closeEnrollPanel()"><i class="fa fa-xmark"></i> Cancel</button>
          <button class="btn-primary" id="btnFacEnroll" onclick="doEnrollFaculty()" style="background:#16a34a;">
            <i class="fa fa-user-plus"></i> Enroll Faculty
          </button>
        </div>
        <div class="enroll-result" id="facEnrollResult"></div>
      </div>
    </div>
    <div class="card" style="max-width:900px;margin:1.2rem auto 0;">
      <div class="card-head">
        <h4><i class="fa fa-users"></i> Enrolled Faculty</h4>
        <button class="btn-sm" onclick="loadFacTable()"><i class="fa fa-rotate-right"></i> Refresh</button>
      </div>
      <div class="table-scroll">
        <table class="data-tbl">
          <thead><tr><th>Faculty ID</th><th>Name</th><th>Dept</th><th>Designation</th><th>Email</th><th>Mobile</th><th>Enrolled On</th></tr></thead>
          <tbody id="facEnrollTbody"><tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text3)">Click Refresh to load</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ═══ HOD PANEL ═══ -->
  <div id="enrollPanel-hod" class="enroll-panel">
    <button class="ep-back" onclick="closeEnrollPanel()"><i class="fa fa-arrow-left"></i> Back to Enroll Hub</button>
    <div class="card" style="max-width:900px;margin:0 auto;">
      <div class="card-head" style="background:linear-gradient(135deg,#faf5ff,#f5f3ff);border-radius:12px 12px 0 0;">
        <h4 style="color:#9333ea;"><i class="fa fa-user-tie"></i> HOD Enrollment</h4>
        <span style="font-size:.78rem;color:var(--text3)">Fields marked <span style="color:#ef4444">*</span> are required</span>
      </div>
      <div style="padding:1.25rem;">
        <div class="reenroll-banner" id="hodReBanner" style="background:#faf5ff;border:1.5px solid #9333ea;">
          <p id="hodReMsg"><i class="fa fa-triangle-exclamation"></i> <strong>HOD already exists.</strong> Do you want to enroll again?</p>
          <div class="rba">
            <button class="btn-primary" style="background:#9333ea;" onclick="confirmReenroll('hod',true)"><i class="fa fa-camera"></i> Yes — Re-Enroll (Open Camera)</button>
            <button class="btn-secondary" onclick="confirmReenroll('hod',false)"><i class="fa fa-xmark"></i> No — Skip Camera</button>
          </div>
        </div>

        <div class="er-title"><i class="fa fa-id-card"></i> Identity</div>
        <div class="er-g3">
          <div class="efg"><label>HOD ID <span class="req">*</span></label>
            <input id="hf_id" placeholder="e.g. HOD002" style="font-family:monospace;font-weight:700;text-transform:uppercase"
              oninput="this.value=this.value.toUpperCase();checkEnrollExists('hod')"/></div>
          <div class="efg"><label>Employee Code</label>
            <input id="hf_empcode" placeholder="e.g. EMP2024HOD01"/></div>
          <div class="efg"><label>Date of Birth <span class="req">*</span></label>
            <input id="hf_dob" type="date"/></div>
        </div>
        <div class="er-g3" style="margin-top:10px;">
          <div class="efg"><label>First Name <span class="req">*</span></label>
            <input id="hf_fname" placeholder="e.g. Dr. Vimala"/></div>
          <div class="efg"><label>Last Name <span class="req">*</span></label>
            <input id="hf_lname" placeholder="e.g. Rani"/></div>
          <div class="efg"><label>Gender <span class="req">*</span></label>
            <select id="hf_gender">
              <option value="">Select</option>
              <option>Male</option><option>Female</option><option>Other</option>
            </select></div>
        </div>

        <div class="er-title" style="margin-top:18px;"><i class="fa fa-building-columns"></i> Academic Details</div>
        <div class="er-g3">
          <div class="efg"><label>Department <span class="req">*</span></label>
            <select id="hf_dept">
              <option value="">Select Dept</option>
              ${DEPTS.map(d=>`<option value="${d}">${d}</option>`).join('')}
            </select></div>
          <div class="efg"><label>Joining Date</label>
            <input id="hf_join" type="date"/></div>
          <div class="efg"><label>Qualification</label>
            <input id="hf_qual" placeholder="e.g. Ph.D, M.E"/></div>
        </div>

        <div class="er-title" style="margin-top:18px;"><i class="fa fa-envelope"></i> Contact</div>
        <div class="er-g3">
          <div class="efg" style="grid-column:1/-1;">
            <label>Email <span class="req">*</span></label>
            <div style="display:flex;gap:6px;align-items:flex-start;">
              <input id="hf_email" type="email" placeholder="hod@college.edu"
                     style="flex:1;" oninput="smfOtpHod.onEmailInput()"
                     onblur="smfOtpHod.onEmailBlur()"/>
              <button type="button" id="btnSendOtpHod"
                      onclick="smfOtpHod.sendOtp()"
                      style="display:none;white-space:nowrap;padding:8px 14px;
                             background:#0284c7;color:#fff;border:none;border-radius:8px;
                             font-size:.8rem;font-weight:600;cursor:pointer;flex-shrink:0;">
                <i class="fa fa-paper-plane"></i> Send OTP
              </button>
            </div>
            <div id="hf_email_status" style="font-size:.78rem;margin-top:4px;"></div>
            <div id="smfOtpSectionHod" style="display:none;margin-top:10px;">
              <div style="display:flex;gap:6px;align-items:center;">
                <input id="hf_otp_input" type="text" inputmode="numeric"
                       maxlength="6" placeholder="Enter 6-digit OTP"
                       style="flex:1;letter-spacing:4px;font-size:1rem;font-weight:700;
                              text-align:center;padding:10px;"
                       oninput="smfOtpHod.onOtpInput(this.value)"/>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px;">
                <span id="smfOtpTimerHod" style="font-size:.78rem;color:#64748b;"></span>
                <button type="button" id="btnResendOtpHod"
                        onclick="smfOtpHod.resendOtp()"
                        style="display:none;font-size:.78rem;background:none;border:none;
                               color:#0284c7;cursor:pointer;text-decoration:underline;">
                  Resend OTP
                </button>
              </div>
              <div id="smfOtpMsgHod" style="font-size:.78rem;margin-top:4px;"></div>
            </div>
          </div>
          <div class="efg"><label>Mobile</label>
            <input id="hf_mobile" type="tel" placeholder="10-digit number"/></div>
          <div class="efg"><label>&nbsp;</label>
            <div style="font-size:.78rem;color:var(--text3);padding:9px;background:var(--bg);border-radius:8px;border:1px solid var(--border);">
              <i class="fa fa-circle-info"></i> HOD password = Date of Birth (YYYY-MM-DD)
            </div>
          </div>
        </div>

        <div style="margin-top:22px;display:flex;gap:10px;justify-content:flex-end;border-top:1px solid var(--border);padding-top:16px;">
          <button class="btn-secondary" onclick="closeEnrollPanel()"><i class="fa fa-xmark"></i> Cancel</button>
          <button class="btn-primary" id="btnHodEnroll2" onclick="doEnrollHod()" style="background:#9333ea;">
            <i class="fa fa-user-plus"></i> Enroll HOD
          </button>
        </div>
        <div class="enroll-result" id="hodEnrollResult2"></div>
      </div>
    </div>
    <div class="card" style="max-width:900px;margin:1.2rem auto 0;">
      <div class="card-head">
        <h4><i class="fa fa-users"></i> Enrolled HODs</h4>
        <button class="btn-sm" onclick="loadHodTable()"><i class="fa fa-rotate-right"></i> Refresh</button>
      </div>
      <div class="table-scroll">
        <table class="data-tbl">
          <thead><tr><th>HOD ID</th><th>Name</th><th>Dept</th><th>Email</th><th>Mobile</th><th>Enrolled On</th></tr></thead>
          <tbody id="hodEnrollTbody"><tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text3)">Click Refresh to load</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>
  `;

  _loadStudentTableRows();
  _loadEnrollKpis();
  loadFacHubTable();
  loadHodHubTable();
}

// ── Enroll state ─────────────────────────────────────────────
const _enrollExisting = { student: null, faculty: null, hod: null };

function openEnrollPanel(role) {
  document.getElementById('enrollHub').style.display = 'none';
  ['student','faculty','hod'].forEach(r => {
    const p = document.getElementById('enrollPanel-'+r);
    if (p) p.classList.remove('active');
  });
  const panel = document.getElementById('enrollPanel-'+role);
  if (panel) panel.classList.add('active');
  // Auto-load the enrolled faculty table whenever the faculty panel opens
  if (role === 'faculty') loadFacTable();
}

function closeEnrollPanel() {
  ['student','faculty','hod'].forEach(r => {
    const p = document.getElementById('enrollPanel-'+r);
    if (p) p.classList.remove('active');
  });
  document.getElementById('enrollHub').style.display = '';
  _loadStudentTableRows();
  _loadEnrollKpis();
  loadFacHubTable();
  loadHodHubTable();
  // Reset OTP state so next enrollment starts fresh
  if (typeof smfOtp    !== 'undefined') smfOtp.reset();
  if (typeof smfOtpFac !== 'undefined') smfOtpFac.reset();
  if (typeof smfOtpHod !== 'undefined') smfOtpHod.reset();
}

// ── KPI strip for hub ────────────────────────────────────────
async function _loadEnrollKpis() {
  const el = document.getElementById('enrollKpiStrip');
  if (!el) return;
  try {
    const stuList = await api.students();
    let facCount = 0, hodCount = 0;
    try { const fd = await apiFetch('/api/faculty/all'); facCount = (fd.faculty||fd||[]).length; } catch(_){}
    try { const hd = await apiFetch('/api/hods'); hodCount = (hd.hods||hd||[]).length; } catch(_){}
    el.innerHTML =
      kpi('Students', stuList.length, 'fa-user-graduate', '#0284c7') +
      kpi('Faculty',  facCount,        'fa-chalkboard-user','#16a34a') +
      kpi('HODs',     hodCount,         'fa-user-tie',      '#9333ea');
  } catch(_) { el.innerHTML = ''; }
}

// ── Load student table rows ──────────────────────────────────
async function _loadStudentTableRows() {
  const tbody = document.getElementById('stuTbody');
  if (!tbody) return;
  try {
    const students = await api.students();
    window._allStudents = students;
    if (!students.length) {
      tbody.innerHTML = '<tr><td colspan="13" style="text-align:center;padding:28px;color:var(--text3)"><i class="fa fa-users" style="font-size:1.4rem;opacity:.3"></i><br>No students yet. Click <strong>Enroll Person</strong> to add one.</td></tr>';
      return;
    }    tbody.innerHTML = students.map((s,i) => {
      const regNo = s.register_number || s.roll_number || s.student_id || '—';
      const rollNo = s.roll_number || '—';
      const name = s.name || '?';
      const gender = s.gender || '—';
      const dept = s.department || '—';
      const course = s.course || '—';
      const year = s.year || '—';
      const section = s.section || '—';
      const mob = s.student_mobile || s.mobile || '—';
      const status = s.status || 'Active';
      const enrolledOn = (s.enrolled_on || '').slice(0, 10) || '—';
      const sIdSafe = (s.student_id || '').replace(/'/g, "\\'");
      const nameSafe = (name).replace(/'/g, "\\'");
      const menuId = `stu_menu_${i}_${(s.student_id||'').replace(/[^a-zA-Z0-9]/g,'_')}`;

      return `<tr>
        <td style="font-family:var(--mono);color:var(--text3);font-size:.82rem">${i+1}</td>
        <td><code style="font-size:.82rem;font-weight:600;color:var(--text1)">${regNo}</code></td>
        <td><code style="font-size:.82rem;color:var(--text2)">${rollNo}</code></td>
        <td><strong style="color:var(--text1);font-weight:700">${name}</strong></td>
        <td>${gender}</td>
        <td>${dept}</td>
        <td>${course}</td>
        <td>${year}</td>
        <td><span class="badge" style="background:#f3e8ff;color:#7e22ce;font-weight:700;border-radius:12px;padding:3px 10px">${section}</span></td>
        <td>${mob}</td>
        <td><span class="badge" style="background:${status==='Active'?'#dcfce7':'#fee2e2'};color:${status==='Active'?'#15803d':'#b91c1c'};font-weight:700;border-radius:12px;padding:3px 10px">${status}</span></td>
        <td style="font-size:.78rem;color:var(--text3)">${enrolledOn}</td>
        <td style="text-align:center;position:relative;">
          <div class="row-action-wrap">
            <button class="btn-action-trigger" onclick="toggleActionMenu(event, '${menuId}')" title="Actions">
              <i class="fa fa-ellipsis-vertical"></i>
            </button>
            <div class="action-dropdown-menu" id="${menuId}">
              <div class="action-dropdown-item" onclick="viewStudentDetail('${sIdSafe}')">
                <i class="fa fa-eye" style="color:#0284c7"></i> View Details
              </div>
              <div class="action-dropdown-item" onclick="editStudentFromHub('${sIdSafe}')">
                <i class="fa fa-pen" style="color:#16a34a"></i> Edit Student
              </div>
              <div class="action-dropdown-item" onclick="openFaceCaptureModal('${sIdSafe}','student','${nameSafe}')">
                <i class="fa fa-camera" style="color:#0284c7"></i> Capture Photo
              </div>
              <div class="action-dropdown-item" onclick="deleteStudent('${sIdSafe}')">
                <i class="fa fa-ban" style="color:#f59e0b"></i> Deactivate
              </div>
              <div class="action-dropdown-item danger" onclick="permanentDeleteStudent('${sIdSafe}','${nameSafe}')">
                <i class="fa fa-trash"></i> Delete
              </div>
            </div>
          </div>
        </td>
      </tr>`;
    }).join('');
  } catch(e) {
    if (tbody) tbody.innerHTML = `<tr><td colspan="13" style="text-align:center;padding:20px;color:var(--coral-d)">${e.message}</td></tr>`;
  }
}

function filterStudents() {
  const q = (document.getElementById('stuSearch')?.value||'').toLowerCase();
  const dept = (document.getElementById('stuDeptFilter')?.value||'').toLowerCase();
  document.querySelectorAll('#stuTbody tr').forEach(tr => {
    const txt = tr.textContent.toLowerCase();
    const matchQ = !q || txt.includes(q);
    const matchD = !dept || txt.includes(dept);
    tr.style.display = (matchQ && matchD) ? '' : 'none';
  });
}
function filterStuTable() { filterStudents(); }
function openAddStudentModal() { openEnrollPanel('student'); }
async function submitAddStudent() { await doEnrollStudent(); }

async function deleteStudent(id) {
  if (!confirm('⚠ Deactivate student ' + id + '?\n\nThe student will be marked Inactive.\nAll attendance records will be preserved.\n\nYou can reactivate them by editing the student record.')) return;
  try {
    await apiFetch('/api/students/' + encodeURIComponent(id) + '/deactivate', { method: 'PATCH' });
    toast('✓ Student ' + id + ' deactivated — records preserved', 'info');
    _loadStudentTableRows();
    _loadEnrollKpis();
  } catch(e) {
    toast('Deactivate failed: ' + e.message, 'error');
  }
}

async function permanentDeleteStudent(id, name) {
  const displayName = name || id;
  if (!confirm(
    '🗑 PERMANENTLY DELETE student ' + displayName + ' (' + id + ')?\n\n' +
    '⚠ WARNING: This cannot be undone!\n' +
    '• Student record will be removed from the database.\n' +
    '• Face enrollment data will be deleted.\n' +
    '• Attendance records will also be removed.\n\n' +
    'Are you absolutely sure?'
  )) return;
  if (!confirm('FINAL CONFIRMATION\n\nDelete ' + displayName + ' permanently?\n\nClick OK to confirm.')) return;
  try {
    await apiFetch('/api/students/' + encodeURIComponent(id), { method: 'DELETE' });
    toast('🗑 Student ' + displayName + ' permanently deleted', 'error');
    _loadStudentTableRows();
    _loadEnrollKpis();
  } catch(e) {
    toast('Delete failed: ' + e.message, 'error');
  }
}

// ── Student Edit (from hub table) ───────────────────────────
async function editStudentFromHub(sid) {
  try {
    const s = await apiFetch('/api/students/' + encodeURIComponent(sid));
    const DEPTS   = ['CSE','IT','ECE','EEE','MECH','CIVIL','AIDS','AIML','CSBS','BME'];
    const COURSES = ['B.E','B.Tech','B.Sc','M.E','M.Tech','MCA','MBA'];
    const YEARS   = ['1st Year','2nd Year','3rd Year','4th Year'];
    const SECTS   = ['A','B','C','D','E'];
    document.getElementById('infoModalTitle').innerHTML =
      '<i class="fa fa-pen" style="color:#16a34a"></i> Edit Student \u2014 ' + sid;
    document.getElementById('infoModalBody').innerHTML = `
    <style>
      .es-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;}
      .es-grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px;}
      .es-field label{font-size:.78rem;font-weight:600;color:var(--text2);display:block;margin-bottom:3px;}
      .es-field input,.es-field select{border:1.5px solid var(--border);border-radius:8px;
        padding:7px 10px;font-size:.875rem;background:var(--card-bg);color:var(--text1);
        width:100%;box-sizing:border-box;transition:border-color .15s;}
      .es-field input:focus,.es-field select:focus{outline:none;border-color:#16a34a;
        box-shadow:0 0 0 3px rgba(22,163,74,.1);}
      .es-field input[readonly]{opacity:.6;cursor:not-allowed;background:var(--card-bg2,#f7f9fb);}
      .es-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px;
        padding-top:12px;border-top:1px solid var(--border);}
      .es-section{font-size:.72rem;font-weight:700;letter-spacing:.06em;
        color:var(--mint-d);text-transform:uppercase;margin:14px 0 6px;
        padding-bottom:3px;border-bottom:1px solid var(--border);}
    </style>
    <p class="es-section"><i class="fa fa-id-card"></i> Identity</p>
    <div class="es-grid">
      <div class="es-field"><label>Student ID</label>
        <input id="es_sid" value="${s.student_id||sid}" readonly/></div>
      <div class="es-field"><label>Register Number</label>
        <input id="es_reg" value="${s.register_number||''}"/></div>
    </div>
    <div class="es-grid">
      <div class="es-field"><label>First Name</label>
        <input id="es_fname" value="${s.first_name||''}"/></div>
      <div class="es-field"><label>Last Name</label>
        <input id="es_lname" value="${s.last_name||''}"/></div>
    </div>
    <div class="es-grid">
      <div class="es-field"><label>Roll Number</label>
        <input id="es_roll" value="${s.roll_number||''}"/></div>
      <div class="es-field"><label>Gender</label>
        <select id="es_gender">
          <option value="">Select</option>
          ${['Male','Female','Other'].map(g=>`<option value="${g}" ${(s.gender||'')=== g?'selected':''}>${g}</option>`).join('')}
        </select></div>
    </div>
    <div class="es-grid">
      <div class="es-field"><label>Date of Birth</label>
        <input id="es_dob" type="date" value="${(s.date_of_birth||'').slice(0,10)}"/></div>
      <div class="es-field"><label>Status</label>
        <select id="es_status">
          ${['Active','Inactive'].map(st=>`<option value="${st}" ${(s.status||'Active')===st?'selected':''}>${st}</option>`).join('')}
        </select></div>
    </div>
    <p class="es-section"><i class="fa fa-building-columns"></i> Academic</p>
    <div class="es-grid-3">
      <div class="es-field"><label>Department</label>
        <select id="es_dept">
          <option value="">Select</option>
          ${DEPTS.map(d=>`<option value="${d}" ${(s.department||s.dept||'')=== d?'selected':''}>${d}</option>`).join('')}
        </select></div>
      <div class="es-field"><label>Course</label>
        <select id="es_course">
          <option value="">Select</option>
          ${COURSES.map(c=>`<option value="${c}" ${(s.course||'')=== c?'selected':''}>${c}</option>`).join('')}
        </select></div>
      <div class="es-field"><label>Year</label>
        <select id="es_year">
          <option value="">Select</option>
          ${YEARS.map(y=>`<option value="${y}" ${(s.year||'')=== y?'selected':''}>${y}</option>`).join('')}
        </select></div>
    </div>
    <div class="es-grid">
      <div class="es-field"><label>Section</label>
        <select id="es_section">
          ${SECTS.map(sc=>`<option value="${sc}" ${(s.section||'')=== sc?'selected':''}>${sc}</option>`).join('')}
        </select></div>
      <div class="es-field"><label>Twin of (Student ID) <span style="font-size:0.75rem;font-weight:normal;color:var(--text3);">(Optional)</span></label>
        <input id="es_twin" placeholder="e.g. STU_... (leave blank if not a twin)" value="${s.twin_of||''}"/></div>
    </div>
    <p class="es-section"><i class="fa fa-envelope"></i> Contact</p>
    <div class="es-grid">
      <div class="es-field"><label>Student Email</label>
        <input id="es_semail" type="email" value="${s.student_email||''}"/></div>
      <div class="es-field"><label>Parent Email</label>
        <input id="es_pemail" type="email" value="${s.parent_email||''}"/></div>
    </div>
    <div class="es-grid">
      <div class="es-field"><label>Student Mobile</label>
        <input id="es_smob" type="tel" value="${s.student_mobile||s.mobile||''}"/></div>
      <div class="es-field"><label>Parent Mobile</label>
        <input id="es_pmob" type="tel" value="${s.parent_mobile||''}"/></div>
    </div>
    <div id="es_msg" style="color:#dc2626;font-size:.82rem;min-height:18px;margin-top:4px;"></div>
    <div class="es-actions">
      <button class="btn-secondary" onclick="closeModal('infoModal')">
        <i class="fa fa-xmark"></i> Cancel</button>
      <button class="btn-primary" style="background:#16a34a"
        onclick="saveStudentEdit('${sid}')">
        <i class="fa fa-floppy-disk"></i> Save Changes</button>
    </div>`;
    document.getElementById('infoModal').classList.remove('dn');
  } catch(e) { toast('Could not load student data: ' + e.message, 'error'); }
}

async function saveStudentEdit(sid) {
  const g = id => (document.getElementById(id)?.value||'').trim();
  const msgEl = document.getElementById('es_msg');
  const fname = g('es_fname'), lname = g('es_lname');
  if (!fname) { if(msgEl) msgEl.textContent='First name is required.'; return; }
  if (!lname) { if(msgEl) msgEl.textContent='Last name is required.';  return; }
  if (!g('es_dept')) { if(msgEl) msgEl.textContent='Department is required.'; return; }
  if (!g('es_year')) { if(msgEl) msgEl.textContent='Year is required.'; return; }
  if (msgEl) msgEl.textContent = '';
  const payload = {
    register_number: g('es_reg'),
    roll_number:     g('es_roll'),
    first_name:      fname,
    last_name:       lname,
    name:            (fname + ' ' + lname).trim(),
    gender:          g('es_gender'),
    date_of_birth:   g('es_dob'),
    department:      g('es_dept'),
    course:          g('es_course'),
    year:            g('es_year'),
    section:         g('es_section') || 'A',
    student_email:   g('es_semail'),
    parent_email:    g('es_pemail'),
    student_mobile:  g('es_smob'),
    parent_mobile:   g('es_pmob'),
    twin_of:         g('es_twin') || null,
    status:          g('es_status') || 'Active',
  };
  try {
    await apiFetch('/api/students/' + encodeURIComponent(sid), {
      method: 'PUT', body: JSON.stringify(payload)
    });
    toast('\u2713 Student ' + sid + ' updated successfully', 'success');
    closeModal('infoModal');
    _loadStudentTableRows(); _loadEnrollKpis();
  } catch(e) { if(msgEl) msgEl.textContent = 'Save failed: ' + e.message; }
}

// ── Hub Faculty Table ────────────────────────────────────────
window._allFacultyHub = [];
async function loadFacHubTable() {
  const tbody = document.getElementById('facHubTbody');
  if (!tbody) return;
  tbody.innerHTML='<tr><td colspan="10" style="text-align:center;padding:20px"><i class="fa fa-spinner fa-spin"></i> Loading...</td></tr>';
  try {
    const data = await apiFetch('/api/faculty/all');
    const list = data.faculty||data||[];
    window._allFacultyHub = list;
    if (!Array.isArray(list) || !list.length) {
      tbody.innerHTML=`<tr><td colspan="10" style="text-align:center;padding:32px;color:var(--text3)"><i class="fa fa-chalkboard-user" style="font-size:1.6rem;opacity:.3;display:block;margin-bottom:8px;"></i><strong>No Faculty Enrolled Yet</strong><br><small>Click <strong>Enroll Faculty</strong> to add one.</small></td></tr>`;
      return;
    }
    _renderFacHubRows(list);
  } catch(e) {
    tbody.innerHTML=`<tr><td colspan="10" style="text-align:center;color:var(--coral-d);padding:20px"><i class="fa fa-circle-exclamation"></i> ${e.message||'Failed to load faculty'}</td></tr>`;
  }
}

function _renderFacHubRows(list) {
  const tbody = document.getElementById('facHubTbody');
  if (!tbody) return;  tbody.innerHTML = list.map((f,i) => {
    const idVal    = f.fac_id || f.faculty_id || '—';
    const nameVal  = f.name || ((f.first_name||'')+' '+(f.last_name||'')).trim() || '—';
    const deptVal  = f.dept || f.department || '—';
    const desigVal = f.designation || '—';
    const emailVal = f.email || '—';
    const mobVal   = f.mobile || '—';
    const status   = f.active===0 ? 'Inactive' : 'Active';
    const dateVal  = (f.enrolled_on||f.created_at||f.joining_date||'').toString().slice(0,10)||'—';
    const idSafe   = (idVal).replace(/'/g,"\\'");
    const nameSafe = (nameVal).replace(/'/g,"\\'");
    const menuId   = `fac_menu_${i}_${(idVal||'').replace(/[^a-zA-Z0-9]/g,'_')}`;

    return `<tr>
      <td style="font-family:var(--mono);color:var(--text3);font-size:.82rem">${i+1}</td>
      <td><code style="font-size:.82rem;font-weight:600;color:var(--text1)">${idVal}</code></td>
      <td><strong style="color:var(--text1);font-weight:700">${nameVal}</strong></td>
      <td><span class="badge mint" style="font-weight:700;border-radius:12px;padding:3px 10px">${deptVal}</span></td>
      <td style="font-size:.82rem">${desigVal}</td>
      <td style="font-size:.82rem;color:var(--text2)">${emailVal}</td>
      <td style="font-size:.82rem">${mobVal}</td>
      <td><span class="badge ${status==='Active'?'b-grn':'b-red'}" style="font-weight:700;border-radius:12px;padding:3px 10px">${status}</span></td>
      <td style="font-size:.78rem;color:var(--text3)">${dateVal}</td>
      <td style="text-align:center;position:relative;">
        <div class="row-action-wrap">
          <button class="btn-action-trigger" onclick="toggleActionMenu(event, '${menuId}')" title="Actions">
            <i class="fa fa-ellipsis-vertical"></i>
          </button>
          <div class="action-dropdown-menu" id="${menuId}">
            <div class="action-dropdown-item" onclick="viewFacultyDetail('${idSafe}','${nameSafe}')">
              <i class="fa fa-eye" style="color:#0284c7"></i> View Details
            </div>
            <div class="action-dropdown-item" onclick="editFacultyFromHub('${idSafe}')">
              <i class="fa fa-pen" style="color:#16a34a"></i> Edit Faculty
            </div>
            <div class="action-dropdown-item" onclick="openFaceCaptureModal('${idSafe}','faculty','${nameSafe}')">
              <i class="fa fa-camera" style="color:#0284c7"></i> Capture Photo
            </div>
            <div class="action-dropdown-item danger" onclick="deleteFacultyFromHub('${idSafe}','${nameSafe}')">
              <i class="fa fa-trash"></i> Delete
            </div>
          </div>
        </div>
      </td>
    </tr>`;
  }).join('');
}

function filterFacHub() {
  const q    = (document.getElementById('facHubSearch')?.value||'').toLowerCase();
  const dept = (document.getElementById('facHubDeptFilter')?.value||'').toLowerCase();
  const list = window._allFacultyHub||[];
  const filtered = list.filter(f => {
    const txt = ((f.fac_id||f.faculty_id||'')+' '+(f.name||'')+' '+(f.dept||f.department||'')+' '+(f.designation||'')+' '+(f.email||'')).toLowerCase();
    return (!q||txt.includes(q)) && (!dept||(f.dept||f.department||'').toLowerCase().includes(dept));
  });
  _renderFacHubRows(filtered);
}

async function viewFacultyDetail(facId, facName) {
  try {
    const data = await apiFetch('/api/faculty/all');
    const list = data.faculty||data||[];
    const f = list.find(x=>(x.fac_id||x.faculty_id||'').toLowerCase()===facId.toLowerCase())||{};
    document.getElementById('infoModalTitle').textContent = (f.name||facName||facId)+' — Faculty Details';
    document.getElementById('infoModalBody').innerHTML = `
    <style>
      .sd-section{font-size:.75rem;font-weight:700;letter-spacing:.06em;color:var(--mint-d);text-transform:uppercase;margin:14px 0 8px;padding-bottom:3px;border-bottom:1px solid var(--border);}
      .sd-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
      .sd-grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;}
      .sd-field label{font-size:.74rem;font-weight:600;color:var(--text3);display:block;margin-bottom:2px;}
      .sd-field input{border:1.5px solid var(--border);border-radius:7px;padding:6px 10px;font-size:.84rem;background:var(--card-bg2,#f7f9fb);color:var(--text1);width:100%;box-sizing:border-box;}
    </style>
    <p class="sd-section"><i class="fa fa-id-card"></i> Identity</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Faculty ID</label><input value="${f.fac_id||f.faculty_id||facId}" readonly/></div>
      <div class="sd-field"><label>Full Name</label><input value="${f.name||((f.first_name||'')+' '+(f.last_name||'')).trim()||'—'}" readonly/></div>
    </div>
    <div class="sd-grid" style="margin-top:8px">
      <div class="sd-field"><label>Gender</label><input value="${f.gender||'—'}" readonly/></div>
      <div class="sd-field"><label>Date of Birth</label><input value="${f.date_of_birth||'—'}" readonly/></div>
    </div>
    <p class="sd-section" style="margin-top:14px"><i class="fa fa-building-columns"></i> Academic</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Department</label><input value="${f.dept||f.department||'—'}" readonly/></div>
      <div class="sd-field"><label>Designation</label><input value="${f.designation||'—'}" readonly/></div>
    </div>
    <div class="sd-grid" style="margin-top:8px">
      <div class="sd-field"><label>Employee Code</label><input value="${f.employee_code||'—'}" readonly/></div>
      <div class="sd-field"><label>Joining Date</label><input value="${(f.joining_date||'—').toString().slice(0,10)}" readonly/></div>
    </div>
    <p class="sd-section" style="margin-top:14px"><i class="fa fa-envelope"></i> Contact</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Email</label><input value="${f.email||'—'}" readonly/></div>
      <div class="sd-field"><label>Mobile</label><input value="${f.mobile||'—'}" readonly/></div>
    </div>
    <p class="sd-section" style="margin-top:14px"><i class="fa fa-clock"></i> System</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Status</label><input value="${f.active===0?'Inactive':'Active'}" readonly/></div>
      <div class="sd-field"><label>Enrolled On</label><input value="${(f.enrolled_on||f.created_at||'—').toString().slice(0,10)}" readonly/></div>
    </div>`;
    document.getElementById('infoModal').classList.remove('dn');
  } catch(e) { toast('Could not load faculty details: '+e.message,'error'); }
}

async function editFacultyFromHub(facId) {
  // Load current data and show an inline edit modal
  try {
    const data = await apiFetch('/api/faculty/all');
    const list = data.faculty||data||[];
    const f = list.find(x=>(x.fac_id||x.faculty_id||'').toUpperCase()===facId.toUpperCase())||{};
    const DEPTS = ['CSE','IT','ECE','EEE','MECH','CIVIL','AIDS','AIML','CSBS','BME'];
    const DESIG = ['Professor','Associate Professor','Assistant Professor','Senior Lecturer','Lecturer','Lab Instructor'];
    document.getElementById('infoModalTitle').innerHTML = '<i class="fa fa-pen" style="color:#16a34a"></i> Edit Faculty — '+facId;
    document.getElementById('infoModalBody').innerHTML = `
    <style>
      .ef-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;}
      .ef-field label{font-size:.78rem;font-weight:600;color:var(--text2);display:block;margin-bottom:3px;}
      .ef-field input,.ef-field select{border:1.5px solid var(--border);border-radius:8px;padding:7px 10px;font-size:.875rem;background:var(--card-bg);color:var(--text1);width:100%;box-sizing:border-box;transition:border-color .15s;}
      .ef-field input:focus,.ef-field select:focus{outline:none;border-color:#16a34a;box-shadow:0 0 0 3px rgba(22,163,74,.1);}
      .ef-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:16px;padding-top:12px;border-top:1px solid var(--border);}
    </style>
    <div class="ef-grid">
      <div class="ef-field"><label>Faculty ID</label><input id="ef_id" value="${f.fac_id||f.faculty_id||facId}" readonly style="opacity:.6;cursor:not-allowed"/></div>
      <div class="ef-field"><label>Full Name</label><input id="ef_name" value="${f.name||((f.first_name||'')+' '+(f.last_name||'')).trim()||''}"/></div>
    </div>
    <div class="ef-grid">
      <div class="ef-field"><label>Department</label>
        <select id="ef_dept">
          <option value="">Select Dept</option>
          ${DEPTS.map(d=>`<option value="${d}" ${(f.dept||f.department||'')=== d?'selected':''}>${d}</option>`).join('')}
        </select>
      </div>
      <div class="ef-field"><label>Designation</label>
        <select id="ef_desig">
          <option value="">Select</option>
          ${DESIG.map(d=>`<option value="${d}" ${(f.designation||'')=== d?'selected':''}>${d}</option>`).join('')}
        </select>
      </div>
    </div>
    <div class="ef-grid">
      <div class="ef-field"><label>Email</label><input id="ef_email" type="email" value="${f.email||''}"/></div>
      <div class="ef-field"><label>Mobile</label><input id="ef_mobile" type="tel" value="${f.mobile||''}"/></div>
    </div>
    <div class="ef-grid">
      <div class="ef-field"><label>Employee Code</label><input id="ef_empcode" value="${f.employee_code||''}"/></div>
      <div class="ef-field"><label>Joining Date</label><input id="ef_join" type="date" value="${(f.joining_date||'').toString().slice(0,10)}"/></div>
    </div>
    <div class="ef-actions">
      <button class="btn-secondary" onclick="closeModal('infoModal')"><i class="fa fa-xmark"></i> Cancel</button>
      <button class="btn-primary" style="background:#16a34a" onclick="saveFacultyEdit('${facId}')"><i class="fa fa-floppy-disk"></i> Save Changes</button>
    </div>`;
    document.getElementById('infoModal').classList.remove('dn');
  } catch(e) { toast('Could not load faculty data: '+e.message,'error'); }
}

async function saveFacultyEdit(facId) {
  const g = id => (document.getElementById(id)?.value||'').trim();
  const payload = {
    name: g('ef_name'), dept: g('ef_dept'),
    designation: g('ef_desig'), email: g('ef_email'),
    mobile: g('ef_mobile'), employee_code: g('ef_empcode'),
    joining_date: g('ef_join')
  };
  if (!payload.name)  { toast('Name is required','warn'); return; }
  if (!payload.dept)  { toast('Department is required','warn'); return; }
  try {
    await apiFetch('/api/faculty/'+encodeURIComponent(facId.toUpperCase()), {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
    toast('✓ '+facId+' updated successfully','success');
    closeModal('infoModal');
    loadFacHubTable(); _loadEnrollKpis();
  } catch(e) { toast('Update failed: '+e.message,'error'); }
}

async function deleteFacultyFromHub(facId, facName) {
  if (!confirm('Delete Faculty account for '+facName+' ('+facId+')?\n\nThis will set the account to Inactive in the database.\nAttendance records will be preserved.')) return;
  try {
    await apiFetch('/api/faculty/'+encodeURIComponent(facId.toUpperCase()), {method:'DELETE'});
    toast('✓ '+facId+' ('+facName+') deactivated','info');
    loadFacHubTable(); _loadEnrollKpis();
  } catch(e) { toast('Delete failed: '+e.message,'error'); }
}

// ── Hub HOD Table ────────────────────────────────────────────
window._allHodHub = [];
async function loadHodHubTable() {
  const tbody = document.getElementById('hodHubTbody');
  if (!tbody) return;
  tbody.innerHTML='<tr><td colspan="10" style="text-align:center;padding:20px"><i class="fa fa-spinner fa-spin"></i> Loading...</td></tr>';
  try {
    const data = await apiFetch('/api/hods');
    const list = data.hods||data||[];
    window._allHodHub = list;
    if (!Array.isArray(list) || !list.length) {
      tbody.innerHTML=`<tr><td colspan="10" style="text-align:center;padding:32px;color:var(--text3)"><i class="fa fa-user-tie" style="font-size:1.6rem;opacity:.3;display:block;margin-bottom:8px;"></i><strong>No HOD Enrolled Yet</strong><br><small>Click <strong>Enroll HOD</strong> to add one.</small></td></tr>`;
      return;
    }
    _renderHodHubRows(list);
  } catch(e) {
    tbody.innerHTML=`<tr><td colspan="10" style="text-align:center;color:var(--coral-d);padding:20px"><i class="fa fa-circle-exclamation"></i> ${e.message||'Failed to load HODs'}</td></tr>`;
  }
}function _renderHodHubRows(list) {
  const tbody = document.getElementById('hodHubTbody');
  if (!tbody) return;
  tbody.innerHTML = list.map((h,i) => {
    const idVal    = h.hod_id || '—';
    const nameVal  = h.name || ((h.first_name||'')+' '+(h.last_name||'')).trim() || '—';
    const deptVal  = h.dept || h.department || '—';
    const desigVal = h.designation || 'Head of Department';
    const emailVal = h.email || '—';
    const mobVal   = h.mobile || '—';
    const status   = h.active===0 ? 'Inactive' : 'Active';
    const dateVal  = (h.enrolled_on||h.created_at||'').toString().slice(0,10)||'—';
    const idSafe   = (idVal).replace(/'/g,"\\'");
    const nameSafe = (nameVal).replace(/'/g,"\\'");
    const menuId   = `hod_menu_${i}_${(idVal||'').replace(/[^a-zA-Z0-9]/g,'_')}`;

    return `<tr>
      <td style="font-family:var(--mono);color:var(--text3);font-size:.82rem">${i+1}</td>
      <td><code style="font-size:.82rem;font-weight:600;color:var(--text1)">${idVal}</code></td>
      <td><strong style="color:var(--text1);font-weight:700">${nameVal}</strong></td>
      <td><span class="badge sky" style="font-weight:700;border-radius:12px;padding:3px 10px">${deptVal}</span></td>
      <td style="font-size:.82rem">${desigVal}</td>
      <td style="font-size:.82rem;color:var(--text2)">${emailVal}</td>
      <td style="font-size:.82rem">${mobVal}</td>
      <td><span class="badge ${status==='Active'?'b-grn':'b-red'}" style="font-weight:700;border-radius:12px;padding:3px 10px">${status}</span></td>
      <td style="font-size:.78rem;color:var(--text3)">${dateVal}</td>
      <td style="text-align:center;position:relative;">
        <div class="row-action-wrap">
          <button class="btn-action-trigger" onclick="toggleActionMenu(event, '${menuId}')" title="Actions">
            <i class="fa fa-ellipsis-vertical"></i>
          </button>
          <div class="action-dropdown-menu" id="${menuId}">
            <div class="action-dropdown-item" onclick="viewHodDetail('${idSafe}','${nameSafe}')">
              <i class="fa fa-eye" style="color:#0284c7"></i> View Details
            </div>
            <div class="action-dropdown-item" onclick="editHod('${idSafe}')">
              <i class="fa fa-pen" style="color:#9333ea"></i> Edit HOD
            </div>
            <div class="action-dropdown-item" onclick="openFaceCaptureModal('${idSafe}','hod','${nameSafe}')">
              <i class="fa fa-camera" style="color:#0284c7"></i> Capture Photo
            </div>
            <div class="action-dropdown-item danger" onclick="deleteHodFromHub('${idSafe}','${nameSafe}')">
              <i class="fa fa-trash"></i> Delete
            </div>
          </div>
        </div>
      </td>
    </tr>`;
  }).join('');
}

function filterHodHub() {
  const q    = (document.getElementById('hodHubSearch')?.value||'').toLowerCase();
  const dept = (document.getElementById('hodHubDeptFilter')?.value||'').toLowerCase();
  const list = window._allHodHub||[];
  const filtered = list.filter(h => {
    const txt = ((h.hod_id||'')+' '+(h.name||'')+' '+(h.dept||h.department||'')+' '+(h.email||'')).toLowerCase();
    return (!q||txt.includes(q)) && (!dept||(h.dept||h.department||'').toLowerCase().includes(dept));
  });
  _renderHodHubRows(filtered);
}

async function viewHodDetail(hodId, hodName) {
  try {
    const data = await apiFetch('/api/hods');
    const list = data.hods||data||[];
    const h = list.find(x=>(x.hod_id||'').toLowerCase()===hodId.toLowerCase())||{};
    document.getElementById('infoModalTitle').textContent = (h.name||hodName||hodId)+' — HOD Details';
    document.getElementById('infoModalBody').innerHTML = `
    <style>
      .sd-section{font-size:.75rem;font-weight:700;letter-spacing:.06em;color:var(--mint-d);text-transform:uppercase;margin:14px 0 8px;padding-bottom:3px;border-bottom:1px solid var(--border);}
      .sd-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
      .sd-field label{font-size:.74rem;font-weight:600;color:var(--text3);display:block;margin-bottom:2px;}
      .sd-field input{border:1.5px solid var(--border);border-radius:7px;padding:6px 10px;font-size:.84rem;background:var(--card-bg2,#f7f9fb);color:var(--text1);width:100%;box-sizing:border-box;}
    </style>
    <p class="sd-section"><i class="fa fa-id-card"></i> Identity</p>
    <div class="sd-grid">
      <div class="sd-field"><label>HOD ID</label><input value="${h.hod_id||hodId}" readonly/></div>
      <div class="sd-field"><label>Full Name</label><input value="${h.name||((h.first_name||'')+' '+(h.last_name||'')).trim()||'—'}" readonly/></div>
    </div>
    <div class="sd-grid" style="margin-top:8px">
      <div class="sd-field"><label>Gender</label><input value="${h.gender||'—'}" readonly/></div>
      <div class="sd-field"><label>Date of Birth</label><input value="${h.date_of_birth||'—'}" readonly/></div>
    </div>
    <p class="sd-section" style="margin-top:14px"><i class="fa fa-building-columns"></i> Academic</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Department</label><input value="${h.dept||h.department||'—'}" readonly/></div>
      <div class="sd-field"><label>Designation</label><input value="${h.designation||'Head of Department'}" readonly/></div>
    </div>
    <div class="sd-grid" style="margin-top:8px">
      <div class="sd-field"><label>Employee Code</label><input value="${h.employee_code||'—'}" readonly/></div>
      <div class="sd-field"><label>Joining Date</label><input value="${(h.joining_date||'—').toString().slice(0,10)}" readonly/></div>
    </div>
    <p class="sd-section" style="margin-top:14px"><i class="fa fa-envelope"></i> Contact</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Email</label><input value="${h.email||'—'}" readonly/></div>
      <div class="sd-field"><label>Mobile</label><input value="${h.mobile||'—'}" readonly/></div>
    </div>
    <p class="sd-section" style="margin-top:14px"><i class="fa fa-clock"></i> System</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Status</label><input value="${h.active===0?'Inactive':'Active'}" readonly/></div>
      <div class="sd-field"><label>Enrolled On</label><input value="${(h.enrolled_on||h.created_at||'—').toString().slice(0,10)}" readonly/></div>
    </div>`;
    document.getElementById('infoModal').classList.remove('dn');
  } catch(e) { toast('Could not load HOD details: '+e.message,'error'); }
}

async function deleteHodFromHub(hodId, hodName) {
  if (!confirm('Delete HOD account for '+hodName+' ('+hodId+')?\n\nThis will set the account to Inactive in the database.\nAttendance records will be preserved.')) return;
  try {
    await apiFetch('/api/hods/'+encodeURIComponent(hodId.toUpperCase()), {method:'DELETE'});
    toast('✓ '+hodId+' ('+hodName+') deactivated','info');
    loadHodHubTable(); _loadEnrollKpis();
  } catch(e) { toast('Delete failed: '+e.message,'error'); }
}

// ── Shared exist-check (debounced) ──────────────────────────
const _existCheckTimers = {};
function checkEnrollExists(role) {
  clearTimeout(_existCheckTimers[role]);
  _existCheckTimers[role] = setTimeout(() => _doExistCheck(role), 600);
}

async function _doExistCheck(role) {
  const banners = { student:'stuReBanner', faculty:'facReBanner', hod:'hodReBanner' };
  const msgIds  = { student:'stuReMsg',    faculty:'facReMsg',    hod:'hodReMsg' };
  const banner  = document.getElementById(banners[role]);
  const msgEl   = document.getElementById(msgIds[role]);
  if (!banner) return;

  let uid = '';
  if (role==='student') uid = (document.getElementById('en_reg')?.value||'').trim();
  if (role==='faculty') uid = (document.getElementById('sf_id')?.value||'').trim().toUpperCase();
  if (role==='hod')     uid = (document.getElementById('hf_id')?.value||'').trim().toUpperCase();

  if (!uid || uid.length < 2) { banner.style.display='none'; _enrollExisting[role]=null; return; }

  try {
    let found = null;
    if (role==='student') {
      const res = await apiFetch('/api/students/check/'+encodeURIComponent(uid));
      if (res.exists) found = res.student;
    } else if (role==='faculty') {
      const fd = await apiFetch('/api/faculty/all');
      const list = fd.faculty||fd||[];
      found = list.find(f=>(f.fac_id||f.faculty_id||'').toUpperCase()===uid)||null;
      if (found) found = { name: found.name||((found.first_name||'')+' '+(found.last_name||'')).trim(), student_id: uid };
    } else if (role==='hod') {
      const hd = await apiFetch('/api/hods');
      const list = hd.hods||hd||[];
      found = list.find(h=>(h.hod_id||'').toUpperCase()===uid)||null;
      if (found) found = { name: found.name||((found.first_name||'')+' '+(found.last_name||'')).trim(), student_id: uid };
    }
    if (found) {
      _enrollExisting[role] = found;
      const roleLabel = role==='student'?'Student':role==='faculty'?'Faculty':'HOD';
      msgEl.innerHTML = `<i class="fa fa-triangle-exclamation"></i> <strong>${found.name||uid}</strong> (${uid}) already exists as ${roleLabel}. Do you want to enroll again?`;
      banner.style.display = '';
    } else {
      _enrollExisting[role] = null;
      banner.style.display = 'none';
    }
  } catch(_) { banner.style.display='none'; _enrollExisting[role]=null; }
}

function confirmReenroll(role, openCam) {
  const banners = { student:'stuReBanner', faculty:'facReBanner', hod:'hodReBanner' };
  document.getElementById(banners[role]).style.display = 'none';
  const msg = openCam
    ? 'Re-enrollment confirmed — webcam will open for face capture.'
    : 'Camera skipped — record updated without re-capturing face.';
  toast(msg, openCam?'info':'success');
  if (role==='student') doEnrollStudent(true, openCam);
  if (role==='faculty') doEnrollFaculty(true, openCam);
  if (role==='hod')     doEnrollHod(true, openCam);
}

// ── Student submit ───────────────────────────────────────────

// ═══════════════════════════════════════════════════════════════════
//  smfOtp  —  Email OTP Verification for Student Enrollment  v2
//  Self-contained controller. No conflicts with existing validators.
//  Flow: email input → format check → Send OTP button appears
//        → POST /api/enroll/send-otp → OTP field + timer appear
//        → user types 6 digits → auto POST /api/enroll/verify-otp
//        → on success: lock email, enable Enroll button
// ═══════════════════════════════════════════════════════════════════
const smfOtp = (function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────────
  let _verified    = false;
  let _otpSent     = false;
  let _timerID     = null;
  let _timerSec    = 300;
  let _resendCount = 0;
  let _lastEmail   = '';

  // ── DOM helpers ────────────────────────────────────────────────
  const $ = function(id) { return document.getElementById(id); };

  function _emailVal() {
    var el = $('en_semail');
    return el ? el.value.trim().toLowerCase() : '';
  }

  function _isValidEmail(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);
  }

  // Status below the email field
  function _setStatus(html, color) {
    var el = $('en_semail_status');
    if (!el) return;
    el.innerHTML   = html;
    el.style.color = color || '#64748b';
  }

  // Message inside the OTP section
  function _setOtpMsg(html, color) {
    var el = $('smfOtpMsg');
    if (!el) return;
    el.innerHTML   = html;
    el.style.color = color || '#64748b';
  }

  // Show/hide the Send OTP button
  function _showSendBtn(show) {
    var btn = $('btnSendOtp');
    if (btn) btn.style.display = show ? '' : 'none';
  }

  // Show/hide the OTP input section
  function _showOtpSection(show) {
    var sec = $('smfOtpSection');
    if (sec) sec.style.display = show ? '' : 'none';
  }

  // Enable/disable Enroll button
  function _setEnrollBtn(enabled) {
    var btn = $('btnStuEnroll');
    if (!btn) return;
    btn.disabled = !enabled;
    btn.title    = enabled ? '' : 'Verify student email with OTP first.';
  }

  // ── Timer ──────────────────────────────────────────────────────
  function _stopTimer() {
    if (_timerID) { clearInterval(_timerID); _timerID = null; }
  }

  function _startTimer() {
    _stopTimer();
    _timerSec = 300;
    _updateTimerDisplay();
    _timerID = setInterval(function () {
      _timerSec--;
      _updateTimerDisplay();
      if (_timerSec <= 0) {
        _stopTimer();
        _setOtpMsg('OTP expired. Please click Resend OTP.', '#dc2626');
        var rsnd = $('btnResendOtp');
        if (rsnd && _resendCount < 3) rsnd.style.display = '';
      }
    }, 1000);
  }

  function _updateTimerDisplay() {
    var el = $('smfOtpTimer');
    if (!el) return;
    if (_timerSec <= 0) { el.textContent = 'Expired'; return; }
    var m = Math.floor(_timerSec / 60);
    var s = _timerSec % 60;
    el.textContent = 'Expires in ' + m + ':' + (s < 10 ? '0' : '') + s;
  }

  // ── Full reset ─────────────────────────────────────────────────
  function reset() {
    _stopTimer();
    _verified    = false;
    _otpSent     = false;
    _resendCount = 0;
    _lastEmail   = '';

    var emailEl = $('en_semail');
    var otpInp  = $('en_otp_input');
    var timerEl = $('smfOtpTimer');
    var rsnd    = $('btnResendOtp');

    if (emailEl) { emailEl.readOnly = false; emailEl.value = ''; }
    if (otpInp)  { otpInp.value = ''; otpInp.disabled = false; }
    if (timerEl) timerEl.textContent = '';
    if (rsnd)    rsnd.style.display = 'none';

    _setStatus('', '');
    _setOtpMsg('', '');
    _showSendBtn(false);
    _showOtpSection(false);
    _setEnrollBtn(false);
  }

  // ── Called on every keypress in the email field ────────────────
  function onEmailInput() {
    var email = _emailVal();

    // If email changed after OTP was sent, reset everything
    if (_otpSent && email !== _lastEmail) {
      reset();
    }

    if (_isValidEmail(email)) {
      _showSendBtn(true);
      _setStatus('', '');
    } else {
      _showSendBtn(false);
      if (email.length > 3) {
        _setStatus('Enter a valid email address.', '#dc2626');
      } else {
        _setStatus('', '');
      }
    }
    _setEnrollBtn(false);
  }

  // ── Called when email field loses focus ────────────────────────
  function onEmailBlur() {
    var email = _emailVal();
    if (!email || !_isValidEmail(email)) return;
    if (_verified) return;  // already verified, don't re-check

    // Async duplicate check
    apiFetch('/api/check/email/' + encodeURIComponent(email))
      .then(function(r) {
        if (r && r.exists) {
          _setStatus('&#x2716; Email already registered to ' + (r.name || 'another user') + '.', '#dc2626');
          _showSendBtn(false);
        }
      })
      .catch(function() {
        // silent — backend enforces on submit
      });
  }

  // ── Send OTP ───────────────────────────────────────────────────
  function sendOtp() {
    var email   = _emailVal();
    var sendBtn = $('btnSendOtp');

    if (!_isValidEmail(email)) {
      _setStatus('Enter a valid email address first.', '#dc2626');
      return;
    }

    if (sendBtn) { sendBtn.disabled = true; sendBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Sending&hellip;'; }
    _setStatus('Sending OTP to ' + email + '&hellip;', '#0284c7');

    apiFetch('/api/enroll/send-otp', {
      method: 'POST',
      body:   JSON.stringify({ email: email })
    })
    .then(function(res) {
      _lastEmail = email;
      _otpSent   = true;
      _resendCount++;

      _setStatus('&#x2714; OTP sent to <strong>' + email + '</strong>. Check your inbox.', '#16a34a');

      // Lock email field
      var emailEl = $('en_semail');
      if (emailEl) emailEl.readOnly = true;

      // Show OTP section and start timer
      var otpInp = $('en_otp_input');
      if (otpInp) { otpInp.value = ''; otpInp.disabled = false; }
      _showOtpSection(true);
      _startTimer();
      _setOtpMsg('Enter the 6-digit OTP sent to your email.', '#0284c7');

      // Show resend button only if already used resends
      var rsnd = $('btnResendOtp');
      if (rsnd) rsnd.style.display = 'none';

      // Focus OTP input
      setTimeout(function() {
        var inp = $('en_otp_input');
        if (inp) inp.focus();
      }, 100);
    })
    .catch(function(e) {
      var msg = (e && e.message) ? e.message : 'Unable to send OTP. Please try again.';
      if (msg.indexOf('already registered') !== -1 || msg.indexOf('409') !== -1) {
        _setStatus('&#x2716; Email already registered.', '#dc2626');
        _showSendBtn(false);
      } else if (msg.indexOf('Maximum resend') !== -1 || msg.indexOf('429') !== -1) {
        _setStatus('&#x2716; Maximum resend attempts reached.', '#dc2626');
        _showSendBtn(false);
      } else {
        _setStatus('&#x2716; ' + msg, '#dc2626');
      }
    })
    .finally(function() {
      if (sendBtn) { sendBtn.disabled = false; sendBtn.innerHTML = '<i class="fa fa-paper-plane"></i> Send OTP'; }
    });
  }

  // ── Resend OTP ─────────────────────────────────────────────────
  function resendOtp() {
    if (_resendCount >= 3) {
      _setOtpMsg('Maximum resend attempts (3) reached.', '#dc2626');
      var rsnd = $('btnResendOtp');
      if (rsnd) rsnd.style.display = 'none';
      return;
    }
    // Unlock email field temporarily so sendOtp can read it
    var emailEl = $('en_semail');
    if (emailEl) emailEl.readOnly = false;
    _otpSent = false;
    sendOtp();
  }

  // ── Auto-verify when user types 6 digits ──────────────────────
  function onOtpInput(val) {
    // Strip non-digits
    val = val.replace(/\D/g, '').slice(0, 6);
    var inp = $('en_otp_input');
    if (inp) inp.value = val;

    if (val.length < 6) {
      if (_verified) {
        _verified = false;
        _setEnrollBtn(false);
        _setOtpMsg('Enter the 6-digit OTP.', '#0284c7');
      }
      return;
    }

    // 6 digits entered — auto-verify
    var email = _emailVal() || _lastEmail;
    if (inp) inp.disabled = true;
    _setOtpMsg('<i class="fa fa-spinner fa-spin"></i> Verifying OTP&hellip;', '#0284c7');

    apiFetch('/api/enroll/verify-otp', {
      method: 'POST',
      body:   JSON.stringify({ email: email, otp: val })
    })
    .then(function() {
      _verified = true;
      _stopTimer();

      var timerEl = $('smfOtpTimer');
      var rsnd    = $('btnResendOtp');
      if (timerEl) timerEl.textContent = '';
      if (rsnd)    rsnd.style.display  = 'none';

      _setOtpMsg('&#x2714; Email Verified Successfully!', '#16a34a');
      _setStatus('&#x2714; Email Verified', '#16a34a');
      _setEnrollBtn(true);
    })
    .catch(function(e) {
      _verified = false;
      _setEnrollBtn(false);
      var msg = (e && e.message) ? e.message : 'Invalid OTP.';

      if (msg.indexOf('expired') !== -1) {
        _setOtpMsg('&#x2716; OTP expired. Click Resend OTP.', '#dc2626');
        var rsnd2 = $('btnResendOtp');
        if (rsnd2 && _resendCount < 3) rsnd2.style.display = '';
      } else if (msg.indexOf('locked') !== -1 || msg.indexOf('429') !== -1) {
        _setOtpMsg('&#x2716; ' + msg, '#dc2626');
        var rsnd3 = $('btnResendOtp');
        if (rsnd3 && _resendCount < 3) rsnd3.style.display = '';
      } else {
        _setOtpMsg('&#x2716; ' + msg, '#dc2626');
      }

      // Clear input so user can retype
      if (inp) {
        inp.disabled = false;
        inp.value    = '';
        inp.focus();
      }
    });
  }

  // ── Public API ─────────────────────────────────────────────────
  return {
    onEmailInput: onEmailInput,
    onEmailBlur:  onEmailBlur,
    sendOtp:      sendOtp,
    resendOtp:    resendOtp,
    onOtpInput:   onOtpInput,
    isVerified:   function() { return _verified; },
    reset:        reset
  };
})();


// ── smfOtpFactory  —  Reusable OTP controller factory ───────────────────────
// Creates independent OTP controllers for any enrollment form.
// Usage: smfOtpFactory({ emailId, statusId, sendBtnId, sectionId, otpInputId,
//                        timerElId, resendBtnId, msgElId, enrollBtnId, enrollBtnTitle })
function smfOtpFactory(cfg) {
  'use strict';
  var _verified    = false;
  var _otpSent     = false;
  var _timerID     = null;
  var _timerSec    = 300;
  var _resendCount = 0;
  var _lastEmail   = '';

  var $ = function(id) { return document.getElementById(id); };

  function _emailVal() {
    var el = $(cfg.emailId);
    return el ? el.value.trim().toLowerCase() : '';
  }

  function _isValidEmail(v) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);
  }

  function _setStatus(html, color) {
    var el = $(cfg.statusId);
    if (!el) return;
    el.innerHTML   = html;
    el.style.color = color || '#64748b';
  }

  function _setOtpMsg(html, color) {
    var el = $(cfg.msgElId);
    if (!el) return;
    el.innerHTML   = html;
    el.style.color = color || '#64748b';
  }

  function _showSendBtn(show) {
    var btn = $(cfg.sendBtnId);
    if (btn) btn.style.display = show ? '' : 'none';
  }

  function _showOtpSection(show) {
    var sec = $(cfg.sectionId);
    if (sec) sec.style.display = show ? '' : 'none';
  }

  function _setEnrollBtn(enabled) {
    var btn = $(cfg.enrollBtnId);
    if (!btn) return;
    btn.disabled = !enabled;
    btn.title    = enabled ? '' : (cfg.enrollBtnTitle || 'Verify email with OTP first.');
  }

  function _stopTimer() {
    if (_timerID) { clearInterval(_timerID); _timerID = null; }
  }

  function _updateTimerDisplay() {
    var el = $(cfg.timerElId);
    if (!el) return;
    if (_timerSec <= 0) { el.textContent = 'Expired'; return; }
    var m = Math.floor(_timerSec / 60);
    var s = _timerSec % 60;
    el.textContent = 'Expires in ' + m + ':' + (s < 10 ? '0' : '') + s;
  }

  function _startTimer() {
    _stopTimer();
    _timerSec = 300;
    _updateTimerDisplay();
    _timerID = setInterval(function () {
      _timerSec--;
      _updateTimerDisplay();
      if (_timerSec <= 0) {
        _stopTimer();
        _setOtpMsg('OTP expired. Please click Resend OTP.', '#dc2626');
        var rsnd = $(cfg.resendBtnId);
        if (rsnd && _resendCount < 3) rsnd.style.display = '';
      }
    }, 1000);
  }

  function reset() {
    _stopTimer();
    _verified    = false;
    _otpSent     = false;
    _resendCount = 0;
    _lastEmail   = '';

    var emailEl = $(cfg.emailId);
    var otpInp  = $(cfg.otpInputId);
    var timerEl = $(cfg.timerElId);
    var rsnd    = $(cfg.resendBtnId);

    if (emailEl) { emailEl.readOnly = false; emailEl.value = ''; }
    if (otpInp)  { otpInp.value = ''; otpInp.disabled = false; }
    if (timerEl) timerEl.textContent = '';
    if (rsnd)    rsnd.style.display = 'none';

    _setStatus('', '');
    _setOtpMsg('', '');
    _showSendBtn(false);
    _showOtpSection(false);
    _setEnrollBtn(false);
  }

  function onEmailInput() {
    var email = _emailVal();
    if (_otpSent && email !== _lastEmail) { reset(); }

    if (_isValidEmail(email)) {
      _showSendBtn(true);
      _setStatus('', '');
    } else {
      _showSendBtn(false);
      if (email.length > 3) {
        _setStatus('Enter a valid email address.', '#dc2626');
      } else {
        _setStatus('', '');
      }
    }
    _setEnrollBtn(false);
  }

  function onEmailBlur() {
    var email = _emailVal();
    if (!email || !_isValidEmail(email)) return;
    if (_verified) return;

    // Only duplicate check — no SMTP / mailbox existence check
    apiFetch('/api/check/email/' + encodeURIComponent(email))
      .then(function(r) {
        if (r && r.exists) {
          _setStatus('&#x2716; Email already registered to ' + (r.name || 'another user') + '.', '#dc2626');
          _showSendBtn(false);
        }
      })
      .catch(function() { /* silent — backend enforces on submit */ });
  }

  function sendOtp() {
    var email   = _emailVal();
    var sendBtn = $(cfg.sendBtnId);

    if (!_isValidEmail(email)) {
      _setStatus('Enter a valid email address first.', '#dc2626');
      return;
    }

    if (sendBtn) { sendBtn.disabled = true; sendBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Sending&hellip;'; }
    _setStatus('Sending OTP to ' + email + '&hellip;', '#0284c7');

    apiFetch('/api/enroll/send-otp', {
      method: 'POST',
      body:   JSON.stringify({ email: email })
    })
    .then(function(res) {
      _lastEmail = email;
      _otpSent   = true;
      _resendCount++;

      _setStatus('&#x2714; OTP sent to <strong>' + email + '</strong>. Check your inbox.', '#16a34a');

      var emailEl = $(cfg.emailId);
      if (emailEl) emailEl.readOnly = true;

      var otpInp = $(cfg.otpInputId);
      if (otpInp) { otpInp.value = ''; otpInp.disabled = false; }
      _showOtpSection(true);
      _startTimer();
      _setOtpMsg('Enter the 6-digit OTP sent to your email.', '#0284c7');

      var rsnd = $(cfg.resendBtnId);
      if (rsnd) rsnd.style.display = 'none';

      setTimeout(function() {
        var inp = $(cfg.otpInputId);
        if (inp) inp.focus();
      }, 100);
    })
    .catch(function(e) {
      var msg = (e && e.message) ? e.message : 'Unable to send OTP. Please try again.';
      if (msg.indexOf('already registered') !== -1 || msg.indexOf('409') !== -1) {
        _setStatus('&#x2716; Email already registered.', '#dc2626');
        _showSendBtn(false);
      } else if (msg.indexOf('Maximum resend') !== -1 || msg.indexOf('429') !== -1) {
        _setStatus('&#x2716; Maximum resend attempts reached.', '#dc2626');
        _showSendBtn(false);
      } else {
        _setStatus('&#x2716; ' + msg, '#dc2626');
      }
    })
    .finally(function() {
      if (sendBtn) { sendBtn.disabled = false; sendBtn.innerHTML = '<i class="fa fa-paper-plane"></i> Send OTP'; }
    });
  }

  function resendOtp() {
    if (_resendCount >= 3) {
      _setOtpMsg('Maximum resend attempts (3) reached.', '#dc2626');
      var rsnd = $(cfg.resendBtnId);
      if (rsnd) rsnd.style.display = 'none';
      return;
    }
    var emailEl = $(cfg.emailId);
    if (emailEl) emailEl.readOnly = false;
    _otpSent = false;
    sendOtp();
  }

  function onOtpInput(val) {
    val = val.replace(/\D/g, '').slice(0, 6);
    var inp = $(cfg.otpInputId);
    if (inp) inp.value = val;

    if (val.length < 6) {
      if (_verified) {
        _verified = false;
        _setEnrollBtn(false);
        _setOtpMsg('Enter the 6-digit OTP.', '#0284c7');
      }
      return;
    }

    var email = _emailVal() || _lastEmail;
    if (inp) inp.disabled = true;
    _setOtpMsg('<i class="fa fa-spinner fa-spin"></i> Verifying OTP&hellip;', '#0284c7');

    apiFetch('/api/enroll/verify-otp', {
      method: 'POST',
      body:   JSON.stringify({ email: email, otp: val })
    })
    .then(function() {
      _verified = true;
      _stopTimer();
      var timerEl = $(cfg.timerElId);
      var rsnd    = $(cfg.resendBtnId);
      if (timerEl) timerEl.textContent = '';
      if (rsnd)    rsnd.style.display  = 'none';

      _setOtpMsg('&#x2714; Email Verified Successfully!', '#16a34a');
      _setStatus('&#x2714; Email Verified', '#16a34a');
      _setEnrollBtn(true);
    })
    .catch(function(e) {
      _verified = false;
      _setEnrollBtn(false);
      var msg = (e && e.message) ? e.message : 'Invalid OTP.';

      if (msg.indexOf('expired') !== -1) {
        _setOtpMsg('&#x2716; OTP expired. Click Resend OTP.', '#dc2626');
        var rsnd2 = $(cfg.resendBtnId);
        if (rsnd2 && _resendCount < 3) rsnd2.style.display = '';
      } else if (msg.indexOf('locked') !== -1 || msg.indexOf('429') !== -1) {
        _setOtpMsg('&#x2716; ' + msg, '#dc2626');
        var rsnd3 = $(cfg.resendBtnId);
        if (rsnd3 && _resendCount < 3) rsnd3.style.display = '';
      } else {
        _setOtpMsg('&#x2716; ' + msg, '#dc2626');
      }

      if (inp) { inp.disabled = false; inp.value = ''; inp.focus(); }
    });
  }

  return {
    onEmailInput: onEmailInput,
    onEmailBlur:  onEmailBlur,
    sendOtp:      sendOtp,
    resendOtp:    resendOtp,
    onOtpInput:   onOtpInput,
    isVerified:   function() { return _verified; },
    reset:        reset
  };
}

// ── Faculty Enrollment OTP Controller ───────────────────────
const smfOtpFac = smfOtpFactory({
  emailId:       'sf_email',
  statusId:      'sf_email_status',
  sendBtnId:     'btnSendOtpFac',
  sectionId:     'smfOtpSectionFac',
  otpInputId:    'sf_otp_input',
  timerElId:     'smfOtpTimerFac',
  resendBtnId:   'btnResendOtpFac',
  msgElId:       'smfOtpMsgFac',
  enrollBtnId:   'btnFacEnroll',
  enrollBtnTitle:'Verify faculty email with OTP first.'
});

// ── HOD Enrollment OTP Controller ───────────────────────────
const smfOtpHod = smfOtpFactory({
  emailId:       'hf_email',
  statusId:      'hf_email_status',
  sendBtnId:     'btnSendOtpHod',
  sectionId:     'smfOtpSectionHod',
  otpInputId:    'hf_otp_input',
  timerElId:     'smfOtpTimerHod',
  resendBtnId:   'btnResendOtpHod',
  msgElId:       'smfOtpMsgHod',
  enrollBtnId:   'btnHodEnroll2',
  enrollBtnTitle:'Verify HOD email with OTP first.'
});

async function doEnrollStudent(forceUpdate=false, openCam=true) {
  if (_enrollExisting.student && !forceUpdate) {
    document.getElementById('stuReBanner').style.display = '';
    toast('Student already exists — choose re-enroll or skip camera.','warn');
    return;
  }
  const g = id => (document.getElementById(id)?.value||'').trim();
  const fname=g('en_fname'), lname=g('en_lname');
  const data = {
    register_number:g('en_reg'), roll_number:g('en_roll'),
    first_name:fname, last_name:lname, name:`${fname} ${lname}`.trim(),
    gender:g('en_gender'), date_of_birth:g('en_dob'),
    department:g('en_dept'), course:g('en_course'),
    year:g('en_year'), section:g('en_section')||'A',
    student_email:g('en_semail'), parent_email:g('en_pemail'),
    student_mobile:g('en_smob'), parent_mobile:g('en_pmob'),
    twin_of:g('en_twin')||null
  };
  // Strict name validation (frontend guard)
  const _stuFnOk = validateNameInput('en_fname', 'First Name');
  const _stuLnOk = validateNameInput('en_lname', 'Last Name');
  if (!_stuFnOk || !_stuLnOk) { toast('Please fix name errors before submitting.','warn'); return; }

  // Strict mobile validation (frontend guard — format + async duplicate check)
  const _stuSmobOk = await validateMobileFull('en_smob', 'Student Mobile');
  const _stuPmobOk = data.parent_mobile
    ? await validateMobileFull('en_pmob', 'Parent Mobile')
    : true;
  if (!_stuSmobOk || !_stuPmobOk) { toast('Please fix mobile number errors before submitting.','warn'); return; }

  // ── Email OTP verification guard (Rule 17) ──────────────────────────
  if (!smfOtp.isVerified()) {
    toast('Please verify your student email address with OTP before enrolling.', 'warn');
    if (document.getElementById('en_semail')) document.getElementById('en_semail').focus();
    return;
  }

  // Strict email validation (frontend guard — format + async duplicate check)
  const _stuSemailOk = data.student_email
    ? await validateEmailFull('en_semail', 'Student Email')
    : true;
  const _stuPemailOk = data.parent_email
    ? await validateEmailFull('en_pemail', 'Parent Email')
    : true;
  if (!_stuSemailOk || !_stuPemailOk) { toast('Please fix email address errors before submitting.','warn'); return; }

  // ── DOB validation (frontend guard) ──────────────────────────
  const _stuDobOk = validateDobInput('en_dob', 'student', null);
  if (!_stuDobOk) { toast('Please fix Date of Birth errors before submitting.', 'warn'); return; }

  const errs=[];
  if (!data.register_number) errs.push('Register Number');
  if (!data.roll_number)     errs.push('Roll Number');
  if (!data.gender)          errs.push('Gender');
  if (!data.year)            errs.push('Year');
  if (errs.length) { toast('Required: '+errs.join(', '),'warn'); return; }

  const btn = document.getElementById('btnStuEnroll');
  if (btn) { btn.disabled=true; btn.innerHTML='<i class="fa fa-spinner fa-spin"></i> Enrolling...'; }
  try {
    let res;
    if (forceUpdate && _enrollExisting.student) {
      const sid = _enrollExisting.student.student_id||('STU_'+data.register_number.toUpperCase());
      res = await apiFetch('/api/students/'+encodeURIComponent(sid),{method:'PUT',body:JSON.stringify(data)});
      toast('✓ '+data.name+' updated!','success');
    } else {
      res = await api.addStudent(data);
      toast('✓ '+data.name+' enrolled! ID: '+(res.student_id||''),'success');
    }
        const _stuSid = res?.student_id || ('STU_'+data.register_number.toUpperCase());
    _showEnrollBox('stuEnrollResult', true,
      `✓ <strong>${data.name}</strong> enrolled! (ID: ${_stuSid})`+
      (openCam?'<br><small><i class="fa fa-camera"></i> Opening camera for face capture&hellip;</small>':
               '<br><small><i class="fa fa-check"></i> Camera skipped — face data not updated.</small>'));
    _enrollExisting.student = null;
    document.getElementById('stuReBanner').style.display='none';
    _loadStudentTableRows(); _loadEnrollKpis();
    if (openCam) { setTimeout(() => openFaceCaptureModal(_stuSid, 'student', data.name), 400); }
  } catch(e) {
    const msg=e.message||'';
    if (msg.toLowerCase().includes('already')||msg.includes('409')) {
      document.getElementById('stuReBanner').style.display='';
      toast('Student already exists — use re-enroll option.','warn');
    } else {
      _showEnrollBox('stuEnrollResult', false, 'Error: '+msg);
      toast('Enrollment failed: '+msg,'error');
    }
  } finally {
    if (btn) { btn.disabled=false; btn.innerHTML='<i class="fa fa-user-plus"></i> Enroll Student'; }
  }
}

// ── Faculty submit ───────────────────────────────────────────
async function doEnrollFaculty(forceUpdate=false, openCam=true) {
  if (_enrollExisting.faculty && !forceUpdate) {
    document.getElementById('facReBanner').style.display='';
    toast('Faculty already exists — choose re-enroll or skip.','warn');
    return;
  }
  const g = id => (document.getElementById(id)?.value||'').trim();
  const facId=g('sf_id').toUpperCase(), fname=g('sf_fname'), lname=g('sf_lname');
  const gender=g('sf_gender'), dob=g('sf_dob'), dept=g('sf_dept');
  // Strict name validation (frontend guard)
  const _facFnOk = validateNameInput('sf_fname', 'First Name');
  const _facLnOk = validateNameInput('sf_lname', 'Last Name');
  if (!_facFnOk || !_facLnOk) { toast('Please fix name errors before submitting.','warn'); return; }

  // Strict mobile validation (frontend guard)
  const _sfMob = (document.getElementById('sf_mobile')?.value||'').trim();
  if (_sfMob) {
    const _facMobOk = await validateMobileFull('sf_mobile', 'Mobile Number', facId);
    if (!_facMobOk) { toast('Please fix mobile number errors before submitting.','warn'); return; }
  }

  // ── Email OTP verification guard ─────────────────────────────────────
  if (!smfOtpFac.isVerified()) {
    toast('Please verify the faculty email address with OTP before enrolling.', 'warn');
    if (document.getElementById('sf_email')) document.getElementById('sf_email').focus();
    return;
  }

  // Strict email duplicate validation (frontend guard)
  const _sfEmail = (document.getElementById('sf_email')?.value||'').trim();
  if (_sfEmail) {
    const _facEmailOk = await validateEmailFull('sf_email', 'Email', facId);
    if (!_facEmailOk) { toast('Please fix email address errors before submitting.','warn'); return; }
  }

  // ── DOB validation (frontend guard) ──────────────────────────
  const _facDobOk = validateDobInput('sf_dob', 'faculty', 'sf_designation');
  if (!_facDobOk) { toast('Please fix Date of Birth errors before submitting.', 'warn'); return; }

  const missing=[];
  if (!facId) missing.push('Faculty ID');
  if (!gender)  missing.push('Gender');
  if (!dob)     missing.push('Date of Birth');
  if (!dept)    missing.push('Department');
  if (missing.length) { toast('Required: '+missing.join(', '),'warn'); return; }

  const ic=g('sf_incharge');
  let ic_dept='',ic_year='',ic_section='';
  if (ic) { const p=ic.split('|'); ic_dept=p[0]||''; ic_year=p[1]||''; ic_section=p[2]||''; }
  const payload = {
    fac_id:facId, faculty_id:facId, employee_code:g('sf_empcode'), first_name:fname, last_name:lname,
    gender, date_of_birth:dob, department:dept,
    designation:g('sf_designation')||'Assistant Professor',
    email:g('sf_email'), mobile:g('sf_mobile'), joining_date:g('sf_join'),
    is_class_incharge:ic?1:0, incharge_department:ic_dept,
    incharge_year:ic_year, incharge_section:ic_section,
    role:ic?'classincharge':'faculty'
  };

  const btn = document.getElementById('btnFacEnroll');
  if (btn) { btn.disabled=true; btn.innerHTML='<i class="fa fa-spinner fa-spin"></i> Enrolling...'; }
  try {
    await apiFetch('/api/faculty/enroll',{method:'POST',body:JSON.stringify(payload)});
    _showEnrollBox('facEnrollResult', true,
      `✓ <strong>${fname} ${lname}</strong> (${facId}) enrolled!`+
      (openCam?'<br><small><i class="fa fa-camera"></i> Opening camera for face capture&hellip;</small>':
               '<br><small><i class="fa fa-check"></i> Camera skipped.</small>'));
    toast('✓ Faculty enrolled: '+facId,'success');
    _enrollExisting.faculty=null;
    document.getElementById('facReBanner').style.display='none';
    loadFacTable();
    loadFacHubTable();
    _loadEnrollKpis();
    if (openCam) { setTimeout(() => openFaceCaptureModal(facId, 'faculty', fname+' '+lname), 400); }
  } catch(e) {
    const msg=e.message||'';
    if (msg.includes('409')||msg.toLowerCase().includes('exists')) {
      document.getElementById('facReBanner').style.display='';
      toast('Faculty already exists — re-enroll or skip.','warn');
    } else { _showEnrollBox('facEnrollResult', false, 'Error: '+msg); }
  } finally {
    if (btn) { btn.disabled=false; btn.innerHTML='<i class="fa fa-user-plus"></i> Enroll Faculty'; }
  }
}

async function loadFacTable() {
  const tbody = document.getElementById('facEnrollTbody');
  if (!tbody) return;
  tbody.innerHTML='<tr><td colspan="7" style="text-align:center;padding:14px"><i class="fa fa-spinner fa-spin"></i> Loading...</td></tr>';
  try {
    const data = await apiFetch('/api/faculty/all');
    const list = data.faculty||data||[];
    if (!Array.isArray(list) || !list.length) {
      tbody.innerHTML='<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text3)">No faculty enrolled yet.</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(f => {
      // dept is the real column; department may be empty alias — use whichever has data
      const deptVal   = f.dept || f.department || '—';
      const nameVal   = f.name || ((f.first_name||'')+' '+(f.last_name||'')).trim() || '—';
      const idVal     = f.fac_id || f.faculty_id || '—';
      const desigVal  = f.designation || '—';
      const emailVal  = f.email || '—';
      const mobVal    = f.mobile || '—';
      const dateRaw   = f.enrolled_on || f.created_at || f.joining_date || '';
      const dateVal   = dateRaw ? dateRaw.toString().slice(0,10) : '—';
      return `<tr>
        <td><code style="font-size:.8rem">${idVal}</code></td>
        <td><strong>${nameVal}</strong></td>
        <td><span class="badge mint">${deptVal}</span></td>
        <td style="font-size:.8rem">${desigVal}</td>
        <td style="font-size:.8rem">${emailVal}</td>
        <td style="font-size:.8rem">${mobVal}</td>
        <td style="font-size:.8rem;color:var(--text3)">${dateVal}</td>
      </tr>`;
    }).join('');
  } catch(e) {
    tbody.innerHTML=`<tr><td colspan="7" style="text-align:center;color:var(--coral-d);padding:16px"><i class="fa fa-circle-exclamation"></i> ${e.message||'Failed to load faculty'}</td></tr>`;
  }
}

// ── HOD submit ───────────────────────────────────────────────
async function doEnrollHod(forceUpdate=false, openCam=true) {
  if (_enrollExisting.hod && !forceUpdate) {
    document.getElementById('hodReBanner').style.display='';
    toast('HOD already exists — choose re-enroll or skip.','warn');
    return;
  }
  const g = id => (document.getElementById(id)?.value||'').trim();
  const hodId=g('hf_id').toUpperCase(), fname=g('hf_fname'), lname=g('hf_lname');
  const gender=g('hf_gender'), dob=g('hf_dob'), dept=g('hf_dept');
  // Strict name validation (frontend guard)
  const _hodFnOk = validateNameInput('hf_fname', 'First Name');
  const _hodLnOk = validateNameInput('hf_lname', 'Last Name');
  if (!_hodFnOk || !_hodLnOk) { toast('Please fix name errors before submitting.','warn'); return; }

  // Strict mobile validation (frontend guard)
  const _hfMob = (document.getElementById('hf_mobile')?.value||'').trim();
  if (_hfMob) {
    const _hodMobOk = await validateMobileFull('hf_mobile', 'Mobile Number', hodId);
    if (!_hodMobOk) { toast('Please fix mobile number errors before submitting.','warn'); return; }
  }

  // ── Email OTP verification guard ─────────────────────────────────────
  if (!smfOtpHod.isVerified()) {
    toast('Please verify the HOD email address with OTP before enrolling.', 'warn');
    if (document.getElementById('hf_email')) document.getElementById('hf_email').focus();
    return;
  }

  // Strict email duplicate validation (frontend guard)
  const _hfEmail = (document.getElementById('hf_email')?.value||'').trim();
  if (_hfEmail) {
    const _hodEmailOk = await validateEmailFull('hf_email', 'Email', hodId);
    if (!_hodEmailOk) { toast('Please fix email address errors before submitting.','warn'); return; }
  }

  // ── DOB validation (frontend guard) ──────────────────────────
  const _hodDobOk = validateDobInput('hf_dob', 'hod', null);
  if (!_hodDobOk) { toast('Please fix Date of Birth errors before submitting.', 'warn'); return; }

  const missing=[];
  if (!hodId)  missing.push('HOD ID');
  if (!gender) missing.push('Gender');
  if (!dob)    missing.push('Date of Birth');
  if (!dept)   missing.push('Department');
  if (missing.length) { toast('Required: '+missing.join(', '),'warn'); return; }

  const payload = {
    hod_id:hodId, employee_code:g('hf_empcode'),
    first_name:fname, last_name:lname, gender, date_of_birth:dob,
    department:dept, email:g('hf_email'), mobile:g('hf_mobile'),
    joining_date:g('hf_join'), designation:'Head of Department', role:'hod'
  };

  const btn = document.getElementById('btnHodEnroll2');
  if (btn) { btn.disabled=true; btn.innerHTML='<i class="fa fa-spinner fa-spin"></i> Enrolling...'; }
  try {
    try { await apiFetch('/api/hods',{method:'POST',body:JSON.stringify(payload)}); }
    catch(_) { await apiFetch('/api/hods',{method:'POST',body:JSON.stringify(payload)}); }
    _showEnrollBox('hodEnrollResult2', true,
      `✓ <strong>${fname} ${lname}</strong> (${hodId}) enrolled as HOD of ${dept}!`+
      (openCam?'<br><small><i class="fa fa-camera"></i> Opening camera for face capture&hellip;</small>':
               '<br><small><i class="fa fa-check"></i> Camera skipped.</small>'));
    toast('✓ HOD enrolled: '+hodId,'success');
    _enrollExisting.hod=null;
    document.getElementById('hodReBanner').style.display='none';
    loadHodTable();
    loadHodHubTable();
    _loadEnrollKpis();
    if (openCam) { setTimeout(() => openFaceCaptureModal(hodId, 'hod', fname+' '+lname), 400); }
  } catch(e) {
    const msg=e.message||'';
    if (msg.includes('409')||msg.toLowerCase().includes('exists')) {
      document.getElementById('hodReBanner').style.display='';
      toast('HOD already exists — re-enroll or skip.','warn');
    } else { _showEnrollBox('hodEnrollResult2', false, 'Error: '+msg); }
  } finally {
    if (btn) { btn.disabled=false; btn.innerHTML='<i class="fa fa-user-plus"></i> Enroll HOD'; }
  }
}

async function loadHodTable() {
  const tbody = document.getElementById('hodEnrollTbody');
  if (!tbody) return;
  tbody.innerHTML='<tr><td colspan="6" style="text-align:center;padding:14px"><i class="fa fa-spinner fa-spin"></i></td></tr>';
  try {
    const data = await apiFetch('/api/hods');
    const list = data.hods||data||[];
    if (!list.length) { tbody.innerHTML='<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text3)">No HODs enrolled yet.</td></tr>'; return; }
    tbody.innerHTML = list.map(h=>`<tr>
      <td><code style="font-size:.8rem">${h.hod_id||'—'}</code></td>
      <td><strong>${h.name||((h.first_name||'')+' '+(h.last_name||'')).trim()||'—'}</strong></td>
      <td><span class="badge sky">${h.department||'—'}</span></td>
      <td style="font-size:.8rem">${h.email||'—'}</td>
      <td style="font-size:.8rem">${h.mobile||'—'}</td>
      <td style="font-size:.8rem;color:var(--text3)">${(h.enrolled_on||h.created_at||'—').toString().slice(0,10)}</td>
    </tr>`).join('');
  } catch(e) { tbody.innerHTML=`<tr><td colspan="6" style="text-align:center;color:var(--coral-d)">${e.message}</td></tr>`; }
}

// ── Shared result box ────────────────────────────────────────
function _showEnrollBox(divId, ok, html) {
  const el = document.getElementById(divId);
  if (!el) return;
  el.style.display='';
  el.style.background  = ok?'#f0fdf4':'#fff1f2';
  el.style.border      = ok?'1.5px solid #86efac':'1.5px solid #fca5a5';
  el.style.color       = ok?'#15803d':'#be123c';
  el.innerHTML = html;
  setTimeout(()=>{ if(el) el.style.display='none'; }, 9000);
}

// ── Legacy stubs ─────────────────────────────────────────────
function openEnrollModal() { openEnrollPanel('student'); }
function _showBanner(s)    { _enrollExisting.student=s; document.getElementById('stuReBanner').style.display=''; }
function _hideBanner()     { document.getElementById('stuReBanner').style.display='none'; }
function _collectEnrollData() { return {}; }
function _validateEnroll()    { return []; }
async function submitEnroll(f=false) { await doEnrollStudent(f); }
async function enrollConfirmUpdate() { await doEnrollStudent(true); }
function enrollCheckExists()  { checkEnrollExists('student'); }


// ── TIMETABLE ─────────────────────────────────────────────────
async function renderTimetablePage() {
  const ttCont=document.getElementById('ttContent');
  if(!ttCont) return;
  ttCont.innerHTML='<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading...</p></div>';
  try {
    const periods=await api.timetable();
    if(!periods.length){ttCont.innerHTML='<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>No timetable configured. Add periods in config.py DEFAULT_PERIODS.</p></div>';return;}
    ttCont.innerHTML='<div class="card"><div class="card-head"><h4><i class="fa fa-calendar-week"></i> Configured Periods</h4></div><div class="table-scroll"><table class="data-tbl"><thead><tr><th>#</th><th>Period Name</th><th>Start</th><th>End</th><th>Status</th></tr></thead><tbody>'+periods.map((p,i)=>'<tr><td style="font-family:var(--mono)">'+(i+1)+'</td><td><strong>'+(p.period_name||p.name||'?')+'</strong></td><td style="font-family:var(--mono)">'+(p.start_time||'—')+'</td><td style="font-family:var(--mono)">'+(p.end_time||'—')+'</td><td>'+(p.active?'<span class="badge b-g">Active</span>':'<span class="badge b-w">Inactive</span>')+'</td></tr>').join('')+'</tbody></table></div></div>';
  } catch(e){ttCont.innerHTML='<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>'+e.message+'</p></div>';}
}

// ── OVERRIDES ─────────────────────────────────────────────────
// ── OVERRIDE v10.1 ─────────────────────────────────────────────
// =============================================================
// HIERARCHICAL ROLE-BASED OVERRIDE SYSTEM  v11.0
// =============================================================
// Access Matrix (enforced on BOTH frontend AND backend):
//   Admin   → can ONLY override HOD records
//   HOD     → can ONLY override Faculty records
//   Faculty → can ONLY override Student records
//   Student → NO override permissions
// =============================================================

// ── API helpers (ensure they exist) ─────────────────────────
if (!api.overrideNew) {
  api.overrideNew     = function(data){ return apiFetch('/api/attendance/override/new',{method:'POST',body:JSON.stringify(data)}); };
  api.overrideHistory = function(p){ return apiFetch('/api/attendance/override/history?'+ new URLSearchParams(p||{})); };
  api.overrideStats   = function(){ return apiFetch('/api/attendance/override/stats'); };
  api.facultyPermissions= function(id){ return apiFetch('/api/faculty/'+id+'/permissions'); };
}
if (!api.overrideRoleMatrix) {
  api.overrideRoleMatrix = function(){ return apiFetch('/api/override/role-matrix'); };
}

// ── Role matrix cache (fetched once per session) ─────────────
var _ovRoleMatrix = null;

async function getOverrideRoleMatrix() {
  if (_ovRoleMatrix) return _ovRoleMatrix;
  try {
    _ovRoleMatrix = await api.overrideRoleMatrix();
    return _ovRoleMatrix;
  } catch(e) {
    // Fallback: derive from APP.role
    var r = (APP.role||'').toLowerCase();
    var tgt = r==='admin' ? 'hod' : r==='hod' ? 'faculty' :
              (r==='faculty'||r==='teacher'||r==='classincharge') ? 'student' : null;
    return { actor_role: r, can_override: !!tgt, allowed_target: tgt||'', allowed_target_display: tgt ? tgt.toUpperCase() : 'None' };
  }
}

// ── Check if current user can show override button for a record ─
// targetRole: 'hod' | 'faculty' | 'student'
async function canShowOverrideFor(targetRole) {
  var matrix = await getOverrideRoleMatrix();
  if (!matrix || !matrix.can_override) return false;
  var allowed = (matrix.allowed_target||'').toLowerCase();
  var target  = (targetRole||'').toLowerCase();
  // Normalise aliases
  if (['faculty','teacher','classincharge','subject_faculty'].includes(target)) target = 'faculty';
  if (['administrator','superadmin'].includes(target)) target = 'admin';
  return allowed === target;
}

// ── Show/hide override button based on role ──────────────────
async function applyOverrideButtonVisibility() {
  var matrix = await getOverrideRoleMatrix();
  var allowed = matrix ? (matrix.allowed_target||'').toLowerCase() : '';

  // "New Override" button on overrides page
  var newBtn = document.getElementById('ovNewOverrideBtn');
  if (newBtn) {
    if (!matrix || !matrix.can_override) {
      newBtn.style.display = 'none';
    } else {
      newBtn.style.display = '';
      newBtn.title = 'You can override ' + (matrix.allowed_target_display||'') + ' attendance records only';
    }
  }

  // Update override type dropdown to only show the allowed type
  var typeSelect = document.getElementById('ov_type');
  if (typeSelect && matrix && matrix.can_override) {
    var allowed = (matrix.allowed_target||'').toLowerCase();
    Array.from(typeSelect.options).forEach(function(opt) {
      var val = (opt.value||'').toLowerCase();
      var optTarget = val==='admin' ? 'hod' : val==='classincharge' ? 'student' : 'student';
      // Map option values to their target role
      var optMap = { 'faculty': 'student', 'classincharge': 'student', 'admin': 'hod' };
      var optAllows = optMap[val] || 'student';
      // Disable options that don't match allowed target
      opt.disabled = (optAllows !== allowed);
      if (!opt.disabled) typeSelect.value = val;
    });
  }
}

// ── Guard: call before opening override modal ────────────────
async function checkOverridePermission(targetRole) {
  var matrix = await getOverrideRoleMatrix();
  if (!matrix || !matrix.can_override) {
    toast('Access Denied: Your role has no override permissions.', 'error');
    return false;
  }
  if (targetRole) {
    var allowed = (matrix.allowed_target||'').toLowerCase();
    var tr = (targetRole||'').toLowerCase();
    if (['faculty','teacher','classincharge'].includes(tr)) tr = 'faculty';
    if (tr !== allowed) {
      toast(
        'Access Denied: ' + (matrix.actor_display||matrix.actor_role) + ' can only override ' +
        (matrix.allowed_target_display||'').toUpperCase() + ' records, not ' + targetRole.toUpperCase() + ' records.',
        'error'
      );
      return false;
    }
  }
  return true;
}

// ================================================================
// Override Modal v12.0 — Professional Hierarchical Role-Based
// THREE separate forms: Admin→HOD, HOD→Faculty, Faculty→Student
// openOverrideModal() auto-detects the logged-in role and opens
// the correct dedicated form. No more combined "Override Type" dropdown.
// ================================================================

// ── Open the correct modal based on the logged-in user's role ─
async function openOverrideModal(type) {
  var matrix = await getOverrideRoleMatrix();

  if (!matrix || !matrix.can_override) {
    toast('Access Denied: Your role (' + (matrix ? matrix.actor_display : APP.role) + ') has no override permissions.', 'error');
    return;
  }

  var actor = (matrix.actor_role || '').toLowerCase();

  // Route to the correct role-specific modal
  if (actor === 'admin' || actor === 'administrator' || actor === 'superadmin') {
    _openAdminOverrideModal();
  } else if (actor === 'hod' || actor === 'hod_admin') {
    _openHodOverrideModal();
  } else {
    // faculty / classincharge / teacher
    _openFacultyOverrideModal();
  }
}

// Also alias used from attendance page button
function openOverrideFromAtt(){ openOverrideModal(); }

// ── Legacy stubs (kept for old call sites) ───────────────────
function onOvTypeChange(){}
function ovFetchPermissions(){}
function loadOverrideStudents(){}
function ovLoadCourses(){}
function ovLoadStudents(){}

// ── Helper: reset a list of input IDs ───────────────────────
function _ovResetFields(ids) {
  ids.forEach(function(id) {
    var el = document.getElementById(id);
    if (!el) return;
    if (el.tagName === 'SELECT') { el.selectedIndex = 0; }
    else { el.value = ''; }
  });
}

// ── Helper: set today's date on a date input ─────────────────
function _ovSetToday(dateId) {
  var el = document.getElementById(dateId);
  if (el) el.value = new Date().toISOString().slice(0,10);
}

// ── Helper: show loading state on a button ───────────────────
function _ovBtnLoading(btn) {
  if (!btn) return '';
  var orig = btn.innerHTML;
  btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Saving...';
  btn.disabled = true;
  return orig;
}
function _ovBtnReset(btn, orig) {
  if (!btn) return;
  btn.innerHTML = orig;
  btn.disabled = false;
}

// ── Helper: submit to backend API ────────────────────────────
async function _ovSubmitToApi(payload, modalId, btnSel) {
  var btn = document.querySelector('#' + modalId + ' .btn-primary');
  var origText = _ovBtnLoading(btn);
  try {
    var matrix = await getOverrideRoleMatrix();
    payload.target_role_hint = matrix ? (matrix.allowed_target || '') : '';
    var result = await api.overrideNew(payload);
    closeModal(modalId);
    toast('Override saved successfully — audit trail updated ✓', 'success');
    setTimeout(function(){ renderOverridesPage(); }, 400);
  } catch(e) {
    var msg = e.message || 'Unknown error';
    if (msg.includes('Access Denied') || msg.includes('403')) {
      toast('🚫 ' + msg, 'error');
    } else {
      toast('Override failed: ' + msg, 'error');
    }
    _ovBtnReset(btn, origText);
  }
}

// ================================================================
// ADMIN → HOD Override
// ================================================================
function _openAdminOverrideModal() {
  _ovResetFields(['adm_facultyId','adm_hodId','adm_reason']);
  _ovResetFields(['adm_dept','adm_from','adm_to','adm_cat']);
  _ovSetToday('adm_date');
  var fromEl = document.getElementById('adm_from'); if(fromEl) fromEl.value = 'Absent';
  var toEl   = document.getElementById('adm_to');   if(toEl)   toEl.value   = 'Present';
  document.getElementById('overrideModal_admin').classList.remove('dn');
}

async function submitOverrideAdmin() {
  var facId  = (document.getElementById('adm_facultyId')||{value:''}).value.trim();
  var hodId    = (document.getElementById('adm_hodId')||{value:''}).value.trim().toUpperCase();
  var dept     = (document.getElementById('adm_dept')||{value:''}).value;
  var date     = (document.getElementById('adm_date')||{value:''}).value;
  var fromVal  = (document.getElementById('adm_from')||{value:'Absent'}).value;
  var toVal    = (document.getElementById('adm_to')||{value:'Present'}).value;
  var cat      = (document.getElementById('adm_cat')||{value:''}).value;
  var reason   = (document.getElementById('adm_reason')||{value:''}).value.trim();

  // Validate
  if (!facId)   { toast('Admin ID is required', 'warn'); document.getElementById('adm_facultyId').focus(); return; }
  if (!hodId)     { toast('HOD ID is required', 'warn'); document.getElementById('adm_hodId').focus(); return; }
  if (!dept)      { toast('Department is required', 'warn'); document.getElementById('adm_dept').focus(); return; }
  if (!date)      { toast('Date is required', 'warn'); document.getElementById('adm_date').focus(); return; }
  if (!reason)    { toast('Reason is mandatory', 'warn'); document.getElementById('adm_reason').focus(); return; }

  var fullReason = cat ? '[' + cat + '] ' + reason : reason;

  // Backend security: role is extracted from JWT, but we pass a hint
  // The override is stored with period='N/A' and course='N/A' since
  // those are not applicable for Admin→HOD overrides per the diagram.
  await _ovSubmitToApi({
    faculty_id:                facId,
    faculty_role:              'Admin',
    target_id:               hodId,
    department:              dept,
    year:                    '',
    semester:                '',
    section:                 '',
    student_register_number: hodId,
    student_name:            '',
    course_code:             'N/A',
    course_name:             'Admin Override',
    period:                  'N/A',
    attendance_from:         fromVal,
    attendance_to:           toVal,
    reason:                  fullReason
  }, 'overrideModal_admin');
}

// ================================================================
// HOD → Faculty Override
// ================================================================
function _openHodOverrideModal() {
  _ovResetFields(['hod_hodId','hod_facultyId','hod_courseCode','hod_courseName','hod_reason']);
  _ovResetFields(['hod_dept','hod_period','hod_from','hod_to','hod_cat']);
  _ovSetToday('hod_date');
  var fromEl = document.getElementById('hod_from'); if(fromEl) fromEl.value = 'Absent';
  var toEl   = document.getElementById('hod_to');   if(toEl)   toEl.value   = 'Present';
  document.getElementById('overrideModal_hod').classList.remove('dn');
}

async function submitOverrideHod() {
  var hodId      = (document.getElementById('hod_hodId')||{value:''}).value.trim();
  var facId    = (document.getElementById('hod_facultyId')||{value:''}).value.trim().toUpperCase();
  var dept       = (document.getElementById('hod_dept')||{value:''}).value;
  var courseCode = (document.getElementById('hod_courseCode')||{value:''}).value.trim().toUpperCase();
  var courseName = (document.getElementById('hod_courseName')||{value:''}).value.trim();
  var period     = (document.getElementById('hod_period')||{value:''}).value;
  var date       = (document.getElementById('hod_date')||{value:''}).value;
  var fromVal    = (document.getElementById('hod_from')||{value:'Absent'}).value;
  var toVal      = (document.getElementById('hod_to')||{value:'Present'}).value;
  var cat        = (document.getElementById('hod_cat')||{value:''}).value;
  var reason     = (document.getElementById('hod_reason')||{value:''}).value.trim();

  // Validate
  if (!hodId)      { toast('HOD ID is required', 'warn'); document.getElementById('hod_hodId').focus(); return; }
  if (!facId)    { toast('Faculty ID is required', 'warn'); document.getElementById('hod_facultyId').focus(); return; }
  if (!dept)       { toast('Department is required', 'warn'); document.getElementById('hod_dept').focus(); return; }
  if (!courseCode) { toast('Course Code is required', 'warn'); document.getElementById('hod_courseCode').focus(); return; }
  if (!period)     { toast('Period is required', 'warn'); document.getElementById('hod_period').focus(); return; }
  if (!date)       { toast('Date is required', 'warn'); document.getElementById('hod_date').focus(); return; }
  if (!reason)     { toast('Reason is mandatory', 'warn'); document.getElementById('hod_reason').focus(); return; }

  var fullReason = cat ? '[' + cat + '] ' + reason : reason;

  await _ovSubmitToApi({
    faculty_id:                hodId,
    faculty_role:              'HOD',
    target_id:               facId,
    department:              dept,
    year:                    '',
    semester:                '',
    section:                 '',
    student_register_number: facId,
    student_name:            '',
    course_code:             courseCode,
    course_name:             courseName,
    period:                  period,
    attendance_from:         fromVal,
    attendance_to:           toVal,
    reason:                  fullReason
  }, 'overrideModal_hod');
}

// ================================================================
// Faculty → Student Override
// ================================================================
function _openFacultyOverrideModal() {
  _ovResetFields(['stf_facultyId','stf_regNum','stf_studentName','stf_courseCode','stf_courseName','stf_reason']);
  _ovResetFields(['stf_dept','stf_year','stf_semester','stf_section','stf_period','stf_from','stf_to','stf_cat']);
  _ovSetToday('stf_date');
  var fromEl = document.getElementById('stf_from'); if(fromEl) fromEl.value = 'Absent';
  var toEl   = document.getElementById('stf_to');   if(toEl)   toEl.value   = 'Present';
  document.getElementById('overrideModal_faculty').classList.remove('dn');
}

// Auto-lookup student name when register number is typed
var _ovLookupTimerStf = null;
function ovLookupStudentFaculty() {
  clearTimeout(_ovLookupTimerStf);
  _ovLookupTimerStf = setTimeout(async function(){
    var reg = ((document.getElementById('stf_regNum')||{}).value||'').trim().toUpperCase();
    if (reg.length < 4) return;
    try {
      var students = await api.students();
      var found = students.find(function(s){
        return (s.register_number||'').toUpperCase() === reg ||
               (s.roll_number||'').toUpperCase()     === reg ||
               (s.student_id||'').toUpperCase()      === reg;
      });
      if (found) {
        var nEl = document.getElementById('stf_studentName'); if(nEl && !nEl.value) nEl.value = found.name || '';
        var dEl = document.getElementById('stf_dept');   if(dEl && !dEl.value && found.department) dEl.value = found.department;
        var yEl = document.getElementById('stf_year');   if(yEl && !yEl.value && found.year)       yEl.value = found.year;
        var sEl = document.getElementById('stf_section');if(sEl && !sEl.value && found.section)    sEl.value = found.section;
      }
    } catch(e){ /* non-fatal */ }
  }, 500);
}

// Legacy alias for old call sites that use ovLookupStudent()
function ovLookupStudent(){ ovLookupStudentFaculty(); }

async function submitOverrideFaculty() {
  var facId    = (document.getElementById('stf_facultyId')||{value:''}).value.trim();
  var dept       = (document.getElementById('stf_dept')||{value:''}).value;
  var year       = (document.getElementById('stf_year')||{value:''}).value;
  var semester   = (document.getElementById('stf_semester')||{value:''}).value;
  var section    = (document.getElementById('stf_section')||{value:''}).value;
  var regNum     = (document.getElementById('stf_regNum')||{value:''}).value.trim().toUpperCase();
  var stuName    = (document.getElementById('stf_studentName')||{value:''}).value.trim();
  var courseCode = (document.getElementById('stf_courseCode')||{value:''}).value.trim().toUpperCase();
  var courseName = (document.getElementById('stf_courseName')||{value:''}).value.trim();
  var period     = (document.getElementById('stf_period')||{value:''}).value;
  var date       = (document.getElementById('stf_date')||{value:''}).value;
  var fromVal    = (document.getElementById('stf_from')||{value:'Absent'}).value;
  var toVal      = (document.getElementById('stf_to')||{value:'Present'}).value;
  var cat        = (document.getElementById('stf_cat')||{value:''}).value;
  var reason     = (document.getElementById('stf_reason')||{value:''}).value.trim();

  // Validate
  if (!facId)    { toast('Faculty ID is required', 'warn'); document.getElementById('stf_facultyId').focus(); return; }
  if (!dept)       { toast('Department is required', 'warn'); document.getElementById('stf_dept').focus(); return; }
  if (!year)       { toast('Year is required', 'warn'); document.getElementById('stf_year').focus(); return; }
  if (!semester)   { toast('Semester is required', 'warn'); document.getElementById('stf_semester').focus(); return; }
  if (!section)    { toast('Section is required', 'warn'); document.getElementById('stf_section').focus(); return; }
  if (!regNum)     { toast('Register Number is required', 'warn'); document.getElementById('stf_regNum').focus(); return; }
  if (!courseCode) { toast('Course Code is required', 'warn'); document.getElementById('stf_courseCode').focus(); return; }
  if (!period)     { toast('Period is required', 'warn'); document.getElementById('stf_period').focus(); return; }
  if (!date)       { toast('Date is required', 'warn'); document.getElementById('stf_date').focus(); return; }
  if (!reason)     { toast('Reason is mandatory — please explain the override', 'warn'); document.getElementById('stf_reason').focus(); return; }

  var fullReason = cat ? '[' + cat + '] ' + reason : reason;

  await _ovSubmitToApi({
    faculty_id:                facId,
    faculty_role:              'Subject Faculty',
    target_id:               regNum,
    department:              dept,
    year:                    year,
    semester:                semester,
    section:                 section,
    student_register_number: regNum,
    student_name:            stuName,
    course_code:             courseCode,
    course_name:             courseName,
    period:                  period,
    attendance_from:         fromVal,
    attendance_to:           toVal,
    reason:                  fullReason
  }, 'overrideModal_faculty');
}

// Legacy alias — both names call the router
function submitOverrideNew() {
  openOverrideModal();
}
function submitOverride(){ submitOverrideNew(); }

// ── Render overrides page (KPI + history table + legacy log) ─
async function renderOverridesPage() {
  // Apply role-based UI restrictions first
  await applyOverrideButtonVisibility();

  // KPI strip
  try {
    var stats = await api.overrideStats();
    var setKpi = function(id, val){ var el=document.getElementById(id); if(el) el.textContent=val||0; };
    setKpi('ovKpiTotal', stats.total);
    setKpi('ovKpiToday', stats.today);
    setKpi('ovKpiFaculty', stats.faculty_count);
    var lastEl = document.getElementById('ovKpiLast');
    if(lastEl && stats.last_override && stats.last_override.overridden_by)
      lastEl.textContent = stats.last_override.overridden_by;
  } catch(e){ /* non-fatal */ }

  // New table + legacy log in parallel
  renderOverrideHistoryTable();
  renderLegacyOverridePage();

  // Section A: Show pending correction requests panel for faculty/classincharge/teacher
  var facRoles = ['faculty','teacher','classincharge','hod','admin'];
  if (facRoles.indexOf(APP.role) !== -1) {
    var sec = document.getElementById('facPendingSection');
    if (sec) sec.classList.remove('dn');
    loadFacultyPendingRequests();
  }
}


// ═══════════════════════════════════════════════════════════════
// SECTION A — Faculty Pending Correction Requests
// Loaded at the top of the Overrides page for faculty / HOD / admin.
// ═══════════════════════════════════════════════════════════════

async function loadFacultyPendingRequests() {
  var body     = document.getElementById('facPendingBody');
  var countEl  = document.getElementById('facPendingCount');
  if (!body) return;

  body.innerHTML = '<div style="text-align:center;padding:28px;color:var(--text2)"><i class="fa fa-spinner fa-spin"></i> Loading pending requests...</div>';

  // Build query: HOD/admin get all HOD-required; faculty get their own same-day queue
  var isHodAdmin = (APP.role === 'hod' || APP.role === 'admin');
  var facId      = (_user && _user.fac_id) ? _user.fac_id : '';
  var params     = new URLSearchParams();
  if (isHodAdmin) {
    params.set('hod_only', 'true');
  } else {
    if (facId) params.set('faculty_id', facId);
  }

  var requests = [];
  try {
    var res  = await apiFetch('/api/attendance/override/pending?' + params.toString());
    requests = (res && res.requests) ? res.requests : (Array.isArray(res) ? res : []);
  } catch(e) {
    body.innerHTML = '<div style="text-align:center;padding:28px;color:var(--danger)"><i class="fa fa-circle-exclamation"></i> ' + (e.message||'Failed to load') + ' <button class="btn-sm" onclick="loadFacultyPendingRequests()" style="margin-left:8px">Retry</button></div>';
    return;
  }

  if (countEl) countEl.textContent = requests.length;

  if (requests.length === 0) {
    body.innerHTML = '<div style="text-align:center;padding:32px;color:var(--text2)"><i class="fa fa-inbox" style="font-size:1.8rem;display:block;margin-bottom:8px;opacity:.4"></i><strong>No pending requests</strong><p style="margin:4px 0 0;font-size:.85rem">All correction requests have been resolved.</p></div>';
    return;
  }

  var rows = requests.map(function(r) {
    var hodBadge = r.hod_required
      ? '<span style="background:#fee2e2;color:#dc2626;border-radius:12px;padding:2px 8px;font-size:.72rem;font-weight:700;margin-left:4px;white-space:nowrap"><i class="fa fa-lock"></i> Needs HOD</span>'
      : '';
    var approveDisabled = r.hod_required && !isHodAdmin;
    var approveBtn = '<button '
      + (approveDisabled ? 'disabled title="HOD approval required" ' : 'onclick="_facApproveRequest(' + r.id + ')" ')
      + 'style="padding:5px 11px;border:none;border-radius:6px;cursor:' + (approveDisabled?'not-allowed':'pointer') + ';font-size:.78rem;font-weight:700;'
      + (approveDisabled ? 'background:#e5e7eb;color:#9ca3af' : 'background:#dcfce7;color:#16a34a')
      + '">'
      + '<i class="fa fa-check"></i> Approve</button>';
    var rejectBtn  = '<button onclick="_facRejectRequest(' + r.id + ')" '
      + 'style="padding:5px 11px;border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:700;background:#fee2e2;color:#dc2626;margin-left:4px">'
      + '<i class="fa fa-xmark"></i> Reject</button>';

    var submittedDate = (r.created_at || '').split(' ')[0] || '—';

    return '<tr style="border-bottom:1px solid var(--border)">'
      + '<td style="padding:9px 10px;font-size:.84rem;color:var(--text1)">' + (r.student_id||'—') + hodBadge + '</td>'
      + '<td style="padding:9px 10px;font-size:.84rem;color:var(--text2)">' + (r.course_code||r.subject_id||'—') + '</td>'
      + '<td style="padding:9px 10px;font-size:.84rem;color:var(--text2)">' + (r.date||'—') + '</td>'
      + '<td style="padding:9px 10px;font-size:.84rem;color:var(--text2)">' + (r.period||'—') + '</td>'
      + '<td style="padding:9px 10px"><span style="background:#fee2e2;color:#dc2626;padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:700">' + (r.old_status||'Absent') + '</span></td>'
      + '<td style="padding:9px 10px"><span style="background:#dcfce7;color:#16a34a;padding:2px 8px;border-radius:12px;font-size:.75rem;font-weight:700">' + (r.new_status||'Present') + '</span></td>'
      + '<td style="padding:9px 10px;font-size:.82rem;color:var(--text2);max-width:160px" title="' + (r.reason||'') + '">' + ((r.reason||'').length>50 ? r.reason.substring(0,50)+'…' : (r.reason||'—')) + '</td>'
      + '<td style="padding:9px 10px;font-size:.8rem;color:var(--text3)">' + submittedDate + '</td>'
      + '<td style="padding:9px 10px;white-space:nowrap">' + approveBtn + rejectBtn + '</td>'
      + '</tr>';
  }).join('');

  body.innerHTML = '<div class="table-scroll"><table class="data-tbl" style="min-width:820px">'
    + '<thead><tr>'
    + '<th>Student</th><th>Subject</th><th>Date</th><th>Period</th>'
    + '<th>From</th><th>To</th><th>Reason</th><th>Submitted</th><th>Actions</th>'
    + '</tr></thead>'
    + '<tbody>' + rows + '</tbody>'
    + '</table></div>';
}

// ── Approve a single request ──────────────────────────────────
async function _facApproveRequest(requestId) {
  try {
    await apiFetch('/api/attendance/override/' + requestId + '/approve', {
      method: 'POST',
      body:   JSON.stringify({ reason: 'Faculty approved' })
    });
    toast('Request #' + requestId + ' approved ✓', 'success');
    loadFacultyPendingRequests();
  } catch(e) {
    toast('Approve failed: ' + (e.message||'Unknown error'), 'error');
  }
}

// ── Reject a request — inline reason prompt ───────────────────
function _facRejectRequest(requestId) {
  // Build inline reject modal inside facPendingBody to avoid browser prompt()
  var existingPrompt = document.getElementById('facRejectPrompt');
  if (existingPrompt) existingPrompt.remove();

  var prompt = document.createElement('div');
  prompt.id  = 'facRejectPrompt';
  prompt.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center';
  prompt.innerHTML = [
    '<div style="background:var(--card-bg,#fff);border-radius:14px;padding:26px 22px;width:min(420px,90vw);box-shadow:0 8px 40px rgba(0,0,0,.2)">',
    '  <h4 style="margin:0 0 14px;font-size:1rem;color:var(--text1)"><i class="fa fa-xmark-circle" style="color:#dc2626;margin-right:6px"></i>Reject Request #' + requestId + '</h4>',
    '  <p style="margin:0 0 10px;font-size:.875rem;color:var(--text2)">Please provide a reason for rejection (required):</p>',
    '  <textarea id="facRejectReason" rows="3" placeholder="e.g. No supporting documents provided..." ',
    '    style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;resize:vertical;color:var(--text1);font-size:.875rem;font-family:inherit;box-sizing:border-box"></textarea>',
    '  <div id="facRejectErr" style="color:var(--danger);font-size:.78rem;margin-top:3px;display:none">Reason must be at least 5 characters.</div>',
    '  <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:14px">',
    '    <button onclick="document.getElementById(\'facRejectPrompt\').remove()" ',
    '      style="padding:8px 16px;border:1.5px solid var(--border);background:var(--bg2,#f1f5f9);border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:600;color:var(--text2)">Cancel</button>',
    '    <button onclick="_facRejectSubmit(' + requestId + ')" ',
    '      style="padding:8px 18px;background:#dc2626;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:700"><i class="fa fa-xmark"></i> Reject</button>',
    '  </div>',
    '</div>',
  ].join('');
  document.body.appendChild(prompt);
  document.getElementById('facRejectReason').focus();
}

async function _facRejectSubmit(requestId) {
  var reason = (document.getElementById('facRejectReason')?.value || '').trim();
  var errEl  = document.getElementById('facRejectErr');
  if (reason.length < 5) {
    if (errEl) errEl.style.display = 'block';
    return;
  }
  try {
    await apiFetch('/api/attendance/override/' + requestId + '/reject', {
      method: 'POST',
      body:   JSON.stringify({ reason: reason })
    });
    document.getElementById('facRejectPrompt')?.remove();
    toast('Request #' + requestId + ' rejected', 'warn');
    loadFacultyPendingRequests();
  } catch(e) {
    toast('Reject failed: ' + (e.message||'Unknown error'), 'error');
  }
}


// ── New attendance_overrides history table ───────────────────
async function renderOverrideHistoryTable() {
  var tbody = document.getElementById('ovTbody');
  if(!tbody) return;
  tbody.innerHTML = '<tr><td colspan="17" style="text-align:center;padding:20px"><i class="fa fa-spinner fa-spin"></i> Loading override history...</td></tr>';

  var dept    = ((document.getElementById('ovFilterDept') ||{}).value||'');
  var year    = ((document.getElementById('ovFilterYear') ||{}).value||'');
  var sem     = ((document.getElementById('ovFilterSem')  ||{}).value||'');
  var sec     = ((document.getElementById('ovFilterSec')  ||{}).value||'');
  var typeF   = ((document.getElementById('ovTypeFilter') ||{}).value||'');

  try {
    var params={};
    if(dept) params.department=dept;
    if(year) params.year=year;
    if(sem)  params.semester=sem;
    if(sec)  params.section=sec;

    var rows = await api.overrideHistory(params);

    if(typeF) {
      rows = rows.filter(function(r){
        return (r.faculty_role||'').toLowerCase().includes(typeF.toLowerCase());
      });
    }

    if(!rows||!rows.length){
      tbody.innerHTML='<tr><td colspan="17" style="text-align:center;padding:28px;color:var(--text3)"><i class="fa fa-inbox" style="font-size:1.5rem;display:block;margin-bottom:.4rem"></i>No override records found'+(dept||year||sem||sec?' for this filter':'')+'</td></tr>';
      return;
    }

    // Populate dept filter from live data
    var deptSel = document.getElementById('ovFilterDept');
    if(deptSel && deptSel.options.length<=1) {
      try {
        var allRows = await api.overrideHistory({limit:2000});
        var depts = [];
        allRows.forEach(function(r){ if(r.department && depts.indexOf(r.department)<0) depts.push(r.department); });
        depts.sort();
        depts.forEach(function(d){ deptSel.innerHTML+='<option value="'+d+'">'+d+'</option>'; });
      } catch(e){}
    }

    var attBadge = function(val) {
      var v=(val||'').toLowerCase();
      var map={present:'#d1fae5;color:#065f46',absent:'#fee2e2;color:#991b1b',late:'#fef3c7;color:#92400e',od:'#ede9fe;color:#5b21b6',medical:'#fce7f3;color:#9d174d'};
      var c=map[v]||'#f1f5f9;color:#475569';
      return '<span style="background:'+c+';padding:2px 9px;border-radius:12px;font-size:.78rem;font-weight:600;white-space:nowrap">'+(val||'-')+'</span>';
    };

    var roleBadge = function(role) {
      var r=(role||'').toLowerCase();
      var c='#f1f5f9;color:#475569';
      if(r.includes('admin')||r.includes('hod')) c='#fef3c7;color:#92400e';
      else if(r.includes('incharge'))            c='#dbeafe;color:#1e40af';
      else if(r.includes('subject')||r.includes('faculty')) c='#d1fae5;color:#065f46';
      return '<span style="background:'+c+';padding:2px 8px;border-radius:10px;font-size:.75rem;white-space:nowrap">'+(role||'-')+'</span>';
    };

    var yearSuffix = function(y){ var n=parseInt(y); if(!n) return y; return y+(n===1?'st':n===2?'nd':n===3?'rd':'th')+' Yr'; };

    tbody.innerHTML = rows.map(function(r) {
      return '<tr>'+
        '<td style="font-weight:700;color:var(--accent);white-space:nowrap">'+(r.department||'—')+'</td>'+
        '<td style="white-space:nowrap">'+(r.year?yearSuffix(r.year):'—')+'</td>'+
        '<td style="white-space:nowrap">'+(r.semester?'Sem '+r.semester:'—')+'</td>'+
        '<td><span style="font-weight:700;color:#4f46e5">'+( r.section?'Sec '+r.section:'—')+'</span></td>'+
        '<td style="font-family:monospace;font-size:.84rem;font-weight:600">'+(r.student_register_number||'—')+'</td>'+
        '<td style="font-weight:500">'+(r.student_name||'—')+'</td>'+
        '<td style="font-family:monospace;font-size:.82rem;color:#0ea5e9;font-weight:600">'+(r.course_code||'—')+'</td>'+
        '<td style="font-size:.82rem;max-width:120px;word-break:break-word">'+(r.course_name||'—')+'</td>'+
        '<td style="font-size:.82rem;white-space:nowrap;font-weight:500">'+(r.period||'—')+'</td>'+
        '<td>'+attBadge(r.attendance_from)+'</td>'+
        '<td>'+attBadge(r.attendance_to)+'</td>'+
        '<td style="font-size:.8rem;max-width:170px;word-break:break-word">'+(r.reason||'—')+'</td>'+
        '<td style="font-weight:600;white-space:nowrap">'+(r.overridden_by||'—')+'</td>'+
        '<td style="font-family:monospace;font-size:.81rem">'+(r.faculty_id||'—')+'</td>'+
        '<td>'+roleBadge(r.faculty_role)+'</td>'+
        '<td style="white-space:nowrap;font-size:.81rem">'+(r.override_date||'—')+'</td>'+
        '<td style="font-size:.81rem">'+(r.override_time||'—')+'</td>'+
      '</tr>';
    }).join('');
  } catch(e) {
    tbody.innerHTML='<tr><td colspan="17" style="text-align:center;padding:20px;color:#dc2626"><i class="fa fa-exclamation-triangle"></i> Failed to load: '+e.message+'</td></tr>';
  }
}

// ── Legacy override_log table ─────────────────────────────────
async function renderLegacyOverridePage() {
  var tbody = document.getElementById('ovLegacyTbody');
  if(!tbody) return;
  tbody.innerHTML='<tr><td colspan="8" style="text-align:center;padding:12px"><i class="fa fa-spinner fa-spin"></i></td></tr>';
  try {
    var rows = await api.overrideLog(100);
    if(!rows||!rows.length){
      tbody.innerHTML='<tr><td colspan="8" style="text-align:center;padding:14px;color:var(--text3)"><i class="fa fa-inbox"></i> No legacy records yet</td></tr>';
      return;
    }
    var lf = ((document.getElementById('ovLegacyFilter')||{}).value||'');
    if(lf) {
      rows=rows.filter(function(r){
        var n=(r.note||'').toLowerCase(), t=(r.teacher||'').toLowerCase();
        if(lf==='faculty') return !n.includes('admin')&&!n.includes('incharge');
        if(lf==='classincharge') return n.includes('incharge');
        if(lf==='admin') return n.includes('admin')||n.includes('hod')||t==='admin';
        return true;
      });
    }
    if(!rows.length){
      tbody.innerHTML='<tr><td colspan="8" style="text-align:center;padding:14px;color:var(--text3)">No records match filter</td></tr>';
      return;
    }
    tbody.innerHTML=rows.map(function(r){
      var note=r.note||'';
      var byMatch=note.match(/\(by ([^)]+)\)/);
      var facId=byMatch?byMatch[1]:(r.teacher||'—');
      var cleanNote=note.replace(/\(by [^)]+\)/,'').replace(/^\[.*?\]\s*/,'').trim();
      var dt=r.created_at||'';
      var dp=dt.split(' ')[0]||'—';
      var tp=(dt.split(' ')[1]||'—').substring(0,8);
      var action=r.action||'';
      var badge=action==='mark_present'?
        '<span style="background:#d1fae5;color:#065f46;padding:2px 8px;border-radius:10px;font-size:.78rem;font-weight:600">Absent → Present</span>':
        action==='mark_absent'?
        '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:10px;font-size:.78rem;font-weight:600">Present → Absent</span>':
        '<span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:10px;font-size:.78rem">'+action+'</span>';
      return '<tr>'+
        '<td><div style="font-weight:600;font-size:.82rem">'+dp+'</div><div style="color:var(--text3);font-size:.74rem">'+tp+'</div></td>'+
        '<td style="font-weight:600">'+(r.teacher||'—')+'</td>'+
        '<td style="font-family:monospace;font-size:.81rem">'+facId+'</td>'+
        '<td><div style="font-weight:600">'+(r.student_name||r.student_id||'—')+'</div><div style="font-size:.74rem;color:var(--text3)">'+(r.roll_number||'')+'</div></td>'+
        '<td style="font-size:.81rem">'+(r.department||'?')+' / Sec '+(r.section||'?')+'</td>'+
        '<td style="font-size:.81rem">'+(r.period||'—')+'</td>'+
        '<td>'+badge+'</td>'+
        '<td style="font-size:.79rem;max-width:160px;word-break:break-word">'+(cleanNote||'—')+'</td>'+
      '</tr>';
    }).join('');
  } catch(e){
    tbody.innerHTML='<tr><td colspan="8" style="text-align:center;padding:14px;color:#dc2626">Failed: '+e.message+'</td></tr>';
  }
}

// Alias kept for any old callers
function renderOverridePage(){ renderLegacyOverridePage(); }

// ── REPORTS ───────────────────────────────────────────────────

// ═══════════════════════════════════════════════════════════════
// STUDENT CORRECTION REQUEST PAGE  — renderStudentCorrectionPage()
// Allows students to view their absent records and raise
// correction requests that go to faculty / HOD for approval.
// ═══════════════════════════════════════════════════════════════
async function renderStudentCorrectionPage() {
  var pg = document.getElementById('pg-correction');
  if (!pg) return;

  pg.innerHTML = '<div style="text-align:center;padding:40px"><i class="fa fa-spinner fa-spin" style="font-size:2rem;color:var(--primary)"></i><p style="margin-top:12px;color:var(--text2)">Loading your attendance...</p></div>';

  // Fetch student attendance
  var records = [];
  try {
    var res = await apiFetch('/api/attendance/my');
    records = Array.isArray(res) ? res : (res.records || res.attendance || []);
  } catch(e) {
    pg.innerHTML = '<div style="text-align:center;padding:40px;color:var(--danger)"><i class="fa fa-circle-exclamation" style="font-size:2rem"></i><p style="margin-top:12px">' + (e.message || 'Failed to load attendance') + '</p><button class="btn-primary" onclick="renderStudentCorrectionPage()" style="margin-top:12px"><i class="fa fa-rotate-right"></i> Retry</button></div>';
    return;
  }

  // Filter absent records
  var absentRecs = records.filter(function(r) {
    var st = (r.status || r.attendance_status || '').toLowerCase();
    return st === 'absent' || st === 'a';
  });

  pg.innerHTML = [
    '<div class="page-header" style="padding:20px 24px 0">',
    '  <h2 style="margin:0;font-size:1.25rem;font-weight:700;color:var(--text1)">',
    '    <i class="fa fa-hand-paper" style="color:var(--primary);margin-right:8px"></i>',
    '    Request Attendance Correction',
    '  </h2>',
    '  <p style="margin:4px 0 0;color:var(--text2);font-size:.875rem">',
    '    Found <strong>' + absentRecs.length + '</strong> absent record(s). Click <em>Request Correction</em> to raise a query.',
    '  </p>',
    '</div>',

    // ── Correction Request Modal ──────────────────────────────
    '<div id="corrModal" class="dn" style="position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center">',
    '  <div style="background:var(--card-bg,#fff);border-radius:14px;padding:28px 24px;width:min(480px,92vw);box-shadow:0 8px 40px rgba(0,0,0,.18);position:relative">',
    '    <button onclick="document.getElementById(\'corrModal\').classList.add(\'dn\')" style="position:absolute;top:12px;right:14px;background:none;border:none;font-size:1.3rem;cursor:pointer;color:var(--text2)">&#x2715;</button>',
    '    <h3 style="margin:0 0 18px;font-size:1.05rem;color:var(--text1)"><i class="fa fa-pen-to-square" style="color:var(--primary);margin-right:6px"></i>Request Correction</h3>',
    '    <div style="display:grid;gap:12px">',
    '      <div>',
    '        <label style="font-size:.8rem;font-weight:600;color:var(--text2);display:block;margin-bottom:4px">Subject</label>',
    '        <input id="corrSubject" readonly style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;background:var(--bg2,#f8f9fa);color:var(--text1);font-size:.9rem;box-sizing:border-box">',
    '      </div>',
    '      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">',
    '        <div>',
    '          <label style="font-size:.8rem;font-weight:600;color:var(--text2);display:block;margin-bottom:4px">Date</label>',
    '          <input id="corrDate" readonly style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;background:var(--bg2,#f8f9fa);color:var(--text1);font-size:.9rem;box-sizing:border-box">',
    '        </div>',
    '        <div>',
    '          <label style="font-size:.8rem;font-weight:600;color:var(--text2);display:block;margin-bottom:4px">Current Status</label>',
    '          <input id="corrOldStatus" readonly value="Absent" style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;background:var(--bg2,#f8f9fa);color:#dc2626;font-size:.9rem;font-weight:600;box-sizing:border-box">',
    '        </div>',
    '      </div>',
    '      <div>',
    '        <label style="font-size:.8rem;font-weight:600;color:var(--text2);display:block;margin-bottom:4px">Requested Status <span style="color:var(--danger)">*</span></label>',
    '        <select id="corrNewStatus" style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;background:var(--card-bg,#fff);color:var(--text1);font-size:.9rem;box-sizing:border-box">',
    '          <option value="Present">Present</option>',
    '          <option value="OD">OD (On Duty)</option>',
    '          <option value="Medical">Medical Leave</option>',
    '          <option value="Late">Late</option>',
    '        </select>',
    '      </div>',
    '      <div>',
    '        <label style="font-size:.8rem;font-weight:600;color:var(--text2);display:block;margin-bottom:4px">Reason <span style="color:var(--danger)">*</span></label>',
    '        <textarea id="corrReason" rows="3" placeholder="Explain why attendance should be corrected (min 10 characters)..." style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;resize:vertical;color:var(--text1);font-size:.9rem;font-family:inherit;box-sizing:border-box"></textarea>',
    '        <div id="corrReasonErr" style="color:var(--danger);font-size:.78rem;margin-top:3px;display:none">Reason must be at least 10 characters.</div>',
    '      </div>',
    '      <div id="corrHodWarn" class="dn" style="background:#fef3c7;border:1.5px solid #f59e0b;border-radius:8px;padding:10px 12px;font-size:.83rem;color:#92400e">',
    '        <i class="fa fa-triangle-exclamation"></i> <strong>Old record:</strong> HOD approval will be required for this correction.',
    '      </div>',
    '      <div id="corrSuccessMsg" class="dn" style="background:#dcfce7;border:1.5px solid #16a34a;border-radius:8px;padding:10px 12px;font-size:.88rem;color:#166534;font-weight:600">',
    '        <i class="fa fa-circle-check"></i> <span id="corrSuccessText"></span>',
    '      </div>',
    '      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:4px">',
    '        <button onclick="document.getElementById(\'corrModal\').classList.add(\'dn\')" style="padding:9px 18px;border:1.5px solid var(--border);background:var(--bg2,#f1f5f9);border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:600;color:var(--text2)">Cancel</button>',
    '        <button id="corrSubmitBtn" onclick="_submitCorrectionRequest()" style="padding:9px 20px;background:var(--primary);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:700"><i class="fa fa-paper-plane"></i> Submit Request</button>',
    '      </div>',
    '    </div>',
    '  </div>',
    '</div>',

    // ── Absent Records Table ──────────────────────────────────
    '<div style="padding:20px 24px">',
  ].join('\n');

  if (absentRecs.length === 0) {
    pg.innerHTML += '<div style="text-align:center;padding:48px 20px;color:var(--text2)"><i class="fa fa-circle-check" style="font-size:2.5rem;color:#16a34a;display:block;margin-bottom:12px"></i><strong style="font-size:1.05rem;color:var(--text1)">No absent records found!</strong><p style="margin:6px 0 0;font-size:.9rem">Your attendance looks good.</p></div>';
  } else {
    var tableRows = absentRecs.map(function(r, i) {
      var subj    = r.course_name || r.subject || r.course_code || '—';
      var code    = r.course_code || '';
      var dateVal = r.date || r.attendance_date || '';
      var period  = r.period || r.period_no || '';
      var facId   = r.faculty_id || r.faculty_id || '';

      // Check if old record (before today)
      var isOld = false;
      try {
        isOld = dateVal && new Date(dateVal) < new Date(new Date().toDateString());
      } catch(e2) {}

      return '<tr style="border-bottom:1px solid var(--border)">' +
        '<td style="padding:10px 12px;font-size:.875rem;color:var(--text1)">' + subj + (code ? '<br><span style="font-size:.75rem;color:var(--text2)">' + code + '</span>' : '') + '</td>' +
        '<td style="padding:10px 12px;font-size:.875rem;color:var(--text2)">' + (dateVal || '—') + '</td>' +
        '<td style="padding:10px 12px;font-size:.875rem;color:var(--text2)">' + (period || '—') + '</td>' +
        '<td style="padding:10px 12px"><span style="background:#fee2e2;color:#dc2626;padding:3px 10px;border-radius:20px;font-size:.78rem;font-weight:700">Absent</span>' +
        (isOld ? ' <span style="background:#fef3c7;color:#92400e;padding:2px 7px;border-radius:10px;font-size:.72rem;margin-left:4px">Old</span>' : '') + '</td>' +
        '<td style="padding:10px 12px">' +
        '<button onclick="_openCorrModal(' + JSON.stringify({idx:i,subj:subj,code:code,date:dateVal,period:period,facId:facId,isOld:isOld,record:r}) + ')" ' +
        'style="padding:7px 14px;background:var(--primary);color:#fff;border:none;border-radius:7px;cursor:pointer;font-size:.8rem;font-weight:600">' +
        '<i class="fa fa-pen-to-square"></i> Request Correction</button>' +
        '</td>' +
        '</tr>';
    }).join('');

    pg.innerHTML += [
      '<div style="overflow-x:auto;border-radius:10px;border:1.5px solid var(--border)">',
      '<table style="width:100%;border-collapse:collapse">',
      '  <thead><tr style="background:var(--bg2,#f8f9fa)">',
      '    <th style="padding:11px 12px;text-align:left;font-size:.8rem;font-weight:700;color:var(--text2);border-bottom:1.5px solid var(--border)">Subject</th>',
      '    <th style="padding:11px 12px;text-align:left;font-size:.8rem;font-weight:700;color:var(--text2);border-bottom:1.5px solid var(--border)">Date</th>',
      '    <th style="padding:11px 12px;text-align:left;font-size:.8rem;font-weight:700;color:var(--text2);border-bottom:1.5px solid var(--border)">Period</th>',
      '    <th style="padding:11px 12px;text-align:left;font-size:.8rem;font-weight:700;color:var(--text2);border-bottom:1.5px solid var(--border)">Status</th>',
      '    <th style="padding:11px 12px;text-align:left;font-size:.8rem;font-weight:700;color:var(--text2);border-bottom:1.5px solid var(--border)">Action</th>',
      '  </thead>',
      '  <tbody>' + tableRows + '</tbody>',
      '</table>',
      '</div>',
    ].join('\n');
  }

  pg.innerHTML += '</div>'; // close padding div

  // Store records for modal access
  window._corrAbsentRecs = absentRecs;
}

// ── Open the correction modal pre-filled for a specific record ──
function _openCorrModal(info) {
  var modal = document.getElementById('corrModal');
  if (!modal) return;

  document.getElementById('corrSubject').value   = info.subj + (info.code ? ' (' + info.code + ')' : '');
  document.getElementById('corrDate').value      = info.date || '';
  document.getElementById('corrOldStatus').value = 'Absent';
  document.getElementById('corrNewStatus').value = 'Present';
  document.getElementById('corrReason').value    = '';
  document.getElementById('corrReasonErr').style.display = 'none';

  // Show HOD warning for old records
  var hodWarn = document.getElementById('corrHodWarn');
  if (info.isOld) hodWarn.classList.remove('dn'); else hodWarn.classList.add('dn');

  // Reset success message
  document.getElementById('corrSuccessMsg').classList.add('dn');
  document.getElementById('corrSubmitBtn').disabled = false;
  document.getElementById('corrSubmitBtn').innerHTML = '<i class="fa fa-paper-plane"></i> Submit Request';

  // Store record context for submit
  modal._corrInfo = info;

  modal.classList.remove('dn');
  modal.style.display = 'flex';
  document.getElementById('corrReason').focus();
}

// ── Submit the correction request to the API ──
async function _submitCorrectionRequest() {
  var modal   = document.getElementById('corrModal');
  var info    = modal._corrInfo || {};
  var reason  = (document.getElementById('corrReason').value || '').trim();
  var newSt   = document.getElementById('corrNewStatus').value;
  var errEl   = document.getElementById('corrReasonErr');
  var btn     = document.getElementById('corrSubmitBtn');

  // Validation
  if (reason.length < 10) {
    errEl.style.display = 'block';
    document.getElementById('corrReason').focus();
    return;
  }
  errEl.style.display = 'none';

  // Get student ID from session
  var studentId = (_user && (_user.register_number || _user.reg_no || _user.username || _user.sub || ''));

  var payload = {
    student_id:  studentId,
    faculty_id:  info.facId || '',
    subject_id:  info.code  || '',
    old_status:  'Absent',
    new_status:  newSt,
    reason:      reason,
    date:        info.date   || '',
    course_code: info.code   || '',
    period:      info.period || ''
  };

  btn.disabled = true;
  btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Submitting...';

  try {
    var res = await apiFetch('/api/attendance/override/request', {
      method: 'POST',
      body:   JSON.stringify(payload)
    });

    var successEl   = document.getElementById('corrSuccessMsg');
    var successText = document.getElementById('corrSuccessText');
    var msg = res.hod_required
      ? '⚠ Request submitted. HOD approval required (old record).'
      : '✓ Request submitted. Faculty will review your request.';

    successText.textContent = msg;
    successEl.classList.remove('dn');
    btn.innerHTML = '<i class="fa fa-circle-check"></i> Submitted';

    toast(res.hod_required ? 'Submitted — awaiting HOD approval' : 'Correction request submitted!', 'success');

    // Auto-close modal after 2.5 seconds
    setTimeout(function() {
      document.getElementById('corrModal').classList.add('dn');
      renderStudentCorrectionPage(); // refresh list
    }, 2500);

  } catch(e) {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa fa-paper-plane"></i> Submit Request';
    toast('Error: ' + (e.message || 'Submission failed'), 'error');
  }
}


// ═══════════════════════════════════════════════════════════════
//  REPORTS & ANALYTICS  — Full SaaS Dashboard
// ═══════════════════════════════════════════════════════════════

let _repChart1 = null, _repChart2 = null, _repChart3 = null;
let _repData   = null;
let _repSortCol = 'pct', _repSortAsc = true;

async function renderReportsPage() {
  const pg = document.getElementById('pg-reports');
  if (!pg) return;

  pg.innerHTML = `
  <style>
    .rep-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1.5rem; flex-wrap:wrap; gap:.75rem; }
    .rep-header h1 { margin:0; font-size:1.45rem; font-weight:800; color:#0f172a; letter-spacing:-.02em; }
    .rep-header .sub { font-size:.82rem; color:#64748b; margin-top:3px; }
    .rep-header .meta { display:flex; align-items:center; gap:1rem; flex-shrink:0; }
    .rep-header .time-badge { background:#f1f5f9; border:1px solid #e2e8f0; border-radius:10px; padding:.4rem .85rem; font-size:.8rem; color:#475569; font-weight:600; display:flex; align-items:center; gap:.4rem; }

    .rep-filters { background:#fff; border:1px solid #e2e8f0; border-radius:16px; padding:1.1rem 1.25rem; margin-bottom:1.25rem; display:flex; align-items:center; gap:.75rem; flex-wrap:wrap; box-shadow:0 1px 4px rgba(0,0,0,.05); }
    .rep-filters select { height:38px; border:1.5px solid #e2e8f0; border-radius:10px; padding:0 .75rem; font-size:.83rem; color:#334155; background:#f8fafc; cursor:pointer; min-width:140px; font-weight:500; }
    .rep-filters select:focus { border-color:#6366f1; outline:none; background:#fff; }
    .rep-btn-gen { height:38px; padding:0 1.1rem; background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff; border:none; border-radius:10px; font-size:.85rem; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:.45rem; white-space:nowrap; box-shadow:0 2px 8px rgba(99,102,241,.3); transition:opacity .15s; }
    .rep-btn-gen:hover { opacity:.88; }
    .rep-btn-reset { height:38px; padding:0 .9rem; background:#f1f5f9; color:#475569; border:1.5px solid #e2e8f0; border-radius:10px; font-size:.83rem; font-weight:600; cursor:pointer; display:flex; align-items:center; gap:.4rem; transition:all .15s; }
    .rep-btn-reset:hover { background:#e2e8f0; }

    .rep-kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:1rem; margin-bottom:1.25rem; }
    .rep-kpi { background:#fff; border-radius:16px; padding:1.25rem 1.35rem; border:1px solid #e2e8f0; box-shadow:0 2px 8px rgba(0,0,0,.05); display:flex; align-items:center; gap:1rem; transition:transform .15s,box-shadow .15s; }
    .rep-kpi:hover { transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,.09); }
    .rep-kpi .kpi-ico { width:46px; height:46px; border-radius:12px; display:flex; align-items:center; justify-content:center; flex-shrink:0; font-size:1.15rem; }
    .rep-kpi .kpi-val { font-size:1.75rem; font-weight:800; color:#0f172a; line-height:1; }
    .rep-kpi .kpi-lbl { font-size:.74rem; font-weight:600; color:#64748b; margin-top:3px; }
    .rep-kpi .kpi-sub { font-size:.7rem; color:#94a3b8; margin-top:2px; }

    .rep-charts { display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-bottom:1.25rem; }
    @media(max-width:720px) { .rep-charts { grid-template-columns:1fr; } }

    .rep-card { background:#fff; border:1px solid #e2e8f0; border-radius:16px; padding:1.25rem; box-shadow:0 2px 8px rgba(0,0,0,.05); }
    .rep-card-title { font-size:.88rem; font-weight:700; color:#0f172a; display:flex; align-items:center; gap:.5rem; margin-bottom:1rem; }
    .rep-card-title i { color:#6366f1; }

    .rep-bar-row { margin-bottom:.65rem; }
    .rep-bar-label { display:flex; justify-content:space-between; align-items:center; margin-bottom:.3rem; }
    .rep-bar-label span { font-size:.78rem; font-weight:600; color:#334155; }
    .rep-bar-label .rpct { font-weight:700; }
    .rep-bar-track { height:10px; background:#f1f5f9; border-radius:5px; overflow:hidden; }
    .rep-bar-fill { height:100%; border-radius:5px; transition:width .6s cubic-bezier(.4,0,.2,1); }

    .rep-bottom { display:grid; grid-template-columns:1fr 380px; gap:1rem; margin-bottom:1.25rem; }
    @media(max-width:960px){ .rep-bottom { grid-template-columns:1fr; } }

    .rep-table-wrap { overflow-x:auto; }
    .rep-table { width:100%; border-collapse:collapse; font-size:.83rem; }
    .rep-table thead tr { background:#f8fafc; }
    .rep-table th { padding:.6rem .85rem; text-align:left; font-size:.72rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:.05em; border-bottom:2px solid #e2e8f0; white-space:nowrap; cursor:pointer; user-select:none; }
    .rep-table th:hover { color:#6366f1; }
    .rep-table th.sort-active { color:#6366f1; }
    .rep-table td { padding:.65rem .85rem; border-bottom:1px solid #f1f5f9; color:#334155; vertical-align:middle; }
    .rep-table tbody tr:hover { background:#f8fafc; }
    .rep-table tbody tr:last-child td { border-bottom:none; }

    .rep-badge { display:inline-flex; align-items:center; gap:.3rem; padding:.22rem .65rem; border-radius:20px; font-size:.72rem; font-weight:700; white-space:nowrap; }
    .rep-badge.good     { background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0; }
    .rep-badge.warning  { background:#fffbeb; color:#d97706; border:1px solid #fde68a; }
    .rep-badge.critical { background:#fef2f2; color:#dc2626; border:1px solid #fecaca; }

    .rep-insights { background:linear-gradient(135deg,#eef2ff,#f5f3ff); border:1px solid #c7d2fe; border-radius:16px; padding:1.1rem 1.25rem; }
    .rep-insight-item { display:flex; align-items:flex-start; gap:.65rem; padding:.45rem 0; border-bottom:1px solid rgba(99,102,241,.12); font-size:.82rem; color:#3730a3; line-height:1.45; }
    .rep-insight-item:last-child { border-bottom:none; }
    .rep-insight-item i { color:#6366f1; margin-top:.15rem; flex-shrink:0; }

    .rep-export-bar { display:flex; gap:.75rem; justify-content:flex-end; flex-wrap:wrap; margin-bottom:.5rem; }
    .rep-export-btn { height:38px; padding:0 1.1rem; border-radius:10px; font-size:.83rem; font-weight:700; cursor:pointer; display:flex; align-items:center; gap:.45rem; border:1.5px solid; transition:all .15s; }
    .rep-export-btn.csv  { background:#f0fdf4; color:#15803d; border-color:#bbf7d0; }
    .rep-export-btn.csv:hover  { background:#dcfce7; }
    .rep-export-btn.pdf  { background:#fff1f2; color:#dc2626; border-color:#fecaca; }
    .rep-export-btn.pdf:hover  { background:#fde8e8; }
    .rep-export-btn.send { background:linear-gradient(135deg,#6366f1,#8b5cf6); color:#fff; border-color:transparent; box-shadow:0 2px 8px rgba(99,102,241,.3); }
    .rep-export-btn.send:hover { opacity:.88; }

    .rep-skel { background:linear-gradient(90deg,#f1f5f9 25%,#e2e8f0 50%,#f1f5f9 75%); background-size:200% 100%; animation:rep-shim 1.4s infinite; border-radius:8px; }
    @keyframes rep-shim { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
    @keyframes rep-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(1.3)} }
    .rep-view-all { text-align:center; padding:.85rem; font-size:.82rem; color:#6366f1; font-weight:600; cursor:pointer; border-top:1px solid #f1f5f9; }
    .rep-view-all:hover { background:#f8fafc; border-radius:0 0 16px 16px; }
    .rep-empty { text-align:center; padding:2.5rem 1rem; color:#94a3b8; }
    .rep-empty i { font-size:2.2rem; opacity:.4; display:block; margin-bottom:.65rem; }
  </style>

  <!-- HEADER -->
  <div class="rep-header">
    <div>
      <h1><i class="fa fa-chart-line" style="color:#6366f1;margin-right:.5rem;font-size:1.3rem"></i>Reports &amp; Analytics</h1>
    </div>
    <div class="meta">
      <div class="time-badge">
        <i class="fa fa-clock"></i>
        <span id="repClock">--:-- --</span>&nbsp;·&nbsp;<span id="repDate">---</span>
      </div>
    </div>
  </div>

  <!-- FILTERS -->
  <div class="rep-filters">
    <select id="repDays">
      <option value="30">Last 30 Days</option>
      <option value="60">Last 60 Days</option>
      <option value="90">Last Quarter</option>
      <option value="180" selected>This Semester</option>
      <option value="365">Full Year</option>
    </select>
    <select id="repYear">
      <option value="">All Years</option>
      <option value="I">I Year</option>
      <option value="II">II Year</option>
      <option value="III">III Year</option>
      <option value="IV">IV Year</option>
    </select>
    <select id="repSection">
      <option value="">All Sections</option>
      <option value="A">Section A</option>
      <option value="B">Section B</option>
      <option value="C">Section C</option>
    </select>
    <button class="rep-btn-gen" onclick="_repGenerate()">
      <i class="fa fa-chart-bar"></i> Generate Report
    </button>
    <button class="rep-btn-reset" onclick="_repReset()">
      <i class="fa fa-rotate"></i> Reset
    </button>
  </div>

  <!-- KPI CARDS -->
  <div class="rep-kpis" id="repKpis">
    ${['Total Students','Average Attendance','Students Below 75%','Students Above 75%'].map(lbl=>`
      <div class="rep-kpi">
        <div class="kpi-ico rep-skel" style="width:46px;height:46px"></div>
        <div>
          <div class="rep-skel" style="width:70px;height:26px;margin-bottom:6px;border-radius:6px"></div>
          <div class="kpi-lbl">${lbl}</div>
        </div>
      </div>`).join('')}
  </div>

  <!-- THREE CHART CARDS -->
  <div class="rep-charts">
    <div class="rep-card">
      <div class="rep-card-title" style="display:flex;align-items:center;justify-content:space-between">
        <span><i class="fa fa-graduation-cap"></i>Year-wise Attendance Performance</span>
        <span id="repLiveBadge" style="font-size:.66rem;font-weight:700;color:#16a34a;display:flex;align-items:center;gap:.3rem">
          <span style="width:7px;height:7px;border-radius:50%;background:#22c55e;display:inline-block;animation:rep-pulse 1.5s infinite"></span>LIVE
        </span>
      </div>
      <div id="repYearBars"><div class="rep-skel" style="height:150px"></div></div>
    </div>
    <div class="rep-card" style="display:flex;flex-direction:column">
      <div class="rep-card-title"><i class="fa fa-chart-pie"></i>Attendance Risk Analysis</div>
      <div style="flex:1;display:flex;align-items:center;gap:1rem;min-height:170px">
        <div style="flex:1;max-width:160px;height:160px;position:relative;margin:0 auto">
          <canvas id="repDonut"></canvas>
        </div>
        <div id="repDonutLegend" style="font-size:.75rem;line-height:1.9;color:#475569;flex-shrink:0">
          <div class="rep-skel" style="width:120px;height:60px"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- BOTTOM ROW -->
  <div class="rep-bottom">
    <!-- Table -->
    <div class="rep-card" style="padding:0;overflow:hidden">
      <div style="padding:1rem 1.25rem;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
        <div class="rep-card-title" style="margin:0"><i class="fa fa-user-xmark" style="color:#ef4444"></i>Students Requiring Immediate Attention</div>
        <span id="repTableCount" style="font-size:.74rem;color:#64748b;font-weight:600"></span>
      </div>
      <div id="repTableWrap" class="rep-table-wrap">
        <div class="rep-skel" style="height:220px;border-radius:0;margin:.75rem"></div>
      </div>
      <div class="rep-view-all" id="repViewAll" style="display:none" onclick="_repToggleAll()">View All</div>
    </div>

    <!-- Right col -->
    <div style="display:flex;flex-direction:column;gap:1rem">
      <div class="rep-card">
        <div class="rep-card-title"><i class="fa fa-arrow-trend-up"></i>Attendance Trend (30 Days)</div>
        <div style="position:relative;height:220px">
          <canvas id="repTrendChart"></canvas>
        </div>
      </div>
    </div>
  </div>

  <!-- EXPORT BAR -->
  <div class="rep-export-bar">
    <button class="rep-export-btn csv"  onclick="_repExportCSV()"><i class="fa fa-download"></i> Export CSV</button>
    <button class="rep-export-btn pdf"  onclick="_repExportPDF()"><i class="fa fa-file-pdf"></i> Export PDF</button>
    <button class="rep-export-btn send" onclick="_repSendReport()"><i class="fa fa-paper-plane"></i> Send Report</button>
  </div>

  <div style="text-align:center;font-size:.72rem;color:#94a3b8;padding:.4rem 0 .8rem">
    © ${new Date().getFullYear()} EduTrack Pro · Smart Attendance System · All rights reserved.
  </div>`;

  _repTickClock();
  if (window._repClockTimer) clearInterval(window._repClockTimer);
  window._repClockTimer = setInterval(_repTickClock, 1000);

  // ── Live auto-refresh: pull fresh attendance data every 15s so the
  //    Year-wise / Risk / Trend charts move in real time as attendance
  //    gets marked elsewhere, without the user needing to click
  //    "Generate Report" again. Stops automatically when the user
  //    navigates away (see showPage()).
  if (window._repPollTimer) clearInterval(window._repPollTimer);
  window._repPollTimer = setInterval(() => {
    if (APP.currentPage === 'reports' && !document.hidden) _repGenerate();
  }, 15000);

  await _repGenerate();
}

function _repTickClock() {
  const now = new Date();
  const el = document.getElementById('repClock');
  const de = document.getElementById('repDate');
  if (el) el.textContent = now.toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  if (de) de.textContent = now.toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric',year:'numeric'});
}

async function _repGenerate() {
  const days    = parseInt(document.getElementById('repDays')?.value    || 180);
  const year    = (document.getElementById('repYear')?.value    || '').trim();
  const section = (document.getElementById('repSection')?.value || '').trim();
  const dept    = (_user && _user.dept) ? _user.dept : '';

  let url = `/api/reports/analytics?days=${days}`;
  if (year)    url += `&year=${encodeURIComponent(year)}`;
  if (section) url += `&section=${encodeURIComponent(section)}`;
  if (dept)    url += `&dept=${encodeURIComponent(dept)}`;

  try {
    _repData = await apiFetch(url);
    _repRenderAll(_repData);
  } catch(e) {
    toast('Report generation failed: ' + e.message, 'error');
    const tw = document.getElementById('repTableWrap');
    if (tw) tw.innerHTML = `<div class="rep-empty"><i class="fa fa-circle-exclamation" style="color:#ef4444;opacity:1"></i><div style="color:#ef4444;font-weight:600">${e.message}</div><div style="font-size:.78rem;margin-top:.3rem">Check server connection and try again.</div></div>`;
  }
}

function _repReset() {
  const els = {repDays:'180', repYear:'', repSection:''};
  Object.entries(els).forEach(([id,val]) => { const el = document.getElementById(id); if(el) el.value = val; });
  _repGenerate();
}

function _repRenderAll(d) {
  const s = d.summary || {};

  // ── KPI cards ──────────────────────────────────────────────
  const kpiDefs = [
    { val: s.total_students  ?? '—', lbl:'Total Students',     sub:'All Years',          ibg:'#eef2ff', ic:'#6366f1', icon:'fa-users' },
    { val: (s.avg_attendance ?? '—') + (s.avg_attendance != null ? '%' : ''), lbl:'Average Attendance', sub:'Department Average',  ibg:'#f0fdf4', ic:'#16a34a', icon:'fa-chart-line' },
    { val: s.below_75_count  ?? '—', lbl:'Students Below 75%', sub:'Attendance < 75%',   ibg:'#fff7ed', ic:'#ea580c', icon:'fa-user-clock' },
    { val: s.above_75_count  ?? '—', lbl:'Students Above 75%', sub:'Attendance ≥ 75%',   ibg:'#f0fdf4', ic:'#16a34a', icon:'fa-user-check' },
  ];
  const kpiEl = document.getElementById('repKpis');
  if (kpiEl) kpiEl.innerHTML = kpiDefs.map(k => `
    <div class="rep-kpi">
      <div class="kpi-ico" style="background:${k.ibg}"><i class="fa ${k.icon}" style="color:${k.ic}"></i></div>
      <div>
        <div class="kpi-val">${k.val}</div>
        <div class="kpi-lbl">${k.lbl}</div>
        <div class="kpi-sub">${k.sub}</div>
      </div>
    </div>`).join('');

  // ── Year-wise bars ─────────────────────────────────────────
  const yw = d.year_wise || [];
  const ywEl = document.getElementById('repYearBars');
  if (ywEl) {
    if (!yw.length) {
      ywEl.innerHTML = '<div class="rep-empty"><i class="fa fa-chart-simple"></i><div style="font-size:.8rem">No year-wise data available</div></div>';
    } else {
      ywEl.innerHTML = yw.map(r => {
        const p = r.avg_pct || 0;
        const col = p >= 75 ? '#22c55e' : p >= 60 ? '#f59e0b' : '#ef4444';
        const yrLabel = r.year ? (r.year.toString().toLowerCase().includes('year') ? r.year : `${r.year} Year`) : '—';
        return `<div class="rep-bar-row">
          <div class="rep-bar-label">
            <span>${yrLabel} &nbsp;<span style="font-size:.68rem;color:#94a3b8;font-weight:500">(${r.count} students)</span></span>
            <span class="rpct" style="color:${col}">${p}%</span>
          </div>
          <div class="rep-bar-track"><div class="rep-bar-fill" style="width:${Math.min(p,100)}%;background:${col}"></div></div>
        </div>`;
      }).join('');
    }
  }

  // ── Donut chart ────────────────────────────────────────────
  if (_repChart3) { try { _repChart3.destroy(); } catch(e){} _repChart3 = null; }
  const above75  = s.above_75_count  || 0;
  const warning  = s.warning_count   || 0;
  const critical = s.critical_count  || 0;
  const total    = s.total_students  || 0;
  const dCtx = document.getElementById('repDonut');
  if (dCtx) {
    _repChart3 = new Chart(dCtx, {
      type: 'doughnut',
      data: {
        labels: ['Good (≥75%)', 'Warning (60–74%)', 'Critical (<60%)'],
        datasets: [{ data: [above75, warning, critical], backgroundColor:['#22c55e','#f59e0b','#ef4444'], borderWidth:3, borderColor:'#fff', hoverOffset:8 }]
      },
      options: {
        cutout:'68%', responsive:true, maintainAspectRatio:false,
        plugins: {
          legend:{display:false},
          tooltip:{callbacks:{label:ctx=>` ${ctx.label}: ${ctx.parsed} students (${total?Math.round(ctx.parsed/total*100):0}%)`}}
        }
      },
      plugins: [{
        id:'ct',
        beforeDraw(chart) {
          const {ctx:c, chartArea:{width,height,top}} = chart;
          c.save(); c.textAlign='center'; c.textBaseline='middle';
          const cx=width/2, cy=top+height/2;
          c.font='bold 20px system-ui,sans-serif'; c.fillStyle='#0f172a';
          c.fillText(total, cx, cy-7);
          c.font='600 10px system-ui,sans-serif'; c.fillStyle='#64748b';
          c.fillText('Total', cx, cy+8); c.restore();
        }
      }]
    });
  }
  const legEl = document.getElementById('repDonutLegend');
  if (legEl) legEl.innerHTML = [
    {color:'#22c55e', lbl:`Good (≥75%)`,     cnt:above75,  pct: total?Math.round(above75/total*100):0},
    {color:'#f59e0b', lbl:`Warning (60-75%)`, cnt:warning,  pct: total?Math.round(warning/total*100):0},
    {color:'#ef4444', lbl:`Critical (<60%)`,  cnt:critical, pct: total?Math.round(critical/total*100):0},
  ].map(l=>`
    <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.25rem">
      <span style="width:10px;height:10px;border-radius:50%;background:${l.color};flex-shrink:0;display:inline-block"></span>
      <span style="flex:1">${l.lbl}</span>
      <strong>${l.cnt}</strong>
      <span style="color:#94a3b8;font-size:.68rem">(${l.pct}%)</span>
    </div>`).join('');

  // ── Trend line chart ───────────────────────────────────────
  if (_repChart1) { try { _repChart1.destroy(); } catch(e){} _repChart1 = null; }
  const trend = d.trend || [];
  const tCtx  = document.getElementById('repTrendChart');
  if (tCtx) {
    if (trend.length) {
      _repChart1 = new Chart(tCtx, {
        type:'line',
        data:{
          labels: trend.map(r=>r.date?r.date.slice(5):''),
          datasets:[{
            label:'Attendance %',
            data: trend.map(r=>r.pct),
            borderColor:'#6366f1', backgroundColor:'rgba(99,102,241,.08)',
            fill:true, tension:.4, pointRadius:3, pointBackgroundColor:'#6366f1', borderWidth:2,
          }]
        },
        options:{
          responsive:true, maintainAspectRatio:false,
          scales:{
            y:{min:0,max:100,grid:{color:'#f1f5f9'},ticks:{callback:v=>v+'%',font:{size:9}},border:{display:false}},
            x:{grid:{display:false},ticks:{font:{size:9},maxRotation:45,maxTicksLimit:10}}
          },
          plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>` ${ctx.parsed.y}%`}}}
        }
      });
    } else {
      tCtx.style.display='none';
      tCtx.insertAdjacentHTML('afterend','<div class="rep-empty" style="padding:1rem"><i class="fa fa-chart-line"></i><div style="font-size:.8rem">No trend data for selected period</div></div>');
    }
  }

  // ── Critical students table ────────────────────────────────
  window._repAllStudents = d.below75_students || [];
  window._repShowAll     = false;
  _repSortCol = 'pct'; _repSortAsc = true;
  _repRenderTable(window._repAllStudents);
}

function _repRenderTable(students) {
  const wrap    = document.getElementById('repTableWrap');
  const countEl = document.getElementById('repTableCount');
  const viewAll = document.getElementById('repViewAll');
  if (!wrap) return;

  if (countEl) countEl.textContent = `${students.length} student${students.length!==1?'s':''} below 75%`;
  if (viewAll) {
    viewAll.style.display = students.length > 8 ? 'block' : 'none';
    viewAll.textContent   = window._repShowAll ? 'Show Less ↑' : `View All (${students.length}) ↓`;
  }

  if (!students.length) {
    wrap.innerHTML = `<div class="rep-empty">
      <i class="fa fa-circle-check" style="color:#22c55e;opacity:1;font-size:2.5rem"></i>
      <div style="color:#15803d;font-weight:700;font-size:.92rem;margin-top:.5rem">All students are above 75%</div>
      <div style="font-size:.78rem;margin-top:.3rem">No attendance concerns for the selected filters.</div>
    </div>`;
    return;
  }

  const displayRows = window._repShowAll ? students : students.slice(0,8);
  const si = col => col===_repSortCol ? (_repSortAsc?' ↑':' ↓') : '';
  const sc = col => col===_repSortCol ? 'sort-active' : '';

  wrap.innerHTML = `<table class="rep-table">
    <thead><tr>
      <th class="${sc('roll')}"    onclick="_repSort('roll')">Roll No${si('roll')}</th>
      <th class="${sc('name')}"    onclick="_repSort('name')">Student Name${si('name')}</th>
      <th class="${sc('year')}"    onclick="_repSort('year')">Year${si('year')}</th>
      <th class="${sc('section')}" onclick="_repSort('section')">Section${si('section')}</th>
      <th class="${sc('pct')}"     onclick="_repSort('pct')">Attendance %${si('pct')}</th>
      <th class="${sc('status')}"  onclick="_repSort('status')">Status${si('status')}</th>
    </tr></thead>
    <tbody>
      ${displayRows.map((r,i)=>{
        const pct    = r.pct??0;
        const isCrit = pct<60;
        const isWarn = pct>=60&&pct<75;
        const badge  = isCrit?'critical':isWarn?'warning':'good';
        const label  = isCrit
          ? '<i class="fa fa-circle-exclamation"></i> Critical'
          : '<i class="fa fa-triangle-exclamation"></i> Warning';
        const pctCol = isCrit?'#dc2626':'#d97706';
        return `<tr>
          <td><code style="font-size:.78rem;font-weight:700;color:#6366f1">${r.roll_number||'—'}</code></td>
          <td><span style="font-weight:600;color:#0f172a">${r.name||'—'}</span></td>
          <td><span style="font-size:.74rem;background:#f1f5f9;padding:.18rem .55rem;border-radius:5px;font-weight:600">${r.year ? (r.year.toString().toLowerCase().includes('year') || r.year.toString().toLowerCase().includes('yr') ? r.year : `${r.year} Yr`) : '—'}</span></td>
          <td><span style="font-size:.74rem;background:#f1f5f9;padding:.18rem .55rem;border-radius:5px;font-weight:600">${r.section||'—'}</span></td>
          <td>
            <div style="display:flex;align-items:center;gap:.55rem">
              <div style="width:56px;height:5px;background:#f1f5f9;border-radius:3px;overflow:hidden;flex-shrink:0">
                <div style="height:100%;width:${Math.min(pct,100)}%;background:${pctCol};border-radius:3px"></div>
              </div>
              <span style="font-weight:800;color:${pctCol};font-size:.85rem">${pct}%</span>
            </div>
          </td>
          <td><span class="rep-badge ${badge}">${label}</span></td>
        </tr>`;
      }).join('')}
    </tbody>
  </table>`;
}

function _repSort(col) {
  if (_repSortCol===col) { _repSortAsc=!_repSortAsc; }
  else { _repSortCol=col; _repSortAsc = col!=='pct'; }
  const keyMap = {roll:'roll_number',name:'name',year:'year',section:'section',pct:'pct',status:'pct'};
  const key    = keyMap[col]||col;
  const rows   = (window._repAllStudents||[]).slice();
  rows.sort((a,b)=>{
    const av=a[key]??'', bv=b[key]??'';
    if(typeof av==='number') return _repSortAsc?av-bv:bv-av;
    return _repSortAsc?String(av).localeCompare(String(bv)):String(bv).localeCompare(String(av));
  });
  window._repAllStudents=rows;
  _repRenderTable(rows);
}

function _repToggleAll() {
  window._repShowAll=!window._repShowAll;
  _repRenderTable(window._repAllStudents||[]);
}

function _repExportCSV() {
  const rows=(window._repAllStudents||[]);
  if(!rows.length){toast('No data to export','warn');return;}
  const hdr='Roll No,Name,Year,Section,Department,Attendance %,Status';
  const lines=rows.map(r=>[
    `"${r.roll_number||''}"`,`"${r.name||''}"`,
    `"${r.year||''}"`,`"${r.section||''}"`,`"${r.department||''}"`,
    r.pct||0, r.pct<60?'Critical':r.pct<75?'Warning':'Good',
  ].join(','));
  const blob=new Blob([hdr+'\n'+lines.join('\n')],{type:'text/csv'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=`attendance_report_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  toast('CSV exported successfully','success');
}

function _repExportPDF(){toast('PDF export — use browser Print → Save as PDF','info');window.print();}
function _repSendReport(){toast('Send Report — configure SMTP in Settings','info');}
function _repApplyFilters(){_repGenerate();}

async function renderHODApprovalsPage() {
  // Ensure the page container exists (created dynamically like pg-courses)
  var pg = document.getElementById('pg-hod_approvals');
  if (!pg) {
    pg = document.createElement('div');
    pg.id        = 'pg-hod_approvals';
    pg.className = 'page dn';
    document.getElementById('pageArea')?.appendChild(pg);
  }

  pg.innerHTML = [
    '<div class="page-header">',
    '  <div class="ph-left">',
    '    <h2><i class="fa fa-circle-check" style="color:var(--primary);margin-right:8px"></i>Pending HOD Approvals</h2>',
    '    <p>Review and action attendance correction requests from faculty and students</p>',
    '  </div>',
    '  <div class="ph-right">',
    '    <button class="btn-primary" onclick="renderHODApprovalsPage()"><i class="fa fa-rotate"></i> Refresh</button>',
    '  </div>',
    '</div>',

    // Summary KPI card
    '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:1.2rem">',
    '  <div class="kpi-card" style="--kc:#fef3c7;flex:1;min-width:160px">',
    '    <div class="kpi-icon" style="color:#d97706"><i class="fa fa-hourglass-half"></i></div>',
    '    <div class="kpi-val" id="hodPendingKpi">—</div>',
    '    <div class="kpi-lbl">Pending HOD Approvals</div>',
    '  </div>',
    '  <div class="kpi-card" style="--kc:#f0fdf4;flex:1;min-width:160px">',
    '    <div class="kpi-icon" style="color:#16a34a"><i class="fa fa-circle-check"></i></div>',
    '    <div class="kpi-val" id="hodApprovedKpi">—</div>',
    '    <div class="kpi-lbl">Approved Today</div>',
    '  </div>',
    '  <div class="kpi-card" style="--kc:#fff1f2;flex:1;min-width:160px">',
    '    <div class="kpi-icon" style="color:#dc2626"><i class="fa fa-ban"></i></div>',
    '    <div class="kpi-val" id="hodRejectedKpi">—</div>',
    '    <div class="kpi-lbl">Rejected Today</div>',
    '  </div>',
    '</div>',

    // Filter tabs
    '<div class="card">',
    '  <div class="card-head" style="flex-wrap:wrap;gap:8px">',
    '    <h4><i class="fa fa-inbox"></i> Correction Requests</h4>',
    '    <div style="display:flex;gap:6px;flex-wrap:wrap">',
    '      <button id="hodTab_PENDING"  onclick="_hodSetTab(\'PENDING\')"  class="btn-sm" style="font-weight:700">⏳ Pending</button>',
    '      <button id="hodTab_APPROVED" onclick="_hodSetTab(\'APPROVED\')" class="btn-sm">✓ Approved</button>',
    '      <button id="hodTab_REJECTED" onclick="_hodSetTab(\'REJECTED\')" class="btn-sm">✗ Rejected</button>',
    '      <button id="hodTab_ALL"      onclick="_hodSetTab(\'ALL\')"      class="btn-sm">☰ All</button>',
    '    </div>',
    '  </div>',
    '  <div id="hodApprovalsBody">',
    '    <div style="text-align:center;padding:36px;color:var(--text2)"><i class="fa fa-spinner fa-spin" style="font-size:1.6rem"></i><p style="margin:10px 0 0">Loading requests...</p></div>',
    '  </div>',
    '</div>',
  ].join('\n');

  _hodRefreshKpis();
  _hodLoadRequests(_hodAppFilter);
}

// ── Refresh KPI counts ────────────────────────────────────────
async function _hodRefreshKpis() {
  try {
    var pending = await apiFetch('/api/attendance/override/pending?hod_only=true');
    var pList   = (pending && pending.requests) ? pending.requests : (Array.isArray(pending) ? pending : []);
    var kpiEl   = document.getElementById('hodPendingKpi');
    if (kpiEl) kpiEl.textContent = pList.length;
  } catch(e) { /* non-fatal */ }
  // Approved/rejected today — stub with dashes for now (no dedicated endpoint yet)
  var aEl = document.getElementById('hodApprovedKpi');
  var rEl = document.getElementById('hodRejectedKpi');
  if (aEl) aEl.textContent = '—';
  if (rEl) rEl.textContent = '—';
}

// ── Switch filter tab ─────────────────────────────────────────
function _hodSetTab(status) {
  _hodAppFilter = status;
  // Update tab button styles
  ['PENDING','APPROVED','REJECTED','ALL'].forEach(function(s) {
    var btn = document.getElementById('hodTab_' + s);
    if (!btn) return;
    if (s === status) {
      btn.style.background    = 'var(--primary)';
      btn.style.color         = '#fff';
      btn.style.fontWeight    = '700';
    } else {
      btn.style.background    = '';
      btn.style.color         = '';
      btn.style.fontWeight    = '';
    }
  });
  _hodLoadRequests(status);
}

// ── Load and render the requests table ───────────────────────
async function _hodLoadRequests(statusFilter) {
  var body = document.getElementById('hodApprovalsBody');
  if (!body) return;

  body.innerHTML = '<div style="text-align:center;padding:36px;color:var(--text2)"><i class="fa fa-spinner fa-spin" style="font-size:1.4rem"></i><p style="margin:10px 0 0">Loading...</p></div>';

  // Highlight active tab
  _hodSetTabStyle(statusFilter);

  var requests = [];
  try {
    if (statusFilter === 'PENDING' || statusFilter === 'ALL') {
      var res  = await apiFetch('/api/attendance/override/pending?hod_only=' + (statusFilter === 'PENDING' ? 'true' : 'false'));
      requests = (res && res.requests) ? res.requests : (Array.isArray(res) ? res : []);
    } else {
      // APPROVED / REJECTED — fetch full history and filter client-side
      var hist = await apiFetch('/api/attendance/override/history?limit=500');
      var all  = Array.isArray(hist) ? hist : (hist && hist.records ? hist.records : []);
      // Map history fields to request shape for display
      requests = all.filter(function(r) {
        return (r.approval_status || '').toUpperCase() === statusFilter;
      });
    }
  } catch(e) {
    body.innerHTML = '<div style="text-align:center;padding:36px;color:var(--danger)"><i class="fa fa-circle-exclamation" style="font-size:1.4rem"></i><p style="margin:10px 0 0">' + (e.message||'Failed to load') + '</p><button class="btn-sm" onclick="_hodLoadRequests(\'' + statusFilter + '\')" style="margin-top:8px">Retry</button></div>';
    return;
  }

  if (requests.length === 0) {
    var emptyIcon  = statusFilter === 'PENDING' ? 'fa-circle-check' : 'fa-inbox';
    var emptyColor = statusFilter === 'PENDING' ? '#16a34a' : 'var(--text3)';
    var emptyMsg   = statusFilter === 'PENDING'
      ? '<strong style="font-size:1.05rem">No pending approvals</strong><br><span style="font-size:.875rem">All correction requests are resolved.</span>'
      : '<strong>No ' + statusFilter.toLowerCase() + ' requests</strong>';
    body.innerHTML = '<div style="text-align:center;padding:48px 20px;color:var(--text2)"><i class="fa ' + emptyIcon + '" style="font-size:2.5rem;color:' + emptyColor + ';display:block;margin-bottom:12px"></i>' + emptyMsg + '</div>';
    return;
  }

  var isPending = (statusFilter === 'PENDING' || statusFilter === 'ALL');
  var rows = requests.map(function(r) {
    var fromTo   = '<span style="background:#fee2e2;color:#dc2626;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:700">' + (r.old_status||'—') + '</span>'
                 + '<span style="margin:0 4px;color:var(--text3)">→</span>'
                 + '<span style="background:#dcfce7;color:#16a34a;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:700">' + (r.new_status||'—') + '</span>';

    var statusBadge = '';
    var st = (r.approval_status || 'PENDING').toUpperCase();
    if (st === 'APPROVED') statusBadge = '<span style="background:#dcfce7;color:#16a34a;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">✓ Approved</span>';
    else if (st === 'REJECTED') statusBadge = '<span style="background:#fee2e2;color:#dc2626;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">✗ Rejected</span>';
    else statusBadge = '<span style="background:#fef3c7;color:#92400e;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">⏳ Pending</span>';

    var actionsHtml = '';
    if (isPending && st === 'PENDING') {
      actionsHtml = '<button onclick="_hodApprove(' + r.id + ')" style="padding:5px 12px;border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:700;background:#dcfce7;color:#16a34a"><i class="fa fa-check"></i> Approve</button>'
                  + '<button onclick="_hodReject(' + r.id + ')"  style="padding:5px 12px;border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:700;background:#fee2e2;color:#dc2626;margin-left:5px"><i class="fa fa-xmark"></i> Reject</button>';
    } else {
      actionsHtml = statusBadge + (r.approved_by ? '<br><span style="font-size:.72rem;color:var(--text3)">by ' + r.approved_by + '</span>' : '');
    }

    var reasonTrunc = (r.reason||'—').length > 55 ? r.reason.substring(0,55) + '…' : (r.reason||'—');
    var submitted   = (r.created_at||'').split(' ')[0] || '—';

    return '<tr style="border-bottom:1px solid var(--border)">'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.faculty_id||'—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text1);font-weight:600">' + (r.student_id||'—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.course_code||r.subject_id||'—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.date||'—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.period||'—') + '</td>'
      + '<td style="padding:9px 11px">' + fromTo + '</td>'
      + '<td style="padding:9px 11px;font-size:.82rem;color:var(--text2);max-width:170px" title="' + (r.reason||'') + '">' + reasonTrunc + '</td>'
      + '<td style="padding:9px 11px;font-size:.8rem;color:var(--text3)">' + submitted + '</td>'
      + '<td style="padding:9px 11px;white-space:nowrap">' + actionsHtml + '</td>'
      + '</tr>';
  }).join('');

  body.innerHTML = '<div class="table-scroll"><table class="data-tbl" style="min-width:900px">'
    + '<thead><tr>'
    + '<th>Faculty</th><th>Student</th><th>Subject</th><th>Date</th>'
    + '<th>Period</th><th>From → To</th><th>Reason</th><th>Submitted</th><th>Actions</th>'
    + '</tr></thead>'
    + '<tbody>' + rows + '</tbody>'
    + '</table></div>';
}

// ── Highlight active tab (called from _hodSetTab and _hodLoadRequests) ──
function _hodSetTabStyle(active) {
  ['PENDING','APPROVED','REJECTED','ALL'].forEach(function(s) {
    var btn = document.getElementById('hodTab_' + s);
    if (!btn) return;
    if (s === active) {
      btn.style.background = 'var(--primary)';
      btn.style.color      = '#fff';
      btn.style.fontWeight = '700';
    } else {
      btn.style.background = '';
      btn.style.color      = '';
      btn.style.fontWeight = '';
    }
  });
}

// ── HOD Approve ───────────────────────────────────────────────
async function _hodApprove(requestId) {
  try {
    await apiFetch('/api/attendance/override/' + requestId + '/approve', {
      method: 'POST',
      body:   JSON.stringify({ reason: 'HOD approved' })
    });
    toast('Request #' + requestId + ' approved ✓', 'success');
    _hodRefreshKpis();
    _hodLoadRequests(_hodAppFilter);
    refreshNotificationCount();
  } catch(e) {
    toast('Approve failed: ' + (e.message||'Error'), 'error');
  }
}

// ── HOD Reject — inline modal (no browser prompt) ─────────────
function _hodReject(requestId) {
  document.getElementById('hodRejectPrompt')?.remove();
  var overlay = document.createElement('div');
  overlay.id  = 'hodRejectPrompt';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center';
  overlay.innerHTML = [
    '<div style="background:var(--card-bg,#fff);border-radius:14px;padding:26px 22px;width:min(440px,92vw);box-shadow:0 8px 40px rgba(0,0,0,.2)">',
    '  <h4 style="margin:0 0 14px;font-size:1.05rem;color:var(--text1)">',
    '    <i class="fa fa-ban" style="color:#dc2626;margin-right:6px"></i>Reject Request #' + requestId,
    '  </h4>',
    '  <p style="margin:0 0 10px;font-size:.875rem;color:var(--text2)">Provide a rejection reason (required, min 5 characters):</p>',
    '  <textarea id="hodRejectReason" rows="3" placeholder="e.g. Student was not present during that period..."',
    '    style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;resize:vertical;',
    '           color:var(--text1);font-size:.875rem;font-family:inherit;box-sizing:border-box"></textarea>',
    '  <div id="hodRejectErr" style="color:var(--danger);font-size:.78rem;margin-top:3px;display:none">',
    '    Reason must be at least 5 characters.',
    '  </div>',
    '  <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:14px">',
    '    <button onclick="document.getElementById(\'hodRejectPrompt\').remove()"',
    '      style="padding:8px 16px;border:1.5px solid var(--border);background:var(--bg2,#f1f5f9);border-radius:8px;',
    '             cursor:pointer;font-size:.875rem;font-weight:600;color:var(--text2)">Cancel</button>',
    '    <button onclick="_hodRejectSubmit(' + requestId + ')"',
    '      style="padding:8px 20px;background:#dc2626;color:#fff;border:none;border-radius:8px;',
    '             cursor:pointer;font-size:.875rem;font-weight:700"><i class="fa fa-ban"></i> Reject</button>',
    '  </div>',
    '</div>',
  ].join('');
  document.body.appendChild(overlay);
  setTimeout(function(){ document.getElementById('hodRejectReason')?.focus(); }, 80);
}

async function _hodRejectSubmit(requestId) {
  var reason = (document.getElementById('hodRejectReason')?.value || '').trim();
  var errEl  = document.getElementById('hodRejectErr');
  if (reason.length < 5) { if (errEl) errEl.style.display = 'block'; return; }
  try {
    await apiFetch('/api/attendance/override/' + requestId + '/reject', {
      method: 'POST',
      body:   JSON.stringify({ reason: reason })
    });
    document.getElementById('hodRejectPrompt')?.remove();
    toast('Request #' + requestId + ' rejected', 'warn');
    _hodRefreshKpis();
    _hodLoadRequests(_hodAppFilter);
    refreshNotificationCount();
  } catch(e) {
    toast('Reject failed: ' + (e.message||'Error'), 'error');
  }
}



// ═══════════════════════════════════════════════════════════════
// ADMIN AUDIT LOG PAGE — renderAuditLogPage()
// Full attendance change history with CSV export.
// ═══════════════════════════════════════════════════════════════

var _auditAllRows   = [];   // full dataset cached after first fetch
var _auditFilter    = 'ALL'; // active client-side filter

async function renderAuditLogPage() {
  // Create page container dynamically (same pattern as pg-courses, pg-hod_approvals)
  var pg = document.getElementById('pg-audit_log');
  if (!pg) {
    pg = document.createElement('div');
    pg.id        = 'pg-audit_log';
    pg.className = 'page dn';
    document.getElementById('pageArea')?.appendChild(pg);
  }

  pg.innerHTML = [
    '<div class="page-header">',
    '  <div class="ph-left">',
    '    <h2><i class="fa fa-clock-rotate-left" style="color:var(--primary);margin-right:8px"></i>Attendance Audit Log</h2>',
    '    <p>Complete record of every attendance change — who changed what, when, and why</p>',
    '  </div>',
    '  <div class="ph-right" style="display:flex;gap:8px;flex-wrap:wrap">',
    '    <button class="btn-sm" onclick="_auditExportCSV()" style="background:#16a34a;color:#fff;font-weight:700"><i class="fa fa-download"></i> Download CSV</button>',
    '    <button class="btn-primary" onclick="renderAuditLogPage()"><i class="fa fa-rotate"></i> Refresh</button>',
    '  </div>',
    '</div>',

    // Summary bar
    '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:1.2rem">',
    '  <div class="kpi-card" style="flex:1;min-width:130px">',
    '    <div class="kpi-icon"><i class="fa fa-list-check"></i></div>',
    '    <div class="kpi-val" id="audTotalKpi">—</div>',
    '    <div class="kpi-lbl">Total Changes</div>',
    '  </div>',
    '  <div class="kpi-card" style="--kc:#fff7ed;flex:1;min-width:130px">',
    '    <div class="kpi-icon" style="color:#ea580c"><i class="fa fa-pen-to-square"></i></div>',
    '    <div class="kpi-val" id="audOverrideKpi">—</div>',
    '    <div class="kpi-lbl">Overrides</div>',
    '  </div>',
    '  <div class="kpi-card" style="--kc:#eff6ff;flex:1;min-width:130px">',
    '    <div class="kpi-icon" style="color:#2563eb"><i class="fa fa-hand-paper"></i></div>',
    '    <div class="kpi-val" id="audCorrKpi">—</div>',
    '    <div class="kpi-lbl">Corrections</div>',
    '  </div>',
    '  <div class="kpi-card" style="--kc:#f0fdf4;flex:1;min-width:130px">',
    '    <div class="kpi-icon" style="color:#16a34a"><i class="fa fa-circle-check"></i></div>',
    '    <div class="kpi-val" id="audApprKpi">—</div>',
    '    <div class="kpi-lbl">Approvals</div>',
    '  </div>',
    '  <div class="kpi-card" style="--kc:#fff1f2;flex:1;min-width:130px">',
    '    <div class="kpi-icon" style="color:#dc2626"><i class="fa fa-ban"></i></div>',
    '    <div class="kpi-val" id="audRejKpi">—</div>',
    '    <div class="kpi-lbl">Rejections</div>',
    '  </div>',
    '</div>',

    // Filter tabs + table card
    '<div class="card">',
    '  <div class="card-head" style="flex-wrap:wrap;gap:8px">',
    '    <h4><i class="fa fa-table-list"></i> Change Records</h4>',
    '    <div id="auditFilterBar" style="display:flex;gap:6px;flex-wrap:wrap">',
    '      <button id="audTab_ALL"        onclick="_auditSetFilter(\'ALL\')"        class="btn-sm">All</button>',
    '      <button id="audTab_override"   onclick="_auditSetFilter(\'override\')"   class="btn-sm">🟠 Override</button>',
    '      <button id="audTab_correction" onclick="_auditSetFilter(\'correction\')" class="btn-sm">🔵 Correction</button>',
    '      <button id="audTab_approval"   onclick="_auditSetFilter(\'approval\')"   class="btn-sm">🟢 Approval</button>',
    '      <button id="audTab_rejection"  onclick="_auditSetFilter(\'rejection\')"  class="btn-sm">🔴 Rejection</button>',
    '    </div>',
    '  </div>',
    '  <div id="auditTableWrap">',
    '    <div style="text-align:center;padding:40px;color:var(--text2)">',
    '      <i class="fa fa-spinner fa-spin" style="font-size:1.8rem"></i>',
    '      <p style="margin:12px 0 0">Loading audit records...</p>',
    '    </div>',
    '  </div>',
    '</div>',
  ].join('\n');

  // Fetch data, populate KPIs, render table
  await _auditFetchAndRender();
}

// ── Fetch from API, cache, update KPIs, render table ────────
async function _auditFetchAndRender() {
  try {
    var res       = await apiFetch('/api/attendance/audit-log?limit=500');
    _auditAllRows = (res && res.logs) ? res.logs : (Array.isArray(res) ? res : []);
  } catch(e) {
    var wrap = document.getElementById('auditTableWrap');
    if (wrap) wrap.innerHTML = '<div style="text-align:center;padding:40px;color:var(--danger)">'
      + '<i class="fa fa-circle-exclamation" style="font-size:1.6rem"></i>'
      + '<p style="margin:10px 0 0">' + (e.message||'Failed to load audit log') + '</p>'
      + '<button class="btn-sm" onclick="_auditFetchAndRender()" style="margin-top:10px">Retry</button></div>';
    return;
  }

  // Update summary KPIs
  var total = _auditAllRows.length;
  var counts = { override:0, correction_request:0, approval:0, rejection:0 };
  _auditAllRows.forEach(function(r) {
    var t = (r.action_type||'').toLowerCase();
    if (t === 'override')            counts.override++;
    else if (t === 'correction_request' || t === 'correction') counts.correction_request++;
    else if (t === 'approval')       counts.approval++;
    else if (t === 'rejection')      counts.rejection++;
  });
  var setKpiText = function(id, val) { var el = document.getElementById(id); if (el) el.textContent = val; };
  setKpiText('audTotalKpi',    total);
  setKpiText('audOverrideKpi', counts.override);
  setKpiText('audCorrKpi',     counts.correction_request);
  setKpiText('audApprKpi',     counts.approval);
  setKpiText('audRejKpi',      counts.rejection);

  _auditRenderTable(_auditFilter);
}

// ── Render the visible (filtered) rows ───────────────────────
function _auditRenderTable(filter) {
  var wrap = document.getElementById('auditTableWrap');
  if (!wrap) return;

  // Apply filter
  var rows = _auditAllRows.filter(function(r) {
    if (filter === 'ALL') return true;
    var t = (r.action_type||'').toLowerCase();
    if (filter === 'correction') return t === 'correction_request' || t === 'correction';
    return t === filter.toLowerCase();
  });

  if (rows.length === 0) {
    wrap.innerHTML = '<div style="text-align:center;padding:48px 20px;color:var(--text2)">'
      + '<i class="fa fa-magnifying-glass" style="font-size:2.2rem;display:block;margin-bottom:12px;opacity:.35"></i>'
      + '<strong>No audit records found</strong>'
      + (filter !== 'ALL' ? '<p style="margin:6px 0 0;font-size:.875rem">No <em>' + filter + '</em> actions yet.</p>' : '')
      + '</div>';
    return;
  }

  // Row colour per action_type
  var rowStyle = function(actionType) {
    var t = (actionType||'').toLowerCase();
    if (t === 'override')                               return 'background:rgba(234,88,12,.05)';
    if (t === 'correction_request' || t === 'correction') return 'background:rgba(37,99,235,.05)';
    if (t === 'approval')                               return 'background:rgba(22,163,74,.05)';
    if (t === 'rejection')                              return 'background:rgba(220,38,38,.05)';
    return '';
  };

  var actionBadge = function(actionType) {
    var t = (actionType||'').toLowerCase();
    var cfg = {
      override:            { bg:'#fff7ed', color:'#ea580c', label:'Override'     },
      correction_request:  { bg:'#eff6ff', color:'#2563eb', label:'Correction'   },
      correction:          { bg:'#eff6ff', color:'#2563eb', label:'Correction'   },
      approval:            { bg:'#f0fdf4', color:'#16a34a', label:'Approval'     },
      rejection:           { bg:'#fff1f2', color:'#dc2626', label:'Rejection'    },
    };
    var c = cfg[t] || { bg:'#f3f4f6', color:'#6b7280', label: actionType||'—' };
    return '<span style="background:' + c.bg + ';color:' + c.color + ';padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">' + c.label + '</span>';
  };

  var tbody = rows.map(function(r, i) {
    var reasonTrunc = (r.reason||'—').length > 55 ? r.reason.substring(0,55)+'…' : (r.reason||'—');
    var ts = (r.timestamp||'').replace('T',' ').substring(0,16);
    return '<tr style="border-bottom:1px solid var(--border);' + rowStyle(r.action_type) + '">'
      + '<td style="padding:8px 10px;font-size:.8rem;color:var(--text3);font-weight:600">' + (i+1) + '</td>'
      + '<td style="padding:8px 10px;font-size:.84rem;color:var(--text1);font-weight:600">' + (r.changed_by||'—') + '</td>'
      + '<td style="padding:8px 10px;font-size:.82rem;color:var(--text2)">' + (r.changed_role||'—') + '</td>'
      + '<td style="padding:8px 10px">' + actionBadge(r.action_type) + '</td>'
      + '<td style="padding:8px 10px"><span style="background:#fee2e2;color:#dc2626;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:700">' + (r.old_value||'—') + '</span></td>'
      + '<td style="padding:8px 10px"><span style="background:#dcfce7;color:#16a34a;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:700">' + (r.new_value||'—') + '</span></td>'
      + '<td style="padding:8px 10px;font-size:.82rem;color:var(--text2);max-width:180px" title="' + (r.reason||'') + '">' + reasonTrunc + '</td>'
      + '<td style="padding:8px 10px;font-size:.8rem;color:var(--text3);white-space:nowrap">' + (ts||'—') + '</td>'
      + '</tr>';
  }).join('');

  wrap.innerHTML = '<div class="table-scroll">'
    + '<table class="data-tbl" style="min-width:860px">'
    + '<thead><tr>'
    + '<th style="width:40px">#</th>'
    + '<th>Changed By</th><th>Role</th><th>Action</th>'
    + '<th>Old Value</th><th>New Value</th>'
    + '<th>Reason</th><th>Timestamp</th>'
    + '</tr></thead>'
    + '<tbody>' + tbody + '</tbody>'
    + '</table></div>'
    + '<div style="padding:8px 14px;font-size:.8rem;color:var(--text3);border-top:1px solid var(--border)">'
    + 'Showing <strong>' + rows.length + '</strong> of <strong>' + _auditAllRows.length + '</strong> records'
    + '</div>';
}

// ── Switch filter tab ─────────────────────────────────────────
function _auditSetFilter(filter) {
  _auditFilter = filter;
  var tabs = ['ALL','override','correction','approval','rejection'];
  tabs.forEach(function(t) {
    var btn = document.getElementById('audTab_' + t);
    if (!btn) return;
    if (t === filter) {
      btn.style.background = 'var(--primary)';
      btn.style.color      = '#fff';
      btn.style.fontWeight = '700';
    } else {
      btn.style.background = '';
      btn.style.color      = '';
      btn.style.fontWeight = '';
    }
  });
  _auditRenderTable(filter);
}

// ── CSV Export (visible / filtered rows) ─────────────────────
function _auditExportCSV() {
  var rows = _auditAllRows.filter(function(r) {
    if (_auditFilter === 'ALL') return true;
    var t = (r.action_type||'').toLowerCase();
    if (_auditFilter === 'correction') return t === 'correction_request' || t === 'correction';
    return t === _auditFilter.toLowerCase();
  });

  if (rows.length === 0) { toast('No records to export', 'warn'); return; }

  var headers = ['#','changed_by','changed_role','action_type','old_value','new_value','reason','timestamp'];
  var csvRows = [headers.join(',')];
  rows.forEach(function(r, i) {
    var esc = function(v) { return '"' + String(v||'').replace(/"/g,'""') + '"'; };
    csvRows.push([
      i+1,
      esc(r.changed_by),
      esc(r.changed_role),
      esc(r.action_type),
      esc(r.old_value),
      esc(r.new_value),
      esc(r.reason),
      esc(r.timestamp),
    ].join(','));
  });

  var blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
  var url  = URL.createObjectURL(blob);
  var a    = document.createElement('a');
  a.href   = url;
  a.download = 'attendance_audit_log_' + new Date().toISOString().substring(0,10) + '.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast('Exported ' + rows.length + ' records to CSV', 'success');
}


let _alertStudents = [];
let _alertSentMap  = {};
let _alertFilter   = 'all';

async function renderAlertsPage() {
  const pg = document.getElementById('pg-alerts');
  if (!pg) return;
  pg.innerHTML = `
    <div class="page-header">
      <div class="ph-left"><h2>Smart Alert System</h2><p>Students below 75% attendance threshold</p></div>
      <div class="ph-right" style="gap:8px;display:flex;flex-wrap:wrap;align-items:center;">
        <select class="sel" id="alertDaysFilter" onchange="loadAlertStudents()">
          <option value="30">Last 30 days</option>
          <option value="60">Last 60 days</option>
          <option value="90">Last 90 days</option>
          <option value="180" selected>Last 6 months (Semester)</option>
        </select>
        <button class="btn-secondary" onclick="loadAlertStudents()"><i class="fa fa-rotate"></i> Refresh</button>
        <button class="btn-primary" id="btnAutoSend" onclick="autoSendAllAlerts()"><i class="fa fa-paper-plane"></i> Auto-Send All Alerts</button>
      </div>
    </div>
    <div class="alert-rules-strip">
      <div class="ars-card" style="--ac:#f6c90e"><i class="fa fa-bell"></i><div class="ars-pct">65-75%</div><div>Student + Parent Notified</div></div>
      <div class="ars-card" style="--ac:#f5a623"><i class="fa fa-triangle-exclamation"></i><div class="ars-pct">60-65%</div><div>Incharge + HOD Alerted</div></div>
      <div class="ars-card" style="--ac:#e05454"><i class="fa fa-radiation"></i><div class="ars-pct">&lt;60%</div><div>Critical - Immediate Action</div></div>
      <div class="ars-card" style="--ac:#5fceaa"><i class="fa fa-envelope-open-text"></i><div class="ars-pct">Auto</div><div>Mail if Faculty Inactive</div></div>
    </div>
    <div class="kpi-strip">
      <div class="kpi-card" style="--kc:#fef3cd"><div class="kpi-icon" style="color:#f6c90e"><i class="fa fa-users"></i></div><div class="kpi-val" id="akTotal">-</div><div class="kpi-lbl">Below 75%</div></div>
      <div class="kpi-card" style="--kc:#fde8d8"><div class="kpi-icon" style="color:#f5a623"><i class="fa fa-triangle-exclamation"></i></div><div class="kpi-val" id="akWarn">-</div><div class="kpi-lbl">60-65% Warning</div></div>
      <div class="kpi-card" style="--kc:#fde8e8"><div class="kpi-icon" style="color:#e05454"><i class="fa fa-radiation"></i></div><div class="kpi-val" id="akCrit">-</div><div class="kpi-lbl">&lt;60% Critical</div></div>
      <div class="kpi-card" style="--kc:#e8f6f0"><div class="kpi-icon" style="color:#5fceaa"><i class="fa fa-envelope-circle-check"></i></div><div class="kpi-val" id="akSent">0</div><div class="kpi-lbl">Mails Sent</div></div>
    </div>
    <div class="card">
      <div class="card-head">
        <h4><i class="fa fa-list-check"></i> Low Attendance - Dept and Section</h4>
        <div class="ch-actions">
          <button class="tab-b active" onclick="filterAlerts('all',this)">All</button>
          <button class="tab-b" onclick="filterAlerts('critical',this)"><span style="color:#e05454">&#9679;</span> Critical</button>
          <button class="tab-b" onclick="filterAlerts('warning',this)"><span style="color:#f5a623">&#9679;</span> Warning</button>
          <button class="tab-b" onclick="filterAlerts('low',this)"><span style="color:#f6c90e">&#9679;</span> Low</button>
          <button class="tab-b" onclick="filterAlerts('unsent',this)"><i class="fa fa-clock"></i> Not Alerted</button>
        </div>
      </div>
      <div id="alertGroupedList" style="padding:16px"><i class="fa fa-spinner fa-spin"></i> Loading...</div>
    </div>
    <div class="card" style="margin-top:1.25rem">
      <div class="card-head">
        <h4><i class="fa fa-triangle-exclamation"></i> Pattern Alerts <span style="font-size:.7rem;font-weight:400;color:var(--muted,#888)">(consecutive absences &amp; declining trends)</span></h4>
        <div class="ch-actions">
          <button class="btn-secondary" onclick="runAnomalyScan()" id="btnAnomalyScan"><i class="fa fa-magnifying-glass-chart"></i> Run Scan</button>
        </div>
      </div>
      <div id="anomalyFlagList" style="padding:16px"><i class="fa fa-spinner fa-spin"></i> Loading...</div>
    </div>`;
  await loadAlertStudents();
  await loadAnomalyFlags();
}

// ── Pattern Alerts (NEW — additive, isolated from existing low-attendance alerts) ──
async function loadAnomalyFlags() {
  const el = document.getElementById('anomalyFlagList');
  if (!el) return;
  try {
    const flags = await apiFetch('/api/anomaly/flags');
    if (!flags.length) {
      el.innerHTML = '<div style="padding:10px;color:var(--muted,#888)"><i class="fa fa-circle-check" style="color:#5fceaa"></i> No pattern anomalies detected.</div>';
      return;
    }
    el.innerHTML = flags.map(f => `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border,#eee)">
        <div>
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${f.severity==='critical'?'#e05454':'#f5a623'};margin-right:8px"></span>
          <strong>${f.name || f.entity_id}</strong>
          <div style="font-size:.78rem;color:var(--muted,#888);margin-left:16px">${f.detail || ''}</div>
        </div>
        <button class="btn-secondary" style="padding:4px 10px;font-size:.75rem" onclick="resolveAnomalyFlag(${f.id})">Resolve</button>
      </div>`).join('');
  } catch (e) {
    el.innerHTML = `<div style="padding:10px;color:var(--red,#e05454)">Failed to load pattern alerts: ${e.message}</div>`;
  }
}

async function runAnomalyScan() {
  const btn = document.getElementById('btnAnomalyScan');
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Scanning...'; }
  try {
    const res = await apiFetch('/api/anomaly/scan', { method: 'POST' });
    await loadAnomalyFlags();
    if (window.toast) toast(`Scan complete — ${res.new_flags} new flag(s) found.`);
  } catch (e) {
    if (window.toast) toast('Scan failed: ' + e.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa fa-magnifying-glass-chart"></i> Run Scan'; }
  }
}

async function resolveAnomalyFlag(id) {
  try {
    await apiFetch(`/api/anomaly/flags/${id}/resolve`, { method: 'PUT' });
    await loadAnomalyFlags();
  } catch (e) {
    if (window.toast) toast('Failed to resolve: ' + e.message, 'error');
  }
}

async function loadAlertStudents() {
  // Default to 180 days (one semester) if no selection exists
  var days = parseInt(document.getElementById('alertDaysFilter') ?
               document.getElementById('alertDaysFilter').value : 180) || 180;
  var container = document.getElementById('alertGroupedList');
  if (!container) return;
  container.innerHTML = '<div style="padding:20px;text-align:center"><i class="fa fa-spinner fa-spin"></i> Loading...</div>';
  try {
    _alertStudents = await api.lowAttendance(75, days);
    renderAlertGrouped(_alertFilter);
    updateAlertKPIs();
  } catch(e) {
    // Fallback: derive from attendance summary
    // NOTE: get_attendance_summary now returns `present_count` and `total_days`
    try {
      var summary = await api.attSummary(days);
      _alertStudents = summary.map(function(r) {
        // Support both new field names (present_count/total_days) and old ones (present/total)
        var total   = r.total_days   || r.total   || days || 1;
        var present = r.present_count || r.present || 0;
        var pct = total > 0 ? Math.round(present / total * 100) : 0;
        return { student_id:r.student_id, name:r.name,
          roll_number:r.roll_number||'',
          section:r.section||'', department:r.department||r.dept||'',
          student_email:r.student_email||'', parent_email:r.parent_email||'',
          present_count:present, total_days:total, pct:pct };
      }).filter(function(r){ return r.pct < 75; })
        .sort(function(a,b){ return a.pct - b.pct; });
      renderAlertGrouped(_alertFilter);
      updateAlertKPIs();
    } catch(e2) {
      container.innerHTML = '<div style="padding:20px;color:var(--red)"><i class="fa fa-exclamation-triangle"></i> Failed: ' + e2.message + '</div>';
    }
  }
}

function updateAlertKPIs() {
  setEl('akTotal', _alertStudents.length);
  setEl('akCrit',  _alertStudents.filter(function(s){ return s.pct < 60; }).length);
  setEl('akWarn',  _alertStudents.filter(function(s){ return s.pct >= 60 && s.pct < 65; }).length);
  setEl('akSent',  Object.keys(_alertSentMap).length);
  // Badge painting is now centralized — see refreshNotificationCount().
  // Re-run it so the topbar bell / sidebar pill pick up any change in
  // _alertStudents immediately, instead of only updating low-attendance
  // counts here while leaving Leave/OD counts stale.
  refreshNotificationCount();
}

function filterAlerts(type, btn) {
  _alertFilter = type;
  document.querySelectorAll('.tab-b').forEach(function(b){ b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  renderAlertGrouped(type);
}

function _alertGrpId(dept, sec) {
  return 'grp_' + dept.replace(/[^a-zA-Z0-9]/g,'_') + '_' + sec.replace(/[^a-zA-Z0-9]/g,'_');
}

function renderAlertGrouped(filter) {
  var container = document.getElementById('alertGroupedList');
  if (!container) return;
  var list = _alertStudents;
  if (filter === 'critical') list = list.filter(function(s){ return s.pct < 60; });
  else if (filter === 'warning') list = list.filter(function(s){ return s.pct >= 60 && s.pct < 65; });
  else if (filter === 'low') list = list.filter(function(s){ return s.pct >= 65 && s.pct < 75; });
  else if (filter === 'unsent') list = list.filter(function(s){ return !_alertSentMap[s.student_id]; });

  if (!list.length) {
    container.innerHTML = '<div style="padding:28px;text-align:center;color:var(--mint-d)"><i class="fa fa-check-circle" style="font-size:2rem;display:block;margin-bottom:8px"></i>No students in this category</div>';
    return;
  }
  var groups = {};
  list.forEach(function(s) {
    var dept = s.department || s.dept || 'General';
    var sec  = s.section || '-';
    var key  = dept + '||' + sec;
    if (!groups[key]) groups[key] = { dept:dept, sec:sec, students:[] };
    groups[key].students.push(s);
  });
  var html = '';
  Object.values(groups).sort(function(a,b){ return a.dept.localeCompare(b.dept) || a.sec.localeCompare(b.sec); }).forEach(function(g) {
    var grpId = _alertGrpId(g.dept, g.sec);
    html += '<div style="margin-bottom:20px">';
    html += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;padding:8px 12px;background:var(--surface2);border-radius:8px;border-left:4px solid var(--mint-d)">';
    html += '<i class="fa fa-building" style="color:var(--mint-d)"></i>';
    html += '<strong style="color:var(--text1)">' + g.dept + '</strong>';
    html += '<span style="color:var(--text3)">&rsaquo;</span>';
    html += '<span style="color:var(--text2)">Section ' + g.sec + '</span>';
    html += '<span class="badge b-amber" style="margin-left:auto">' + g.students.length + ' students</span>';
    html += '<button class="btn-sm" style="background:#6366f1;color:#fff;margin-left:8px" onclick="sendBulkGroup(\'' + grpId + '\')">';
    html += '<i class="fa fa-paper-plane"></i> Send Group</button></div>';
    html += '<div class="table-scroll"><table class="data-tbl"><thead><tr>';
    html += '<th><input type="checkbox" onchange="toggleGroupCheck(this,\'' + grpId + '\')" title="Select all"></th>';
    html += '<th>Student</th><th>Roll No</th><th>Attendance</th><th>Status</th><th>Student Email</th><th>Parent Email</th><th>Action</th>';
    html += '</tr></thead><tbody>';
    g.students.forEach(function(s) {
      var pct   = s.pct;
      var col   = pct < 60 ? '#e05454' : pct < 65 ? '#f5a623' : '#f6c90e';
      var cls   = pct < 60 ? 'b-c'     : pct < 65 ? 'b-d'     : 'b-amber';
      var label = pct < 60 ? 'Critical' : pct < 65 ? 'Warning' : 'Low';
      var sent  = _alertSentMap[s.student_id];
      var sJson = JSON.stringify(s).replace(/"/g, '&quot;');
      html += '<tr id="alert-row-' + s.student_id + '">';
      html += '<td><input type="checkbox" class="' + grpId + ' alert-chk" value="' + s.student_id + '"></td>';
      html += '<td><strong>' + (s.name||'-') + '</strong></td>';
      html += '<td>' + (s.roll_number||'-') + '</td>';
      html += '<td><div style="display:flex;align-items:center;gap:8px">';
      html += '<div style="width:72px;height:8px;background:var(--surface2);border-radius:4px;overflow:hidden">';
      html += '<div style="width:' + Math.min(pct,100) + '%;height:100%;background:' + col + ';border-radius:4px"></div></div>';
      html += '<strong style="color:' + col + '">' + pct + '%</strong></div></td>';
      html += '<td><span class="badge ' + cls + '">' + label + '</span></td>';
      html += '<td style="font-size:.8rem">' + (s.student_email || '<span style="color:var(--text3)">-</span>') + '</td>';
      html += '<td style="font-size:.8rem">' + (s.parent_email  || '<span style="color:var(--text3)">-</span>') + '</td>';
      html += '<td>' + (sent
        ? '<span class="badge" style="background:#d1fae5;color:#065f46"><i class="fa fa-check"></i> Sent</span>'
        : '<button class="btn-sm accent" onclick="sendAlertForStudent(' + sJson + ')"><i class="fa fa-envelope"></i> Mail</button>') + '</td>';
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    html += '<div style="display:flex;gap:8px;margin-top:8px;padding:0 4px">';
    html += '<button class="btn-sm" style="background:var(--surface2)" onclick="sendBulkSelected(\'' + grpId + '\')">';
    html += '<i class="fa fa-paper-plane"></i> Send to Selected</button></div></div>';
  });
  container.innerHTML = html;
}

function toggleGroupCheck(masterCb, grpClass) {
  document.querySelectorAll('.' + grpClass + '.alert-chk').forEach(function(cb){ cb.checked = masterCb.checked; });
}

async function sendAlertForStudent(s) {
  var rowBtn = document.querySelector('#alert-row-' + s.student_id + ' .btn-sm.accent');
  if (rowBtn) { rowBtn.disabled=true; rowBtn.innerHTML='<i class="fa fa-spinner fa-spin"></i>'; }
  try {
    var res = await api.sendAlertMail({
      student_id:s.student_id, name:s.name, roll:s.roll_number,
      pct:s.pct, section:s.section||'', dept:s.department||'',
      student_email:s.student_email||'', parent_email:s.parent_email||''
    });
    _alertSentMap[s.student_id] = true;
    updateAlertKPIs();
    var ac = document.querySelector('#alert-row-' + s.student_id + ' td:last-child');
    if (ac) ac.innerHTML = '<span class="badge" style="background:#d1fae5;color:#065f46"><i class="fa fa-check"></i> Sent</span>';
    toast(res.message || 'Alert sent!', 'success');
  } catch(e) {
    if (rowBtn) { rowBtn.disabled=false; rowBtn.innerHTML='<i class="fa fa-envelope"></i> Mail'; }
    toast('Failed: ' + e.message, 'error');
  }
}

async function sendBulkGroup(grpId) {
  var toSend = _alertStudents.filter(function(s) {
    var dept = s.department || s.dept || 'General';
    var sec  = s.section || '-';
    return _alertGrpId(dept,sec) === grpId && !_alertSentMap[s.student_id];
  });
  if (!toSend.length) { toast('All in this group already alerted', 'warn'); return; }
  var count = 0;
  for (var i=0; i<toSend.length; i++) {
    var s = toSend[i];
    try {
      await api.sendAlertMail({ student_id:s.student_id, name:s.name, roll:s.roll_number,
        pct:s.pct, section:s.section||'', dept:s.department||'',
        student_email:s.student_email||'', parent_email:s.parent_email||'' });
      _alertSentMap[s.student_id] = true; count++;
      var ac = document.querySelector('#alert-row-' + s.student_id + ' td:last-child');
      if (ac) ac.innerHTML = '<span class="badge" style="background:#d1fae5;color:#065f46"><i class="fa fa-check"></i> Sent</span>';
    } catch(e) { /* continue */ }
  }
  updateAlertKPIs();
  toast('Alerts sent for ' + count + ' student(s)', 'success');
}

async function sendBulkSelected(grpId) {
  var checked = Array.from(document.querySelectorAll('.' + grpId + '.alert-chk:checked'));
  if (!checked.length) { toast('Select at least one student', 'warn'); return; }
  var ids = checked.map(function(c){ return c.value; });
  var students = _alertStudents.filter(function(s){ return ids.indexOf(s.student_id) >= 0; });
  var count = 0;
  for (var i=0; i<students.length; i++) {
    var s = students[i];
    try {
      await api.sendAlertMail({ student_id:s.student_id, name:s.name, roll:s.roll_number,
        pct:s.pct, section:s.section||'', dept:s.department||'',
        student_email:s.student_email||'', parent_email:s.parent_email||'' });
      _alertSentMap[s.student_id] = true; count++;
      var ac = document.querySelector('#alert-row-' + s.student_id + ' td:last-child');
      if (ac) ac.innerHTML = '<span class="badge" style="background:#d1fae5;color:#065f46"><i class="fa fa-check"></i> Sent</span>';
    } catch(e) { /* continue */ }
  }
  updateAlertKPIs();
  toast('Alerts sent for ' + count + ' student(s)', 'success');
}

async function autoSendAllAlerts() {
  var btn = document.getElementById('btnAutoSend');
  if (btn) { btn.disabled=true; btn.innerHTML='<i class="fa fa-spinner fa-spin"></i> Sending...'; }
  try {
    var res = await api.autoSendAlerts();
    (res.results||[]).forEach(function(r){ _alertSentMap[r.student_id]=true; });
    updateAlertKPIs();
    renderAlertGrouped(_alertFilter);
    toast(res.message || 'Auto-alerts sent for ' + (res.count||0) + ' students', 'success');
  } catch(e) { toast('Auto-send failed: ' + e.message, 'error'); }
  finally { if (btn) { btn.disabled=false; btn.innerHTML='<i class="fa fa-paper-plane"></i> Auto-Send All Alerts'; } }
}

function renderAlertFeed() { /* legacy shim */ }
function setAlertFilter(type,btn){ filterAlerts(type, btn); }
async function runAlerts(){ await loadAlertStudents(); toast('Alert engine refreshed','warn'); }
async function bulkSendAlerts(){ await autoSendAllAlerts(); }


// ── SETTINGS ──────────────────────────────────────────────────
async function renderSettingsPage() {
  const pg=document.getElementById('pg-settings');
  if(!pg) return;
  pg.innerHTML='<div class="page-header"><div class="ph-left"><h2>System Settings</h2><p>Recognition thresholds</p></div></div><div class="card" id="settingsCard"><div class="card-head"><h4><i class="fa fa-gear"></i> Thresholds</h4></div><div style="padding:20px"><i class="fa fa-spinner fa-spin"></i> Loading...</div></div>';
  try {
    const s=await api.settings();
    document.getElementById('settingsCard').innerHTML='<div class="card-head"><h4><i class="fa fa-gear"></i> Recognition Thresholds</h4><button class="btn-primary" onclick="saveSettings()"><i class="fa fa-save"></i> Save</button></div><div style="padding:20px;display:grid;grid-template-columns:1fr 1fr;gap:14px">'+Object.entries(s).map(([k,v])=>'<div class="fg"><label>'+k.replace(/_/g,' ')+'</label><input id="stg_'+k+'" value="'+v+'" type="'+(typeof v==='boolean'?'checkbox':'text')+'" '+(typeof v==='boolean'&&v?'checked':'')+'/></div>').join('')+'</div>';
  } catch(e){ toast('Settings failed: '+e.message,'error'); }
}

async function saveSettings() {
  const keys=['LBPH_THRESHOLD','DLIB_DISTANCE','MIN_CONFIDENCE_PCT','CONFIRM_FRAMES_REQUIRED','LIVENESS_THRESHOLD','LIVENESS_ON','CAMERA_INDEX'];
  const data={};
  keys.forEach(k=>{const el=document.getElementById('stg_'+k);if(el)data[k]=el.type==='checkbox'?el.checked:el.value;});
  try{ await api.saveSettings(data); toast('Settings saved!','success'); } catch(e){ toast('Save failed: '+e.message,'error'); }
}

// ═══════════════════════════════════════════════════════════
// AI MODEL TRAINING MANAGEMENT  —  ADMIN ONLY
// ═══════════════════════════════════════════════════════════

// ── Training state (module-level) ─────────────────────────
const TM = {
  activeTab:       'hod',         // hod | faculty | student
  statusData:      null,          // last /api/train/status/all response
  progressTimer:   null,          // selective training poll interval
  fullTrainTimer:  null,          // full retraining poll interval
  searchQuery:     { hod:'', faculty:'', student:'' },
  filterStatus:    { hod:'all', faculty:'all', student:'all' },
};

const TRAIN_STAGES = [
  { key:'reading_images',      label:'Reading Images',       sub:'Reading images from dataset...' },
  { key:'processing_dataset',  label:'Processing Dataset',   sub:'Preprocessing images...' },
  { key:'augmentation',        label:'Augmentation',         sub:'Augmenting training data...' },
  { key:'training_model',      label:'Training Model',       sub:'Training LBPH model...' },
  { key:'saving_model',        label:'Saving Model',         sub:'Saving model to disk...' },
  { key:'updating_trained_ids',label:'Updating Trained IDs', sub:'Updating trained_ids.json...' },
  { key:'completed',           label:'Completed',            sub:'Training completed successfully' },
];

// ── Route guard: redirect non-admins away from training ───
function guardTrainingRoute() {
  if (APP.role !== 'admin') {
    console.warn('[TrainingGuard] Access denied for role:', APP.role);
    showPage('dashboard');
    toast('Access denied: AI Training is restricted to Admin only.', 'error');
    return false;
  }
  return true;
}

// ── Entry point called by showPage('train') ───────────────
function renderTrainPage() {
  if (!guardTrainingRoute()) return;
  const pg = document.getElementById('pg-train');
  if (!pg) return;

  pg.innerHTML = `
  <style>
    /* ── Training Dashboard Scoped Styles ─────────────────── */
    .tm-header { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; margin-bottom:20px; }
    .tm-header-left h2 { font-size:1.35rem; font-weight:700; color:var(--text1); margin:0 0 2px; }
    .tm-header-left p  { font-size:.82rem; color:var(--text3); margin:0; }
    .tm-header-right   { display:flex; gap:10px; flex-wrap:wrap; }
    .tm-stat-strip     { display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-bottom:22px; }
    @media(max-width:900px){ .tm-stat-strip{ grid-template-columns:repeat(3,1fr); } }
    @media(max-width:600px){ .tm-stat-strip{ grid-template-columns:repeat(2,1fr); } }
    .tm-stat           { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }
    .tm-stat-label     { font-size:.72rem; color:var(--text3); text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px; }
    .tm-stat-val       { font-size:1.5rem; font-weight:700; color:var(--text1); line-height:1; }
    .tm-stat-sub       { font-size:.72rem; color:var(--text3); margin-top:4px; }
    .tm-tabs           { display:flex; gap:2px; background:var(--bg); border:1px solid var(--border); border-radius:10px; padding:4px; margin-bottom:20px; }
    .tm-tab            { flex:1; text-align:center; padding:8px 12px; border-radius:7px; font-size:.82rem; font-weight:600; cursor:pointer; border:none; background:transparent; color:var(--text3); transition:all .18s; }
    .tm-tab.active     { background:var(--card); color:var(--primary); box-shadow:0 1px 4px rgba(0,0,0,.08); }
    .tm-body           { display:grid; grid-template-columns:1fr 340px; gap:18px; }
    @media(max-width:1100px){ .tm-body{ grid-template-columns:1fr; } }
    .tm-list-card      { background:var(--card); border:1px solid var(--border); border-radius:14px; overflow:hidden; }
    .tm-list-head      { padding:14px 18px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
    .tm-list-title     { font-size:.95rem; font-weight:700; color:var(--text1); display:flex; align-items:center; gap:8px; }
    .tm-pill           { font-size:.68rem; font-weight:700; padding:3px 9px; border-radius:20px; }
    .tm-pill-green     { background:#dcfce7; color:#15803d; }
    .tm-pill-amber     { background:#fef9c3; color:#854d0e; }
    .tm-search-row     { display:flex; gap:8px; align-items:center; padding:10px 14px; border-bottom:1px solid var(--border); background:var(--bg); }
    .tm-search-input   { flex:1; border:1px solid var(--border); border-radius:8px; padding:7px 12px; font-size:.82rem; background:var(--card); color:var(--text1); outline:none; }
    .tm-filter-sel     { border:1px solid var(--border); border-radius:8px; padding:7px 10px; font-size:.8rem; background:var(--card); color:var(--text2); cursor:pointer; }
    .tm-person-row     { display:flex; align-items:center; gap:10px; padding:12px 16px; border-bottom:1px solid var(--border); transition:background .12s; }
    .tm-person-row:last-child { border-bottom:none; }
    .tm-person-row:hover { background:var(--bg); }
    .tm-avatar         { width:36px; height:36px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:.82rem; font-weight:700; flex-shrink:0; }
    .tm-av-hod         { background:#ede9fe; color:#7c3aed; }
    .tm-av-faculty       { background:#dbeafe; color:#1d4ed8; }
    .tm-av-student     { background:#dcfce7; color:#15803d; }
    .tm-person-info    { flex:1; min-width:0; }
    .tm-person-id      { font-size:.85rem; font-weight:600; color:var(--text1); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .tm-person-meta    { font-size:.72rem; color:var(--text3); margin-top:1px; }
    .tm-status-badge   { font-size:.7rem; font-weight:600; padding:3px 9px; border-radius:20px; white-space:nowrap; }
    .tm-badge-trained  { background:#dcfce7; color:#15803d; }
    .tm-badge-missing  { background:#fee2e2; color:#b91c1c; }
    .tm-btn-train      { font-size:.75rem; font-weight:600; padding:5px 12px; border-radius:7px; border:1.5px solid var(--primary); background:transparent; color:var(--primary); cursor:pointer; transition:all .15s; white-space:nowrap; }
    .tm-btn-train:hover { background:var(--primary); color:#fff; }
    .tm-btn-trained    { font-size:.75rem; font-weight:600; padding:5px 12px; border-radius:7px; border:1.5px solid var(--border); background:var(--bg); color:var(--text3); cursor:default; }
    .tm-btn-missing    { font-size:.75rem; font-weight:600; padding:5px 12px; border-radius:7px; border:1.5px solid #fca5a5; background:#fef2f2; color:#b91c1c; cursor:default; }
    .tm-empty          { text-align:center; padding:32px 16px; color:var(--text3); font-size:.83rem; }
    .tm-pagination     { display:flex; align-items:center; justify-content:space-between; padding:10px 16px; border-top:1px solid var(--border); font-size:.75rem; color:var(--text3); }
    .tm-page-btns      { display:flex; gap:4px; }
    .tm-page-btn       { border:1px solid var(--border); background:var(--card); color:var(--text2); padding:4px 10px; border-radius:6px; cursor:pointer; font-size:.75rem; }
    .tm-page-btn.active { background:var(--primary); color:#fff; border-color:var(--primary); }
    .tm-progress-card  { background:var(--card); border:1px solid var(--border); border-radius:14px; overflow:hidden; position:sticky; top:16px; }
    .tm-prog-head      { padding:14px 18px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; }
    .tm-prog-title     { font-size:.9rem; font-weight:700; color:var(--text1); }
    .tm-prog-id        { font-size:.72rem; color:var(--primary); font-weight:600; background:var(--bg); padding:2px 8px; border-radius:6px; }
    .tm-prog-list      { padding:14px; }
    .tm-prog-item      { display:flex; align-items:flex-start; gap:10px; padding:6px 0; }
    .tm-prog-icon      { width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0; margin-top:1px; }
    .tm-prog-icon.done { background:#dcfce7; color:#15803d; }
    .tm-prog-icon.active { background:#dbeafe; color:#1d4ed8; }
    .tm-prog-icon.idle { background:var(--bg); color:var(--text3); border:1.5px solid var(--border); }
    .tm-prog-label     { font-size:.82rem; font-weight:600; color:var(--text1); }
    .tm-prog-sub       { font-size:.72rem; color:var(--text3); margin-top:1px; }
    .tm-prog-bar-wrap  { margin:12px 14px; }
    .tm-prog-bar-bg    { background:var(--border); border-radius:8px; height:8px; overflow:hidden; }
    .tm-prog-bar-fill  { height:100%; border-radius:8px; background:linear-gradient(90deg,var(--primary),#7c3aed); transition:width .4s; }
    .tm-dataset-strip  { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:18px; }
    @media(max-width:700px){ .tm-dataset-strip{ grid-template-columns:1fr; } }
    .tm-ds-card        { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }
    .tm-ds-icon        { font-size:1.1rem; margin-bottom:6px; }
    .tm-ds-label       { font-size:.72rem; color:var(--text3); text-transform:uppercase; letter-spacing:.06em; font-weight:700; margin-bottom:4px; }
    .tm-ds-folders     { font-size:1rem; font-weight:700; color:var(--text1); }
    .tm-ds-images      { font-size:.78rem; color:var(--text3); }
    .tm-note           { font-size:.76rem; color:var(--text3); text-align:center; margin-top:16px; padding-top:14px; border-top:1px dashed var(--border); }
    .tm-full-btn       { background:linear-gradient(135deg,#dc2626,#b91c1c); color:#fff; border:none; border-radius:10px; padding:10px 20px; font-size:.85rem; font-weight:600; cursor:pointer; display:flex; align-items:center; gap:8px; transition:opacity .15s; }
    .tm-full-btn:hover { opacity:.88; }
    .tm-refresh-btn    { background:var(--primary); color:#fff; border:none; border-radius:10px; padding:10px 18px; font-size:.82rem; font-weight:600; cursor:pointer; display:flex; align-items:center; gap:8px; transition:opacity .15s; }
    .tm-refresh-btn:hover { opacity:.85; }
  </style>

  <div class="tm-header">
    <div class="tm-header-left">
      <h2><i class="fa fa-brain" style="color:var(--primary)"></i> AI Model Training Management</h2>
      <p>Manage and train AI models for HOD, Faculty and Students</p>
    </div>
    <div class="tm-header-right">
      <button class="tm-full-btn" onclick="tmConfirmFullRetrain()">
        <i class="fa fa-rotate"></i> Full Model Retraining
      </button>
      <button class="tm-refresh-btn" onclick="tmLoadStatus()">
        <i class="fa fa-arrows-rotate"></i> Refresh Status
      </button>
    </div>
  </div>

  <div id="tmStatStrip" class="tm-stat-strip">
    ${tmStatLoading()}
  </div>

  <div class="tm-tabs">
    <button class="tm-tab active" id="tmTab-hod"     onclick="tmSwitchTab('hod')">
      <i class="fa fa-user-tie"></i> HOD Training
    </button>
    <button class="tm-tab"        id="tmTab-faculty"   onclick="tmSwitchTab('faculty')">
      <i class="fa fa-chalkboard-teacher"></i> Faculty Training
    </button>
    <button class="tm-tab"        id="tmTab-student" onclick="tmSwitchTab('student')">
      <i class="fa fa-user-graduate"></i> Student Training
    </button>
    <button class="tm-tab"        id="tmTab-history" onclick="tmSwitchTab('history')">
      <i class="fa fa-clock-rotate-left"></i> Training History
    </button>
  </div>

  <div class="tm-body">
    <div id="tmPanelMain">
      <div class="tm-list-card">
        <div class="tm-empty"><i class="fa fa-spinner fa-spin" style="font-size:1.4rem;margin-bottom:8px"></i><br>Loading training status...</div>
      </div>
    </div>
    <div id="tmPanelProgress">
      ${tmProgressIdle()}
    </div>
  </div>

  <div id="tmDatasetSummary" style="margin-top:18px"></div>

  <div class="tm-note">
    Note: Selective training will update the existing model without removing previously trained data.
  </div>
  `;

  TM.activeTab = 'hod';
  tmLoadStatus();
}

// ── Stat strip helpers ────────────────────────────────────
function tmStatLoading() {
  return Array(5).fill(0).map(()=>`
    <div class="tm-stat">
      <div class="tm-stat-label" style="height:10px;background:var(--border);border-radius:4px;width:60%"></div>
      <div class="tm-stat-val"   style="height:22px;background:var(--border);border-radius:4px;margin-top:6px;width:40%"></div>
    </div>`).join('');
}

function tmBuildStatStrip(data) {
  if (!data) return '';
  let th=0,tp=0, sh=0,sp=0, st=0,stP=0, totalImg=0;
  const roles = { hod:'hod', faculty:'faculty', student:'student' };
  for (const [, rkey] of Object.entries(roles)) {
    const d = data[rkey];
    if (!d) continue;
    const trained = d.trained?.length||0;
    const notT    = d.not_trained?.length||0;
    const total   = trained+notT;
    const allImgs = [...(d.trained||[]),...(d.not_trained||[])].reduce((s,x)=>s+(x.image_count||0),0);
    totalImg += allImgs;
    if (rkey==='hod')   { th=trained; tp=notT; }
    if (rkey==='faculty') { sh=trained; sp=notT; }
    if (rkey==='student'){ st=trained; stP=notT; }
  }
  const modelStatus = 'Ready';
  return `
    <div class="tm-stat">
      <div class="tm-stat-label"><i class="fa fa-user-tie"></i> Total HODs</div>
      <div class="tm-stat-val">${th+tp}</div>
      <div class="tm-stat-sub">Trained: <b style="color:#15803d">${th}</b> &nbsp;|&nbsp; Pending: <b style="color:#b45309">${tp}</b></div>
    </div>
    <div class="tm-stat">
      <div class="tm-stat-label"><i class="fa fa-chalkboard-teacher"></i> Total Faculty</div>
      <div class="tm-stat-val">${sh+sp}</div>
      <div class="tm-stat-sub">Trained: <b style="color:#15803d">${sh}</b> &nbsp;|&nbsp; Pending: <b style="color:#b45309">${sp}</b></div>
    </div>
    <div class="tm-stat">
      <div class="tm-stat-label"><i class="fa fa-user-graduate"></i> Total Students</div>
      <div class="tm-stat-val">${st+stP}</div>
      <div class="tm-stat-sub">Trained: <b style="color:#15803d">${st}</b> &nbsp;|&nbsp; Pending: <b style="color:#b45309">${stP}</b></div>
    </div>
    <div class="tm-stat">
      <div class="tm-stat-label"><i class="fa fa-images"></i> Total Images</div>
      <div class="tm-stat-val">${totalImg.toLocaleString()}</div>
      <div class="tm-stat-sub">Across all datasets</div>
    </div>
    <div class="tm-stat">
      <div class="tm-stat-label"><i class="fa fa-microchip"></i> Model Status</div>
      <div class="tm-stat-val" style="font-size:1rem;color:#15803d">${modelStatus}</div>
      <div class="tm-stat-sub">LBPH Model Active</div>
    </div>`;
}

// ── Load status from API ──────────────────────────────────
async function tmLoadStatus() {
  if (APP.role !== 'admin') return;
  const mainPanel = document.getElementById('tmPanelMain');
  if (!mainPanel) return;
  try {
    const data = await api.trainStatusAll();
    TM.statusData = data;
    const strip = document.getElementById('tmStatStrip');
    if (strip) strip.innerHTML = tmBuildStatStrip(data);
    tmRenderTab(TM.activeTab);
    tmRenderDatasetSummary(data);
  } catch(e) {
    if (mainPanel) mainPanel.innerHTML = `
      <div class="tm-list-card">
        <div class="tm-empty">
          <i class="fa fa-triangle-exclamation" style="font-size:1.3rem;color:#dc2626;margin-bottom:8px"></i><br>
          Failed to load training status: ${e.message||'Unknown error'}
          <br><button class="tm-refresh-btn" style="margin:12px auto 0" onclick="tmLoadStatus()">
            <i class="fa fa-rotate-right"></i> Retry
          </button>
        </div>
      </div>`;
  }
}

// ── Switch tab ────────────────────────────────────────────
function tmSwitchTab(tab) {
  TM.activeTab = tab;
  document.querySelectorAll('.tm-tab').forEach(el => el.classList.remove('active'));
  const t = document.getElementById('tmTab-'+tab);
  if (t) t.classList.add('active');
  if (tab === 'history') {
    tmRenderHistory();
  } else {
    tmRenderTab(tab);
  }
}

// ── Build person list panel for a role ────────────────────
function tmRenderTab(role) {
  const mainPanel = document.getElementById('tmPanelMain');
  if (!mainPanel) return;
  if (!TM.statusData) {
    mainPanel.innerHTML = `<div class="tm-list-card"><div class="tm-empty">Loading...</div></div>`;
    tmLoadStatus();
    return;
  }
  const d = TM.statusData[role];
  if (!d) { mainPanel.innerHTML = `<div class="tm-list-card"><div class="tm-empty">No data</div></div>`; return; }

  const trained    = d.trained    || [];
  const notTrained = d.not_trained || [];
  const all        = [...trained, ...notTrained];

  const q = (TM.searchQuery[role]||'').toLowerCase();
  const f = TM.filterStatus[role] || 'all';
  let filtered = all;
  if (q) filtered = filtered.filter(x => x.id.toLowerCase().includes(q));
  if (f === 'trained')     filtered = filtered.filter(x => x.trained);
  if (f === 'not_trained') filtered = filtered.filter(x => !x.trained && x.image_count > 0);
  if (f === 'missing')     filtered = filtered.filter(x => !x.trained && x.image_count === 0);

  const roleLabel = { hod:'HOD', faculty:'Faculty', student:'Student' }[role] || role;
  const avClass   = `tm-av-${role}`;
  const initials  = (id) => id.substring(0, 2).toUpperCase();

  const PAGE_SIZE = 8;
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  TM[`page_${role}`] = TM[`page_${role}`] || 1;
  let page = TM[`page_${role}`];
  if (page > totalPages) page = 1;
  const slice = filtered.slice((page-1)*PAGE_SIZE, page*PAGE_SIZE);

  const rows = slice.map(p => {
    const hasImages = p.image_count > 0;
    let badge, btn;
    if (p.trained) {
      badge = `<span class="tm-status-badge tm-badge-trained"><i class="fa fa-circle-check"></i> Trained</span>`;
      btn   = `<button class="tm-btn-trained" disabled>Already Trained</button>`;
    } else if (!hasImages) {
      badge = `<span class="tm-status-badge tm-badge-missing"><i class="fa fa-circle-xmark"></i> No Images</span>`;
      btn   = `<button class="tm-btn-missing" disabled>Dataset Missing</button>`;
    } else {
      badge = `<span class="tm-status-badge" style="background:#fef9c3;color:#854d0e"><i class="fa fa-clock"></i> Pending</span>`;
      btn   = `<button class="tm-btn-train" onclick="tmStartSelective('${role}','${p.id}')"><i class="fa fa-play"></i> Train Model</button>`;
    }
    return `
      <div class="tm-person-row">
        <div class="tm-avatar ${avClass}">${initials(p.id)}</div>
        <div class="tm-person-info">
          <div class="tm-person-id">${p.id}</div>
          <div class="tm-person-meta">Images: ${p.image_count}</div>
        </div>
        ${badge}
        ${btn}
      </div>`;
  }).join('');

  const paginationHtml = totalPages > 1 ? `
    <div class="tm-pagination">
      <span>Showing ${(page-1)*PAGE_SIZE+1}–${Math.min(page*PAGE_SIZE, filtered.length)} of ${filtered.length} ${roleLabel}s</span>
      <div class="tm-page-btns">
        <button class="tm-page-btn" onclick="tmChangePage('${role}',${page-1})" ${page===1?'disabled':''}>‹</button>
        ${Array.from({length:Math.min(totalPages,5)},(_, i)=>i+Math.max(1,page-2)).filter(p2=>p2<=totalPages).map(p2=>`
          <button class="tm-page-btn ${p2===page?'active':''}" onclick="tmChangePage('${role}',${p2})">${p2}</button>`).join('')}
        <button class="tm-page-btn" onclick="tmChangePage('${role}',${page+1})" ${page===totalPages?'disabled':''}>›</button>
      </div>
    </div>` : '';

  mainPanel.innerHTML = `
    <div class="tm-list-card">
      <div class="tm-list-head">
        <div class="tm-list-title">
          <i class="fa fa-${role==='hod'?'user-tie':role==='faculty'?'chalkboard-teacher':'user-graduate'}"></i>
          ${roleLabel} — Training Status
          <span class="tm-pill tm-pill-green">${trained.length} Trained</span>
          <span class="tm-pill tm-pill-amber">${notTrained.length} Pending</span>
        </div>
      </div>
      <div class="tm-search-row">
        <input class="tm-search-input" placeholder="Search ${roleLabel} ID..."
          value="${TM.searchQuery[role]||''}"
          oninput="tmSearch('${role}',this.value)">
        <select class="tm-filter-sel" onchange="tmFilter('${role}',this.value)">
          <option value="all"        ${f==='all'?'selected':''}>All Status</option>
          <option value="trained"    ${f==='trained'?'selected':''}>Trained</option>
          <option value="not_trained"${f==='not_trained'?'selected':''}>Pending</option>
          <option value="missing"    ${f==='missing'?'selected':''}>Dataset Missing</option>
        </select>
      </div>
      ${rows || `<div class="tm-empty">No ${roleLabel}s match your filter.</div>`}
      ${paginationHtml}
    </div>`;
}

function tmChangePage(role, page) {
  TM[`page_${role}`] = page;
  tmRenderTab(role);
}
function tmSearch(role, q) {
  TM.searchQuery[role] = q;
  TM[`page_${role}`] = 1;
  tmRenderTab(role);
}
function tmFilter(role, f) {
  TM.filterStatus[role] = f;
  TM[`page_${role}`] = 1;
  tmRenderTab(role);
}

// ── Dataset summary section ───────────────────────────────
function tmRenderDatasetSummary(data) {
  const el = document.getElementById('tmDatasetSummary');
  if (!el || !data) return;
  const rows = [
    { role:'hod',     label:'HOD Dataset',     icon:'fa-user-tie',          color:'#7c3aed', bg:'#ede9fe' },
    { role:'faculty',   label:'Faculty Dataset',   icon:'fa-chalkboard-teacher', color:'#1d4ed8', bg:'#dbeafe' },
    { role:'student', label:'Student Dataset', icon:'fa-user-graduate',      color:'#15803d', bg:'#dcfce7' },
  ].map(r => {
    const d = data[r.role];
    if (!d) return '';
    const all    = [...(d.trained||[]),...(d.not_trained||[])];
    const folders = all.length;
    const images  = all.reduce((s,x)=>s+(x.image_count||0),0);
    return `
      <div class="tm-ds-card">
        <div class="tm-ds-icon" style="color:${r.color}"><i class="fa ${r.icon}"></i></div>
        <div class="tm-ds-label" style="color:${r.color}">${r.label}</div>
        <div class="tm-ds-folders">${folders} Folders <span style="font-weight:400;font-size:.75rem;color:var(--text3)">Total Subjects</span></div>
        <div class="tm-ds-images">${images.toLocaleString()} Images — Total Images</div>
      </div>`;
  }).join('');
  el.innerHTML = `
    <div style="font-size:.82rem;font-weight:700;color:var(--text2);margin-bottom:10px;text-transform:uppercase;letter-spacing:.06em">Dataset Summary</div>
    <div class="tm-dataset-strip">${rows}</div>`;
}

// ── Idle progress panel ───────────────────────────────────
function tmProgressIdle() {
  return `
    <div class="tm-progress-card">
      <div class="tm-prog-head">
        <div class="tm-prog-title"><i class="fa fa-list-check"></i> Training Progress</div>
        <div class="tm-prog-id" id="tmProgId" style="display:none"></div>
      </div>
      <div class="tm-prog-list" id="tmProgList">
        ${TRAIN_STAGES.map(s => `
          <div class="tm-prog-item" id="tmS-${s.key}">
            <div class="tm-prog-icon idle" id="tmSi-${s.key}">
              <i class="fa fa-circle" style="font-size:.45rem"></i>
            </div>
            <div>
              <div class="tm-prog-label" style="color:var(--text3)">${s.label}</div>
              <div class="tm-prog-sub">${s.sub}</div>
            </div>
          </div>`).join('')}
      </div>
      <div class="tm-prog-bar-wrap">
        <div class="tm-prog-bar-bg"><div class="tm-prog-bar-fill" id="tmProgBar" style="width:0%"></div></div>
        <div style="text-align:right;font-size:.72rem;color:var(--text3);margin-top:4px" id="tmProgPct">0%</div>
      </div>
      <div style="padding:0 14px 14px;font-size:.72rem;color:var(--text3)" id="tmProgLog">
        Select a person and click "Train Model" to begin.
      </div>
    </div>`;
}

// ── Update progress panel ─────────────────────────────────
function tmUpdateProgress(prog) {
  const idEl = document.getElementById('tmProgId');
  if (idEl) {
    idEl.textContent = prog.person_id ? `Training ${prog.person_id}` : '';
    idEl.style.display = prog.person_id ? '' : 'none';
  }

  const done  = new Set(prog.stages_done || []);
  const stage = prog.stage || '';
  const stageIdx = TRAIN_STAGES.findIndex(s => s.key === stage);
  const pct = !prog.running && prog.done ? 100
            : stageIdx >= 0 ? Math.round((stageIdx / TRAIN_STAGES.length) * 100) : 0;

  TRAIN_STAGES.forEach((s, i) => {
    const icon = document.getElementById('tmSi-'+s.key);
    const label = document.querySelector(`#tmS-${s.key} .tm-prog-label`);
    if (!icon) return;
    if (done.has(s.key)) {
      icon.className = 'tm-prog-icon done';
      icon.innerHTML = '<i class="fa fa-check" style="font-size:.6rem"></i>';
      if (label) label.style.color = '';
    } else if (s.key === stage && prog.running) {
      icon.className = 'tm-prog-icon active';
      icon.innerHTML = '<i class="fa fa-spinner fa-spin" style="font-size:.6rem"></i>';
      if (label) label.style.color = 'var(--primary)';
    } else {
      icon.className = 'tm-prog-icon idle';
      icon.innerHTML = '<i class="fa fa-circle" style="font-size:.45rem"></i>';
      if (label) label.style.color = 'var(--text3)';
    }
  });

  const bar = document.getElementById('tmProgBar');
  const pctEl = document.getElementById('tmProgPct');
  if (bar) bar.style.width = pct + '%';
  if (pctEl) pctEl.textContent = pct + '%';

  const logEl = document.getElementById('tmProgLog');
  if (logEl && prog.log) {
    logEl.innerHTML = prog.log.slice(-6).map(l=>
      `<div style="font-size:.7rem;color:var(--text3);padding:1px 0">${l}</div>`
    ).join('');
  }

  if (prog.error) {
    const logEl2 = document.getElementById('tmProgLog');
    if (logEl2) logEl2.innerHTML += `<div style="color:#dc2626;margin-top:4px"><i class="fa fa-triangle-exclamation"></i> ${prog.error}</div>`;
  }
}

// ── Start selective training ──────────────────────────────
async function tmStartSelective(role, personId) {
  if (APP.role !== 'admin') {
    toast('Access denied: Admin only.', 'error');
    return;
  }
  clearInterval(TM.progressTimer);

  // Reset progress display
  const prog = document.getElementById('tmPanelProgress');
  if (prog) prog.innerHTML = tmProgressIdle();
  const logEl = document.getElementById('tmProgLog');
  if (logEl) logEl.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Starting training...';

  try {
    const res = await api.trainSelective(role, personId);
    if (res.status === 'already_running') {
      toast('Training already in progress — please wait.', 'warn');
      return;
    }
    toast(`Training started for ${personId}`, 'info');

    // Show person ID in progress header
    const idEl = document.getElementById('tmProgId');
    if (idEl) { idEl.textContent = `Training ${personId}`; idEl.style.display=''; }

    TM.progressTimer = setInterval(async () => {
      try {
        const p = await api.trainProgress();
        tmUpdateProgress(p);
        if (!p.running) {
          clearInterval(TM.progressTimer);
          if (p.error) {
            toast('Training error: ' + p.error, 'error');
          } else if (p.done) {
            toast(`✓ ${personId} trained successfully!`, 'success');
            setTimeout(() => tmLoadStatus(), 800); // refresh list
          }
        }
      } catch(e) { /* poll silently */ }
    }, 1500);
  } catch(e) {
    toast('Failed to start training: ' + (e.message||'Unknown error'), 'error');
  }
}

// ── Confirm + start full retraining ──────────────────────
function tmConfirmFullRetrain() {
  if (APP.role !== 'admin') {
    toast('Access denied: Admin only.', 'error');
    return;
  }
  // Use inline modal instead of confirm() for mobile compatibility
  const el = document.getElementById('pg-train');
  if (!el) return;

  // Check if modal already exists
  let modal = document.getElementById('tmFullModal');
  if (modal) { modal.style.display='flex'; return; }

  modal = document.createElement('div');
  modal.id = 'tmFullModal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;z-index:9999;';
  modal.innerHTML = `
    <div style="background:var(--card);border-radius:16px;padding:28px 28px 24px;max-width:420px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.3)">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <div style="width:42px;height:42px;border-radius:50%;background:#fee2e2;display:flex;align-items:center;justify-content:center;flex-shrink:0">
          <i class="fa fa-triangle-exclamation" style="color:#dc2626;font-size:1.1rem"></i>
        </div>
        <div>
          <div style="font-size:1rem;font-weight:700;color:var(--text1)">Full Model Retraining</div>
          <div style="font-size:.78rem;color:var(--text3)">This action retrains all enrolled persons</div>
        </div>
      </div>
      <p style="font-size:.83rem;color:var(--text2);margin-bottom:20px;line-height:1.55">
        Full retraining will <strong>rebuild the model from scratch</strong> using all enrolled persons' datasets.
        This is resource-intensive and may take several minutes. All existing trained data will be replaced.
      </p>
      <div style="display:flex;gap:10px;justify-content:flex-end">
        <button onclick="document.getElementById('tmFullModal').style.display='none'"
          style="padding:9px 20px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text2);font-size:.83rem;cursor:pointer">
          Cancel
        </button>
        <button onclick="tmRunFullRetrain()" id="tmFullConfirmBtn"
          style="padding:9px 20px;border-radius:8px;border:none;background:#dc2626;color:#fff;font-size:.83rem;font-weight:600;cursor:pointer">
          <i class="fa fa-rotate"></i> Yes, Retrain All
        </button>
      </div>
    </div>`;
  document.body.appendChild(modal);
}

async function tmRunFullRetrain() {
  const modal = document.getElementById('tmFullModal');
  const btn   = document.getElementById('tmFullConfirmBtn');
  if (btn) { btn.disabled=true; btn.innerHTML='<i class="fa fa-spinner fa-spin"></i> Starting...'; }
  try {
    const res = await api.trainFull();
    if (modal) modal.style.display='none';
    if (res.status === 'already_running' || res.status === 'conflict') {
      toast(res.message||'Training already running', 'warn');
      return;
    }
    toast('Full retraining started in background!', 'info');
    clearInterval(TM.fullTrainTimer);
    TM.fullTrainTimer = setInterval(async () => {
      try {
        const s = await api.trainFullStatus();
        if (!s.running) {
          clearInterval(TM.fullTrainTimer);
          if (s.error) toast('Full retraining error: ' + s.error, 'error');
          else if (s.done) { toast('Full retraining completed!', 'success'); tmLoadStatus(); }
        }
      } catch(e){}
    }, 3000);
  } catch(e) {
    if (btn) { btn.disabled=false; btn.innerHTML='<i class="fa fa-rotate"></i> Yes, Retrain All'; }
    toast('Failed: ' + (e.message||'Error starting full retrain'), 'error');
  }
}

// ── Training History tab ──────────────────────────────────
function tmRenderHistory() {
  const mainPanel = document.getElementById('tmPanelMain');
  if (!mainPanel) return;
  const data = TM.statusData;
  if (!data) { mainPanel.innerHTML=`<div class="tm-list-card"><div class="tm-empty">Load status first.</div></div>`; return; }

  // Build history from trained IDs across roles
  const rows = [];
  const roleInfo = [
    { key:'hod',     label:'HOD',     icon:'fa-user-tie',           color:'#7c3aed' },
    { key:'faculty',   label:'Faculty',   icon:'fa-chalkboard-teacher', color:'#1d4ed8' },
    { key:'student', label:'Student', icon:'fa-user-graduate',       color:'#15803d' },
  ];
  for (const r of roleInfo) {
    const trained = data[r.key]?.trained || [];
    for (const p of trained) {
      rows.push({ ...p, roleLabel:r.label, icon:r.icon, color:r.color });
    }
  }

  if (!rows.length) {
    mainPanel.innerHTML = `<div class="tm-list-card"><div class="tm-empty"><i class="fa fa-brain" style="font-size:1.4rem;margin-bottom:8px;color:var(--text3)"></i><br>No trained users found.<br><small>Train individual users to see history here.</small></div></div>`;
    return;
  }

  mainPanel.innerHTML = `
    <div class="tm-list-card">
      <div class="tm-list-head">
        <div class="tm-list-title"><i class="fa fa-clock-rotate-left"></i> Training History
          <span class="tm-pill tm-pill-green">${rows.length} Total Trained</span>
        </div>
      </div>
      ${rows.map(p=>`
        <div class="tm-person-row">
          <div class="tm-avatar" style="background:${p.color+'22'};color:${p.color}">${p.id.substring(0,2).toUpperCase()}</div>
          <div class="tm-person-info">
            <div class="tm-person-id">${p.id}</div>
            <div class="tm-person-meta">${p.roleLabel} &nbsp;·&nbsp; ${p.image_count} images</div>
          </div>
          <span class="tm-status-badge tm-badge-trained"><i class="fa fa-circle-check"></i> Trained</span>
        </div>`).join('')}
    </div>`;
}

// ── Legacy trainStart / checkTrainStatus kept for compat ──
async function startTraining() {
  if (!guardTrainingRoute()) return;
  try {
    await api.trainStart(); toast('Full training started (legacy)!','info');
    clearInterval(APP.trainPollTimer);
    APP.trainPollTimer = setInterval(checkTrainStatus, 3000);
  } catch(e) { toast('Failed: '+e.message,'error'); }
}

async function checkTrainStatus() {
  try {
    const s = await api.trainStatus();
    if (!s.running) {
      clearInterval(APP.trainPollTimer);
      if (s.error) toast('Training error: '+s.error,'error');
      else if (s.done) toast('Training complete!','success');
    }
  } catch(e) {}
}
// ── FACULTY DASHBOARD ─────────────────────────────────────────
async function renderFacDashboard() {
  const el = document.getElementById('facDashContent');
  if (!el) return;

  // ── BUGFIX: dashboard CSS used to be injected as a <style> tag inside
  // the temporary "Loading your dashboard..." skeleton's innerHTML below.
  // The moment real data arrived, el.innerHTML was replaced again with the
  // actual cards — which wiped out that <style> tag along with it, leaving
  // .fac-qbtn / .fac-mini-kpi / .fac-db-grid etc. completely unstyled
  // (icons still showed because Font Awesome is loaded globally, but the
  // layout/borders/grid collapsed). Injecting it once into <head> means it
  // survives every innerHTML swap for the lifetime of the page.
  if (!document.getElementById('facDashStyles')) {
    const facDashStyleTag = document.createElement('style');
    facDashStyleTag.id = 'facDashStyles';
    facDashStyleTag.textContent = `
      .fac-db-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
      .fac-db-grid.wide { grid-template-columns:2fr 1fr; }
      @media(max-width:800px){ .fac-db-grid,.fac-db-grid.wide{ grid-template-columns:1fr; } }
      .fac-mini-kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:18px; }
      @media(max-width:700px){ .fac-mini-kpis{ grid-template-columns:repeat(2,1fr); } }
      .fac-mini-kpi { background:var(--white); border:1.5px solid var(--border); border-radius:var(--r); padding:14px 12px; text-align:center; position:relative; overflow:hidden; box-shadow:var(--shadow); }
      .fac-mini-kpi::before { content:''; position:absolute; top:0; left:0; right:0; height:3px; background:var(--mk,var(--mint)); }
      .fac-mk-icon { font-size:1.3rem; color:var(--mk,var(--mint)); margin-bottom:6px; }
      .fac-mk-val  { font-size:1.6rem; font-weight:900; color:var(--text); }
      .fac-mk-lbl  { font-size:.72rem; color:var(--text2); margin-top:3px; font-weight:600; text-transform:uppercase; letter-spacing:.5px; }
      .fac-class-now { background:linear-gradient(135deg,#2fa882,#2284d4); color:#fff; border-radius:var(--r); padding:16px 20px; display:flex; align-items:center; gap:16px; margin-bottom:18px; }
      .fac-class-now.free { background:linear-gradient(135deg,#667eea,#764ba2); }
      .fac-cn-icon { font-size:2rem; opacity:.85; }
      .fac-cn-label { font-size:.7rem; text-transform:uppercase; letter-spacing:1px; opacity:.8; margin-bottom:2px; }
      .fac-cn-course { font-size:1.1rem; font-weight:800; }
      .fac-cn-meta { font-size:.8rem; opacity:.85; margin-top:4px; }
      .fac-cn-time { margin-left:auto; text-align:right; font-size:.8rem; opacity:.85; }
      .tt-today-row { display:flex; flex-direction:column; gap:8px; }
      .tt-slot { display:flex; align-items:center; gap:12px; padding:10px 14px; border-radius:var(--r-sm); background:var(--bg); border:1.5px solid var(--border); transition:.2s; }
      .tt-slot.active { background:var(--mint-l); border-color:var(--mint); }
      .tt-slot.done { opacity:.55; }
      .tt-slot-p { font-size:.72rem; font-weight:800; color:var(--text2); width:28px; text-align:center; }
      .tt-slot-time { font-size:.75rem; color:var(--text3); width:80px; }
      .tt-slot-course { flex:1; font-weight:700; font-size:.85rem; color:var(--text); }
      .tt-slot-meta { font-size:.75rem; color:var(--text2); }
      .tt-slot-badge { font-size:.68rem; font-weight:700; padding:2px 8px; border-radius:99px; }
      .tt-slot-badge.now { background:var(--mint); color:#fff; }
      .tt-slot-badge.done { background:var(--border); color:var(--text2); }
      .tt-slot-badge.upcoming { background:var(--sky-l); color:var(--sky-d); }
      .fac-att-row { display:flex; align-items:center; justify-content:space-between; padding:10px 0; border-bottom:1px solid var(--border); }
      .fac-att-row:last-child { border-bottom:none; }
      .fac-att-name { font-weight:700; font-size:.85rem; }
      .fac-att-id { font-size:.75rem; color:var(--text2); }
      .fac-att-pct-bar { width:70px; height:6px; background:var(--border); border-radius:3px; margin-top:4px; }
      .fac-att-pct-fill { height:100%; border-radius:3px; background:var(--mint); }
      .fac-req-item { display:flex; align-items:center; gap:12px; padding:10px 0; border-bottom:1px solid var(--border); }
      .fac-req-item:last-child { border-bottom:none; }
      .fac-req-icon { width:36px; height:36px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:.95rem; flex-shrink:0; }
      .fac-req-text { flex:1; }
      .fac-req-name { font-weight:700; font-size:.85rem; }
      .fac-req-date { font-size:.75rem; color:var(--text2); }
      .fac-req-badge { font-size:.7rem; font-weight:700; padding:3px 9px; border-radius:99px; }
      .rb-pending { background:var(--amber-l); color:var(--amber-d); }
      .rb-approved { background:var(--mint-l); color:var(--mint-d); }
      .rb-rejected { background:var(--coral-l); color:var(--coral-d); }
      .fac-section-title { font-size:.75rem; font-weight:800; text-transform:uppercase; letter-spacing:.6px; color:var(--text2); margin:0 0 10px; display:flex; align-items:center; gap:6px; }
      .fac-refresh-btn { background:none; border:none; color:var(--mint-d); cursor:pointer; font-size:.8rem; font-weight:700; margin-left:auto; display:flex; align-items:center; gap:4px; }
      .fac-quick-btns { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:18px; }
      .fac-qbtn { flex:1; min-width:120px; padding:12px 14px; border-radius:var(--r-sm); border:1.5px solid var(--border); background:var(--white); color:var(--text); font-weight:700; font-size:.82rem; cursor:pointer; display:flex; align-items:center; gap:8px; transition:.2s; box-shadow:var(--shadow); }
      .fac-qbtn:hover { border-color:var(--mint); background:var(--mint-l); color:var(--mint-d); transform:translateY(-2px); }
      .fac-qbtn i { color:var(--mint-d); }
      .fac-workload-bar { margin:8px 0; }
      .fac-wl-label { display:flex; justify-content:space-between; font-size:.8rem; color:var(--text2); margin-bottom:4px; }
      .fac-wl-track { height:8px; background:var(--border); border-radius:4px; }
      .fac-wl-fill { height:100%; border-radius:4px; background:linear-gradient(90deg,var(--mint),var(--sky)); transition:width .5s ease; }
    `;
    document.head.appendChild(facDashStyleTag);
  }

  // ── helpers ──────────────────────────────────────────────────
  const now = new Date();
  const todayKey = ['SUN','MON','TUE','WED','THU','FRI','SAT'][now.getDay()];
  const todayLabel = now.toLocaleDateString('en-IN', { weekday:'long', year:'numeric', month:'long', day:'numeric' });
  const timeStr = now.toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit' });

  function getCurrentPeriod() {
    const h = now.getHours(), m = now.getMinutes();
    const mins = h * 60 + m;
    const slots = [
      { no:1, start:9*60,   end:10*60  },
      { no:2, start:10*60,  end:11*60  },
      { no:3, start:11*60+15, end:12*60+15 },
      { no:4, start:12*60+15, end:13*60+15 },
      { no:5, start:14*60,  end:15*60  },
      { no:6, start:15*60,  end:16*60  },
      { no:7, start:16*60,  end:17*60  },
    ];
    return slots.find(s => mins >= s.start && mins < s.end) || null;
  }

  function miniKpi(label, val, icon, color) {
    return `<div class="fac-mini-kpi" style="--mk:#${color.replace('#','')}">
      <div class="fac-mk-icon"><i class="fa ${icon}"></i></div>
      <div class="fac-mk-val">${val ?? '—'}</div>
      <div class="fac-mk-lbl">${label}</div>
    </div>`;
  }

  function statusBadge(pct) {
    pct = parseFloat(pct) || 0;
    if (pct >= 75) return `<span class="badge b-g">${pct}%</span>`;
    if (pct >= 70) return `<span class="badge b-w">${pct}%</span>`;
    return `<span class="badge b-d">${pct}%</span>`;
  }

  // ── skeleton while loading ───────────────────────────────────
  el.innerHTML = `
    <div class="empty-msg"><i class="fa fa-spinner fa-spin" style="font-size:1.8rem"></i><p style="margin-top:10px">Loading your dashboard...</p></div>
  `;

  try {
    // ── Parallel data fetch ──────────────────────────────────
    const [todayAtt, reqCounts, ttRows, facDetail] = await Promise.allSettled([
      api.todayAtt(),
      apiFetch('/api/faculty/requests/dashboard-counts'),
      (typeof apiEx !== 'undefined' && _user.fac_id)
        ? apiEx.fullFacultyTT(_user.fac_id)
        : Promise.resolve([]),
      _user.fac_id
        ? apiFetch('/api/faculty/' + encodeURIComponent(_user.fac_id))
        : Promise.resolve({}),
    ]);

    const today      = todayAtt.status === 'fulfilled'  ? (todayAtt.value || [])    : [];
    const counts     = reqCounts.status === 'fulfilled' ? (reqCounts.value || {})   : {};
    const ttAll      = ttRows.status === 'fulfilled'    ? (ttRows.value || [])      : [];
    const facInfo    = facDetail.status === 'fulfilled' ? (facDetail.value || {})   : {};

    // ── Today's timetable for this faculty ──────────────────
    const currentPeriod = getCurrentPeriod();
    const todayTT = ttAll
      .filter(r => (r.day_of_week || '').toUpperCase() === todayKey)
      .sort((a, b) => (a.period_no || 0) - (b.period_no || 0));

    // ── Attendance stats ────────────────────────────────────
    const totalPresent = today.length;
    const uniqueStudents = new Set(today.map(r => r.student_id)).size;
    const latestRecord = today[0] || null;

    // ── Build welcome banner ─────────────────────────────────
    const firstName = (_user.name || 'Faculty').split(' ')[0];
    const dept = facInfo.dept || _user.dept || '';
    const attPct = facInfo.att_pct || 0;
    const greetHour = now.getHours();
    const greet = greetHour < 12 ? 'Good Morning' : greetHour < 17 ? 'Good Afternoon' : 'Good Evening';

    // ── "Now" class banner ───────────────────────────────────
    let nowClassHtml = '';
    if (todayTT.length > 0) {
      const nowSlot = currentPeriod
        ? todayTT.find(r => r.period_no === currentPeriod.no)
        : null;
      if (nowSlot) {
        const pt = PERIOD_TIMES.find(p => p.no === nowSlot.period_no);
        nowClassHtml = `<div class="fac-class-now">
          <div class="fac-cn-icon"><i class="fa fa-chalkboard-user"></i></div>
          <div>
            <div class="fac-cn-label">Currently Teaching · Period ${nowSlot.period_no}</div>
            <div class="fac-cn-course">${nowSlot.course_name || '—'}</div>
            <div class="fac-cn-meta"><i class="fa fa-users" style="margin-right:4px"></i>${nowSlot.dept || ''} Y${nowSlot.year || ''}${nowSlot.section || ''} &nbsp;|&nbsp; <i class="fa fa-door-open" style="margin-right:4px"></i>${nowSlot.room || 'Room TBA'}</div>
          </div>
          <div class="fac-cn-time"><i class="fa fa-clock"></i><br>${pt ? pt.time : ''}</div>
        </div>`;
      } else {
        // Find next class
        const nextSlot = currentPeriod
          ? todayTT.find(r => r.period_no > currentPeriod.no)
          : todayTT[0];
        if (nextSlot) {
          const pt = PERIOD_TIMES.find(p => p.no === nextSlot.period_no);
          nowClassHtml = `<div class="fac-class-now free">
            <div class="fac-cn-icon"><i class="fa fa-mug-hot"></i></div>
            <div>
              <div class="fac-cn-label">Free Period · Next class at P${nextSlot.period_no}</div>
              <div class="fac-cn-course">${nextSlot.course_name || '—'}</div>
              <div class="fac-cn-meta">${nextSlot.dept || ''} Y${nextSlot.year || ''}${nextSlot.section || ''}</div>
            </div>
            <div class="fac-cn-time"><i class="fa fa-clock"></i><br>${pt ? pt.time : ''}</div>
          </div>`;
        }
      }
    }

    // ── Today's timetable slots ─────────────────────────────
    let ttHtml = '';
    if (todayTT.length === 0) {
      ttHtml = '<div style="text-align:center;padding:20px;color:var(--text3)"><i class="fa fa-calendar-xmark" style="font-size:1.5rem;display:block;margin-bottom:8px"></i>No classes scheduled today</div>';
    } else {
      ttHtml = '<div class="tt-today-row">';
      todayTT.forEach(r => {
        const pt = PERIOD_TIMES.find(p => p.no === r.period_no);
        const isCurrent = currentPeriod && r.period_no === currentPeriod.no;
        const isDone = currentPeriod ? r.period_no < currentPeriod.no
          : (now.getHours() >= 17);
        const slotClass = isCurrent ? 'active' : isDone ? 'done' : '';
        const badgeClass = isCurrent ? 'now' : isDone ? 'done' : 'upcoming';
        const badgeLabel = isCurrent ? '● Now' : isDone ? '✓ Done' : '◷ Up next';
        ttHtml += `<div class="tt-slot ${slotClass}">
          <div class="tt-slot-p">P${r.period_no}</div>
          <div class="tt-slot-time">${pt ? pt.time : '—'}</div>
          <div>
            <div class="tt-slot-course">${r.course_name || '—'}</div>
            <div class="tt-slot-meta">${r.dept || ''} Y${r.year || ''}${r.section || ''} &nbsp;|&nbsp; ${r.room || 'TBA'}</div>
          </div>
          <span class="tt-slot-badge ${badgeClass}">${badgeLabel}</span>
        </div>`;
      });
      ttHtml += '</div>';
    }

    // ── Recent attendance list ───────────────────────────────
    // BUGFIX: this widget must stay read-only and must never send the
    // faculty into the admin/role-based attendance page (that page starts
    // camera sessions and lets admins mark/override attendance — not
    // appropriate here). "Full View" now opens a read-only modal listing
    // every record for today instead. The compact box itself is capped at
    // 5 rows so a 40-student class doesn't flood the dashboard.
    APP._facTodayAttendance = today; // full list, used by the Full View modal
    let attHtml = '';
    if (today.length === 0) {
      attHtml = '<div style="text-align:center;padding:20px;color:var(--text3)"><i class="fa fa-user-clock" style="font-size:1.5rem;display:block;margin-bottom:8px"></i>No attendance marked today</div>';
    } else {
      const recent = today.slice(0, 5);
      attHtml = recent.map(r => `<div class="fac-att-row">
        <div>
          <div class="fac-att-name">${r.name || '?'}</div>
          <div class="fac-att-id"><code>${r.student_id || '?'}</code> &nbsp;·&nbsp; P${r.period || '—'} &nbsp;·&nbsp; ${String(r.time || '').slice(0,8)}</div>
        </div>
        ${confBadge(r.confidence)}
      </div>`).join('');
      if (today.length > 5) {
        attHtml += `<div style="text-align:center;padding:10px;font-size:.8rem;color:var(--mint-d);font-weight:700;cursor:pointer" onclick="showFacAttFullView()">View all ${today.length} records →</div>`;
      }
    }

    // ── Pending requests preview ─────────────────────────────
    const pendingLeave = counts.pending_leave_requests ?? 0;
    const pendingOD = counts.pending_od_requests ?? 0;
    const approvedToday = counts.approved_requests_today ?? 0;
    const rejectedToday = counts.rejected_requests_today ?? 0;

    // ── Workload bar (hours/week from timetable) ─────────────
    const totalPeriods = ttAll.length;
    const maxLoad = 35; // typical max
    const loadPct = Math.min(Math.round(totalPeriods / maxLoad * 100), 100);
    const loadLabel = totalPeriods === 0 ? 'No load data'
      : totalPeriods <= 15 ? 'Light load'
      : totalPeriods <= 25 ? 'Moderate'
      : 'Heavy load';

    // ── Final HTML assembly ─────────────────────────────────
    el.innerHTML = `
      <!-- Welcome Banner -->
      <div class="fac-dash-welcome" style="margin-bottom:20px">
        <div class="fdw-bg"></div>
        <div class="fdw-title">${greet}, ${firstName}! 👋</div>
        <div class="fdw-sub">Faculty Portal &nbsp;·&nbsp; ${_user.fac_id || ''} ${dept ? '&nbsp;·&nbsp; ' + dept : ''}</div>
        <div class="fdw-meta">
          <span class="fdw-m"><i class="fa fa-calendar-day"></i> ${todayLabel}</span>
          <span class="fdw-m"><i class="fa fa-clock"></i> ${timeStr}</span>
          ${attPct ? `<span class="fdw-m"><i class="fa fa-chart-line"></i> My Attendance: ${attPct}%</span>` : ''}
        </div>
      </div>

      <!-- Quick Action Buttons removed — same links already live in the
           sidebar under "My Portal" / "Request Management", so this row
           was a duplicate. -->

      <!-- KPI Strip -->
      <div class="fac-mini-kpis">
        ${miniKpi('Present Today', totalPresent, 'fa-circle-check', '#4ecba8')}
        ${miniKpi('Unique Students', uniqueStudents, 'fa-users', '#4da6f5')}
        ${miniKpi('Pending Leave', pendingLeave, 'fa-umbrella-beach', '#ffb347')}
        ${miniKpi('Pending OD', pendingOD, 'fa-id-badge', '#e05454')}
      </div>

      <!-- Now class banner -->
      ${nowClassHtml}

      <!-- Main 2-col grid -->
      <div class="fac-db-grid wide">
        <!-- Left: Today's Schedule -->
        <div class="card" style="overflow:hidden">
          <div class="card-head">
            <h4><i class="fa fa-calendar-day"></i> Today's Schedule
              <span style="font-size:.72rem;font-weight:600;color:var(--text2);margin-left:6px">${now.toLocaleDateString('en-IN',{weekday:'long'})}</span>
            </h4>
            <button class="fac-refresh-btn" onclick="renderFacDashboard()"><i class="fa fa-rotate-right"></i> Refresh</button>
          </div>
          <div style="padding:14px 16px">${ttHtml}</div>
        </div>

        <!-- Right: Request Summary -->
        <div style="display:flex;flex-direction:column;gap:16px">
          <!-- Request counts -->
          <div class="card" style="overflow:hidden">
            <div class="card-head">
              <h4><i class="fa fa-inbox"></i> Request Summary</h4>
              <button class="fac-refresh-btn" onclick="showPage('fac-leave-approvals')">Manage →</button>
            </div>
            <div style="padding:14px 16px">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
                <div style="background:var(--amber-l);border-radius:var(--r-sm);padding:12px;text-align:center;cursor:pointer" onclick="showPage('fac-leave-approvals')">
                  <div style="font-size:1.6rem;font-weight:900;color:var(--amber-d)">${pendingLeave}</div>
                  <div style="font-size:.72rem;font-weight:700;color:var(--amber-d);text-transform:uppercase;letter-spacing:.5px">Pending Leave</div>
                </div>
                <div style="background:var(--sky-l);border-radius:var(--r-sm);padding:12px;text-align:center;cursor:pointer" onclick="showPage('fac-od-approvals')">
                  <div style="font-size:1.6rem;font-weight:900;color:var(--sky-d)">${pendingOD}</div>
                  <div style="font-size:.72rem;font-weight:700;color:var(--sky-d);text-transform:uppercase;letter-spacing:.5px">Pending OD</div>
                </div>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                <div style="background:var(--mint-l);border-radius:var(--r-sm);padding:10px;text-align:center">
                  <div style="font-size:1.3rem;font-weight:900;color:var(--mint-d)">${approvedToday}</div>
                  <div style="font-size:.7rem;font-weight:700;color:var(--mint-d);text-transform:uppercase;letter-spacing:.5px">Approved Today</div>
                </div>
                <div style="background:var(--coral-l);border-radius:var(--r-sm);padding:10px;text-align:center">
                  <div style="font-size:1.3rem;font-weight:900;color:var(--coral-d)">${rejectedToday}</div>
                  <div style="font-size:.7rem;font-weight:700;color:var(--coral-d);text-transform:uppercase;letter-spacing:.5px">Rejected Today</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Weekly workload -->
          <div class="card" style="overflow:hidden">
            <div class="card-head"><h4><i class="fa fa-gauge-high"></i> Teaching Workload</h4></div>
            <div style="padding:14px 16px">
              <div class="fac-workload-bar">
                <div class="fac-wl-label">
                  <span>${totalPeriods} periods/week</span>
                  <span style="font-weight:700;color:var(--mint-d)">${loadLabel}</span>
                </div>
                <div class="fac-wl-track"><div class="fac-wl-fill" style="width:${loadPct}%"></div></div>
              </div>
              <div style="font-size:.78rem;color:var(--text2);margin-top:8px">
                <i class="fa fa-circle-info" style="margin-right:4px"></i>
                ${totalPeriods > 0 ? `${todayTT.length} class${todayTT.length !== 1 ? 'es' : ''} today out of ${totalPeriods} this week` : 'No timetable data available'}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent Attendance -->
      <div class="card" style="overflow:hidden">
        <div class="card-head">
          <h4><i class="fa fa-list-check"></i> Today's Attendance Records
            <span style="font-size:.78rem;font-weight:600;color:var(--text2);margin-left:6px">${today.length} record${today.length !== 1 ? 's' : ''}</span>
          </h4>
          <button class="fac-refresh-btn" onclick="showFacAttFullView()">Full View →</button>
        </div>
        <div style="padding:6px 16px 10px">${attHtml}</div>
      </div>
    `;

  } catch(e) {
    el.innerHTML = `<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>${e.message}</p><button class="btn-primary" onclick="renderFacDashboard()"><i class="fa fa-rotate-right"></i> Retry</button></div>`;
  }
}

// ── CHARTS ────────────────────────────────────────────────────
function mkBar(id,labels,data,colors,suffix){
  const ctx=document.getElementById(id); if(!ctx) return;
  try{APP.charts[id]?.destroy();}catch(e){}
  APP.charts[id]=new Chart(ctx,{type:'bar',data:{labels,datasets:[{data,backgroundColor:Array.isArray(colors)?colors:data.map(()=>colors),borderRadius:8,borderSkipped:false}]},options:{responsive:true,maintainAspectRatio:true,plugins:{legend:{display:false},tooltip:{backgroundColor:'#fff',titleColor:'#1a2332',bodyColor:'#5a6a80',borderColor:'#dde4f0',borderWidth:1.5,padding:10,cornerRadius:10,callbacks:{label:c=>' '+c.parsed.y+(suffix||'')}}},scales:{x:{grid:{display:false},ticks:{color:'#96a8be',font:{size:10,family:'Plus Jakarta Sans'}}},y:{grid:{color:'rgba(0,0,0,.06)'},ticks:{color:'#96a8be',font:{size:10}},beginAtZero:true}}}});
}

function mkDonut(id,labels,data,colors){
  const ctx=document.getElementById(id); if(!ctx) return;
  try{APP.charts[id]?.destroy();}catch(e){}
  APP.charts[id]=new Chart(ctx,{type:'doughnut',data:{labels,datasets:[{data,backgroundColor:colors,borderWidth:3,borderColor:'#fff',hoverOffset:8}]},options:{responsive:true,maintainAspectRatio:true,cutout:'65%',plugins:{legend:{position:'bottom',labels:{color:'#5a6a80',font:{size:10.5,family:'Plus Jakarta Sans'},padding:10,boxWidth:12}},tooltip:{backgroundColor:'#fff',titleColor:'#1a2332',bodyColor:'#5a6a80',borderColor:'#dde4f0',borderWidth:1.5,padding:10,cornerRadius:10}}}});
}

// ── HELPERS ───────────────────────────────────────────────────
function kpi(label,value,icon,color){return'<div class="kpi-card" style="--kc:'+color+'"><div class="kpi-icon"><i class="fa '+icon+'"></i></div><div class="kpi-val">'+value+'</div><div class="kpi-lbl">'+label+'</div></div>';}
function attBar(pct){const st=getStatus(pct);return'<div class="att-bar"><div class="att-track"><div class="att-fill '+st.cls+'" style="width:'+pct+'%"></div></div><span class="att-pct" style="color:'+st.color+'">'+pct+'%</span></div>';}
function confBadge(conf){const p=Math.round(parseFloat(conf||0)*100);return'<span class="badge '+(p>=75?'b-g':p>=50?'b-w':'b-d')+'">'+p+'%</span>';}

// ── Faculty dashboard "Today's Attendance Records" — Full View ──
// Read-only modal that lists EVERY record marked today (e.g. all 40
// students of a class), reusing the data already fetched for the
// compact dashboard widget. Intentionally does NOT navigate to the
// admin/role-based attendance page — faculty should only ever see a
// read-only list of their own students' attendance here, never the
// camera/session controls used to mark attendance.
function showFacAttFullView() {
  const records = APP._facTodayAttendance || [];
  const title = document.getElementById('infoModalTitle');
  const body  = document.getElementById('infoModalBody');
  if (!title || !body) return;
  title.innerHTML = `<i class="fa fa-list-check"></i> Today's Attendance Records — ${records.length} record${records.length !== 1 ? 's' : ''}`;
  if (records.length === 0) {
    body.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text3)"><i class="fa fa-user-clock" style="font-size:1.6rem;display:block;margin-bottom:8px"></i>No attendance marked today</div>';
  } else {
    body.innerHTML = `<div style="max-height:60vh;overflow-y:auto">${records.map(r => `
      <div class="fac-att-row">
        <div>
          <div class="fac-att-name">${r.name || '?'}</div>
          <div class="fac-att-id"><code>${r.student_id || '?'}</code> &nbsp;·&nbsp; P${r.period || '—'} &nbsp;·&nbsp; ${String(r.time || '').slice(0,8)}</div>
        </div>
        ${confBadge(r.confidence)}
      </div>`).join('')}</div>`;
  }
  document.getElementById('infoModal').classList.remove('dn');
}

function getStatus(pct){if(pct>=75)return{cls:'g',bc:'b-g',label:'✓ Good',color:'var(--mint-d)'};if(pct>=70)return{cls:'w',bc:'b-w',label:'⚠ Warn',color:'var(--amber-d)'};if(pct>=65)return{cls:'d',bc:'b-d',label:'✗ Poor',color:'var(--coral-d)'};return{cls:'d',bc:'b-c',label:'☠ Critical',color:'#b22222'};}
function initials(name){return(name||'').split(' ').map(n=>n[0]).join('').toUpperCase().slice(0,2)||'??';}
// =============================================================
// GLOBAL NOTIFICATION SYSTEM (single source of truth)
// Aggregates everything "pending" relevant to the logged-in role
// — low-attendance alerts, pending Leave requests, pending OD
// requests, pending attendance-override (HOD) requests — into one
// count. Drives BOTH the topbar bell (#notifBadge) and the sidebar
// Alerts pill (#navAlertPill), so they can never disagree.
//
// Triggered: on login (startApp), on session restore (page
// refresh), on a recurring poll, and immediately after any
// approve/reject action so the count updates instantly instead of
// waiting for the next poll.
// =============================================================
var _notifBreakdown = { lowAttendance: 0, pendingLeave: 0, pendingOD: 0, pendingOverrides: 0 };
var _notifCount = 0;
var _notifPollMs = 45000;

async function refreshNotificationCount() {
  if (!_token) return;
  var counts = { lowAttendance: 0, pendingLeave: 0, pendingOD: 0, pendingOverrides: 0 };

  // Low-attendance alerts — admin / hod / classincharge only (the
  // roles that actually have an "Alerts" page in their nav).
  try {
    if (['admin', 'hod', 'classincharge'].includes(APP.role)) {
      var low = await api.lowAttendance(75, 180);
      var list = Array.isArray(low) ? low : (low && low.students) || [];
      _alertStudents = list;            // keep existing Alerts-page state in sync
      counts.lowAttendance = list.length;
    }
  } catch (e) { /* non-fatal — leave at 0 */ }

  // Pending attendance-correction overrides — HOD only.
  try {
    if (APP.role === 'hod') {
      var pending = await apiFetch('/api/attendance/override/pending?hod_only=true');
      var pList = (pending && pending.requests) ? pending.requests : (Array.isArray(pending) ? pending : []);
      counts.pendingOverrides = pList.length;
    }
  } catch (e) { /* non-fatal */ }

  // Pending Leave + OD requests — faculty (their own queue) and HOD
  // (department-wide queue); same endpoint, scoped server-side by role.
  try {
    if (APP.role === 'faculty' || APP.role === 'hod') {
      var c = await apiFetch('/api/faculty/requests/dashboard-counts');
      counts.pendingLeave = c.pending_leave_requests ?? 0;
      counts.pendingOD    = c.pending_od_requests ?? 0;
    }
  } catch (e) { /* non-fatal */ }

  _notifBreakdown = counts;
  _notifCount = counts.lowAttendance + counts.pendingLeave + counts.pendingOD + counts.pendingOverrides;
  _paintNotifBadges(_notifCount);
}

function _paintNotifBadges(count) {
  var bell = document.getElementById('notifBadge');
  if (bell) {
    bell.textContent = count;
    bell.style.display = count > 0 ? 'flex' : 'none';
  }
  var pill = document.getElementById('navAlertPill');
  if (pill) {
    pill.textContent = count;
    pill.style.display = count > 0 ? 'flex' : 'none';
  }
}

function startNotificationPolling() {
  if (APP.notifPollTimer) clearInterval(APP.notifPollTimer);
  refreshNotificationCount();
  APP.notifPollTimer = setInterval(refreshNotificationCount, _notifPollMs);
}

function stopNotificationPolling() {
  if (APP.notifPollTimer) clearInterval(APP.notifPollTimer);
  APP.notifPollTimer = null;
  _notifBreakdown = { lowAttendance: 0, pendingLeave: 0, pendingOD: 0, pendingOverrides: 0 };
  _notifCount = 0;
  _paintNotifBadges(0);
}

// Clicking the bell — go to whatever is actually pending, instead of
// always jumping straight to the low-attendance Alerts page.
function openNotificationCenter() {
  var b = _notifBreakdown;
  if (APP.role === 'faculty') {
    showPage(b.pendingOD > b.pendingLeave ? 'fac-od-approvals' : 'fac-leave-approvals');
    return;
  }
  if (APP.role === 'hod') {
    if (b.pendingOverrides > 0) { showPage('hod_approvals'); return; }
    if (b.pendingOD > 0 || b.pendingLeave > 0) { showPage('hod-od-approvals'); return; }
    showPage('alerts');
    return;
  }
  showPage('alerts');
}

function setEl(id,val){const el=document.getElementById(id);if(el)el.innerHTML=val;}
function closeModal(id){document.getElementById(id)?.classList.add('dn');}
function toast(msg,type){const icons={success:'fa-circle-check',error:'fa-circle-exclamation',info:'fa-circle-info',warn:'fa-triangle-exclamation'};const z=document.getElementById('toastContainer');if(!z)return;const el=document.createElement('div');el.className='toast '+(type||'info');el.innerHTML='<i class="fa '+(icons[type||'info']||'fa-circle-info')+'"></i><span>'+msg+'</span>';z.appendChild(el);setTimeout(()=>{el.classList.add('toast-out');setTimeout(()=>el.remove(),300);},4000);}

// Stubs for HTML-referenced functions
// ── Stub functions (overridden by features.js after DOMContentLoaded) ──────────
// Non-feature stubs (keep as real no-ops)
// attOnDeptChange / attOnCourseChange / attOnYearChange
// ── Implemented in attendance.js (role-based version) ─────────
// These stubs are kept here only as fallbacks.  attendance.js
// overrides them with full implementations after DOMContentLoaded.
async function attOnDeptChange()  {
  if (typeof ATT !== 'undefined') return; // handled by attendance.js
}
async function attOnCourseChange() {
  if (typeof ATT !== 'undefined') return;
}
async function attOnYearChange() {
  if (typeof ATT !== 'undefined') return;
}
function ttOnDeptChange(){}
function ttOnCourseChange(){}
function renderTimetable(){}
function renderCIPage(){}
function loadCIData(){}
function ciAlert(){}
function onAnlLevelChange(){}
function renderAnalytics(){}
function renderMyTimetable(){ renderTimetablePage(); }
function renderMyClasses(){}
function renderMyAttendance(){ renderReportsPage(); }

// Feature 1 stubs — replaced by features.js
function drillGoto(){}
function drillToCourse(d){ window.drillToCourse && window.drillToCourse(d); }
function drillToSection(c,col,dk){ window.drillToSection && window.drillToSection(c,col,dk); }
function drillToSectionDetail(c,s,col,dk){ window.drillToSectionDetail && window.drillToSectionDetail(c,s,col,dk); }
function initDeptDrill(){ window.initDeptDrill && window.initDeptDrill(); }

// Feature 2 stubs — replaced by features.js
function renderFacultyPage(){ window.renderFacultyPage && window.renderFacultyPage(); }
function openMarkFacultyModal(){ window.openMarkFacultyModal && window.openMarkFacultyModal(); }
function editFacAtt(id,lid){ window.editFacAtt && window.editFacAtt(id,lid); }
function saveFacultyAttendance(){ window.saveFacultyAttendance && window.saveFacultyAttendance(); }
function viewFacDetail(id){ window.viewFacDetail && window.viewFacDetail(id); }

document.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const ls = document.getElementById('loginScreen');
  if (ls && ls.style.display !== 'none') {
    const path = window.location.pathname.toLowerCase();
    if (path.includes('hod') || (document.getElementById('hodPortalOnly') && !document.getElementById('hodPortalOnly').classList.contains('dn'))) {
      loginHod();
    } else if (path.includes('faculty') || (document.getElementById('facultyPortalOnly') && !document.getElementById('facultyPortalOnly').classList.contains('dn')) || document.querySelector('.ptab.active')?.dataset?.portal === 'faculty') {
      loginFaculty();
    } else {
      loginAdmin();
    }
  }
});
document.addEventListener('click',e=>{const sb=document.getElementById('sidebar');if(sb?.classList.contains('open')&&!sb.contains(e.target)&&!e.target.closest('.mob-ham'))closeSidebar();});

// ── Portal UI Configuration Helper ──────────────────────────
function setupPortalView(portal) {
  const adminOnly = document.getElementById('adminPortalOnly');
  const hodOnly   = document.getElementById('hodPortalOnly');
  const facOnly   = document.getElementById('facultyPortalOnly');
  const gw        = document.getElementById('unifiedGateway');
  const lc        = document.querySelector('.login-card');
  const tabs      = document.querySelector('.portal-tabs');
  const adminPanel= document.getElementById('adminPortal');
  const facPanel  = document.getElementById('facultyPortal');

  if (gw) gw.classList.add('dn');
  if (lc) lc.classList.remove('dn');

  // Standalone dedicated portal pages (/admin, /hod, /faculty)
  if (adminOnly && !hodOnly && !facOnly) {
    adminOnly.classList.remove('dn');
    return;
  }
  if (hodOnly && !adminOnly && !facOnly) {
    hodOnly.classList.remove('dn');
    return;
  }
  if (facOnly && !adminOnly && !hodOnly) {
    facOnly.classList.remove('dn');
    return;
  }

  // Multi-panel layout (index.html fallback)
  if (adminOnly && hodOnly && facOnly) {
    adminOnly.classList.toggle('dn', portal !== 'admin');
    hodOnly.classList.toggle('dn', portal !== 'hod');
    facOnly.classList.toggle('dn', portal !== 'faculty');
  } else {
    // Dynamic fallback inside index.html
    if (tabs) tabs.style.display = 'none';
    if (portal === 'faculty') {
      if (adminPanel) adminPanel.classList.add('dn');
      if (facPanel) facPanel.classList.remove('dn');
    } else if (portal === 'hod') {
      if (facPanel) facPanel.classList.add('dn');
      if (adminPanel) {
        adminPanel.classList.remove('dn');
        const roleSel = document.getElementById('adminRoleSelect');
        if (roleSel) { roleSel.value = 'hod'; onAdminRoleChange(); }
        const rField = document.querySelector('#adminPortal .login-field:first-of-type');
        if (rField) rField.style.display = 'none';
        const hdr = adminPanel.querySelector('.portal-header');
        if (hdr) hdr.innerHTML = '<h3><span class="portal-badge badge-hod"><i class="fa fa-user-tie"></i> HOD Portal</span></h3><p>Sign in with your HOD ID or registered email</p>';
      }
    } else if (portal === 'admin') {
      if (facPanel) facPanel.classList.add('dn');
      if (adminPanel) {
        adminPanel.classList.remove('dn');
        const roleSel = document.getElementById('adminRoleSelect');
        if (roleSel) { roleSel.value = 'admin'; onAdminRoleChange(); }
        const rField = document.querySelector('#adminPortal .login-field:first-of-type');
        if (rField) rField.style.display = 'none';
        const hdr = adminPanel.querySelector('.portal-header');
        if (hdr) hdr.innerHTML = '<h3><span class="portal-badge badge-admin"><i class="fa fa-shield-halved"></i> Admin Portal</span></h3><p>Sign in with Administrator credentials</p>';
      }
    }
  }
}

// ── SESSION RESTORE & PORTAL ROUTE GUARDS on page load/refresh ──
document.addEventListener('DOMContentLoaded', async () => {
  if (window.__loginBootstrapped) return;
  window.__loginBootstrapped = true;

  const currentPath = window.location.pathname.toLowerCase();
  let activePortal = null;
  if (currentPath.includes('admin')) activePortal = 'admin';
  else if (currentPath.includes('hod')) activePortal = 'hod';
  else if (currentPath.includes('faculty')) activePortal = 'faculty';
  else if (currentPath.includes('student')) activePortal = 'student';

  const savedToken = sessionStorage.getItem('_token');
  const savedRole  = sessionStorage.getItem('_role');
  const savedUser  = sessionStorage.getItem('_user');
  const savedPage  = sessionStorage.getItem('_lastPage');

  // If already logged in:
  if (savedToken && savedRole) {
    // ── ROLE ISOLATION: Check if current URL matches the user's role ──
    if (activePortal && activePortal !== 'student') {
      const isAllowed = (activePortal === 'faculty')
        ? ['faculty', 'teacher', 'classincharge'].includes(savedRole)
        : (savedRole === activePortal);

      if (!isAllowed) {
        console.warn(`[PortalGuard] Access denied: User role "${savedRole}" cannot access "${activePortal}" portal`);
        const targetPortal = (savedRole === 'admin' ? 'admin' : (savedRole === 'hod' ? 'hod' : 'faculty'));
        alert(`Access Restricted:\nYou are logged in as ${savedRole.toUpperCase()}.\nYou cannot access the ${activePortal.toUpperCase()} Portal.\n\nRedirecting to your ${savedRole.toUpperCase()} Portal...`);
        window.location.replace('/' + targetPortal);
        return;
      }
    } else if (!activePortal) {
      // User is on root / or /app with an active session -> auto forward to their portal
      const targetPortal = (savedRole === 'admin' ? 'admin' : (savedRole === 'hod' ? 'hod' : 'faculty'));
      window.location.replace('/' + targetPortal);
      return;
    }

    // Validate token with backend
    try {
      _token = savedToken;
      const info = await apiFetch('/api/verify-token');
      _role  = info.role || savedRole || 'admin';
      try { _user = JSON.parse(savedUser) || {}; } catch(e) { _user = {}; }
      _user.role = _role;
      if (info.fac_id) _user.fac_id = info.fac_id;
      const looksLikeFallbackId = info.name && (info.name === info.username || info.name === info.fac_id || info.name === _user.fac_id);
      if (info.name && !looksLikeFallbackId) _user.name = info.name;
      if (info.username && !_user.username) _user.username = info.username;
      APP.role = _role;

      // Hide login, show app
      document.getElementById('loginScreen').style.display = 'none';
      document.getElementById('appShell').classList.remove('dn');
      syncPortalTabTitle(activePortal, _role);
      populateFacSelect();
      buildSideNav();
      setTopbarProfile();
      startClock();

      const targetPage = (typeof getPageFromUrl === 'function' ? getPageFromUrl() : null) || savedPage || (_role === 'faculty' ? 'fac-dashboard' : 'dashboard');
      setTimeout(() => {
        showPage(targetPage, false);
      }, 0);
      startNotificationPolling();
      return;
    } catch(e) {
      // Token invalid or expired — clear and show login
      sessionStorage.removeItem('_token');
      sessionStorage.removeItem('_role');
      sessionStorage.removeItem('_portal');
      sessionStorage.removeItem('_user');
      sessionStorage.removeItem('_lastPage');
      _token = null;
    }
  }

  // If NOT logged in:
  syncPortalTabTitle(activePortal);
  if (activePortal === 'admin') {
    setupPortalView('admin');
  } else if (activePortal === 'hod') {
    setupPortalView('hod');
  } else if (activePortal === 'faculty') {
    setupPortalView('faculty');
  } else {
    // Root or /app: Show Unified Gateway Hub if present
    const gw = document.getElementById('unifiedGateway');
    const lc = document.querySelector('.login-card');
    if (gw && lc) {
      gw.classList.remove('dn');
      lc.classList.add('dn');
      document.title = 'EduTrack Pro — Portal Gateway';
    }
  }
});

// =============================================================
// COURSES, ELECTIVES, TIMETABLE & ENROLLMENT  —  v10.0
// =============================================================

// ── API helpers ──────────────────────────────────────────────
const apiEx = {
  courses:       (dept, sem, type) => apiFetch('/api/courses?dept='+encodeURIComponent(dept)+(sem?'&semester='+sem:'')+(type?'&course_type='+type:'')),
  coursesByYear: (dept, year)      => apiFetch('/api/courses/by-year?dept='+encodeURIComponent(dept)+'&year='+year),
  electivePool:  (dept)            => apiFetch('/api/courses/elective-pool?dept='+encodeURIComponent(dept)),
  saveCourse:    (data)            => apiFetch('/api/courses', {method:'POST',body:JSON.stringify(data)}),
  semesters:     (dept)            => apiFetch('/api/semesters?dept='+encodeURIComponent(dept)),
  currentSem:    (dept,year)       => apiFetch('/api/semesters/current?dept='+encodeURIComponent(dept)+'&year='+year),
  electives:     (dept,sem,sec)    => apiFetch('/api/electives?dept='+encodeURIComponent(dept)+'&semester='+sem+(sec?'&section='+sec:'')),
  assignElective:(data)            => apiFetch('/api/electives/assign',{method:'POST',body:JSON.stringify(data)}),
  studentExt:    (sid)             => apiFetch('/api/students/extended?student_id='+encodeURIComponent(sid)),
  saveStudentExt:(data)            => apiFetch('/api/students/extended',{method:'POST',body:JSON.stringify(data)}),
  sectionStudents:(dept,year,sec)  => apiFetch('/api/students/section?dept='+encodeURIComponent(dept)+'&year='+year+'&section='+sec),
  studentTT:     (dept,year,sec,semester)   => apiFetch('/api/timetable/student?dept='+encodeURIComponent(dept)+'&year='+year+'&section='+sec+(semester?'&semester='+semester:'')),
  saveStudentTT: (data,force)      => apiFetch('/api/timetable/student'+(force?'?force=true':''),{method:'POST',body:JSON.stringify(data)}),
  facultyTT:       (facId,dept,semester) => apiFetch('/api/timetable/faculty?faculty_id='+encodeURIComponent(facId)+(dept?'&dept='+encodeURIComponent(dept):'')+(semester?'&semester='+semester:'')),
  periodSlots:   ()                => apiFetch('/api/period-slots'),
};

// ─────────────────────────────────────────────────────────────
// TIMETABLE PAGE  (Student + Faculty, dual view)
// ─────────────────────────────────────────────────────────────
const DEPT_LIST = [
  {key:'CSE',name:'CSE – Computer Science & Engineering'},
  {key:'AIDS',name:'AIDS – AI & Data Science'},
  {key:'IT',name:'IT – Information Technology'},
  {key:'CSBS',name:'CSBS – CS & Business Systems'},
  {key:'ECE',name:'ECE – Electronics & Communication'},
  {key:'EEE',name:'EEE – Electrical & Electronics'},
  {key:'BM',name:'BM – Bio Medical Engineering'},
  {key:'MECH',name:'MECH – Mechanical Engineering'},
  {key:'CIVIL',name:'CIVIL – Civil Engineering'},
];
const DAYS_ORDER = ['MON','TUE','WED','THU','FRI','SAT'];
const DAY_LABEL  = {MON:'Monday',TUE:'Tuesday',WED:'Wednesday',THU:'Thursday',FRI:'Friday',SAT:'Saturday'};

async function renderTimetablePage() {
  // Populate dept dropdown
  const deptSel = document.getElementById('ttDept');
  if (deptSel && deptSel.options.length <= 1) {
    DEPT_LIST.forEach(d => {
      const o = document.createElement('option');
      o.value = d.key; o.textContent = d.name;
      deptSel.appendChild(o);
    });
  }
  const ttCont = document.getElementById('ttContent');
  if (!ttCont) return;

  // Tabs: Student TT | Faculty TT | Manage TT
  if (!document.getElementById('ttTabStrip')) {
    const strip = document.createElement('div');
    strip.id = 'ttTabStrip';
    strip.className = 'tab-strip';
    strip.innerHTML = `
      <button class="tab-b active" onclick="ttSwitchTab('student',this)"><i class="fa fa-users"></i> Student Timetable</button>
      <button class="tab-b" onclick="ttSwitchTab('faculty',this)"><i class="fa fa-chalkboard-teacher"></i> Faculty Timetable</button>
      <button class="tab-b" onclick="ttSwitchTab('manage',this)"><i class="fa fa-pen-to-square"></i> Manage / Add</button>
    `;
    ttCont.parentElement.insertBefore(strip, ttCont);
  }
  ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>Select Department, Year, Semester and Section to view timetable</p></div>';
  window._ttActiveTab = window._ttActiveTab || 'student';
}

function ttSwitchTab(tab, btn) {
  document.querySelectorAll('#ttTabStrip .tab-b').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  window._ttActiveTab = tab;
  const dept     = document.getElementById('ttDept')?.value;
  const course   = document.getElementById('ttCourse')?.value;
  const semester = document.getElementById('ttSemester')?.value;
  const section  = document.getElementById('ttSection')?.value;
  if (tab === 'faculty') {
    renderFacultyTimetablePanel();
  } else if (dept && course && semester && section) {
    renderTimetable();
  } else {
    const ttCont = document.getElementById('ttContent');
    if (ttCont) ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>Select Department, Year, Semester and Section</p></div>';
  }
}

async function ttOnDeptChange() {
  const dept = document.getElementById('ttDept')?.value;
  const cSel = document.getElementById('ttCourse');
  const semSel = document.getElementById('ttSemester');
  const sSel = document.getElementById('ttSection');
  if (cSel) {
    cSel.innerHTML = '<option value="">Year</option>';
    if (dept) {
      [1,2,3,4].forEach(y => {
        const o = document.createElement('option');
        o.value = y; o.textContent = 'Year ' + y;
        cSel.appendChild(o);
      });
    }
  }
  if (semSel) { semSel.innerHTML = '<option value="">Semester</option>'; semSel.style.display = 'none'; }
  if (sSel)   { sSel.innerHTML   = '<option value="">Section</option>';   sSel.style.display   = 'none'; }
  const ttCont = document.getElementById('ttContent');
  if (ttCont) ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>Select Year, Semester and Section to view timetable</p></div>';
}

function ttOnCourseChange() {
  const year   = parseInt(document.getElementById('ttCourse')?.value);
  const semSel = document.getElementById('ttSemester');
  const sSel   = document.getElementById('ttSection');
  if (!semSel) return;

  // Reset section
  if (sSel) { sSel.innerHTML = '<option value="">Section</option>'; ['A','B','C'].forEach(s => { const o = document.createElement('option'); o.value=s; o.textContent='Section '+s; sSel.appendChild(o); }); sSel.style.display = 'none'; }

  if (!year) { semSel.style.display = 'none'; semSel.innerHTML = '<option value="">Semester</option>'; return; }

  // Always show all 8 semesters
  semSel.innerHTML = '<option value="">— Select Semester —</option>'
    + [1,2,3,4,5,6,7,8].map(s => `<option value="${s}">Semester ${s}</option>`).join('');
  semSel.style.display = '';

  const ttCont = document.getElementById('ttContent');
  if (ttCont) ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>Select Semester and Section to view timetable</p></div>';
}

function ttOnSemesterChange() {
  const sem  = document.getElementById('ttSemester')?.value;
  const sSel = document.getElementById('ttSection');
  if (!sSel) return;
  if (sem) {
    sSel.style.display = '';
  } else {
    sSel.style.display = 'none';
  }
  sSel.value = '';
  const ttCont = document.getElementById('ttContent');
  if (ttCont) ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>Select Section to view timetable</p></div>';
}

async function renderTimetable() {
  const dept     = document.getElementById('ttDept')?.value;
  const year     = document.getElementById('ttCourse')?.value;
  const semester = document.getElementById('ttSemester')?.value;
  const section  = document.getElementById('ttSection')?.value;
  const ttCont   = document.getElementById('ttContent');
  if (!ttCont || !dept || !year || !semester || !section) return;

  if (window._ttActiveTab === 'faculty') { renderFacultyTimetablePanel(); return; }
  if (window._ttActiveTab === 'manage') { renderTimetableManager(); return; }

  ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading...</p></div>';
  try {
    const [slots, rows] = await Promise.all([
      apiEx.periodSlots(),
      apiEx.studentTT(dept, year, section, semester)
    ]);

    // Build a map: DAY -> {period_no -> row}
    const ttMap = {};
    DAYS_ORDER.forEach(d => ttMap[d] = {});
    rows.forEach(r => {
      if (!ttMap[r.day_of_week]) ttMap[r.day_of_week] = {};
      ttMap[r.day_of_week][r.period_no] = r;
    });

    let html = `
      <div class="card">
        <div class="card-head">
          <h4><i class="fa fa-calendar-week"></i> ${dept} – Year ${year} – Semester ${semester} – Section ${section} Student Timetable</h4>
          <button class="btn-sm" onclick="exportTimetableCSV('${dept}','${year}','${section}','${semester}')"><i class="fa fa-download"></i> Export CSV</button>
        </div>
        <div class="table-scroll">
          <table class="data-tbl tt-grid">
            <thead><tr>
              <th style="min-width:80px">Day</th>
              ${slots.map(s=>'<th>P'+s.no+'<br><small style="font-weight:400;color:var(--text3)">'+s.start+'–'+s.end+'</small></th>').join('')}
            </tr></thead>
            <tbody>`;

    DAYS_ORDER.forEach(day => {
      html += `<tr><td><strong>${DAY_LABEL[day]||day}</strong></td>`;
      slots.forEach(s => {
        const cell = ttMap[day]?.[s.no];
        if (cell) {
          html += `<td class="tt-cell filled">
            <div class="ttc-subject">${cell.course_name}</div>
            <div class="ttc-code">${cell.course_code}</div>
            ${cell.faculty_name ? '<div class="ttc-fac"><i class="fa fa-user" style="font-size:.65rem"></i> '+cell.faculty_name+'</div>' : ''}
            ${cell.room ? '<div class="ttc-room"><i class="fa fa-door-open" style="font-size:.65rem"></i> '+cell.room+'</div>' : ''}
          </td>`;
        } else {
          html += `<td class="tt-cell empty"><span style="color:var(--text3);font-size:.75rem">—</span></td>`;
        }
      });
      html += '</tr>';
    });

    html += '</tbody></table></div></div>';
    ttCont.innerHTML = html;
  } catch(e) {
    ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>' + e.message + '</p></div>';
  }
}

async function renderFacultyTimetablePanel() {
  const ttCont = document.getElementById('ttContent');
  if (!ttCont) return;

  // Load all faculty for cascade population
  let facList = [];
  try { const data = await apiFetch('/api/faculty'); facList = data.faculty || data || []; } catch(_) {}

  // Build dept list from faculty data
  const deptSet = [...new Set(facList.map(f => f.dept).filter(Boolean))].sort();
  const deptOpts = '<option value="">— Select Department —</option>' +
    deptSet.map(d => `<option value="${d}">${d}</option>`).join('');

  // Store faculty list on window for cascade use
  window._facultyTTPanelFacList = facList;

  ttCont.innerHTML = `<div class="card">
    <div class="card-head"><h4><i class="fa fa-chalkboard-teacher"></i> Faculty Timetable</h4></div>
    <div class="modal-body">
      <div class="fg-3" style="margin-bottom:12px">
        <div class="fg">
          <label><i class="fa fa-building" style="color:var(--primary);margin-right:4px"></i> Step 1 — Department</label>
          <select class="sel" id="stpDept" onchange="stpOnDeptChange()">
            ${deptOpts}
          </select>
        </div>
        <div class="fg">
          <label><i class="fa fa-id-badge" style="color:var(--primary);margin-right:4px"></i> Step 2 — Faculty ID</label>
          <select class="sel" id="stpFac" onchange="stpOnFacChange()" disabled>
            <option value="">— Select Department first —</option>
          </select>
        </div>
        <div class="fg">
          <label><i class="fa fa-calendar-alt" style="color:var(--primary);margin-right:4px"></i> Step 3 — Semester</label>
          <select class="sel" id="stpSem" disabled>
            <option value="">— Select Faculty first —</option>
          </select>
        </div>
      </div>
      <button class="btn-primary" id="stpShowBtn" onclick="loadFacultyTimetable()" disabled style="margin-bottom:8px">
        <i class="fa fa-table"></i> Show Timetable
      </button>
    </div>
    <div id="facultyTTGrid"><div class="empty-msg"><i class="fa fa-user-clock"></i><p>Select Department → Faculty ID → Semester to view timetable.</p></div></div>
  </div>`;

  // If logged-in as faculty, auto-cascade to their dept/id
  if (APP.role === 'faculty' && _user.fac_id) {
    setTimeout(() => {
      const fac = facList.find(f => f.fac_id === _user.fac_id);
      if (fac && fac.dept) {
        const deptSel = document.getElementById('stpDept');
        if (deptSel) { deptSel.value = fac.dept; stpOnDeptChange(fac.fac_id); }
      }
    }, 120);
  }
}

function stpOnDeptChange(preselectFacId) {
  const dept = document.getElementById('stpDept')?.value;
  const facSel = document.getElementById('stpFac');
  const semSel = document.getElementById('stpSem');
  const btn    = document.getElementById('stpShowBtn');
  if (!facSel) return;

  // Reset downstream
  semSel.innerHTML = '<option value="">— Select Faculty first —</option>';
  semSel.disabled = true;
  btn.disabled = true;
  const grid = document.getElementById('facultyTTGrid');
  if (grid) grid.innerHTML = '<div class="empty-msg"><i class="fa fa-user-clock"></i><p>Select Department → Faculty ID → Semester to view timetable.</p></div>';

  if (!dept) { facSel.innerHTML = '<option value="">— Select Department first —</option>'; facSel.disabled = true; return; }

  const facList = window._facultyTTPanelFacList || [];
  const filtered = facList.filter(f => f.dept === dept);
  facSel.innerHTML = '<option value="">— Select Faculty —</option>' +
    filtered.map(f => `<option value="${f.fac_id}">${f.name} (${f.fac_id})</option>`).join('');
  facSel.disabled = false;

  if (preselectFacId) {
    facSel.value = preselectFacId;
    stpOnFacChange(true);
  }
}

async function stpOnFacChange(autoLoad) {
  const facId  = document.getElementById('stpFac')?.value;
  const semSel = document.getElementById('stpSem');
  const btn    = document.getElementById('stpShowBtn');
  if (!semSel) return;

  btn.disabled = true;
  const grid = document.getElementById('facultyTTGrid');
  if (grid) grid.innerHTML = '<div class="empty-msg"><i class="fa fa-user-clock"></i><p>Select a Semester to view timetable.</p></div>';

  if (!facId) {
    semSel.innerHTML = '<option value="">— Select Faculty first —</option>';
    semSel.disabled = true;
    return;
  }

  // Always show all 8 semesters — no API call needed
  semSel.innerHTML = '<option value="">— Select Semester —</option>'
    + [1,2,3,4,5,6,7,8].map(s => `<option value="${s}">Semester ${s}</option>`).join('');
  semSel.disabled = false;
  btn.disabled = false;
}

async function loadFacultyTimetable() {
  const dept  = document.getElementById('stpDept')?.value;
  const facId = document.getElementById('stpFac')?.value;
  const sem   = document.getElementById('stpSem')?.value;
  const grid  = document.getElementById('facultyTTGrid');
  if (!grid || !facId || !sem) {
    if (grid) grid.innerHTML = '<div class="empty-msg"><i class="fa fa-circle-info"></i><p>Please complete all three steps: Department → Faculty ID → Semester.</p></div>';
    return;
  }
  grid.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading timetable...</p></div>';
  try {
    const [slots, rows] = await Promise.all([apiEx.periodSlots(), apiEx.fullFacultyTT(facId, dept, sem)]);
    if (!rows.length) {
      grid.innerHTML = '<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>No timetable found for this faculty in Semester ' + sem + '. Use Manage tab to add slots.</p></div>';
      return;
    }

    // Get faculty name for header
    const facList = window._facultyTTPanelFacList || [];
    const fac = facList.find(f => f.fac_id === facId);
    const facName = fac ? fac.name : facId;

    const ttMap = {};
    DAYS_ORDER.forEach(d => ttMap[d] = {});
    rows.forEach(r => { if (!ttMap[r.day_of_week]) ttMap[r.day_of_week] = {}; ttMap[r.day_of_week][r.period_no] = r; });

    let html = `
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 16px;border-bottom:1px solid var(--border);margin-bottom:4px">
      <span style="font-weight:700;font-size:1rem"><i class="fa fa-chalkboard-teacher" style="color:var(--primary)"></i> ${facName}</span>
      <span style="font-size:.78rem;color:var(--text2)">${facId}</span>
      <span style="background:var(--primary);color:#fff;border-radius:20px;padding:2px 14px;font-size:.78rem;font-weight:600">
        <i class="fa fa-calendar-check"></i> Semester ${sem}
      </span>
      <span style="background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;border-radius:20px;padding:2px 12px;font-size:.76rem">
        ${dept || rows[0]?.dept || ''}
      </span>
      <span style="margin-left:auto;font-size:.75rem;color:var(--text3)">${rows.length} period(s) / week</span>
    </div>
    <div class="table-scroll"><table class="data-tbl tt-grid"><thead><tr>
      <th>Day</th>${slots.map(s=>'<th>P'+s.no+'<br><small style="font-weight:400;color:var(--text3)">'+s.start+'–'+s.end+'</small></th>').join('')}
    </tr></thead><tbody>`;

    DAYS_ORDER.forEach(day => {
      html += `<tr><td><strong>${DAY_LABEL[day]||day}</strong></td>`;
      slots.forEach(s => {
        const cell = ttMap[day]?.[s.no];
        if (cell) {
          html += `<td class="tt-cell filled">
            <div class="ttc-subject">${cell.course_name}</div>
            <div class="ttc-code">${cell.dept} Y${cell.year} · Sec ${cell.section}</div>
            ${cell.room?'<div class="ttc-room"><i class="fa fa-door-open" style="font-size:.65rem"></i> '+cell.room+'</div>':''}
          </td>`;
        } else {
          html += `<td class="tt-cell empty"><span style="color:var(--text3);font-size:.75rem">—</span></td>`;
        }
      });
      html += '</tr>';
    });
    html += '</tbody></table></div>';
    grid.innerHTML = html;
  } catch(e) {
    grid.innerHTML = '<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>' + e.message + '</p></div>';
  }
}

async function renderTimetableManager() {
  const ttCont = document.getElementById('ttContent');
  if (!ttCont) return;

  let facList = [];
  try { const data = await apiFetch('/api/faculty'); facList = data.faculty || data || []; } catch(_) {}

  ttCont.innerHTML = `
  <div class="card">
    <div class="card-head"><h4><i class="fa fa-pen-to-square"></i> Add / Edit Timetable Slot</h4></div>
    <div class="modal-body">
      <div class="fg-3">
        <div class="fg"><label>Department *</label>
          <select id="mgDept" class="sel" onchange="mgOnDeptYearChange()">
            <option value="">Select</option>
            ${DEPT_LIST.map(d=>'<option value="'+d.key+'">'+d.key+'</option>').join('')}
          </select></div>
        <div class="fg"><label>Year *</label>
          <select id="mgYear" class="sel" onchange="mgOnDeptYearChange()">
            <option value="">Select</option>
            ${[1,2,3,4].map(y=>'<option value="'+y+'">Year '+y+'</option>').join('')}
          </select></div>
        <div class="fg"><label>Semester *</label>
          <select id="mgSemester" class="sel" onchange="mgLoadCourses()">
            <option value="">Select Year first</option>
          </select></div>
      </div>
      <div class="fg-3">
        <div class="fg"><label>Section *</label>
          <select id="mgSection" class="sel">
            ${['A','B','C'].map(s=>'<option value="'+s+'">Section '+s+'</option>').join('')}
          </select></div>
        <div class="fg"><label>Day *</label>
          <select id="mgDay" class="sel" onchange="mgClashPreCheck()">
            ${DAYS_ORDER.map(d=>'<option value="'+d+'">'+DAY_LABEL[d]+'</option>').join('')}
          </select></div>
        <div class="fg"><label>Period *</label>
          <select id="mgPeriod" class="sel" onchange="mgClashPreCheck()">
            <option value="1">P1 – 08:55–09:45</option>
            <option value="2">P2 – 09:45–10:35</option>
            <option value="3">P3 – 10:55–11:45</option>
            <option value="4">P4 – 11:45–12:35</option>
            <option value="5">P5 – 13:35–14:25</option>
            <option value="6">P6 – 14:25–15:15</option>
            <option value="7">P7 – 15:15–16:05</option>
          </select></div>
      </div>
      <div class="fg-3">
        <div class="fg"><label>Course *</label>
          <select id="mgCourse" class="sel">
            <option value="">Select dept/year first</option>
          </select></div>
        <div class="fg"><label>Faculty</label>
          <select id="mgFaculty" class="sel" onchange="mgClashPreCheck()">
            <option value="">None</option>
            ${facList.map(f=>'<option value="'+f.fac_id+'" data-name="'+f.name+'">'+f.name+' ('+f.fac_id+')</option>').join('')}
          </select></div>
        <div class="fg"><label>Room</label>
          <input id="mgRoom" class="sel" placeholder="e.g. CSE-301" onchange="mgClashPreCheck()"/></div>
      </div>
      <div id="mgClashWarning" style="display:none;background:#fde8e8;color:#c0392b;border:1px solid #f3b9b9;border-radius:8px;padding:10px 14px;margin-top:8px;font-size:.82rem"></div>
      <div style="display:flex;gap:12px;margin-top:8px">
        <button class="btn-primary" onclick="saveTTSlot()"><i class="fa fa-save"></i> Save Slot</button>
        <button class="btn-secondary" onclick="renderTimetable()"><i class="fa fa-eye"></i> View Student TT</button>
      </div>
    </div>
  </div>`;
}

function mgOnDeptYearChange() {
  const year    = parseInt(document.getElementById('mgYear')?.value);
  const semSel  = document.getElementById('mgSemester');
  const courseSel = document.getElementById('mgCourse');
  if (!semSel) return;
  if (!year) {
    semSel.innerHTML = '<option value="">Select Year first</option>';
    if (courseSel) courseSel.innerHTML = '<option value="">Select dept/year/semester first</option>';
    return;
  }
  const sem1 = (year * 2) - 1;
  const sem2 = year * 2;
  semSel.innerHTML = '<option value="">Select Semester</option>'
    + [1,2,3,4,5,6,7,8].map(s => `<option value="${s}"${s===sem1||s===sem2?' selected':''}>Semester ${s}</option>`).join('');
  if (courseSel) courseSel.innerHTML = '<option value="">Select semester first</option>';
}

async function mgLoadCourses() {
  const dept = document.getElementById('mgDept')?.value;
  const year = document.getElementById('mgYear')?.value;
  const sel  = document.getElementById('mgCourse');
  if (!sel || !dept || !year) return;
  sel.innerHTML = '<option value="">Loading...</option>';
  try {
    const courses = await apiEx.coursesByYear(dept, year);
    sel.innerHTML = '<option value="">Select Course</option>'
      + courses.map(c => `<option value="${c.course_code}" data-name="${c.course_name}">[${c.course_type.toUpperCase()}] ${c.course_code} – ${c.course_name}</option>`).join('');
  } catch(e) { sel.innerHTML = '<option value="">Error loading courses</option>'; }
}

// ── Timetable Clash Pre-Check (NEW — additive) ──────────────────
let _mgLastClashConflicts = [];
async function mgClashPreCheck() {
  const banner = document.getElementById('mgClashWarning');
  if (!banner) return;
  const dept = document.getElementById('mgDept')?.value;
  const year = document.getElementById('mgYear')?.value;
  const semester = document.getElementById('mgSemester')?.value;
  const section = document.getElementById('mgSection')?.value;
  const day = document.getElementById('mgDay')?.value;
  const period = document.getElementById('mgPeriod')?.value;
  const facSel = document.getElementById('mgFaculty');
  const faculty_id = facSel?.value || '';
  const room = document.getElementById('mgRoom')?.value || '';

  if (!day || !period || (!faculty_id && !section)) { banner.style.display = 'none'; _mgLastClashConflicts = []; return; }

  try {
    const qs = new URLSearchParams();
    if (faculty_id) qs.set('faculty_id', faculty_id);
    if (section) qs.set('section', section);
    if (dept) qs.set('dept', dept);
    if (year) qs.set('year', year);
    if (semester) qs.set('semester', semester);
    qs.set('day_of_week', day);
    qs.set('period_no', period);
    if (room) qs.set('room', room);

    const res = await apiFetch('/api/timetable/clash-check?' + qs.toString());
    _mgLastClashConflicts = res.conflicts || [];
    if (res.has_conflict) {
      const names = _mgLastClashConflicts.map(c => `${c.reason.replace('_clash','')}: ${c.faculty_name || c.section || c.room || '—'} (${c.course_name || ''})`).join('; ');
      banner.style.display = 'block';
      banner.innerHTML = `<i class="fa fa-triangle-exclamation"></i> Clash detected — ${names}. You can still save, but please confirm.`;
    } else {
      banner.style.display = 'none';
    }
  } catch (e) {
    banner.style.display = 'none'; // fail-open — never block the form on a check error
  }
}

async function saveTTSlot() {
  const dept      = document.getElementById('mgDept')?.value;
  const year      = document.getElementById('mgYear')?.value;
  const semester  = document.getElementById('mgSemester')?.value;
  const section   = document.getElementById('mgSection')?.value;
  const day       = document.getElementById('mgDay')?.value;
  const period    = document.getElementById('mgPeriod')?.value;
  const courseSel = document.getElementById('mgCourse');
  const course_code = courseSel?.value;
  const course_name = courseSel?.selectedOptions[0]?.dataset.name || course_code;
  const facSel      = document.getElementById('mgFaculty');
  const faculty_id   = facSel?.value || '';
  const faculty_name = facSel?.selectedOptions[0]?.text?.split('(')[0]?.trim() || '';
  const room         = document.getElementById('mgRoom')?.value || '';

  if (!dept || !year || !semester || !section || !day || !period || !course_code) {
    toast('Fill all required fields (including Semester)', 'warn'); return;
  }

  // If the live pre-check already flagged a clash, confirm with the admin before forcing.
  let force = false;
  if (_mgLastClashConflicts.length) {
    const ok = confirm(`A scheduling clash was detected (${_mgLastClashConflicts.length} conflict(s)). Save anyway?`);
    if (!ok) return;
    force = true;
  }

  try {
    await apiEx.saveStudentTT({dept, year:+year, semester:+semester, section, day_of_week:day, period_no:+period,
      course_code, course_name, faculty_id, faculty_name, room}, force);
    toast('Slot saved!', 'success');
    const banner = document.getElementById('mgClashWarning');
    if (banner) banner.style.display = 'none';
    _mgLastClashConflicts = [];
  } catch(e) {
    // Backend caught a clash we hadn't pre-checked (e.g. race condition) — offer force-save.
    if (String(e.message).includes('Clash detected')) {
      const ok = confirm('A scheduling clash was detected on the server. Save anyway?');
      if (ok) {
        try {
          await apiEx.saveStudentTT({dept, year:+year, semester:+semester, section, day_of_week:day, period_no:+period,
            course_code, course_name, faculty_id, faculty_name, room}, true);
          toast('Slot saved!', 'success');
          return;
        } catch (e2) { toast('Save failed: ' + e2.message, 'error'); return; }
      }
      return;
    }
    toast('Save failed: ' + e.message, 'error');
  }
}

async function exportTimetableCSV(dept, year, section, semester) {
  try {
    const rows = await apiEx.fullStudentTT(dept, year, section, semester);
    if (!rows.length) { toast('No timetable data', 'warn'); return; }
    const header = 'Day,Period,Semester,Course Code,Course Name,Faculty,Room\n';
    const body = rows.map(r => [r.day_of_week,r.period_no,r.semester||semester,r.course_code,r.course_name,r.faculty_name||'',r.room||''].join(',')).join('\n');
    const blob = new Blob([header+body], {type:'text/csv'});
    const a = Object.assign(document.createElement('a'), {href:URL.createObjectURL(blob), download:`timetable_${dept}_Y${year}_Sem${semester}_Sec${section}.csv`});
    a.click(); toast('CSV exported!', 'success');
  } catch(e) { toast('Export failed: ' + e.message, 'error'); }
}

// ─────────────────────────────────────────────────────────────
// COURSES & ELECTIVES PAGE  (shown under Timetable or own page)
// ─────────────────────────────────────────────────────────────
async function renderCoursesPage() {
  // This renders inside the timetable page or can be its own page.
  const pg = document.getElementById('pg-courses');
  if (!pg) return;

  pg.innerHTML = `
  <div class="page-header">
    <div class="ph-left"><h2>Course Catalogue & Electives</h2>
      <p>Manage semester-wise courses and assign elective papers per section</p></div>
    <div class="ph-right">
      <select class="sel" id="cpDept" onchange="cpOnDeptChange()">
        <option value="">Department</option>
        ${DEPT_LIST.map(d=>'<option value="'+d.key+'">'+d.key+'</option>').join('')}
      </select>
      <select class="sel" id="cpYear" onchange="cpOnYearChange()">
        <option value="">Year</option>
        ${[1,2,3,4].map(y=>'<option value="'+y+'">Year '+y+'</option>').join('')}
      </select>
      <select class="sel" id="cpSemester">
        <option value="">Semester</option>
      </select>
      <button class="btn-primary" onclick="loadCourseCatalogue()"><i class="fa fa-search"></i> Load</button>
    </div>
  </div>
  <div id="cpContent"><div class="empty-msg"><i class="fa fa-book"></i><p>Select Department and Year to view courses</p></div></div>`;
}

async function cpOnDeptChange() {
  const semSel = document.getElementById('cpSemester');
  const year   = document.getElementById('cpYear')?.value;
  if (!semSel) return;
  semSel.innerHTML = '<option value="">All Semesters</option>';
  const dept = document.getElementById('cpDept')?.value;
  if (!dept) return;
  try {
    const sems = await apiEx.semesters(dept);
    sems.forEach(s => {
      const o = document.createElement('option');
      o.value = s.sem_number;
      o.textContent = 'Sem ' + s.sem_number + (s.is_current?' (Current)':'') + ' — Year '+s.year;
      if (s.is_current) o.selected = true;
      semSel.appendChild(o);
    });
  } catch(_) {}
}

function cpOnYearChange() {
  const year = document.getElementById('cpYear')?.value;
  const semSel = document.getElementById('cpSemester');
  if (!semSel || !year) return;
  semSel.innerHTML = '<option value="">All Semesters</option>';
  const y = +year;
  [y*2-1, y*2].forEach(s => {
    const o = document.createElement('option');
    o.value = s; o.textContent = 'Semester ' + s;
    semSel.appendChild(o);
  });
}

async function loadCourseCatalogue() {
  const dept = document.getElementById('cpDept')?.value;
  const year = document.getElementById('cpYear')?.value;
  const sem  = document.getElementById('cpSemester')?.value;
  const cont = document.getElementById('cpContent');
  if (!cont || !dept) { toast('Select a Department', 'warn'); return; }
  cont.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading courses...</p></div>';
  try {
    const courses = year ? await apiEx.coursesByYear(dept, year) : await apiEx.courses(dept, sem||null);
    const elPool  = await apiEx.electivePool(dept);
    const bySem   = {};
    courses.forEach(c => { if(!bySem[c.semester]) bySem[c.semester]=[]; bySem[c.semester].push(c); });

    let html = '';
    // Add course form
    html += `
    <div class="card" style="margin-bottom:16px">
      <div class="card-head"><h4><i class="fa fa-plus-circle"></i> Add / Override Course</h4></div>
      <div class="modal-body">
        <div class="fg-3">
          <div class="fg"><label>Code *</label><input id="nc_code" placeholder="e.g. CS_EL03" class="sel"/></div>
          <div class="fg"><label>Name *</label><input id="nc_name" placeholder="Course name" class="sel"/></div>
          <div class="fg"><label>Type</label>
            <select id="nc_type" class="sel">
              <option value="core">Core</option>
              <option value="elective" selected>Elective</option>
              <option value="lab">Lab</option>
            </select></div>
        </div>
        <div class="fg-3">
          <div class="fg"><label>Year</label><select id="nc_year" class="sel">
            ${[1,2,3,4].map(y=>'<option value="'+y+'"'+(year==y?' selected':'')+'>Year '+y+'</option>').join('')}
          </select></div>
          <div class="fg"><label>Semester</label><select id="nc_sem" class="sel">
            ${[1,2,3,4,5,6,7,8].map(s=>'<option value="'+s+'"'+(sem==s?' selected':'')+'>Sem '+s+'</option>').join('')}
          </select></div>
          <div class="fg"><label>Credits</label><input id="nc_credits" type="number" value="3" min="1" max="6" class="sel"/></div>
        </div>
        <button class="btn-primary" onclick="saveCourse('${dept}')"><i class="fa fa-save"></i> Save Course</button>
      </div>
    </div>`;

    // Elective pool section
    html += `
    <div class="card" style="margin-bottom:16px">
      <div class="card-head">
        <h4><i class="fa fa-star"></i> Elective Pool for ${dept}</h4>
        <span style="font-size:.8rem;color:var(--text3)">${elPool.length} available electives</span>
      </div>
      <div class="table-scroll"><table class="data-tbl">
        <thead><tr><th>Code</th><th>Elective Paper</th><th>Credits</th><th>Sem</th><th>Assign to Section</th></tr></thead>
        <tbody>
        ${elPool.map(e=>`
          <tr>
            <td><code>${e.course_code}</code></td>
            <td><strong>${e.course_name}</strong></td>
            <td>${e.credits}</td>
            <td>${e.semester}</td>
            <td>
              <select class="sel-sm" id="eSection_${e.course_code}">
                <option value="A">Section A</option>
                <option value="B">Section B</option>
                <option value="C">Section C</option>
              </select>
              <button class="btn-sm accent" onclick="assignElective('${dept}','${e.course_code}','${e.course_name}',${e.semester})">
                <i class="fa fa-check"></i> Assign
              </button>
            </td>
          </tr>`).join('')}
        </tbody>
      </table></div>
    </div>`;

    // Course catalogue by semester
    Object.keys(bySem).sort((a,b)=>+a-+b).forEach(semNo => {
      const list = bySem[semNo];
      html += `<div class="card" style="margin-bottom:12px">
        <div class="card-head"><h4><i class="fa fa-book-open"></i> Semester ${semNo} — ${list.length} courses</h4></div>
        <div class="table-scroll"><table class="data-tbl">
          <thead><tr><th>Code</th><th>Course Name</th><th>Type</th><th>Credits</th></tr></thead>
          <tbody>
          ${list.map(c=>`
            <tr>
              <td><code>${c.course_code}</code></td>
              <td>${c.course_name}</td>
              <td><span class="badge ${c.course_type==='core'?'b-g':c.course_type==='elective'?'b-amber':'b-lav'}">${c.course_type}</span></td>
              <td>${c.credits}</td>
            </tr>`).join('')}
          </tbody>
        </table></div>
      </div>`;
    });

    if (!html.includes('tbody')) html += '<div class="empty-msg"><i class="fa fa-book"></i><p>No courses found. Add one above.</p></div>';
    cont.innerHTML = html;
  } catch(e) {
    cont.innerHTML = '<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>' + e.message + '</p></div>';
  }
}

async function saveCourse(dept) {
  const code    = document.getElementById('nc_code')?.value.trim().toUpperCase();
  const name    = document.getElementById('nc_name')?.value.trim();
  const type    = document.getElementById('nc_type')?.value;
  const year    = +document.getElementById('nc_year')?.value;
  const sem     = +document.getElementById('nc_sem')?.value;
  const credits = +document.getElementById('nc_credits')?.value;
  if (!code || !name) { toast('Code and Name are required', 'warn'); return; }
  try {
    await apiEx.saveCourse({dept, year, semester:sem, course_code:code, course_name:name, course_type:type, credits});
    toast('Course saved: ' + code, 'success');
    loadCourseCatalogue();
  } catch(e) { toast('Save failed: ' + e.message, 'error'); }
}

async function assignElective(dept, code, name, semester) {
  const section = document.getElementById('eSection_'+code)?.value || 'A';
  const year    = Math.ceil(semester / 2);
  try {
    await apiEx.assignElective({dept, year, semester, section, course_code:code, student_id:''});
    toast(`Elective "${name}" assigned to ${dept} Section ${section} Sem ${semester}`, 'success');
  } catch(e) { toast('Assign failed: ' + e.message, 'error'); }
}


// ─────────────────────────────────────────────────────────────
// STUDENT ENROLLMENT  — 15-field, matches terminal enroll.py
// ─────────────────────────────────────────────────────────────

// Legacy enroll constants (kept for backward compat with any residual references)
const GENDER_OPTIONS   = ['Male','Female','Other'];
const YEAR_OPTIONS     = ['1st Year','2nd Year','3rd Year','4th Year'];
const COURSE_OPTIONS   = ['B.E','B.Tech','B.Sc','M.E','M.Tech','M.Sc','MBA','MCA','Diploma'];
const SECTION_OPTIONS  = ['A','B','C','D'];

// openEnrollModal — redirects to new unified Enroll hub (defined earlier in this file)
// The full enrollment UI is now inside renderEnrollPage() / openEnrollPanel()


// ─────────────────────────────────────────────────────────────
// NAV INJECTION — add Courses page to admin/hod nav
// ─────────────────────────────────────────────────────────────
const _origBuildSideNav = buildSideNav;
buildSideNav = function() {
  _origBuildSideNav();
  // Inject Courses link if not already in nav config
  const nav = document.getElementById('sbNav');
  if (!nav) return;
  if (nav.querySelector('[data-page="courses"]')) return;
  if (APP.role !== 'admin' && APP.role !== 'hod') return;
  // Find timetable link and insert after it
  const ttLink = nav.querySelector('[data-page="timetable"]');
  const a = document.createElement('a');
  a.className = 'nav-link'; a.dataset.page = 'courses';
  a.onclick = () => { showPage('courses'); };
  a.innerHTML = '<i class="fa fa-book-open"></i><span>Courses & Electives</span>';
  if (ttLink) ttLink.parentElement.insertBefore(a, ttLink.nextSibling);
  else nav.appendChild(a);
};

// ─────────────────────────────────────────────────────────────
// NAV RESTRICTION — hide "Student Timetable", "Leave Approvals" and
// "OD Approvals" links for faculty who are NOT a Class In-Charge.
// Subject-faculty-only faculty (e.g. Ajitha) never see them; Class
// In-Charge faculty (e.g. Suganya) see them and can manage their
// class's student timetable / leave / OD requests.
// ─────────────────────────────────────────────────────────────
const _origBuildSideNav2 = buildSideNav;
buildSideNav = function() {
  _origBuildSideNav2();
  if (APP.role !== 'faculty' && APP.role !== 'teacher') return;
  const nav = document.getElementById('sbNav');
  if (!nav) return;
  const inchargeOnlyPages = ['timetable', 'fac-leave-approvals', 'fac-od-approvals'];
  const getLinks = () => inchargeOnlyPages
    .map(p => document.querySelector('#sbNav [data-page="' + p + '"]'))
    .filter(Boolean);
  // Show/hide immediately based on any cached value, then re-verify with server.
  if (APP._isClassIncharge === false) getLinks().forEach(l => l.style.display = 'none');
  apiFetch('/api/faculty/my-class').then(info => {
    APP._isClassIncharge = !!(info && info.is_class_incharge);
    getLinks().forEach(l => l.style.display = APP._isClassIncharge ? '' : 'none');
    // If the user is currently on a Class In-Charge-only page but lost
    // access (or never had it), bounce them back to their dashboard.
    if (!APP._isClassIncharge && inchargeOnlyPages.includes(APP.currentPage)) {
      showPage('fac-dashboard');
    }
  }).catch(() => { /* fail closed: keep links hidden until confirmed */ });
};

// Ensure showPage handles 'courses'
const _origShowPage = showPage;
showPage = function(pid) {
  if (pid === 'courses') {
    // ensure pg-courses exists
    let pg = document.getElementById('pg-courses');
    if (!pg) {
      pg = document.createElement('div');
      pg.id = 'pg-courses';
      pg.className = 'page dn';
      document.getElementById('pageArea')?.appendChild(pg);
    }
    document.querySelectorAll('.page').forEach(p => p.classList.add('dn'));
    document.querySelectorAll('.nav-link').forEach(a => a.classList.remove('active'));
    pg.classList.remove('dn');
    document.querySelector('[data-page="courses"]')?.classList.add('active');
    setEl('tbPageTitle', 'Courses & Electives');
    APP.currentPage = 'courses';
    if(_token) sessionStorage.setItem("_lastPage", 'courses');
    closeSidebar();
    renderCoursesPage();
    return;
  }
  _origShowPage(pid);
};

async function viewStudentDetail(sid) {
  try {
    let s = {};
    try { s = await apiFetch('/api/students/' + sid); } catch(e) {}
    // Merge any ext data if available
    try {
      const ext = await (typeof apiEx!=='undefined' ? apiEx.studentExt(sid).catch(()=>({})) : Promise.resolve({}));
      s = {...s, ...ext};
    } catch(e2) {}

    document.getElementById('infoModalTitle').textContent = (s.name || sid) + ' — Details';
    document.getElementById('infoModalBody').innerHTML = `
    <style>
      .sd-section{font-size:.75rem;font-weight:700;letter-spacing:.06em;color:var(--mint-d);text-transform:uppercase;margin:14px 0 8px;padding-bottom:3px;border-bottom:1px solid var(--border);}
      .sd-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
      .sd-grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;}
      .sd-field label{font-size:.74rem;font-weight:600;color:var(--text3);display:block;margin-bottom:2px;}
      .sd-field input{border:1.5px solid var(--border);border-radius:7px;padding:6px 10px;font-size:.84rem;background:var(--card-bg2,#f7f9fb);color:var(--text1);width:100%;box-sizing:border-box;}
    </style>

    <p class="sd-section"><i class="fa fa-id-card"></i> Identity</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Student ID</label><input value="${s.student_id||sid}" readonly/></div>
      <div class="sd-field"><label>Register Number</label><input value="${s.register_number||'—'}" readonly/></div>
    </div>
    <div class="sd-grid" style="margin-top:8px">
      <div class="sd-field"><label>Roll Number</label><input value="${s.roll_number||'—'}" readonly/></div>
      <div class="sd-field"><label>Full Name</label><input value="${s.name||'—'}" readonly/></div>
    </div>
    <div class="sd-grid" style="margin-top:8px">
      <div class="sd-field"><label>First Name</label><input value="${s.first_name||'—'}" readonly/></div>
      <div class="sd-field"><label>Last Name</label><input value="${s.last_name||'—'}" readonly/></div>
    </div>
    <div class="sd-grid" style="margin-top:8px">
      <div class="sd-field"><label>Gender</label><input value="${s.gender||'—'}" readonly/></div>
      <div class="sd-field"><label>Date of Birth</label><input value="${s.date_of_birth||'—'}" readonly/></div>
    </div>

    <p class="sd-section"><i class="fa fa-building-columns"></i> Academic</p>
    <div class="sd-grid-3">
      <div class="sd-field"><label>Department</label><input value="${s.department||s.dept||'—'}" readonly/></div>
      <div class="sd-field"><label>Course</label><input value="${s.course||'—'}" readonly/></div>
      <div class="sd-field"><label>Year</label><input value="${s.year||'—'}" readonly/></div>
    </div>
    <div class="sd-grid" style="margin-top:8px">
      <div class="sd-field"><label>Section</label><input value="${s.section||'—'}" readonly/></div>
      <div class="sd-field"><label>Status</label><input value="${s.status||'Active'}" readonly/></div>
    </div>

    <p class="sd-section"><i class="fa fa-envelope"></i> Contact</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Student Email</label><input value="${s.student_email||'—'}" readonly/></div>
      <div class="sd-field"><label>Parent Email</label><input value="${s.parent_email||'—'}" readonly/></div>
    </div>
    <div class="sd-grid" style="margin-top:8px">
      <div class="sd-field"><label>Student Mobile</label><input value="${s.student_mobile||s.mobile||'—'}" readonly/></div>
      <div class="sd-field"><label>Parent Mobile</label><input value="${s.parent_mobile||'—'}" readonly/></div>
    </div>
    ${s.twin_of ? `<div class="sd-grid" style="margin-top:8px"><div class="sd-field"><label>Twin of</label><input value="${s.twin_of}" readonly/></div></div>` : ''}

    <p class="sd-section"><i class="fa fa-clock"></i> System</p>
    <div class="sd-grid">
      <div class="sd-field"><label>Enrolled On</label><input value="${(s.enrolled_on||'—').slice(0,10)}" readonly/></div>
      <div class="sd-field"><label>Active</label><input value="${s.active===1||s.active===true?'Yes':'No'}" readonly/></div>
    </div>`;
    document.getElementById('infoModal').classList.remove('dn');
  } catch(e) { toast('Could not load details: ' + e.message, 'error'); }
}

// ─────────────────────────────────────────────────────────────
// CSS helpers  (timetable grid cells)
// ─────────────────────────────────────────────────────────────
(function injectTTStyles() {
  if (document.getElementById('tt-extra-styles')) return;
  const s = document.createElement('style');
  s.id = 'tt-extra-styles';
  s.textContent = `
    .tt-grid th, .tt-grid td { white-space:normal; min-width:110px; vertical-align:top; }
    .tt-cell { padding:6px 8px !important; }
    .tt-cell.filled { background:var(--card-bg2,#f5f9ff); border-radius:6px; }
    .tt-cell.empty  { opacity:.4; }
    .ttc-subject { font-weight:600; font-size:.82rem; color:var(--text1); }
    .ttc-code    { font-size:.72rem; color:var(--mint-d); font-family:var(--mono); margin-top:2px; }
    .ttc-fac,.ttc-room { font-size:.7rem; color:var(--text3); margin-top:2px; }
    .tab-strip { display:flex; gap:8px; margin-bottom:12px; }
    .tab-strip .tab-b { padding:7px 16px; border-radius:8px; border:1.5px solid var(--border); background:var(--card-bg); color:var(--text2); cursor:pointer; font-size:.85rem; }
    .tab-strip .tab-b.active { background:var(--mint-d); color:#fff; border-color:var(--mint-d); }
  `;
  document.head.appendChild(s);
})();

// =============================================================
// ENHANCED TIMETABLE — Full Seed Data Integration (all depts/sems/50 faculty)
// =============================================================

// Extended API endpoints for seeded timetable data
Object.assign(apiEx, {
  fullStudentTT:  (dept,year,sec,semester) => apiFetch(`/api/timetable/full?dept=${encodeURIComponent(dept)}&year=${year}&section=${sec}${semester?'&semester='+semester:''}`),
  fullFacultyTT:    (facId,dept,semester) => apiFetch(`/api/timetable/faculty/full?faculty_id=${encodeURIComponent(facId)}${dept?'&dept='+encodeURIComponent(dept):''}${semester?'&semester='+semester:''}`),
  allFaculty:     ()              => apiFetch('/api/faculty/all'),
  seedTimetable:  (force)         => apiFetch('/api/admin/seed-timetable', {method:'POST', body:JSON.stringify({force:!!force})}),
  coursesByYear:  (dept,year)     => apiFetch(`/api/courses/by-year?dept=${encodeURIComponent(dept)}&year=${year}`),
});

const ALL_DEPTS = [
  {key:'CSE',  name:'CSE – Computer Science & Engineering'},
  {key:'AIDS', name:'AIDS – Artificial Intelligence & Data Science'},
  {key:'CSBS', name:'CSBS – CS & Business Systems'},
  {key:'ECE',  name:'ECE – Electronics & Communication'},
  {key:'EEE',  name:'EEE – Electrical & Electronics'},
  {key:'MECH', name:'MECH – Mechanical Engineering'},
  {key:'CIVIL',name:'CIVIL – Civil Engineering'},
  {key:'BME',  name:'BME – Biomedical Engineering'},
];

const PERIOD_TIMES = [
  {no:1,label:'P1',time:'9:00–10:00'},
  {no:2,label:'P2',time:'10:00–11:00'},
  {no:3,label:'P3',time:'11:15–12:15'},
  {no:4,label:'P4',time:'12:15–1:15'},
  {no:5,label:'P5',time:'2:00–3:00'},
  {no:6,label:'P6',time:'3:00–4:00'},
  {no:7,label:'P7',time:'4:00–5:00'},
];
const BREAK_AFTER = 2;   // break after period 2
const LUNCH_AFTER = 4;   // lunch after period 4
const ALL_DAYS = ['MON','TUE','WED','THU','FRI'];
const DAY_FULL = {MON:'Monday',TUE:'Tuesday',WED:'Wednesday',THU:'Thursday',FRI:'Friday'};

// Subject type color coding
function _ttCellClass(row) {
  if (!row) return 'tt-cell empty';
  if (row.is_lab) return 'tt-cell filled tt-lab';
  const code = (row.course_code || '').toLowerCase();
  if (code.startsWith('pe') || code.startsWith('oe')) return 'tt-cell filled tt-elec';
  if (code.includes('project') || code.includes('811') || code.includes('711') || code.includes('713')) return 'tt-cell filled tt-proj';
  return 'tt-cell filled tt-theory';
}

// Inject enhanced styles
(function injectEnhancedTTStyles() {
  if (document.getElementById('tt-enhanced-styles')) return;
  const s = document.createElement('style');
  s.id = 'tt-enhanced-styles';
  s.textContent = `
    .tt-table { width:100%; border-collapse:collapse; font-size:.82rem; }
    .tt-table th { background:var(--card-bg2,#f0f4ff); padding:8px 6px; text-align:center;
      border:1px solid var(--border); font-weight:600; font-size:.75rem; color:var(--text2); white-space:nowrap; }
    .tt-table td { border:1px solid var(--border); padding:0; vertical-align:top; min-width:100px; }
    .tt-table .day-col { font-weight:600; font-size:.78rem; color:var(--text1); padding:8px 10px;
      background:var(--card-bg2,#f5f5ff); text-align:center; white-space:nowrap; min-width:70px; }
    .tt-table .brk-col { background:repeating-linear-gradient(45deg,#f9f9f9,#f9f9f9 4px,#fff 4px,#fff 8px);
      color:var(--text3); font-size:.68rem; text-align:center; padding:4px 2px; min-width:48px; }
    .tt-cell { padding:6px 7px; min-height:58px; }
    .tt-cell.empty { opacity:.3; text-align:center; padding:16px 4px; color:var(--text3); }
    .tt-theory { background:#eef6ff; }
    .tt-lab    { background:#edfff4; border-left:3px solid #22c55e; }
    .tt-elec   { background:#fefce8; border-left:3px solid #eab308; }
    .tt-proj   { background:#fff0f0; border-left:3px solid #ef4444; }
    .ttc-name  { font-weight:600; font-size:.78rem; color:var(--text1); line-height:1.3; }
    .ttc-code  { font-size:.68rem; color:#555; font-family:monospace; margin-top:2px; }
    .ttc-fac   { font-size:.67rem; color:#777; margin-top:3px; }
    .ttc-room  { font-size:.65rem; color:#999; margin-top:1px; }
    .tt-legend { display:flex; gap:12px; flex-wrap:wrap; margin:10px 0; font-size:.75rem; }
    .tt-leg-item{ display:flex; align-items:center; gap:5px; }
    .tt-leg-dot { width:12px; height:12px; border-radius:2px; }
    .tt-sem-badge { display:inline-block; padding:2px 10px; border-radius:12px; font-size:.72rem;
      font-weight:600; background:var(--mint-d,#0ea5e9); color:#fff; margin-left:8px; }
    .tt-filter-bar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:14px; }
    .tt-filter-bar select, .tt-filter-bar button { font-size:.82rem; padding:6px 10px; }
    .tt-faculty-badge { display:inline-flex; align-items:center; gap:6px; padding:4px 12px;
      border-radius:20px; font-size:.78rem; font-weight:500; }
    .tt-faculty-m { background:#dbeafe; color:#1d4ed8; }
    .tt-faculty-f { background:#fce7f3; color:#be185d; }
    .tt-print-btn { float:right; }
    @media print {
      .tt-filter-bar, .tab-strip, .tt-legend, .tt-print-btn { display:none !important; }
      .tt-table { font-size:.7rem; }
    }
  `;
  document.head.appendChild(s);
})();

// ── Student Timetable (full seeded data) ─────────────────────
async function renderFullStudentTimetable() {
  const dept     = document.getElementById('ttDept')?.value;
  const year     = document.getElementById('ttCourse')?.value;
  const semester = document.getElementById('ttSemester')?.value;
  const section  = document.getElementById('ttSection')?.value;
  const ttCont   = document.getElementById('ttContent');
  if (!ttCont) return;

  if (!dept || !year || !semester || !section) {
    ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>Select Department, Year, Semester and Section to view timetable</p></div>';
    return;
  }
  ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading timetable...</p></div>';

  try {
    const rows = await apiEx.fullStudentTT(dept, year, section, semester);

    // Build map: DAY -> periodNo -> row
    const ttMap = {};
    ALL_DAYS.forEach(d => ttMap[d] = {});
    rows.forEach(r => {
      const d = (r.day_of_week||'').toUpperCase();
      if (!ttMap[d]) ttMap[d] = {};
      ttMap[d][r.period_no] = r;
    });

    let html = `
    <div class="card">
      <div class="card-head">
        <h4><i class="fa fa-calendar-week"></i> ${dept} — Year ${year}
          <span class="tt-sem-badge">Sem ${semester}</span>
          — Section ${section}
        </h4>
        <button class="btn-sm tt-print-btn" onclick="window.print()"><i class="fa fa-print"></i> Print</button>
      </div>
      <div class="tt-legend">
        <div class="tt-leg-item"><div class="tt-leg-dot" style="background:#eef6ff;border:1px solid #3b82f6"></div> Theory</div>
        <div class="tt-leg-item"><div class="tt-leg-dot" style="background:#edfff4;border-left:3px solid #22c55e"></div> Lab</div>
        <div class="tt-leg-item"><div class="tt-leg-dot" style="background:#fefce8;border-left:3px solid #eab308"></div> Elective</div>
        <div class="tt-leg-item"><div class="tt-leg-dot" style="background:#fff0f0;border-left:3px solid #ef4444"></div> Project</div>
      </div>
      <div class="table-scroll">
        <table class="tt-table"><thead><tr>
          <th>Day</th>`;

    PERIOD_TIMES.forEach((p, i) => {
      html += `<th>${p.label}<br><small style="font-weight:400">${p.time}</small></th>`;
      if (i === BREAK_AFTER - 1) html += `<th class="brk-col">BREAK</th>`;
      if (i === LUNCH_AFTER - 1) html += `<th class="brk-col">LUNCH</th>`;
    });
    html += `</tr></thead><tbody>`;

    ALL_DAYS.forEach(day => {
      html += `<tr><td class="day-col">${DAY_FULL[day]||day}</td>`;
      PERIOD_TIMES.forEach((p, i) => {
        const cell = ttMap[day]?.[p.no];
        if (cell) {
          html += `<td><div class="${_ttCellClass(cell)}">
            <div class="ttc-name">${cell.course_name}</div>
            <div class="ttc-code">${cell.course_code}</div>
            ${cell.faculty_name ? `<div class="ttc-fac"><i class="fa fa-user" style="font-size:.6rem"></i> ${cell.faculty_name}</div>` : ''}
            ${cell.room ? `<div class="ttc-room"><i class="fa fa-door-open" style="font-size:.6rem"></i> ${cell.room}</div>` : ''}
          </div></td>`;
        } else {
          html += `<td><div class="tt-cell empty">—</div></td>`;
        }
        if (i === BREAK_AFTER - 1) html += `<td class="brk-col" style="font-size:.65rem;color:#999">☕<br>Break</td>`;
        if (i === LUNCH_AFTER - 1) html += `<td class="brk-col" style="font-size:.65rem;color:#999">🍱<br>Lunch</td>`;
      });
      html += `</tr>`;
    });

    html += `</tbody></table></div></div>`;

    // Subject-Faculty mapping table
    const subjectMap = {};
    rows.forEach(r => {
      if (!subjectMap[r.course_code]) subjectMap[r.course_code] = r;
    });
    const subjects = Object.values(subjectMap);

    html += `<div class="card" style="margin-top:12px">
      <div class="card-head"><h4><i class="fa fa-list"></i> Subject & Faculty Assignment — ${dept} Y${year} Sec ${section}</h4></div>
      <div class="table-scroll"><table class="data-tbl"><thead>
        <tr><th>#</th><th>Code</th><th>Subject Name</th><th>Type</th><th>Faculty ID</th><th>Faculty Name</th><th>Room</th></tr>
      </thead><tbody>`;

    subjects.forEach((s, idx) => {
      const typeLabel = s.is_lab ? 'Lab' : (s.course_code.startsWith('PE')||s.course_code.startsWith('OE')) ? 'Elective' : 'Theory';
      const typeBadge = s.is_lab ? 'badge-success' : (typeLabel==='Elective') ? 'badge-warn' : 'badge-info';
      html += `<tr>
        <td>${idx+1}</td>
        <td style="font-family:monospace;font-size:.78rem">${s.course_code}</td>
        <td style="text-align:left">${s.course_name}</td>
        <td><span class="badge ${typeBadge}">${typeLabel}</span></td>
        <td style="font-family:monospace">${s.faculty_id||'—'}</td>
        <td style="text-align:left">${s.faculty_name||'—'}</td>
        <td>${s.room||'—'}</td>
      </tr>`;
    });
    html += `</tbody></table></div></div>`;

    ttCont.innerHTML = html;
  } catch(e) {
    // fallback to original
    return renderTimetable();
  }
}

// ── Faculty Timetable (full seeded data) ───────────────────────
async function renderFullFacultyTimetable() {
  const ttCont = document.getElementById('ttContent');
  if (!ttCont) return;

  ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading faculty list...</p></div>';

  let facList = [];
  let fetchErr = null;
  try {
    const res = await apiFetch('/api/faculty/all');
    facList = Array.isArray(res) ? res : (res.faculty || res || []);
  } catch(e1) { fetchErr = e1.message; }
  if (!facList.length) {
    try {
      const res2 = await apiFetch('/api/faculty');
      facList = Array.isArray(res2) ? res2 : (res2.faculty || res2 || []);
    } catch(e2) { fetchErr = e2.message; }
  }

  // Store for cascade use
  window._fullFacultyFacList = facList;

  const deptSet = [...new Set(facList.map(f => f.dept||'Other').filter(Boolean))].sort();
  const deptOpts = '<option value="">— Select Department —</option>' +
    deptSet.map(d => `<option value="${d}">${d}</option>`).join('');

  const seedNote = !facList.length
    ? `<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;padding:10px 14px;margin-bottom:10px;font-size:.83rem;color:#856404">
        <i class="fa fa-triangle-exclamation"></i> No faculty found. Click <b>Seed DB</b> to populate sample data, then refresh.
        ${fetchErr ? `<br><small style="color:#999">Error: ${fetchErr}</small>` : ''}
       </div>` : '';

  ttCont.innerHTML = `
  <div class="card">
    <div class="card-head">
      <h4><i class="fa fa-chalkboard-teacher"></i> Faculty Timetable</h4>
      <span style="font-size:.78rem;color:var(--text3)">${facList.length} faculty loaded</span>
    </div>
    ${seedNote}
    <div class="modal-body">
      <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-bottom:4px">
        <div style="display:flex;flex-direction:column;gap:4px;min-width:170px">
          <label style="font-size:.78rem;font-weight:600;color:var(--text2)">
            <i class="fa fa-building" style="color:var(--primary)"></i> Step 1 — Department
          </label>
          <select id="fstDept" class="sel" onchange="fstOnDeptChange()" style="padding:7px 10px">
            ${deptOpts}
          </select>
        </div>
        <div style="display:flex;flex-direction:column;gap:4px;min-width:260px">
          <label style="font-size:.78rem;font-weight:600;color:var(--text2)">
            <i class="fa fa-id-badge" style="color:var(--primary)"></i> Step 2 — Faculty ID
          </label>
          <select id="fstFac" class="sel" onchange="fstOnFacChange()" disabled style="padding:7px 10px">
            <option value="">— Select Department first —</option>
          </select>
        </div>
        <div style="display:flex;flex-direction:column;gap:4px;min-width:170px">
          <label style="font-size:.78rem;font-weight:600;color:var(--text2)">
            <i class="fa fa-calendar-alt" style="color:var(--primary)"></i> Step 3 — Semester
          </label>
          <select id="fstSem" class="sel" disabled style="padding:7px 10px">
            <option value="">— Select Faculty first —</option>
          </select>
        </div>
        <button id="fstShowBtn" class="btn btn-primary btn-sm" onclick="loadFullFacultyTimetable()" disabled
          style="padding:8px 18px;font-size:.85rem;height:38px;align-self:flex-end">
          <i class="fa fa-table"></i> Show Timetable
        </button>
      </div>
    </div>
    <div id="facultyTTGrid"><div class="empty-msg"><i class="fa fa-user-clock"></i><p>Select Department → Faculty ID → Semester to view timetable.</p></div></div>
  </div>`;

  // Auto-cascade for faculty login
  if (APP.role === 'faculty' && _user.fac_id) {
    setTimeout(() => {
      const fac = facList.find(f => f.fac_id === _user.fac_id);
      if (fac && fac.dept) {
        const d = document.getElementById('fstDept');
        if (d) { d.value = fac.dept; fstOnDeptChange(fac.fac_id); }
      }
    }, 120);
  }
}

function fstOnDeptChange(preselectFacId) {
  const dept   = document.getElementById('fstDept')?.value;
  const facSel = document.getElementById('fstFac');
  const semSel = document.getElementById('fstSem');
  const btn    = document.getElementById('fstShowBtn');
  if (!facSel) return;

  semSel.innerHTML = '<option value="">— Select Faculty first —</option>';
  semSel.disabled = true;
  btn.disabled = true;
  const grid = document.getElementById('facultyTTGrid');
  if (grid) grid.innerHTML = '<div class="empty-msg"><i class="fa fa-user-clock"></i><p>Select Department → Faculty ID → Semester to view timetable.</p></div>';

  if (!dept) { facSel.innerHTML = '<option value="">— Select Department first —</option>'; facSel.disabled = true; return; }

  const facList = window._fullFacultyFacList || [];
  const filtered = facList.filter(f => (f.dept||'Other') === dept);
  const badge = f => f.gender === 'F' ? '♀' : '♂';
  facSel.innerHTML = '<option value="">— Select Faculty —</option>' +
    filtered.map(f => `<option value="${f.fac_id}" data-gender="${f.gender||''}">${badge(f)} ${f.name} (${f.fac_id})</option>`).join('');
  facSel.disabled = false;

  if (preselectFacId) { facSel.value = preselectFacId; fstOnFacChange(true); }
}

async function fstOnFacChange(autoLoad) {
  const facId  = document.getElementById('fstFac')?.value;
  const semSel = document.getElementById('fstSem');
  const btn    = document.getElementById('fstShowBtn');
  if (!semSel) return;

  btn.disabled = true;
  const grid = document.getElementById('facultyTTGrid');
  if (grid) grid.innerHTML = '<div class="empty-msg"><i class="fa fa-user-clock"></i><p>Select a Semester to view the timetable.</p></div>';

  if (!facId) {
    semSel.innerHTML = '<option value="">— Select Faculty first —</option>';
    semSel.disabled = true;
    return;
  }

  // Always show all 8 semesters — no API call needed
  semSel.innerHTML = '<option value="">— Select Semester —</option>'
    + [1,2,3,4,5,6,7,8].map(s => `<option value="${s}">Semester ${s}</option>`).join('');
  semSel.disabled = false;
  btn.disabled = false;
}

async function loadFullFacultyTimetable() {
  const dept  = document.getElementById('fstDept')?.value;
  const facId = document.getElementById('fstFac')?.value;
  const sem   = parseInt(document.getElementById('fstSem')?.value, 10);
  const grid  = document.getElementById('facultyTTGrid');
  if (!grid) return;
  if (!facId || !sem) {
    grid.innerHTML = '<div class="empty-msg"><i class="fa fa-circle-info"></i><p>Please complete all steps: Department → Faculty ID → Semester.</p></div>';
    return;
  }

  // Get faculty meta
  const facSel = document.getElementById('fstFac');
  const facName = facSel?.selectedOptions[0]?.textContent?.replace(/[♀♂]/,'').trim() || facId;
  const gender  = facSel?.selectedOptions[0]?.dataset?.gender || 'M';

  grid.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading timetable...</p></div>';

  try {
    const rows = await apiEx.fullFacultyTT(facId, dept, sem);

    if (!rows || !rows.length) {
      grid.innerHTML = `<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>No timetable assigned for <b>${facName}</b> in <b>Semester ${sem}</b>. Use the Manage tab to add slots.</p></div>`;
      return;
    }

    const ttMap = {};
    ALL_DAYS.forEach(d => ttMap[d] = {});
    rows.forEach(r => {
      const d = (r.day_of_week||'').toUpperCase();
      if (!ttMap[d]) ttMap[d] = {};
      ttMap[d][r.period_no] = r;
    });

    const totalSlots = rows.length;
    const labSlots   = rows.filter(r=>r.is_lab).length;
    const depts      = [...new Set(rows.map(r=>r.dept))].join(', ');
    const gBadge     = gender === 'F'
      ? `<span class="tt-faculty-badge tt-faculty-f">♀ Female</span>`
      : `<span class="tt-faculty-badge tt-faculty-m">♂ Male</span>`;

    let html = `
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:10px 16px;border-bottom:1px solid var(--border);margin-bottom:8px">
      ${gBadge}
      <span style="font-weight:700;font-size:.95rem">${facName}</span>
      <span style="font-size:.78rem;color:var(--text2)">${facId}</span>
      <span style="background:var(--primary);color:#fff;border-radius:20px;padding:2px 14px;font-size:.78rem;font-weight:700">
        <i class="fa fa-calendar-check"></i> Semester ${sem}
      </span>
      <span style="background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;border-radius:20px;padding:2px 12px;font-size:.76rem">${depts}</span>
      <span style="margin-left:auto;font-size:.75rem;color:var(--text3)">
        ${totalSlots} period(s)/week &nbsp;·&nbsp; Theory: ${totalSlots-labSlots} &nbsp;·&nbsp; Lab: ${labSlots}
      </span>
    </div>
    <div class="table-scroll"><table class="tt-table"><thead><tr><th>Day</th>`;

    PERIOD_TIMES.forEach((p, i) => {
      html += `<th>${p.label}<br><small style="font-weight:400">${p.time}</small></th>`;
      if (i === BREAK_AFTER - 1) html += `<th class="brk-col">BREAK</th>`;
      if (i === LUNCH_AFTER - 1) html += `<th class="brk-col">LUNCH</th>`;
    });
    html += `</tr></thead><tbody>`;

    ALL_DAYS.forEach(day => {
      html += `<tr><td class="day-col">${DAY_FULL[day]||day}</td>`;
      PERIOD_TIMES.forEach((p, i) => {
        const cell = ttMap[day]?.[p.no];
        if (cell) {
          html += `<td><div class="${_ttCellClass(cell)}">
            <div class="ttc-name">${cell.course_name}</div>
            <div class="ttc-code">${cell.dept} · Y${cell.year} Sec ${cell.section}</div>
            <div class="ttc-room">${cell.room||''}</div>
          </div></td>`;
        } else {
          html += `<td><div class="tt-cell empty">—</div></td>`;
        }
        if (i === BREAK_AFTER - 1) html += `<td class="brk-col" style="font-size:.62rem;color:#aaa">☕</td>`;
        if (i === LUNCH_AFTER - 1) html += `<td class="brk-col" style="font-size:.62rem;color:#aaa">🍱</td>`;
      });
      html += `</tr>`;
    });

    html += `</tbody></table></div>`;

    // Day-wise detail table
    html += `<div style="margin-top:12px"><div class="card-head"><h4 style="font-size:.9rem"><i class="fa fa-list-check"></i> Weekly Schedule Detail — Semester ${sem}</h4></div>
    <div class="table-scroll"><table class="data-tbl"><thead>
      <tr><th>Day</th><th>Period</th><th>Time</th><th>Course Code</th><th>Subject</th><th>Dept</th><th>Year</th><th>Sec</th><th>Room</th><th>Type</th></tr>
    </thead><tbody>`;

    ALL_DAYS.forEach(day => {
      const dayRows = rows.filter(r => (r.day_of_week||'').toUpperCase() === day).sort((a,b) => a.period_no - b.period_no);
      if (!dayRows.length) {
        html += `<tr><td style="font-weight:600">${DAY_FULL[day]}</td><td colspan="9" style="color:var(--text3);font-style:italic">No classes</td></tr>`;
      } else {
        dayRows.forEach((r, ri) => {
          const pt = PERIOD_TIMES.find(p => p.no === r.period_no);
          html += `<tr>
            ${ri===0 ? `<td style="font-weight:600;vertical-align:middle" rowspan="${dayRows.length}">${DAY_FULL[day]}</td>` : ''}
            <td>P${r.period_no}</td>
            <td style="font-family:monospace;font-size:.75rem">${pt?.time||''}</td>
            <td style="font-family:monospace;font-size:.75rem">${r.course_code}</td>
            <td style="text-align:left">${r.course_name}</td>
            <td><span class="badge badge-info">${r.dept}</span></td>
            <td>Year ${r.year}</td>
            <td>Sec ${r.section}</td>
            <td>${r.room||'—'}</td>
            <td><span class="badge ${r.is_lab?'badge-success':'badge-warn'}">${r.is_lab?'Lab':'Theory'}</span></td>
          </tr>`;
        });
      }
    });

    html += `</tbody></table></div></div>`;
    grid.innerHTML = html;
  } catch(e) {
    grid.innerHTML = `<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>${e.message}</p></div>`;
  }
}

// ── Admin: Seed timetable button (adds to Admin page) ────────
function renderSeedTimetablePanel() {
  const existing = document.getElementById('seedTTPanelWrap');
  if (existing) { existing.scrollIntoView({behavior:'smooth'}); return; }

  const pg = document.getElementById('pg-dashboard') || document.querySelector('.page-body');
  if (!pg) return;

  const wrap = document.createElement('div');
  wrap.id = 'seedTTPanelWrap';
  wrap.className = 'card';
  wrap.style.marginTop = '18px';
  wrap.innerHTML = `
    <div class="card-head">
      <h4><i class="fa fa-database"></i> Timetable Database Seed</h4>
    </div>
    <div class="modal-body" style="padding:14px 16px">
      <p style="font-size:.85rem;color:var(--text2);margin-bottom:12px">
        Seeds the complete college timetable for all 8 departments (CSE, AIDS, CSBS, ECE, EEE, MECH, CIVIL, BME),
        semesters 1–8, sections A/B/C, and all 50 faculty members (FAC001–FAC050) into the database.
        This operation is <b>idempotent</b> — safe to run multiple times.
      </p>
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
        <button class="btn-primary" onclick="doSeedTimetable(false)" id="seedTTBtn">
          <i class="fa fa-play"></i> Seed Timetable (Keep Existing)
        </button>
        <button class="btn-danger" onclick="doSeedTimetable(true)" id="seedTTForceBtn">
          <i class="fa fa-rotate"></i> Force Re-Seed (Clear First)
        </button>
      </div>
      <div id="seedTTStatus" style="margin-top:10px;font-size:.82rem"></div>
    </div>`;
  pg.appendChild(wrap);
  wrap.scrollIntoView({behavior:'smooth'});
}

async function doSeedTimetable(force) {
  const statusEl = document.getElementById('seedTTStatus');
  const btn = document.getElementById(force ? 'seedTTForceBtn' : 'seedTTBtn');
  if (statusEl) statusEl.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Seeding timetable data... this may take a few seconds.';
  if (btn) btn.disabled = true;
  try {
    const res = await apiEx.seedTimetable(force);
    if (statusEl) statusEl.innerHTML = `<span style="color:var(--mint-d)"><i class="fa fa-circle-check"></i> ${res.message || 'Timetable seeded successfully!'}</span>`;
    toast('Timetable seeded!', 'success');
  } catch(e) {
    if (statusEl) statusEl.innerHTML = `<span style="color:var(--red,#ef4444)"><i class="fa fa-triangle-exclamation"></i> ${e.message}</span>`;
    toast('Seed failed: ' + e.message, 'error');
  }
  if (btn) btn.disabled = false;
}

// ── Override renderTimetablePage to use full seeded data ─────
const _origRenderTimetablePage = renderTimetablePage;
async function renderTimetablePage() {
  const ttCont = document.getElementById('ttContent');
  if (!ttCont) return;

  // ── Faculty: restricted, read-only "My Timetable" view ─────
  // Faculty cannot browse other classes and cannot manage/edit
  // timetables — only their own assigned Class In-Charge class
  // (if any) is shown, with no Manage/Add controls.
  const _role = (typeof APP !== 'undefined' && APP.role) || sessionStorage.getItem('_role');
  if (_role === 'faculty' || _role === 'teacher' || _role === 'classincharge') {
    const ttHeader = document.getElementById('ttHeaderControls');
    if (ttHeader) ttHeader.style.display = 'none';
    const oldStrip = document.getElementById('ttTabStrip');
    if (oldStrip) oldStrip.remove();
    return renderFacultyMyTimetable();
  }

  // ── Admin / HOD: full browse + manage UI (unrestricted) ────
  const ttHeader = document.getElementById('ttHeaderControls');
  if (ttHeader) ttHeader.style.display = '';

  // Populate dept dropdown with all 8 depts
  const deptSel = document.getElementById('ttDept');
  if (deptSel) {
    const existing = Array.from(deptSel.options).map(o=>o.value);
    ALL_DEPTS.forEach(d => {
      if (!existing.includes(d.key)) {
        const o = document.createElement('option');
        o.value = d.key; o.textContent = d.name;
        deptSel.appendChild(o);
      }
    });
  }

  // Auto-check seed status and seed if needed
  try {
    const status = await apiFetch('/api/timetable/status');
    if (!status.seeded) {
      ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-database fa-spin"></i><p>Seeding timetable data for first run... please wait.</p></div>';
      await apiFetch('/api/admin/seed-timetable', {method:'POST', body:JSON.stringify({force:false})});
    }
  } catch(_) {}

  // Tab strip (student / faculty / manage)
  if (!document.getElementById('ttTabStrip')) {
    const strip = document.createElement('div');
    strip.id = 'ttTabStrip';
    strip.className = 'tab-strip';
    strip.innerHTML = `
      <button class="tab-b active" onclick="ttSwitchTabFull('student',this)"><i class="fa fa-users"></i> Student Timetable</button>
      <button class="tab-b" onclick="ttSwitchTabFull('faculty',this)"><i class="fa fa-chalkboard-teacher"></i> Faculty Timetable</button>
      <button class="tab-b" onclick="ttSwitchTabFull('manage',this)"><i class="fa fa-pen-to-square"></i> Manage / Add</button>
    `;
    ttCont.parentElement.insertBefore(strip, ttCont);
  }
  window._ttActiveTab = window._ttActiveTab || 'student';
  ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>Select Department, Year, Semester and Section above</p></div>';
}

function ttSwitchTabFull(tab, btn) {
  document.querySelectorAll('#ttTabStrip .tab-b').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  window._ttActiveTab = tab;
  if (tab === 'faculty') {
    renderFullFacultyTimetable();
  } else if (tab === 'manage') {
    renderTimetableManager();
  } else {
    const dept     = document.getElementById('ttDept')?.value;
    const year     = document.getElementById('ttCourse')?.value;
    const semester = document.getElementById('ttSemester')?.value;
    const section  = document.getElementById('ttSection')?.value;
    if (dept && year && semester && section) renderFullStudentTimetable();
    else {
      const ttCont = document.getElementById('ttContent');
      if (ttCont) ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>Select Department, Year, Semester and Section</p></div>';
    }
  }
}

// Override renderTimetable to use full seeded version for student tab
const _origRenderTimetable = renderTimetable;
async function renderTimetable() {
  if (window._ttActiveTab === 'faculty') { renderFullFacultyTimetable(); return; }
  if (window._ttActiveTab === 'manage') { renderTimetableManager(); return; }
  return renderFullStudentTimetable();
}

// =============================================================
// FACULTY "MY TIMETABLE" — Class In-Charge only, read-only view
// =============================================================
// Faculty have no department/year/section pickers and no manage
// controls. The server tells us (via /api/faculty/my-class) which
// single class — if any — this faculty member is the Class
// In-Charge of, and we render only that class's timetable.
// Faculty who are not a Class In-Charge see an empty state.

async function renderFacultyMyTimetable() {
  const ttCont = document.getElementById('ttContent');
  if (!ttCont) return;
  ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Checking your Class In-Charge assignment...</p></div>';

  let info;
  try {
    info = await apiFetch('/api/faculty/my-class');
  } catch (e) {
    ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>Could not load your timetable. Please try again later.</p></div>';
    return;
  }

  if (!info || !info.is_class_incharge || !info.dept || !info.year || !info.section) {
    ttCont.innerHTML = `<div class="empty-msg">
      <i class="fa fa-calendar-xmark"></i>
      <p>You are not currently assigned as a Class In-Charge.<br>No class timetable is available here.</p>
    </div>`;
    return;
  }

  const { dept, year, section } = info;

  // A year spans two semesters (e.g. Year 1 → Sem 1 & Sem 2). Default to
  // whichever is marked "current" for this dept/year; fall back to the
  // first (odd) semester of the year.
  const semOptions = [year * 2 - 1, year * 2];
  let semester = semOptions[0];
  try {
    const cs = await apiEx.currentSem(dept, year);
    if (cs && cs.sem_number && semOptions.includes(cs.sem_number)) semester = cs.sem_number;
  } catch (_) {}

  await renderFacultyClassGrid(dept, year, section, semester, semOptions);
}

async function renderFacultyClassGrid(dept, year, section, semester, semOptions) {
  const ttCont = document.getElementById('ttContent');
  if (!ttCont) return;
  ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading your class timetable...</p></div>';

  try {
    const rows = await apiEx.fullStudentTT(dept, year, section, semester);

    const ttMap = {};
    ALL_DAYS.forEach(d => ttMap[d] = {});
    rows.forEach(r => {
      const d = (r.day_of_week || '').toUpperCase();
      if (!ttMap[d]) ttMap[d] = {};
      ttMap[d][r.period_no] = r;
    });

    const semTabs = semOptions.map(s => `
      <button class="btn-sm ${s === semester ? 'btn-primary' : ''}"
        onclick="renderFacultyClassGrid('${dept}',${year},'${section}',${s},[${semOptions.join(',')}])">
        Semester ${s}
      </button>`).join('');

    let html = `
    <div class="card">
      <div class="card-head">
        <h4><i class="fa fa-user-shield"></i> ${dept} — Year ${year}
          <span class="tt-sem-badge">Sem ${semester}</span>
          — Section ${section}
          <span class="badge badge-success" style="margin-left:8px">My Class — Class In-Charge</span>
        </h4>
        <button class="btn-sm tt-print-btn" onclick="window.print()"><i class="fa fa-print"></i> Print</button>
      </div>
      <div class="tt-filter-bar">${semTabs}</div>
      <div class="tt-legend">
        <div class="tt-leg-item"><div class="tt-leg-dot" style="background:#eef6ff;border:1px solid #3b82f6"></div> Theory</div>
        <div class="tt-leg-item"><div class="tt-leg-dot" style="background:#edfff4;border-left:3px solid #22c55e"></div> Lab</div>
        <div class="tt-leg-item"><div class="tt-leg-dot" style="background:#fefce8;border-left:3px solid #eab308"></div> Elective</div>
        <div class="tt-leg-item"><div class="tt-leg-dot" style="background:#fff0f0;border-left:3px solid #ef4444"></div> Project</div>
      </div>
      <div class="table-scroll">
        <table class="tt-table"><thead><tr>
          <th>Day</th>`;

    PERIOD_TIMES.forEach((p, i) => {
      html += `<th>${p.label}<br><small style="font-weight:400">${p.time}</small></th>`;
      if (i === BREAK_AFTER - 1) html += `<th class="brk-col">BREAK</th>`;
      if (i === LUNCH_AFTER - 1) html += `<th class="brk-col">LUNCH</th>`;
    });
    html += `</tr></thead><tbody>`;

    ALL_DAYS.forEach(day => {
      html += `<tr><td class="day-col">${DAY_FULL[day] || day}</td>`;
      PERIOD_TIMES.forEach((p, i) => {
        const cell = ttMap[day]?.[p.no];
        if (cell) {
          html += `<td><div class="${_ttCellClass(cell)}">
            <div class="ttc-name">${cell.course_name}</div>
            <div class="ttc-code">${cell.course_code}</div>
            ${cell.faculty_name ? `<div class="ttc-fac"><i class="fa fa-user" style="font-size:.6rem"></i> ${cell.faculty_name}</div>` : ''}
            ${cell.room ? `<div class="ttc-room"><i class="fa fa-door-open" style="font-size:.6rem"></i> ${cell.room}</div>` : ''}
          </div></td>`;
        } else {
          html += `<td><div class="tt-cell empty">—</div></td>`;
        }
        if (i === BREAK_AFTER - 1) html += `<td class="brk-col" style="font-size:.65rem;color:#999">☕<br>Break</td>`;
        if (i === LUNCH_AFTER - 1) html += `<td class="brk-col" style="font-size:.65rem;color:#999">🍱<br>Lunch</td>`;
      });
      html += `</tr>`;
    });

    html += `</tbody></table></div></div>`;
    ttCont.innerHTML = html;
  } catch (e) {
    ttCont.innerHTML = '<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>Could not load your class timetable. Please try again later.</p></div>';
  }
}

// ── Faculty Dashboard: timetable now built into renderFacDashboard above ─

// =============================================================
// FACULTY "MY TEACHING TIMETABLE" — every faculty member's own
// weekly teaching schedule (the subjects/periods THEY teach),
// regardless of Class In-Charge status. Subject-faculty-only
// faculty (not a Class In-Charge) still see this — it is just
// their own timetable, not a whole class's student timetable.
// =============================================================
async function renderMyTeachingTimetable() {
  const cont = document.getElementById('myTTContent');
  if (!cont) return;
  cont.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading your teaching timetable...</p></div>';

  const facId = _user && _user.fac_id;
  if (!facId) {
    cont.innerHTML = '<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>Could not determine your Faculty ID.</p></div>';
    return;
  }
  let dept = (_user && _user.dept) || '';
  if (!dept) {
    try {
      const facInfo = await apiFetch('/api/faculty/' + encodeURIComponent(facId));
      dept = (facInfo && facInfo.dept) || '';
      _user.dept = dept;
    } catch(_) {}
  }

  cont.innerHTML = `
    <div class="card">
      <div class="card-head">
        <h4><i class="fa fa-chalkboard-teacher"></i> My Weekly Teaching Schedule</h4>
        <div style="display:flex;gap:8px;align-items:center">
          <label style="font-size:.78rem;font-weight:600;color:var(--text2)">Semester</label>
          <select id="mytSem" class="sel" onchange="loadMyTeachingTimetable()" style="padding:6px 10px">
            ${[1,2,3,4,5,6,7,8].map(s=>`<option value="${s}">Semester ${s}</option>`).join('')}
          </select>
        </div>
      </div>
      <div id="mytGrid"><div class="empty-msg"><i class="fa fa-calendar-days"></i><p>Loading...</p></div></div>
    </div>`;

  // Fetch ALL of this faculty's periods once (no semester filter) so we
  // can default-select a semester that actually has data, instead of
  // guessing a semester and showing a misleading "no periods" message.
  let allRows = [];
  try { allRows = await apiEx.fullFacultyTT(facId, dept) || []; } catch(_) {}
  window._myTTAllRows = allRows;

  const semsWithData = [...new Set(allRows.map(r => r.semester))].sort((a,b)=>a-b);

  let defaultSem = semsWithData[0] || 1;
  try {
    const info = await apiFetch('/api/faculty/my-class');
    if (info && info.year) {
      const cs = await apiEx.currentSem(info.dept, info.year).catch(()=>null);
      const guess = (cs && cs.sem_number) ? cs.sem_number : (info.year * 2 - 1);
      // Prefer the "current" semester only if this faculty actually has
      // periods assigned in it; otherwise fall back to whichever semester
      // does have data.
      if (semsWithData.includes(guess)) defaultSem = guess;
    }
  } catch(_) {}
  const semSel = document.getElementById('mytSem');
  if (semSel) semSel.value = String(defaultSem);
  await loadMyTeachingTimetable();
}

async function loadMyTeachingTimetable() {
  const grid = document.getElementById('mytGrid');
  if (!grid) return;
  const facId = _user && _user.fac_id;
  const dept  = (_user && _user.dept) || '';
  const sem   = parseInt(document.getElementById('mytSem')?.value, 10) || 1;
  grid.innerHTML = '<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading timetable...</p></div>';

  try {
    const rows = await apiEx.fullFacultyTT(facId, dept, sem);
    if (!rows || !rows.length) {
      grid.innerHTML = `<div class="empty-msg"><i class="fa fa-calendar-days"></i><p>No teaching periods assigned to you in Semester ${sem}.</p></div>`;
      return;
    }

    const ttMap = {};
    ALL_DAYS.forEach(d => ttMap[d] = {});
    rows.forEach(r => {
      const d = (r.day_of_week||'').toUpperCase();
      if (!ttMap[d]) ttMap[d] = {};
      ttMap[d][r.period_no] = r;
    });

    const totalSlots = rows.length;
    const labSlots = rows.filter(r=>r.is_lab).length;

    let html = `
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:10px 16px;border-bottom:1px solid var(--border);margin-bottom:8px">
      <span style="background:var(--primary);color:#fff;border-radius:20px;padding:2px 14px;font-size:.78rem;font-weight:700">
        <i class="fa fa-calendar-check"></i> Semester ${sem}
      </span>
      <span style="margin-left:auto;font-size:.75rem;color:var(--text3)">
        ${totalSlots} period(s)/week &nbsp;·&nbsp; Theory: ${totalSlots-labSlots} &nbsp;·&nbsp; Lab: ${labSlots}
      </span>
    </div>
    <div class="table-scroll"><table class="tt-table"><thead><tr><th>Day</th>`;

    PERIOD_TIMES.forEach((p, i) => {
      html += `<th>${p.label}<br><small style="font-weight:400">${p.time}</small></th>`;
      if (i === BREAK_AFTER - 1) html += `<th class="brk-col">BREAK</th>`;
      if (i === LUNCH_AFTER - 1) html += `<th class="brk-col">LUNCH</th>`;
    });
    html += `</tr></thead><tbody>`;

    ALL_DAYS.forEach(day => {
      html += `<tr><td class="day-col">${DAY_FULL[day]||day}</td>`;
      PERIOD_TIMES.forEach((p, i) => {
        const cell = ttMap[day]?.[p.no];
        if (cell) {
          html += `<td><div class="${_ttCellClass(cell)}">
            <div class="ttc-name">${cell.course_name}</div>
            <div class="ttc-code">${cell.dept} · Y${cell.year} Sec ${cell.section}</div>
            <div class="ttc-room">${cell.room||''}</div>
          </div></td>`;
        } else {
          html += `<td><div class="tt-cell empty">—</div></td>`;
        }
        if (i === BREAK_AFTER - 1) html += `<td class="brk-col" style="font-size:.62rem;color:#aaa">☕</td>`;
        if (i === LUNCH_AFTER - 1) html += `<td class="brk-col" style="font-size:.62rem;color:#aaa">🍱</td>`;
      });
      html += `</tr>`;
    });
    html += `</tbody></table></div>`;
    grid.innerHTML = html;
  } catch(e) {
    grid.innerHTML = `<div class="empty-msg"><i class="fa fa-triangle-exclamation"></i><p>${e.message}</p></div>`;
  }
}

console.log('[TimetableSeed] Enhanced timetable module loaded. All 8 depts, 50 faculty, 8 sems ready.');


// =============================================================
// FACULTY REQUEST MANAGEMENT MODULE (PHASE 1)
// Leave Approvals + OD Approvals — faculty-side workflow only.
// Reuses existing card/table/tab styling (same pattern as
// renderHODApprovalsPage). Does not touch Student Portal.
// =============================================================

// ── Dashboard widgets: request KPI cards now built into renderFacDashboard ─

// ── Shared state ────────────────────────────────────────────
var _facReqTab = { leave: 'Pending', od: 'Pending' };

// ── Leave Approvals Page ────────────────────────────────────
async function renderFacLeaveApprovalsPage() {
  var pg = document.getElementById('pg-fac-leave-approvals');
  if (!pg) {
    pg = document.createElement('div');
    pg.id = 'pg-fac-leave-approvals';
    pg.className = 'page dn';
    document.getElementById('pageArea')?.appendChild(pg);
  }
  pg.innerHTML = _facReqPageShell('leave', 'Leave Approvals', 'fa-umbrella-beach',
    'Review and action student leave requests');
  _facReqLoadList('leave', _facReqTab.leave);
}

// ── OD Approvals Page ───────────────────────────────────────
async function renderFacODApprovalsPage() {
  var pg = document.getElementById('pg-fac-od-approvals');
  if (!pg) {
    pg = document.createElement('div');
    pg.id = 'pg-fac-od-approvals';
    pg.className = 'page dn';
    document.getElementById('pageArea')?.appendChild(pg);
  }
  pg.innerHTML = _facReqPageShell('od', 'OD Approvals', 'fa-id-badge',
    'Review and action student on-duty (OD) requests');
  _facReqLoadList('od', _facReqTab.od);
}

// ── Shared page shell (tabs + table container) ──────────────
function _facReqPageShell(kind, title, icon, sub) {
  return [
    '<div class="page-header">',
    '  <div class="ph-left"><h2><i class="fa ' + icon + '" style="color:var(--primary);margin-right:8px"></i>' + title + '</h2>',
    '  <p>' + sub + '</p></div>',
    '  <div class="ph-right"><button class="btn-primary" onclick="' + (kind === 'leave' ? 'renderFacLeaveApprovalsPage()' : 'renderFacODApprovalsPage()') + '"><i class="fa fa-rotate"></i> Refresh</button></div>',
    '</div>',
    '<div class="card">',
    '  <div class="card-head" style="flex-wrap:wrap;gap:8px">',
    '    <h4><i class="fa fa-inbox"></i> ' + title + '</h4>',
    '    <div style="display:flex;gap:6px;flex-wrap:wrap">',
    '      <button id="facReqTab_' + kind + '_Pending"  onclick="_facReqSetTab(\'' + kind + '\',\'Pending\')"  class="btn-sm" style="font-weight:700">⏳ Pending</button>',
    '      <button id="facReqTab_' + kind + '_Approved" onclick="_facReqSetTab(\'' + kind + '\',\'Approved\')" class="btn-sm">✓ Approved</button>',
    '      <button id="facReqTab_' + kind + '_Rejected" onclick="_facReqSetTab(\'' + kind + '\',\'Rejected\')" class="btn-sm">✗ Rejected</button>',
    '    </div>',
    '  </div>',
    '  <div id="facReqBody_' + kind + '">',
    '    <div style="text-align:center;padding:36px;color:var(--text2)"><i class="fa fa-spinner fa-spin" style="font-size:1.6rem"></i><p style="margin:10px 0 0">Loading requests...</p></div>',
    '  </div>',
    '</div>',
  ].join('\n');
}

function _facReqSetTabStyle(kind, active) {
  ['Pending', 'Approved', 'Rejected'].forEach(function (s) {
    var btn = document.getElementById('facReqTab_' + kind + '_' + s);
    if (!btn) return;
    if (s === active) {
      btn.style.background = 'var(--primary)';
      btn.style.color = '#fff';
      btn.style.fontWeight = '700';
    } else {
      btn.style.background = '';
      btn.style.color = '';
      btn.style.fontWeight = '';
    }
  });
}

function _facReqSetTab(kind, status) {
  _facReqTab[kind] = status;
  _facReqLoadList(kind, status);
}

async function _facReqLoadList(kind, status) {
  var body = document.getElementById('facReqBody_' + kind);
  if (!body) return;
  _facReqSetTabStyle(kind, status);
  body.innerHTML = '<div style="text-align:center;padding:36px;color:var(--text2)"><i class="fa fa-spinner fa-spin" style="font-size:1.4rem"></i><p style="margin:10px 0 0">Loading...</p></div>';

  var requests = [];
  try {
    var path = '/api/faculty/requests/' + kind + '?status=' + encodeURIComponent(status);
    var res = await apiFetch(path);
    requests = (res && res.requests) ? res.requests : [];
  } catch (e) {
    body.innerHTML = '<div style="text-align:center;padding:36px;color:var(--danger)"><i class="fa fa-circle-exclamation" style="font-size:1.4rem"></i><p style="margin:10px 0 0">' + (e.message || 'Failed to load') + '</p><button class="btn-sm" onclick="_facReqLoadList(\'' + kind + '\',\'' + status + '\')" style="margin-top:8px">Retry</button></div>';
    return;
  }

  if (requests.length === 0) {
    var emptyIcon = status === 'Pending' ? 'fa-circle-check' : 'fa-inbox';
    var emptyColor = status === 'Pending' ? '#16a34a' : 'var(--text3)';
    var emptyMsg = status === 'Pending'
      ? '<strong style="font-size:1.05rem">No pending requests</strong><br><span style="font-size:.875rem">All ' + kind + ' requests are resolved.</span>'
      : '<strong>No ' + status.toLowerCase() + ' requests</strong>';
    body.innerHTML = '<div style="text-align:center;padding:48px 20px;color:var(--text2)"><i class="fa ' + emptyIcon + '" style="font-size:2.5rem;color:' + emptyColor + ';display:block;margin-bottom:12px"></i>' + emptyMsg + '</div>';
    return;
  }

  var isPending = (status === 'Pending');
  var rows = requests.map(function (r) {
    var statusBadge = '';
    var st = (r.status || 'Pending');
    if (st === 'Approved') statusBadge = '<span style="background:#dcfce7;color:#16a34a;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">✓ Approved</span>';
    else if (st === 'Rejected') statusBadge = '<span style="background:#fee2e2;color:#dc2626;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">✗ Rejected</span>';
    else statusBadge = '<span style="background:#fef3c7;color:#92400e;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">⏳ Pending</span>';

    var actionsHtml = '';
    if (isPending) {
      actionsHtml = '<button onclick="_facReqApprove(\'' + kind + '\',' + r.id + ')" style="padding:5px 12px;border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:700;background:#dcfce7;color:#16a34a"><i class="fa fa-check"></i> Approve</button>'
        + '<button onclick="_facReqReject(\'' + kind + '\',' + r.id + ')" style="padding:5px 12px;border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:700;background:#fee2e2;color:#dc2626;margin-left:5px"><i class="fa fa-xmark"></i> Reject</button>'
        + '<button onclick="_facReqView(\'' + kind + '\',' + r.id + ')" style="padding:5px 10px;border:1.5px solid var(--border);border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:600;background:none;color:var(--text2);margin-left:5px"><i class="fa fa-eye"></i></button>';
    } else {
      actionsHtml = statusBadge + (r.decided_by ? '<br><span style="font-size:.72rem;color:var(--text3)">by ' + r.decided_by + '</span>' : '')
        + ' <button onclick="_facReqView(\'' + kind + '\',' + r.id + ')" style="padding:4px 9px;border:1.5px solid var(--border);border-radius:6px;cursor:pointer;font-size:.76rem;font-weight:600;background:none;color:var(--text2);margin-left:4px"><i class="fa fa-eye"></i></button>';
    }

    var reasonTrunc = (r.reason || '—').length > 50 ? r.reason.substring(0, 50) + '…' : (r.reason || '—');
    var submitted = (r.applied_at || '').split('T')[0] || '—';

    if (kind === 'leave') {
      return '<tr style="border-bottom:1px solid var(--border)">'
        + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text1);font-weight:600">' + (r.student_name || '—') + '</td>'
        + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)"><code>' + (r.register_number || '—') + '</code></td>'
        + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.department || '—') + '</td>'
        + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.year || '—') + '</td>'
        + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.section || '—') + '</td>'
        + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.from_date || '—') + ' → ' + (r.to_date || '—') + '</td>'
        + '<td style="padding:9px 11px;font-size:.82rem;color:var(--text2);max-width:160px" title="' + (r.reason || '') + '">' + reasonTrunc + '</td>'
        + '<td style="padding:9px 11px;font-size:.8rem;color:var(--text3)">' + submitted + '</td>'
        + '<td style="padding:9px 11px">' + (isPending ? statusBadge : '') + '</td>'
        + '<td style="padding:9px 11px;white-space:nowrap">' + actionsHtml + '</td>'
        + '</tr>';
    }
    // OD
    var attach = r.attachment ? '<a href="' + r.attachment + '" target="_blank" style="color:var(--primary)"><i class="fa fa-paperclip"></i> View</a>' : '<span style="color:var(--text3)">—</span>';
    return '<tr style="border-bottom:1px solid var(--border)">'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text1);font-weight:600">' + (r.student_name || '—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)"><code>' + (r.register_number || '—') + '</code></td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.event_name || '—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.event_date || '—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.82rem;color:var(--text2);max-width:160px" title="' + (r.reason || '') + '">' + reasonTrunc + '</td>'
      + '<td style="padding:9px 11px;font-size:.82rem">' + attach + '</td>'
      + '<td style="padding:9px 11px">' + (isPending ? statusBadge : '') + '</td>'
      + '<td style="padding:9px 11px;white-space:nowrap">' + actionsHtml + '</td>'
      + '</tr>';
  }).join('');

  var head = kind === 'leave'
    ? '<th>Student</th><th>Register No.</th><th>Department</th><th>Year</th><th>Section</th><th>Leave Date</th><th>Reason</th><th>Submitted</th><th>Status</th><th>Actions</th>'
    : '<th>Student</th><th>Register No.</th><th>Event Name</th><th>Event Date</th><th>Reason</th><th>Attachment</th><th>Status</th><th>Actions</th>';

  body.innerHTML = '<div class="table-scroll"><table class="data-tbl" style="min-width:900px">'
    + '<thead><tr>' + head + '</tr></thead>'
    + '<tbody>' + rows + '</tbody>'
    + '</table></div>';
}

// ── View details modal (read-only) ──────────────────────────
async function _facReqView(kind, id) {
  try {
    var r = await apiFetch('/api/faculty/requests/' + kind + '/' + id);
    document.getElementById('facReqViewModal')?.remove();
    var overlay = document.createElement('div');
    overlay.id = 'facReqViewModal';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center';
    var rows = kind === 'leave'
      ? [
          ['Student', r.student_name], ['Register No.', r.register_number],
          ['Department', r.department], ['Year', r.year], ['Section', r.section],
          ['From', r.from_date], ['To', r.to_date], ['Reason', r.reason],
          ['Status', r.status], ['Remarks', r.remarks || '—'],
        ]
      : [
          ['Student', r.student_name], ['Register No.', r.register_number],
          ['Event Name', r.event_name], ['Event Date', r.event_date],
          ['Reason', r.reason],
          ['Attachment', r.attachment ? ('<a href="' + r.attachment + '" target="_blank">View attachment</a>') : '—'],
          ['Status', r.status], ['Remarks', r.remarks || '—'],
        ];
    overlay.innerHTML = [
      '<div style="background:var(--card-bg,#fff);border-radius:14px;padding:26px 22px;width:min(460px,92vw);box-shadow:0 8px 40px rgba(0,0,0,.2)">',
      '  <h4 style="margin:0 0 14px;font-size:1.05rem;color:var(--text1)"><i class="fa fa-circle-info" style="color:var(--primary);margin-right:6px"></i>Request #' + id + ' Details</h4>',
      rows.map(function (kv) {
        return '<div style="display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid var(--border);font-size:.85rem">'
          + '<span style="color:var(--text3);font-weight:600">' + kv[0] + '</span><span style="color:var(--text1);text-align:right">' + kv[1] + '</span></div>';
      }).join(''),
      '  <div style="display:flex;justify-content:flex-end;margin-top:16px">',
      '    <button onclick="document.getElementById(\'facReqViewModal\').remove()" style="padding:8px 16px;border:1.5px solid var(--border);background:var(--bg2,#f1f5f9);border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:600;color:var(--text2)">Close</button>',
      '  </div>',
      '</div>',
    ].join('');
    document.body.appendChild(overlay);
  } catch (e) {
    toast('Could not load details: ' + (e.message || 'Error'), 'error');
  }
}

// ── Approve — inline modal with optional remarks ──────────────
function _facReqApprove(kind, id) {
  document.getElementById('facReqApprovePrompt')?.remove();
  var overlay = document.createElement('div');
  overlay.id = 'facReqApprovePrompt';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center';
  overlay.innerHTML = [
    '<div style="background:var(--card-bg,#fff);border-radius:14px;padding:26px 22px;width:min(440px,92vw);box-shadow:0 8px 40px rgba(0,0,0,.2)">',
    '  <h4 style="margin:0 0 14px;font-size:1.05rem;color:var(--text1)"><i class="fa fa-circle-check" style="color:#16a34a;margin-right:6px"></i>Approve ' + (kind === 'leave' ? 'Leave' : 'OD') + ' Request #' + id + '</h4>',
    '  <p style="margin:0 0 10px;font-size:.875rem;color:var(--text2)">Add remarks for the student (optional):</p>',
    '  <textarea id="facReqApproveReason" rows="3" placeholder="e.g. Approved, carry your ID card..."',
    '    style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;resize:vertical;color:var(--text1);font-size:.875rem;font-family:inherit;box-sizing:border-box"></textarea>',
    '  <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:14px">',
    '    <button onclick="document.getElementById(\'facReqApprovePrompt\').remove()" style="padding:8px 16px;border:1.5px solid var(--border);background:var(--bg2,#f1f5f9);border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:600;color:var(--text2)">Cancel</button>',
    '    <button onclick="_facReqApproveSubmit(\'' + kind + '\',' + id + ')" style="padding:8px 20px;background:#16a34a;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:700"><i class="fa fa-check"></i> Approve</button>',
    '  </div>',
    '</div>',
  ].join('');
  document.body.appendChild(overlay);
  setTimeout(function () { document.getElementById('facReqApproveReason')?.focus(); }, 80);
}

async function _facReqApproveSubmit(kind, id) {
  var remarks = (document.getElementById('facReqApproveReason')?.value || '').trim();
  try {
    await apiFetch('/api/faculty/requests/' + kind + '/' + id + '/approve', {
      method: 'POST', body: JSON.stringify({ remarks: remarks }),
    });
    document.getElementById('facReqApprovePrompt')?.remove();
    var successMsg = kind === 'leave'
      ? 'Leave request #' + id + ' approved ✓'
      : 'OD request #' + id + ' approved and forwarded to HOD for final decision';
    toast(successMsg, 'success');
    _facReqLoadList(kind, _facReqTab[kind]);
    refreshNotificationCount();
    if (document.getElementById('pg-fac-dashboard') && !document.getElementById('pg-fac-dashboard').classList.contains('dn')) renderFacDashboard();
  } catch (e) {
    toast('Approve failed: ' + (e.message || 'Error'), 'error');
  }
}

// ── Reject — inline modal with required remarks ───────────────
function _facReqReject(kind, id) {
  document.getElementById('facReqRejectPrompt')?.remove();
  var overlay = document.createElement('div');
  overlay.id = 'facReqRejectPrompt';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center';
  overlay.innerHTML = [
    '<div style="background:var(--card-bg,#fff);border-radius:14px;padding:26px 22px;width:min(440px,92vw);box-shadow:0 8px 40px rgba(0,0,0,.2)">',
    '  <h4 style="margin:0 0 14px;font-size:1.05rem;color:var(--text1)"><i class="fa fa-ban" style="color:#dc2626;margin-right:6px"></i>Reject ' + (kind === 'leave' ? 'Leave' : 'OD') + ' Request #' + id + '</h4>',
    '  <p style="margin:0 0 10px;font-size:.875rem;color:var(--text2)">Add remarks for the student (required, min 5 characters):</p>',
    '  <textarea id="facReqRejectReason" rows="3" placeholder="e.g. Insufficient documentation..."',
    '    style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;resize:vertical;color:var(--text1);font-size:.875rem;font-family:inherit;box-sizing:border-box"></textarea>',
    '  <div id="facReqRejectErr" style="color:var(--danger);font-size:.78rem;margin-top:3px;display:none">Remarks must be at least 5 characters.</div>',
    '  <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:14px">',
    '    <button onclick="document.getElementById(\'facReqRejectPrompt\').remove()" style="padding:8px 16px;border:1.5px solid var(--border);background:var(--bg2,#f1f5f9);border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:600;color:var(--text2)">Cancel</button>',
    '    <button onclick="_facReqRejectSubmit(\'' + kind + '\',' + id + ')" style="padding:8px 20px;background:#dc2626;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:700"><i class="fa fa-ban"></i> Reject</button>',
    '  </div>',
    '</div>',
  ].join('');
  document.body.appendChild(overlay);
  setTimeout(function () { document.getElementById('facReqRejectReason')?.focus(); }, 80);
}

async function _facReqRejectSubmit(kind, id) {
  var reason = (document.getElementById('facReqRejectReason')?.value || '').trim();
  var errEl = document.getElementById('facReqRejectErr');
  if (reason.length < 5) { if (errEl) errEl.style.display = 'block'; return; }
  try {
    await apiFetch('/api/faculty/requests/' + kind + '/' + id + '/reject', {
      method: 'POST', body: JSON.stringify({ remarks: reason }),
    });
    document.getElementById('facReqRejectPrompt')?.remove();
    toast((kind === 'leave' ? 'Leave' : 'OD') + ' request #' + id + ' rejected', 'warn');
    _facReqLoadList(kind, _facReqTab[kind]);
    refreshNotificationCount();
    if (document.getElementById('pg-fac-dashboard') && !document.getElementById('pg-fac-dashboard').classList.contains('dn')) renderFacDashboard();
  } catch (e) {
    toast('Reject failed: ' + (e.message || 'Error'), 'error');
  }
}

// =============================================================
// HOD OD APPROVAL QUEUE MODULE (Prompt 3)
// HOD-only page: review/approve/reject student OD requests across
// all departments (HOD gets unrestricted scope per _resolve_scope
// in api_faculty_requests.py). Reuses the existing
// /api/faculty/requests/od* and /api/faculty/requests/dashboard-counts
// endpoints — no backend changes. Read-only reuse of teacher_required
// auth dependency already covers hod role server-side.
// =============================================================

var _hodOdTab = 'Pending';

async function renderHODODApprovalsPage() {
  // Ensure the page container exists (created dynamically, same
  // pattern as pg-hod_approvals / pg-fac-od-approvals).
  var pg = document.getElementById('pg-hod-od-approvals');
  if (!pg) {
    pg = document.createElement('div');
    pg.id = 'pg-hod-od-approvals';
    pg.className = 'page dn';
    document.getElementById('pageArea')?.appendChild(pg);
  }

  pg.innerHTML = [
    '<div class="page-header">',
    '  <div class="ph-left">',
    '    <h2><i class="fa fa-id-badge" style="color:var(--primary);margin-right:8px"></i>OD Approval Queue</h2>',
    '    <p>Review and action student on-duty (OD) requests across all departments</p>',
    '  </div>',
    '  <div class="ph-right">',
    '    <button class="btn-primary" onclick="renderHODODApprovalsPage()"><i class="fa fa-rotate"></i> Refresh</button>',
    '  </div>',
    '</div>',

    // 3 dashboard cards: Pending OD, Approved Today, Rejected Today
    '<div class="kpi-strip" id="hodOdKpiStrip" style="margin-bottom:1.2rem">',
    '  <div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading...</p></div>',
    '</div>',

    '<div class="card">',
    '  <div class="card-head" style="flex-wrap:wrap;gap:8px">',
    '    <h4><i class="fa fa-inbox"></i> OD Requests</h4>',
    '    <div style="display:flex;gap:6px;flex-wrap:wrap">',
    '      <button id="hodOdTab_Pending"  onclick="_hodOdSetTab(\'Pending\')"  class="btn-sm" style="font-weight:700">⏳ Pending HOD Review</button>',
    '      <button id="hodOdTab_Approved" onclick="_hodOdSetTab(\'Approved\')" class="btn-sm">✓ Approved</button>',
    '      <button id="hodOdTab_Rejected" onclick="_hodOdSetTab(\'Rejected\')" class="btn-sm">✗ Rejected</button>',
    '    </div>',
    '  </div>',
    '  <div id="hodOdBody">',
    '    <div style="text-align:center;padding:36px;color:var(--text2)"><i class="fa fa-spinner fa-spin" style="font-size:1.6rem"></i><p style="margin:10px 0 0">Loading requests...</p></div>',
    '  </div>',
    '</div>',
  ].join('\n');

  _hodOdLoadKpis();
  _hodOdLoadList(_hodOdTab);
}

// ── Dashboard cards: Pending OD / Approved Today / Rejected Today ──
async function _hodOdLoadKpis() {
  var strip = document.getElementById('hodOdKpiStrip');
  if (!strip) return;
  try {
    var c = await apiFetch('/api/faculty/requests/dashboard-counts');
    strip.innerHTML =
      kpi('Pending OD',      c.pending_od_requests ?? 0,      'fa-id-badge',     '#4da6f5') +
      kpi('Approved Today',  c.approved_requests_today ?? 0,  'fa-circle-check', '#4ecba8') +
      kpi('Rejected Today',  c.rejected_requests_today ?? 0,  'fa-ban',          '#e05454');
  } catch (e) {
    strip.innerHTML = '<div class="empty-msg"><p>' + (e.message || 'Failed to load counts') + '</p></div>';
  }
}

function _hodOdSetTabStyle(active) {
  ['Pending', 'Approved', 'Rejected'].forEach(function (s) {
    var btn = document.getElementById('hodOdTab_' + s);
    if (!btn) return;
    if (s === active) {
      btn.style.background = 'var(--primary)';
      btn.style.color = '#fff';
      btn.style.fontWeight = '700';
    } else {
      btn.style.background = '';
      btn.style.color = '';
      btn.style.fontWeight = '';
    }
  });
}

function _hodOdSetTab(status) {
  _hodOdTab = status;
  _hodOdLoadList(status);
}

// ── Table: Student Name, Register No, Dept, Year, Section,
//    Event Name, Event Date, Faculty Remarks, Status + Actions ──
async function _hodOdLoadList(status) {
  var body = document.getElementById('hodOdBody');
  if (!body) return;
  _hodOdSetTabStyle(status);
  body.innerHTML = '<div style="text-align:center;padding:36px;color:var(--text2)"><i class="fa fa-spinner fa-spin" style="font-size:1.4rem"></i><p style="margin:10px 0 0">Loading...</p></div>';

  var requests = [];
  try {
    var res = await apiFetch('/api/faculty/requests/od?status=' + encodeURIComponent(status));
    requests = (res && res.requests) ? res.requests : [];
  } catch (e) {
    body.innerHTML = '<div style="text-align:center;padding:36px;color:var(--danger)"><i class="fa fa-circle-exclamation" style="font-size:1.4rem"></i><p style="margin:10px 0 0">' + (e.message || 'Failed to load') + '</p><button class="btn-sm" onclick="_hodOdLoadList(\'' + status + '\')" style="margin-top:8px">Retry</button></div>';
    return;
  }

  if (requests.length === 0) {
    var emptyIcon = status === 'Pending' ? 'fa-circle-check' : 'fa-inbox';
    var emptyColor = status === 'Pending' ? '#16a34a' : 'var(--text3)';
    var emptyMsg = status === 'Pending'
      ? '<strong style="font-size:1.05rem">No pending OD requests</strong><br><span style="font-size:.875rem">All OD requests are resolved.</span>'
      : '<strong>No ' + status.toLowerCase() + ' OD requests</strong>';
    body.innerHTML = '<div style="text-align:center;padding:48px 20px;color:var(--text2)"><i class="fa ' + emptyIcon + '" style="font-size:2.5rem;color:' + emptyColor + ';display:block;margin-bottom:12px"></i>' + emptyMsg + '</div>';
    return;
  }

  var isPending = (status === 'Pending');
  var rows = requests.map(function (r) {
    var statusBadge = '';
    var st = (r.status || 'Pending');
    if (st === 'Approved') statusBadge = '<span style="background:#dcfce7;color:#16a34a;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">✓ Approved</span>';
    else if (st === 'Rejected') statusBadge = '<span style="background:#fee2e2;color:#dc2626;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">✗ Rejected</span>';
    else if (st === 'Forwarded') statusBadge = '<span style="background:#dbeafe;color:#1d4ed8;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">↗ Awaiting HOD</span>';
    else statusBadge = '<span style="background:#fef3c7;color:#92400e;padding:2px 9px;border-radius:12px;font-size:.75rem;font-weight:700">⏳ Pending</span>';

    var actionsHtml = '';
    if (isPending) {
      actionsHtml = '<button onclick="_hodOdApprove(' + r.id + ')" style="padding:5px 12px;border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:700;background:#dcfce7;color:#16a34a"><i class="fa fa-check"></i> Approve</button>'
        + '<button onclick="_hodOdReject(' + r.id + ')" style="padding:5px 12px;border:none;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:700;background:#fee2e2;color:#dc2626;margin-left:5px"><i class="fa fa-xmark"></i> Reject</button>';
    } else {
      // Two-stage decision trail: Faculty's call is always present once
      // a request has left 'Pending'; HOD's line only renders once HOD
      // has actually decided (hod_decided_by non-empty) -- a faculty
      // rejection never reaches HOD, so this line correctly stays hidden.
      var trailHtml = '<br><span style="font-size:.72rem;color:var(--text3)">Faculty: ' + (r.faculty_status || '—') + ' by ' + (r.faculty_decided_by || '—') + '</span>';
      if (r.hod_decided_by) {
        trailHtml += '<br><span style="font-size:.72rem;color:var(--text3)">HOD: ' + (r.hod_status || '—') + ' by ' + r.hod_decided_by + '</span>';
      }
      actionsHtml = statusBadge + trailHtml;
    }

    var remarksTrunc = (r.remarks || '—');
    remarksTrunc = remarksTrunc.length > 50 ? remarksTrunc.substring(0, 50) + '…' : remarksTrunc;

    return '<tr style="border-bottom:1px solid var(--border)">'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text1);font-weight:600">' + (r.student_name || '—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)"><code>' + (r.register_number || '—') + '</code></td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.department || '—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.year || '—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.section || '—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.event_name || '—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.84rem;color:var(--text2)">' + (r.event_date || '—') + '</td>'
      + '<td style="padding:9px 11px;font-size:.82rem;color:var(--text2);max-width:160px" title="' + (r.remarks || '') + '">' + remarksTrunc + '</td>'
      + '<td style="padding:9px 11px">' + (isPending ? statusBadge : '') + '</td>'
      + '<td style="padding:9px 11px;white-space:nowrap">' + actionsHtml + '</td>'
      + '</tr>';
  }).join('');

  var head = '<th>Student Name</th><th>Register No.</th><th>Dept</th><th>Year</th><th>Section</th>'
    + '<th>Event Name</th><th>Event Date</th><th>Faculty Remarks</th><th>Status</th><th>Actions</th>';

  body.innerHTML = '<div class="table-scroll"><table class="data-tbl" style="min-width:980px">'
    + '<thead><tr>' + head + '</tr></thead>'
    + '<tbody>' + rows + '</tbody>'
    + '</table></div>';
}

// ── Approve — inline modal with optional remarks ──────────────
function _hodOdApprove(id) {
  document.getElementById('hodOdApprovePrompt')?.remove();
  var overlay = document.createElement('div');
  overlay.id = 'hodOdApprovePrompt';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center';
  overlay.innerHTML = [
    '<div style="background:var(--card-bg,#fff);border-radius:14px;padding:26px 22px;width:min(440px,92vw);box-shadow:0 8px 40px rgba(0,0,0,.2)">',
    '  <h4 style="margin:0 0 14px;font-size:1.05rem;color:var(--text1)"><i class="fa fa-circle-check" style="color:#16a34a;margin-right:6px"></i>Approve OD Request #' + id + '</h4>',
    '  <p style="margin:0 0 10px;font-size:.875rem;color:var(--text2)">Add remarks for the student (optional):</p>',
    '  <textarea id="hodOdApproveReason" rows="3" placeholder="e.g. Approved, carry your ID card..."',
    '    style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;resize:vertical;color:var(--text1);font-size:.875rem;font-family:inherit;box-sizing:border-box"></textarea>',
    '  <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:14px">',
    '    <button onclick="document.getElementById(\'hodOdApprovePrompt\').remove()" style="padding:8px 16px;border:1.5px solid var(--border);background:var(--bg2,#f1f5f9);border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:600;color:var(--text2)">Cancel</button>',
    '    <button onclick="_hodOdApproveSubmit(' + id + ')" style="padding:8px 20px;background:#16a34a;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:700"><i class="fa fa-check"></i> Approve</button>',
    '  </div>',
    '</div>',
  ].join('');
  document.body.appendChild(overlay);
  setTimeout(function () { document.getElementById('hodOdApproveReason')?.focus(); }, 80);
}

async function _hodOdApproveSubmit(id) {
  var remarks = (document.getElementById('hodOdApproveReason')?.value || '').trim();
  try {
    await apiFetch('/api/faculty/requests/od/' + id + '/approve', {
      method: 'POST', body: JSON.stringify({ remarks: remarks }),
    });
    document.getElementById('hodOdApprovePrompt')?.remove();
    toast('OD request #' + id + ' approved ✓', 'success');
    _hodOdLoadList(_hodOdTab);
    _hodOdLoadKpis();
    refreshNotificationCount();
  } catch (e) {
    if (e.status === 409) {
      toast('This request is not yet forwarded by faculty, or has already been finalized.', 'warn');
    } else {
      toast('Approve failed: ' + (e.message || 'Error'), 'error');
    }
  }
}

// ── Reject — inline modal with required remarks ───────────────
function _hodOdReject(id) {
  document.getElementById('hodOdRejectPrompt')?.remove();
  var overlay = document.createElement('div');
  overlay.id = 'hodOdRejectPrompt';
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;display:flex;align-items:center;justify-content:center';
  overlay.innerHTML = [
    '<div style="background:var(--card-bg,#fff);border-radius:14px;padding:26px 22px;width:min(440px,92vw);box-shadow:0 8px 40px rgba(0,0,0,.2)">',
    '  <h4 style="margin:0 0 14px;font-size:1.05rem;color:var(--text1)"><i class="fa fa-ban" style="color:#dc2626;margin-right:6px"></i>Reject OD Request #' + id + '</h4>',
    '  <p style="margin:0 0 10px;font-size:.875rem;color:var(--text2)">Add remarks for the student (required, min 5 characters):</p>',
    '  <textarea id="hodOdRejectReason" rows="3" placeholder="e.g. Insufficient documentation..."',
    '    style="width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:8px;resize:vertical;color:var(--text1);font-size:.875rem;font-family:inherit;box-sizing:border-box"></textarea>',
    '  <div id="hodOdRejectErr" style="color:var(--danger);font-size:.78rem;margin-top:3px;display:none">Remarks must be at least 5 characters.</div>',
    '  <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:14px">',
    '    <button onclick="document.getElementById(\'hodOdRejectPrompt\').remove()" style="padding:8px 16px;border:1.5px solid var(--border);background:var(--bg2,#f1f5f9);border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:600;color:var(--text2)">Cancel</button>',
    '    <button onclick="_hodOdRejectSubmit(' + id + ')" style="padding:8px 20px;background:#dc2626;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:.875rem;font-weight:700"><i class="fa fa-ban"></i> Reject</button>',
    '  </div>',
    '</div>',
  ].join('');
  document.body.appendChild(overlay);
  setTimeout(function () { document.getElementById('hodOdRejectReason')?.focus(); }, 80);
}

async function _hodOdRejectSubmit(id) {
  var reason = (document.getElementById('hodOdRejectReason')?.value || '').trim();
  var errEl = document.getElementById('hodOdRejectErr');
  if (reason.length < 5) { if (errEl) errEl.style.display = 'block'; return; }
  try {
    await apiFetch('/api/faculty/requests/od/' + id + '/reject', {
      method: 'POST', body: JSON.stringify({ remarks: reason }),
    });
    document.getElementById('hodOdRejectPrompt')?.remove();
    toast('OD request #' + id + ' rejected', 'warn');
    _hodOdLoadList(_hodOdTab);
    _hodOdLoadKpis();
    refreshNotificationCount();
  } catch (e) {
    if (e.status === 409) {
      toast('This request is not yet forwarded by faculty, or has already been finalized.', 'warn');
    } else {
      toast('Reject failed: ' + (e.message || 'Error'), 'error');
    }
  }
}

// =============================================================
// HOD MANAGEMENT MODULE

// Admin: full CRUD on HOD accounts + mark/edit/delete HOD attendance
// Flow: Admin → HOD → Faculty → Student
// =============================================================

// ── State ────────────────────────────────────────────────────
let _hodList = [];
let _hodFilter = { dept: '', search: '' };

// ── API helpers ──────────────────────────────────────────────
const hodApi = {
  list:      (dept, search) => {
    let q = '/api/hods';
    const p = [];
    if (dept)   p.push('dept='   + encodeURIComponent(dept));
    if (search) p.push('search=' + encodeURIComponent(search));
    if (p.length) q += '?' + p.join('&');
    return apiFetch(q);
  },
  analytics: ()           => apiFetch('/api/hods/analytics'),
  get:       (id)         => apiFetch('/api/hods/' + id),
  create:    (data)       => apiFetch('/api/hods',          { method:'POST',   body:JSON.stringify(data) }),
  update:    (id, data)   => apiFetch('/api/hods/'+id,      { method:'PUT',    body:JSON.stringify(data) }),
  delete:    (id)         => apiFetch('/api/hods/'+id,      { method:'DELETE' }),
  getAtt:    (id, days)   => apiFetch('/api/hods/'+id+'/attendance?days='+(days||30)),
  markAtt:   (data)       => apiFetch('/api/hods/attendance',{ method:'POST',  body:JSON.stringify(data) }),
  editAtt:   (id, lid, d) => apiFetch('/api/hods/'+id+'/attendance/'+lid, { method:'PUT', body:JSON.stringify(d) }),
  deleteAtt: (id, lid)    => apiFetch('/api/hods/'+id+'/attendance/'+lid, { method:'DELETE' }),
};

// ── Status helpers ───────────────────────────────────────────
function hodStatusBadge(s) {
  const map = {
    present: ['#dcfce7','#16a34a','Present'],
    absent:  ['#fee2e2','#dc2626','Absent'],
    late:    ['#fef9c3','#ca8a04','Late'],
    halfday: ['#fff7ed','#ea580c','Half Day'],
    od:      ['#eff6ff','#2563eb','On Duty'],
    leave:   ['#faf5ff','#7c3aed','Leave'],
  };
  const [bg,col,lbl] = map[s] || ['#f1f5f9','#64748b', s||'—'];
  return `<span style="background:${bg};color:${col};padding:2px 10px;border-radius:20px;font-size:.78rem;font-weight:600">${lbl}</span>`;
}

function hodAttPctColor(pct) {
  if (pct >= 85) return '#16a34a';
  if (pct >= 75) return '#ca8a04';
  return '#dc2626';
}

// ── Main page renderer ───────────────────────────────────────
async function renderManageHodPage() {
  if (APP.role !== 'admin') {
    document.getElementById('pg-manage-hod').innerHTML =
      '<div class="empty-msg"><i class="fa fa-lock"></i><p>Admin access only</p></div>';
    return;
  }

  const cont = document.getElementById('pg-manage-hod');
  cont.innerHTML = `<div class="empty-msg"><i class="fa fa-spinner fa-spin"></i><p>Loading HOD data...</p></div>`;

  try {
    const [analytics, hods] = await Promise.all([
      hodApi.analytics(),
      hodApi.list(_hodFilter.dept, _hodFilter.search),
    ]);
    _hodList = hods;

    // ── Dept breakdown chips
    const deptChips = (analytics.dept_breakdown||[]).map(d =>
      `<span style="background:#f1f5f9;border-radius:20px;padding:3px 12px;font-size:.8rem;font-weight:600;color:#475569">
        ${d.dept}: ${d.cnt}
      </span>`
    ).join('');

    cont.innerHTML = `
      <!-- Page Header -->
      <div class="page-header" style="margin-bottom:1.15rem">
        <div class="ph-left">
          <h2><i class="fa fa-user-tie" style="color:#7c3aed"></i> HOD Management</h2>
        </div>
        <div class="ph-right">
          <button class="btn-primary" onclick="openHodModal()"
            style="background:linear-gradient(135deg,#7c3aed,#4f46e5);border-radius:8px;padding:.5rem 1rem">
            <i class="fa fa-plus"></i> Add HOD
          </button>
        </div>
      </div>

      <!-- KPI Strip -->
      <div class="kpi-strip" style="margin-bottom:1.25rem">
        ${kpi('Total HODs', analytics.total_hods||0, 'fa-user-tie', '#7c3aed')}
        ${kpi('Present Today', analytics.present_today||0, 'fa-circle-check', '#16a34a')}
        ${kpi('Absent Today', analytics.absent_today||0, 'fa-circle-xmark', '#dc2626')}
        <div class="kpi-card" style="border-left:4px solid #0ea5e9;display:flex;align-items:center;gap:.75rem;padding:1rem 1.25rem">
          <div style="background:#eff6ff;border-radius:50%;width:40px;height:40px;display:flex;align-items:center;justify-content:center">
            <i class="fa fa-building-columns" style="color:#0ea5e9"></i>
          </div>
          <div>
            <div style="font-size:.72rem;color:#64748b;font-weight:600;text-transform:uppercase;letter-spacing:.05em">Departments</div>
            <div style="font-size:1.3rem;font-weight:700;color:#0f172a;line-height:1.2">${(analytics.dept_breakdown||[]).length}</div>
            <div style="margin-top:.25rem;display:flex;flex-wrap:wrap;gap:.3rem">${deptChips}</div>
          </div>
        </div>
      </div>

      <!-- Filters -->
      <div style="display:flex;gap:12px;align-items:center;margin-bottom:1.25rem;flex-wrap:wrap">
        <div style="display:flex;align-items:center;gap:10px;flex:1;min-width:240px;background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:9px 16px;box-shadow:0 1px 3px rgba(0,0,0,0.02)">
          <i class="fa fa-search" style="color:#94a3b8;font-size:0.95rem"></i>
          <input placeholder="Search by name, ID or email..." value="${_hodFilter.search||''}"
            oninput="_hodFilter.search=this.value;_debouncedHodSearch()"
            style="border:none;outline:none;flex:1;font-size:0.88rem;background:transparent;color:#0f172a"/>
        </div>
        <select onchange="_hodFilter.dept=this.value;renderManageHodPage()"
          style="border:1px solid #e2e8f0;border-radius:10px;padding:9px 16px;font-size:0.88rem;background:#ffffff;color:#1e293b;font-weight:500;cursor:pointer;outline:none;box-shadow:0 1px 3px rgba(0,0,0,0.02)">
          <option value="">All Departments</option>
          <option value="CS"    ${_hodFilter.dept==='CS'?'selected':''}>CS</option>
          <option value="IT"    ${_hodFilter.dept==='IT'?'selected':''}>IT</option>
          <option value="ECE"   ${_hodFilter.dept==='ECE'?'selected':''}>ECE</option>
          <option value="EEE"   ${_hodFilter.dept==='EEE'?'selected':''}>EEE</option>
          <option value="MECH"  ${_hodFilter.dept==='MECH'?'selected':''}>MECH</option>
          <option value="CIVIL" ${_hodFilter.dept==='CIVIL'?'selected':''}>CIVIL</option>
          <option value="AIDS"  ${_hodFilter.dept==='AIDS'?'selected':''}>AIDS</option>
          <option value="AIML"  ${_hodFilter.dept==='AIML'?'selected':''}>AIML</option>
          <option value="MBA"   ${_hodFilter.dept==='MBA'?'selected':''}>MBA</option>
        </select>
        <button onclick="_hodFilter={dept:'',search:''};renderManageHodPage()" title="Reset Filters"
          style="border:1px solid #e2e8f0;border-radius:10px;background:#ffffff;width:40px;height:40px;display:flex;align-items:center;justify-content:center;color:#475569;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,0.02);transition:all 0.15s"
          onmouseenter="this.style.background='#f8fafc'" onmouseleave="this.style.background='#ffffff'">
          <i class="fa fa-sliders" style="font-size:0.95rem"></i>
        </button>
      </div>

      <!-- HOD Table -->
      <div class="card" style="padding:0;overflow:visible;border-radius:14px;border:1px solid #eef2f6;box-shadow:0 1px 4px rgba(0,0,0,0.04);background:#ffffff;margin-bottom:1.5rem">
        <div class="table-scroll" style="overflow:visible">
          <table class="data-tbl" id="hodTable" style="width:100%;border-collapse:collapse">
            <thead>
              <tr style="border-bottom:1px solid #f1f5f9;background:#fafbfc">
                <th style="padding:14px 18px;text-align:left;font-size:0.72rem;font-weight:700;color:#64748b;letter-spacing:0.05em;text-transform:uppercase">HOD ID</th>
                <th style="padding:14px 18px;text-align:left;font-size:0.72rem;font-weight:700;color:#64748b;letter-spacing:0.05em;text-transform:uppercase">NAME</th>
                <th style="padding:14px 18px;text-align:left;font-size:0.72rem;font-weight:700;color:#64748b;letter-spacing:0.05em;text-transform:uppercase">DEPARTMENT</th>
                <th style="padding:14px 18px;text-align:left;font-size:0.72rem;font-weight:700;color:#64748b;letter-spacing:0.05em;text-transform:uppercase">DESIGNATION</th>
                <th style="padding:14px 18px;text-align:left;font-size:0.72rem;font-weight:700;color:#64748b;letter-spacing:0.05em;text-transform:uppercase">CONTACT</th>
                <th style="padding:14px 18px;text-align:center;font-size:0.72rem;font-weight:700;color:#64748b;letter-spacing:0.05em;text-transform:uppercase">30-DAY ATT%</th>
                <th style="padding:14px 18px;text-align:center;font-size:0.72rem;font-weight:700;color:#64748b;letter-spacing:0.05em;text-transform:uppercase">TODAY</th>
                <th style="padding:14px 18px;text-align:center;font-size:0.72rem;font-weight:700;color:#64748b;letter-spacing:0.05em;text-transform:uppercase">ACTION</th>
              </tr>
            </thead>
            <tbody id="hodTbody">
              ${_renderHodRows(hods)}
            </tbody>
          </table>
        </div>
      </div>

      <!-- 30-Day Leaderboard -->
      <div class="card" style="margin-top:1.5rem;padding:0;overflow:hidden;border-radius:14px;border:1px solid #eef2f6;box-shadow:0 1px 4px rgba(0,0,0,0.04);background:#ffffff">
        <div class="card-head" style="display:flex;align-items:center;padding:14px 18px;border-bottom:1px solid #f1f5f9">
          <div style="width:36px;height:36px;border-radius:10px;background:#ede9fe;display:flex;align-items:center;justify-content:center;margin-right:12px">
            <i class="fa fa-trophy" style="color:#6366f1;font-size:1.15rem"></i>
          </div>
          <h3 style="margin:0;font-size:1.05rem;font-weight:700;color:#0f172a">30-Day Attendance Leaderboard</h3>
        </div>
        <div style="padding:0">
          ${_renderHodLeaderboard(analytics.hod_summary||[])}
        </div>
      </div>
    `;

    // Populate HOD att modal select
    _populateHodAttSelect(hods);

  } catch(e) {
    cont.innerHTML = `<div class="empty-msg">
      <i class="fa fa-triangle-exclamation" style="color:#ef4444"></i>
      <p>${e.message}</p>
      <button class="btn-primary" onclick="renderManageHodPage()">Retry</button>
    </div>`;
  }
}

let _hodSearchTimer = null;
function _debouncedHodSearch() {
  clearTimeout(_hodSearchTimer);
  _hodSearchTimer = setTimeout(() => renderManageHodPage(), 350);
}

function _renderHodRows(hods) {
  if (!hods || hods.length === 0) {
    return `<tr><td colspan="8" style="text-align:center;padding:36px;color:#94a3b8">
      <i class="fa fa-user-tie" style="font-size:1.6rem;opacity:.4"></i>
      <div style="margin-top:8px;font-weight:600;font-size:.9rem">No HODs found</div>
      <button class="btn-primary" onclick="openHodModal()" style="margin-top:12px;padding:6px 16px;font-size:.82rem">
        <i class="fa fa-plus"></i> Add First HOD
      </button>
    </td></tr>`;
  }
  return hods.map(h => {
    const pct = h.att_pct || 0;
    const pctColor = hodAttPctColor(pct);
    const todayMark = h.marked_today
      ? `<span style="color:#16a34a;font-weight:600;font-size:.85rem"><i class="fa fa-circle-check"></i> Marked</span>`
      : `<span style="color:#64748b;font-weight:500;font-size:.95rem">—</span>`;

    const attDisplay = (h.total_logged > 0)
      ? `<div style="display:flex;align-items:center;gap:.5rem;justify-content:center">
           <div style="flex:1;max-width:70px;background:#f1f5f9;border-radius:20px;height:6px;overflow:hidden">
             <div style="width:${pct}%;height:100%;background:${pctColor};border-radius:20px"></div>
           </div>
           <span style="font-weight:700;color:${pctColor};font-size:.82rem">${pct}%</span>
         </div>`
      : `<span style="color:#64748b;font-weight:600;font-size:.95rem">—</span>`;

    const desig = (h.designation || 'Head of Department')
      .replace(/Head of Department/gi, 'Head of<br>Department');

    const nameSafe = (h.name || '').replace(/'/g, "\\'");
    const menuId = `hodMenu_${h.hod_id}`;

    return `<tr style="border-bottom:1px solid #f8fafc;transition:background .15s" onmouseenter="this.style.background='#fafbfc'" onmouseleave="this.style.background='transparent'">
      <td style="padding:14px 18px;vertical-align:middle">
        <span style="font-weight:700;color:#4f46e5;font-size:.88rem;letter-spacing:.3px">${h.hod_id}</span>
      </td>
      <td style="padding:14px 18px;vertical-align:middle">
        <span style="font-weight:700;color:#0f172a;font-size:.88rem">${h.name||'—'}</span>
      </td>
      <td style="padding:14px 18px;vertical-align:middle">
        <span style="background:#ede9fe;color:#6366f1;padding:4px 14px;border-radius:9999px;font-size:.76rem;font-weight:700;display:inline-block">${h.dept||'—'}</span>
      </td>
      <td style="padding:14px 18px;vertical-align:middle;font-size:.82rem;color:#475569;line-height:1.35;font-weight:500">
        ${desig}
      </td>
      <td style="padding:14px 18px;vertical-align:middle;font-size:.82rem">
        ${h.email ? `<div style="display:flex;align-items:center;gap:8px;color:#334155;font-weight:500;margin-bottom:4px"><i class="fa fa-envelope" style="color:#64748b;font-size:.82rem;width:14px"></i><span>${h.email}</span></div>` : ''}
        ${h.mobile ? `<div style="display:flex;align-items:center;gap:8px;color:#334155;font-weight:500"><i class="fa fa-phone" style="color:#64748b;font-size:.82rem;width:14px"></i><span>${h.mobile}</span></div>` : ''}
      </td>
      <td style="padding:14px 18px;vertical-align:middle;text-align:center">
        ${attDisplay}
      </td>
      <td style="padding:14px 18px;vertical-align:middle;text-align:center">
        ${todayMark}
      </td>
      <td style="padding:14px 18px;vertical-align:middle;text-align:center;white-space:nowrap">
        <div class="row-action-wrap" style="display:inline-flex;align-items:center;gap:8px;position:relative">
          <button onclick="openHodAttModal('${h.hod_id}')"
            style="background:#4338ca;background:linear-gradient(135deg,#4f46e5,#4338ca);color:#fff;border:none;border-radius:8px;padding:7px 15px;font-size:.82rem;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:7px;box-shadow:0 1px 3px rgba(79,70,229,.28);transition:all .15s"
            onmouseenter="this.style.opacity='.9'" onmouseleave="this.style.opacity='1'">
            <i class="fa fa-calendar-check" style="font-size:.88rem"></i> Attendance
          </button>
          <button class="btn-action-trigger" onclick="toggleActionMenu(event, '${menuId}')" title="Actions"
            style="width:32px;height:32px;border:none;background:transparent;color:#475569;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.15rem;border-radius:6px;transition:all .15s"
            onmouseenter="this.style.background='#f1f5f9';this.style.color='#0f172a'" onmouseleave="this.style.background='transparent';this.style.color='#475569'">
            <i class="fa fa-ellipsis-vertical"></i>
          </button>
          <div class="action-dropdown-menu" id="${menuId}">
            <div class="action-dropdown-item" onclick="viewHodAttDetail('${h.hod_id}','${nameSafe}')">
              <i class="fa fa-clock-rotate-left" style="color:#6366f1"></i> View Attendance Log
            </div>
            <div class="action-dropdown-item" onclick="editHod('${h.hod_id}')">
              <i class="fa fa-pen" style="color:#f59e0b"></i> Edit HOD
            </div>
            <div class="action-dropdown-item danger" onclick="deleteHod('${h.hod_id}','${nameSafe}')">
              <i class="fa fa-trash"></i> Delete
            </div>
          </div>
        </div>
      </td>
    </tr>`;
  }).join('');
}

function _renderHodLeaderboard(summary) {
  if (!summary || summary.length === 0) {
    return '<p style="color:#94a3b8;text-align:center;padding:1.5rem">No attendance data yet.</p>';
  }
  return summary.map((h, i) => {
    const pct  = h.logged > 0 ? Math.round(h.present / h.logged * 100) : 0;
    const col  = hodAttPctColor(pct);
    const medal = i === 0
      ? `<div style="width:36px;height:36px;border-radius:50%;background:#fef3c7;display:flex;align-items:center;justify-content:center;font-size:1.25rem;flex-shrink:0">🥇</div>`
      : i === 1
      ? `<div style="width:36px;height:36px;border-radius:50%;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:1.25rem;flex-shrink:0">🥈</div>`
      : i === 2
      ? `<div style="width:36px;height:36px;border-radius:50%;background:#ffedd5;display:flex;align-items:center;justify-content:center;font-size:1.25rem;flex-shrink:0">🥉</div>`
      : `<div style="width:36px;height:36px;border-radius:50%;background:#f8fafc;display:flex;align-items:center;justify-content:center;font-weight:700;color:#94a3b8;font-size:.85rem">#${i+1}</div>`;

    return `<div style="display:flex;align-items:center;padding:14px 18px;border-bottom:1px solid #f8fafc;transition:background .15s" onmouseenter="this.style.background='#fafbfc'" onmouseleave="this.style.background='transparent'">
      <div style="margin-right:14px;flex-shrink:0">
        ${medal}
      </div>
      <div style="min-width:180px;flex:1">
        <div style="font-weight:700;font-size:.92rem;color:#0f172a">${h.name||h.hod_id}</div>
        <div style="font-size:.78rem;color:#64748b;font-weight:600;margin-top:2px">${h.dept||'—'}</div>
      </div>
      <div style="min-width:110px;font-size:.85rem;color:#475569;font-weight:500;text-align:center">
        ${h.present||0} / ${h.logged||0} days
      </div>
      <div style="flex:2;max-width:280px;background:#f1f5f9;border-radius:9999px;height:8px;overflow:hidden;margin:0 1.5rem">
        <div style="width:${pct}%;height:100%;background:${col};border-radius:9999px"></div>
      </div>
      <div style="min-width:45px;text-align:center;font-weight:600;color:#64748b;font-size:.88rem">
        ${pct > 0 ? pct + '%' : '—'}
      </div>
      <div style="min-width:85px;text-align:right;font-size:.82rem;color:#94a3b8;font-weight:500">
        ${h.logged > 0 ? (pct >= 75 ? '<span style="color:#16a34a;font-weight:600">Good</span>' : '<span style="color:#ef4444;font-weight:600">Critical</span>') : 'No data'}
      </div>
    </div>`;
  }).join('');
}

function _populateHodAttSelect(hods) {
  const sel = document.getElementById('hod_att_hod_id');
  if (!sel) return;
  sel.innerHTML = '<option value="">Select HOD</option>'
    + (hods||_hodList).map(h => `<option value="${h.hod_id}">${h.hod_id} — ${h.name} (${h.dept})</option>`).join('');
}

// ── Modal: Add HOD ───────────────────────────────────────────
function openHodModal() {
  document.getElementById('hodModalTitle').innerHTML = '<i class="fa fa-plus-circle"></i> Add New HOD';
  document.getElementById('hod_edit_id').value = '';
  document.getElementById('hod_id').value = '';
  document.getElementById('hod_id').disabled = false;
  document.getElementById('hod_name').value = '';
  document.getElementById('hod_dept').value = '';
  document.getElementById('hod_designation').value = 'Head of Department';
  document.getElementById('hod_email').value = '';
  document.getElementById('hod_mobile').value = '';
  document.getElementById('hod_password').value = '';
  document.getElementById('hod_pass_hint').textContent = '(default: hod@2025)';
  document.getElementById('hodModal').classList.remove('dn');
}

async function editHod(hodId) {
  try {
    const h = await hodApi.get(hodId);
    document.getElementById('hodModalTitle').innerHTML = '<i class="fa fa-pen"></i> Edit HOD';
    document.getElementById('hod_edit_id').value     = h.hod_id;
    document.getElementById('hod_id').value          = h.hod_id;
    document.getElementById('hod_id').disabled       = true;
    document.getElementById('hod_name').value        = h.name || '';
    document.getElementById('hod_dept').value        = h.dept || '';
    document.getElementById('hod_designation').value = h.designation || 'Head of Department';
    document.getElementById('hod_email').value       = h.email || '';
    document.getElementById('hod_mobile').value      = h.mobile || '';
    document.getElementById('hod_password').value    = '';
    document.getElementById('hod_pass_hint').textContent = '(leave blank to keep current password)';
    document.getElementById('hodModal').classList.remove('dn');
  } catch(e) {
    toast('Failed to load HOD: ' + e.message, 'error');
  }
}

async function saveHod() {
  const editId = document.getElementById('hod_edit_id').value;
  const isEdit = !!editId;
  const hodId  = (document.getElementById('hod_id').value || '').trim().toUpperCase();
  const name   = document.getElementById('hod_name').value.trim();
  const dept   = document.getElementById('hod_dept').value;
  const desg   = document.getElementById('hod_designation').value.trim() || 'Head of Department';
  const email  = document.getElementById('hod_email').value.trim();
  const mobile = document.getElementById('hod_mobile').value.trim();
  const pass   = document.getElementById('hod_password').value.trim();

  if (!hodId || !name || !dept) {
    toast('HOD ID, Name, and Department are required.', 'warn'); return;
  }

  try {
    if (isEdit) {
      const data = { name, dept, designation:desg, email, mobile };
      if (pass) data.password = pass;
      await hodApi.update(editId, data);
      toast(`HOD ${editId} updated successfully!`, 'success');
    } else {
      await hodApi.create({ hod_id:hodId, name, dept, designation:desg, email, mobile, password:pass||'hod@2025' });
      toast(`HOD ${hodId} created successfully!`, 'success');
    }
    closeModal('hodModal');
    renderManageHodPage();
  } catch(e) {
    toast((isEdit ? 'Update' : 'Create') + ' failed: ' + e.message, 'error');
  }
}

async function deleteHod(hodId, name) {
  if (!confirm(`Delete HOD account for ${name} (${hodId})?\n\nThis will deactivate the account. Attendance records will be preserved.`)) return;
  try {
    await hodApi.delete(hodId);
    toast(`HOD ${hodId} removed.`, 'success');
    renderManageHodPage();
  } catch(e) {
    toast('Delete failed: ' + e.message, 'error');
  }
}

// ── Modal: Attendance ────────────────────────────────────────
function openHodAttModal(preselect) {
  // Set today's date
  document.getElementById('hod_att_date').value = new Date().toISOString().split('T')[0];
  document.getElementById('hod_att_status').value = 'present';
  document.getElementById('hod_att_time').value  = '09:00';
  document.getElementById('hod_att_reason').value = '';
  _populateHodAttSelect();
  if (preselect) document.getElementById('hod_att_hod_id').value = preselect;
  document.getElementById('hodAttModal').classList.remove('dn');
}

async function saveHodAttendance() {
  const hod_id      = document.getElementById('hod_att_hod_id').value;
  const att_date    = document.getElementById('hod_att_date').value;
  const status      = document.getElementById('hod_att_status').value;
  const arrival_time= document.getElementById('hod_att_time').value;
  const reason      = document.getElementById('hod_att_reason').value.trim();

  if (!hod_id || !att_date || !status) {
    toast('Please select HOD, date and status.', 'warn'); return;
  }

  try {
    await hodApi.markAtt({
      hod_id, att_date, status, arrival_time,
      reason, updated_by: _user.username || 'ADMIN'
    });
    toast(`Attendance marked: ${hod_id} → ${status}`, 'success');
    closeModal('hodAttModal');
    renderManageHodPage();
  } catch(e) {
    toast('Save failed: ' + e.message, 'error');
  }
}

// ── Attendance Detail Modal ──────────────────────────────────
async function viewHodAttDetail(hodId, hodName) {
  document.getElementById('hodAttDetailTitle').innerHTML =
    `<i class="fa fa-calendar-days"></i> ${hodName} — Attendance Log`;
  document.getElementById('hodAttDetailBody').innerHTML =
    '<div style="text-align:center;padding:24px"><i class="fa fa-spinner fa-spin"></i> Loading…</div>';
  document.getElementById('hodAttDetailModal').classList.remove('dn');

  try {
    const rows = await hodApi.getAtt(hodId, 60);
    if (!rows || rows.length === 0) {
      document.getElementById('hodAttDetailBody').innerHTML =
        '<p style="text-align:center;color:#94a3b8;padding:20px">No attendance records found.</p>';
      return;
    }

    const presentDays = rows.filter(r => r.status === 'present').length;
    const pct = Math.round(presentDays / rows.length * 100);

    document.getElementById('hodAttDetailBody').innerHTML = `
      <div style="display:flex;gap:1rem;margin-bottom:1rem;flex-wrap:wrap">
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:.75rem 1.25rem;flex:1;min-width:120px;text-align:center">
          <div style="font-size:1.6rem;font-weight:800;color:#16a34a">${presentDays}</div>
          <div style="font-size:.78rem;color:#64748b;font-weight:600">Present Days</div>
        </div>
        <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:.75rem 1.25rem;flex:1;min-width:120px;text-align:center">
          <div style="font-size:1.6rem;font-weight:800;color:#dc2626">${rows.length - presentDays}</div>
          <div style="font-size:.78rem;color:#64748b;font-weight:600">Absent/Other</div>
        </div>
        <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:.75rem 1.25rem;flex:1;min-width:120px;text-align:center">
          <div style="font-size:1.6rem;font-weight:800;color:${hodAttPctColor(pct)}">${pct}%</div>
          <div style="font-size:.78rem;color:#64748b;font-weight:600">Attendance %</div>
        </div>
      </div>
      <div class="table-scroll">
        <table class="data-tbl" style="font-size:.84rem">
          <thead><tr>
            <th>Date</th><th>Status</th><th>Arrival</th><th>Reason</th><th>Updated By</th><th>Actions</th>
          </tr></thead>
          <tbody>
            ${rows.map(r => `<tr>
              <td style="font-family:monospace;font-weight:600">${r.att_date}</td>
              <td>${hodStatusBadge(r.status)}</td>
              <td style="color:#64748b">${r.arrival_time||'—'}</td>
              <td style="color:#64748b;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${r.reason||''}">${r.reason||'—'}</td>
              <td style="font-size:.78rem;color:#94a3b8">${r.updated_by||'—'}</td>
              <td>
                <button onclick="deleteHodAttRecord('${hodId}','${hodName}',${r.id})"
                  style="background:#fee2e2;color:#dc2626;border:none;border-radius:6px;padding:3px 9px;cursor:pointer;font-size:.76rem;font-weight:600">
                  <i class="fa fa-trash"></i>
                </button>
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  } catch(e) {
    document.getElementById('hodAttDetailBody').innerHTML =
      `<p style="color:#ef4444;text-align:center;padding:20px">${e.message}</p>`;
  }
}

async function deleteHodAttRecord(hodId, hodName, logId) {
  if (!confirm(`Delete this attendance record for ${hodName}?`)) return;
  try {
    await hodApi.deleteAtt(hodId, logId);
    toast('Attendance record deleted.', 'success');
    viewHodAttDetail(hodId, hodName); // refresh detail modal
    renderManageHodPage();            // refresh main table
  } catch(e) {
    toast('Delete failed: ' + e.message, 'error');
  }
}

console.log('[HOD Module] HOD Management loaded — Admin → HOD → Faculty → Student hierarchy active.');

// ================================================================
// FACE CAPTURE MODAL  —  Browser-based 5-pose webcam enrollment
// ================================================================
// Called after successful enrollment when user chooses to capture face.
// Walks through 5 poses: Straight, Left, Right, Up, Down.
// Captures 8 images per pose = 40 total, uploads to /api/enroll/face-images
// ================================================================

(function() {

const FC_POSES = [
  { key: 'straight', label: 'Look STRAIGHT',      hint: 'Face the camera directly, keep head level',      icon: '⬆' },
  { key: 'left',     label: 'Turn HEAD LEFT',      hint: 'Slowly turn your head about 20° to the left',   icon: '⬅' },
  { key: 'right',    label: 'Turn HEAD RIGHT',     hint: 'Slowly turn your head about 20° to the right',  icon: '➡' },
  { key: 'up',       label: 'Tilt HEAD UP',        hint: 'Tilt your chin slightly upward',                 icon: '⬆' },
  { key: 'down',     label: 'Tilt HEAD DOWN',      hint: 'Tilt your chin slightly downward',               icon: '⬇' },
];
const FC_IMAGES_PER_POSE = 8;   // 8 × 5 = 40 total images
const FC_CAPTURE_INTERVAL = 250; // ms between captures

let _fcStream   = null;
let _fcCapTimer = null;
let _fcCaptured = [];   // { blob, pose }
let _fcPoseIdx  = 0;
let _fcPoseCount = 0;
let _fcEntityId = '';
let _fcRole     = 'student';
let _fcName     = '';
let _fcActive   = false;

// ── Inject modal HTML once ────────────────────────────────────
function _injectFcModal() {
  if (document.getElementById('fcModal')) return;
  const div = document.createElement('div');
  div.id = 'fcModal';
  div.innerHTML = `
  <style>
    #fcModal{display:none;position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.75);
      align-items:center;justify-content:center;font-family:inherit;}
    #fcModal.fc-open{display:flex;}
    #fcBox{background:var(--card-bg,#fff);border-radius:18px;width:min(520px,96vw);
      box-shadow:0 24px 60px rgba(0,0,0,.4);overflow:hidden;animation:fcSlideIn .25s ease;}
    @keyframes fcSlideIn{from{transform:translateY(30px);opacity:0}to{transform:none;opacity:1}}
    #fcHeader{background:linear-gradient(135deg,#0284c7,#0ea5e9);color:#fff;padding:18px 22px;
      display:flex;align-items:center;gap:12px;}
    #fcHeader h3{margin:0;font-size:1.05rem;font-weight:700;}
    #fcHeader p{margin:2px 0 0;font-size:.8rem;opacity:.85;}
    #fcVideo{width:100%;max-height:280px;background:#000;display:block;object-fit:cover;}
    #fcCanvas{display:none;}
    #fcBody{padding:18px 22px;}
    #fcPoseBar{display:flex;gap:6px;margin-bottom:14px;}
    .fc-pose-dot{flex:1;height:6px;border-radius:3px;background:#e2e8f0;transition:background .3s;}
    .fc-pose-dot.done{background:#16a34a;}
    .fc-pose-dot.active{background:#0284c7;}
    #fcPoseLabel{font-size:1.1rem;font-weight:700;color:var(--text1,#1e293b);margin-bottom:4px;}
    #fcPoseHint{font-size:.83rem;color:var(--text2,#64748b);margin-bottom:14px;}
    #fcProgress{height:8px;border-radius:4px;background:#e2e8f0;margin-bottom:12px;overflow:hidden;}
    #fcProgressBar{height:100%;background:linear-gradient(90deg,#0284c7,#38bdf8);
      border-radius:4px;transition:width .2s;width:0%;}
    #fcCount{font-size:.8rem;color:var(--text2,#64748b);text-align:center;margin-bottom:14px;}
    #fcStatus{min-height:32px;padding:8px 12px;border-radius:8px;font-size:.85rem;
      text-align:center;background:#f0f9ff;color:#0284c7;display:none;margin-bottom:10px;}
    #fcButtons{display:flex;gap:10px;flex-wrap:wrap;}
    #fcBtnStart{flex:1;padding:11px;background:#0284c7;color:#fff;border:none;border-radius:10px;
      font-weight:700;font-size:.92rem;cursor:pointer;display:flex;align-items:center;
      justify-content:center;gap:7px;transition:background .15s;}
    #fcBtnStart:hover{background:#0369a1;}
    #fcBtnStart:disabled{background:#94a3b8;cursor:not-allowed;}
    #fcBtnSkip{padding:11px 18px;background:var(--card-bg,#fff);color:var(--text2,#64748b);
      border:1.5px solid var(--border,#e2e8f0);border-radius:10px;font-weight:600;
      font-size:.88rem;cursor:pointer;}
    #fcBtnSkip:hover{border-color:#94a3b8;}
    #fcUploadStatus{margin-top:12px;padding:10px 14px;border-radius:10px;font-size:.85rem;
      display:none;text-align:center;}
  </style>
  <div id="fcBox">
    <div id="fcHeader">
      <i class="fa fa-camera" style="font-size:1.4rem;opacity:.9"></i>
      <div>
        <h3 id="fcTitle">Face Capture</h3>
        <p id="fcSubtitle">Enroll face data — 5 poses required</p>
      </div>
    </div>
    <video id="fcVideo" autoplay playsinline muted></video>
    <canvas id="fcCanvas"></canvas>
    <div id="fcBody">
      <div id="fcPoseBar">
        ${FC_POSES.map((_,i)=>`<div class="fc-pose-dot" id="fcDot${i}"></div>`).join('')}
      </div>
      <div id="fcPoseLabel">Ready to start</div>
      <div id="fcPoseHint">Click "Start Capture" to begin face enrollment</div>
      <div id="fcProgress"><div id="fcProgressBar"></div></div>
      <div id="fcCount">0 / ${FC_POSES.length * FC_IMAGES_PER_POSE} images captured</div>
      <div id="fcStatus"></div>
      <div id="fcButtons">
        <button id="fcBtnStart" onclick="window._fcStartCapture()">
          <i class="fa fa-play"></i> Start Capture
        </button>
        <button id="fcBtnSkip" onclick="window._fcClose()">
          <i class="fa fa-xmark"></i> Skip
        </button>
      </div>
      <div id="fcUploadStatus"></div>
    </div>
  </div>`;
  document.body.appendChild(div);
}

// ── Open modal ────────────────────────────────────────────────
window.openFaceCaptureModal = async function(entityId, role, name) {
  _injectFcModal();
  _fcEntityId = entityId;
  _fcRole     = role || 'student';
  _fcName     = name || entityId;
  _fcCaptured = [];
  _fcPoseIdx  = 0;
  _fcPoseCount= 0;
  _fcActive   = false;

  // Reset UI
  document.getElementById('fcTitle').textContent    = `Face Capture — ${_fcName}`;
  document.getElementById('fcSubtitle').textContent = `ID: ${entityId} | Role: ${role}`;
  document.getElementById('fcPoseLabel').textContent = 'Ready to start';
  document.getElementById('fcPoseHint').textContent  = 'Click "Start Capture" to begin face enrollment';
  document.getElementById('fcProgressBar').style.width = '0%';
  document.getElementById('fcCount').textContent = `0 / ${FC_POSES.length * FC_IMAGES_PER_POSE} images captured`;
  document.getElementById('fcStatus').style.display = 'none';
  document.getElementById('fcUploadStatus').style.display = 'none';
  const btn = document.getElementById('fcBtnStart');
  btn.disabled = false;
  btn.innerHTML = '<i class="fa fa-play"></i> Start Capture';
  btn.onclick = window._fcStartCapture;   // FIX: always reset click handler on re-open
  FC_POSES.forEach((_,i) => {
    const dot = document.getElementById('fcDot'+i);
    if (dot) { dot.className = 'fc-pose-dot'; }
  });

  // Open camera
  try {
    _fcStream = await navigator.mediaDevices.getUserMedia({
      video: { width:{ideal:640}, height:{ideal:480}, facingMode:'user' },
      audio: false
    });
    const vid = document.getElementById('fcVideo');
    vid.srcObject = _fcStream;
    await vid.play();
  } catch(err) {
    _fcShowStatus(`⚠ Camera error: ${err.message}. Grant camera permission and try again.`, 'error');
    document.getElementById('fcBtnStart').disabled = true;
  }

  document.getElementById('fcModal').classList.add('fc-open');
};

// ── Start capturing ───────────────────────────────────────────
window._fcStartCapture = function() {
  if (_fcActive) return;
  _fcActive   = true;
  _fcPoseIdx  = 0;
  _fcPoseCount= 0;
  _fcCaptured = [];
  const btn = document.getElementById('fcBtnStart');
  btn.disabled = true;
  btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Capturing…';
  document.getElementById('fcBtnSkip').textContent = 'Cancel';
  _fcNextPose();
};

function _fcNextPose() {
  if (_fcPoseIdx >= FC_POSES.length) {
    _fcFinish();
    return;
  }
  _fcPoseCount = 0;
  const pose = FC_POSES[_fcPoseIdx];

  // Update dot states
  FC_POSES.forEach((_,i) => {
    const dot = document.getElementById('fcDot'+i);
    if (!dot) return;
    if (i < _fcPoseIdx)       dot.className = 'fc-pose-dot done';
    else if (i === _fcPoseIdx) dot.className = 'fc-pose-dot active';
    else                       dot.className = 'fc-pose-dot';
  });

  document.getElementById('fcPoseLabel').textContent = `Pose ${_fcPoseIdx+1}/5: ${pose.label}`;
  document.getElementById('fcPoseHint').textContent  = pose.hint;
  _fcShowStatus(`Get ready… ${pose.label}`, 'info');

  // Brief countdown then start shooting
  setTimeout(() => {
    _fcShowStatus(`Capturing ${pose.label}…`, 'info');
    _fcCapTimer = setInterval(_fcCaptureFrame, FC_CAPTURE_INTERVAL);
  }, 1200);
}

function _fcCaptureFrame() {
  if (!_fcActive) { clearInterval(_fcCapTimer); return; }
  const vid    = document.getElementById('fcVideo');
  const canvas = document.getElementById('fcCanvas');
  canvas.width  = vid.videoWidth  || 640;
  canvas.height = vid.videoHeight || 480;
  canvas.getContext('2d').drawImage(vid, 0, 0);

  canvas.toBlob(blob => {
    if (!blob) return;
    _fcCaptured.push({ blob, pose: FC_POSES[_fcPoseIdx].key });
    _fcPoseCount++;

    const total    = _fcCaptured.length;
    const maxTotal = FC_POSES.length * FC_IMAGES_PER_POSE;
    document.getElementById('fcProgressBar').style.width = `${(total/maxTotal)*100}%`;
    document.getElementById('fcCount').textContent = `${total} / ${maxTotal} images captured`;

    if (_fcPoseCount >= FC_IMAGES_PER_POSE) {
      clearInterval(_fcCapTimer);
      _fcCapTimer = null;
      // Mark dot done
      const dot = document.getElementById('fcDot'+_fcPoseIdx);
      if (dot) dot.className = 'fc-pose-dot done';
      _fcPoseIdx++;
      setTimeout(_fcNextPose, 600);
    }
  }, 'image/jpeg', 0.88);
}

function _fcFinish() {
  _fcActive = false;
  clearInterval(_fcCapTimer);
  document.getElementById('fcPoseLabel').textContent = 'All poses captured!';
  document.getElementById('fcPoseHint').textContent  = 'Uploading face images to server…';
  _fcShowStatus('⬆ Uploading images to server…', 'info');
  FC_POSES.forEach((_,i) => {
    const dot = document.getElementById('fcDot'+i);
    if (dot) dot.className = 'fc-pose-dot done';
  });
  document.getElementById('fcProgressBar').style.width = '100%';
  const btn = document.getElementById('fcBtnStart');
  btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Uploading…';
  _fcUpload();
}

// async function _fcUpload() {
//   try {
//     // const token = localStorage.getItem('authToken') || localStorage.getItem('token') || '';
//     sessionStorage.getItem('_token') ||
//     localStorage.getItem('authToken') ||
//     localStorage.getItem('token') ||
//     ''
    
    
//     const form  = new FormData();
//     form.append('entity_id', _fcEntityId);
//     form.append('role', _fcRole);

//     _fcCaptured.forEach((item, i) => {
//       const filename = `${_fcEntityId}_${item.pose}_${String(i).padStart(4,'0')}.jpg`;
//       form.append('files', item.blob, filename);
//     });
     async function _fcUpload() {
  try {

    const token =
      sessionStorage.getItem('_token') ||
      localStorage.getItem('authToken') ||
      localStorage.getItem('token') ||
      '';

    const form = new FormData();
    form.append('entity_id', _fcEntityId);
    form.append('role', _fcRole);

    _fcCaptured.forEach((item, i) => {
      const filename = `${_fcEntityId}_${item.pose}_${String(i).padStart(4,'0')}.jpg`;
      form.append('files', item.blob, filename);
    }); 
    const res = await fetch('/api/enroll/face-images', {
      method: 'POST',
      headers: token ? { 'Authorization': 'Bearer '+token } : {},
      body: form,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    const data = await res.json();

    // Success
    const upEl = document.getElementById('fcUploadStatus');
    upEl.style.display = '';
    upEl.style.background = '#f0fdf4';
    upEl.style.color = '#15803d';
    upEl.style.border = '1.5px solid #86efac';
    upEl.innerHTML = `<i class="fa fa-circle-check"></i> <strong>${data.count || _fcCaptured.length} images saved</strong> for <strong>${_fcName}</strong>.<br>
      <small style="color:#64748b">Run model training to activate face recognition for this person.</small>`;
    document.getElementById('fcPoseHint').textContent = 'Face enrollment complete!';
    _fcShowStatus('✓ Upload complete!', 'success');
    const btn = document.getElementById('fcBtnStart');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa fa-check"></i> Done — Close';
    btn.onclick = window._fcClose;
    document.getElementById('fcBtnSkip').style.display = 'none';
    if (typeof toast === 'function') toast(`✓ Face images saved for ${_fcName}`, 'success');
  } catch(err) {
    _fcShowStatus(`Upload failed: ${err.message}`, 'error');
    const btn = document.getElementById('fcBtnStart');
    btn.disabled = false;
    btn.innerHTML = '<i class="fa fa-rotate-right"></i> Retry Upload';
    btn.onclick = _fcUpload;
    if (typeof toast === 'function') toast('Face upload failed: '+err.message, 'error');
  }
}

function _fcShowStatus(msg, type) {
  const el = document.getElementById('fcStatus');
  if (!el) return;
  el.style.display = '';
  const colors = {
    info:    { bg:'#f0f9ff', color:'#0284c7' },
    success: { bg:'#f0fdf4', color:'#15803d' },
    error:   { bg:'#fff1f2', color:'#be123c' },
  };
  const c = colors[type] || colors.info;
  el.style.background = c.bg;
  el.style.color      = c.color;
  el.textContent      = msg;
}

// ── Close modal & stop camera ─────────────────────────────────
window._fcClose = function() {
  _fcActive = false;
  clearInterval(_fcCapTimer);
  if (_fcStream) {
    _fcStream.getTracks().forEach(t => t.stop());
    _fcStream = null;
  }
  const vid = document.getElementById('fcVideo');
  if (vid) { vid.srcObject = null; }
  const modal = document.getElementById('fcModal');
  if (modal) modal.classList.remove('fc-open');
  // Reset button for next use
  const btn = document.getElementById('fcBtnStart');
  if (btn) {
    btn.onclick   = window._fcStartCapture;
    btn.innerHTML = '<i class="fa fa-play"></i> Start Capture';
    btn.disabled  = false;
  }
  const skip = document.getElementById('fcBtnSkip');
  if (skip) { skip.style.display=''; skip.textContent = 'Skip'; }
};

})(); // end IIFE
// ── Universal Table Row Action Menu Dropdown ─────────────────
window.toggleActionMenu = function(event, menuId) {
  event.stopPropagation();
  const menu = document.getElementById(menuId);
  if (!menu) return;
  const isShown = menu.classList.contains('show');
  document.querySelectorAll('.action-dropdown-menu.show').forEach(m => m.classList.remove('show'));
  document.querySelectorAll('.btn-action-trigger.active').forEach(b => b.classList.remove('active'));
  if (!isShown) {
    menu.classList.add('show');
    event.currentTarget.classList.add('active');
  }
};

if (!window._actionMenuClickAttached) {
  window._actionMenuClickAttached = true;
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.row-action-wrap')) {
      document.querySelectorAll('.action-dropdown-menu.show').forEach(m => m.classList.remove('show'));
      document.querySelectorAll('.btn-action-trigger.active').forEach(b => b.classList.remove('active'));
    }
  });
}

// ── Smart Auto-Derivation (Register No -> Dept, Year, Course, Roll No) ──
window.onStudentRegInput = function(val) {
  if (!val) return;
  const clean = val.trim().toUpperCase();
  const rollInp = document.getElementById('en_roll');
  if (rollInp && (!rollInp.value || rollInp.value.toUpperCase() === clean.slice(0, -1))) {
    rollInp.value = clean;
  }
  const deptSelect = document.getElementById('en_dept');
  if (deptSelect && (!deptSelect.value || deptSelect.value === '')) {
    const DEPTS = ['CSE','IT','ECE','EEE','MECH','CIVIL','AIDS','AIML','CSBS','BME'];
    for (const d of DEPTS) {
      if (clean.includes(d)) { deptSelect.value = d; break; }
    }
    if (!deptSelect.value && clean.includes('CS')) deptSelect.value = 'CSE';
  }
  const yearSelect = document.getElementById('en_year');
  if (yearSelect && (!yearSelect.value || yearSelect.value === '')) {
    const currentYear = new Date().getFullYear();
    const match = clean.match(/^(\d{2})/);
    if (match) {
      const startYr = 2000 + parseInt(match[1], 10);
      const diff = currentYear - startYr;
      if (diff >= 3) yearSelect.value = '4th Year';
      else if (diff === 2) yearSelect.value = '3rd Year';
      else if (diff === 1) yearSelect.value = '2nd Year';
      else yearSelect.value = '1st Year';
    }
  }
  const courseSelect = document.getElementById('en_course');
  if (courseSelect && !courseSelect.value) {
    courseSelect.value = 'B.E';
  }
};

// ── Smart Voice Form Fill (Web Speech API) ───────────────────
window.startVoiceEnroll = function(role) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    toast('Voice recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.', 'warn');
    return;
  }
  const btn = document.getElementById('btnVoiceFillStu');
  const reco = new SpeechRecognition();
  reco.lang = 'en-IN';
  reco.continuous = false;
  reco.interimResults = false;

  if (btn) {
    btn.style.background = '#ef4444';
    btn.innerHTML = '<i class="fa fa-microphone fa-beat"></i> <span>Listening...</span>';
  }
  toast('🎙️ Listening... Say: Name, Register number, Department, Mobile number', 'info');

  reco.onresult = function(event) {
    const text = event.results[0][0].transcript;
    toast('🎙️ Heard: "' + text + '"', 'success');
    parseVoiceToForm(text, role);
  };
  reco.onerror = function(err) {
    toast('Voice input notice: ' + (err.error || 'Check microphone permission'), 'warn');
  };
  reco.onend = function() {
    if (btn) {
      btn.style.background = '#0284c7';
      btn.innerHTML = '<i class="fa fa-microphone"></i> <span>Voice Fill</span>';
    }
  };
  try {
    reco.start();
  } catch(e) {
    console.warn('SpeechRecognition start error:', e);
  }
};

function parseVoiceToForm(text, role) {
  if (!text) return;
  const lower = text.toLowerCase();
  
  // 1. Phone number (10 digits)
  const phoneMatch = text.replace(/[^0-9]/g, '').match(/\d{10}/);
  if (phoneMatch) {
    const mobInp = document.getElementById(role === 'student' ? 'en_smob' : 'sf_mob');
    if (mobInp) mobInp.value = phoneMatch[0];
  }

  // 2. Register No
  const regMatch = text.match(/\b(\d{2}[A-Za-z]{2,4}\d{2,6}|\d{6,12})\b/i);
  if (regMatch) {
    const regInp = document.getElementById(role === 'student' ? 'en_reg' : 'sf_id');
    if (regInp) {
      regInp.value = regMatch[0].toUpperCase();
      if (role === 'student') window.onStudentRegInput(regInp.value);
    }
  }

  // 3. Department
  const depts = ['CSE','IT','ECE','EEE','MECH','CIVIL','AIDS','AIML','CSBS','BME'];
  for (const d of depts) {
    if (lower.includes(d.toLowerCase())) {
      const dSel = document.getElementById(role === 'student' ? 'en_dept' : 'sf_dept');
      if (dSel) dSel.value = d;
      break;
    }
  }

  // 4. Name extraction
  let nameStr = '';
  const namePattern = /(?:name\s+is|name|i am|student)\s+([A-Za-z\s]+?)(?:department|reg|roll|mobile|year|$)/i;
  const nameMatch = text.match(namePattern);
  if (nameMatch) {
    nameStr = nameMatch[1].trim();
  } else if (!regMatch && !phoneMatch) {
    nameStr = text.trim();
  }
  if (nameStr) {
    const parts = nameStr.split(/\s+/);
    if (role === 'student') {
      const fInp = document.getElementById('en_fname');
      const lInp = document.getElementById('en_lname');
      if (fInp) fInp.value = parts[0] || '';
      if (lInp) lInp.value = parts.slice(1).join(' ') || (parts[0] ? '.' : '');
    }
  }
}
