// src/components/HeroLanding.jsx
import React from 'react';
import { Sparkles, ArrowRight, ShieldCheck, Eye, Activity, MessageSquare } from 'lucide-react';

export const HeroLanding = ({ onOpenLaunchpad, appsCount = 4 }) => {
  return (
    <div>
      {/* ── Main Hero Section (Mirrors Image 1) ───────────────── */}
      <section className="hero-wrapper">
        <div className="hero-overlay"></div>

        <div className="hero-content">
          <div className="welcome-chip">
            <Sparkles size={14} color="#f43f5e" />
            + WELCOME TO GAVI TECHNOLOGIES WORKSPACE
          </div>

          <h1 className="hero-title">
            Gavi
          </h1>

          <p style={{
            fontSize: '1.4rem',
            color: '#f43f5e',
            fontWeight: '700',
            letterSpacing: '0.12em',
            textTransform: 'lowercase',
            marginBottom: '1rem',
            fontFamily: 'var(--font-heading)'
          }}>
            technologies
          </p>

          <p className="hero-subtitle">
            Enterprise unified workspace orchestrating CampusGuard Watchman Security,
            AI Face Recognition, Disaster Response Radar, and High-Throughput SMS Gateway.
          </p>

          <div className="hero-buttons">
            <button
              id="hero-btn-my-apps"
              className="btn-hero-launch"
              onClick={onOpenLaunchpad}
            >
              MY APPS
              <ArrowRight size={20} />
            </button>

            <button
              className="btn-hero-secondary"
              onClick={onOpenLaunchpad}
            >
              CONTACT US
            </button>
          </div>
        </div>
      </section>

      {/* ── Quick Stats & Feature Cards Section ──────────────── */}
      <section style={{ maxWidth: '1200px', margin: '-40px auto 4rem', padding: '0 1.5rem', position: 'relative', zIndex: 20 }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '1.25rem'
        }}>
          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '1.5rem',
            boxShadow: 'var(--shadow-md)',
            border: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '14px',
              background: 'rgba(16, 185, 129, 0.12)',
              color: '#059669',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Eye size={24} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: '1.05rem', color: '#0f172a' }}>Face Recognition</div>
              <div style={{ fontSize: '0.82rem', color: '#64748b' }}>AI Attendance System</div>
            </div>
          </div>

          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '1.5rem',
            boxShadow: 'var(--shadow-md)',
            border: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '14px',
              background: 'rgba(245, 158, 11, 0.12)',
              color: '#d97706',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <ShieldCheck size={24} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: '1.05rem', color: '#0f172a' }}>CampusGuard</div>
              <div style={{ fontSize: '0.82rem', color: '#64748b' }}>Smart Watchman & Gates</div>
            </div>
          </div>

          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '1.5rem',
            boxShadow: 'var(--shadow-md)',
            border: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '14px',
              background: 'rgba(244, 63, 94, 0.12)',
              color: '#e11d48',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Activity size={24} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: '1.05rem', color: '#0f172a' }}>Survivor Detection</div>
              <div style={{ fontSize: '0.82rem', color: '#64748b' }}>Disaster Emergency Radar</div>
            </div>
          </div>

          <div style={{
            background: 'white',
            borderRadius: '16px',
            padding: '1.5rem',
            boxShadow: 'var(--shadow-md)',
            border: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '14px',
              background: 'rgba(59, 130, 246, 0.12)',
              color: '#2563eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <MessageSquare size={24} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: '1.05rem', color: '#0f172a' }}>SMS Gateway</div>
              <div style={{ fontSize: '0.82rem', color: '#64748b' }}>Campus Broadcast Engine</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
