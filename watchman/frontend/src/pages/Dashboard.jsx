import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Users,
  DoorOpen,
  ArrowDownLeft,
  ArrowUpRight,
  ClockAlert,
  PackageCheck,
  ShieldCheck,
  CheckCircle2,
  FileCheck,
  Car
} from 'lucide-react';

export const Dashboard = ({ setActiveTab }) => {
  const { stats, t, language, outPasses } = useAuth();
  const pendingPassesCount = (outPasses || []).filter((p) => p.status === 'PENDING' || p.status === 'APPROVED_BY_HOD').length;

  const statCards = [
    {
      title: t.liveCampus,
      value: stats.totalOnCampus.toLocaleString(),
      change: language === 'ta' ? '+18 கடந்த மணிநேரத்தில்' : '+18 in last hour',
      icon: Users,
      color: '#2563EB',
      bg: '#EFF6FF',
    },
    {
      title: t.inToday,
      value: stats.entriesToday.toLocaleString(),
      change: language === 'ta'
        ? (stats.lateEntriesToday > 0 ? `${t.normalFlow} (${stats.lateEntriesToday} தாமதம்)` : t.normalFlow)
        : (stats.lateEntriesToday > 0 ? `${t.normalFlow} (${stats.lateEntriesToday} late)` : t.normalFlow),
      icon: ArrowDownLeft,
      color: '#10B981',
      bg: '#ECFDF5',
    },
    {
      title: t.outToday,
      value: stats.exitsToday.toLocaleString(),
      change: t.onSchedule,
      icon: ArrowUpRight,
      color: '#6366F1',
      bg: '#EEF2FF',
    },
    {
      title: t.activeVisitors,
      value: stats.activeVisitors.toString(),
      change: t.activePassesIssued,
      icon: DoorOpen,
      color: '#0EA5E9',
      bg: '#F0F9FF',
    },
  ];

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Quick Action Shortcuts Bar (Header cleaned & reduced) */}
      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '14px',
        border: '1.5px solid #DBEAFE',
        padding: '0.75rem 1.25rem',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        background: 'linear-gradient(135deg, #FFFFFF 60%, #EFF6FF 100%)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="badge badge-blue" style={{ fontSize: '0.78rem', padding: '0.25rem 0.6rem' }}>
            {t.badgeSystem}
          </span>
          <span style={{ fontSize: '0.8rem', color: '#64748B', fontWeight: 700 }}>
            {t.academicYear}
          </span>
        </div>

        {/* Quick Action Shortcuts */}
        <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setActiveTab('vehicles')}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', padding: '0.5rem 1.15rem', fontSize: '0.85rem' }}
          >
            <Car size={16} />
            <span>{t.navVehicles}</span>
          </button>
          <button
            onClick={() => setActiveTab('gate-kiosk')}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', padding: '0.5rem 1.15rem', fontSize: '0.85rem' }}
          >
            <DoorOpen size={16} />
            <span>{t.btnOpenKiosk}</span>
          </button>
          <button
            onClick={() => setActiveTab('out-pass')}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', padding: '0.5rem 1.15rem', fontSize: '0.85rem' }}
          >
            <FileCheck size={16} />
            <span>{t.btnVerifyPasses}</span>
          </button>
        </div>
      </div>

      {/* 4 Key Stat Cards in a Single Row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '1rem'
      }}>
        {statCards.map((card, idx) => {
          const Icon = card.icon;
          return (
            <div
              key={idx}
              className="card"
              style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                padding: '0.9rem 1.1rem',
                borderRadius: '12px',
                border: '1px solid #E2E8F0',
                boxShadow: '0 1px 4px rgba(0,0,0,0.04)'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.45rem' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748B' }}>
                  {card.title}
                </span>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  backgroundColor: card.bg,
                  color: card.color,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <Icon size={17} strokeWidth={2.4} />
                </div>
              </div>

              <div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', lineHeight: 1.15 }}>
                  {card.value}
                </div>
                <div style={{
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  color: card.isWarning ? '#D97706' : '#059669',
                  marginTop: '0.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem'
                }}>
                  <span>{card.change}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>


      {/* Campus Capacity & Peak Rush Info */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A' }}>
              {t.capacityTitle}
            </h3>
            <p style={{ fontSize: '0.8rem', color: '#64748B' }}>
              {t.capacitySubtitle}
            </p>
          </div>
          <span className="badge badge-green">{t.safeOccupancy}</span>
        </div>

        {/* Capacity Progress Bar */}
        <div style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: 700, marginBottom: '0.45rem' }}>
            <span style={{ color: '#334155' }}>{t.currentOccupancy}: 1,420 / {t.capacityLimit}</span>
            <span style={{ color: '#2563EB' }}>71%</span>
          </div>
          <div style={{
            width: '100%',
            height: '12px',
            backgroundColor: '#EFF6FF',
            borderRadius: '999px',
            overflow: 'hidden',
            border: '1px solid #DBEAFE'
          }}>
            <div style={{
              width: '71%',
              height: '100%',
              background: 'linear-gradient(90deg, #3B82F6 0%, #2563EB 100%)',
              borderRadius: '999px'
            }} />
          </div>
        </div>

        {/* Peak Times Info Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div style={{
            padding: '1.1rem',
            borderRadius: '12px',
            backgroundColor: '#F8FAFD',
            border: '1px solid #E2E8F0'
          }}>
            <div style={{ fontSize: '0.8rem', color: '#64748B', fontWeight: 700 }}>
              {t.rushHourTitle}
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#1E40AF', marginTop: '0.2rem' }}>
              {t.rushHourTime}
            </div>
            <div style={{ fontSize: '0.78rem', color: '#059669', fontWeight: 600, marginTop: '0.35rem' }}>
              ⚡ {t.rushHourDesc}
            </div>
          </div>

          <div style={{
            padding: '1.1rem',
            borderRadius: '12px',
            backgroundColor: '#F8FAFD',
            border: '1px solid #E2E8F0'
          }}>
            <div style={{ fontSize: '0.8rem', color: '#64748B', fontWeight: 700 }}>
              {t.curfewTitle}
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#DC2626', marginTop: '0.2rem' }}>
              {t.curfewTime}
            </div>
            <div style={{ fontSize: '0.78rem', color: '#B91C1C', fontWeight: 600, marginTop: '0.35rem' }}>
              🔒 {t.curfewDesc}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
