import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Search,
  UserCheck,
  ArrowDownLeft,
  ArrowUpRight,
  ShieldAlert,
  QrCode,
  CheckCircle2,
  Clock,
  Phone,
  Home,
  Bus,
  Sparkles,
  Volume2,
  Layers,
  FileCheck,
  Car
} from 'lucide-react';

export const GateKiosk = ({ setAppTab }) => {
  const { t, addGateLog, gateLogs, clearGateLogs, deleteGateLog, language } = useAuth();

  const [activeTab, setActiveTab] = useState('STUDENT'); // STUDENT, PASS_VERIFY
  const [rollNumberInput, setRollNumberInput] = useState('');
  const [studentPreview, setStudentPreview] = useState(null);
  const [loadingStudent, setLoadingStudent] = useState(false);
  const [passCodeInput, setPassCodeInput] = useState('');
  const [passVerificationResult, setPassVerificationResult] = useState(null);
  const [notificationBanner, setNotificationBanner] = useState('');

  // Search student
  const handleStudentLookup = async (rollNoToLookup) => {
    const query = rollNoToLookup || rollNumberInput;
    if (!query.trim()) return;
    setLoadingStudent(true);
    setNotificationBanner('');
    try {
      const student = await api.lookupStudent(query);
      setStudentPreview(student);
    } catch {
      setNotificationBanner(language === 'ta' ? 'மாணவரை தேடுவதில் பிழை ஏற்பட்டது' : 'Error looking up student');
    } finally {
      setLoadingStudent(false);
    }
  };

  // Perform Gate Entry
  const handleGateAction = async (direction) => {
    if (!studentPreview) return;

    const hour = new Date().getHours();
    const isLate = direction === 'IN' && (hour >= 9 || hour >= 19);

    const logEntry = {
      id: Date.now(),
      personType: 'STUDENT',
      identifier: studentPreview.rollNumber,
      personName: studentPreview.name,
      purpose: isLate ? 'Late Entry / Post-curfew' : `${studentPreview.hostelOrDayScholar} Regular In/Out`,
      direction: direction,
      entryTime: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      gateNumber: 'Main Gate 1',
      status: isLate ? 'LATE_ENTRY' : 'APPROVED',
      remarks: `${studentPreview.department} • Year ${studentPreview.yearOfStudy}`
    };

    // Save to server / context
    await api.logGateEntry(logEntry);
    addGateLog(logEntry);

    // Audio announcement simulation for guard
    if ('speechSynthesis' in window) {
      const voiceText = language === 'ta'
        ? `${studentPreview.name} ${direction === 'IN' ? 'உள்ளே வந்தார்' : 'வெளியே சென்றார்'}`
        : `${studentPreview.name} marked ${direction}`;
      const msg = new SpeechSynthesisUtterance(voiceText);
      msg.lang = language === 'ta' ? 'ta-IN' : 'en-US';
      window.speechSynthesis.speak(msg);
    }

    setNotificationBanner(
      language === 'ta'
        ? `✅ ${studentPreview.name} (${studentPreview.rollNumber}) ${direction === 'IN' ? 'உள்ளே வருகை' : 'வெளியே சென்றது'} பதிவு செய்யப்பட்டது`
        : `✅ Success: ${studentPreview.name} (${studentPreview.rollNumber}) marked ${direction}`
    );

    // Clear preview after 2.5 seconds
    setTimeout(() => {
      setStudentPreview(null);
      setRollNumberInput('');
    }, 2500);
  };

  // Verify Outpass Code
  const handleVerifyPassCode = async (e) => {
    e.preventDefault();
    if (!passCodeInput.trim()) return;
    const res = await api.verifyOutPassCode(passCodeInput.trim());
    setPassVerificationResult(res);

    if (res.valid) {
      const logEntry = {
        id: Date.now(),
        personType: 'STUDENT',
        identifier: res.pass.studentRollNumber || 'STUDENT',
        personName: res.pass.studentName,
        purpose: 'Approved Out-Pass: ' + res.pass.passCode,
        direction: 'OUT',
        entryTime: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        gateNumber: 'Main Gate 1',
        status: 'APPROVED',
        remarks: 'Digital Pass Verified'
      };
      addGateLog(logEntry);
    }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner Alert if any */}
      {notificationBanner && (
        <div style={{
          backgroundColor: '#ECFDF5',
          border: '1.5px solid #10B981',
          padding: '0.85rem 1.25rem',
          borderRadius: '12px',
          color: '#065F46',
          fontWeight: 700,
          display: 'flex',
          alignItems: 'center',
          gap: '0.65rem',
          animation: 'fadeIn 0.2s ease',
          boxShadow: '0 4px 12px rgba(16, 185, 129, 0.15)'
        }}>
          <CheckCircle2 size={22} color="#10B981" />
          <span>{notificationBanner}</span>
        </div>
      )}

      {/* Main Touch Kiosk Card */}
      <div className="card" style={{ padding: '1.75rem', border: '1.5px solid #BFDBFE' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1.25rem',
          flexWrap: 'wrap',
          gap: '1rem'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
              {setAppTab && (
                <button
                  type="button"
                  onClick={() => setAppTab('dashboard')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    padding: '0.3rem 0.75rem',
                    backgroundColor: '#FFFFFF',
                    border: '1.5px solid #CBD5E1',
                    borderRadius: '8px',
                    fontSize: '0.78rem',
                    fontWeight: 800,
                    color: '#334155',
                    cursor: 'pointer',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                  }}
                >
                  ← {language === 'ta' ? 'மேற்பார்வைக்கு திரும்பு' : 'Back to Overview'}
                </button>
              )}
              <span style={{
                backgroundColor: '#EFF6FF',
                color: '#2563EB',
                padding: '0.25rem 0.65rem',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 700
              }}>
                {t.kioskModeBadge}
              </span>
              <span style={{ fontSize: '0.8rem', color: '#64748B', fontWeight: 600 }}>
                {t.kioskModeDesc}
              </span>
            </div>
            <h2 style={{ fontSize: '1.6rem', color: '#0F172A', marginTop: '0.35rem', fontWeight: 800 }}>
              {t.kioskStudentTitle}
            </h2>
          </div>

          {/* Action Row in Marked Top Place: Vehicle Parking Log & Quick Filter Tabs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', flexWrap: 'wrap' }}>
            {/* Vehicle Parking Log Default Button in Marked Place */}
            <button
              type="button"
              onClick={() => setAppTab && setAppTab('vehicles')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '0.55rem 1.15rem',
                borderRadius: '10px',
                backgroundColor: '#2563EB',
                color: '#FFFFFF',
                fontWeight: 800,
                fontSize: '0.85rem',
                border: 'none',
                cursor: 'pointer',
                boxShadow: '0 4px 12px rgba(37, 99, 235, 0.25)',
                transition: 'all 0.15s ease'
              }}
              title={language === 'ta' ? 'வாகன பார்க்கிங் பதிவிற்கு செல் (ANPR)' : 'Go to Vehicle Parking Log (ANPR)'}
            >
              <Car size={18} />
              <span>{language === 'ta' ? 'வாகன பார்க்கிங் பதிவு' : 'Vehicle Parking Log'}</span>
              <span style={{
                fontSize: '0.65rem',
                backgroundColor: 'rgba(255, 255, 255, 0.25)',
                color: '#FFFFFF',
                padding: '0.15rem 0.45rem',
                borderRadius: '6px',
                fontWeight: 900
              }}>
                ANPR
              </span>
            </button>

            {/* Quick Filter Tabs */}
            <div style={{
              display: 'flex',
              backgroundColor: '#F1F5F9',
              padding: '4px',
              borderRadius: '10px',
              gap: '4px'
            }}>
            <button
              onClick={() => setActiveTab('STUDENT')}
              style={{
                padding: '0.5rem 1.1rem',
                borderRadius: '8px',
                fontSize: '0.825rem',
                fontWeight: 700,
                backgroundColor: activeTab === 'STUDENT' ? '#FFFFFF' : 'transparent',
                color: activeTab === 'STUDENT' ? '#2563EB' : '#475569',
                boxShadow: activeTab === 'STUDENT' ? '0 2px 6px rgba(0,0,0,0.06)' : 'none',
                border: 'none'
              }}
            >
              🎓 {t.tabRollLookup}
            </button>
            <button
              onClick={() => setActiveTab('PASS_VERIFY')}
              style={{
                padding: '0.5rem 1.1rem',
                borderRadius: '8px',
                fontSize: '0.825rem',
                fontWeight: 700,
                backgroundColor: activeTab === 'PASS_VERIFY' ? '#FFFFFF' : 'transparent',
                color: activeTab === 'PASS_VERIFY' ? '#2563EB' : '#475569',
                boxShadow: activeTab === 'PASS_VERIFY' ? '0 2px 6px rgba(0,0,0,0.06)' : 'none',
                border: 'none'
              }}
            >
              🎫 {t.tabVerifyQr}
            </button>
          </div>
        </div>
      </div>

        {/* Tab 1: Student Roll Number Lookup */}
        {activeTab === 'STUDENT' && (
          <div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto auto',
              gap: '0.75rem',
              alignItems: 'center',
              marginBottom: '1.25rem'
            }}>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  className="input-field"
                  style={{
                    fontSize: '1.15rem',
                    fontWeight: 600,
                    padding: '0.85rem 1rem 0.85rem 3rem',
                    borderRadius: '12px',
                    borderColor: '#93C5FD'
                  }}
                  value={rollNumberInput}
                  onChange={(e) => setRollNumberInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleStudentLookup()}
                  placeholder={t.rollPlaceholder}
                  autoFocus
                />
                <Search size={22} color="#3B82F6" style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)' }} />
              </div>

              <button
                onClick={() => handleStudentLookup()}
                disabled={loadingStudent}
                className="btn btn-primary btn-lg"
                style={{ padding: '0.85rem 1.6rem', fontWeight: 800 }}
              >
                {loadingStudent ? t.searching : t.btnQuickLookup}
              </button>

              {/* Sample Quick Click Tags for easy testing */}
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                {['22CS101', '22CS102', '23ME045'].map((r) => (
                  <button
                    key={r}
                    onClick={() => {
                      setRollNumberInput(r);
                      handleStudentLookup(r);
                    }}
                    style={{
                      padding: '0.85rem 0.75rem',
                      borderRadius: '10px',
                      backgroundColor: '#EFF6FF',
                      border: '1px solid #BFDBFE',
                      color: '#1D4ED8',
                      fontWeight: 700,
                      fontSize: '0.85rem'
                    }}
                  >
                    +{r}
                  </button>
                ))}
              </div>
            </div>

            {/* Student Preview Card */}
            {studentPreview && (
              <div style={{
                backgroundColor: '#F8FAFD',
                border: '2px solid #3B82F6',
                borderRadius: '16px',
                padding: '1.5rem',
                display: 'grid',
                gridTemplateColumns: '130px 1fr 280px',
                gap: '1.5rem',
                alignItems: 'center',
                animation: 'fadeIn 0.25s ease'
              }}>
                {/* Photo & Roll */}
                <div style={{ textAlign: 'center' }}>
                  <img
                    src={studentPreview.photoUrl}
                    alt={studentPreview.name}
                    style={{
                      width: '100px',
                      height: '100px',
                      borderRadius: '14px',
                      objectFit: 'cover',
                      border: '3px solid #FFFFFF',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                    }}
                  />
                  <span className="badge badge-blue" style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
                    {studentPreview.rollNumber}
                  </span>
                </div>

                {/* Details */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <h3 style={{ fontSize: '1.35rem', color: '#0F172A', fontWeight: 800 }}>
                      {studentPreview.name}
                    </h3>
                    <span className="badge badge-green">{t.verifiedId}</span>
                  </div>

                  <div style={{ fontSize: '0.925rem', color: '#334155', fontWeight: 600, marginBottom: '0.75rem' }}>
                    {studentPreview.department} • Year {studentPreview.yearOfStudy}
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.85rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#475569' }}>
                      {studentPreview.hostelOrDayScholar === 'HOSTEL' ? (
                        <>
                          <Home size={16} color="#2563EB" />
                          <span>{t.hostelLabel}: <strong>{studentPreview.roomOrBusRoute}</strong></span>
                        </>
                      ) : (
                        <>
                          <Bus size={16} color="#059669" />
                          <span>{t.transportLabel}: <strong>{studentPreview.roomOrBusRoute}</strong></span>
                        </>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#475569' }}>
                      <Phone size={16} color="#2563EB" />
                      <span>{t.parentLabel}: <strong>{studentPreview.parentPhone}</strong></span>
                    </div>
                  </div>
                </div>

                {/* Big 1-Click Action Buttons for Watchman */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                  <button
                    onClick={() => handleGateAction('IN')}
                    className="btn btn-success"
                    style={{
                      padding: '0.9rem',
                      fontSize: '1.05rem',
                      fontWeight: 800,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.6rem'
                    }}
                  >
                    <ArrowDownLeft size={22} strokeWidth={2.5} />
                    <span>{t.markIn}</span>
                  </button>

                  <button
                    onClick={() => handleGateAction('OUT')}
                    className="btn btn-primary"
                    style={{
                      padding: '0.9rem',
                      fontSize: '1.05rem',
                      fontWeight: 800,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.6rem'
                    }}
                  >
                    <ArrowUpRight size={22} strokeWidth={2.5} />
                    <span>{t.markOut}</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Verify Digital Out-Pass Code */}
        {activeTab === 'PASS_VERIFY' && (
          <div style={{ maxWidth: '600px', margin: '0 auto', textAlign: 'center', padding: '1rem 0' }}>
            <div style={{
              width: '60px',
              height: '60px',
              borderRadius: '50%',
              backgroundColor: '#EFF6FF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#2563EB',
              margin: '0 auto 1rem'
            }}>
              <QrCode size={32} />
            </div>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0F172A', marginBottom: '0.35rem' }}>
              {t.digitalVerifyTitle}
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: '1.5rem' }}>
              {t.digitalVerifyDesc}
            </p>

            <form onSubmit={handleVerifyPassCode} style={{ display: 'flex', gap: '0.65rem', marginBottom: '1rem' }}>
              <input
                type="text"
                className="input-field"
                style={{ fontSize: '1.1rem', letterSpacing: '0.1em', textAlign: 'center', fontWeight: 700 }}
                placeholder={t.passCodePlaceholder}
                value={passCodeInput}
                onChange={(e) => setPassCodeInput(e.target.value)}
              />
              <button type="submit" className="btn btn-primary" style={{ padding: '0 1.5rem', whiteSpace: 'nowrap', fontWeight: 800 }}>
                {t.btnVerifyOpen}
              </button>
            </form>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', fontSize: '0.8rem', color: '#64748B' }}>
              <span>{t.trySample}</span>
              <button
                type="button"
                onClick={() => setPassCodeInput('OP-4592')}
                style={{ background: 'none', color: '#2563EB', fontWeight: 700, textDecoration: 'underline' }}
              >
                OP-4592
              </button>
            </div>

            {passVerificationResult && (
              <div style={{
                marginTop: '1.5rem',
                padding: '1.25rem',
                borderRadius: '12px',
                backgroundColor: passVerificationResult.valid ? '#ECFDF5' : '#FEF2F2',
                border: passVerificationResult.valid ? '1.5px solid #10B981' : '1.5px solid #EF4444',
                textAlign: 'left'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 800, fontSize: '1.05rem', color: passVerificationResult.valid ? '#065F46' : '#991B1B' }}>
                  {passVerificationResult.valid ? <CheckCircle2 size={22} color="#10B981" /> : <ShieldAlert size={22} color="#EF4444" />}
                  <span>{passVerificationResult.message}</span>
                </div>
                {passVerificationResult.pass && (
                  <div style={{ marginTop: '0.65rem', fontSize: '0.85rem', color: '#1E293B' }}>
                    <div><strong>Student:</strong> {passVerificationResult.pass.studentName} ({passVerificationResult.pass.studentRollNumber})</div>
                    <div><strong>Destination:</strong> {passVerificationResult.pass.destination}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Live Gate Entry Register Table */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0F172A' }}>
              {t.logbookTitle}
            </h3>
            <p style={{ fontSize: '0.8rem', color: '#64748B' }}>
              {t.logbookSubtitle}
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            {gateLogs && gateLogs.length > 0 && clearGateLogs && (
              <button
                type="button"
                onClick={clearGateLogs}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  padding: '0.35rem 0.85rem',
                  fontSize: '0.78rem',
                  fontWeight: 800,
                  color: '#DC2626',
                  backgroundColor: '#FEE2E2',
                  border: '1px solid #FECACA',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
                title={language === 'ta' ? 'அனைத்து பதிவுகளையும் அழி' : 'Clear all gate log records'}
              >
                <span>🗑️</span>
                <span>{language === 'ta' ? 'பதிவுகளை அழி' : 'Clear Logbook'}</span>
              </button>
            )}
            <span className="badge badge-blue">
              {(gateLogs || []).length} {t.entriesRecorded}
            </span>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#F8FAFD', borderBottom: '2px solid #E2E8F0', color: '#475569', fontWeight: 700, fontSize: '0.8rem', textTransform: 'uppercase' }}>
                <th style={{ padding: '0.75rem 1rem' }}>{t.colDirection}</th>
                <th style={{ padding: '0.75rem 1rem' }}>{t.colPerson}</th>
                <th style={{ padding: '0.75rem 1rem' }}>{t.colCategory}</th>
                <th style={{ padding: '0.75rem 1rem' }}>{t.colPurpose}</th>
                <th style={{ padding: '0.75rem 1rem' }}>{t.colTime}</th>
                <th style={{ padding: '0.75rem 1rem' }}>{t.colStatus}</th>
              </tr>
            </thead>
            <tbody>
              {gateLogs && gateLogs.length > 0 ? (
                gateLogs.map((log) => (
                  <tr key={log.id} style={{ borderBottom: '1px solid #F1F5F9', transition: 'background-color 0.15s ease' }}>
                    <td style={{ padding: '0.85rem 1rem' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        fontWeight: 800,
                        fontSize: '0.8rem',
                        padding: '0.3rem 0.65rem',
                        borderRadius: '6px',
                        backgroundColor: log.direction === 'IN' ? '#ECFDF5' : '#EFF6FF',
                        color: log.direction === 'IN' ? '#065F46' : '#1D4ED8',
                        border: log.direction === 'IN' ? '1px solid #A7F3D0' : '1px solid #BFDBFE'
                      }}>
                        {log.direction === 'IN' ? <ArrowDownLeft size={15} /> : <ArrowUpRight size={15} />}
                        {log.direction}
                      </span>
                    </td>
                    <td style={{ padding: '0.85rem 1rem' }}>
                      <div style={{ fontWeight: 700, color: '#0F172A' }}>{log.personName}</div>
                      <div style={{ fontSize: '0.75rem', color: '#64748B' }}>{log.identifier}</div>
                    </td>
                    <td style={{ padding: '0.85rem 1rem' }}>
                      <span className="badge badge-blue">{log.personType}</span>
                    </td>
                    <td style={{ padding: '0.85rem 1rem', color: '#334155' }}>
                      <div>{log.purpose}</div>
                      {log.remarks && <div style={{ fontSize: '0.75rem', color: '#64748B' }}>{log.remarks}</div>}
                    </td>
                    <td style={{ padding: '0.85rem 1rem', fontWeight: 600, color: '#475569' }}>
                      {log.entryTime}
                    </td>
                    <td style={{ padding: '0.85rem 1rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className={`badge ${log.status === 'APPROVED' ? 'badge-green' : 'badge-amber'}`}>
                          {log.status}
                        </span>
                        {deleteGateLog && (
                          <button
                            type="button"
                            onClick={() => deleteGateLog(log.id)}
                            style={{
                              border: 'none',
                              background: 'transparent',
                              color: '#94A3B8',
                              cursor: 'pointer',
                              fontSize: '0.85rem',
                              padding: '0.2rem'
                            }}
                            title={language === 'ta' ? 'நீக்கு' : 'Delete'}
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748B' }}>
                    <div style={{
                      width: '46px',
                      height: '46px',
                      borderRadius: '50%',
                      backgroundColor: '#F1F5F9',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      margin: '0 auto 0.75rem',
                      color: '#94A3B8'
                    }}>
                      <Clock size={24} />
                    </div>
                    <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#334155' }}>
                      {language === 'ta' ? 'இன்றைய கேட் பதிவுகள் ஏதுமில்லை (சுத்தமான நிலை)' : 'No Gate Log Entries Recorded Yet (Clean State)'}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#94A3B8', marginTop: '0.35rem' }}>
                      {language === 'ta'
                        ? 'மாணவர் வருகை அல்லது வாகனங்கள் கேட்டை கடக்கும்போது மட்டுமே தானாக இங்கே பதிவாகும்.'
                        : 'Real-time entries will appear here automatically as students or vehicles pass the gate.'}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
