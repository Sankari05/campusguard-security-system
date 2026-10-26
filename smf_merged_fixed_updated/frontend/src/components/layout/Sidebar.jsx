import React from 'react';
import {
  Users,
  Clock,
  FileText,
  Camera,
  BarChart3,
  LogOut,
  ShieldCheck,
  CalendarCheck,
} from 'lucide-react';

export default function Sidebar({ currentPage, onNavigate, user, onLogout }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
    { id: 'hod-students', label: 'Student Management', icon: Users },
    { id: 'overrides', label: 'Attendance Overrides', icon: CalendarCheck },
    { id: 'reports', label: 'Reports & Analytics', icon: FileText },
    { id: 'camera', label: 'Live Face Recognition', icon: Camera },
    { id: 'logs', label: 'System Logs', icon: Clock },
  ];

  return (
    <aside
      style={{
        width: '260px',
        background: 'rgba(15, 23, 42, 0.95)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'sticky',
        top: 0,
      }}
    >
      {/* Brand */}
      <div
        className="sb-brand"
        style={{
          padding: '24px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <div
          style={{
            width: '38px',
            height: '38px',
            borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, var(--primary), var(--accent-cyan))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
          }}
        >
          <ShieldCheck size={20} />
        </div>
        <div>
          <div
            style={{
              fontSize: '1.1rem',
              fontWeight: 800,
              color: 'var(--text-main)',
              letterSpacing: '-0.02em',
            }}
          >
            EduTrack <span style={{ color: 'var(--accent-cyan)' }}>Pro</span>
          </div>
          <div
            style={{
              fontSize: '0.7rem',
              color: 'var(--text-dim)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            {user?.role ? `${user.role} Portal` : 'Portal'}
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav
        id="sbNav"
        style={{
          flex: 1,
          padding: '16px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentPage === item.id;
          return (
            <a
              key={item.id}
              data-page={item.id}
              href={`#${item.id}`}
              onClick={(e) => {
                e.preventDefault();
                onNavigate(item.id);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                color: isActive ? '#ffffff' : 'var(--text-muted)',
                background: isActive ? 'var(--primary)' : 'transparent',
                fontWeight: isActive ? 600 : 500,
                fontSize: '0.875rem',
                textDecoration: 'none',
                transition: 'all var(--transition-fast)',
              }}
            >
              <Icon size={18} color={isActive ? '#ffffff' : 'var(--text-dim)'} />
              <span>{item.label}</span>
            </a>
          );
        })}
      </nav>

      {/* Footer Profile / Logout */}
      <div style={{ padding: '16px 12px', borderTop: '1px solid var(--border-subtle)' }}>
        <button
          onClick={onLogout}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            padding: '10px 14px',
            borderRadius: 'var(--radius-md)',
            background: 'transparent',
            border: 'none',
            color: 'var(--text-dim)',
            fontSize: '0.85rem',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <LogOut size={16} />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
