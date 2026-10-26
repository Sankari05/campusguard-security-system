import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Clock,
  UserCheck,
  Shield,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Play,
  Square,
  FileText,
  User
} from 'lucide-react';

export const DutyLogManager = () => {
  const { user, language } = useAuth();
  const [currentDuty, setCurrentDuty] = useState(null);
  const [dutyHistory, setDutyHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showClockOutModal, setShowClockOutModal] = useState(false);
  const [supervisorNotes, setSupervisorNotes] = useState('');

  const guardId = user?.username || 'watchman1';

  const fetchDuty = async () => {
    setLoading(true);
    try {
      const duty = await api.getCurrentDuty(guardId);
      setCurrentDuty(duty || null);
      setDutyHistory([
        { id: 101, guard_name: 'Ramasamy (Main Gate Security)', shift_name: 'Morning Shift (06:00 AM - 02:00 PM)', clock_in: new Date(Date.now() - 5 * 3600000).toISOString(), clock_out: null, is_active: true, total_patrols_done: 4, total_incidents_handled: 0 },
        { id: 100, guard_name: 'Murugan (Shift B)', shift_name: 'Night Shift (10:00 PM - 06:00 AM)', clock_in: new Date(Date.now() - 24 * 3600000).toISOString(), clock_out: new Date(Date.now() - 16 * 3600000).toISOString(), is_active: false, total_patrols_done: 6, total_incidents_handled: 1 }
      ]);
    } catch {
      setCurrentDuty(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDuty();
  }, []);

  const handleClockIn = async () => {
    const res = await api.clockInDuty({
      guard_id: guardId,
      guard_name: user?.fullName || 'Ramasamy (Main Gate Security)',
      shift_name: 'Morning Shift (06:00 AM - 02:00 PM)',
      gate_assigned: 'Main Campus Ingress'
    });
    setCurrentDuty(res);
    fetchDuty();
  };

  const handleClockOut = async () => {
    await api.clockOutDuty({
      guard_id: guardId,
      supervisor_notes: supervisorNotes || 'Shift completed. Shift handover acknowledged.'
    });
    setShowClockOutModal(false);
    setSupervisorNotes('');
    fetchDuty();
  };

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* ── Top Header ────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ padding: '0.5rem', background: '#ecfdf5', borderRadius: '10px', color: '#059669' }}>
              <UserCheck size={26} strokeWidth={2.4} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
                {language === 'ta' ? 'வாட்ச்மேன் பணி வருகை & பணி பதிவு' : 'Smart Duty Attendance & Work Log'}
              </h1>
              <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '0.2rem 0 0' }}>
                {language === 'ta' ? 'பணி தொடக்கம் / முடிவு நேரம், ரோந்து சுழற்சிகள், மேற்பார்வையாளர் அறிக்கை (Pillar 7)' : 'Pillar 7: Digital guard duty timestamping, active shift logs, and supervisor work audit'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Current Active Duty Card ──────────────────────────── */}
      <div
        style={{
          background: 'white',
          borderRadius: '20px',
          padding: '1.75rem',
          border: '1px solid #e2e8f0',
          boxShadow: '0 8px 24px rgba(0,0,0,0.04)',
          marginBottom: '2rem'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.5rem' }}>
              <span
                style={{
                  display: 'inline-block',
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  background: currentDuty?.is_active ? '#10b981' : '#94a3b8'
                }}
              />
              <span style={{ fontSize: '0.82rem', fontWeight: 800, color: currentDuty?.is_active ? '#059669' : '#64748b', letterSpacing: '0.05em' }}>
                {currentDuty?.is_active ? 'DUTY SHIFT IN PROGRESS' : 'OFF DUTY'}
              </span>
            </div>

            <h2 style={{ fontSize: '1.45rem', fontWeight: 800, color: '#0f172a', margin: '0 0 0.35rem' }}>
              {currentDuty?.guard_name || 'Ramasamy (Main Gate Security)'}
            </h2>
            <div style={{ fontSize: '0.9rem', color: '#64748b', marginBottom: '1.25rem' }}>
              Assigned Post: <strong>{currentDuty?.gate_assigned || 'Main Campus Gate'}</strong> &bull; {currentDuty?.shift_name || 'Morning Shift'}
            </div>

            <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 700 }}>DUTY CLOCKED IN</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0f172a' }}>
                  {currentDuty?.clock_in ? new Date(currentDuty.clock_in).toLocaleTimeString() : '--:--'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 700 }}>PATROLS COMPLETED</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#2563eb' }}>
                  {currentDuty?.total_patrols_done || 4} Checks
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 700 }}>INCIDENTS LOGGED</div>
                <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#10b981' }}>
                  {currentDuty?.total_incidents_handled || 0} Open
                </div>
              </div>
            </div>
          </div>

          <div>
            {currentDuty?.is_active ? (
              <button
                onClick={() => setShowClockOutModal(true)}
                className="btn btn-primary"
                style={{ background: '#ef4444', borderColor: '#ef4444', fontWeight: 800, padding: '0.75rem 1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <Square size={16} />
                Clock Out / End Shift
              </button>
            ) : (
              <button
                onClick={handleClockIn}
                className="btn btn-primary"
                style={{ background: '#10b981', borderColor: '#10b981', fontWeight: 800, padding: '0.75rem 1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <Play size={16} />
                Clock In / Start Duty
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Shift Attendance Log History ──────────────────────── */}
      <h2 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0f172a', marginBottom: '1rem' }}>
        Duty Attendance History & Supervisor Work Summary
      </h2>

      <div style={{ background: 'white', borderRadius: '16px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              <th style={{ padding: '0.85rem 1.25rem' }}>Guard Name</th>
              <th style={{ padding: '0.85rem 1.25rem' }}>Shift Schedule</th>
              <th style={{ padding: '0.85rem 1.25rem' }}>Clock In</th>
              <th style={{ padding: '0.85rem 1.25rem' }}>Clock Out</th>
              <th style={{ padding: '0.85rem 1.25rem' }}>Status</th>
              <th style={{ padding: '0.85rem 1.25rem' }}>Patrols Done</th>
            </tr>
          </thead>
          <tbody>
            {dutyHistory.map((d) => (
              <tr key={d.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '1rem 1.25rem', fontWeight: 700, color: '#0f172a' }}>
                  {d.guard_name}
                </td>
                <td style={{ padding: '1rem 1.25rem', color: '#64748b' }}>
                  {d.shift_name}
                </td>
                <td style={{ padding: '1rem 1.25rem', color: '#0f172a', fontWeight: 600 }}>
                  {new Date(d.clock_in).toLocaleTimeString()}
                </td>
                <td style={{ padding: '1rem 1.25rem', color: '#64748b' }}>
                  {d.clock_out ? new Date(d.clock_out).toLocaleTimeString() : 'In Progress'}
                </td>
                <td style={{ padding: '1rem 1.25rem' }}>
                  <span
                    style={{
                      padding: '0.2rem 0.55rem',
                      borderRadius: '999px',
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      background: d.is_active ? '#ecfdf5' : '#f1f5f9',
                      color: d.is_active ? '#065f46' : '#475569'
                    }}
                  >
                    {d.is_active ? 'ON DUTY' : 'COMPLETED'}
                  </span>
                </td>
                <td style={{ padding: '1rem 1.25rem', fontWeight: 800, color: '#2563eb' }}>
                  {d.total_patrols_done} Checkpoints
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Clock Out Modal ───────────────────────────────────── */}
      {showClockOutModal && (
        <div className="modal-backdrop">
          <div className="modal-content" style={{ maxWidth: '440px', borderRadius: '20px' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: '0 0 0.5rem' }}>
              Confirm Shift Clock-Out
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1.25rem' }}>
              Please enter any notes or observations for the supervisor and next shift guard.
            </p>

            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                Shift Handover Notes
              </label>
              <textarea
                rows="3"
                placeholder="e.g., All barriers closed, parcels handed over, North Gate floodlight reported."
                value={supervisorNotes}
                onChange={(e) => setSupervisorNotes(e.target.value)}
                style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1' }}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setShowClockOutModal(false)}
                className="btn btn-secondary"
                style={{ fontWeight: 700 }}
              >
                Cancel
              </button>
              <button
                onClick={handleClockOut}
                className="btn btn-primary"
                style={{ fontWeight: 800, background: '#ef4444', borderColor: '#ef4444' }}
              >
                Confirm End Duty
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
