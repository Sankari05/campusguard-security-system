// src/components/AppLauncherModal.jsx
import React from 'react';
import { X, ExternalLink, ShieldCheck, Terminal, Copy, CheckCircle2 } from 'lucide-react';

export const AppLauncherModal = ({ app, onClose }) => {
  const [copied, setCopied] = React.useState(false);

  if (!app) return null;

  const handleCopyUrl = () => {
    navigator.clipboard.writeText(app.url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleLaunch = () => {
    window.open(app.url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div
              style={{
                width: '46px',
                height: '46px',
                borderRadius: '14px',
                background: app.gradient,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
              }}
            >
              <ShieldCheck size={26} />
            </div>
            <div>
              <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.25rem', fontWeight: 800, color: '#0f172a' }}>
                {app.name}
              </h3>
              <span style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 600 }}>{app.category}</span>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: '#f1f5f9',
              border: 'none',
              borderRadius: '8px',
              padding: '0.4rem',
              cursor: 'pointer',
            }}
          >
            <X size={18} color="#64748b" />
          </button>
        </div>

        <p style={{ fontSize: '0.9rem', color: '#475569', lineHeight: 1.6, marginBottom: '1.5rem' }}>
          {app.description}
        </p>

        {/* ── Security Credentials & Roles Notice ────────────── */}
        <div
          style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '12px',
            padding: '1.1rem',
            marginBottom: '1.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
            <ShieldCheck size={16} color="#059669" />
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#0f172a' }}>
              Isolated Authentication &amp; Roles
            </span>
          </div>

          <p style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '0.6rem' }}>
            This application maintains its own independent database and credentials.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {app.roles?.map((role) => (
              <span
                key={role}
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  padding: '0.2rem 0.55rem',
                  background: 'white',
                  border: '1px solid #cbd5e1',
                  borderRadius: '6px',
                  color: '#334155',
                }}
              >
                {role}
              </span>
            ))}
          </div>
        </div>

        {/* ── Target Port & Folder ───────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.75rem' }}>
          <div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600 }}>TARGET URL</div>
            <div style={{ fontFamily: 'monospace', fontWeight: 700, color: '#0f172a', fontSize: '0.92rem' }}>
              {app.url}
            </div>
          </div>

          <button
            onClick={handleCopyUrl}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.45rem 0.75rem',
              borderRadius: '8px',
              border: '1px solid #cbd5e1',
              background: 'white',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              color: '#334155',
            }}
          >
            {copied ? <CheckCircle2 size={14} color="#059669" /> : <Copy size={14} />}
            {copied ? 'Copied' : 'Copy URL'}
          </button>
        </div>

        {/* ── Action Buttons ─────────────────────────────────── */}
        <div style={{ display: 'flex', gap: '0.85rem' }}>
          <button
            onClick={onClose}
            style={{
              flex: 1,
              padding: '0.75rem',
              borderRadius: '12px',
              border: '1px solid #cbd5e1',
              background: 'white',
              color: '#475569',
              fontWeight: 600,
              fontSize: '0.92rem',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>

          <button
            onClick={handleLaunch}
            style={{
              flex: 2,
              padding: '0.75rem',
              borderRadius: '12px',
              border: 'none',
              background: app.gradient,
              color: 'white',
              fontWeight: 700,
              fontSize: '0.95rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              boxShadow: '0 4px 15px rgba(0,0,0,0.15)',
            }}
          >
            Open Application
            <ExternalLink size={16} />
          </button>
        </div>
      </div>
    </div>
  );
};
