import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const WatchmanAdaptiveWorkspace = ({ onNavigateToModule }) => {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [incidentModal, setIncidentModal] = useState(false);
  const [incidentType, setIncidentType] = useState('TRESPASSING');
  const [severity, setSeverity] = useState('MEDIUM');
  const [incidentDesc, setIncidentDesc] = useState('');
  const [incidentAction, setIncidentAction] = useState('');
  const [bannerMessage, setBannerMessage] = useState(null);

  // Industry Feature Simulation State
  const [hospitalAmbulanceCleared, setHospitalAmbulanceCleared] = useState(false);
  const [parcelLogged, setParcelLogged] = useState(false);
  const [parcelFlat, setParcelFlat] = useState('');
  const [parcelCourier, setParcelCourier] = useState('Amazon');
  const [factoryPassLogged, setFactoryPassLogged] = useState(false);
  const [materialItem, setMaterialItem] = useState('');
  const [collegeRollNumber, setCollegeRollNumber] = useState('');
  const [collegeOutpassStatus, setCollegeOutpassStatus] = useState(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const data = await api.getWatchmanAdaptiveProfile();
        setProfile(data);
      } catch (err) {
        console.error('Failed to load watchman profile:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const handleReportIncident = async (e) => {
    e.preventDefault();
    try {
      await api.reportSecurityIncident({
        incident_type: incidentType,
        severity: severity,
        description: incidentDesc.trim(),
        action_taken: incidentAction.trim() || undefined,
        gate_number: user?.assignedGate || 'Main Gate'
      });
      setIncidentModal(false);
      setIncidentDesc('');
      setIncidentAction('');
      setBannerMessage('🚨 Security Incident Logged & Dispatched to Facility Admin!');
      setTimeout(() => setBannerMessage(null), 5000);
    } catch (err) {
      alert(`Error logging incident: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleVerifyCollegeOutpass = async () => {
    if (!collegeRollNumber.trim()) return;
    try {
      const res = await api.verifyStudent(collegeRollNumber.trim());
      setCollegeOutpassStatus(res);
    } catch {
      setCollegeOutpassStatus({ valid: false, message: 'Student roll number not verified or no active out-pass found.' });
    }
  };

  const orgType = profile?.organization?.org_type || 'COLLEGE';
  const orgName = profile?.organization?.name || 'Central Campus Security';
  const gate = user?.assignedGate || profile?.guard?.assigned_gate || 'Main Gate 1';
  const shift = user?.assignedShift || profile?.guard?.assigned_shift || 'Morning Shift';

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
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      padding: '2rem 3rem',
      position: 'relative'
    }}>
      {/* Top Guard Identification Card */}
      <div style={{
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        border: '1.5px solid #DBEAFE',
        borderRadius: '20px',
        padding: '1.5rem 2rem',
        marginBottom: '2rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 10px 30px -5px rgba(37, 99, 235, 0.1)',
        backdropFilter: 'blur(16px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
          <div style={{
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.8rem',
            border: '2px solid rgba(255, 255, 255, 0.8)',
            boxShadow: '0 4px 14px rgba(37, 99, 235, 0.3)'
          }}>
            🛡️
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 900, margin: 0, color: '#0F172A' }}>
                {user?.fullName || user?.username}
              </h2>
              <span style={{
                backgroundColor: '#EFF6FF',
                color: '#1D4ED8',
                border: '1px solid #BFDBFE',
                padding: '0.2rem 0.6rem',
                borderRadius: '6px',
                fontSize: '0.72rem',
                fontWeight: 800
              }}>
                ON-DUTY GUARD
              </span>
            </div>
            <div style={{ fontSize: '0.85rem', color: '#64748B', marginTop: '0.25rem' }}>
              🏢 <strong style={{ color: '#0F172A' }}>{orgName}</strong> ({orgType}) • 🚪 Assigned to: <strong style={{ color: '#2563EB' }}>{gate}</strong> • ⏱️ Shift: <strong style={{ color: '#0F172A' }}>{shift}</strong>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={() => setIncidentModal(true)}
            style={{
              backgroundColor: '#DC2626',
              color: '#FFFFFF',
              border: 'none',
              padding: '0.65rem 1.25rem',
              borderRadius: '10px',
              fontWeight: 800,
              fontSize: '0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: '0 4px 15px rgba(220, 38, 38, 0.3)'
            }}
          >
            <span>⚠️</span> Report Threat / Incident
          </button>
          <button
            onClick={logout}
            style={{
              backgroundColor: '#F1F5F9',
              border: '1px solid #CBD5E1',
              color: '#334155',
              padding: '0.65rem 1.1rem',
              borderRadius: '10px',
              fontWeight: 700,
              fontSize: '0.82rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            }}
          >
            Sign Out
          </button>
        </div>
      </div>

      {bannerMessage && (
        <div style={{
          backgroundColor: '#FEF2F2',
          border: '1.5px solid #FCA5A5',
          color: '#B91C1C',
          padding: '1rem 1.5rem',
          borderRadius: '12px',
          marginBottom: '2rem',
          fontWeight: 800,
          fontSize: '0.92rem',
          boxShadow: '0 4px 12px rgba(220, 38, 38, 0.1)'
        }}>
          {bannerMessage}
        </div>
      )}

      {/* Industry-Specific Adaptive Panel */}
      <div style={{ marginBottom: '2.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.25rem' }}>
          <span style={{ fontSize: '1.2rem' }}>⚡</span>
          <h3 style={{ fontSize: '1.3rem', fontWeight: 900, margin: 0, color: '#0F172A' }}>
            {profile?.vertical_profile?.title || 'Specialized Facility Operations'}
          </h3>
          <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 600 }}>
            (Automatically tailored to {orgType})
          </span>
        </div>

        {/* 1. HOSPITAL ADAPTATION */}
        {orgType === 'HOSPITAL' && (
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            border: '2px solid #FCA5A5',
            borderRadius: '20px',
            padding: '2rem',
            display: 'grid',
            gridTemplateColumns: '1.2fr 1fr',
            gap: '2rem',
            boxShadow: '0 12px 30px -5px rgba(239, 68, 68, 0.12)'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '1.8rem' }}>🚑</span>
                <h4 style={{ fontSize: '1.25rem', fontWeight: 900, color: '#DC2626', margin: 0 }}>
                  Emergency Trauma & Ambulance Bay Clearance
                </h4>
              </div>
              <p style={{ fontSize: '0.88rem', color: '#475569', lineHeight: 1.5, marginBottom: '1.5rem' }}>
                Single-tap priority clearance raises the emergency barrier, notifies the ER trauma team, and activates the exterior warning strobes.
              </p>

              <button
                onClick={() => {
                  setHospitalAmbulanceCleared(true);
                  setTimeout(() => setHospitalAmbulanceCleared(false), 6000);
                }}
                style={{
                  backgroundColor: '#DC2626',
                  color: '#FFFFFF',
                  padding: '1rem 2rem',
                  borderRadius: '12px',
                  fontWeight: 900,
                  fontSize: '1rem',
                  border: 'none',
                  cursor: 'pointer',
                  boxShadow: '0 6px 20px rgba(220, 38, 38, 0.35)'
                }}
              >
                🚨 Fast-Track Approaching Ambulance Bay (Clear Lane)
              </button>

              {hospitalAmbulanceCleared && (
                <div style={{ marginTop: '1rem', color: '#059669', fontWeight: 800, fontSize: '0.9rem' }}>
                  ✓ EMERGENCY BARRIER RAISED! Trauma Bay Alert Dispatched to Emergency Ward.
                </div>
              )}
            </div>

            <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '14px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>Hospital Protocols:</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>ICU Passes:</strong> Maximum 1 attendant badge per patient bed.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Bio-Hazard:</strong> Red-bin waste carrier requires supervisor sign-off.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Oxygen Tanker:</strong> Park at Bay 4 with fire watch posted.</div>
            </div>
          </div>
        )}

        {/* 2. APARTMENT ADAPTATION */}
        {orgType === 'APARTMENT' && (
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            border: '2px solid #A7F3D0',
            borderRadius: '20px',
            padding: '2rem',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '2rem',
            boxShadow: '0 12px 30px -5px rgba(16, 185, 129, 0.12)'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '1.8rem' }}>📦</span>
                <h4 style={{ fontSize: '1.25rem', fontWeight: 900, color: '#059669', margin: 0 }}>
                  E-Commerce Courier & Parcel Inward Log
                </h4>
              </div>
              <p style={{ fontSize: '0.88rem', color: '#475569', marginBottom: '1.25rem' }}>
                Log Amazon, Flipkart, or Swiggy deliveries and instantly alert the resident flat.
              </p>

              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Flat No (e.g. A-402, B-105)"
                  value={parcelFlat}
                  onChange={(e) => setParcelFlat(e.target.value)}
                  style={{ flex: 1, padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.85rem' }}
                />
                <select
                  value={parcelCourier}
                  onChange={(e) => setParcelCourier(e.target.value)}
                  style={{ padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.85rem' }}
                >
                  <option value="Amazon">Amazon</option>
                  <option value="Flipkart">Flipkart</option>
                  <option value="Swiggy">Swiggy / Zomato</option>
                  <option value="BlueDart">BlueDart</option>
                </select>
              </div>

              <button
                onClick={() => {
                  if (!parcelFlat.trim()) return;
                  setParcelLogged(true);
                  setTimeout(() => {
                    setParcelLogged(false);
                    setParcelFlat('');
                  }, 4000);
                }}
                style={{ backgroundColor: '#059669', color: '#FFFFFF', padding: '0.75rem 1.5rem', borderRadius: '8px', fontWeight: 800, border: 'none', cursor: 'pointer', fontSize: '0.88rem', boxShadow: '0 4px 12px rgba(5, 150, 105, 0.3)' }}
              >
                Log Parcel & Send App Notification
              </button>

              {parcelLogged && (
                <div style={{ marginTop: '0.75rem', color: '#047857', fontWeight: 700, fontSize: '0.85rem' }}>
                  ✓ Parcel for Flat {parcelFlat} logged! Notification sent to resident phone.
                </div>
              )}
            </div>

            <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '14px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>Community Protocols:</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Resident App Approval:</strong> Check intercom if guest is unexpected.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Maids & Drivers:</strong> Verify QR daily entry badge.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Visitors Parking:</strong> Direct vehicles to designated visitor slots only.</div>
            </div>
          </div>
        )}

        {/* 3. FACTORY ADAPTATION */}
        {orgType === 'FACTORY' && (
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            border: '2px solid #FDE68A',
            borderRadius: '20px',
            padding: '2rem',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '2rem',
            boxShadow: '0 12px 30px -5px rgba(217, 119, 6, 0.12)'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '1.8rem' }}>📋</span>
                <h4 style={{ fontSize: '1.25rem', fontWeight: 900, color: '#B45309', margin: 0 }}>
                  Material Gate Pass (RGP / NRGP) & Weighbridge Audit
                </h4>
              </div>
              <p style={{ fontSize: '0.88rem', color: '#475569', marginBottom: '1.25rem' }}>
                Verify truck freight invoices, tare weights, and raw material returnable gate passes.
              </p>

              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Material Description (e.g. Steel Coils, Scrap)"
                  value={materialItem}
                  onChange={(e) => setMaterialItem(e.target.value)}
                  style={{ flex: 1, padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.85rem' }}
                />
              </div>

              <button
                onClick={() => {
                  if (!materialItem.trim()) return;
                  setFactoryPassLogged(true);
                  setTimeout(() => {
                    setFactoryPassLogged(false);
                    setMaterialItem('');
                  }, 4000);
                }}
                style={{ backgroundColor: '#D97706', color: '#FFFFFF', padding: '0.75rem 1.5rem', borderRadius: '8px', fontWeight: 800, border: 'none', cursor: 'pointer', fontSize: '0.88rem', boxShadow: '0 4px 12px rgba(217, 119, 6, 0.3)' }}
              >
                Validate RGP Pass & Clear Weighbridge
              </button>

              {factoryPassLogged && (
                <div style={{ marginTop: '0.75rem', color: '#92400E', fontWeight: 700, fontSize: '0.85rem' }}>
                  ✓ Material Gate Pass Verified! Weighbridge tare weight captured.
                </div>
              )}
            </div>

            <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '14px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>Factory Safety Audit Checklist:</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Driver PPE:</strong> Hard Hat, Steel-Toe Boots & High-Vis Vest Mandatory.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Chemical Tankers:</strong> Spark arrestor check on vehicle exhaust.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Exit Audit:</strong> Match physical count against dispatch challan.</div>
            </div>
          </div>
        )}

        {/* 4. COLLEGE ADAPTATION */}
        {orgType === 'COLLEGE' && (
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            border: '2px solid #BFDBFE',
            borderRadius: '20px',
            padding: '2rem',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '2rem',
            boxShadow: '0 12px 30px -5px rgba(37, 99, 235, 0.12)'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '1.8rem' }}>🎓</span>
                <h4 style={{ fontSize: '1.25rem', fontWeight: 900, color: '#1D4ED8', margin: 0 }}>
                  Student Digital Out-Pass Verification
                </h4>
              </div>
              <p style={{ fontSize: '0.88rem', color: '#475569', marginBottom: '1.25rem' }}>
                Instant verification of warden authorization and parental approval for campus departure.
              </p>

              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Roll Number (e.g. 22CS101, 23ME045)"
                  value={collegeRollNumber}
                  onChange={(e) => setCollegeRollNumber(e.target.value)}
                  style={{ flex: 1, padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.85rem' }}
                />
                <button
                  onClick={handleVerifyCollegeOutpass}
                  style={{ backgroundColor: '#2563EB', color: '#FFFFFF', padding: '0.65rem 1.25rem', borderRadius: '8px', fontWeight: 800, border: 'none', cursor: 'pointer', fontSize: '0.85rem', boxShadow: '0 4px 12px rgba(37, 99, 235, 0.25)' }}
                >
                  Verify Out-Pass
                </button>
              </div>

              {collegeOutpassStatus && (
                <div style={{
                  backgroundColor: collegeOutpassStatus.valid !== false ? '#ECFDF5' : '#FEF2F2',
                  border: collegeOutpassStatus.valid !== false ? '1.5px solid #A7F3D0' : '1.5px solid #FECACA',
                  borderRadius: '10px',
                  padding: '0.85rem',
                  fontSize: '0.82rem'
                }}>
                  {collegeOutpassStatus.student ? (
                    <div>
                      <div style={{ color: '#047857', fontWeight: 800 }}>✓ VERIFIED: {collegeOutpassStatus.student.name}</div>
                      <div style={{ color: '#334155', marginTop: '0.2rem' }}>Dept: {collegeOutpassStatus.student.department} • Hostel: {collegeOutpassStatus.student.roomOrBusRoute}</div>
                    </div>
                  ) : (
                    <div style={{ color: '#DC2626', fontWeight: 700 }}>{collegeOutpassStatus.message}</div>
                  )}
                </div>
              )}
            </div>

            <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '14px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>Campus Security Protocols:</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Curfew Hour:</strong> 21:30 PM. All hostelites must log biometric tap.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Parent Passes:</strong> Escort required for hostel block visits.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Vehicle Stickers:</strong> Blue sticker (Student), Gold sticker (Faculty).</div>
            </div>
          </div>
        )}

        {/* 5. OFFICE ADAPTATION */}
        {orgType === 'OFFICE' && (
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            border: '2px solid #DDD6FE',
            borderRadius: '20px',
            padding: '2rem',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '2rem',
            boxShadow: '0 12px 30px -5px rgba(124, 58, 237, 0.12)'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '1.8rem' }}>🏛️</span>
                <h4 style={{ fontSize: '1.25rem', fontWeight: 900, color: '#6D28D9', margin: 0 }}>
                  Corporate Turnstile & Visitor NDA Terminal
                </h4>
              </div>
              <p style={{ fontSize: '0.88rem', color: '#475569', marginBottom: '1.25rem' }}>
                Verify client visitor badges, host meeting notifications, and laptop asset passes.
              </p>
              <button
                onClick={() => alert('Digital NDA Kiosk Prompt dispatched to lobby iPad.')}
                style={{ backgroundColor: '#7C3AED', color: '#FFFFFF', padding: '0.75rem 1.5rem', borderRadius: '8px', fontWeight: 800, border: 'none', cursor: 'pointer', fontSize: '0.88rem', boxShadow: '0 4px 12px rgba(124, 58, 237, 0.25)' }}
              >
                📝 Launch iPad Visitor NDA Sign-off
              </button>
            </div>

            <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '14px', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>Corporate Office Protocols:</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Laptop Serials:</strong> External vendor laptops must be stamped on entry.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>Visitor Escort:</strong> Client visitors must wait in reception lobby.</div>
              <div style={{ fontSize: '0.8rem', color: '#334155' }}>• <strong>After-Hours:</strong> Access granted only with VP email approval.</div>
            </div>
          </div>
        )}
      </div>

      {/* Incident Modal */}
      {incidentModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.5)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1.5rem' }}>
          <div style={{ backgroundColor: '#FFFFFF', border: '1.5px solid #E2E8F0', borderRadius: '24px', maxWidth: '520px', width: '100%', padding: '2rem', boxShadow: '0 25px 60px -15px rgba(15, 23, 42, 0.25)' }}>
            <h3 style={{ fontSize: '1.35rem', fontWeight: 900, marginBottom: '0.5rem', color: '#DC2626' }}>
              🚨 Report Security Threat / Incident
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: '1.25rem' }}>
              Logged incident will be scoped to <strong>{orgName}</strong> and immediately visible to the Facility Admin.
            </p>

            <form onSubmit={handleReportIncident}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '0.85rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Incident Type *</label>
                  <select value={incidentType} onChange={(e) => setIncidentType(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.85rem' }}>
                    <option value="TRESPASSING">TRESPASSING</option>
                    <option value="FIGHT">ALTERCATION / FIGHT</option>
                    <option value="THEFT">THEFT / MISSING ITEM</option>
                    <option value="FIRE_SMOKE">FIRE / SMOKE DETECTED</option>
                    <option value="MEDICAL_EMERGENCY">MEDICAL EMERGENCY</option>
                    <option value="PROPERTY_DAMAGE">PROPERTY DAMAGE</option>
                    <option value="OTHER">OTHER UNUSUAL EVENT</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Severity *</label>
                  <select value={severity} onChange={(e) => setSeverity(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.85rem' }}>
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH (Urgent)</option>
                    <option value="CRITICAL">CRITICAL (Emergency)</option>
                  </select>
                </div>
              </div>

              <div style={{ marginBottom: '0.85rem' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Description of Event *</label>
                <textarea required rows="3" placeholder="Describe what occurred, persons involved, vehicle numbers..." value={incidentDesc} onChange={(e) => setIncidentDesc(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.85rem', resize: 'none' }} />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#334155', marginBottom: '0.3rem' }}>Action Taken by Guard</label>
                <input type="text" placeholder="e.g. Cleared lane, called campus ambulance, detained suspect" value={incidentAction} onChange={(e) => setIncidentAction(e.target.value)} style={{ width: '100%', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.85rem' }} />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button type="button" onClick={() => setIncidentModal(false)} style={{ backgroundColor: '#F1F5F9', color: '#475569', border: '1.5px solid #CBD5E1', padding: '0.6rem 1rem', borderRadius: '8px', fontWeight: 700, cursor: 'pointer' }}>Cancel</button>
                <button type="submit" style={{ backgroundColor: '#DC2626', color: '#FFFFFF', border: 'none', padding: '0.6rem 1.25rem', borderRadius: '8px', fontWeight: 800, cursor: 'pointer', boxShadow: '0 4px 12px rgba(220, 38, 38, 0.3)' }}>Submit Incident Report</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
