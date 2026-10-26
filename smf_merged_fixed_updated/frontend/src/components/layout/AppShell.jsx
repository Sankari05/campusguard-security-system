import React from 'react';
import Sidebar from './Sidebar';
import Navbar from './Navbar';

export default function AppShell({ currentPage, onNavigate, user, onLogout, pageTitle, children }) {
  return (
    <div
      id="appShell"
      style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-primary)' }}
    >
      {/* Sidebar with .sb-brand and #sbNav */}
      <Sidebar currentPage={currentPage} onNavigate={onNavigate} user={user} onLogout={onLogout} />

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <Navbar title={pageTitle} user={user} />

        <main style={{ flex: 1, padding: '28px', overflowY: 'auto' }}>{children}</main>
      </div>
    </div>
  );
}
