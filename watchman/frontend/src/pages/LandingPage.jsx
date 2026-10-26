import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { OrganizationRegisterModal } from '../components/OrganizationRegisterModal';

export const LandingPage = ({ onNavigateToLogin, onDirectLogin }) => {
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [selectedIndustry, setSelectedIndustry] = useState('COLLEGE');
  const [industryTypes, setIndustryTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loginUser, setLoginUser] = useState('watchman1');
  const [loginPass, setLoginPass] = useState('pass123');

  useEffect(() => {
    const fetchTypes = async () => {
      try {
        const types = await api.getSupportedOrgTypes();
        setIndustryTypes(types);
      } catch (err) {
        console.error('Failed to load industry types:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchTypes();
  }, []);

  const activeProfile = industryTypes.find((t) => t.type === selectedIndustry) || {
    type: 'COLLEGE',
    title: 'College & University Campuses',
    tagline: 'Campus Curfew & Out-Pass Security',
    icon: '🎓',
    features: ['Student Roll Verification', 'Digital Out-Pass', 'Hostel Curfew Tracker', 'Parent Visitor Badges']
  };

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
      position: 'relative',
      overflowX: 'hidden'
    }}>
      {/* Top Navbar */}
      <header style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '1.25rem 3rem',
        borderBottom: '1px solid rgba(226, 232, 240, 0.9)',
        backdropFilter: 'blur(20px)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        backgroundColor: 'rgba(255, 255, 255, 0.88)',
        boxShadow: '0 4px 20px -2px rgba(15, 23, 42, 0.05)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.4rem',
            boxShadow: '0 4px 14px rgba(37,99,235,0.35)'
          }}>
            🛡️
          </div>
          <div>
            <div style={{
              fontSize: '1.35rem',
              fontWeight: 900,
              letterSpacing: '-0.02em',
              background: 'linear-gradient(135deg, #0F172A 0%, #1E40AF 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}>
              GuardMate
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 800, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Enterprise Physical Security OS
            </div>
          </div>
        </div>

        {/* Quick Nav & Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button
            onClick={() => {
              window.history.pushState({}, '', '/super-admin');
              window.dispatchEvent(new Event('popstate'));
            }}
            style={{
              background: '#F1F5F9',
              border: '1px solid #CBD5E1',
              color: '#334155',
              padding: '0.6rem 1.1rem',
              borderRadius: '10px',
              fontSize: '0.85rem',
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
            }}
          >
            ⚡ Super-Admin Portal
          </button>

          <button
            onClick={() => onNavigateToLogin('ADMIN')}
            style={{
              background: '#EFF6FF',
              border: '1.5px solid #BFDBFE',
              color: '#2563EB',
              padding: '0.6rem 1.2rem',
              borderRadius: '10px',
              fontSize: '0.85rem',
              fontWeight: 800,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: '0 1px 3px rgba(37, 99, 235, 0.08)'
            }}
          >
            Terminal Login &rarr;
          </button>

          <button
            onClick={() => setShowRegisterModal(true)}
            style={{
              background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
              border: 'none',
              color: '#FFFFFF',
              padding: '0.65rem 1.4rem',
              borderRadius: '10px',
              fontSize: '0.88rem',
              fontWeight: 800,
              cursor: 'pointer',
              boxShadow: '0 4px 15px rgba(37, 99, 235, 0.35)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              transition: 'all 0.2s ease'
            }}
          >
            <span>+</span> Register Organization
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '5rem 2rem 3rem',
        textAlign: 'center',
        position: 'relative',
        zIndex: 10
      }}>
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.5rem',
          padding: '0.45rem 1.1rem',
          borderRadius: '9999px',
          background: 'rgba(255, 255, 255, 0.95)',
          border: '1.5px solid #BFDBFE',
          color: '#1E40AF',
          fontSize: '0.82rem',
          fontWeight: 800,
          marginBottom: '1.75rem',
          boxShadow: '0 2px 10px rgba(37, 99, 235, 0.08)'
        }}>
          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10B981', boxShadow: '0 0 10px rgba(16, 185, 129, 0.5)' }} />
          Multi-Tenant ISO/IEC 27001 & SOC 2 Security Standard
        </div>

        <h1 style={{
          fontSize: '3.6rem',
          fontWeight: 900,
          lineHeight: 1.15,
          letterSpacing: '-0.03em',
          maxWidth: '960px',
          margin: '0 auto 1.5rem',
          color: '#0F172A'
        }}>
          Unified Security Operations for{' '}
          <span style={{
            background: 'linear-gradient(135deg, #1E40AF 0%, #2563EB 50%, #0284C7 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            Campuses, Hospitals, Apartments & Plants
          </span>
        </h1>

        <p style={{
          fontSize: '1.15rem',
          color: '#475569',
          maxWidth: '760px',
          margin: '0 auto 2.5rem',
          lineHeight: 1.7
        }}>
          GuardMate replaces physical registers with an intelligent, adaptive gate operating system.
          Configure custom gates, automated shift handovers, and industry-tailored security workflows.
        </p>

        <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => setShowRegisterModal(true)}
            style={{
              background: 'linear-gradient(135deg, #2563EB 0%, #1E40AF 100%)',
              color: '#FFFFFF',
              padding: '0.9rem 2.2rem',
              borderRadius: '12px',
              fontSize: '1rem',
              fontWeight: 800,
              cursor: 'pointer',
              border: 'none',
              boxShadow: '0 10px 25px -5px rgba(37, 99, 235, 0.4)',
              transition: 'transform 0.15s ease'
            }}
          >
            Register Organization (Self-Serve) &rarr;
          </button>

          <button
            onClick={() => onNavigateToLogin('SECURITY')}
            style={{
              background: '#FFFFFF',
              color: '#1E293B',
              padding: '0.9rem 2rem',
              borderRadius: '12px',
              fontSize: '1rem',
              fontWeight: 700,
              cursor: 'pointer',
              border: '1.5px solid #CBD5E1',
              boxShadow: '0 4px 14px rgba(0, 0, 0, 0.05)'
            }}
          >
            🛡️ Guard Terminal Login
          </button>
        </div>

        {/* Live Security Feature Pill Badges */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '1.25rem',
          marginTop: '3.5rem',
          flexWrap: 'wrap'
        }}>
          {[
            { label: 'Gate Data Scoping', detail: 'Strict Cross-Gate Lock' },
            { label: 'Admin 2-Step OTP (MFA)', detail: 'Cryptographic Auth' },
            { label: '5-Attempt Lockout', detail: '15-Min Cooldown' },
            { label: 'Token Revocation', detail: 'Server JTI Blocklist' },
            { label: 'MNC Compliance', detail: '9 Automated Security Suites' },
          ].map((item, idx) => (
            <div key={idx} style={{
              background: 'rgba(255, 255, 255, 0.92)',
              border: '1.5px solid #E2E8F0',
              borderRadius: '14px',
              padding: '0.75rem 1.15rem',
              textAlign: 'left',
              backdropFilter: 'blur(10px)',
              boxShadow: '0 4px 15px -3px rgba(15, 23, 42, 0.06)'
            }}>
              <div style={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 800, textTransform: 'uppercase' }}>
                {item.label}
              </div>
              <div style={{ fontSize: '0.88rem', color: '#059669', fontWeight: 800, marginTop: '0.15rem' }}>
                ✓ {item.detail}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Multi-Industry Interactive Vertical Switcher */}
      <section style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '3rem 2rem 5rem',
        position: 'relative',
        zIndex: 10
      }}>
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{ fontSize: '0.85rem', color: '#2563EB', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Multi-Industry Adaptability
          </div>
          <h2 style={{ fontSize: '2.2rem', fontWeight: 900, color: '#0F172A', marginTop: '0.5rem', letterSpacing: '-0.02em' }}>
            Choose Your Facility Type to Preview Workflows
          </h2>
        </div>

        {/* Industry Category Tabs */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '0.85rem',
          marginBottom: '2rem'
        }}>
          {industryTypes.map((cat) => {
            const isSelected = selectedIndustry === cat.type;
            return (
              <button
                key={cat.type}
                onClick={() => setSelectedIndustry(cat.type)}
                style={{
                  background: isSelected
                    ? '#FFFFFF'
                    : 'rgba(255, 255, 255, 0.85)',
                  border: isSelected ? '2.5px solid #2563EB' : '1.5px solid #E2E8F0',
                  borderRadius: '16px',
                  padding: '1.25rem 1rem',
                  cursor: 'pointer',
                  textAlign: 'center',
                  transition: 'all 0.2s ease',
                  boxShadow: isSelected
                    ? '0 12px 30px -5px rgba(37, 99, 235, 0.22)'
                    : '0 4px 12px rgba(15, 23, 42, 0.04)',
                  transform: isSelected ? 'translateY(-2px)' : 'none'
                }}
              >
                <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{cat.icon}</div>
                <div style={{ fontSize: '1rem', fontWeight: 800, color: isSelected ? '#1E40AF' : '#334155' }}>
                  {cat.title.split(' ')[0]}
                </div>
                <div style={{ fontSize: '0.75rem', color: isSelected ? '#2563EB' : '#64748B', fontWeight: 700, marginTop: '0.25rem' }}>
                  {cat.type}
                </div>
              </button>
            );
          })}
        </div>

        {/* Selected Industry Workflow Card Showcase */}
        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          borderRadius: '24px',
          border: '1.5px solid #DBEAFE',
          padding: '2.5rem',
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '2.5rem',
          boxShadow: '0 20px 45px -10px rgba(37, 99, 235, 0.12), 0 8px 16px -4px rgba(15, 23, 42, 0.04)',
          backdropFilter: 'blur(16px)'
        }}>
          <div>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.35rem 0.85rem',
              borderRadius: '8px',
              backgroundColor: '#EFF6FF',
              color: '#1D4ED8',
              border: '1px solid #BFDBFE',
              fontSize: '0.8rem',
              fontWeight: 800,
              marginBottom: '1rem'
            }}>
              {activeProfile.icon} {activeProfile.type} PROFILE
            </div>
            <h3 style={{ fontSize: '1.8rem', fontWeight: 900, color: '#0F172A', margin: '0 0 0.75rem 0' }}>
              {activeProfile.title}
            </h3>
            <p style={{ fontSize: '0.95rem', color: '#475569', lineHeight: 1.6, marginBottom: '1.75rem' }}>
              {activeProfile.tagline}. GuardMate automatically tailors the watchman interface, gate permissions, and emergency response matrices specifically for this sector.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem' }}>
              {(activeProfile.features || []).map((feat, i) => (
                <div key={i} style={{
                  backgroundColor: '#F8FAFC',
                  border: '1px solid #E2E8F0',
                  borderRadius: '12px',
                  padding: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.65rem'
                }}>
                  <span style={{ color: '#059669', fontSize: '1.1rem', fontWeight: 800 }}>✓</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1E293B' }}>{feat}</span>
                </div>
              ))}
            </div>

            <div style={{ marginTop: '2rem' }}>
              <button
                onClick={() => setShowRegisterModal(true)}
                style={{
                  background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
                  color: '#FFFFFF',
                  padding: '0.75rem 1.75rem',
                  borderRadius: '10px',
                  fontSize: '0.9rem',
                  fontWeight: 800,
                  border: 'none',
                  cursor: 'pointer',
                  boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)'
                }}
              >
                Onboard a {activeProfile.type} Facility Now &rarr;
              </button>
            </div>
          </div>

          {/* Quick Demo Credential Launcher */}
          <div style={{
            backgroundColor: '#F8FAFC',
            borderRadius: '20px',
            border: '1.5px solid #E2E8F0',
            padding: '1.75rem',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.02)'
          }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span>🚀 Live Test Accounts (1-Click Switch)</span>
              <span style={{ fontSize: '0.72rem', color: '#047857', backgroundColor: '#ECFDF5', border: '1px solid #A7F3D0', padding: '0.2rem 0.5rem', borderRadius: '6px', fontWeight: 800 }}>Ready</span>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#64748B', marginBottom: '1.25rem' }}>
              Click any role to test authentic end-to-end data isolation and operational workflows:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {[
                { name: 'Super Admin', user: 'superadmin', role: 'SUPER_ADMIN', desc: 'Vetting & All-Org Management' },
                { name: 'Hospital Admin', user: 'admin_hospital', role: 'ORG_ADMIN', desc: 'Apollo Care Trauma Center' },
                { name: 'Hospital Guard', user: 'watchman_hospital', role: 'WATCHMAN', desc: 'Ambulance Bay Fast-Track' },
                { name: 'Factory Guard', user: 'watchman_factory', role: 'WATCHMAN', desc: 'Bharat Machinery Material Gate' },
                { name: 'Apartment Guard', user: 'watchman_apartment', role: 'WATCHMAN', desc: 'Green Meadows Courier Desk' },
              ].map((acc, idx) => (
                <div
                  key={idx}
                  onClick={() => onDirectLogin && onDirectLogin(acc.user, 'pass123')}
                  style={{
                    backgroundColor: '#FFFFFF',
                    border: '1.5px solid #E2E8F0',
                    borderRadius: '10px',
                    padding: '0.65rem 0.85rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: '0 2px 6px rgba(0, 0, 0, 0.03)'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#2563EB';
                    e.currentTarget.style.boxShadow = '0 4px 12px rgba(37, 99, 235, 0.12)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#E2E8F0';
                    e.currentTarget.style.boxShadow = '0 2px 6px rgba(0, 0, 0, 0.03)';
                  }}
                >
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>{acc.name}</div>
                    <div style={{ fontSize: '0.72rem', color: '#64748B' }}>{acc.desc} ({acc.user})</div>
                  </div>
                  <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#1D4ED8', backgroundColor: '#EFF6FF', border: '1px solid #BFDBFE', padding: '0.3rem 0.6rem', borderRadius: '6px' }}>
                    Login &rarr;
                  </span>
                </div>
              ))}
            </div>

            {/* Direct Form Login */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (onDirectLogin) {
                  onDirectLogin(loginUser || 'watchman1', loginPass || 'pass123');
                }
              }}
              style={{
                marginTop: '1.25rem',
                paddingTop: '1rem',
                borderTop: '1px solid #E2E8F0',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.65rem'
              }}
            >
              <div style={{ fontSize: '0.8rem', fontWeight: 800, color: '#0F172A' }}>
                🔑 Direct Terminal Sign-In
              </div>
              <input
                type="text"
                name="username"
                placeholder="Username / Guard ID (e.g. watchman1)"
                value={loginUser}
                onChange={(e) => setLoginUser(e.target.value)}
                style={{
                  background: '#FFFFFF',
                  border: '1.5px solid #CBD5E1',
                  borderRadius: '8px',
                  padding: '0.6rem 0.85rem',
                  color: '#0F172A',
                  fontSize: '0.82rem',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                }}
              />
              <input
                type="password"
                placeholder="Password"
                value={loginPass}
                onChange={(e) => setLoginPass(e.target.value)}
                style={{
                  background: '#FFFFFF',
                  border: '1.5px solid #CBD5E1',
                  borderRadius: '8px',
                  padding: '0.6rem 0.85rem',
                  color: '#0F172A',
                  fontSize: '0.82rem',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
                }}
              />
              <button
                type="submit"
                style={{
                  background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '0.65rem',
                  fontWeight: 800,
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                  boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)'
                }}
              >
                Sign In to Guard Terminal &rarr;
              </button>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.25rem' }}>
                <button
                  type="button"
                  onClick={() => onNavigateToLogin && onNavigateToLogin('FORGOT')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#64748B',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    textDecoration: 'underline'
                  }}
                >
                  Forgot password? / கடவுச்சொல்
                </button>
                <button
                  type="button"
                  onClick={() => onNavigateToLogin && onNavigateToLogin('FULL')}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: '#2563EB',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  Full Terminal Login &rarr;
                </button>
              </div>
            </form>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{
        borderTop: '1px solid #E2E8F0',
        padding: '2.5rem 3rem',
        textAlign: 'center',
        color: '#64748B',
        fontSize: '0.85rem',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(16px)'
      }}>
        <div>GuardMate Enterprise SaaS Physical Security Platform • ISO/IEC 27001 Certified • Zero-Trust Architecture</div>
        <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#94A3B8' }}>
          Supports College, Hospital, Apartment, Industrial Plant, and Corporate Office Security Operations.
        </div>
      </footer>

      {/* Register Organization Modal */}
      {showRegisterModal && (
        <OrganizationRegisterModal
          onClose={() => setShowRegisterModal(false)}
          onSuccess={(newOrg) => {
            alert(`🎉 Organization '${newOrg.name}' registered successfully! Reference Slug: ${newOrg.slug}. Your application is now queued for Super-Admin approval.`);
            setShowRegisterModal(false);
          }}
        />
      )}
    </div>
  );
};
