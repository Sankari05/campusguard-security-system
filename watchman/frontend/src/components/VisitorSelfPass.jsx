import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { RealQRCode } from './RealQRCode';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { parseSpokenVisitorPass, extractPhoneNumber, extractIdentifier } from '../utils/voicePassParser';
import {
  QrCode,
  User,
  GraduationCap,
  Briefcase,
  Users,
  Building,
  CheckCircle2,
  Clock,
  ShieldCheck,
  AlertTriangle,
  Copy,
  Check,
  ArrowRight,
  RotateCcw,
  Sparkles,
  Phone,
  FileText,
  Mic,
  MicOff,
  Globe,
  Volume2
} from 'lucide-react';

export const VisitorSelfPass = ({ onQuickFillOtp, onClose, onBackToPoster }) => {
  const [visitorType, setVisitorType] = useState('STUDENT'); // STUDENT, STAFF, PARENT, OTHERS
  
  // Form fields
  const [name, setName] = useState('');
  const [identifier, setIdentifier] = useState(''); // Roll No or Staff ID or Student Name/Roll
  const [phoneNumber, setPhoneNumber] = useState('');
  const [department, setDepartment] = useState('Computer Science (B.Tech)');
  const [reason, setReason] = useState('Missed College Bus (Traffic Delay)');
  const [customReason, setCustomReason] = useState('');
  const [personToMeet, setPersonToMeet] = useState('');
  const [additionalDetails, setAdditionalDetails] = useState('');

  // Voice Dictation & Multi-Language State
  const [selectedLanguage, setSelectedLanguage] = useState('ta-IN'); // 'ta-IN', 'en-IN', 'tanglish'
  const [activeVoiceTarget, setActiveVoiceTarget] = useState(null); // 'GLOBAL' or field name
  const [liveTranscript, setLiveTranscript] = useState('');
  const [voiceNotification, setVoiceNotification] = useState(null);
  const [highlightField, setHighlightField] = useState(null);

  const {
    isSupported: speechSupported,
    isListening,
    startListening,
    stopListening
  } = useSpeechRecognition();

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [generatedPass, setGeneratedPass] = useState(null);
  const [copied, setCopied] = useState(false);
  const [timeLeft, setTimeLeft] = useState(15 * 60); // 15 minutes in seconds

  // Timer countdown
  useEffect(() => {
    if (!generatedPass) return;
    const interval = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [generatedPass]);

  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const departmentsList = [
    'Computer Science (B.Tech)',
    'Information Technology (B.Tech)',
    'Mechanical Engineering',
    'Electronics & Comm (ECE)',
    'Electrical & Electronics (EEE)',
    'Civil Engineering',
    'Artificial Intelligence & Data Science',
    'Management Studies (MBA)',
    'Administration / Principal Office'
  ];

  const studentReasons = [
    'Missed College Bus (Traffic Delay)',
    'Medical Clinic / Hospital Visit',
    'Special Project / Lab Work',
    'Train / Public Transit Delay',
    'Family Emergency / Personal Reason',
    'Other (Specify below)'
  ];

  const staffReasons = [
    'Official Department Meeting',
    'Guest Lecture / Visiting Faculty',
    'University Exam Valuation Duty',
    'Research Lab Supervision',
    'Other (Specify below)'
  ];

  const parentPurposes = [
    'Meeting Principal / HOD Regarding Academic Progress',
    'Tuition Fee & Scholarship Payment Desk',
    'Hostel Warden Meeting / Leave Formalities',
    'Original Certificates Submission / Verification',
    'Other (Specify below)'
  ];

  const othersPurposes = [
    'Vendor / Lab Equipment Delivery',
    'Placement Recruiter & Campus Drive',
    'Campus Facility Maintenance & Repairs',
    'Student Admission Enquiry',
    'Guest Speaker / Dignitary Visit',
    'Other (Specify below)'
  ];

  // Global Voice Dictation Handler
  const handleStartGlobalVoice = () => {
    if (isListening && activeVoiceTarget === 'GLOBAL') {
      stopListening();
      setActiveVoiceTarget(null);
      return;
    }

    setActiveVoiceTarget('GLOBAL');
    setLiveTranscript('');
    setVoiceNotification(null);

    // ta-IN recognizes Tamil & Tanglish; en-IN recognizes English & Indian phonetics
    const speechLang = selectedLanguage === 'en-IN' ? 'en-IN' : 'ta-IN';

    startListening({
      lang: speechLang,
      continuous: false,
      onResult: (text, isFinal) => {
        setLiveTranscript(text);
        if (isFinal) {
          processGlobalVoiceTranscript(text);
        }
      },
      onError: (err) => {
        setVoiceNotification({ type: 'error', message: err });
        setActiveVoiceTarget(null);
      },
      onEnd: () => {
        setActiveVoiceTarget(null);
      }
    });
  };

  const processGlobalVoiceTranscript = (text) => {
    const parsed = parseSpokenVisitorPass(text, visitorType);
    let filledCount = 0;
    const filledNames = [];

    if (parsed.visitorType && parsed.visitorType !== visitorType) {
      setVisitorType(parsed.visitorType);
      if (parsed.visitorType === 'STUDENT') setReason(studentReasons[0]);
      if (parsed.visitorType === 'STAFF') setReason(staffReasons[0]);
      if (parsed.visitorType === 'PARENT') setReason(parentPurposes[0]);
      if (parsed.visitorType === 'OTHERS') setReason(othersPurposes[0]);
      filledNames.push('Visitor Type');
      filledCount++;
    }

    if (parsed.name) {
      setName(parsed.name);
      filledNames.push('Name');
      filledCount++;
    }

    if (parsed.phoneNumber) {
      setPhoneNumber(parsed.phoneNumber);
      filledNames.push('Phone');
      filledCount++;
    }

    if (parsed.identifier) {
      setIdentifier(parsed.identifier);
      filledNames.push('Roll/ID');
      filledCount++;
    }

    if (parsed.department) {
      setDepartment(parsed.department);
      filledNames.push('Department');
      filledCount++;
    }

    if (parsed.reason) {
      setReason(parsed.reason);
      filledNames.push('Reason');
      filledCount++;
    }

    if (parsed.personToMeet) {
      setPersonToMeet(parsed.personToMeet);
      filledNames.push('Whom to Meet');
      filledCount++;
    }

    if (filledCount > 0) {
      setVoiceNotification({
        type: 'success',
        message: `✨ Spoken data auto-filled: ${filledNames.join(', ')}!`
      });
      setHighlightField('all');
      setTimeout(() => setHighlightField(null), 2500);
    } else {
      if (!name) {
        setName(text);
      } else if (!additionalDetails) {
        setAdditionalDetails(text);
      }
      setVoiceNotification({
        type: 'info',
        message: `🎙️ Heard: "${text}"`
      });
    }
  };

  // Field-Specific Voice Dictation Handler
  const handleToggleFieldMic = (fieldName) => {
    if (isListening && activeVoiceTarget === fieldName) {
      stopListening();
      setActiveVoiceTarget(null);
      return;
    }

    setActiveVoiceTarget(fieldName);
    setLiveTranscript('');
    const speechLang = selectedLanguage === 'en-IN' ? 'en-IN' : 'ta-IN';

    startListening({
      lang: speechLang,
      continuous: false,
      onResult: (text, isFinal) => {
        setLiveTranscript(text);
        if (isFinal) {
          applyFieldVoice(fieldName, text);
        }
      },
      onError: (err) => {
        setVoiceNotification({ type: 'error', message: err });
        setActiveVoiceTarget(null);
      },
      onEnd: () => {
        setActiveVoiceTarget(null);
      }
    });
  };

  const applyFieldVoice = (fieldName, text) => {
    if (fieldName === 'name') {
      const clean = text.replace(/^(my name is|name is|en peyar|en peru|என் பெயர்|நான்)\s+/i, '').trim();
      const cap = clean.replace(/\b\w/g, (c) => c.toUpperCase());
      setName(cap || text);
    } else if (fieldName === 'phoneNumber') {
      const num = extractPhoneNumber(text) || text.replace(/\D/g, '');
      setPhoneNumber(num);
    } else if (fieldName === 'identifier') {
      const id = extractIdentifier(text) || text.toUpperCase().replace(/\s+/g, '');
      setIdentifier(id);
    } else if (fieldName === 'personToMeet') {
      setPersonToMeet(text.replace(/\b\w/g, (c) => c.toUpperCase()));
    } else if (fieldName === 'customReason') {
      setCustomReason(text);
    } else if (fieldName === 'additionalDetails') {
      setAdditionalDetails(text);
    }

    setHighlightField(fieldName);
    setTimeout(() => setHighlightField(null), 2000);
    setVoiceNotification({
      type: 'success',
      message: `✨ Voice input saved: "${text}"`
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    if (isSubmitting) return;

    setIsSubmitting(true);
    try {
      const finalReason = reason === 'Other (Specify below)' ? customReason : reason;

      const payload = {
        visitorType,
        visitorName: name.trim(),
        identifier: identifier.trim(),
        phoneNumber: phoneNumber.trim(),
        department: visitorType === 'OTHERS' ? (department || 'Campus Security') : department,
        reason: finalReason,
        personToMeet: visitorType === 'OTHERS' ? personToMeet : '',
        additionalDetails: additionalDetails.trim()
      };

      const res = await api.selfRegisterVisitor(payload);
      if (res.success) {
        setGeneratedPass(res.visitorPass || res);
        setTimeLeft(15 * 60);
      }
    } catch (err) {
      console.error('Registration error:', err);
      alert('Error generating pass. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopyOtp = (otp) => {
    navigator.clipboard?.writeText(otp);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleReset = () => {
    setGeneratedPass(null);
    setName('');
    setIdentifier('');
    setPhoneNumber('');
    setCustomReason('');
    setAdditionalDetails('');
    setPersonToMeet('');
    setVoiceNotification(null);
  };

  // Helper to render inline Mic button inside text inputs
  const renderMicButton = (fieldName) => {
    const isTarget = activeVoiceTarget === fieldName;
    return (
      <button
        type="button"
        onClick={() => handleToggleFieldMic(fieldName)}
        title="Click to speak (பேசி நிரப்பவும்)"
        style={{
          position: 'absolute',
          right: '8px',
          top: '50%',
          transform: 'translateY(-50%)',
          background: isTarget ? '#EF4444' : '#F1F5F9',
          border: isTarget ? '1px solid #DC2626' : '1px solid #CBD5E1',
          borderRadius: '8px',
          width: '32px',
          height: '32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          color: isTarget ? '#ffffff' : '#475569',
          transition: 'all 0.2s ease',
          boxShadow: isTarget ? '0 0 12px rgba(239, 68, 68, 0.6)' : 'none',
          zIndex: 2
        }}
      >
        <Mic size={15} className={isTarget ? 'animate-pulse' : ''} />
      </button>
    );
  };

  return (
    <div style={{
      maxWidth: '580px',
      margin: '0 auto',
      backgroundColor: '#ffffff',
      borderRadius: '24px',
      boxShadow: '0 20px 40px -15px rgba(15, 23, 42, 0.15), 0 0 0 1px rgba(15, 23, 42, 0.05)',
      overflow: 'hidden',
      border: '1px solid #E2E8F0'
    }}>
      {/* Mobile Header Banner */}
      <div style={{
        background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)',
        padding: '1.25rem 1.5rem',
        color: '#ffffff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '12px',
            backgroundColor: '#2563EB',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 8px 16px -4px rgba(37, 99, 235, 0.5)'
          }}>
            <QrCode size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{
                fontSize: '0.68rem',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                fontWeight: 800,
                color: '#60A5FA',
                backgroundColor: 'rgba(37, 99, 235, 0.2)',
                padding: '2px 8px',
                borderRadius: '999px'
              }}>
                Main Gate Self-Pass
              </span>
            </div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 800, margin: '2px 0 0 0', letterSpacing: '-0.01em' }}>
              College Gate Self-Service Pass
            </h2>
          </div>
        </div>

        {onBackToPoster && (
          <button
            type="button"
            onClick={onBackToPoster}
            style={{
              background: 'rgba(255, 255, 255, 0.12)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: '8px',
              padding: '6px 12px',
              color: '#93C5FD',
              fontSize: '0.8rem',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            Gate Poster
          </button>
        )}
      </div>

      {/* BODY CONTENT */}
      <div style={{ padding: '1.5rem' }}>

        {!generatedPass ? (
          <div>
            {/* VOICE ASSISTANT & MULTI-LANGUAGE SECTION (Tamil, English, Tanglish) */}
            <div style={{
              backgroundColor: '#F8FAFC',
              border: '1.5px solid #CBD5E1',
              borderRadius: '18px',
              padding: '1.1rem',
              marginBottom: '1.35rem',
              boxShadow: '0 4px 12px rgba(15, 23, 42, 0.03)'
            }}>
              {/* Language Selection Bar */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', fontWeight: 800, color: '#334155' }}>
                  <Globe size={15} color="#2563EB" />
                  <span>Language / மொழி:</span>
                </div>
                <div style={{ display: 'inline-flex', backgroundColor: '#E2E8F0', borderRadius: '10px', padding: '3px' }}>
                  {[
                    { id: 'ta-IN', label: 'தமிழ்' },
                    { id: 'en-IN', label: 'English' },
                    { id: 'tanglish', label: 'Tanglish (தமிழ்+Eng)' }
                  ].map((lang) => (
                    <button
                      key={lang.id}
                      type="button"
                      onClick={() => setSelectedLanguage(lang.id)}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '7px',
                        border: 'none',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        backgroundColor: selectedLanguage === lang.id ? '#2563EB' : 'transparent',
                        color: selectedLanguage === lang.id ? '#ffffff' : '#475569',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      {lang.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Main Glowing Mic Dictate Button */}
              <button
                type="button"
                onClick={handleStartGlobalVoice}
                style={{
                  width: '100%',
                  padding: '0.85rem 1.25rem',
                  borderRadius: '14px',
                  border: isListening && activeVoiceTarget === 'GLOBAL' ? '2px solid #DC2626' : '1.5px solid #2563EB',
                  backgroundColor: isListening && activeVoiceTarget === 'GLOBAL' ? '#FEF2F2' : '#EFF6FF',
                  color: isListening && activeVoiceTarget === 'GLOBAL' ? '#DC2626' : '#1D4ED8',
                  fontSize: '0.92rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  boxShadow: isListening && activeVoiceTarget === 'GLOBAL'
                    ? '0 0 16px rgba(220, 38, 38, 0.4)'
                    : '0 4px 12px rgba(37, 99, 235, 0.12)',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  backgroundColor: isListening && activeVoiceTarget === 'GLOBAL' ? '#DC2626' : '#2563EB',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <Mic size={16} className={isListening && activeVoiceTarget === 'GLOBAL' ? 'animate-pulse' : ''} />
                </div>
                <span>
                  {isListening && activeVoiceTarget === 'GLOBAL'
                    ? '🔴 Listening... (பேசுங்கள், நிறுத்த மீண்டும் அழுத்தவும்)'
                    : '🎙️ Voice Auto-Fill (பேசி தானாக நிரப்பவும்)'}
                </span>
              </button>

              {/* Helper speech example phrase based on selected language */}
              <div style={{ marginTop: '0.6rem', fontSize: '0.74rem', color: '#64748B', lineHeight: '1.4' }}>
                {selectedLanguage === 'ta-IN' && (
                  <span>உதாரணம்: <em>"என் பெயர் கார்த்திக், போன் 9876543210, கம்ப்யூட்டர் சயின்ஸ், பேருந்து தாமதம்"</em></span>
                )}
                {selectedLanguage === 'en-IN' && (
                  <span>Example: <em>"My name is Ramesh Kumar, phone 9840123456, CSE dept, missed bus"</em></span>
                )}
                {selectedLanguage === 'tanglish' && (
                  <span>Example: <em>"En peru Karthik, phone 9840123456, roll 22CS101, bus miss aayiduchu"</em></span>
                )}
              </div>

              {/* Live transcript or notification banner */}
              {liveTranscript && (
                <div style={{
                  marginTop: '0.65rem',
                  backgroundColor: '#FFFFFF',
                  borderRadius: '10px',
                  padding: '6px 12px',
                  border: '1px solid #BFDBFE',
                  fontSize: '0.8rem',
                  color: '#1E293B',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  <Volume2 size={15} color="#2563EB" />
                  <span>"{liveTranscript}"</span>
                </div>
              )}

              {voiceNotification && (
                <div style={{
                  marginTop: '0.65rem',
                  backgroundColor: voiceNotification.type === 'error' ? '#FEF2F2' : '#F0FDF4',
                  border: voiceNotification.type === 'error' ? '1px solid #FECACA' : '1px solid #BBF7D0',
                  borderRadius: '10px',
                  padding: '6px 12px',
                  fontSize: '0.8rem',
                  color: voiceNotification.type === 'error' ? '#DC2626' : '#166534',
                  fontWeight: 700
                }}>
                  {voiceNotification.message}
                </div>
              )}
            </div>

            {/* Step 2: Role Selector */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{
                display: 'block',
                fontSize: '0.8rem',
                fontWeight: 800,
                color: '#475569',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: '0.6rem'
              }}>
                STEP 2: Select Visitor Type (யார் வருகிறீர்கள்?)
              </label>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
                {[
                  { id: 'STUDENT', label: 'Student', sub: 'மாணவர்', icon: GraduationCap, color: '#2563EB' },
                  { id: 'STAFF', label: 'Staff', sub: 'பணியாளர்', icon: Briefcase, color: '#0D9488' },
                  { id: 'PARENT', label: 'Parent', sub: 'பெற்றோர்', icon: Users, color: '#D97706' },
                  { id: 'OTHERS', label: 'Others', sub: 'இதர நபர்கள்', icon: Building, color: '#7C3AED' }
                ].map((item) => {
                  const Icon = item.icon;
                  const isSelected = visitorType === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        setVisitorType(item.id);
                        if (item.id === 'STUDENT') setReason(studentReasons[0]);
                        if (item.id === 'STAFF') setReason(staffReasons[0]);
                        if (item.id === 'PARENT') setReason(parentPurposes[0]);
                        if (item.id === 'OTHERS') setReason(othersPurposes[0]);
                      }}
                      style={{
                        padding: '0.75rem 0.4rem',
                        borderRadius: '12px',
                        border: isSelected ? `2px solid ${item.color}` : '1.5px solid #E2E8F0',
                        backgroundColor: isSelected ? `${item.color}0D` : '#F8FAFC',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '0.3rem',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                    >
                      <div style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '8px',
                        backgroundColor: isSelected ? item.color : '#E2E8F0',
                        color: isSelected ? '#ffffff' : '#64748B',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        <Icon size={18} />
                      </div>
                      <span style={{
                        fontSize: '0.82rem',
                        fontWeight: 700,
                        color: isSelected ? item.color : '#1E293B'
                      }}>
                        {item.label}
                      </span>
                      <span style={{ fontSize: '0.68rem', color: '#64748B' }}>
                        {item.sub}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Step 3: Dynamic Form with Voice & Typing support */}
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
              <div style={{
                fontSize: '0.8rem',
                fontWeight: 800,
                color: '#475569',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                borderBottom: '1px solid #E2E8F0',
                paddingBottom: '0.4rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span>STEP 3: Fill Details ({visitorType})</span>
                <span style={{ fontSize: '0.72rem', color: '#64748B', textTransform: 'none', fontWeight: 600 }}>
                  ⌨️ Type or 🎙️ Speak into field mic
                </span>
              </div>

              {/* STUDENT FIELDS */}
              {visitorType === 'STUDENT' && (
                <>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Student Full Name / மாணவர் பெயர் <span style={{ color: '#EF4444' }}>*</span>
                    </label>
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <input
                        type="text"
                        required
                        className="input-field"
                        placeholder="e.g. Karthik Subramanian"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        style={{
                          paddingRight: '44px',
                          borderColor: highlightField === 'all' || highlightField === 'name' ? '#2563EB' : undefined,
                          backgroundColor: highlightField === 'all' || highlightField === 'name' ? '#EFF6FF' : undefined
                        }}
                      />
                      {renderMicButton('name')}
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: '0.75rem' }}>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>
                        Student Roll No / பதிவு எண் <span style={{ color: '#EF4444' }}>*</span>
                      </label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="text"
                          required
                          className="input-field"
                          placeholder="e.g. 22CS101"
                          value={identifier}
                          onChange={(e) => setIdentifier(e.target.value)}
                          style={{
                            textTransform: 'uppercase',
                            fontWeight: 700,
                            letterSpacing: '0.05em',
                            paddingRight: '44px',
                            borderColor: highlightField === 'all' || highlightField === 'identifier' ? '#2563EB' : undefined,
                            backgroundColor: highlightField === 'all' || highlightField === 'identifier' ? '#EFF6FF' : undefined
                          }}
                        />
                        {renderMicButton('identifier')}
                      </div>
                    </div>

                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>
                        Phone / மொபைல் எண்
                      </label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="tel"
                          className="input-field"
                          placeholder="10-digit mobile"
                          value={phoneNumber}
                          onChange={(e) => setPhoneNumber(e.target.value)}
                          style={{
                            paddingRight: '44px',
                            borderColor: highlightField === 'all' || highlightField === 'phoneNumber' ? '#2563EB' : undefined,
                            backgroundColor: highlightField === 'all' || highlightField === 'phoneNumber' ? '#EFF6FF' : undefined
                          }}
                        />
                        {renderMicButton('phoneNumber')}
                      </div>
                    </div>
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Department / கல்லூரி துறை
                    </label>
                    <select
                      className="input-field"
                      value={department}
                      onChange={(e) => setDepartment(e.target.value)}
                    >
                      {departmentsList.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Late Arrival Reason / வருகை காரணம் <span style={{ color: '#EF4444' }}>*</span>
                    </label>
                    <select
                      className="input-field"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    >
                      {studentReasons.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  </div>

                  {reason === 'Other (Specify below)' && (
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>Specify Reason</label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="text"
                          required
                          className="input-field"
                          placeholder="Type late arrival reason..."
                          value={customReason}
                          onChange={(e) => setCustomReason(e.target.value)}
                          style={{ paddingRight: '44px' }}
                        />
                        {renderMicButton('customReason')}
                      </div>
                    </div>
                  )}

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Additional Details / கூடுதல் குறிப்புகள் <span style={{ color: '#94A3B8', fontWeight: 500 }}>(Optional)</span>
                    </label>
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <input
                        type="text"
                        className="input-field"
                        placeholder="e.g. Attending 2nd period OS Lab, permission given by tutor"
                        value={additionalDetails}
                        onChange={(e) => setAdditionalDetails(e.target.value)}
                        style={{ paddingRight: '44px' }}
                      />
                      {renderMicButton('additionalDetails')}
                    </div>
                  </div>
                </>
              )}

              {/* STAFF FIELDS */}
              {visitorType === 'STAFF' && (
                <>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Staff Full Name / பணியாளர் பெயர் <span style={{ color: '#EF4444' }}>*</span>
                    </label>
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <input
                        type="text"
                        required
                        className="input-field"
                        placeholder="e.g. Dr. R. Manivannan"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        style={{ paddingRight: '44px' }}
                      />
                      {renderMicButton('name')}
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>
                        Staff ID / அடையாள எண் <span style={{ color: '#EF4444' }}>*</span>
                      </label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="text"
                          required
                          className="input-field"
                          placeholder="e.g. STF-8821"
                          value={identifier}
                          onChange={(e) => setIdentifier(e.target.value)}
                          style={{ textTransform: 'uppercase', fontWeight: 700, paddingRight: '44px' }}
                        />
                        {renderMicButton('identifier')}
                      </div>
                    </div>

                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>Phone / அலைபேசி</label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="tel"
                          className="input-field"
                          placeholder="10-digit mobile"
                          value={phoneNumber}
                          onChange={(e) => setPhoneNumber(e.target.value)}
                          style={{ paddingRight: '44px' }}
                        />
                        {renderMicButton('phoneNumber')}
                      </div>
                    </div>
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>Department</label>
                    <select
                      className="input-field"
                      value={department}
                      onChange={(e) => setDepartment(e.target.value)}
                    >
                      {departmentsList.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Visit Reason / வருகை நோக்கம் <span style={{ color: '#EF4444' }}>*</span>
                    </label>
                    <select
                      className="input-field"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    >
                      {staffReasons.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  </div>

                  {reason === 'Other (Specify below)' && (
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>Specify Reason</label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="text"
                          required
                          className="input-field"
                          placeholder="Type visit reason..."
                          value={customReason}
                          onChange={(e) => setCustomReason(e.target.value)}
                          style={{ paddingRight: '44px' }}
                        />
                        {renderMicButton('customReason')}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* PARENT FIELDS */}
              {visitorType === 'PARENT' && (
                <>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Parent / Guardian Name (பெற்றோர் பெயர்) <span style={{ color: '#EF4444' }}>*</span>
                    </label>
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <input
                        type="text"
                        required
                        className="input-field"
                        placeholder="e.g. Senthil Nathan"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        style={{ paddingRight: '44px' }}
                      />
                      {renderMicButton('name')}
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '0.75rem' }}>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>
                        Mobile Number / போன் <span style={{ color: '#EF4444' }}>*</span>
                      </label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="tel"
                          required
                          className="input-field"
                          placeholder="10-digit mobile"
                          value={phoneNumber}
                          onChange={(e) => setPhoneNumber(e.target.value)}
                          style={{ paddingRight: '44px' }}
                        />
                        {renderMicButton('phoneNumber')}
                      </div>
                    </div>

                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>
                        Student Name & Roll <span style={{ color: '#EF4444' }}>*</span>
                      </label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="text"
                          required
                          className="input-field"
                          placeholder="e.g. Priya - 22CS102"
                          value={identifier}
                          onChange={(e) => setIdentifier(e.target.value)}
                          style={{ paddingRight: '44px' }}
                        />
                        {renderMicButton('identifier')}
                      </div>
                    </div>
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>Department</label>
                    <select
                      className="input-field"
                      value={department}
                      onChange={(e) => setDepartment(e.target.value)}
                    >
                      {departmentsList.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Visit Purpose / வருகை நோக்கம் <span style={{ color: '#EF4444' }}>*</span>
                    </label>
                    <select
                      className="input-field"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    >
                      {parentPurposes.map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>

                  {reason === 'Other (Specify below)' && (
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>Specify Purpose</label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="text"
                          required
                          className="input-field"
                          placeholder="Type visit purpose..."
                          value={customReason}
                          onChange={(e) => setCustomReason(e.target.value)}
                          style={{ paddingRight: '44px' }}
                        />
                        {renderMicButton('customReason')}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* OTHERS / VENDOR FIELDS */}
              {visitorType === 'OTHERS' && (
                <>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Visitor Name / Company (பெயர் / நிறுவனம்) <span style={{ color: '#EF4444' }}>*</span>
                    </label>
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <input
                        type="text"
                        required
                        className="input-field"
                        placeholder="e.g. Gopinath (Science Lab Vendor)"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        style={{ paddingRight: '44px' }}
                      />
                      {renderMicButton('name')}
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>
                        Mobile Number / போன் <span style={{ color: '#EF4444' }}>*</span>
                      </label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="tel"
                          required
                          className="input-field"
                          placeholder="10-digit mobile"
                          value={phoneNumber}
                          onChange={(e) => setPhoneNumber(e.target.value)}
                          style={{ paddingRight: '44px' }}
                        />
                        {renderMicButton('phoneNumber')}
                      </div>
                    </div>

                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>
                        Whom To Meet / யாரை பார்க்க <span style={{ color: '#EF4444' }}>*</span>
                      </label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="text"
                          required
                          className="input-field"
                          placeholder="e.g. Dr. Ramesh (Physics HOD)"
                          value={personToMeet}
                          onChange={(e) => setPersonToMeet(e.target.value)}
                          style={{ paddingRight: '44px' }}
                        />
                        {renderMicButton('personToMeet')}
                      </div>
                    </div>
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>Department / Building</label>
                    <input
                      type="text"
                      className="input-field"
                      placeholder="e.g. Science Block Lab 2"
                      value={department}
                      onChange={(e) => setDepartment(e.target.value)}
                    />
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label" style={{ fontWeight: 700 }}>
                      Visit Purpose / நோக்கம் <span style={{ color: '#EF4444' }}>*</span>
                    </label>
                    <select
                      className="input-field"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    >
                      {othersPurposes.map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>

                  {reason === 'Other (Specify below)' && (
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label" style={{ fontWeight: 700 }}>Specify Purpose</label>
                      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                        <input
                          type="text"
                          required
                          className="input-field"
                          placeholder="Type visit purpose..."
                          value={customReason}
                          onChange={(e) => setCustomReason(e.target.value)}
                          style={{ paddingRight: '44px' }}
                        />
                        {renderMicButton('customReason')}
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting}
                style={{
                  marginTop: '0.75rem',
                  padding: '0.9rem',
                  borderRadius: '12px',
                  backgroundColor: '#2563EB',
                  color: '#ffffff',
                  fontSize: '1rem',
                  fontWeight: 800,
                  border: 'none',
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.6rem',
                  boxShadow: '0 10px 20px -5px rgba(37, 99, 235, 0.4)'
                }}
              >
                {isSubmitting ? (
                  'Generating Gate Pass & OTP...'
                ) : (
                  <>
                    <span>STEP 4: Submit & Generate Gate Pass + OTP</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </form>
          </div>
        ) : (
          /* STEP 4 & 5: Digital Gate Pass + Scannable QR & OTP Screen */
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{
              backgroundColor: '#ECFDF5',
              border: '1.5px solid #10B981',
              borderRadius: '16px',
              padding: '1rem 1.25rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem'
            }}>
              <CheckCircle2 size={28} color="#059669" />
              <div>
                <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800, color: '#065F46' }}>
                  Step 3 & 4 — Gate Pass Generated & Sent to Guard Live!
                </h4>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.82rem', color: '#047857' }}>
                  Watchman screen updates automatically live. Show this pass QR or OTP to the gate officer.
                </p>
              </div>
            </div>

            {/* PASS BADGE CARD */}
            <div style={{
              background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)',
              borderRadius: '20px',
              padding: '1.5rem',
              color: '#ffffff',
              boxShadow: '0 20px 30px -10px rgba(15, 23, 42, 0.3)',
              position: 'relative',
              overflow: 'hidden'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
                <div>
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 800,
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                    color: '#93C5FD'
                  }}>
                    DIGITAL GATE PASS
                  </span>
                  <h3 style={{ margin: '2px 0 0 0', fontSize: '1.35rem', fontWeight: 900, color: '#F8FAFC' }}>
                    {generatedPass.passNumber || 'GP-2026-XXXX'}
                  </h3>
                </div>
                <span style={{
                  backgroundColor: generatedPass.visitorType === 'STUDENT' ? '#2563EB' :
                                   generatedPass.visitorType === 'STAFF' ? '#0D9488' :
                                   generatedPass.visitorType === 'PARENT' ? '#D97706' : '#7C3AED',
                  color: '#ffffff',
                  fontWeight: 800,
                  fontSize: '0.75rem',
                  padding: '4px 10px',
                  borderRadius: '999px',
                  textTransform: 'uppercase'
                }}>
                  {generatedPass.visitorType}
                </span>
              </div>

              {/* REAL SCANNABLE PASS QR CODE */}
              <div style={{
                display: 'flex',
                justifyContent: 'center',
                marginBottom: '1.25rem'
              }}>
                <div style={{
                  backgroundColor: '#ffffff',
                  padding: '12px',
                  borderRadius: '16px',
                  boxShadow: '0 10px 25px rgba(0,0,0,0.3)',
                  display: 'inline-flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '6px'
                }}>
                  <RealQRCode text={generatedPass.passNumber || `GP-${generatedPass.otp}`} size={160} />
                  <span style={{ fontSize: '0.7rem', fontWeight: 800, color: '#0F172A', letterSpacing: '0.04em' }}>
                    GATE SCANNER QR CODE
                  </span>
                </div>
              </div>

              {/* STEP 5: VISITOR SHOWS OTP TO WATCHMAN */}
              <div style={{
                backgroundColor: 'rgba(255, 255, 255, 0.07)',
                border: '1.5px dashed rgba(255, 255, 255, 0.25)',
                borderRadius: '16px',
                padding: '1.25rem',
                textAlign: 'center',
                marginBottom: '1.25rem',
                backdropFilter: 'blur(8px)'
              }}>
                <div style={{ fontSize: '0.78rem', color: '#94A3B8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Pass OTP (Guard Verification Code)
                </div>
                <div style={{
                  fontSize: '2.5rem',
                  fontWeight: 900,
                  letterSpacing: '0.25em',
                  color: '#38BDF8',
                  margin: '0.5rem 0',
                  fontFamily: 'monospace',
                  textShadow: '0 0 20px rgba(56, 189, 248, 0.5)'
                }}>
                  {generatedPass.otp}
                </div>

                {/* Expiry Countdown */}
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  fontSize: '0.8rem',
                  color: timeLeft > 120 ? '#FDE047' : '#F87171',
                  backgroundColor: 'rgba(0, 0, 0, 0.3)',
                  padding: '4px 12px',
                  borderRadius: '999px',
                  fontWeight: 700
                }}>
                  <Clock size={14} />
                  <span>Valid for: {formatTimer(timeLeft)}</span>
                </div>
              </div>

              {/* Quick Actions */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
                <button
                  type="button"
                  onClick={() => handleCopyOtp(generatedPass.otp)}
                  style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.12)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    color: '#ffffff',
                    padding: '0.6rem',
                    borderRadius: '10px',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.4rem'
                  }}
                >
                  {copied ? <Check size={16} color="#4ADE80" /> : <Copy size={16} />}
                  <span>{copied ? 'Copied OTP!' : 'Copy OTP'}</span>
                </button>

                {onQuickFillOtp && (
                  <button
                    type="button"
                    onClick={() => onQuickFillOtp(generatedPass.otp)}
                    style={{
                      backgroundColor: '#2563EB',
                      border: 'none',
                      color: '#ffffff',
                      padding: '0.6rem',
                      borderRadius: '10px',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.4rem',
                      boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)'
                    }}
                  >
                    <Sparkles size={16} />
                    <span>Quick-Fill to Guard</span>
                  </button>
                )}
              </div>

              {/* Pass Metadata List */}
              <div style={{
                marginTop: '1.25rem',
                borderTop: '1px solid rgba(255, 255, 255, 0.1)',
                paddingTop: '1rem',
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '0.75rem',
                fontSize: '0.82rem'
              }}>
                <div>
                  <div style={{ color: '#94A3B8', fontSize: '0.7rem' }}>Visitor Name</div>
                  <div style={{ fontWeight: 700, color: '#F1F5F9' }}>{generatedPass.visitorName}</div>
                </div>
                <div>
                  <div style={{ color: '#94A3B8', fontSize: '0.7rem' }}>Identifier</div>
                  <div style={{ fontWeight: 700, color: '#F1F5F9' }}>{generatedPass.identifier || 'N/A'}</div>
                </div>
                <div>
                  <div style={{ color: '#94A3B8', fontSize: '0.7rem' }}>Department</div>
                  <div style={{ fontWeight: 700, color: '#F1F5F9' }}>{generatedPass.department}</div>
                </div>
                <div>
                  <div style={{ color: '#94A3B8', fontSize: '0.7rem' }}>Reason / Purpose</div>
                  <div style={{ fontWeight: 700, color: '#F1F5F9' }}>{generatedPass.reason}</div>
                </div>
              </div>
            </div>

            {/* Back Button */}
            <button
              type="button"
              onClick={handleReset}
              style={{
                padding: '0.75rem',
                backgroundColor: '#F1F5F9',
                border: '1px solid #CBD5E1',
                borderRadius: '12px',
                color: '#475569',
                fontWeight: 700,
                fontSize: '0.88rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem'
              }}
            >
              <RotateCcw size={16} />
              <span>Submit Another Visitor Pass</span>
            </button>
          </div>
        )}

      </div>
    </div>
  );
};
