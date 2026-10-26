// =============================================================
// academics.js — NEW FILE (additive only)
// Extends the global `api` object and provides the Academics
// page (CGPA & backlog tracking). Loaded via a new <script> tag
// in index.html, AFTER features.js — does not touch any existing
// file's logic.
// =============================================================

Object.assign(api, {
  academicsFor:   (sid)            => apiFetch('/api/academics/' + encodeURIComponent(sid)),
  academicsSave:  (data)           => apiFetch('/api/academics', { method: 'POST', body: JSON.stringify(data) }),
  academicsBacklogs: (dept)        => apiFetch('/api/academics/backlogs' + (dept ? ('?dept=' + encodeURIComponent(dept)) : '')),
  academicsCgpaSummary: (dept)     => apiFetch('/api/academics/cgpa-summary' + (dept ? ('?dept=' + encodeURIComponent(dept)) : '')),
});

let _acadRows = [];
let _acadFilter = 'all';
let _acadSortKey = null;
let _acadSortDir = 1;

async function renderAcademicsPage() {
  const ds = document.getElementById('acadDeptFilter');
  if (ds && ds.options.length <= 1 && typeof DEPT_LIST !== 'undefined') {
    DEPT_LIST.forEach(d => { ds.innerHTML += `<option value="${d.key}">${d.key}</option>`; });
  }
  await Promise.all([_acadLoadKpis(), _acadLoadTable()]);
}

async function _acadLoadKpis() {
  const strip = document.getElementById('acadKpiStrip');
  if (!strip) return;
  const dept = document.getElementById('acadDeptFilter')?.value || '';
  try {
    const s = await api.academicsCgpaSummary(dept);
    const avgCgpa = s.avg_cgpa ?? '—';
    strip.innerHTML = `
      <div class="kpi-card" style="--kc:#e8f0fe"><div class="kpi-icon" style="color:#4da6f5"><i class="fa fa-graduation-cap"></i></div><div class="kpi-val">${s.total_records ?? 0}</div><div class="kpi-lbl">Academic Records</div></div>
      <div class="kpi-card" style="--kc:#e8f6f0"><div class="kpi-icon" style="color:#4ecba8"><i class="fa fa-star"></i></div><div class="kpi-val">${avgCgpa}</div><div class="kpi-lbl">Avg CGPA</div></div>
      <div class="kpi-card" style="--kc:#fde8e8"><div class="kpi-icon" style="color:#e05454"><i class="fa fa-triangle-exclamation"></i></div><div class="kpi-val">${s.students_with_backlogs ?? 0}</div><div class="kpi-lbl">Students with Backlogs</div></div>
      <div class="kpi-card" style="--kc:#fef3cd"><div class="kpi-icon" style="color:#f6c90e"><i class="fa fa-list-ol"></i></div><div class="kpi-val">${s.total_backlog_count ?? 0}</div><div class="kpi-lbl">Total Backlog Count</div></div>`;
  } catch (e) {
    strip.innerHTML = `<div style="color:var(--coral-d,#e05454);padding:12px">${e.message}</div>`;
  }
}

async function _acadLoadTable() {
  const tbody = document.getElementById('acadTbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:24px"><i class="fa fa-spinner fa-spin"></i></td></tr>';
  const dept = document.getElementById('acadDeptFilter')?.value || '';
  try {
    _acadRows = await api.academicsBacklogs(dept); // backend: backlog_count >= 0 when no dept filter just returns all w/ backlog>0; for "All" view we still want full list
    if (_acadFilter !== 'backlog') {
      // also fetch ALL records (not just backlog) for the default 'all' view
      try {
        const all = await apiFetch('/api/academics/all' + (dept ? ('?dept=' + encodeURIComponent(dept)) : ''));
        _acadRows = all;
      } catch (_) { /* fallback: keep backlog-only rows if /all isn't available */ }
    }
    _acadRenderRows();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:20px;color:var(--coral-d,#e05454)">${e.message}</td></tr>`;
  }
}

function _acadRenderRows() {
  const tbody = document.getElementById('acadTbody');
  if (!tbody) return;
  let rows = _acadFilter === 'backlog' ? _acadRows.filter(r => (r.backlog_count || 0) > 0) : _acadRows.slice();

  if (_acadSortKey) {
    rows.sort((a, b) => {
      const av = a[_acadSortKey] ?? 0, bv = b[_acadSortKey] ?? 0;
      if (typeof av === 'string') return av.localeCompare(bv) * _acadSortDir;
      return (av - bv) * _acadSortDir;
    });
  }

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text3,#888)">No academic records found.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(r => {
    const backlogHigh = (r.backlog_count || 0) > 2;
    return `<tr${backlogHigh ? ' style="background:#fde8e8"' : ''}>
      <td>${_esc ? _esc(r.name || r.student_id) : (r.name || r.student_id)}</td>
      <td><code>${r.student_id}</code></td>
      <td>${r.dept || r.department || '—'}</td>
      <td>${r.semester ?? '—'}</td>
      <td>${r.cgpa ?? '—'}</td>
      <td>${r.sgpa ?? '—'}</td>
      <td style="font-weight:700;color:${backlogHigh ? '#e05454' : 'inherit'}">${r.backlog_count ?? 0}</td>
      <td style="font-size:.78rem">${r.backlog_subjects || '—'}</td>
      <td style="font-size:.74rem;color:var(--text3,#888)">${(r.updated_at || '').slice(0, 10) || '—'}</td>
    </tr>`;
  }).join('');
}

function acadFilter(type, btn) {
  _acadFilter = type;
  document.querySelectorAll('#pg-academics .tab-b').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  _acadRenderRows();
}

function acadSort(key) {
  if (_acadSortKey === key) { _acadSortDir *= -1; } else { _acadSortKey = key; _acadSortDir = -1; }
  _acadRenderRows();
}

function openAcademicRecordModal() {
  ['acadStudentId','acadCgpa','acadSgpa','acadBacklogSubjects'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  const sem = document.getElementById('acadSemester'); if (sem) sem.value = 1;
  const bc = document.getElementById('acadBacklogCount'); if (bc) bc.value = 0;
  document.getElementById('acadModal')?.classList.remove('dn');
}

async function saveAcademicRecord() {
  const student_id = document.getElementById('acadStudentId')?.value.trim();
  const semester = +(document.getElementById('acadSemester')?.value || 1);
  const cgpa = document.getElementById('acadCgpa')?.value;
  const sgpa = document.getElementById('acadSgpa')?.value;
  const backlog_count = +(document.getElementById('acadBacklogCount')?.value || 0);
  const backlog_subjects = document.getElementById('acadBacklogSubjects')?.value.trim() || '';

  if (!student_id) { if (window.toast) toast('Student ID is required', 'warn'); return; }

  try {
    await api.academicsSave({
      student_id, semester,
      cgpa: cgpa ? parseFloat(cgpa) : null,
      sgpa: sgpa ? parseFloat(sgpa) : null,
      backlog_count, backlog_subjects,
    });
    if (window.toast) toast('Academic record saved!', 'success');
    if (typeof closeModal === 'function') closeModal('acadModal');
    await renderAcademicsPage();
  } catch (e) {
    if (window.toast) toast('Save failed: ' + e.message, 'error');
  }
}
