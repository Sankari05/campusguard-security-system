import React, { useState } from 'react';
import { api } from '../services/api';

export const OrganizationRegisterModal = ({ onClose, onSuccess }) => {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Form State
  const [orgType, setOrgType] = useState('COLLEGE');
  const [name, setName] = useState('');
  const [contactPerson, setContactPerson] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('Chennai');
  const [gateCount, setGateCount] = useState(2);
  const [expectedGuards, setExpectedGuards] = useState(6);
  const [selectedFeatures, setSelectedFeatures] = useState([
    'Automated Shift Handover',
    'Emergency Siren & SOS',
    'Visitor Photo & QR Passes'
  ]);
  const [customNotes, setCustomNotes] = useState('');

  const industries = [
    { type: 'COLLEGE', title: 'College / University', icon: '🎓', desc: 'Hostels, Students Out-Pass & Campus Gates' },
    { type: 'HOSPITAL', title: 'Hospital / Healthcare', icon: '🏥', desc: 'Ambulance Bays, ICU Visitors & Oxygen Storage' },
    { type: 'APARTMENT', title: 'Apartment / Gated Community', icon: '🏢', desc: 'Couriers, Resident Intercoms & Daily Maids' },
    { type: 'FACTORY', title: 'Factory / Heavy Plant', icon: '🏭', desc: 'Material RGP Pass, Weighbridge & Truck Driver PPE' },
    { type: 'OFFICE', title: 'Corporate Tech Park', icon: '🏛️', desc: 'Turnstile Badges, Laptop Serials & NDA Sign-off' },
  ];

  const handleFeatureToggle = (feature) => {
    if (selectedFeatures.includes(feature)) {
      setSelectedFeatures(selectedFeatures.filter((f) => f !== feature));
    } else {
      setSelectedFeatures([...selectedFeatures, feature]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const payload = {
        name: name.trim(),
        org_type: orgType,
        contact_person: contactPerson.trim(),
        contact_email: contactEmail.trim().toLowerCase(),
        contact_phone: contactPhone.trim(),
        address: address.trim() || undefined,
        city: city.trim() || 'Chennai',
        gate_count: parseInt(gateCount, 10) || 1,
        expected_guards: parseInt(expectedGuards, 10) || 2,
        security_requirements: `${selectedFeatures.join(', ')}. Special Notes: ${customNotes || 'None'}`
      };

      const result = await api.registerOrganization(payload);
      setLoading(false);
      if (onSuccess) {
        onSuccess(result);
      }
    } catch (err) {
      setLoading(false);
      const detail = err.response?.data?.detail || err.response?.data?.message || err.message;
      setError(typeof detail === 'string' ? detail : 'Failed to register organization. Please verify your entries.');
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.45)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
      padding: '1.5rem'
    }}>
      <div style={{
        backgroundColor: '#FFFFFF',
        border: '1.5px solid #E2E8F0',
        borderRadius: '24px',
        width: '100%',
        maxWidth: '680px',
        maxHeight: '92vh',
        overflowY: 'auto',
        boxShadow: '0 25px 60px -15px rgba(15, 23, 42, 0.25)',
        color: '#0F172A',
        padding: '2.5rem'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
          <div>
            <div style={{ fontSize: '0.8rem', color: '#2563EB', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Step {step} of 3 • Self-Serve Facility Onboarding
            </div>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 900, color: '#0F172A', margin: '0.35rem 0 0 0' }}>
              Register Your Organization
            </h2>
          </div>
          <button
            onClick={onClose}
            style={{
              background: '#F1F5F9',
              border: '1px solid #CBD5E1',
              color: '#64748B',
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              fontSize: '1.1rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div style={{
            backgroundColor: '#FEF2F2',
            border: '1.5px solid #EF4444',
            color: '#B91C1C',
            padding: '0.85rem 1rem',
            borderRadius: '12px',
            fontSize: '0.88rem',
            marginBottom: '1.5rem',
            fontWeight: 700
          }}>
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* STEP 1: Select Facility Type */}
          {step === 1 && (
            <div>
              <p style={{ color: '#475569', fontSize: '0.9rem', marginBottom: '1.25rem', lineHeight: 1.5 }}>
                Select the primary industry vertical that matches your facility. GuardMate tailors specialized security workflows for each type:
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '2rem' }}>
                {industries.map((ind) => {
                  const isSelected = orgType === ind.type;
                  return (
                    <div
                      key={ind.type}
                      onClick={() => setOrgType(ind.type)}
                      style={{
                        padding: '1rem 1.25rem',
                        borderRadius: '16px',
                        cursor: 'pointer',
                        border: isSelected ? '2.5px solid #2563EB' : '1.5px solid #E2E8F0',
                        background: isSelected
                          ? '#EFF6FF'
                          : '#F8FAFC',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '1rem',
                        transition: 'all 0.15s ease',
                        boxShadow: isSelected ? '0 4px 14px rgba(37, 99, 235, 0.12)' : 'none'
                      }}
                    >
                      <div style={{ fontSize: '2rem' }}>{ind.icon}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '1rem', fontWeight: 800, color: isSelected ? '#1E40AF' : '#1E293B' }}>
                          {ind.title}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#64748B', marginTop: '0.2rem' }}>
                          {ind.desc}
                        </div>
                      </div>
                      <div style={{
                        width: '20px',
                        height: '20px',
                        borderRadius: '50%',
                        border: isSelected ? '6px solid #2563EB' : '2px solid #CBD5E1',
                        backgroundColor: '#FFFFFF'
                      }} />
                    </div>
                  );
                })}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  style={{
                    background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
                    color: '#FFFFFF',
                    padding: '0.75rem 1.8rem',
                    borderRadius: '10px',
                    fontWeight: 800,
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '0.95rem',
                    boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)'
                  }}
                >
                  Next: Contact Details &rarr;
                </button>
              </div>
            </div>
          )}

          {/* STEP 2: Basic & Contact Details */}
          {step === 2 && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1rem', marginBottom: '1.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                    Organization / Facility Name *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. SRM Tech Campus or Apollo Healthcare"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.75rem 1rem',
                      borderRadius: '10px',
                      border: '1.5px solid #CBD5E1',
                      backgroundColor: '#FFFFFF',
                      color: '#0F172A',
                      fontSize: '0.9rem',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                    }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                      Primary Security Contact Person *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Col. Sundaram (Dean / CSO)"
                      value={contactPerson}
                      onChange={(e) => setContactPerson(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '0.75rem 1rem',
                        borderRadius: '10px',
                        border: '1.5px solid #CBD5E1',
                        backgroundColor: '#FFFFFF',
                        color: '#0F172A',
                        fontSize: '0.9rem',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                      Contact Email (For Admin Setup) *
                    </label>
                    <input
                      type="email"
                      required
                      placeholder="e.g. security@organization.org"
                      value={contactEmail}
                      onChange={(e) => setContactEmail(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '0.75rem 1rem',
                        borderRadius: '10px',
                        border: '1.5px solid #CBD5E1',
                        backgroundColor: '#FFFFFF',
                        color: '#0F172A',
                        fontSize: '0.9rem',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                      }}
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                      Contact Phone Number *
                    </label>
                    <input
                      type="tel"
                      required
                      placeholder="e.g. +91 98765 43210"
                      value={contactPhone}
                      onChange={(e) => setContactPhone(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '0.75rem 1rem',
                        borderRadius: '10px',
                        border: '1.5px solid #CBD5E1',
                        backgroundColor: '#FFFFFF',
                        color: '#0F172A',
                        fontSize: '0.9rem',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                      City / Location *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Chennai, Bangalore"
                      value={city}
                      onChange={(e) => setCity(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '0.75rem 1rem',
                        borderRadius: '10px',
                        border: '1.5px solid #CBD5E1',
                        backgroundColor: '#FFFFFF',
                        color: '#0F172A',
                        fontSize: '0.9rem',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                      }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                    Full Campus / Facility Address
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Survey 42, GST Road, Kattankulathur"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.75rem 1rem',
                      borderRadius: '10px',
                      border: '1.5px solid #CBD5E1',
                      backgroundColor: '#FFFFFF',
                      color: '#0F172A',
                      fontSize: '0.9rem',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                    }}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  style={{
                    backgroundColor: '#F1F5F9',
                    color: '#475569',
                    padding: '0.75rem 1.25rem',
                    borderRadius: '10px',
                    fontWeight: 700,
                    border: '1px solid #CBD5E1',
                    cursor: 'pointer'
                  }}
                >
                  &larr; Back
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (!name || !contactPerson || !contactEmail || !contactPhone) {
                      setError('Please fill in all required fields.');
                      return;
                    }
                    setError('');
                    setStep(3);
                  }}
                  style={{
                    background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
                    color: '#FFFFFF',
                    padding: '0.75rem 1.8rem',
                    borderRadius: '10px',
                    fontWeight: 800,
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '0.95rem',
                    boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)'
                  }}
                >
                  Next: Security Workflows &rarr;
                </button>
              </div>
            </div>
          )}

          {/* STEP 3: Gates, Guards & Workflows */}
          {step === 3 && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                    Number of Gates / Entry Portals *
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    required
                    value={gateCount}
                    onChange={(e) => setGateCount(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.75rem 1rem',
                      borderRadius: '10px',
                      border: '1.5px solid #CBD5E1',
                      backgroundColor: '#FFFFFF',
                      color: '#0F172A',
                      fontSize: '0.9rem',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                    }}
                  />
                  <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: '0.2rem' }}>e.g. Main Gate, Cargo Gate, Emergency Bay</div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                    Expected Security Guard Strength *
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="200"
                    required
                    value={expectedGuards}
                    onChange={(e) => setExpectedGuards(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.75rem 1rem',
                      borderRadius: '10px',
                      border: '1.5px solid #CBD5E1',
                      backgroundColor: '#FFFFFF',
                      color: '#0F172A',
                      fontSize: '0.9rem',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                    }}
                  />
                  <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: '0.2rem' }}>Total watchmen across shifts</div>
                </div>
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.6rem' }}>
                  Select Required Security Capabilities:
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                  {[
                    'Automated Shift Handover',
                    'Emergency Siren & SOS',
                    'Visitor Photo & QR Passes',
                    'ANPR Vehicle License Tagging',
                    'Digital Material Pass (RGP/NRGP)',
                    'Biometric / Face Recognition',
                    'Courier Parcel Desk',
                    'Curfew / After-Hours Escort'
                  ].map((feat) => {
                    const isChecked = selectedFeatures.includes(feat);
                    return (
                      <div
                        key={feat}
                        onClick={() => handleFeatureToggle(feat)}
                        style={{
                          padding: '0.65rem 0.85rem',
                          borderRadius: '8px',
                          border: isChecked ? '1.5px solid #2563EB' : '1px solid #CBD5E1',
                          backgroundColor: isChecked ? '#EFF6FF' : '#F8FAFC',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          fontSize: '0.82rem',
                          color: isChecked ? '#1D4ED8' : '#334155',
                          fontWeight: isChecked ? 700 : 500
                        }}
                      >
                        <span style={{ color: isChecked ? '#2563EB' : '#94A3B8' }}>{isChecked ? '☑' : '☐'}</span>
                        <span>{feat}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div style={{ marginBottom: '2rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                  Special Operational Protocols / Custom Instructions
                </label>
                <textarea
                  rows="2"
                  placeholder="e.g. Strict ambulance lane clearance, 21:30 PM hostel curfew bell, weighbridge tare logging"
                  value={customNotes}
                  onChange={(e) => setCustomNotes(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    borderRadius: '10px',
                    border: '1.5px solid #CBD5E1',
                    backgroundColor: '#FFFFFF',
                    color: '#0F172A',
                    fontSize: '0.85rem',
                    resize: 'none',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  style={{
                    backgroundColor: '#F1F5F9',
                    color: '#475569',
                    padding: '0.75rem 1.25rem',
                    borderRadius: '10px',
                    fontWeight: 700,
                    border: '1px solid #CBD5E1',
                    cursor: 'pointer'
                  }}
                >
                  &larr; Back
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
                    color: '#FFFFFF',
                    padding: '0.85rem 2rem',
                    borderRadius: '10px',
                    fontWeight: 800,
                    border: 'none',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    fontSize: '0.95rem',
                    boxShadow: '0 4px 15px rgba(5, 150, 105, 0.35)'
                  }}
                >
                  {loading ? 'Submitting Application...' : 'Submit Registration to Super-Admin 🚀'}
                </button>
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};
