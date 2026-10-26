// src/components/Launchpad.jsx
import React, { useState } from 'react';
import {
  Rocket,
  Plus,
  ExternalLink,
  ShieldCheck,
  ScanFace,
  Radar,
  MessageSquare,
  Sparkles,
  Server,
  FolderGit2,
  Info
} from 'lucide-react';

export const Launchpad = ({
  apps,
  onOpenApp,
  onOpenAddModal,
  onSelectAppInfo
}) => {
  const [filterCategory, setFilterCategory] = useState('ALL');

  const filteredApps = filterCategory === 'ALL'
    ? apps
    : apps.filter(a => a.category.toLowerCase().includes(filterCategory.toLowerCase()));

  // Icon renderer helper
  const renderAppIcon = (iconName, size = 38) => {
    switch (iconName) {
      case 'ScanFace':
        return <ScanFace size={size} strokeWidth={2.2} />;
      case 'ShieldCheck':
        return <ShieldCheck size={size} strokeWidth={2.2} />;
      case 'Radar':
        return <Radar size={size} strokeWidth={2.2} />;
      case 'MessageSquare':
        return <MessageSquare size={size} strokeWidth={2.2} />;
      default:
        return <Rocket size={size} strokeWidth={2.2} />;
    }
  };

  return (
    <div className="launchpad-wrapper">
      {/* ── Top Header Section (Mirrors Image 2) ───────────────── */}
      <div className="launchpad-header">
        <div className="rocket-icon-badge">
          <Rocket size={30} strokeWidth={2.4} />
        </div>

        <h1 className="launchpad-title">
          Your <span>Launchpad</span>
        </h1>

        <p className="launchpad-subtitle">
          {apps.length} apps ready to launch &amp; manage
        </p>
      </div>

      {/* ── Main App Squircles Grid (Mirrors Image 2) ──────────── */}
      <div className="apps-grid">
        {apps.map((app) => (
          <button
            key={app.id}
            id={`launch-app-${app.id}`}
            className="app-card-item"
            onClick={() => onOpenApp(app)}
          >
            <div
              className="app-squircle"
              style={{
                background: app.gradient,
              }}
            >
              {renderAppIcon(app.iconName, 40)}
              <span className="app-badge-indicator badge-online" title="Service Registered"></span>
            </div>
            <span className="app-label">{app.name}</span>
          </button>
        ))}

        {/* ── Dotted Plus Button ("Add apps") (From Image 2) ─── */}
        <button
          id="btn-add-app"
          className="add-app-card"
          onClick={onOpenAddModal}
        >
          <div className="add-app-squircle">
            <Plus size={36} strokeWidth={2.2} />
          </div>
          <span className="add-app-label">Add apps</span>
        </button>
      </div>

      {/* ── Detailed Workspace Cards Section ────────────────── */}
      <div style={{ width: '100%', marginTop: '2rem' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1.5rem',
          flexWrap: 'wrap',
          gap: '1rem'
        }}>
          <div>
            <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.45rem', fontWeight: 800, color: '#0f172a' }}>
              Project Workspaces &amp; Ports
            </h2>
            <p style={{ fontSize: '0.88rem', color: '#64748b' }}>
              Independent security &amp; zero-touch isolated environments
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {['ALL', 'Campus Safety', 'AI & Biometrics', 'Disaster', 'Communication'].map(cat => (
              <button
                key={cat}
                onClick={() => setFilterCategory(cat)}
                style={{
                  padding: '0.4rem 0.85rem',
                  borderRadius: '8px',
                  border: '1px solid',
                  borderColor: filterCategory === cat ? 'var(--color-primary)' : '#e2e8f0',
                  background: filterCategory === cat ? 'rgba(236, 72, 153, 0.08)' : 'white',
                  color: filterCategory === cat ? 'var(--color-primary)' : '#64748b',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        <div className="detailed-apps-container">
          {filteredApps.map((app) => (
            <div key={app.id} className="detail-card">
              <div className="detail-header">
                <div
                  className="detail-icon-squircle"
                  style={{ background: app.gradient }}
                >
                  {renderAppIcon(app.iconName, 26)}
                </div>
                <div className="detail-title-group">
                  <span className="detail-category-tag">{app.category}</span>
                  <h3>{app.name}</h3>
                </div>
              </div>

              <p className="detail-desc">{app.description}</p>

              <div className="detail-meta-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Server size={14} color="#64748b" />
                  <span>Port:</span>
                  <span className="port-badge">{app.devPort}</span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <FolderGit2 size={14} color="#64748b" />
                  <span style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{app.folder}</span>
                </div>
              </div>

              {app.roles && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1.25rem' }}>
                  {app.roles.map(r => (
                    <span
                      key={r}
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        padding: '0.2rem 0.5rem',
                        borderRadius: '6px',
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        color: '#475569'
                      }}
                    >
                      {r}
                    </span>
                  ))}
                </div>
              )}

              <button
                className="btn-open-app"
                style={{ background: app.gradient }}
                onClick={() => onOpenApp(app)}
              >
                Launch {app.shortName}
                <ExternalLink size={16} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
