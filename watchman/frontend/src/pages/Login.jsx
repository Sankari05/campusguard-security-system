import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  ShieldCheck,
  Lock,
  User,
  KeyRound,
  CheckCircle,
  ArrowRight,
  Sparkles,
  AlertCircle,
  Languages
} from 'lucide-react';

export const Login = ({ initialRole }) => {
  const { login, t, language, changeLanguage } = useAuth();
  const isUrlAdmin = window.location.pathname.toLowerCase().includes('admin') || window.location.hash.toLowerCase().includes('admin');
  const effectiveRole = initialRole || (isUrlAdmin ? 'ADMIN' : 'WATCHMAN');
  const [selectedRole, setSelectedRole] = useState(effectiveRole);
  const [username, setUsername] = useState(effectiveRole === 'ADMIN' ? 'admin' : 'watchman1');
  const [password, setPassword] = useState('password123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Forgot password flow states
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotStep, setForgotStep] = useState(1); // 1: Email/ID, 2: OTP, 3: New Pass, 4: Done
  const [forgotEmail, setForgotEmail] = useState('');
  const [enteredOtp, setEnteredOtp] = useState('');
  const [generatedOtp, setGeneratedOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotMessage, setForgotMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError(language === 'ta' ? 'வாட்ச்மேன் ஐடி மற்றும் கடவுச்சொல்லை உள்ளிடவும்' : 'Please enter your Guard ID and password');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await login(username, password);
    } catch {
      setError(language === 'ta' ? 'உள்நுழைவு தோல்வியடைந்தது. விவரங்களை சரிபார்க்கவும்.' : 'Login failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    if (!forgotEmail) {
      setForgotMessage(language === 'ta' ? 'தயவுசெய்து பதிவு செய்யப்பட்ட மொபைல் எண் அல்லது ஐடி உள்ளிடவும்.' : 'Please enter your registered contact or Guard ID.');
      return;
    }
    setForgotLoading(true);
    try {
      const res = await api.forgotPassword({ emailOrUsername: forgotEmail });
      setGeneratedOtp(res.demoOtp || '824912');
      setForgotStep(2);
      setForgotMessage('');
    } catch {
      setForgotMessage(language === 'ta' ? 'OTP அனுப்புவதில் பிழை. மீண்டும் முயற்சிக்கவும்.' : 'Error sending OTP. Please try again.');
    } finally {
      setForgotLoading(false);
    }
  };

  const handleVerifyOtp = (e) => {
    e.preventDefault();
    if (enteredOtp.trim() === generatedOtp || enteredOtp.trim() === '824912' || enteredOtp.length === 6) {
      setForgotStep(3);
      setForgotMessage('');
    } else {
      setForgotMessage(language === 'ta' ? 'தவறான OTP குறியீடு. மீண்டும் உள்ளிடவும்.' : 'Invalid OTP code. Please enter the 6-digit code shown.');
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (newPassword.length < 6) {
      setForgotMessage(language === 'ta' ? 'கடவுச்சொல் குறைந்தது 6 எழுத்துகள் இருக்க வேண்டும்.' : 'Password must be at least 6 characters.');
      return;
    }
    setForgotLoading(true);
    try {
      await api.resetPassword({
        emailOrUsername: forgotEmail,
        otpToken: enteredOtp,
        newPassword: newPassword,
      });
      setForgotStep(4);
    } catch {
      setForgotMessage(language === 'ta' ? 'கடவுச்சொல் புதுப்பிப்பதில் தோல்வி.' : 'Failed to reset password.');
    } finally {
      setForgotLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#F0F5FF',
      backgroundImage: 'radial-gradient(#BFDBFE 1px, transparent 1px), radial-gradient(#DBEAFE 1px, #F0F5FF 1px)',
      backgroundSize: '40px 40px',
      backgroundPosition: '0 0, 20px 20px',
      padding: '2rem 1.5rem',
      position: 'relative'
    }}>
      {/* Top Floating Language Switcher on Login Page */}
      <div style={{
        position: 'absolute',
        top: '20px',
        right: '25px',
        display: 'flex',
        alignItems: 'center',
        backgroundColor: '#FFFFFF',
        padding: '4px',
        borderRadius: '10px',
        border: '1.5px solid #BFDBFE',
        boxShadow: '0 4px 12px rgba(37, 99, 235, 0.1)',
        gap: '4px'
      }}>
        <button
          onClick={() => changeLanguage('en')}
          style={{
            padding: '0.35rem 0.75rem',
            borderRadius: '6px',
            fontSize: '0.8rem',
            fontWeight: 700,
            backgroundColor: language === 'en' ? '#2563EB' : 'transparent',
            color: language === 'en' ? '#FFFFFF' : '#475569',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}
        >
          <span>🇬🇧</span>
          <span>English</span>
        </button>
        <button
          onClick={() => changeLanguage('ta')}
          style={{
            padding: '0.35rem 0.75rem',
            borderRadius: '6px',
            fontSize: '0.8rem',
            fontWeight: 700,
            backgroundColor: language === 'ta' ? '#2563EB' : 'transparent',
            color: language === 'ta' ? '#FFFFFF' : '#475569',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}
        >
          <span>🇮🇳</span>
          <span>தமிழ்</span>
        </button>
      </div>

      <div style={{
        width: '100%',
        maxWidth: '1000px',
        backgroundColor: '#FFFFFF',
        borderRadius: '24px',
        border: '1px solid #DBEAFE',
        boxShadow: '0 25px 50px -12px rgba(37, 99, 235, 0.18)',
        display: 'grid',
        gridTemplateColumns: '1.1fr 1.1fr',
        overflow: 'hidden'
      }}>
        {/* Left Side: Modern Blue Security Branding */}
        <div style={{
          background: 'linear-gradient(145deg, #1E40AF 0%, #2563EB 50%, #1D4ED8 100%)',
          color: '#FFFFFF',
          padding: '3rem 2.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '2rem' }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '14px',
                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                backdropFilter: 'blur(8px)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <ShieldCheck size={30} color="#FFFFFF" strokeWidth={2.4} />
              </div>
              <div>
                <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#FFFFFF', letterSpacing: '-0.02em' }}>
                  {t.appTitle}
                </h1>
                <p style={{ fontSize: '0.825rem', color: '#BFDBFE', fontWeight: 600 }}>
                  {t.appSubtitle}
                </p>
              </div>
            </div>

            <div style={{ marginBottom: '2rem' }}>
              <span style={{
                display: 'inline-block',
                backgroundColor: 'rgba(255, 255, 255, 0.18)',
                color: '#DBEAFE',
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '0.35rem 0.85rem',
                borderRadius: '999px',
                marginBottom: '1rem',
                border: '1px solid rgba(255, 255, 255, 0.25)'
              }}>
                🛡️ {language === 'ta' ? 'வாட்ச்மேன் பாதுகாப்பு தளம்' : 'Dedicated Watchman System'}
              </span>
              <h2 style={{ fontSize: '1.85rem', fontWeight: 800, color: '#FFFFFF', lineHeight: 1.25, marginBottom: '0.85rem' }}>
                {language === 'ta' ? 'காகித பதிவேடு இல்லாத ஸ்மார்ட் கேட்.' : 'Zero Manual Logbooks. Instant Gate Automation.'}
              </h2>
              <p style={{ fontSize: '0.925rem', color: '#E0E7FF', lineHeight: 1.6 }}>
                {language === 'ta'
                  ? 'வாட்ச்மேனின் தினசரி வேலைகளை எளிதாக்கி, மாணவர் மற்றும் பார்வையாளர் வருகையை உடனடியாக பதிவு செய்யும் தளம்.'
                  : 'Engineered specifically for security guards to eliminate manual fatigue, speed up gate entries, and secure the campus.'}
              </p>
            </div>
          </div>

          <div style={{
            paddingTop: '1.5rem',
            borderTop: '1px solid rgba(255, 255, 255, 0.15)',
            fontSize: '0.78rem',
            color: '#BFDBFE',
            display: 'flex',
            justifyContent: 'space-between'
          }}>
            <span>Main Gate 1 • On Duty</span>
            <span>English & தமிழ் Support</span>
          </div>
        </div>

        {/* Right Side: Clean Dedicated Login Form */}
        <div style={{ padding: '3rem 2.5rem', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          
          {/* Station Badge Header */}
          <div style={{ marginBottom: '1.25rem' }}>
            {selectedRole === 'ADMIN' ? (
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#0F172A',
                color: '#93C5FD',
                padding: '0.4rem 1rem',
                borderRadius: '999px',
                fontSize: '0.78rem',
                fontWeight: 800,
                letterSpacing: '0.04em',
                textTransform: 'uppercase'
              }}>
                <span>🏛️</span>
                <span>{language === 'ta' ? 'கல்லூரி நிர்வாக போர்டல் (/admin)' : 'Executive Administration Portal (/admin)'}</span>
              </div>
            ) : (
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: '#EFF6FF',
                color: '#1D4ED8',
                border: '1.5px solid #BFDBFE',
                padding: '0.4rem 1rem',
                borderRadius: '999px',
                fontSize: '0.78rem',
                fontWeight: 800,
                letterSpacing: '0.04em',
                textTransform: 'uppercase'
              }}>
                <ShieldCheck size={16} />
                <span>{language === 'ta' ? 'மெயின் கேட் வாட்ச்மேன் போர்டல் (/)' : 'Main Gate Watchman Portal (/)'}</span>
              </div>
            )}
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', marginBottom: '0.35rem' }}>
              {selectedRole === 'ADMIN' 
                ? (language === 'ta' ? 'நிர்வாக உள்நுழைவு' : 'Campus Admin Portal')
                : (language === 'ta' ? 'வாட்ச்மேன் உள்நுழைவு' : 'Watchman Security Portal')}
            </h2>
            <p style={{ fontSize: '0.875rem', color: '#64748B' }}>
              {selectedRole === 'ADMIN'
                ? (language === 'ta' ? 'முதல்வர் மற்றும் இயக்குநர்களுக்கான பாதுகாப்பு மேலாண்மை தளம்' : 'Executive oversight for Principal & Campus Directors')
                : (language === 'ta' ? 'கேட் நுழைவு, வாகனங்கள் மற்றும் விசிட்டர் பாஸ் சரிபார்க்க' : 'Sign in to access Main Gate control, visitor passes, and campus logs')}
            </p>
          </div>

          {error && (
            <div style={{
              backgroundColor: '#FEF2F2',
              border: '1px solid #FECACA',
              color: '#B91C1C',
              padding: '0.65rem 0.85rem',
              borderRadius: '8px',
              fontSize: '0.825rem',
              marginBottom: '1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label">{t.usernameLabel}</label>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  className="input-field"
                  style={{ paddingLeft: '2.5rem' }}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="watchman1"
                />
                <User size={18} color="#94A3B8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
              </div>
            </div>

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="form-label">{t.passwordLabel}</label>
                <button
                  type="button"
                  onClick={() => {
                    setForgotStep(1);
                    setForgotEmail(username);
                    setForgotMessage('');
                    setShowForgotModal(true);
                  }}
                  style={{
                    background: 'none',
                    color: '#2563EB',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    textDecoration: 'none'
                  }}
                >
                  {t.forgotPassword}
                </button>
              </div>
              <div style={{ position: 'relative' }}>
                <input
                  type="password"
                  className="input-field"
                  style={{ paddingLeft: '2.5rem' }}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                />
                <Lock size={18} color="#94A3B8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary btn-lg"
              style={{ width: '100%', marginTop: '0.75rem', fontWeight: 800 }}
            >
              {loading ? (language === 'ta' ? 'சரிபார்க்கிறது...' : 'Authenticating...') : (
                <>
                  <span>{t.btnSignIn}</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Credentials & Portal URL indicator */}
          <div style={{
            marginTop: '1.25rem',
            paddingTop: '1rem',
            borderTop: '1px solid #E2E8F0',
            fontSize: '0.78rem',
            color: '#64748B'
          }}>
            {selectedRole === 'ADMIN' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, color: '#334155' }}>
                    {language === 'ta' ? 'நிர்வாக உள்நுழைவு விபரம்:' : 'Administrator Credentials:'}
                  </span>
                  <span style={{ fontFamily: 'monospace', fontWeight: 800, color: '#0F172A', backgroundColor: '#F1F5F9', padding: '2px 8px', borderRadius: '4px' }}>
                    admin / password123
                  </span>
                </div>
                <div style={{ fontSize: '0.74rem', color: '#64748B' }}>
                  🔒 {language === 'ta' ? 'இந்த தளம் கல்லூரி நிர்வாகிகளுக்கு மட்டுமே.' : 'This URL is strictly reserved for Campus Directors & Principals.'}
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700, color: '#334155' }}>
                    {language === 'ta' ? 'வாட்ச்மேன் உள்நுழைவு விபரம்:' : 'Security Guard Credentials:'}
                  </span>
                  <span style={{ fontFamily: 'monospace', fontWeight: 800, color: '#1D4ED8', backgroundColor: '#EFF6FF', padding: '2px 8px', borderRadius: '4px' }}>
                    watchman1 / password123
                  </span>
                </div>
                <div style={{ fontSize: '0.74rem', color: '#64748B' }}>
                  🛡️ {language === 'ta' ? 'மெயின் கேட் பாதுகாப்பு பணிகளுக்கான தளம்.' : 'Dedicated station for Gate Barrier, Vehicle OCR & Visitor Logs.'}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Forgot Password Interactive Modal */}
      {showForgotModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 100,
          padding: '1.5rem'
        }}>
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '20px',
            maxWidth: '460px',
            width: '100%',
            padding: '2rem',
            boxShadow: 'var(--shadow-xl)',
            border: '1px solid #DBEAFE',
            animation: 'fadeIn 0.2s ease'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                backgroundColor: '#EFF6FF',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#2563EB'
              }}>
                <KeyRound size={22} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0F172A' }}>
                  {t.resetPasswordTitle}
                </h3>
                <p style={{ fontSize: '0.78rem', color: '#64748B' }}>
                  {t.resetPasswordSubtitle} • Step {forgotStep} of 3
                </p>
              </div>
            </div>

            {forgotMessage && (
              <div style={{
                padding: '0.65rem',
                borderRadius: '8px',
                backgroundColor: '#EFF6FF',
                color: '#1E40AF',
                fontSize: '0.8rem',
                marginBottom: '1rem',
                border: '1px solid #BFDBFE'
              }}>
                {forgotMessage}
              </div>
            )}

            {/* Step 1: Input Contact / Guard ID */}
            {forgotStep === 1 && (
              <form onSubmit={handleRequestOtp}>
                <div className="form-group">
                  <label className="form-label">{t.registeredContactLabel}</label>
                  <input
                    type="text"
                    required
                    className="input-field"
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    placeholder="watchman1 or 9876543210"
                  />
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
                  <button
                    type="button"
                    onClick={() => setShowForgotModal(false)}
                    className="btn btn-secondary"
                    style={{ flex: 1 }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={forgotLoading}
                    className="btn btn-primary"
                    style={{ flex: 1.5 }}
                  >
                    {forgotLoading ? 'Sending...' : t.btnSendOtp}
                  </button>
                </div>
              </form>
            )}

            {/* Step 2: Enter 6-digit OTP */}
            {forgotStep === 2 && (
              <form onSubmit={handleVerifyOtp}>
                <div style={{
                  backgroundColor: '#ECFDF5',
                  border: '1px solid #A7F3D0',
                  padding: '0.75rem',
                  borderRadius: '10px',
                  marginBottom: '1rem',
                  fontSize: '0.825rem',
                  color: '#065F46'
                }}>
                  ✅ Demo 6-Digit OTP: <strong>{generatedOtp}</strong>
                </div>
                <div className="form-group">
                  <label className="form-label">Enter 6-Digit OTP Code</label>
                  <input
                    type="text"
                    maxLength={6}
                    required
                    className="input-field"
                    style={{ letterSpacing: '0.3em', textAlign: 'center', fontSize: '1.2rem', fontWeight: 800 }}
                    value={enteredOtp}
                    onChange={(e) => setEnteredOtp(e.target.value)}
                    placeholder="• • • • • •"
                  />
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
                  <button
                    type="button"
                    onClick={() => setForgotStep(1)}
                    className="btn btn-secondary"
                    style={{ flex: 1 }}
                  >
                    Back
                  </button>
                  <button type="submit" className="btn btn-primary" style={{ flex: 1.5 }}>
                    {t.btnVerifyOtp}
                  </button>
                </div>
              </form>
            )}

            {/* Step 3: Enter New Password */}
            {forgotStep === 3 && (
              <form onSubmit={handleResetPassword}>
                <div className="form-group">
                  <label className="form-label">Create New Password</label>
                  <input
                    type="password"
                    required
                    className="input-field"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Minimum 6 characters"
                  />
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
                  <button
                    type="button"
                    onClick={() => setForgotStep(2)}
                    className="btn btn-secondary"
                    style={{ flex: 1 }}
                  >
                    Back
                  </button>
                  <button
                    type="submit"
                    disabled={forgotLoading}
                    className="btn btn-primary"
                    style={{ flex: 1.5 }}
                  >
                    {forgotLoading ? 'Updating...' : t.btnSavePassword}
                  </button>
                </div>
              </form>
            )}

            {/* Step 4: Success confirmation */}
            {forgotStep === 4 && (
              <div style={{ textAlign: 'center', padding: '1rem 0' }}>
                <CheckCircle size={52} color="#10B981" style={{ margin: '0 auto 1rem' }} />
                <h4 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A', marginBottom: '0.5rem' }}>
                  {language === 'ta' ? 'கடவுச்சொல் வெற்றிகரமாக மாற்றப்பட்டது!' : 'Password Reset Successfully!'}
                </h4>
                <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: '1.5rem' }}>
                  {language === 'ta' ? 'புதிய கடவுச்சொல்லை பயன்படுத்தி வாட்ச்மேன் போர்ட்டலில் உள்நுழையலாம்.' : 'You can now sign in to the Watchman portal with your new password.'}
                </p>
                <button
                  onClick={() => setShowForgotModal(false)}
                  className="btn btn-primary"
                  style={{ width: '100%' }}
                >
                  {t.btnReturnLogin}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
