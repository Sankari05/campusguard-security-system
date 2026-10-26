import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  ShieldCheck,
  LayoutDashboard,
  DoorOpen,
  FileBadge,
  Users,
  Package,
  Car,
  AlertOctagon,
  LogOut,
  Shield,
  Clock,
  ClipboardCheck,
  Building,
  Wrench,
  Compass,
  PackageCheck,
  UserCheck,
  CloudRain,
  Sparkles,
  X
} from 'lucide-react';

export const Sidebar = ({ activeTab, setActiveTab, isOpen, onClose }) => {
  const { user, t, logout, stats, outPasses, parcels, language, activeDashboard, setActiveDashboard } = useAuth();

  const pendingPassesCount = outPasses.filter((p) => p.status === 'PENDING' || p.status === 'APPROVED_BY_HOD').length;
  const pendingParcelsCount = parcels.filter((p) => p.status === 'WAITING_COLLECTION').length;

  // ── R&D Priority Hierarchy for Watchman ─────────────────────────
  // 1. ROUTINE GATE ACCESS (Highest Frequency - Continuous Daily Work)
  // 2. AI ASSISTANCE & OVERSIGHT (Real-Time Situational Awareness)
  // 3. SHIFT & DESK ROUTINES (Periodic / Shift Tasks)
  // 4. INCIDENTS & DEFECTS (Occasional / As-Needed)
  // 5. CONTINGENCY & PLATFORM (Emergency & System Admin)
  const securityMenuSections = [
    {
      titleEn: 'Routine Gate Access',
      titleTa: 'அன்றாட கேட் பணிகள்',
      items: [
        {
          id: 'vehicles',
          label: language === 'ta' ? 'வாகன அனுமதி (ANPR)' : (t.navVehicles || 'Vehicle Parking Log'),
          icon: Car,
          badge: 'ANPR',
          badgeColor: 'badge-blue',
        },
        {
          id: 'visitors',
          label: t.navVisitors || 'Visitor Management',
          icon: Users,
          badge: stats.activeVisitors > 0 ? `${stats.activeVisitors}` : 'Active',
          badgeColor: 'badge-blue',
        },
        {
          id: 'parking',
          label: language === 'ta' ? 'பார்க்கிங் மேலாண்மை' : 'Smart Parking',
          icon: Car,
          badge: 'Live',
          badgeColor: 'badge-green',
        },
        {
          id: 'out-pass',
          label: language === 'ta' ? 'அவுட்-பாஸ் சரிபார்ப்பு' : 'Student Out-Pass Kiosk',
          icon: DoorOpen,
          badge: pendingPassesCount > 0 ? `${pendingPassesCount}` : null,
          badgeColor: 'badge-amber',
        },
      ]
    },
    {
      titleEn: 'AI & Situation Monitoring',
      titleTa: 'AI கண்காணிப்பு & ரேடார்',
      items: [
        {
          id: 'copilot',
          label: language === 'ta' ? 'AI கார்டு கோ-பைலட்' : 'AI Guard Co-Pilot',
          icon: Sparkles,
          badge: 'Radar',
          badgeColor: 'badge-purple',
        },
        {
          id: 'dashboard',
          label: language === 'ta' ? 'கேட் மேலோட்டம் & லாக்' : (t.navDashboard || 'Gate Overview & Stats'),
          icon: LayoutDashboard,
          badge: 'Live',
          badgeColor: 'badge-blue',
        },
      ]
    },
    {
      titleEn: 'Shift & Desk Routines',
      titleTa: 'ஷிப்ட் & மேசை பணிகள்',
      items: [
        {
          id: 'parcels',
          label: t.navParcels || 'Parcel & Courier Desk',
          icon: Package,
          badge: pendingParcelsCount > 0 ? `${pendingParcelsCount}` : null,
          badgeColor: 'badge-green',
        },
        {
          id: 'patrol',
          label: language === 'ta' ? 'ரோந்து & QR சரிபார்ப்பு' : 'Patrol Checkpoints',
          icon: Compass,
          badge: 'QR',
          badgeColor: 'badge-purple',
        },
        {
          id: 'duty',
          label: language === 'ta' ? 'பணி வருகை & லாக்' : 'Duty Attendance',
          icon: UserCheck,
          badge: 'Active',
          badgeColor: 'badge-blue',
        },
        {
          id: 'handover',
          label: t.navHandover || 'Shift Handover',
          icon: ClipboardCheck,
          badge: 'Smart',
          badgeColor: 'badge-amber',
        },
      ]
    },
    {
      titleEn: 'Incidents & Defects',
      titleTa: 'பழுது & குறைதீர்ப்பு (அவ்வப்போது)',
      items: [
        {
          id: 'maintenance',
          label: language === 'ta' ? 'பராமரிப்பு பழுதுகள்' : 'Maintenance Defect',
          icon: Wrench,
          badge: 'Open',
          badgeColor: 'badge-amber',
        },
        {
          id: 'lost-found',
          label: language === 'ta' ? 'தொலைந்தவை & கிடைத்தவை' : 'Lost & Found',
          icon: PackageCheck,
          badge: 'AI Match',
          badgeColor: 'badge-green',
        },
        {
          id: 'zone-risk',
          label: language === 'ta' ? 'வானிலை & மண்டல ஆபத்து' : 'Zone Risk & Weather',
          icon: CloudRain,
          badge: 'Alert',
          badgeColor: 'badge-red',
        },
      ]
    },
    {
      titleEn: 'Contingency & Platform',
      titleTa: 'அவசரம் & அமைப்புகள்',
      items: [
        {
          id: 'emergency',
          label: t.navEmergency || 'Emergency SOS Alert',
          icon: AlertOctagon,
          badge: 'SOS',
          badgeColor: 'badge-red',
        },
        {
          id: 'guardmate-workspace',
          label: language === 'ta' ? 'கார்டுமேட் பிரத்யேக தளம்' : 'GuardMate Facility OS',
          icon: Shield,
          badge: 'Multi-Tenant',
          badgeColor: 'badge-blue',
        },
      ]
    }
  ];

  const adminMenuSections = [
    {
      titleEn: 'Executive Governance',
      titleTa: 'நிர்வாகப் பிரிவு',
      items: [
        {
          id: 'admin-dashboard',
          label: language === 'ta' ? 'நிர்வாக மேலோட்டம்' : 'Executive Overview',
          icon: Building,
          badge: 'Admin',
          badgeColor: 'badge-blue',
        },
        {
          id: 'admin-compliance',
          label: language === 'ta' ? 'தாமத வருகை (24)' : 'Late Arrivals (24)',
          icon: Clock,
          badge: 'Discipline',
          badgeColor: 'badge-amber',
        },
        {
          id: 'admin-overdues',
          label: language === 'ta' ? 'அவுட்பாஸ் மீறல்கள் (3)' : 'Curfew Overdues (3)',
          icon: AlertOctagon,
          badge: 'Critical',
          badgeColor: 'badge-red',
        },
        {
          id: 'admin-shifts',
          label: language === 'ta' ? 'ஷிப்ட் தணிக்கை' : 'Shift Governance Audit',
          icon: ClipboardCheck,
          badge: 'Audited',
          badgeColor: 'badge-green',
        },
      ]
    }
  ];

  const currentSections = activeDashboard === 'ADMIN' ? adminMenuSections : securityMenuSections;

  return (
    <>
      {isOpen && (
        <div
          className="sidebar-backdrop"
          onClick={onClose}
        />
      )}

      <aside className={`app-sidebar ${isOpen ? 'open' : ''}`}>
        {/* Brand Header */}
        <div style={{
          padding: '1.25rem',
          borderBottom: '1px solid var(--border-blue)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.85rem'
        }}>
        <div style={{
          width: '42px',
          height: '42px',
          borderRadius: '12px',
          background: activeDashboard === 'ADMIN'
            ? 'linear-gradient(135deg, #0F172A 0%, #334155 100%)'
            : 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#FFFFFF',
          boxShadow: activeDashboard === 'ADMIN'
            ? '0 4px 10px rgba(15, 23, 42, 0.3)'
            : '0 4px 10px rgba(37, 99, 235, 0.3)',
          flexShrink: 0
        }}>
          {activeDashboard === 'ADMIN' ? (
            <Building size={24} strokeWidth={2.4} />
          ) : (
            <ShieldCheck size={26} strokeWidth={2.4} />
          )}
        </div>
        <div>
          <div style={{
            fontFamily: 'var(--font-heading)',
            fontSize: '1.25rem',
            fontWeight: 800,
            color: 'var(--primary)',
            letterSpacing: '-0.02em',
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem'
          }}>
            {t.appTitle}
            <span style={{
              fontSize: '0.65rem',
              backgroundColor: activeDashboard === 'ADMIN' ? '#F5F3FF' : '#EFF6FF',
              color: activeDashboard === 'ADMIN' ? '#7C3AED' : '#2563EB',
              border: activeDashboard === 'ADMIN' ? '1px solid #DDD6FE' : '1px solid #BFDBFE',
              padding: '0.1rem 0.4rem',
              borderRadius: '999px',
              fontWeight: 800
            }}>
              {activeDashboard === 'ADMIN' ? 'ADMIN' : 'GATE'}
            </span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            {activeDashboard === 'ADMIN'
              ? (language === 'ta' ? 'நிர்வாகப் பிரிவு' : 'Executive Governance')
              : t.appSubtitle}
          </div>
        </div>

        {/* Mobile close button visible on tablets & mobile */}
        <button
          type="button"
          className="mobile-sidebar-close"
          onClick={onClose}
          aria-label="Close menu"
        >
          <X size={18} />
        </button>
      </div>



      {/* Navigation List Grouped by Priority */}
      <nav style={{ flex: 1, padding: '0.65rem 0.75rem', overflowY: 'auto' }}>
        {currentSections.map((section) => (
          <div key={section.titleEn} style={{ marginBottom: '0.85rem' }}>
            <div style={{
              fontSize: '0.67rem',
              fontWeight: 800,
              color: '#94A3B8',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              padding: '0.35rem 0.5rem 0.35rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <span>{language === 'ta' ? section.titleTa : section.titleEn}</span>
              <span style={{
                fontSize: '0.65rem',
                backgroundColor: '#F1F5F9',
                color: '#64748B',
                fontWeight: 700,
                padding: '1px 6px',
                borderRadius: '999px'
              }}>
                {section.items.length}
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setActiveTab(item.id);
                      if (onClose) onClose();
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.65rem 0.75rem',
                      borderRadius: '10px',
                      backgroundColor: isActive ? '#EFF6FF' : 'transparent',
                      color: isActive ? '#1D4ED8' : '#334155',
                      fontWeight: isActive ? 800 : 600,
                      fontSize: '0.86rem',
                      border: isActive ? '1.5px solid #93C5FD' : '1px solid transparent',
                      width: '100%',
                      textAlign: 'left',
                      transition: 'all 0.15s ease',
                      boxShadow: isActive ? '0 1px 3px rgba(37,99,235,0.08)' : 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', minWidth: 0 }}>
                      <Icon size={18} color={isActive ? '#2563EB' : '#64748B'} strokeWidth={isActive ? 2.4 : 1.9} style={{ flexShrink: 0 }} />
                      <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.label}</span>
                    </div>
                    {item.badge && (
                      <span className={`badge ${item.badgeColor || 'badge-blue'}`} style={{ fontSize: '0.68rem', padding: '0.15rem 0.45rem', flexShrink: 0, marginLeft: '4px' }}>
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom Footer: Watchman Profile & Logout */}
      <div style={{
        padding: '1rem',
        borderTop: '1px solid var(--border-blue)',
        backgroundColor: '#FAFCFF'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.2rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', overflow: 'hidden' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              backgroundColor: activeDashboard === 'ADMIN' ? '#EDE9FE' : '#DBEAFE',
              color: activeDashboard === 'ADMIN' ? '#6D28D9' : '#1D4ED8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: '0.9rem',
              flexShrink: 0
            }}>
              {activeDashboard === 'ADMIN' ? 'S' : 'R'}
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div style={{
                fontSize: '0.85rem',
                fontWeight: 800,
                color: '#0F172A',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}>
                {activeDashboard === 'ADMIN'
                  ? 'Dr. K. Sundararajan'
                  : 'Ramasamy (Main Gate)'}
              </div>
              <div style={{ fontSize: '0.725rem', color: '#64748B', fontWeight: 600 }}>
                {activeDashboard === 'ADMIN'
                  ? (language === 'ta' ? 'வளாக இயக்குனர் & நிர்வாகி' : 'Campus Director & Admin')
                  : t.gateName}
              </div>
            </div>
          </div>

          <button
            onClick={() => {
              logout();
              if (onClose) onClose();
            }}
            title={t.logout}
            style={{
              width: '34px',
              height: '34px',
              borderRadius: '8px',
              backgroundColor: '#FEE2E2',
              color: '#DC2626',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              transition: 'all 0.15s ease'
            }}
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
    </>
  );
};
