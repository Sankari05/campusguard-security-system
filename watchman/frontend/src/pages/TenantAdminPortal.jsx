import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const TenantAdminPortal = ({ onBackToLanding }) => {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('telemetry');
  const [setupData, setSetupData] = useState(null);
  const [telemetry, setTelemetry] = useState(null);
  const [loading, setLoading] = useState(true);

  // Add Gate Modal State
  const [showGateModal, setShowGateModal] = useState(false);
  const [gateNumber, setGateNumber] = useState('');
  const [gateName, setGateName] = useState('');
  const [gateType, setGateType] = useState('MAIN');

  // Add Shift Modal State
  const [showShiftModal, setShowShiftModal] = useState(false);
  const [shiftName, setShiftName] = useState('');
  const [startTime, setStartTime] = useState('06:00');
  const [endTime, setEndTime] = useState('14:00');

  // Create Guard Modal State
  const [showGuardModal, setShowGuardModal] = useState(false);
  const [guardFullName, setGuardFullName] = useState('');
  const [guardUsername, setGuardUsername] = useState('');
  const [guardEmail, setGuardEmail] = useState('');
  const [guardPhone, setGuardPhone] = useState('');
  const [guardGate, setGuardGate] = useState('');
  const [guardShift, setGuardShift] = useState('');
  const [guardPassword, setGuardPassword] = useState('pass123');
  const [createdGuardCred, setCreatedGuardCred] = useState(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [setupRes, telemRes] = await Promise.all([
        api.getTenantSetup(),
        api.getTenantTelemetry()
      ]);
      setSetupData(setupRes);
      setTelemetry(telemRes);
      if (setupRes.gates?.length > 0 && !guardGate) {
        setGuardGate(setupRes.gates[0].gate_number);
      }
      if (setupRes.shifts?.length > 0 && !guardShift) {
        setGuardShift(setupRes.shifts[0].shift_name);
      }
    } catch (err) {
      console.error('Failed to load tenant setup:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateGate = async (e) => {
    e.preventDefault();
    try {
      await api.addTenantGate({
        gate_number: gateNumber.trim(),
        gate_name: gateName.trim(),
        gate_type: gateType
      });
      setShowGateModal(false);
      setGateNumber('');
      setGateName('');
      loadData();
    } catch (err) {
      alert(`Error creating gate: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleCreateShift = async (e) => {
    e.preventDefault();
    try {
      await api.addTenantShift({
        shift_name: shiftName.trim(),
        start_time: startTime.trim(),
        end_time: endTime.trim()
      });
      setShowShiftModal(false);
      setShiftName('');
      loadData();
    } catch (err) {
      alert(`Error creating shift: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleCreateGuard = async (e) => {
    e.preventDefault();
    try {
      const res = await api.createTenantGuard({
        full_name: guardFullName.trim(),
        username: guardUsername.trim(),
        email: guardEmail.trim(),
        phone_number: guardPhone.trim(),
        assigned_gate: guardGate,
        assigned_shift: guardShift,
        password: guardPassword
      });
      setCreatedGuardCred({
        username: res.username,
        full_name: res.full_name,
        gate: res.assigned_gate,
        shift: res.assigned_shift,
        password: guardPassword
      });
      setGuardFullName('');
      setGuardUsername('');
      setGuardEmail('');
      setGuardPhone('');
      loadData();
    } catch (err) {
      alert(`Error creating guard: ${err.response?.data?.detail || err.message}`);
    }
  };

  const org = setupData?.organization || { name: 'Campus Security', org_type: 'COLLEGE' };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#FFFFFF',
      backgroundImage: `
        radial-gradient(circle at 10% 15%, rgba(153, 246, 228, 0.35) 0%, rgba(186, 230, 253, 0.20) 30%, transparent 60%),
        radial-gradient(circle at 50% 38%, rgba(254, 215, 170, 0.40) 0%, rgba(254, 243, 199, 0.20) 32%, transparent 65%),
        radial-gradient(circle at 85% 80%, rgba(199, 210, 254, 0.40) 0%, rgba(224, 231, 255, 0.25) 35%, transparent 65%),
        linear-gradient(to right, rgba(14, 165, 233, 0.08) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(14, 165, 233, 0.08) 1px, transparent 1px)
      `,
      backgroundSize: '100% 100%, 100% 100%, 100% 100%, 36px 36px, 36px 36px',
      backgroundAttachment: 'fixed',
      color: '#0F172A',
      fontFamily: "'Inter', sans-serif"
    }}>
      {/* Top Tenant Header */}
      <header style={{
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        borderBottom: '1px solid #E2E8F0',
        backdropFilter: 'blur(16px)',
        padding: '1.25rem 2.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 2px 10px rgba(15, 23, 42, 0.04)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.3rem',
            color: '#FFFFFF',
            boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)'
          }}>
            🏛️
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ fontSize: '1.25rem', fontWeight: 900, color: '#0F172A' }}>{org.name}</span>
              <span style={{ backgroundColor: '#EFF6FF', color: '#1D4ED8', border: '1px solid #BFDBFE', fontSize: '0.72rem', fontWeight: 800, padding: '0.2rem 0.5rem', borderRadius: '6px' }}>
                {org.org_type}
              </span>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748B' }}>
              Facility Admin Workspace • Logged in as <strong>{user?.fullName || user?.username}</strong>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={onBackToLanding}
            style={{ backgroundColor: '#F1F5F9', color: '#334155', border: '1px solid #CBD5E1', padding: '0.5rem 1rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer' }}
          >
            ← Public Portal
          </button>
          <button
            onClick={logout}
            style={{ backgroundColor: '#FEF2F2', color: '#B91C1C', border: '1.5px solid #FCA5A5', padding: '0.5rem 1rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 800, cursor: 'pointer' }}
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <main style={{ padding: '2rem 2.5rem', maxWidth: '1400px', margin: '0 auto' }}>
        {/* Telemetry KPI Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.25rem', marginBottom: '2rem' }}>
          {[
            { label: 'Configured Gates', value: telemetry?.active_gates_count ?? setupData?.counts?.gates ?? 0, icon: '🚪', color: '#2563EB' },
            { label: 'Active Duty Shifts', value: setupData?.counts?.shifts ?? 0, icon: '⏱️', color: '#7C3AED' },
            { label: 'Registered Watchmen', value: telemetry?.guards_on_duty_count ?? setupData?.counts?.guards ?? 0, icon: '🛡️', color: '#059669' },
            { label: 'Open Security Incidents', value: telemetry?.open_incidents_count ?? 0, icon: '⚠️', color: '#DC2626' },
          ].map((kpi, idx) => (
            <div key={idx} style={{
              backgroundColor: '#FFFFFF',
              border: '1.5px solid #E2E8F0',
              borderRadius: '16px',
              padding: '1.25rem 1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              boxShadow: '0 4px 15px -3px rgba(15, 23, 42, 0.06)'
            }}>
              <div>
                <div style={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 800, textTransform: 'uppercase' }}>{kpi.label}</div>
                <div style={{ fontSize: '2rem', fontWeight: 900, color: kpi.color, marginTop: '0.25rem' }}>{kpi.value}</div>
              </div>
              <div style={{ fontSize: '2rem', opacity: 0.85 }}>{kpi.icon}</div>
            </div>
          ))}
        </div>

        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '0.75rem', borderBottom: '1px solid #E2E8F0', paddingBottom: '0.75rem', marginBottom: '2rem' }}>
          {[
            { id: 'telemetry', label: '📊 Live Security Telemetry' },
            { id: 'guards', label: '👥 Watchman Provisioning' },
            { id: 'gates', label: '🚪 Gates & Portals' },
            { id: 'shifts', label: '⏱️ Duty Shifts' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                backgroundColor: activeTab === tab.id ? '#EFF6FF' : '#FFFFFF',
                color: activeTab === tab.id ? '#1D4ED8' : '#475569',
                border: activeTab === tab.id ? '2px solid #2563EB' : '1px solid #CBD5E1',
                padding: '0.65rem 1.25rem',
                borderRadius: '8px',
                fontWeight: 800,
                fontSize: '0.85rem',
                cursor: 'pointer',
                boxShadow: activeTab === tab.id ? '0 2px 6px rgba(37, 99, 235, 0.12)' : 'none'
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '4rem', color: '#64748B' }}>Loading facility data...</div>
        ) : (
          <>
            {/* TAB 1: Live Telemetry */}
            {activeTab === 'telemetry' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '2rem' }}>
                {/* Recent Gate Logs */}
                <div style={{ backgroundColor: '#FFFFFF', borderRadius: '16px', border: '1.5px solid #E2E8F0', padding: '1.5rem', boxShadow: '0 4px 15px -3px rgba(15, 23, 42, 0.06)' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 800, margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#0F172A' }}>
                    <span>🔴</span> Live Gate Entry & Exit Stream
                  </h3>
                  {telemetry?.recent_gate_logs?.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {telemetry.recent_gate_logs.map((log) => (
                        <div key={log.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.65rem 0.85rem', backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', fontSize: '0.82rem' }}>
                          <div>
                            <span style={{ fontWeight: 800, color: '#0F172A' }}>{log.person_name || 'Vehicle Entry'}</span>
                            <span style={{ color: '#64748B', marginLeft: '0.5rem' }}>({log.gate_number})</span>
                          </div>
                          <span style={{
                            padding: '0.2rem 0.5rem',
                            borderRadius: '4px',
                            fontWeight: 800,
                            fontSize: '0.72rem',
                            backgroundColor: log.direction === 'IN' ? '#ECFDF5' : '#FEF2F2',
                            color: log.direction === 'IN' ? '#047857' : '#B91C1C',
                            border: `1px solid ${log.direction === 'IN' ? '#A7F3D0' : '#FCA5A5'}`
                          }}>
                            {log.direction}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: '#64748B', fontSize: '0.85rem', padding: '2rem', textAlign: 'center' }}>No gate logs recorded yet today.</div>
                  )}
                </div>

                {/* Recent Incidents */}
                <div style={{ backgroundColor: '#FFFFFF', borderRadius: '16px', border: '1.5px solid #E2E8F0', padding: '1.5rem', boxShadow: '0 4px 15px -3px rgba(15, 23, 42, 0.06)' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 800, margin: '0 0 1rem 0', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#0F172A' }}>
                    <span>⚠️</span> Security Incidents & Threat Logs
                  </h3>
                  {telemetry?.recent_incidents?.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {telemetry.recent_incidents.map((inc) => (
                        <div key={inc.id} style={{ backgroundColor: '#FEF2F2', borderLeft: '4px solid #EF4444', borderTop: '1px solid #FCA5A5', borderRight: '1px solid #FCA5A5', borderBottom: '1px solid #FCA5A5', borderRadius: '6px', padding: '0.75rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', fontWeight: 800, marginBottom: '0.25rem' }}>
                            <span style={{ color: '#B91C1C' }}>{inc.incident_type}</span>
                            <span style={{ color: '#64748B' }}>{inc.gate_number}</span>
                          </div>
                          <div style={{ fontSize: '0.78rem', color: '#334155', lineHeight: 1.4 }}>{inc.description}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: '#047857', fontSize: '0.85rem', padding: '2rem', textAlign: 'center', fontWeight: 700 }}>✓ No active security threats or incidents logged.</div>
                  )}
                </div>
              </div>
            )}

            {/* TAB 2: Watchmen Management */}
            {activeTab === 'guards' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <div>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 900, margin: 0, color: '#0F172A' }}>Watchmen Accounts & Shift Assignments</h3>
                    <div style={{ fontSize: '0.8rem', color: '#64748B' }}>Provision individual guard accounts with specific gate and shift permissions</div>
                  </div>
                  <button
                    onClick={() => {
                      setShowGuardModal(true);
                      setCreatedGuardCred(null);
                    }}
                    style={{ background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)', color: '#FFFFFF', border: 'none', padding: '0.65rem 1.25rem', borderRadius: '8px', fontWeight: 800, fontSize: '0.85rem', cursor: 'pointer', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.3)' }}
                  >
                    + Provision New Watchman
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
                  {(setupData?.guards || []).map((gd) => (
                    <div key={gd.id} style={{ backgroundColor: '#FFFFFF', border: '1.5px solid #E2E8F0', borderRadius: '16px', padding: '1.25rem', boxShadow: '0 4px 15px -3px rgba(15, 23, 42, 0.06)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                        <div>
                          <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0F172A' }}>{gd.full_name}</div>
                          <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Username: <code style={{ color: '#2563EB' }}>{gd.username}</code></div>
                        </div>
                        <span style={{ backgroundColor: '#ECFDF5', color: '#047857', border: '1px solid #A7F3D0', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 800 }}>ACTIVE</span>
                      </div>
                      <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', padding: '0.65rem', fontSize: '0.8rem', color: '#334155', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <div><strong>🚪 Gate:</strong> {gd.assigned_gate || 'Main Gate 1'}</div>
                        <div><strong>⏱️ Shift:</strong> {gd.assigned_shift || 'Morning Shift'}</div>
                        <div><strong>📞 Phone:</strong> {gd.phone_number || 'Not provided'}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 3: Gates Configuration */}
            {activeTab === 'gates' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <div>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 900, margin: 0, color: '#0F172A' }}>Configured Gates & Portals</h3>
                    <div style={{ fontSize: '0.8rem', color: '#64748B' }}>Manage entry points, barrier types, and dedicated vehicle/pedestrian gates</div>
                  </div>
                  <button
                    onClick={() => setShowGateModal(true)}
                    style={{ background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)', color: '#FFFFFF', border: 'none', padding: '0.65rem 1.25rem', borderRadius: '8px', fontWeight: 800, fontSize: '0.85rem', cursor: 'pointer', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.3)' }}
                  >
                    + Add New Gate
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.25rem' }}>
                  {(setupData?.gates || []).map((gt) => (
                    <div key={gt.id} style={{ backgroundColor: '#FFFFFF', border: '1.5px solid #E2E8F0', borderRadius: '16px', padding: '1.25rem', boxShadow: '0 4px 15px -3px rgba(15, 23, 42, 0.06)' }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: 800, color: '#0284C7', backgroundColor: '#F0F9FF', border: '1px solid #BAE6FD', display: 'inline-block', padding: '0.2rem 0.5rem', borderRadius: '4px', marginBottom: '0.5rem' }}>
                        {gt.gate_type}
                      </div>
                      <div style={{ fontSize: '1.1rem', fontWeight: 900, color: '#0F172A' }}>{gt.gate_number}</div>
                      <div style={{ fontSize: '0.82rem', color: '#64748B', marginTop: '0.25rem' }}>{gt.gate_name}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 4: Shifts Configuration */}
            {activeTab === 'shifts' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <div>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 900, margin: 0, color: '#0F172A' }}>Configured Duty Shifts</h3>
                    <div style={{ fontSize: '0.8rem', color: '#64748B' }}>Define operating shift schedules for automated handover logs</div>
                  </div>
                  <button
                    onClick={() => setShowShiftModal(true)}
                    style={{ background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)', color: '#FFFFFF', border: 'none', padding: '0.65rem 1.25rem', borderRadius: '8px', fontWeight: 800, fontSize: '0.85rem', cursor: 'pointer', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.3)' }}
                  >
                    + Add New Shift
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1.25rem' }}>
                  {(setupData?.shifts || []).map((sh) => (
                    <div key={sh.id} style={{ backgroundColor: '#FFFFFF', border: '1.5px solid #E2E8F0', borderRadius: '16px', padding: '1.25rem', boxShadow: '0 4px 15px -3px rgba(15, 23, 42, 0.06)' }}>
                      <div style={{ fontSize: '1.1rem', fontWeight: 900, color: '#0F172A' }}>{sh.shift_name}</div>
                      <div style={{ fontSize: '0.88rem', color: '#059669', fontWeight: 700, marginTop: '0.4rem' }}>
                        ⏱️ {sh.start_time} - {sh.end_time}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {/* Add Gate Modal */}
      {showGateModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.45)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1.5rem' }}>
          <div style={{ backgroundColor: '#FFFFFF', border: '1.5px solid #E2E8F0', borderRadius: '20px', maxWidth: '440px', width: '100%', padding: '2rem', boxShadow: '0 25px 60px -15px rgba(15, 23, 42, 0.25)', color: '#0F172A' }}>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 900, marginBottom: '1.25rem', color: '#0F172A' }}>Configure New Gate</h3>
            <form onSubmit={handleCreateGate}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Gate Number / Identifier *</label>
                <input required type="text" placeholder="e.g. Gate 3, Ambulance Bay" value={gateNumber} onChange={(e) => setGateNumber(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Gate Name / Description *</label>
                <input required type="text" placeholder="e.g. South Campus Visitors Entrance" value={gateName} onChange={(e) => setGateName(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
              </div>
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Gate Type</label>
                <select value={gateType} onChange={(e) => setGateType(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }}>
                  <option value="MAIN">MAIN</option>
                  <option value="VEHICLE">VEHICLE</option>
                  <option value="PEDESTRIAN">PEDESTRIAN</option>
                  <option value="EMERGENCY">EMERGENCY</option>
                  <option value="CARGO">CARGO</option>
                </select>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => setShowGateModal(false)} style={{ backgroundColor: '#F1F5F9', color: '#475569', border: '1px solid #CBD5E1', padding: '0.6rem 1rem', borderRadius: '8px', fontWeight: 700, cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)', color: '#FFFFFF', border: 'none', padding: '0.6rem 1.25rem', borderRadius: '8px', fontWeight: 800, cursor: 'pointer', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)' }}>Save Gate</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Shift Modal */}
      {showShiftModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.45)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1.5rem' }}>
          <div style={{ backgroundColor: '#FFFFFF', border: '1.5px solid #E2E8F0', borderRadius: '20px', maxWidth: '440px', width: '100%', padding: '2rem', boxShadow: '0 25px 60px -15px rgba(15, 23, 42, 0.25)', color: '#0F172A' }}>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 900, marginBottom: '1.25rem', color: '#0F172A' }}>Configure Duty Shift</h3>
            <form onSubmit={handleCreateShift}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Shift Name *</label>
                <input required type="text" placeholder="e.g. Night Curfew Shift" value={shiftName} onChange={(e) => setShiftName(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Start Time</label>
                  <input required type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>End Time</label>
                  <input required type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => setShowShiftModal(false)} style={{ backgroundColor: '#F1F5F9', color: '#475569', border: '1px solid #CBD5E1', padding: '0.6rem 1rem', borderRadius: '8px', fontWeight: 700, cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)', color: '#FFFFFF', border: 'none', padding: '0.6rem 1.25rem', borderRadius: '8px', fontWeight: 800, cursor: 'pointer', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)' }}>Save Shift</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Provision Guard Modal */}
      {showGuardModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.45)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1.5rem' }}>
          <div style={{ backgroundColor: '#FFFFFF', border: '1.5px solid #E2E8F0', borderRadius: '24px', maxWidth: '520px', width: '100%', padding: '2rem', boxShadow: '0 25px 60px -15px rgba(15, 23, 42, 0.25)', color: '#0F172A' }}>
            <h3 style={{ fontSize: '1.35rem', fontWeight: 900, marginBottom: '0.5rem', color: '#0F172A' }}>Provision Security Watchman Account</h3>
            <p style={{ fontSize: '0.82rem', color: '#64748B', marginBottom: '1.25rem' }}>
              Assign a new watchman to <strong>{org.name}</strong> with a designated gate and shift.
            </p>

            {!createdGuardCred ? (
              <form onSubmit={handleCreateGuard}>
                <div style={{ marginBottom: '0.85rem' }}>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Guard Full Name *</label>
                  <input required type="text" placeholder="e.g. Ramasamy / Murugan" value={guardFullName} onChange={(e) => setGuardFullName(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '0.85rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Username (Login ID) *</label>
                    <input required type="text" placeholder="e.g. guard_gate1" value={guardUsername} onChange={(e) => setGuardUsername(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Phone Number *</label>
                    <input required type="tel" placeholder="e.g. 9876543210" value={guardPhone} onChange={(e) => setGuardPhone(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
                  </div>
                </div>

                <div style={{ marginBottom: '0.85rem' }}>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Email Address *</label>
                  <input required type="email" placeholder="e.g. guard1@organization.org" value={guardEmail} onChange={(e) => setGuardEmail(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '0.85rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Assigned Gate *</label>
                    <select value={guardGate} onChange={(e) => setGuardGate(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }}>
                      {(setupData?.gates || []).map((g) => (
                        <option key={g.id} value={g.gate_number}>{g.gate_number} ({g.gate_name})</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Assigned Shift *</label>
                    <select value={guardShift} onChange={(e) => setGuardShift(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }}>
                      {(setupData?.shifts || []).map((s) => (
                        <option key={s.id} value={s.shift_name}>{s.shift_name} ({s.start_time}-{s.end_time})</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Initial Password</label>
                  <input type="text" value={guardPassword} onChange={(e) => setGuardPassword(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.88rem' }} />
                </div>

                <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                  <button type="button" onClick={() => setShowGuardModal(false)} style={{ backgroundColor: '#F1F5F9', color: '#475569', border: '1px solid #CBD5E1', padding: '0.6rem 1rem', borderRadius: '8px', fontWeight: 700, cursor: 'pointer' }}>Cancel</button>
                  <button type="submit" style={{ background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)', color: '#FFFFFF', border: 'none', padding: '0.6rem 1.25rem', borderRadius: '8px', fontWeight: 800, cursor: 'pointer', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)' }}>Create Watchman</button>
                </div>
              </form>
            ) : (
              <div>
                <div style={{ backgroundColor: '#ECFDF5', border: '1.5px solid #10B981', borderRadius: '12px', padding: '1rem', marginBottom: '1.5rem' }}>
                  <div style={{ color: '#065F46', fontWeight: 800, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                    🎉 Watchman Provisioned Successfully!
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#1E293B', lineHeight: 1.6 }}>
                    <div><strong>Name:</strong> {createdGuardCred.full_name}</div>
                    <div><strong>Username:</strong> <code style={{ color: '#2563EB', backgroundColor: '#EFF6FF', padding: '2px 6px', borderRadius: '4px' }}>{createdGuardCred.username}</code></div>
                    <div><strong>Password:</strong> <code style={{ color: '#2563EB', backgroundColor: '#EFF6FF', padding: '2px 6px', borderRadius: '4px' }}>{createdGuardCred.password}</code></div>
                    <div><strong>Assigned Gate:</strong> {createdGuardCred.gate}</div>
                    <div><strong>Assigned Shift:</strong> {createdGuardCred.shift}</div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setShowGuardModal(false);
                    setCreatedGuardCred(null);
                  }}
                  style={{ width: '100%', background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)', color: '#FFFFFF', border: 'none', padding: '0.75rem', borderRadius: '8px', fontWeight: 800, cursor: 'pointer', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)' }}
                >
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
