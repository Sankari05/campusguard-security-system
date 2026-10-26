/**
 * frontend/js/components/layout.js
 * ================================
 * Centralized Enterprise Layout Shell for EduTrack Pro.
 * Eliminates duplicate Sidebar & Topbar across admin.html, faculty.html, and hod.html.
 * Single Source of Truth for:
 * - Brand Icon & Sidebar Header
 * - Dynamic User Profile Card (#sbUserCard, #sucAv, #sucName, #sucRole, #sucDept)
 * - Navigation links container (#sbNav)
 * - System Status & Logout Button
 * - Top Navigation Bar (#topbar) with Breadcrumbs, Live Clock, and Notifications
 */

export function getSidebarHtml(role = 'admin') {
  const roleNameMap = {
    admin: { name: 'Administrator', role: 'System Admin', dept: 'All Departments', av: 'AD' },
    faculty: {
      name: 'Faculty Member',
      role: 'Teaching Staff',
      dept: 'Assigned Department',
      av: 'FA',
    },
    hod: {
      name: 'Department Head',
      role: 'Head of Department',
      dept: 'Department Office',
      av: 'HD',
    },
    student: {
      name: 'Student Portal',
      role: 'Enrolled Student',
      dept: 'Academic Student',
      av: 'ST',
    },
  };

  const defaultMeta = roleNameMap[role] || roleNameMap.admin;

  return `
    <div class="sb-head">
      <div class="sb-brand">
        <div class="sb-icon"><i class="fa fa-graduation-cap"></i></div>
        <div class="sb-title-wrap">
          <span class="sb-title">EduTrack <b>Pro</b></span>
          <span class="sb-version">Smart Attendance</span>
        </div>
      </div>
      <button class="sb-hamburger" onclick="toggleSidebar()"><i class="fa fa-bars"></i></button>
    </div>

    <!-- User card in sidebar -->
    <div class="sb-user-card" id="sbUserCard">
      <div class="suc-av" id="sucAv">${defaultMeta.av}</div>
      <div class="suc-info">
        <div class="suc-name" id="sucName">${defaultMeta.name}</div>
        <div class="suc-role" id="sucRole">${defaultMeta.role}</div>
        <div class="suc-dept" id="sucDept">${defaultMeta.dept}</div>
      </div>
    </div>

    <nav class="sb-nav" id="sbNav"><!-- Populated dynamically by app.js --></nav>

    <div class="sb-bottom">
      <div class="sb-status">
        <span class="status-dot"></span>
        <span>System Active</span>
      </div>
      <button class="sb-logout-btn" onclick="doLogout()">
        <i class="fa fa-right-from-bracket"></i> Logout
      </button>
    </div>
  `;
}

export function getTopbarHtml() {
  return `
    <div class="tb-l">
      <button class="mob-ham" onclick="toggleSidebar()"><i class="fa fa-bars"></i></button>
      <div class="tb-page-title" id="tbPageTitle">Dashboard</div>
    </div>
    <div class="tb-r">
      <div class="tb-clock" id="tbClock"></div>
      <button class="tb-icon-btn notif-btn" onclick="openNotificationCenter()">
        <i class="fa fa-bell"></i>
        <span class="notif-badge" id="notifBadge" style="display:none">0</span>
      </button>
      <div class="tb-profile" id="tbProfile">
        <div class="tbp-av" id="tbpAv">AD</div>
        <div class="tbp-info">
          <span class="tbp-name" id="tbpName">Admin</span>
          <span class="tbp-role" id="tbpRole">Administrator</span>
        </div>
      </div>
    </div>
  `;
}

/**
 * Automatically mount layout shell into target containers if empty
 */
export function initLayout(role = 'admin') {
  const sidebar = document.getElementById('sidebar');
  if (sidebar && sidebar.innerHTML.trim() === '') {
    sidebar.innerHTML = getSidebarHtml(role);
  }

  const topbar = document.getElementById('topbar');
  if (topbar && topbar.innerHTML.trim() === '') {
    topbar.innerHTML = getTopbarHtml();
  }

  // Start live clock update
  updateLiveClock();
}

/**
 * Updates the #tbClock element every minute
 */
function updateLiveClock() {
  const clockEl = document.getElementById('tbClock');
  if (!clockEl) return;

  function tick() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  tick();
  setInterval(tick, 30000);
}

export default {
  getSidebarHtml,
  getTopbarHtml,
  initLayout,
};
