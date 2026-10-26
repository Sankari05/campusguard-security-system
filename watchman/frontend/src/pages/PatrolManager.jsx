import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Compass,
  QrCode,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldCheck,
  MapPin,
  Camera,
  Play
} from 'lucide-react';

export const PatrolManager = () => {
  const { user, language } = useAuth();
  const [checkpoints, setCheckpoints] = useState([]);
  const [patrolStatus, setPatrolStatus] = useState({ total_checkpoints: 0, completed_today: 0, missed_count: 0, next_due_checkpoint: null, next_due_time: 'Now' });
  const [loading, setLoading] = useState(false);
  const [scanningCheckpoint, setScanningCheckpoint] = useState(null);
  const [scanRemarks, setScanRemarks] = useState('');
  const [successBanner, setSuccessBanner] = useState(null);

  const fetchPatrolData = async () => {
    setLoading(true);
    try {
      const [cps, stat] = await Promise.all([
        api.getPatrolCheckpoints(),
        api.getPatrolStatus()
      ]);
      setCheckpoints(cps || []);
      setPatrolStatus(stat || {});
    } catch {
      setCheckpoints([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPatrolData();
  }, []);

  const handleSimulateScan = async (cp) => {
    const res = await api.scanPatrolCheckpoint({
      qr_token: cp.qr_token,
      guard_id: user?.username || 'watchman1',
      guard_name: user?.fullName || 'Ramasamy (Main Gate Security)',
      remarks: scanRemarks || `Checkpoint ${cp.name} scanned and verified clear.`
    });

    setScanningCheckpoint(null);
    setScanRemarks('');
    setSuccessBanner(`✅ Checkpoint ${cp.name} verified successfully at ${new Date().toLocaleTimeString()}!`);
    setTimeout(() => setSuccessBanner(null), 4000);
    fetchPatrolData();
  };

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* ── Top Header ────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ padding: '0.5rem', background: '#f5f3ff', borderRadius: '10px', color: '#7c3aed' }}>
              <Compass size={26} strokeWidth={2.4} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
                {language === 'ta' ? 'ஸ்மார்ட் ரோந்து & கியூஆர் சரிபார்ப்பு' : 'Smart Campus Patrolling & Missed Checkpoint Alert'}
              </h1>
            </div>
          </div>
        </div>
      </div>

      {successBanner && (
        <div style={{ padding: '0.85rem 1.25rem', background: '#ecfdf5', color: '#065f46', borderRadius: '12px', border: '1px solid #a7f3d0', fontWeight: 700, marginBottom: '1.25rem' }}>
          {successBanner}
        </div>
      )}

      {/* ── Status Metrics ───────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ background: 'white', borderRadius: '14px', padding: '1.1rem', border: '1px solid #e2e8f0', boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}>
          <div style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 700 }}>DESIGNATED CHECKPOINTS</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 900, color: '#0f172a' }}>{checkpoints.length}</div>
        </div>
        <div style={{ background: '#ecfdf5', borderRadius: '14px', padding: '1.1rem', border: '1px solid #d1fae5' }}>
          <div style={{ fontSize: '0.8rem', color: '#059669', fontWeight: 700 }}>PATROLS COMPLETED TODAY</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 900, color: '#047857' }}>
            {patrolStatus.completed_today || 8}
          </div>
        </div>
        <div style={{ background: '#fef2f2', borderRadius: '14px', padding: '1.1rem', border: '1px solid #fee2e2' }}>
          <div style={{ fontSize: '0.8rem', color: '#dc2626', fontWeight: 700 }}>MISSED CHECKPOINTS</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 900, color: '#b91c1c' }}>
            {patrolStatus.missed_count || 0}
          </div>
        </div>
        <div style={{ background: '#eff6ff', borderRadius: '14px', padding: '1.1rem', border: '1px solid #dbeafe' }}>
          <div style={{ fontSize: '0.8rem', color: '#2563eb', fontWeight: 700 }}>NEXT DUE PATROL</div>
          <div style={{ fontSize: '1rem', fontWeight: 800, color: '#1e40af', marginTop: '0.25rem' }}>
            {patrolStatus.next_due_checkpoint || 'Faculty Parking Lot'}
          </div>
          <div style={{ fontSize: '0.78rem', color: '#3b82f6' }}>Due: In 25 minutes</div>
        </div>
      </div>

      {/* ── Checkpoints Patrol Route ─────────────────────────── */}
      <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0f172a', marginBottom: '1rem' }}>
        {language === 'ta' ? 'கேம்பஸ் பாதுகாப்பு ரோந்து பாதைகள் (Patrol Sequence)' : 'Active Patrol Route & QR Checkpoints'}
      </h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
        {checkpoints.map((cp, idx) => (
          <div
            key={cp.id}
            style={{
              background: 'white',
              borderRadius: '16px',
              border: '1px solid #e2e8f0',
              padding: '1.25rem',
              boxShadow: '0 4px 12px rgba(0,0,0,0.03)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 800, padding: '0.2rem 0.55rem', borderRadius: '6px', background: '#f5f3ff', color: '#7c3aed' }}>
                  STEP #{idx + 1} &bull; {cp.checkpoint_code}
                </span>
                <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 800 }}>
                  ACTIVE ROUTE
                </span>
              </div>

              <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f172a', margin: '0 0 0.35rem' }}>
                {cp.name}
              </h3>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.82rem', color: '#64748b', marginBottom: '0.75rem' }}>
                <MapPin size={15} color="#94a3b8" />
                <span>{cp.location_description}</span>
              </div>

              <div style={{ padding: '0.6rem 0.8rem', background: '#f8fafc', borderRadius: '10px', border: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                <div style={{ fontSize: '0.75rem', color: '#475569' }}>
                  QR Token: <strong>{cp.qr_token}</strong>
                </div>
                <QrCode size={20} color="#64748b" />
              </div>
            </div>

            <button
              onClick={() => setScanningCheckpoint(cp)}
              className="btn btn-primary"
              style={{ width: '100%', fontSize: '0.85rem', fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.45rem' }}
            >
              <QrCode size={16} />
              {language === 'ta' ? 'QR ஸ்கேன் செய்' : 'Simulate QR Check-in'}
            </button>
          </div>
        ))}
      </div>

      {/* ── Scan Simulator Modal ──────────────────────────────── */}
      {scanningCheckpoint && (
        <div className="modal-backdrop">
          <div className="modal-content" style={{ maxWidth: '460px', borderRadius: '20px' }}>
            <div style={{ textAlign: 'center', marginBottom: '1.25rem' }}>
              <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: '#f5f3ff', color: '#7c3aed', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 0.75rem' }}>
                <QrCode size={32} />
              </div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: '0 0 0.3rem' }}>
                {scanningCheckpoint.name}
              </h2>
              <p style={{ fontSize: '0.82rem', color: '#64748b', margin: 0 }}>
                Token: <strong>{scanningCheckpoint.qr_token}</strong>
              </p>
            </div>

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                Inspection Notes (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g., Gate padlocks secure, lighting verified"
                value={scanRemarks}
                onChange={(e) => setScanRemarks(e.target.value)}
                style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1' }}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setScanningCheckpoint(null)}
                className="btn btn-secondary"
                style={{ fontWeight: 700 }}
              >
                Cancel
              </button>
              <button
                onClick={() => handleSimulateScan(scanningCheckpoint)}
                className="btn btn-primary"
                style={{ fontWeight: 800, background: '#7c3aed', borderColor: '#7c3aed' }}
              >
                Confirm Scan Verification
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
