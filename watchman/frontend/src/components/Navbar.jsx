import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Bell,
  AlertTriangle,
  Clock,
  Volume2,
  Languages,
  X,
  ShieldCheck,
  Building,
  Menu
} from 'lucide-react';

export const Navbar = ({ onOpenSosModal, onToggleSidebar }) => {
  const { user, t, language, changeLanguage, notifications, activeDashboard, setActiveDashboard } = useAuth();
  const [time, setTime] = useState(new Date().toLocaleTimeString());
  const [showNotifications, setShowNotifications] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const triggerVoiceGreeting = () => {
    setVoiceNotice(true);
    if ('speechSynthesis' in window) {
      const voiceText = language === 'ta'
        ? (activeDashboard === 'ADMIN' ? "நிர்வாக பாதுகாப்பு மேலோட்டப் பார்வை தயாராக உள்ளது." : "கேம்பஸ்கார்ட் அமைப்பிற்கு நல்வரவு. கேட் பாதுகாப்பு தயார் நிலையில் உள்ளது.")
        : (activeDashboard === 'ADMIN' ? "Welcome to CampusGuard Admin Dashboard." : "Welcome to CampusGuard. Main Gate security system is online.");
      const msg = new SpeechSynthesisUtterance(voiceText);
      msg.lang = language === 'ta' ? 'ta-IN' : 'en-US';
      window.speechSynthesis.speak(msg);
    }
    setTimeout(() => setVoiceNotice(false), 4000);
  };

  return (
    <header className="top-navbar">
      {/* Left: Mobile Toggle + Station & Gate Status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
        {/* Mobile Hamburger Menu Toggle Button */}
        <button
          type="button"
          className="mobile-menu-toggle"
          onClick={onToggleSidebar}
          aria-label="Toggle navigation menu"
        >
          <Menu size={20} />
        </button>

        {/* DEDICATED STATION BADGE (ZERO CROSS-ACCESS SWITCHING) */}
        {activeDashboard === 'ADMIN' ? (
          <div className="nav-station-badge" style={{
            display: 'flex',
            alignItems: 'center',
            gap: '7px',
            backgroundColor: '#0F172A',
            color: '#FFFFFF',
            padding: '0.45rem 1rem',
            borderRadius: '10px',
            fontSize: '0.82rem',
            fontWeight: 800,
            border: '1.5px solid #334155',
            boxShadow: '0 2px 8px rgba(15,23,42,0.25)'
          }}>
            <Building size={16} color="#60A5FA" />
            <span className="nav-station-text">{language === 'ta' ? '🏛️ கல்லூரி நிர்வாக மையம் (/admin)' : '🏛️ Campus Executive Portal (/admin)'}</span>
          </div>
        ) : (
          <div className="nav-station-badge" style={{
            display: 'flex',
            alignItems: 'center',
            gap: '7px',
            backgroundColor: '#EFF6FF',
            color: '#1D4ED8',
            padding: '0.45rem 1rem',
            borderRadius: '10px',
            fontSize: '0.82rem',
            fontWeight: 800,
            border: '1.5px solid #BFDBFE',
            boxShadow: '0 2px 6px rgba(37,99,235,0.1)'
          }}>
            <ShieldCheck size={16} color="#2563EB" />
            <span className="nav-station-text">{language === 'ta' ? '🛡️ மெயின் கேட் பாதுகாப்பு பிரிவு (/)' : '🛡️ Main Gate Security Station (/)'}</span>
          </div>
        )}

        {/* Status Pill Badge */}
        <div className="nav-gate-pill" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          backgroundColor: activeDashboard === 'ADMIN' ? '#F5F3FF' : '#ECFDF5',
          border: activeDashboard === 'ADMIN' ? '1.5px solid #DDD6FE' : '1.5px solid #A7F3D0',
          padding: '0.4rem 0.85rem',
          borderRadius: '999px',
          color: activeDashboard === 'ADMIN' ? '#6D28D9' : '#065F46',
          fontSize: '0.8rem',
          fontWeight: 800,
          letterSpacing: '0.02em'
        }}>
          <span style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: activeDashboard === 'ADMIN' ? '#8B5CF6' : '#10B981',
            display: 'inline-block',
            boxShadow: activeDashboard === 'ADMIN' ? '0 0 0 3px rgba(139, 92, 246, 0.25)' : '0 0 0 3px rgba(16, 185, 129, 0.25)'
          }} />
          <span>{activeDashboard === 'ADMIN' ? 'ADMIN • ACTIVE' : t.gateStatus}</span>
        </div>

        {/* Tamil / English Voice Assistant Button */}
        <button
          onClick={triggerVoiceGreeting}
          className="nav-voice-btn"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.45rem',
            backgroundColor: '#EFF6FF',
            border: '1.5px solid #BFDBFE',
            padding: '0.4rem 0.85rem',
            borderRadius: '8px',
            color: '#1D4ED8',
            fontSize: '0.8rem',
            fontWeight: 700
          }}
          title={language === 'ta' ? "குரல் அறிவிப்பை ஒலிக்க" : "Play Voice Announcement"}
        >
          <Volume2 size={16} />
          <span>{t.voicePromptBtn}</span>
        </button>

        {voiceNotice && (
          <div style={{
            backgroundColor: '#DBEAFE',
            color: '#1E40AF',
            fontSize: '0.78rem',
            fontWeight: 600,
            padding: '0.35rem 0.75rem',
            borderRadius: '6px',
            animation: 'fadeIn 0.2s ease',
            border: '1px solid #93C5FD'
          }}>
            🔊 {language === 'ta' ? '"கேட் பாதுகாப்பு தயார் நிலையில் உள்ளது"' : '"Gate security system is online"'}
          </div>
        )}
      </div>

      {/* Right: Prominent Language Selector, Clock, Emergency SOS */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {/* PROMINENT LANGUAGE SELECTOR (Marked by User in red box) */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          backgroundColor: '#F1F5F9',
          padding: '3px',
          borderRadius: '10px',
          border: '1.5px solid #CBD5E1',
          gap: '2px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
        }}>
          <button
            onClick={() => changeLanguage('en')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '7px',
              fontSize: '0.825rem',
              fontWeight: 700,
              backgroundColor: language === 'en' ? '#2563EB' : 'transparent',
              color: language === 'en' ? '#FFFFFF' : '#475569',
              boxShadow: language === 'en' ? '0 2px 6px rgba(37, 99, 235, 0.3)' : 'none',
              transition: 'all 0.15s ease'
            }}
          >
            <span>🇬🇧</span>
            <span>English</span>
          </button>

          <button
            onClick={() => changeLanguage('ta')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '7px',
              fontSize: '0.825rem',
              fontWeight: 700,
              backgroundColor: language === 'ta' ? '#2563EB' : 'transparent',
              color: language === 'ta' ? '#FFFFFF' : '#475569',
              boxShadow: language === 'ta' ? '0 2px 6px rgba(37, 99, 235, 0.3)' : 'none',
              transition: 'all 0.15s ease'
            }}
          >
            <span>🇮🇳</span>
            <span>தமிழ்</span>
          </button>
        </div>

        {/* Live Clock */}
        <div className="nav-clock-box" style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.45rem',
          color: '#334155',
          fontSize: '0.85rem',
          fontWeight: 700,
          backgroundColor: '#FFFFFF',
          border: '1.5px solid #E2E8F0',
          padding: '0.4rem 0.85rem',
          borderRadius: '8px',
          boxShadow: 'var(--shadow-sm)'
        }}>
          <Clock size={16} color="#2563EB" />
          <span>{time}</span>
        </div>

        {/* Emergency SOS Button */}
        <button
          onClick={onOpenSosModal}
          className="pulse-sos"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            backgroundColor: '#DC2626',
            color: '#FFFFFF',
            padding: '0.5rem 1.15rem',
            borderRadius: '8px',
            fontWeight: 800,
            fontSize: '0.85rem',
            letterSpacing: '0.02em',
            boxShadow: '0 4px 14px rgba(220, 38, 38, 0.35)'
          }}
        >
          <AlertTriangle size={17} />
          <span>{t.sosTrigger}</span>
        </button>

        {/* Notifications */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: '#FFFFFF',
              border: '1.5px solid #E2E8F0',
              color: '#334155',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative'
            }}
          >
            <Bell size={18} />
            <span style={{
              position: 'absolute',
              top: '7px',
              right: '7px',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: '#EF4444'
            }} />
          </button>

          {showNotifications && (
            <div style={{
              position: 'absolute',
              right: 0,
              top: '48px',
              width: '330px',
              backgroundColor: '#FFFFFF',
              borderRadius: '14px',
              boxShadow: 'var(--shadow-xl)',
              border: '1.5px solid var(--border-blue)',
              padding: '1.15rem',
              zIndex: 100,
              animation: 'fadeIn 0.2s ease'
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: '0.65rem',
                borderBottom: '1px solid var(--border-light)',
                marginBottom: '0.85rem'
              }}>
                <div style={{ fontWeight: 800, fontSize: '0.925rem', color: '#0F172A' }}>
                  {t.alertsTitle}
                </div>
                <button
                  onClick={() => setShowNotifications(false)}
                  style={{ background: 'none', color: '#94A3B8' }}
                >
                  <X size={16} />
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                {notifications.map((n) => (
                  <div key={n.id} style={{
                    padding: '0.6rem 0.75rem',
                    borderRadius: '8px',
                    backgroundColor: n.unread ? '#EFF6FF' : '#F8FAFC',
                    border: n.unread ? '1px solid #BFDBFE' : '1px solid #E2E8F0',
                    fontSize: '0.8rem',
                    color: '#1E293B'
                  }}>
                    <div style={{ fontWeight: 600 }}>
                      {language === 'ta' ? n.textTa : n.textEn}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '3px' }}>
                      {n.time}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
