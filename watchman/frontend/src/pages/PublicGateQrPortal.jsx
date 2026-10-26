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

      {/* MODE 2: PRINTABLE GATE QR POSTER (Softnix-Style Scan & Go Modal) */}
      {activeMode === 'poster' && (
        <div className="animate-fade-in" style={{
          maxWidth: '540px',
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
            marginBottom: '1.25rem',
            paddingBottom: '0.75rem',
            borderBottom: '1px solid #F1F5F9'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', textAlign: 'left' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                backgroundColor: '#EFF6FF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#2563EB'
              }}>
                <Building size={18} />
              </div>
              <div>
                <h3 style={{
                  fontSize: '1.18rem',
                  fontWeight: 900,
                  color: '#0F172A',
                  margin: 0,
                  letterSpacing: '-0.01em'
                }}>
                  Gate 1 &bull; Scan &amp; Go
                </h3>
                <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 600 }}>
                  Smart Digital Pass &bull; மொபைல் மூலம் ஸ்கேன் செய்க
                </span>
              </div>
            </div>

            {/* Softnix Blue Close/Switch Button */}
            <button
              type="button"
              onClick={() => switchMode('form')}
              title="Open Mobile Pass Catalog"
              style={{
                width: '32px',
                height: '32px',
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
              <ExternalLink size={16} />
            </button>
          </div>

          {/* NETWORK SCANNING SELECTOR: Real Phone Camera Target */}
          <div style={{
            backgroundColor: '#F8FAFC',
            border: '1.5px solid #E2E8F0',
            borderRadius: '16px',
            padding: '0.85rem',
            marginBottom: '1.35rem',
            textAlign: 'left'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '0.55rem',
              flexWrap: 'wrap',
              gap: '4px'
            }}>
              <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#1E293B', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <Wifi size={14} color="#2563EB" />
                <span>QR Scanner Network Mode (போன் ஸ்கேனிங்):</span>
              </span>
              <span style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                color: networkMode === 'wifi' ? '#15803D' : '#2563EB',
                backgroundColor: networkMode === 'wifi' ? '#DCFCE7' : '#EFF6FF',
                padding: '2px 8px',
                borderRadius: '999px',
                border: networkMode === 'wifi' ? '1px solid #86EFAC' : '1px solid #BFDBFE'
              }}>
                {networkMode === 'wifi' ? '🟢 Phone Camera Ready' : networkMode === 'tunnel' ? '🌐 Public Online' : '💻 Local PC'}
              </span>
            </div>

            {/* Mode Switcher Tabs */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: '4px',
              backgroundColor: '#EDF2F7',
              borderRadius: '10px',
              padding: '3px',
              marginBottom: '0.65rem'
            }}>
              <button
                type="button"
                onClick={() => setNetworkMode('wifi')}
                style={{
                  padding: '6px 4px',
                  borderRadius: '7px',
                  border: 'none',
                  fontSize: '0.73rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  backgroundColor: networkMode === 'wifi' ? '#2563EB' : 'transparent',
                  color: networkMode === 'wifi' ? '#ffffff' : '#475569',
                  transition: 'all 0.15s ease'
                }}
              >
                📱 Wi-Fi / Hotspot
              </button>
              <button
                type="button"
                onClick={() => setNetworkMode('tunnel')}
                style={{
                  padding: '6px 4px',
                  borderRadius: '7px',
                  border: 'none',
                  fontSize: '0.73rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  backgroundColor: networkMode === 'tunnel' ? '#2563EB' : 'transparent',
                  color: networkMode === 'tunnel' ? '#ffffff' : '#475569',
                  transition: 'all 0.15s ease'
                }}
              >
                🌐 Public Tunnel
              </button>
              <button
                type="button"
                onClick={() => setNetworkMode('local')}
                style={{
                  padding: '6px 4px',
                  borderRadius: '7px',
                  border: 'none',
                  fontSize: '0.73rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  backgroundColor: networkMode === 'local' ? '#2563EB' : 'transparent',
                  color: networkMode === 'local' ? '#ffffff' : '#475569',
                  transition: 'all 0.15s ease'
                }}
              >
                💻 Localhost
              </button>
            </div>

            {/* Mode Explanations & Inputs */}
            {networkMode === 'wifi' && (
              <div style={{ fontSize: '0.75rem', color: '#475569' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span>
                    IP முகவரி: <strong style={{ color: '#0F172A', fontFamily: 'monospace' }}>{lanIp}:{lanPort}</strong>
                  </span>
                  {!editingIp ? (
                    <button
                      type="button"
                      onClick={() => {
                        setTempIpInput(lanIp);
                        setEditingIp(true);
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#2563EB',
                        cursor: 'pointer',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '2px'
                      }}
                    >
                      <Edit2 size={11} />
                      <span>மாற்று</span>
                    </button>
                  ) : null}
                </div>

                {editingIp && (
                  <div style={{ display: 'flex', gap: '4px', marginBottom: '6px' }}>
                    <input
                      type="text"
                      value={tempIpInput}
                      onChange={(e) => setTempIpInput(e.target.value)}
                      placeholder="e.g. 192.168.43.69"
                      style={{
                        flex: 1,
                        padding: '4px 8px',
                        fontSize: '0.75rem',
                        borderRadius: '6px',
                        border: '1.5px solid #2563EB',
                        outline: 'none',
                        fontFamily: 'monospace'
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        if (tempIpInput.trim()) setLanIp(tempIpInput.trim());
                        setEditingIp(false);
                      }}
                      style={{
                        backgroundColor: '#16A34A',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '4px 8px',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingIp(false)}
                      style={{
                        backgroundColor: '#64748B',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '6px',
                        padding: '4px 8px',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                )}

                <div style={{
                  backgroundColor: '#EFF6FF',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  border: '1px solid #BFDBFE',
                  fontSize: '0.72rem',
                  color: '#1E40AF',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  <Smartphone size={14} color="#2563EB" />
                  <span>
                    <strong>போன் மூலம் ஸ்கேன் செய்ய:</strong> உங்கள் மொபைலை லேப்டாப்பின் அதே Wi-Fi அல்லது மொபைல் ஹாட்ஸ்பாட்டில் இணைக்கவும்.
                  </span>
                </div>
              </div>
            )}

            {networkMode === 'tunnel' && (
              <div style={{ fontSize: '0.75rem' }}>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Softnix போன்ற ஆன்லைன் Cloud URL (Mobile 4G/5G-ல் வேலை செய்யும்):
                </label>
                <input
                  type="text"
                  value={tunnelUrl}
                  onChange={(e) => setTunnelUrl(e.target.value)}
                  placeholder="e.g. https://sample.softnix.in/pass or https://xyz.loca.lt"
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    fontSize: '0.75rem',
                    borderRadius: '8px',
                    border: '1.5px solid #CBD5E1',
                    outline: 'none',
                    boxSizing: 'border-box',
                    fontFamily: 'monospace'
                  }}
                />
              </div>
            )}

            {networkMode === 'local' && (
              <div style={{ fontSize: '0.72rem', color: '#64748B' }}>
                கம்ப்யூட்டர் உலாவிக்கான முகவரி (Localhost). மொபைல் கேமரா மூலம் ஸ்கேன் செய்ய மேலே உள்ள <strong>Wi-Fi / Hotspot</strong> தேர்வை அழுத்தவும்.
              </div>
            )}

            {/* Target URL Preview */}
            <div style={{ marginTop: '0.55rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '0.68rem', fontWeight: 800, color: '#64748B' }}>ENCODED URL:</span>
              <code style={{
                fontSize: '0.72rem',
                color: '#2563EB',
                backgroundColor: '#ffffff',
                padding: '2px 6px',
                borderRadius: '4px',
                border: '1px solid #CBD5E1',
                flex: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {portalUrl}
              </code>
            </div>
          </div>

          {/* REAL SCANNABLE QR CODE CONTAINER */}
          <div style={{
            display: 'inline-block',
            padding: '16px',
            backgroundColor: '#ffffff',
            borderRadius: '20px',
            border: '3px solid #0F172A',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.15)',
            marginBottom: '1rem',
            position: 'relative'
          }}>
            <RealQRCode text={portalUrl} size={220} />
            <div style={{
              marginTop: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              fontSize: '0.72rem',
              fontWeight: 800,
              color: '#16A34A'
            }}>
              <CheckCircle2 size={13} strokeWidth={3} />
              <span>Camera Scannable &bull; Real-Time</span>
            </div>
          </div>

          <h3 style={{ fontSize: '1.25rem', fontWeight: 900, color: '#0F172A', margin: '0 0 0.35rem 0' }}>
            SCAN WITH PHONE CAMERA TO ENTER
          </h3>
          <p style={{ fontSize: '0.82rem', color: '#64748B', margin: '0 0 1.25rem 0', fontWeight: 600 }}>
            மொபைல் கேமரா மூலம் QR-ஐ ஸ்கேன் செய்து டிஜிட்டல் பாஸ் பெறவும்
          </p>

          {/* ACTION BUTTONS: Matches Softnix Image 2 [Print QR] & [Open link] */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
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

            {/* Quick Copy Link Bar */}
            <button
              type="button"
              onClick={() => {
                navigator.clipboard?.writeText(portalUrl);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              style={{
                width: '100%',
                padding: '0.65rem 1rem',
                borderRadius: '10px',
                backgroundColor: '#F8FAFC',
                color: '#475569',
                fontSize: '0.8rem',
                fontWeight: 700,
                border: '1px solid #CBD5E1',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px'
              }}
            >
              {copied ? <Check size={15} color="#16A34A" /> : <Copy size={15} />}
              <span>{copied ? 'Mobile URL Copied to Clipboard!' : 'Copy Mobile URL for Testing'}</span>
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
