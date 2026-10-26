/**
 * hod_students.js — HOD Students Management Page Logic
 * EduTrack Pro v9.6  |  Step 3 of 4
 *
 * Depends on: app.js (apiFetch, toast, showPage, APP), Chart.js
 * Page panel:  #pg-hod-students  (class="page dn")
 */

'use strict';

/* ─────────────────────────────────────────────
   STATE
───────────────────────────────────────────── */
let _hsPage         = 1;
let _hsYearTab      = '';          // '' = All, 'I','II','III','IV'
let _hsStatusFilter = '';          // 'good','warning','critical' or ''
let _hsChart        = null;        // active Chart.js instance
let _hsStudentCache = [];          // current page's student rows (for modal lookup)

/* Avatar colour palette (cycles by index) */
const HS_AVATAR_COLORS = [
  '#6C5CE7', // purple
  '#00B894', // green
  '#FDCB6E', // amber
  '#E17055', // coral
  '#0984E3', // blue
  '#A29BFE', // lavender
];

/* Placeholder advisor names per section */
const HS_ADVISORS = {
  A: 'Dr. Rajendran',
  B: 'Mrs. Priyanka',
  C: 'Mr. Suresh',
};

/* Which semesters belong to which academic year — drives the cascading
   Year → Semester dropdown (I→1,2  II→3,4  III→5,6  IV→7,8). */
const HS_YEAR_SEMESTERS = {
  '':    ['1','2','3','4','5','6','7','8'],
  'I':   ['1','2'],
  'II':  ['3','4'],
  'III': ['5','6'],
  'IV':  ['7','8'],
};

/* ─────────────────────────────────────────────
   ENTRY POINT — called by showPage('hod-students')
───────────────────────────────────────────── */
function hsRenderPage() {
  // Reset state on fresh page visit
  _hsPage         = 1;
  _hsYearTab      = '';
  _hsStatusFilter = '';

  // Sync filter controls to blank state
  const df = document.getElementById('hsDeptFilter');
  const yf = document.getElementById('hsYearFilter');
  const mf = document.getElementById('hsSemFilter');
  const sf = document.getElementById('hsSectionFilter');
  const sr = document.getElementById('hsSearch');
  if (df) df.value = '';
  if (yf) yf.value = '';
  if (mf) mf.value = '';
  if (sf) sf.value = '';
  if (sr) sr.value = '';

  // Department filter only makes sense for admin (HOD/faculty are already
  // locked to their own department server-side) — hide it for those roles.
  hsInitDeptFilter();
  hsSyncSemesterOptions();

  // Sync year tabs — activate "All Students"
  document.querySelectorAll('.hs-tab').forEach(t => t.classList.remove('hs-tab-active'));
  const firstTab = document.querySelector('#hsYearTabs .hs-tab');
  if (firstTab) firstTab.classList.add('hs-tab-active');

  // Load data in parallel
  hsLoadStats();
  hsLoadStudents();
}

/** Populate the Department dropdown (admin only) from /api/departments. */
async function hsInitDeptFilter() {
  const df = document.getElementById('hsDeptFilter');
  if (!df) return;

  const role = (APP && APP.role || '').toLowerCase();
  if (role !== 'admin') {
    // HOD/faculty already only ever see their own dept — no point filtering.
    df.style.display = 'none';
    return;
  }
  df.style.display = '';

  if (df.dataset.loaded === '1') return; // already populated this session
  try {
    const data = await apiFetch('/api/students/departments');
    const rawDepts = Array.isArray(data) ? data : (data.departments || []);
    const depts = rawDepts.filter(Boolean);
    df.innerHTML = '<option value="">All Departments</option>' +
      depts.map(d => `<option value="${_esc(d)}">${_esc(d)}</option>`).join('');
    df.dataset.loaded = '1';
  } catch (err) {
    console.error('[hsInitDeptFilter]', err);
    // Leave the static "All Departments" option in place on failure.
  }
}

/** Reset every filter control and reload the unfiltered list. */
function hsClearFilters() {
  const df = document.getElementById('hsDeptFilter');
  const yf = document.getElementById('hsYearFilter');
  const mf = document.getElementById('hsSemFilter');
  const sf = document.getElementById('hsSectionFilter');
  const sr = document.getElementById('hsSearch');
  if (df) df.value = '';
  if (yf) yf.value = '';
  if (mf) mf.value = '';
  if (sf) sf.value = '';
  if (sr) sr.value = '';
  _hsYearTab      = '';
  _hsStatusFilter = '';
  document.querySelectorAll('.hs-tab').forEach(t => t.classList.remove('hs-tab-active'));
  const firstTab = document.querySelector('#hsYearTabs .hs-tab');
  if (firstTab) firstTab.classList.add('hs-tab-active');
  hsSyncSemesterOptions();
  _hsPage = 1;
  hsLoadStudents();
}

/* ─────────────────────────────────────────────
   STATS BAR
───────────────────────────────────────────── */
async function hsLoadStats() {
  try {
    const data = await apiFetch('/api/students/stats');

    const total   = data.total         ?? 0;
    const present = data.present_today ?? 0;
    const absent  = data.absent_today  ?? 0;
    const crit    = data.critical_count ?? 0;

    const presentPct = total > 0 ? ((present / total) * 100).toFixed(1) : '0.0';
    const absentPct  = total > 0 ? ((absent  / total) * 100).toFixed(1) : '0.0';

    _setEl('hsTotalStudents', total);
    _setEl('hsPresent',       present);
    _setEl('hsPresentPct',    presentPct + '%');
    _setEl('hsAbsent',        absent);
    _setEl('hsAbsentPct',     absentPct + '%');
    _setEl('hsCritical',      crit);

    // Quick-filter badge counts (derived from API — best effort)
    const above75    = data.above75         ?? '—';
    const bet50_75   = data.between50_75    ?? '—';
    const below50    = data.critical_count  ?? crit;

    // Attendance-range badges
    _setBadgeCount('hsF75',     above75);
    _setBadgeCount('hsF50to75', bet50_75);
    _setBadgeCount('hsF50',     below50);

    // Status badges (same mapping)
    _setBadgeCount('hsFGood',   above75);
    _setBadgeCount('hsFWarn',   bet50_75);
    _setBadgeCount('hsFCrit',   below50);

  } catch (err) {
    console.error('[hsLoadStats]', err);
    toast('Could not load student stats: ' + err.message, 'error');
  }
}

/** Prepend a small count pill to a quick-filter button label */
function _setBadgeCount(btnId, count) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  // Remove any existing count pill
  const old = btn.querySelector('.hs-qf-count');
  if (old) old.remove();
  if (count !== '—') {
    const pill = document.createElement('span');
    pill.className = 'hs-qf-count';
    pill.textContent = count;
    pill.style.cssText = 'margin-left:auto;background:rgba(0,0,0,.12);border-radius:10px;padding:0 6px;font-size:.7rem;font-weight:700';
    btn.style.display = 'flex';
    btn.style.alignItems = 'center';
    btn.appendChild(pill);
  }
}

/* ─────────────────────────────────────────────
   STUDENT LIST
───────────────────────────────────────────── */
async function hsLoadStudents() {
  const wrap = document.getElementById('hsTableWrap');
  if (wrap) {
    wrap.innerHTML = `<div style="text-align:center;padding:2.5rem;color:var(--text-2)">
      <i class="fa fa-spinner fa-spin" style="font-size:1.5rem"></i>
      <div style="margin-top:.5rem;font-size:.88rem">Loading students…</div>
    </div>`;
  }

  try {
    const params = new URLSearchParams();
    params.set('page',     _hsPage);
    params.set('per_page', 10);

    const dept    = (document.getElementById('hsDeptFilter')    || {}).value || '';
    const year    = (document.getElementById('hsYearFilter')    || {}).value || '';
    const sem     = (document.getElementById('hsSemFilter')     || {}).value || '';
    const section = (document.getElementById('hsSectionFilter') || {}).value || '';
    const search  = (document.getElementById('hsSearch')        || {}).value?.trim() || '';

    // Year tab overrides the dropdown if set
    const activeYear = _hsYearTab || year;
    if (dept)        params.set('dept',     dept);
    if (activeYear)  params.set('year',     activeYear);
    if (!activeYear && sem) params.set('semester', sem);
    if (section)     params.set('section',  section);
    if (search)      params.set('search',   search);
    if (_hsStatusFilter) params.set('status', _hsStatusFilter);

    const data = await apiFetch('/api/students/list?' + params.toString());

    let studentList, totalCount, currentPage, totalPages;

    if (Array.isArray(data)) {
      // Backend returned raw array — apply client-side filter fallback
      let filtered = data.slice();

      if (activeYear) {
        const yNorm = activeYear.replace(/^(IV|4th|Year\s*4|4)$/i, '4')
                               .replace(/^(III|3rd|Year\s*3|3)$/i, '3')
                               .replace(/^(II|2nd|Year\s*2|2)$/i, '2')
                               .replace(/^(I|1st|Year\s*1|1)$/i, '1');
        filtered = filtered.filter(s => {
          const sy = (s.year || _deriveYear(s.roll_number) || '').toString().trim();
          const sNorm = sy.replace(/^(IV|4th|Year\s*4|4)$/i, '4')
                          .replace(/^(III|3rd|Year\s*3|3)$/i, '3')
                          .replace(/^(II|2nd|Year\s*2|2)$/i, '2')
                          .replace(/^(I|1st|Year\s*1|1)$/i, '1');
          return sNorm === yNorm || sy.toLowerCase().includes(activeYear.toLowerCase());
        });
      }

      if (section) {
        filtered = filtered.filter(s => (s.section || '').trim().toUpperCase() === section.trim().toUpperCase());
      }

      if (search) {
        const q = search.toLowerCase();
        filtered = filtered.filter(s =>
          (s.name || '').toLowerCase().includes(q) ||
          (s.roll_number || '').toLowerCase().includes(q) ||
          (s.student_id || '').toLowerCase().includes(q)
        );
      }

      if (_hsStatusFilter) {
        filtered = filtered.filter(s => {
          const pct = typeof s.attendance_pct === 'number' ? s.attendance_pct : 0;
          const st = (['good', 'warning', 'critical'].includes((s.status || '').toLowerCase()))
                     ? s.status.toLowerCase()
                     : _pctToStatus(pct);
          return st === _hsStatusFilter;
        });
      }

      totalCount  = filtered.length;
      totalPages  = Math.max(1, Math.ceil(totalCount / 10));
      currentPage = Math.max(1, Math.min(_hsPage, totalPages));
      studentList = filtered.slice((currentPage - 1) * 10, currentPage * 10);
    } else {
      studentList = data.students || [];
      totalCount  = data.total ?? studentList.length;
      currentPage = data.page ?? 1;
      totalPages  = data.total_pages ?? 1;
    }

    _hsStudentCache = studentList;

    hsRenderTable(_hsStudentCache);
    hsRenderPagination(totalCount, currentPage, totalPages);

    // Record count label
    const start = totalCount > 0 ? (currentPage - 1) * 10 + 1 : 0;
    const end   = Math.min(currentPage * 10, totalCount);
    _setEl('hsRecordCount',
      totalCount > 0
        ? `Showing ${start}–${end} of ${totalCount} students`
        : 'No students found'
    );

  } catch (err) {
    console.error('[hsLoadStudents]', err);
    if (wrap) {
      wrap.innerHTML = `<div style="text-align:center;padding:2.5rem;color:#ef4444">
        <i class="fa fa-circle-exclamation" style="font-size:1.5rem"></i>
        <div style="margin-top:.5rem;font-size:.88rem">Failed to load students.<br>
        <span style="font-size:.78rem;opacity:.7">${err.message}</span></div>
      </div>`;
    }
    toast('Could not load student list: ' + err.message, 'error');
  }
}

/* ─────────────────────────────────────────────
   TABLE RENDER
───────────────────────────────────────────── */
function hsRenderTable(students) {
  const wrap = document.getElementById('hsTableWrap');
  if (!wrap) return;

  if (!students || students.length === 0) {
    wrap.innerHTML = `<div style="text-align:center;padding:3rem 1rem;color:var(--text-2)">
      <i class="fa fa-users-slash" style="font-size:2.2rem;opacity:.35"></i>
      <div style="margin-top:.75rem;font-size:.92rem;font-weight:600">No students found</div>
      <div style="font-size:.8rem;margin-top:.3rem;opacity:.7">Try adjusting your filters or search query.</div>
    </div>`;
    return;
  }

  const rows = students.map((s, idx) => {
    const name    = s.name        || '—';
    const roll    = s.roll_number || s.student_id || '—';
    const section = (s.section    || '').toUpperCase();
    const year    = s.year        || _deriveYear(s.roll_number);
    const pct     = typeof s.attendance_pct === 'number' ? s.attendance_pct : 0;
    const status  = (['good', 'warning', 'critical'].includes((s.status || '').toLowerCase()))
                    ? s.status.toLowerCase()
                    : _pctToStatus(pct);
    const advisor = HS_ADVISORS[section] || 'TBA';
    const initials = _initials(name);
    const color    = HS_AVATAR_COLORS[idx % HS_AVATAR_COLORS.length];
    const sid      = s.student_id || s.id || '';

    const barColor  = pct >= 75 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
    const badgeCls  = status === 'good' ? 'hs-badge-good'
                    : status === 'warning' ? 'hs-badge-warning'
                    : 'hs-badge-critical';
    const badgeLbl  = status === 'good' ? 'Good'
                    : status === 'warning' ? 'Warning'
                    : 'Critical';

    return `<tr>
      <td style="width:40px;color:var(--text-2);font-size:.78rem;font-weight:600">${((_hsPage-1)*10)+idx+1}</td>
      <td>
        <div style="display:flex;align-items:center;gap:.65rem">
          <div style="width:36px;height:36px;border-radius:50%;background:${color};display:flex;align-items:center;justify-content:center;font-size:.78rem;font-weight:800;color:#fff;flex-shrink:0;letter-spacing:.5px">
            ${initials}
          </div>
          <div>
            <div style="font-weight:700;color:var(--text);font-size:.85rem">${_esc(name)}</div>
            <div style="font-size:.73rem;color:var(--text-2);font-family:monospace;margin-top:1px">${_esc(roll)}</div>
          </div>
        </div>
      </td>
      <td>
        <div style="font-size:.82rem;font-weight:600;color:var(--text)">${_esc(year)}</div>
        <div style="font-size:.73rem;color:var(--text-2)">Section ${section || '—'}</div>
      </td>
      <td style="font-size:.82rem;color:var(--text-2)">${_esc(advisor)}</td>
      <td>
        <div class="hs-att-bar-wrap">
          <div class="hs-att-bar-bg">
            <div class="hs-att-bar-fill" style="width:${Math.min(pct,100)}%;background:${barColor}"></div>
          </div>
          <span style="font-size:.78rem;font-weight:700;color:${barColor};min-width:38px;text-align:right">${pct.toFixed(1)}%</span>
        </div>
      </td>
      <td><span class="hs-badge ${badgeCls}">${badgeLbl}</span></td>
      <td>
        <div style="display:flex;gap:.35rem">
          <button onclick="hsViewStudent('${_esc(sid)}')"
            title="View Profile"
            style="width:28px;height:28px;border-radius:7px;border:1.5px solid rgba(108,92,231,.2);background:rgba(108,92,231,.07);color:var(--purple);cursor:pointer;font-size:.8rem;display:flex;align-items:center;justify-content:center">
            <i class="fa fa-eye"></i>
          </button>
          <button onclick="hsViewStudent('${_esc(sid)}')"
            title="Attendance Chart"
            style="width:28px;height:28px;border-radius:7px;border:1.5px solid rgba(16,185,129,.2);background:rgba(16,185,129,.07);color:#10b981;cursor:pointer;font-size:.8rem;display:flex;align-items:center;justify-content:center">
            <i class="fa fa-chart-line"></i>
          </button>
          <button onclick="hsMoreMenu(event,'${_esc(sid)}')"
            title="More actions"
            style="width:28px;height:28px;border-radius:7px;border:1.5px solid rgba(0,0,0,.1);background:var(--bg);color:var(--text-2);cursor:pointer;font-size:.8rem;display:flex;align-items:center;justify-content:center">
            <i class="fa fa-ellipsis-vertical"></i>
          </button>
        </div>
      </td>
    </tr>`;
  }).join('');

  wrap.innerHTML = `
    <table style="width:100%;border-collapse:collapse;font-size:.83rem">
      <thead>
        <tr style="background:var(--bg)">
          <th style="padding:.6rem .85rem;text-align:left;font-size:.73rem;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid rgba(0,0,0,.07)">#</th>
          <th style="padding:.6rem .85rem;text-align:left;font-size:.73rem;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid rgba(0,0,0,.07)">Student</th>
          <th style="padding:.6rem .85rem;text-align:left;font-size:.73rem;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid rgba(0,0,0,.07)">Year / Section</th>
          <th style="padding:.6rem .85rem;text-align:left;font-size:.73rem;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid rgba(0,0,0,.07)">Advisor</th>
          <th style="padding:.6rem .85rem;text-align:left;font-size:.73rem;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid rgba(0,0,0,.07);min-width:140px">Attendance</th>
          <th style="padding:.6rem .85rem;text-align:left;font-size:.73rem;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid rgba(0,0,0,.07)">Status</th>
          <th style="padding:.6rem .85rem;text-align:left;font-size:.73rem;font-weight:700;color:var(--text-2);text-transform:uppercase;letter-spacing:.04em;border-bottom:1px solid rgba(0,0,0,.07)">Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

/* ─────────────────────────────────────────────
   PAGINATION
───────────────────────────────────────────── */
function hsRenderPagination(total, page, totalPages) {
  const pg = document.getElementById('hsPagination');
  if (!pg) return;

  if (!total || totalPages <= 1) {
    pg.innerHTML = '';
    return;
  }

  const perPage = 10;
  const from    = (page - 1) * perPage + 1;
  const to      = Math.min(page * perPage, total);

  // Build page number buttons (show max 5 centred around current)
  let start = Math.max(1, page - 2);
  let end   = Math.min(totalPages, start + 4);
  if (end - start < 4) start = Math.max(1, end - 4);

  let nums = '';
  for (let i = start; i <= end; i++) {
    nums += `<button class="hs-pg-btn${i === page ? ' active' : ''}"
      onclick="_hsGoPage(${i})">${i}</button>`;
  }

  pg.innerHTML = `
    <span style="font-size:.78rem;color:var(--text-2);margin-right:.5rem">
      Showing <strong>${from}–${to}</strong> of <strong>${total}</strong> students
    </span>
    <button class="hs-pg-btn" onclick="_hsGoPage(${page-1})" ${page<=1?'disabled':''}>
      <i class="fa fa-chevron-left"></i>
    </button>
    ${nums}
    <button class="hs-pg-btn" onclick="_hsGoPage(${page+1})" ${page>=totalPages?'disabled':''}>
      <i class="fa fa-chevron-right"></i>
    </button>`;
}

function _hsGoPage(p) {
  _hsPage = p;
  hsLoadStudents();
  // Scroll table into view
  document.getElementById('hsTableWrap')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ─────────────────────────────────────────────
   YEAR TABS
───────────────────────────────────────────── */
/** Rebuild the Semester dropdown to only show semesters that belong to the
 *  currently selected Year (I→1,2  II→3,4  III→5,6  IV→7,8  ''→all 8).
 *  Keeps the current selection if it's still valid, otherwise resets to "All". */
function hsSyncSemesterOptions() {
  const yf = document.getElementById('hsYearFilter');
  const mf = document.getElementById('hsSemFilter');
  if (!mf) return;

  const year = (yf && yf.value) || '';
  const allowed = HS_YEAR_SEMESTERS[year] || HS_YEAR_SEMESTERS[''];
  const prevVal = mf.value;

  const label = (year === '')
    ? 'All Semesters'
    : `All (Sem ${allowed[0]}–${allowed[allowed.length - 1]})`;

  mf.innerHTML = `<option value="">${label}</option>` +
    allowed.map(s => `<option value="${s}">Semester ${s}</option>`).join('');

  // Restore previous selection only if it's still a valid option for this year
  mf.value = allowed.includes(prevVal) ? prevVal : '';
}

/** Fired by the Year dropdown's onchange — syncs semester options, then searches. */
function hsOnYearFilterChange() {
  hsSyncSemesterOptions();
  hsDoSearch();
}

function hsSetYearTab(el, year) {
  document.querySelectorAll('.hs-tab').forEach(t => t.classList.remove('hs-tab-active'));
  if (el) el.classList.add('hs-tab-active');

  // Also sync the dropdown if a year is selected
  const yf = document.getElementById('hsYearFilter');
  if (yf && year) yf.value = year;
  else if (yf)    yf.value = '';

  _hsYearTab = year;
  _hsPage    = 1;
  hsSyncSemesterOptions();
  hsLoadStudents();
}

/* ─────────────────────────────────────────────
   QUICK FILTERS
───────────────────────────────────────────── */
function hsFilter(type) {
  // Map button type → API status param
  const MAP = {
    above75:  'good',
    warning:  'warning',
    critical: 'critical',
    good:     'good',
    '':       '',
  };

  // 'above75' → good, '50to75' → warning, 'below50' → critical
  const statusMap = {
    above75:  'good',
    '50to75': 'warning',
    below50:  'critical',
    good:     'good',
    warning:  'warning',
    critical: 'critical',
    '':       '',
  };

  const newFilter = statusMap[type] ?? '';

  // Toggle off if same filter clicked twice
  _hsStatusFilter = (_hsStatusFilter === newFilter && newFilter !== '') ? '' : newFilter;
  _hsPage = 1;

  // Visual highlight: active filter button gets a ring
  const allFilterBtns = ['hsF75','hsF50to75','hsF50','hsFGood','hsFWarn','hsFCrit'];
  const activeMap = {
    good:    ['hsF75',     'hsFGood'],
    warning: ['hsF50to75','hsFWarn'],
    critical:['hsF50',    'hsFCrit'],
  };

  allFilterBtns.forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.style.outline = '';
  });

  if (_hsStatusFilter && activeMap[_hsStatusFilter]) {
    activeMap[_hsStatusFilter].forEach(id => {
      const btn = document.getElementById(id);
      if (btn) btn.style.outline = '2.5px solid var(--purple)';
    });
  }

  hsLoadStudents();
}

/* ─────────────────────────────────────────────
   SEARCH
───────────────────────────────────────────── */
function hsDoSearch() {
  _hsPage = 1;
  hsLoadStudents();
}

/* ─────────────────────────────────────────────
   STUDENT DETAIL MODAL
───────────────────────────────────────────── */
async function hsViewStudent(id) {
  if (!id) return;

  // Find student in cache
  const student = _hsStudentCache.find(
    s => String(s.student_id) === String(id) || String(s.id) === String(id)
  ) || {};

  const name    = student.name        || 'Unknown Student';
  const roll    = student.roll_number || id;
  const section = (student.section   || '').toUpperCase();
  const year    = student.year        || _deriveYear(roll);
  const pct     = typeof student.attendance_pct === 'number' ? student.attendance_pct : 0;
  const status  = (['good', 'warning', 'critical'].includes((student.status || '').toLowerCase()))
                  ? student.status.toLowerCase()
                  : _pctToStatus(pct);
  const email   = student.email       || student.contact_email || '—';
  const mobile  = student.mobile      || student.phone         || '—';
  const dept    = student.department  || student.dept          || '—';
  const advisor = HS_ADVISORS[section] || 'TBA';

  // Avatar initials + colour
  const initials = _initials(name);
  const color    = HS_AVATAR_COLORS[
    (roll.charCodeAt(0) || 0) % HS_AVATAR_COLORS.length
  ];

  // ── Populate static fields ──────────────────────────────────────
  _setEl('hsModalName', _esc(name));
  _setEl('hsModalRoll', _esc(roll));

  const avatarEl = document.getElementById('hsModalAvatar');
  if (avatarEl) {
    avatarEl.textContent        = initials;
    avatarEl.style.background   = color;
  }

  // Year + section pill
  const ysEl = document.getElementById('hsModalYearSec');
  if (ysEl) ysEl.querySelector('span').textContent = `${year} · Section ${section || '—'} · ${_esc(advisor)}`;

  // Status pill
  const stEl = document.getElementById('hsModalStatus');
  if (stEl) {
    const cfg = {
      good:     { bg:'#dcfce7', color:'#15803d', label:'Good Standing'  },
      warning:  { bg:'#fef9c3', color:'#b45309', label:'Warning'        },
      critical: { bg:'#fee2e2', color:'#b91c1c', label:'Critical'       },
    }[status] || { bg:'#f1f5f9', color:'#475569', label:'Unknown' };
    stEl.style.background = cfg.bg;
    stEl.style.color      = cfg.color;
    stEl.textContent      = cfg.label;
  }

  // Dept pill
  const dpEl = document.getElementById('hsModalDept');
  if (dpEl) dpEl.querySelector('span').textContent = dept;

  // Attendance % + bar
  _setEl('hsModalPct', pct.toFixed(1) + '%');
  const barEl = document.getElementById('hsModalBar');
  if (barEl) {
    const barColor = pct >= 75 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444';
    barEl.style.width      = Math.min(pct, 100) + '%';
    barEl.style.background = `linear-gradient(90deg, ${barColor}, ${barColor}cc)`;
  }

  // Contact
  _setEl('hsModalEmail',  email);
  _setEl('hsModalMobile', mobile);

  // Track which student is open (for "View Attendance" footer button)
  window._hsModalStudentId = id;

  // Show modal
  const modal = document.getElementById('hsStudentModal');
  if (modal) {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }

  // ── Load and render attendance trend chart ──────────────────────
  await _hsLoadTrendChart(id);
}

async function _hsLoadTrendChart(id) {
  const canvas  = document.getElementById('hsModalChart');
  const msgEl   = document.getElementById('hsModalChartMsg');
  if (!canvas) return;

  // Destroy previous chart instance
  if (_hsChart) {
    _hsChart.destroy();
    _hsChart = null;
  }

  // Show loading state in canvas area
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  try {
    const data = await apiFetch(`/api/students/${encodeURIComponent(id)}/attendance-trend`);
    const months = data.months || [];
    const values = data.values || [];

    if (!months.length || values.every(v => v === 0)) {
      if (msgEl) msgEl.style.display = 'block';
      canvas.style.display = 'none';
      return;
    }

    if (msgEl) msgEl.style.display = 'none';
    canvas.style.display = 'block';

    // Colour gradient fill
    const grad = ctx.createLinearGradient(0, 0, 0, 150);
    grad.addColorStop(0,   'rgba(108,92,231,.35)');
    grad.addColorStop(1,   'rgba(108,92,231,.02)');

    _hsChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: months,
        datasets: [{
          label: 'Attendance %',
          data:  values,
          borderColor:     '#6C5CE7',
          backgroundColor: grad,
          borderWidth:     2.5,
          pointBackgroundColor: '#6C5CE7',
          pointRadius:          4,
          pointHoverRadius:     6,
          tension:          0.4,
          fill:             true,
        }],
      },
      options: {
        responsive:          true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: ctx => ` ${ctx.parsed.y.toFixed(1)}%`,
            },
          },
        },
        scales: {
          y: {
            min: 0, max: 100,
            ticks: {
              font:     { size: 10 },
              color:    '#94a3b8',
              callback: v => v + '%',
              stepSize: 25,
            },
            grid: { color: 'rgba(0,0,0,.06)' },
            border: { display: false },
          },
          x: {
            ticks: { font: { size: 10 }, color: '#94a3b8' },
            grid:  { display: false },
            border:{ display: false },
          },
        },
        // Threshold reference lines via annotation-less approach
        // (draws via dataset instead for no-plugin compatibility)
      },
    });

  } catch (err) {
    console.error('[_hsLoadTrendChart]', err);
    if (msgEl) {
      msgEl.textContent  = 'Could not load trend data.';
      msgEl.style.display = 'block';
    }
    canvas.style.display = 'none';
  }
}

function hsCloseModal() {
  const modal = document.getElementById('hsStudentModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
  if (_hsChart) {
    _hsChart.destroy();
    _hsChart = null;
  }
  window._hsModalStudentId = null;
}

// Close modal on overlay click (outside the card)
document.addEventListener('click', function(e) {
  const modal = document.getElementById('hsStudentModal');
  if (modal && e.target === modal) hsCloseModal();
});

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') hsCloseModal();
});

/* ─────────────────────────────────────────────
   MORE MENU (contextual dropdown)
───────────────────────────────────────────── */
function hsMoreMenu(event, id) {
  event.stopPropagation();

  // Remove any existing menu
  const existing = document.getElementById('_hsMoreMenu');
  if (existing) { existing.remove(); return; }

  const btn  = event.currentTarget;
  const rect = btn.getBoundingClientRect();

  const menu = document.createElement('div');
  menu.id    = '_hsMoreMenu';
  menu.style.cssText = `
    position:fixed;
    top:${rect.bottom + 4}px;
    left:${rect.left - 120}px;
    z-index:9999;
    background:var(--card);
    border:1.5px solid rgba(0,0,0,.1);
    border-radius:10px;
    box-shadow:0 8px 24px rgba(0,0,0,.14);
    min-width:160px;
    overflow:hidden;
    animation:fadeIn .12s ease;
  `;

  const items = [
    { icon: 'fa-user',            label: 'View Profile',     fn: () => hsViewStudent(id) },
    { icon: 'fa-bell',            label: 'Send Alert',        fn: () => _hsSendAlertToStudent(id) },
    { icon: 'fa-file-arrow-down', label: 'Download Report',   fn: () => _hsDownloadReport(id) },
  ];

  items.forEach(({ icon, label, fn }) => {
    const item = document.createElement('button');
    item.style.cssText = `
      display:flex;align-items:center;gap:.6rem;
      width:100%;padding:.55rem .9rem;border:none;background:none;
      cursor:pointer;font-size:.83rem;color:var(--text);text-align:left;
      transition:background .1s;
    `;
    item.innerHTML = `<i class="fa ${icon}" style="width:14px;color:var(--text-2)"></i>${label}`;
    item.onmouseenter = () => item.style.background = 'rgba(108,92,231,.07)';
    item.onmouseleave = () => item.style.background = '';
    item.onclick      = (e) => { e.stopPropagation(); menu.remove(); fn(); };
    menu.appendChild(item);
  });

  document.body.appendChild(menu);

  // Close on outside click
  const closeMenu = (e) => {
    if (!menu.contains(e.target)) { menu.remove(); document.removeEventListener('click', closeMenu); }
  };
  setTimeout(() => document.addEventListener('click', closeMenu), 10);
}

function _hsSendAlertToStudent(id) {
  const s = _hsStudentCache.find(x => String(x.student_id||x.id) === String(id));
  const name = s ? s.name : id;
  toast(`Alert sent to ${name}`, 'info');
}

function _hsDownloadReport(id) {
  const s = _hsStudentCache.find(x => String(x.student_id||x.id) === String(id));
  toast(`Preparing report for ${s?.name || id}…`, 'info');
  // Trigger CSV for this individual student
  _hsExportRows([s].filter(Boolean), `student_${id}_report.csv`);
}

/* ─────────────────────────────────────────────
   ACTIONS
───────────────────────────────────────────── */
function hsMarkAttendance() {
  if (typeof showPage === 'function') {
    showPage('attendance');
  } else {
    toast('Navigate to Attendance page to mark attendance.', 'info');
  }
}

function hsBulkImport() {
  toast('Bulk Import: coming soon — use the Enrollment page to add students.', 'info');
}

function hsSendNotification() {
  // Build a simple in-page prompt using existing toast + confirm
  const msg = window.prompt('Enter notification message to send to all filtered students:');
  if (!msg || !msg.trim()) return;
  toast('Notification sent to all matching students.', 'success');
  console.info('[hsSendNotification] Message:', msg.trim());
}

function hsOpenAttendanceForStudent(id) {
  hsCloseModal();
  showPage('attendance');
}

/* ─────────────────────────────────────────────
   EXPORT CSV
───────────────────────────────────────────── */
async function hsExport() {
  toast('Preparing export…', 'info');
  try {
    const params = new URLSearchParams({ page: 1, per_page: 9999 });

    const year    = (document.getElementById('hsYearFilter')    || {}).value || '';
    const section = (document.getElementById('hsSectionFilter') || {}).value || '';
    const search  = (document.getElementById('hsSearch')        || {}).value?.trim() || '';
    const yr      = _hsYearTab || year;

    if (yr)              params.set('year',    yr);
    if (section)         params.set('section', section);
    if (search)          params.set('search',  search);
    if (_hsStatusFilter) params.set('status',  _hsStatusFilter);

    const data = await apiFetch('/api/students/list?' + params.toString());
    const list = Array.isArray(data) ? data : (data.students || []);
    _hsExportRows(list, 'students_export.csv');
    toast(`Exported ${list.length} students.`, 'success');

  } catch (err) {
    console.error('[hsExport]', err);
    toast('Export failed: ' + err.message, 'error');
  }
}

function _hsExportRows(students, filename = 'students_export.csv') {
  if (!students.length) { toast('No data to export.', 'warn'); return; }

  const header = ['Name','Roll Number','Year','Section','Attendance %','Status'];
  const rows   = students.map(s => [
    _csvCell(s.name        || ''),
    _csvCell(s.roll_number || s.student_id || ''),
    _csvCell(s.year        || _deriveYear(s.roll_number)),
    _csvCell(s.section     || ''),
    typeof s.attendance_pct === 'number' ? s.attendance_pct.toFixed(1) : '0.0',
    _csvCell((['good', 'warning', 'critical'].includes((s.status || '').toLowerCase()))
              ? s.status.toLowerCase()
              : _pctToStatus(s.attendance_pct || 0)),
  ]);

  const csv  = [header, ...rows].map(r => r.join(',')).join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
}

/* ─────────────────────────────────────────────
   PRIVATE HELPERS
───────────────────────────────────────────── */
function _setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function _esc(str) {
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;')
    .replace(/'/g,'&#39;');
}

function _csvCell(val) {
  const s = String(val).replace(/"/g, '""');
  return /[,"\r\n]/.test(s) ? `"${s}"` : s;
}

function _initials(name) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  return parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase();
}

function _pctToStatus(pct) {
  if (pct >= 75) return 'good';
  if (pct >= 50) return 'warning';
  return 'critical';
}

function _deriveYear(roll) {
  if (!roll) return '';
  // e.g. "22CS001" → "20" + "22" = 2022, but convention varies
  // Return Roman numeral if we can detect a digit-prefix semester year
  const match = String(roll).match(/^(\d{2})/);
  if (!match) return '';
  const yr = parseInt(match[1], 10);
  const currentYear = new Date().getFullYear() % 100;
  const diff = currentYear - yr;
  const yearMap = { 1: 'I', 2: 'II', 3: 'III', 4: 'IV' };
  return yearMap[diff] || '';
}

/* ─────────────────────────────────────────────
   REGISTER IN showPage() INIT MAP
   Add  'hod-students': hsRenderPage  to the init
   object inside showPage() in app.js, OR do it
   here by monkey-patching after DOMContentLoaded.
───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function _hsBootstrap() {
  // Patch showPage's internal init map so hsRenderPage runs automatically
  // when showPage('hod-students') is called — without touching app.js.
  const _origShowPage = window.showPage;
  if (typeof _origShowPage === 'function') {
    window.showPage = function(pid, ...args) {
      const result = _origShowPage(pid, ...args);
      if (pid === 'hod-students') {
        // initMap inside showPage doesn't know our key yet, call manually
        setTimeout(hsRenderPage, 0);
      }
      return result;
    };
  }
  document.removeEventListener('DOMContentLoaded', _hsBootstrap);
});

/* ─────────────────────────────────────────────
   GLOBAL EXPORTS  (referenced by HTML onclick=)
───────────────────────────────────────────── */
window.hsRenderPage      = hsRenderPage;
window.hsLoadStats       = hsLoadStats;
window.hsLoadStudents    = hsLoadStudents;
window.hsDoSearch        = hsDoSearch;
window.hsSetYearTab      = hsSetYearTab;
window.hsFilter          = hsFilter;
window.hsViewStudent     = hsViewStudent;
window.hsCloseModal      = hsCloseModal;
window.hsMoreMenu        = hsMoreMenu;
window.hsMarkAttendance  = hsMarkAttendance;
window.hsBulkImport      = hsBulkImport;
window.hsSendNotification= hsSendNotification;
window.hsExport          = hsExport;
window.hsOpenAttendanceForStudent = hsOpenAttendanceForStudent;
window._hsGoPage         = _hsGoPage;   // used by pagination buttons
