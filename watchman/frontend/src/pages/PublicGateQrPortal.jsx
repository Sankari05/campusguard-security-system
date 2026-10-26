import React, { useState, useEffect } from 'react';
import { VisitorSelfPass } from '../components/VisitorSelfPass';
import { RealQRCode } from '../components/RealQRCode';
import {
  QrCode,
  Smartphone,
  Printer,
  ExternalLink,
  ShieldCheck,
  Building,
  Copy,
  Check
} from 'lucide-react';

export const PublicGateQrPortal = () => {
  const [activeMode, setActiveMode] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const m = params.get('mode');
      if (m === 'form') return 'form';
      if (m === 'poster') return 'poster';
    } catch {
      // safe fallback
    }
    return 'poster';
  });

  const [copied, setCopied] = useState(false);
  const portalUrl = `${window.location.origin}/self-pass?mode=form`;

  const switchMode = (mode) => {
    setActiveMode(mode);
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('mode', mode);
      window.history.replaceState({}, '', url.toString());
    } catch {
      // safe fallback
    }
  };

  useEffect(() => {
    const handlePopState = () => {
      try {
        const params = new URLSearchParams(window.location.search);
        const m = params.get('mode');
        if (m === 'form' || m === 'poster') {
          setActiveMode(m);
        }
      } catch {
        // safe fallback
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#FFFFFF',
      backgroundImage: `
        radial-gradient(circle at 10% 15%, rgba(153, 246, 228, 0.40) 0%, rgba(186, 230, 253, 0.25) 30%, transparent 60%),
        radial-gradient(circle at 50% 38%, rgba(254, 215, 170, 0.45) 0%, rgba(254, 243, 199, 0.25) 32%, transparent 65%),
        radial-gradient(circle at 85% 80%, rgba(199, 210, 254, 0.45) 0%, rgba(224, 231, 255, 0.30) 35%, transparent 65%),
        linear-gradient(to right, rgba(14, 165, 233, 0.08) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(14, 165, 233, 0.08) 1px, transparent 1px)
      `,
      backgroundSize: '100% 100%, 100% 100%, 100% 100%, 36px 36px, 36px 36px',
      backgroundAttachment: 'fixed',
      color: '#0F172A',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '2.5rem 1rem',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
    }}>
      {/* Top Header */}
      <div style={{
        maxWidth: '700px',
        width: '100%',
        textAlign: 'center',
        marginBottom: '2rem'
      }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          backgroundColor: '#EFF6FF',
          border: '1.5px solid #BFDBFE',
          borderRadius: '999px',
          padding: '6px 16px',
          fontSize: '0.8rem',
          fontWeight: 800,
          color: '#1D4ED8',
          marginBottom: '1rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          boxShadow: '0 2px 8px rgba(37, 99, 235, 0.08)'
        }}>
          <ShieldCheck size={16} color="#2563EB" />
          <span>College Main Gate &bull; Standalone Public Portal</span>
        </div>

        <h1 style={{
          fontSize: '2.4rem',
          fontWeight: 900,
          margin: '0 0 0.5rem 0',
          letterSpacing: '-0.02em',
          color: '#0F172A'
        }}>
          CampusGuard Digital Self-Pass
        </h1>

        {/* Mode Switcher */}
        <div style={{
          display: 'inline-flex',
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          borderRadius: '14px',
          padding: '5px',
          marginTop: '1.25rem',
          border: '1.5px solid #E2E8F0',
          boxShadow: '0 4px 14px rgba(15, 23, 42, 0.05)'
        }}>
          <button
            type="button"
            onClick={() => switchMode('form')}
            style={{
              padding: '8px 18px',
              borderRadius: '10px',
              border: 'none',
              fontSize: '0.85rem',
              fontWeight: 800,
              cursor: 'pointer',
              backgroundColor: activeMode === 'form' ? '#2563EB' : 'transparent',
              color: activeMode === 'form' ? '#ffffff' : '#64748B',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
              boxShadow: activeMode === 'form' ? '0 4px 12px rgba(37, 99, 235, 0.3)' : 'none'
            }}
          >
            <Smartphone size={16} />
            <span>Fill Visitor Form (Mobile View)</span>
          </button>

          <button
            type="button"
            onClick={() => switchMode('poster')}
            style={{
              padding: '8px 18px',
              borderRadius: '10px',
              border: 'none',
              fontSize: '0.85rem',
              fontWeight: 800,
              cursor: 'pointer',
              backgroundColor: activeMode === 'poster' ? '#2563EB' : 'transparent',
              color: activeMode === 'poster' ? '#ffffff' : '#64748B',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease',
              boxShadow: activeMode === 'poster' ? '0 4px 12px rgba(37, 99, 235, 0.3)' : 'none'
            }}
          >
            <QrCode size={16} />
            <span>Gate QR Poster (Physical Standee)</span>
          </button>
        </div>
      </div>

      {/* MODE 1: VISITOR SELF PASS FORM */}
      {activeMode === 'form' && (
        <div style={{ width: '100%', maxWidth: '580px' }}>
          <VisitorSelfPass onBackToPoster={() => switchMode('poster')} />
        </div>
      )}

      {/* MODE 2: PRINTABLE GATE QR POSTER */}
      {activeMode === 'poster' && (
        <div className="animate-fade-in" style={{
          maxWidth: '540px',
          width: '100%',
          backgroundColor: '#ffffff',
          borderRadius: '24px',
          padding: '2.5rem 2rem',
          color: '#0F172A',
          textAlign: 'center',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          border: '4px solid #2563EB'
        }}>
          {/* Standee Branding */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', marginBottom: '0.5rem' }}>
            <Building size={24} color="#2563EB" />
            <span style={{ fontSize: '1.25rem', fontWeight: 900, color: '#0F172A', letterSpacing: '-0.01em' }}>
              COLLEGE MAIN GATE 1
            </span>
          </div>

          <div style={{
            fontSize: '0.85rem',
            fontWeight: 800,
            color: '#2563EB',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            marginBottom: '1.25rem'
          }}>
            Smart Digital Gate Entry Point
          </div>

          {/* REAL SCANNABLE QR CODE */}
          <div style={{
            display: 'inline-block',
            padding: '16px',
            backgroundColor: '#ffffff',
            borderRadius: '20px',
            border: '3px solid #0F172A',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.15)',
            marginBottom: '1.25rem'
          }}>
            <RealQRCode text={portalUrl} size={220} />
          </div>

          <h3 style={{ fontSize: '1.25rem', fontWeight: 900, color: '#0F172A', margin: '0 0 1rem 0' }}>
            SCAN WITH PHONE CAMERA TO ENTER
          </h3>

          {/* ACTION BUTTONS: Open with Link & Print Poster */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={() => switchMode('form')}
              style={{
                width: '100%',
                padding: '0.9rem 1.5rem',
                borderRadius: '12px',
                backgroundColor: '#2563EB',
                color: '#ffffff',
                fontSize: '1rem',
                fontWeight: 800,
                border: 'none',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                boxShadow: '0 10px 20px -5px rgba(37, 99, 235, 0.4)',
                transition: 'all 0.15s ease'
              }}
            >
              <ExternalLink size={18} />
              <span>Open with Link (படிவத்தை திறக்கவும்)</span>
            </button>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard?.writeText(portalUrl);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                style={{
                  padding: '0.7rem 1rem',
                  borderRadius: '10px',
                  backgroundColor: '#F8FAFC',
                  color: '#334155',
                  fontSize: '0.85rem',
                  fontWeight: 700,
                  border: '1.5px solid #CBD5E1',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                {copied ? <Check size={16} color="#16A34A" /> : <Copy size={16} />}
                <span>{copied ? 'Link Copied!' : 'Copy Form Link'}</span>
              </button>

              <button
                type="button"
                onClick={() => window.print()}
                style={{
                  padding: '0.7rem 1rem',
                  borderRadius: '10px',
                  backgroundColor: '#0F172A',
                  color: '#ffffff',
                  fontSize: '0.85rem',
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                <Printer size={16} />
                <span>Print Gate Poster</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Return to Watchman link */}
      <div style={{ marginTop: '2rem', textAlign: 'center' }}>
        <a
          href="/"
          onClick={(e) => {
            e.preventDefault();
            window.history.pushState({}, '', '/');
            window.dispatchEvent(new Event('popstate'));
          }}
          style={{
            color: '#60A5FA',
            fontSize: '0.85rem',
            fontWeight: 700,
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '5px',
            cursor: 'pointer'
          }}
        >
          <span>&larr; Return to Guard / Watchman Terminal</span>
        </a>
      </div>
    </div>
  );
};
