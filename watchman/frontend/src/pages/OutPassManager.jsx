import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  FileBadge,
  CheckCircle2,
  Clock,
  UserCheck,
  MapPin,
  QrCode,
  ShieldCheck,
  Search,
  ArrowUpRight
} from 'lucide-react';

export const OutPassManager = ({ setAppTab }) => {
  const { outPasses, addGateLog, language, t } = useAuth();
  const [passCodeInput, setPassCodeInput] = useState('');
  const [verificationResult, setVerificationResult] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const handleVerify = async (e) => {
    e.preventDefault();
    if (!passCodeInput.trim()) return;
    const res = await api.verifyOutPassCode(passCodeInput.trim());
    setVerificationResult(res);

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

  const filteredPasses = outPasses.filter((p) =>
    p.studentName.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.studentRollNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.passCode.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.6rem', color: '#0F172A', fontWeight: 800, margin: 0 }}>
            {t.outpassTitle}
          </h2>
        </div>

        {setAppTab && (
          <button
            type="button"
            onClick={() => setAppTab('dashboard')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.45rem 0.95rem',
              backgroundColor: '#FFFFFF',
              border: '1.5px solid #CBD5E1',
              borderRadius: '8px',
              fontSize: '0.825rem',
              fontWeight: 800,
              color: '#334155',
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
            }}
          >
            ← {language === 'ta' ? 'மேற்பார்வைக்கு திரும்பு (Overview)' : 'Back to Gate Overview'}
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '1.5rem' }}>
        {/* Rapid Pass Verification Box for Watchman */}
        <div className="card" style={{ border: '2px solid #BFDBFE' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '1.25rem' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              backgroundColor: '#EFF6FF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#2563EB'
            }}>
              <QrCode size={22} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                {t.digitalVerifyTitle}
              </h3>
            </div>
          </div>

          <form onSubmit={handleVerify}>
            <div className="form-group">
              <label className="form-label">{language === 'ta' ? 'மாணவரின் பாஸ் குறியீடு' : 'Student Pass Code'}</label>
              <input
                type="text"
                className="input-field"
                style={{ fontSize: '1.2rem', letterSpacing: '0.1em', textAlign: 'center', fontWeight: 800 }}
                placeholder={t.passCodePlaceholder}
                value={passCodeInput}
                onChange={(e) => setPassCodeInput(e.target.value)}
                autoFocus
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', padding: '0.85rem', fontWeight: 800, fontSize: '1rem', marginTop: '0.5rem' }}
            >
              <ArrowUpRight size={18} />
              <span>{t.btnVerifyOpen}</span>
            </button>
          </form>



          {verificationResult && (
            <div style={{
              marginTop: '1.5rem',
              padding: '1.2rem',
              borderRadius: '12px',
              backgroundColor: verificationResult.valid ? '#ECFDF5' : '#FEF2F2',
              border: verificationResult.valid ? '1.5px solid #10B981' : '1.5px solid #EF4444',
              textAlign: 'left'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 800, fontSize: '1.05rem', color: verificationResult.valid ? '#065F46' : '#991B1B' }}>
                <CheckCircle2 size={22} color="#10B981" />
                <span>{verificationResult.message}</span>
              </div>
              {verificationResult.pass && (
                <div style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: '#1E293B', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <div><strong>Student:</strong> {verificationResult.pass.studentName} ({verificationResult.pass.studentRollNumber})</div>
                  <div><strong>Destination:</strong> {verificationResult.pass.destination}</div>
                  <div style={{ color: '#059669', fontWeight: 700 }}>✓ Gate cleared and logged automatically</div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* List of Approved Passes Today */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                {language === 'ta' ? 'அனுமதிக்கப்பட்ட பாஸ்கள்' : 'Active Approved Passes'}
              </h3>
            </div>

            <div style={{ position: 'relative', width: '200px' }}>
              <input
                type="text"
                className="input-field"
                style={{ padding: '0.4rem 0.6rem 0.4rem 2rem', fontSize: '0.8rem' }}
                placeholder={language === 'ta' ? 'தேட...' : 'Search pass / name...'}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <Search size={14} color="#94A3B8" style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {filteredPasses.map((pass) => (
              <div
                key={pass.id}
                style={{
                  border: '1.5px solid #DBEAFE',
                  backgroundColor: pass.status === 'APPROVED_BY_HOD' ? '#F0FDF4' : '#FFFFFF',
                  borderRadius: '12px',
                  padding: '1rem 1.15rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                    <span style={{
                      backgroundColor: '#FFFFFF',
                      border: '1.5px solid #CBD5E1',
                      padding: '0.2rem 0.6rem',
                      borderRadius: '6px',
                      fontFamily: 'monospace',
                      fontWeight: 800,
                      fontSize: '0.85rem',
                      color: '#1E293B'
                    }}>
                      {pass.passCode}
                    </span>
                    <h4 style={{ fontSize: '1rem', fontWeight: 800, color: '#0F172A' }}>
                      {pass.studentName} ({pass.studentRollNumber})
                    </h4>
                    <span className={`badge ${pass.status === 'APPROVED_BY_HOD' ? 'badge-green' : 'badge-blue'}`}>
                      {pass.status === 'APPROVED_BY_HOD' ? (language === 'ta' ? 'HOD அனுமதித்தது' : 'HOD APPROVED') : pass.status}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.825rem', color: '#334155', marginBottom: '0.35rem' }}>
                    <strong>{t.reasonLabel}:</strong> {pass.reason}
                  </div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', fontSize: '0.75rem', color: '#64748B' }}>
                    <div>📍 {t.destinationLabel}: <strong>{pass.destination}</strong></div>
                    <div>🕒 {t.timingLabel}: <strong>{pass.outTimeExpected} → {pass.inTimeExpected}</strong></div>
                    {pass.approvedBy && (
                      <div style={{ color: '#047857', fontWeight: 700 }}>✓ {t.approvedByLabel}: {pass.approvedBy}</div>
                    )}
                  </div>
                </div>

                <button
                  onClick={() => {
                    setPassCodeInput(pass.passCode);
                  }}
                  className="btn btn-secondary btn-sm"
                  style={{ whiteSpace: 'nowrap' }}
                >
                  <span>{language === 'ta' ? 'கேட் திறக்க' : 'Verify'}</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
