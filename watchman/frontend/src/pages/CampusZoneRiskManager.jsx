import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  CloudRain,
  AlertTriangle,
  ShieldAlert,
  Wind,
  Droplets,
  Thermometer,
  CheckCircle,
  RefreshCw,
  MapPin,
  Flame,
  Check,
  Eye
} from 'lucide-react';

export const CampusZoneRiskManager = () => {
  const { language } = useAuth();
  const [zones, setZones] = useState([]);
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(false);
  const [successBanner, setSuccessBanner] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [zData, wData] = await Promise.all([
        api.getZoneMonitoring(),
        api.getWeatherTelemetry()
      ]);
      setZones(zData || []);
      setWeather(wData || null);
    } catch {
      setZones([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleInspect = async (zoneId) => {
    await api.inspectZone(zoneId, true);
    setSuccessBanner('Zone inspected and safety verified. Risk indicators refreshed.');
    setTimeout(() => setSuccessBanner(null), 3500);
    fetchData();
  };

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* ── Top Header ────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ padding: '0.5rem', background: '#eff6ff', borderRadius: '10px', color: '#2563eb' }}>
              <CloudRain size={26} strokeWidth={2.4} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
                {language === 'ta' ? 'வானிலை எச்சரிக்கை & வளாக மண்டல கண்காணிப்பு' : 'Weather Alerts & Campus Zone Monitoring'}
              </h1>
              <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '0.2rem 0 0' }}>
                {language === 'ta' ? 'மழை/புயல் அபாய எச்சரிக்கைகள், தொடர் புகார்கள் & மண்டல ஆபத்து பகுப்பாய்வு (Pillars 8 & 11)' : 'Pillars 8 & 11: Real-time campus weather hazard telemetry & automated zone attention radar'}
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={fetchData}
          className="btn btn-secondary"
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700 }}
        >
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          {language === 'ta' ? 'புதுப்பி' : 'Refresh Telemetry'}
        </button>
      </div>

      {successBanner && (
        <div style={{ padding: '0.85rem 1.25rem', background: '#ecfdf5', color: '#065f46', borderRadius: '12px', border: '1px solid #a7f3d0', fontWeight: 700, marginBottom: '1.25rem' }}>
          {successBanner}
        </div>
      )}

      {/* ── Weather Hazard Telemetry Card (Pillar 8) ──────────── */}
      {weather && (
        <div
          style={{
            background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
            color: 'white',
            borderRadius: '20px',
            padding: '1.75rem',
            marginBottom: '2rem',
            boxShadow: '0 10px 30px rgba(15, 23, 42, 0.25)',
            border: '1px solid rgba(255, 255, 255, 0.1)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 800, padding: '0.2rem 0.6rem', borderRadius: '999px', background: '#f59e0b', color: '#000000' }}>
                  ACTIVE WEATHER HAZARD &bull; {weather.hazard_level}
                </span>
                <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Live Campus Station</span>
              </div>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '0 0 0.25rem' }}>
                {weather.hazard_title}
              </h2>
              <div style={{ fontSize: '0.88rem', color: '#cbd5e1' }}>
                Forecast Condition: <strong>{weather.condition}</strong>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '1.5rem', background: 'rgba(255, 255, 255, 0.05)', padding: '0.85rem 1.25rem', borderRadius: '14px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
              <div style={{ textAlign: 'center' }}>
                <Thermometer size={18} color="#f87171" style={{ margin: '0 auto 0.25rem' }} />
                <div style={{ fontSize: '1.15rem', fontWeight: 900 }}>{weather.temperature_celsius}°C</div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>TEMP</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <Droplets size={18} color="#60a5fa" style={{ margin: '0 auto 0.25rem' }} />
                <div style={{ fontSize: '1.15rem', fontWeight: 900 }}>{weather.rainfall_probability}%</div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>RAIN</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <Wind size={18} color="#34d399" style={{ margin: '0 auto 0.25rem' }} />
                <div style={{ fontSize: '1.15rem', fontWeight: 900 }}>{weather.wind_speed_kmh}</div>
                <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>KM/H WIND</div>
              </div>
            </div>
          </div>

          <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.1)', paddingTop: '1rem' }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#f59e0b', textTransform: 'uppercase', marginBottom: '0.5rem', letterSpacing: '0.04em' }}>
              🛡️ Mandatory Guard Safety Checklist:
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.65rem' }}>
              {weather.safety_checklist.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: '#e2e8f0' }}>
                  <Check size={16} color="#10b981" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Campus Zone Monitoring Heatmap (Pillar 11) ───────── */}
      <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0f172a', marginBottom: '1rem' }}>
        Campus Zone Monitoring & Attention Radar
      </h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
        {zones.map((zone) => {
          const isHigh = zone.risk_level === 'HIGH';
          const isAttention = zone.attention_needed;

          return (
            <div
              key={zone.id}
              style={{
                background: 'white',
                borderRadius: '16px',
                border: isHigh ? '2px solid #ef4444' : isAttention ? '1.5px solid #f59e0b' : '1px solid #e2e8f0',
                padding: '1.25rem',
                boxShadow: '0 4px 12px rgba(0,0,0,0.03)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#64748b', letterSpacing: '0.04em' }}>
                    {zone.zone_code}
                  </span>

                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      padding: '0.2rem 0.55rem',
                      borderRadius: '999px',
                      background: isHigh ? '#fee2e2' : zone.risk_level === 'MODERATE' ? '#fef3c7' : '#ecfdf5',
                      color: isHigh ? '#b91c1c' : zone.risk_level === 'MODERATE' ? '#b45309' : '#047857'
                    }}
                  >
                    {zone.risk_level} RISK
                  </span>
                </div>

                <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a', margin: '0 0 0.35rem' }}>
                  {zone.zone_name}
                </h3>

                {isAttention && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#b91c1c', fontSize: '0.78rem', fontWeight: 800, marginBottom: '0.65rem' }}>
                    <AlertTriangle size={15} />
                    <span>ATTENTION NEEDED: {zone.repeated_complaints_count} Repeated Complaints</span>
                  </div>
                )}

                <p style={{ fontSize: '0.85rem', color: '#475569', lineHeight: 1.5, margin: '0 0 0.85rem' }}>
                  {zone.recommendation}
                </p>

                {zone.weather_hazard && zone.weather_hazard !== 'Normal' && (
                  <div style={{ padding: '0.45rem 0.75rem', background: '#fef2f2', color: '#991b1b', borderRadius: '8px', fontSize: '0.78rem', fontWeight: 700, marginBottom: '1rem' }}>
                    ⚠️ {zone.weather_hazard}
                  </div>
                )}
              </div>

              <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '0.85rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  Last Checked: {new Date(zone.last_inspected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>

                <button
                  onClick={() => handleInspect(zone.id)}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.78rem', padding: '0.4rem 0.75rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                >
                  <Eye size={14} />
                  Mark Inspected
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
