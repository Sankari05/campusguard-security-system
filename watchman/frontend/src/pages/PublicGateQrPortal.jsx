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
  Check,
  Wifi,
  Globe,
  Settings,
  RefreshCw,
  Sparkles,
  CheckCircle2,
  Edit2
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

  // Network mode: 'wifi' (Local Network IP for phone camera scan), 'tunnel' (Softnix-style public cloud URL), 'local' (PC localhost)
  const [networkMode, setNetworkMode] = useState(() => {
    try {
      const saved = localStorage.getItem('campusguard_qr_net_mode');
      if (saved) return saved;
    } catch {}
    if (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')) {
      return 'wifi';
    }
    return 'local';
  });

  // Local Network IP (Auto-detected from active Wi-Fi adapter: 192.168.43.69)
  const [lanIp, setLanIp] = useState(() => {
    try {
      const saved = localStorage.getItem('campusguard_qr_lan_ip');
      if (saved) return saved;
    } catch {}
    return '192.168.43.69';
  });

  const [lanPort, setLanPort] = useState(() => {
    try {
      const saved = localStorage.getItem('campusguard_qr_lan_port');
      if (saved) return saved;
    } catch {}
    return (typeof window !== 'undefined' && window.location.port) ? window.location.port : '5173';
  });

  // Softnix-style public domain / tunnel URL (e.g. https://sample.softnix.in/... or ngrok/localtunnel)
  const [tunnelUrl, setTunnelUrl] = useState(() => {
    try {
      const saved = localStorage.getItem('campusguard_qr_tunnel_url');
      if (saved) return saved;
    } catch {}
    return '';
  });

  const [editingIp, setEditingIp] = useState(false);
  const [tempIpInput, setTempIpInput] = useState(lanIp);

  // Keep settings synced in localStorage
  useEffect(() => {
    try {
      localStorage.setItem('campusguard_qr_net_mode', networkMode);
      localStorage.setItem('campusguard_qr_lan_ip', lanIp);
      localStorage.setItem('campusguard_qr_lan_port', lanPort);
      localStorage.setItem('campusguard_qr_tunnel_url', tunnelUrl);
    } catch {}
  }, [networkMode, lanIp, lanPort, tunnelUrl]);

  // Compute the live URL encoded inside the QR Code
  const portalUrl = (() => {
    if (networkMode === 'wifi' && lanIp) {
      return `http://${lanIp}:${lanPort}/self-pass?mode=form`;
    }
    if (networkMode === 'tunnel' && tunnelUrl.trim()) {
      const clean = tunnelUrl.trim().replace(/\/+$/, '');
      return clean.includes('/self-pass') ? clean : `${clean}/self-pass?mode=form`;
    }
    return `${window.location.origin}/self-pass?mode=form`;
  })();

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

      {/* MODE 1: VISITOR SELF PASS FORM (Softnix-Style Dish/Menu Order Interface) */}
      {activeMode === 'form' && (
        <div style={{ width: '100%', maxWidth: '580px' }}>
          <VisitorSelfPass onBackToPoster={() => switchMode('poster')} />
        </div>
      )}

      {/* MODE 2: PRINTABLE GATE QR POSTER (Softnix-Style Scan & Go Standee) */}
      {activeMode === 'poster' && (
        <div className="animate-fade-in" style={{
          maxWidth: '460px',
          width: '100%',
          backgroundColor: '#ffffff',
          borderRadius: '24px',
          padding: '2rem 1.75rem',
          color: '#0F172A',
          textAlign: 'center',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          border: '2px solid #E2E8F0',
          position: 'relative'
        }}>
          {/* Header matching Softnix Image 2: "Table T-3 · Scan & Go" */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '1.5rem',
            paddingBottom: '0.85rem',
            borderBottom: '1px solid #F1F5F9'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', textAlign: 'left' }}>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                backgroundColor: '#EFF6FF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#2563EB'
              }}>
                <Building size={20} />
              </div>
              <h3 style={{
                fontSize: '1.25rem',
                fontWeight: 900,
                color: '#0F172A',
                margin: 0,
                letterSpacing: '-0.01em'
              }}>
                Gate 1 &bull; Scan &amp; Go
              </h3>
            </div>

            {/* Softnix Blue Close/Switch Button */}
            <button
              type="button"
              onClick={() => switchMode('form')}
              title="Open Mobile Pass Catalog"
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '8px',
                border: '1.5px solid #BFDBFE',
                backgroundColor: '#EFF6FF',
                color: '#2563EB',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer'
              }}
            >
              <ExternalLink size={17} />
            </button>
          </div>

          {/* REAL SCANNABLE QR CODE CONTAINER */}
          <div style={{
            display: 'inline-block',
            padding: '20px',
            backgroundColor: '#ffffff',
            borderRadius: '20px',
            border: '3px solid #0F172A',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.15)',
            marginBottom: '1.75rem',
            position: 'relative'
          }}>
            <RealQRCode text={portalUrl} size={230} />
          </div>

          {/* ACTION BUTTONS: Matches Softnix Image 2 [Print QR] & [Open link] */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            {/* Softnix Red Button: Print QR */}
            <button
              type="button"
              onClick={() => window.print()}
              style={{
                padding: '0.85rem 1rem',
                borderRadius: '12px',
                backgroundColor: '#C8372D', // Softnix Red
                color: '#ffffff',
                fontSize: '0.95rem',
                fontWeight: 800,
                border: 'none',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                boxShadow: '0 4px 14px rgba(200, 55, 45, 0.35)',
                transition: 'all 0.15s ease'
              }}
            >
              <Printer size={18} />
              <span>Print QR</span>
            </button>

            {/* Softnix White Button: Open link */}
            <button
              type="button"
              onClick={() => switchMode('form')}
              style={{
                padding: '0.85rem 1rem',
                borderRadius: '12px',
                backgroundColor: '#ffffff',
                color: '#0F172A',
                fontSize: '0.95rem',
                fontWeight: 800,
                border: '1.5px solid #E2E8F0',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                boxShadow: '0 2px 8px rgba(15, 23, 42, 0.05)',
                transition: 'all 0.15s ease'
              }}
            >
              <ExternalLink size={18} color="#2563EB" />
              <span>Open link</span>
            </button>
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
