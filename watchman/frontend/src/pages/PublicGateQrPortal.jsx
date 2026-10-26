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
      {/* MODE 1: VISITOR SELF PASS FORM (Opened in another tab when QR is scanned to collect details) */}
      {activeMode === 'form' && (
        <div style={{ width: '100%', maxWidth: '640px' }}>
          <VisitorSelfPass />
        </div>
      )}

      {/* MODE 2: GATE QR POSTER (Physical Standee - Only QR Code on /self-pass) */}
      {activeMode === 'poster' && (
        <div className="animate-fade-in" style={{
          maxWidth: '440px',
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
          {/* Header matching Softnix: "Gate 1 · Scan & Go" */}
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

            {/* Open Form in New Tab */}
            <a
              href={portalUrl}
              target="_blank"
              rel="noopener noreferrer"
              title="Open Visitor Pass Form in New Tab"
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
                cursor: 'pointer',
                textDecoration: 'none'
              }}
            >
              <ExternalLink size={17} />
            </a>
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

          {/* ACTION BUTTONS: [Print QR] & [Open link ↗] (Opens form in another tab) */}
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

            {/* Softnix White Button: Open link in ANOTHER TAB */}
            <a
              href={portalUrl}
              target="_blank"
              rel="noopener noreferrer"
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
                transition: 'all 0.15s ease',
                textDecoration: 'none'
              }}
            >
              <ExternalLink size={18} color="#2563EB" />
              <span>Open link ↗</span>
            </a>
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
