import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  AlertOctagon,
  ShieldAlert,
  PhoneCall,
  CheckCircle2,
  Ambulance,
  Flame,
  Radio,
  Siren,
  Volume2
} from 'lucide-react';

export const EmergencySOS = () => {
  const { activeSos, triggerSos, resolveSos, language, t } = useAuth();
  const [selectedIncident, setSelectedIncident] = useState('Medical Emergency');
  const [incidentLocation, setIncidentLocation] = useState('Main Gate 1');
  const [incidentNotes, setIncidentNotes] = useState('');

  const playAlertSiren = () => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(800, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(400, audioCtx.currentTime + 0.3);
      osc.frequency.exponentialRampToValueAtTime(800, audioCtx.currentTime + 0.6);
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.8);
    } catch {
      // AudioContext not supported
    }
  };

  const handleTrigger = (e) => {
    e.preventDefault();
    triggerSos(`${selectedIncident} at ${incidentLocation}: ${incidentNotes || 'Immediate Assistance Required'}`);
    playAlertSiren();
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>

      {/* Active Incident Alert Banner if triggered */}
      {activeSos && (
        <div style={{
          backgroundColor: '#FEF2F2',
          border: '2px solid #EF4444',
          borderRadius: '16px',
          padding: '1.5rem',
          boxShadow: '0 10px 25px rgba(239, 68, 68, 0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          animation: 'fadeIn 0.3s ease'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              backgroundColor: '#DC2626',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF'
            }}>
              <Siren size={28} className="pulse-sos" />
            </div>
            <div>
              <div style={{
                display: 'inline-block',
                backgroundColor: '#DC2626',
                color: '#FFFFFF',
                fontSize: '0.75rem',
                fontWeight: 800,
                padding: '0.2rem 0.6rem',
                borderRadius: '6px',
                marginBottom: '0.25rem'
              }}>
                {language === 'ta' ? 'அவசர ஆபத்து எச்சரிக்கை' : 'ACTIVE CAMPUS EMERGENCY'}
              </div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#991B1B' }}>
                {activeSos.reason}
              </h3>
              <div style={{ fontSize: '0.825rem', color: '#B91C1C' }}>
                {activeSos.time} • {activeSos.reportedBy}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              onClick={playAlertSiren}
              className="btn btn-secondary"
              style={{ borderColor: '#EF4444', color: '#DC2626', fontWeight: 700 }}
            >
              <Volume2 size={18} />
              <span>{t.btnSiren}</span>
            </button>
            <button
              onClick={resolveSos}
              className="btn btn-success"
              style={{ fontWeight: 800 }}
            >
              <CheckCircle2 size={18} />
              <span>{t.btnResolved}</span>
            </button>
          </div>
        </div>
      )}

      {/* Grid: Trigger SOS Form & Quick Emergency Contacts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: '1.5rem' }}>
        {/* Panic Trigger Card */}
        <div className="card" style={{ border: '2px solid #FCA5A5' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '12px',
              backgroundColor: '#FEE2E2',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#DC2626'
            }}>
              <AlertOctagon size={24} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                {t.broadcastSosTitle}
              </h3>
            </div>
          </div>

          <form onSubmit={handleTrigger}>
            <div className="form-group">
              <label className="form-label">{t.incidentTypeLabel}</label>
              <select
                className="input-field"
                value={selectedIncident}
                onChange={(e) => setSelectedIncident(e.target.value)}
              >
                <option value="Medical Emergency / Ambulance Needed">🚑 {language === 'ta' ? 'மருத்துவ அவசரம் / ஆம்புலன்ஸ் தேவை' : 'Medical Emergency / Ambulance Needed'}</option>
                <option value="Unauthorized Vehicle / Gate Barrier Break">🚗 {language === 'ta' ? 'அனுமதியற்ற வாகனம் / கேட் தடுப்பு உடைப்பு' : 'Unauthorized Vehicle / Gate Barrier Crash'}</option>
                <option value="Fire Hazard / Chemical Leak">🧯 {language === 'ta' ? 'தீ விபத்து / ரசாயன கசிவு' : 'Fire Hazard / Lab Spill'}</option>
                <option value="Trespassing / Suspicious Person">⚠️ {language === 'ta' ? 'சந்தேகத்திற்குரிய நபர் ஊடுருவல்' : 'Trespassing / Suspicious Person'}</option>
                <option value="Student Altercation at Main Gate">👥 {language === 'ta' ? 'மாணவர் தகராறு / பிரச்சனை' : 'Student Altercation at Main Gate'}</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">{t.locationLabel}</label>
              <input
                type="text"
                className="input-field"
                value={incidentLocation}
                onChange={(e) => setIncidentLocation(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">{t.situationNotesLabel}</label>
              <textarea
                className="input-field"
                rows={3}
                placeholder={language === 'ta' ? 'சம்பவ விவரத்தை சுருக்கமாக குறிப்பிடவும்...' : 'Describe current situation for the response team...'}
                value={incidentNotes}
                onChange={(e) => setIncidentNotes(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="btn btn-danger btn-lg pulse-sos"
              style={{ width: '100%', marginTop: '0.5rem', fontWeight: 800 }}
            >
              <ShieldAlert size={20} />
              <span>{t.btnTriggerSos}</span>
            </button>
          </form>
        </div>

        {/* Rapid Contacts Directory */}
        <div className="card">
          <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A', marginBottom: '1.25rem' }}>
            {t.contactsTitle}
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {[
              { title: language === 'ta' ? 'வளாக சுகாதார மையம் & ஆம்புலன்ஸ்' : 'Campus Health Center & Ambulance', number: '+91 98400 11221', icon: Ambulance, color: '#DC2626', bg: '#FEE2E2' },
              { title: language === 'ta' ? 'தலைமை பாதுகாப்பு அதிகாரி (CSO)' : 'Chief Security Officer (CSO)', number: '+91 98400 11222', icon: Radio, color: '#2563EB', bg: '#EFF6FF' },
              { title: language === 'ta' ? 'முதல்வர் & நிர்வாக மேசை' : 'Principal & Management Desk', number: '+91 98400 11223', icon: PhoneCall, color: '#059669', bg: '#ECFDF5' },
              { title: language === 'ta' ? 'அருகிலுள்ள காவல் நிலையம்' : 'Nearest Police Station', number: '100 / 044-24340001', icon: ShieldAlert, color: '#4F46E5', bg: '#EEF2FF' },
              { title: language === 'ta' ? 'தீயணைப்பு & மீட்பு பணி' : 'Fire & Rescue Services', number: '101 / 044-28551010', icon: Flame, color: '#D97706', bg: '#FEF3C7' }
            ].map((contact, idx) => {
              const Icon = contact.icon;
              return (
                <div key={idx} style={{
                  padding: '0.85rem 1rem',
                  borderRadius: '12px',
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #E2E8F0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      backgroundColor: contact.bg,
                      color: contact.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}>
                      <Icon size={18} />
                    </div>
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#0F172A' }}>
                        {contact.title}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#2563EB', fontWeight: 700 }}>
                        {contact.number}
                      </div>
                    </div>
                  </div>

                  <a
                    href={`tel:${contact.number}`}
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: '0.75rem', fontWeight: 700 }}
                  >
                    {language === 'ta' ? 'அழைக்க' : 'Call'}
                  </a>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
