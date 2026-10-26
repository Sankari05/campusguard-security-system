// =============================================================
// compliance.js — NEW FILE (additive only)
// Extends the global `api` object and provides the Compliance
// Tracker page (Kanban board) plus the dashboard "Compliance Due"
// KPI loader referenced from renderDashboard() in app.js.
// Loaded via a new <script> tag in index.html, AFTER academics.js.
// =============================================================

Object.assign(api, {
  complianceList:     (dept, category, status) => {
    const qs = new URLSearchParams();
    if (dept) qs.set('dept', dept);
    if (category) qs.set('category', category);
    if (status) qs.set('status', status);
    return apiFetch('/api/compliance' + (qs.toString() ? '?' + qs.toString() : ''));
  },
  complianceCreate:   (data) => apiFetch('/api/compliance', { method: 'POST', body: JSON.stringify(data) }),
  complianceUpdate:   (id, data) => apiFetch('/api/compliance/' + id, { method: 'PUT', body: JSON.stringify(data) }),
  complianceDelete:   (id) => apiFetch('/api/compliance/' + id, { method: 'DELETE' }),
  complianceUpcoming: (days, dept) => {
    const qs = new URLSearchParams();
    if (days) qs.set('days', days);
    if (dept) qs.set('dept', dept);
    return apiFetch('/api/compliance/upcoming' + (qs.toString() ? '?' + qs.toString() : ''));
  },
});

const COMP_STATUSES = ['pending', 'in_progress', 'submitted', 'approved'];

// ── Dashboard KPI hook (called from renderDashboard() in app.js) ──
async function _loadComplianceKpi() {
  const el = document.getElementById('complianceKpiVal');
  if (!el) return;
  try {
    const items = await api.complianceUpcoming(7);
    el.textContent = items.length;
  } catch (e) {
    el.textContent = '—';
  }
}

// ── Compliance Tracker page ─────────────────────────────────────
async function renderCompliancePage() {
  const ds = document.getElementById('compDeptFilter');
  if (ds && ds.options.length <= 1 && typeof DEPT_LIST !== 'undefined') {
    DEPT_LIST.forEach(d => { ds.innerHTML += `<option value="${d.key}">${d.key}</option>`; });
  }
  await Promise.all([_compLoadKpis(), _compLoadBoard()]);
}

async function _compLoadKpis() {
  const strip = document.getElementById('compKpiStrip');
  if (!strip) return;
  const dept = document.getElementById('compDeptFilter')?.value || '';
  try {
    const all = await api.complianceList(dept);
    const upcoming = await api.complianceUpcoming(14, dept);
    const overdue = all.filter(i => i.status !== 'approved' && i.due_date && i.due_date < new Date().toISOString().slice(0, 10));
    const approved = all.filter(i => i.status === 'approved');
    strip.innerHTML = `
      <div class="kpi-card" style="--kc:#e8f0fe"><div class="kpi-icon" style="color:#4da6f5"><i class="fa fa-list-check"></i></div><div class="kpi-val">${all.length}</div><div class="kpi-lbl">Total Items</div></div>
      <div class="kpi-card" style="--kc:#fef3cd"><div class="kpi-icon" style="color:#f6c90e"><i class="fa fa-clock"></i></div><div class="kpi-val">${upcoming.length}</div><div class="kpi-lbl">Due in 14 Days</div></div>
      <div class="kpi-card" style="--kc:#fde8e8"><div class="kpi-icon" style="color:#e05454"><i class="fa fa-triangle-exclamation"></i></div><div class="kpi-val">${overdue.length}</div><div class="kpi-lbl">Overdue</div></div>
      <div class="kpi-card" style="--kc:#e8f6f0"><div class="kpi-icon" style="color:#4ecba8"><i class="fa fa-circle-check"></i></div><div class="kpi-val">${approved.length}</div><div class="kpi-lbl">Approved</div></div>`;
  } catch (e) {
    strip.innerHTML = `<div style="color:var(--coral-d,#e05454);padding:12px">${e.message}</div>`;
  }
}

async function _compLoadBoard() {
  COMP_STATUSES.forEach(s => {
    const col = document.getElementById('compCol-' + s);
    if (col) col.innerHTML = '<div style="text-align:center;padding:10px"><i class="fa fa-spinner fa-spin"></i></div>';
  });
  const dept = document.getElementById('compDeptFilter')?.value || '';
  const category = document.getElementById('compCategoryFilter')?.value || '';
  try {
    const items = await api.complianceList(dept, category);
    const today = new Date().toISOString().slice(0, 10);
    COMP_STATUSES.forEach(status => {
      const col = document.getElementById('compCol-' + status);
      if (!col) return;
      const colItems = items.filter(i => i.status === status);
      if (!colItems.length) {
        col.innerHTML = '<div style="text-align:center;padding:14px;color:var(--text3,#aaa);font-size:.76rem">No items</div>';
        return;
      }
      col.innerHTML = colItems.map(i => {
        const overdue = i.status !== 'approved' && i.due_date && i.due_date < today;
        return `<div class="comp-item">
          <span class="ci-del" onclick="deleteComplianceItem(${i.id})" title="Delete"><i class="fa fa-trash"></i></span>
          <div class="ci-title">${_esc ? _esc(i.title) : i.title}</div>
          <div style="font-size:.74rem;color:var(--text3,#888)">${i.dept || '—'} · ${i.category || '—'}</div>
          <div class="ci-meta">
            <span class="${overdue ? 'ci-overdue' : ''}"><i class="fa fa-calendar"></i> ${i.due_date || 'No due date'}</span>
            <span>${i.assigned_to || ''}</span>
          </div>
          <select onchange="moveComplianceItem(${i.id}, this.value)">
            ${COMP_STATUSES.map(s => `<option value="${s}" ${s === i.status ? 'selected' : ''}>${s.replace('_', ' ')}</option>`).join('')}
          </select>
        </div>`;
      }).join('');
    });
  } catch (e) {
    COMP_STATUSES.forEach(s => {
      const col = document.getElementById('compCol-' + s);
      if (col) col.innerHTML = `<div style="color:var(--coral-d,#e05454);font-size:.76rem;padding:8px">${e.message}</div>`;
    });
  }
}

async function moveComplianceItem(id, newStatus) {
  try {
    await api.complianceUpdate(id, { status: newStatus });
    await renderCompliancePage();
  } catch (e) {
    if (window.toast) toast('Update failed: ' + e.message, 'error');
  }
}

async function deleteComplianceItem(id) {
  if (!confirm('Delete this compliance item?')) return;
  try {
    await api.complianceDelete(id);
    await renderCompliancePage();
  } catch (e) {
    if (window.toast) toast('Delete failed: ' + e.message, 'error');
  }
}

function openComplianceModal() {
  ['compDept','compTitle','compDescription','compAssignedTo','compDueDate'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
  const cat = document.getElementById('compCategory'); if (cat) cat.value = 'NBA';
  document.getElementById('compModal')?.classList.remove('dn');
}

async function saveComplianceItem() {
  const dept = document.getElementById('compDept')?.value.trim() || null;
  const category = document.getElementById('compCategory')?.value || 'NBA';
  const title = document.getElementById('compTitle')?.value.trim();
  const description = document.getElementById('compDescription')?.value.trim() || '';
  const due_date = document.getElementById('compDueDate')?.value || null;
  const assigned_to = document.getElementById('compAssignedTo')?.value.trim() || null;

  if (!title) { if (window.toast) toast('Title is required', 'warn'); return; }

  try {
    await api.complianceCreate({ dept, category, title, description, due_date, assigned_to });
    if (window.toast) toast('Compliance item added!', 'success');
    if (typeof closeModal === 'function') closeModal('compModal');
    await renderCompliancePage();
  } catch (e) {
    if (window.toast) toast('Save failed: ' + e.message, 'error');
  }
}
