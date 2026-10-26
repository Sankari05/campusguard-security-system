// src/App.jsx
import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { HeroLanding } from './components/HeroLanding';
import { Launchpad } from './components/Launchpad';
import { AddAppModal } from './components/AddAppModal';
import { AppLauncherModal } from './components/AppLauncherModal';
import { INITIAL_APPS } from './data/appsData';

export function App() {
  const [currentView, setCurrentView] = useState('landing'); // 'landing' | 'launchpad'
  const [apps, setApps] = useState(() => {
    try {
      const saved = localStorage.getItem('campushub_apps');
      return saved ? JSON.parse(saved) : INITIAL_APPS;
    } catch {
      return INITIAL_APPS;
    }
  });

  const [selectedApp, setSelectedApp] = useState(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Sync with localStorage
  useEffect(() => {
    localStorage.setItem('campushub_apps', JSON.stringify(apps));
  }, [apps]);

  // URL Hash routing support (#my-apps or #home)
  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.toLowerCase();
      if (hash === '#my-apps' || hash === '#apps' || hash === '#launchpad') {
        setCurrentView('launchpad');
      } else {
        setCurrentView('landing');
      }
    };

    handleHash();
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  const handleViewChange = (view) => {
    setCurrentView(view);
    if (view === 'launchpad') {
      window.location.hash = '#my-apps';
    } else {
      window.location.hash = '';
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleAddApp = (newApp) => {
    setApps((prev) => [newApp, ...prev]);
  };

  const handleOpenApp = (app) => {
    setSelectedApp(app);
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* ── Top Navigation Bar ───────────────────────────────── */}
      <Navbar
        currentView={currentView}
        setCurrentView={handleViewChange}
        appsCount={apps.length}
      />

      {/* ── Main View Switcher ───────────────────────────────── */}
      <main style={{ flex: 1 }}>
        {currentView === 'landing' ? (
          <HeroLanding
            onOpenLaunchpad={() => handleViewChange('launchpad')}
            appsCount={apps.length}
          />
        ) : (
          <Launchpad
            apps={apps}
            onOpenApp={handleOpenApp}
            onOpenAddModal={() => setIsAddModalOpen(true)}
          />
        )}
      </main>

      {/* ── Add App Modal ────────────────────────────────────── */}
      <AddAppModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAddApp={handleAddApp}
      />

      {/* ── Application Launch Preview Modal ─────────────────── */}
      <AppLauncherModal
        app={selectedApp}
        onClose={() => setSelectedApp(null)}
      />

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer style={{
        background: '#0f172a',
        color: '#94a3b8',
        padding: '2.5rem 1.5rem',
        borderTop: '1px solid #1e293b',
        textAlign: 'center',
        fontSize: '0.88rem'
      }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, color: 'white', fontSize: '1.1rem' }}>
            <span>Gavi Technologies</span>
            <span style={{ fontSize: '0.72rem', background: 'var(--color-primary)', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>
              PORTAL
            </span>
          </div>
          <p>Next-Generation Enterprise Multi-Project Management Workspace</p>
          <p style={{ fontSize: '0.78rem', color: '#64748b' }}>
            Independent Authentication &bull; Zero-Touch Isolation &bull; 4 Connected Campus Systems
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
