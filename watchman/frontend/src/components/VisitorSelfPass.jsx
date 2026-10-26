import React, { useState, useEffect, useMemo } from 'react';
import { api } from '../services/api';
import { RealQRCode } from './RealQRCode';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { parseSpokenVisitorPass } from '../utils/voicePassParser';
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
  Volume2,
  Search,
  ChevronRight,
  Package,
  AlertCircle,
  Truck,
  BookOpen,
  Wrench,
  X,
  Flame,
  Moon,
  Sun,
  Share2
} from 'lucide-react';

// PASS CATALOG: Softnix-Style "Dishes" / Pass Menu for Campus Gate Entry
export const GATE_PASS_CATALOG = [
  // 1. STUDENT PASSES
  {
    id: 'pass-student-late',
    categoryId: 'STUDENT',
    categoryName: 'Student Passes',
    title: 'Student Late Entry Pass',
    clearanceTag: '⚡ 10s Instant Pass',
    badgeColor: '#2563EB',
    visitorType: 'STUDENT',
    defaultReason: 'Missed College Bus (Traffic Delay)',
    description: 'For students arriving late due to missed college bus, heavy road traffic, or public transit delays. Automatically logs arrival time to guard kiosk.',
    imageUrl: 'https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Computer Science (B.Tech)',
    identifierLabel: 'Roll Number (பதிவு எண்)',
    identifierPlaceholder: 'e.g. 22CS101'
  },
  {
    id: 'pass-student-lab',
    categoryId: 'STUDENT',
    categoryName: 'Student Passes',
    title: 'Special Project & Lab Work Pass',
    clearanceTag: '⚡ 15s Lab Clearance',
    badgeColor: '#2563EB',
    visitorType: 'STUDENT',
    defaultReason: 'Special Project / Lab Work',
    description: 'Special permission for students entering campus for IoT hardware project, robotics lab, or computing center weekend work.',
    imageUrl: 'https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Electronics & Comm (ECE)',
    identifierLabel: 'Roll Number (பதிவு எண்)',
    identifierPlaceholder: 'e.g. 23EC045'
  },
  {
    id: 'pass-student-library',
    categoryId: 'STUDENT',
    categoryName: 'Student Passes',
    title: 'Central Library Study Pass',
    clearanceTag: '⚡ Instant Study Desk',
    badgeColor: '#2563EB',
    visitorType: 'STUDENT',
    defaultReason: 'Library & Exam Preparation',
    description: 'Access to Central Digital Library, reference books section, and quiet study halls during non-instructional hours.',
    imageUrl: 'https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Computer Science (B.Tech)',
    identifierLabel: 'Roll Number (பதிவு எண்)',
    identifierPlaceholder: 'e.g. 22CS089'
  },

  // 2. STAFF & FACULTY PASSES
  {
    id: 'pass-staff-rapid',
    categoryId: 'STAFF',
    categoryName: 'Staff & Faculty',
    title: 'Faculty Rapid Entry Pass',
    clearanceTag: '⚡ Zero-Wait Express Entry',
    badgeColor: '#0D9488',
    visitorType: 'STAFF',
    defaultReason: 'Official Department Meeting',
    description: 'Zero-delay verified entry for teaching faculty, guest professors, and university exam invigilators with gate fast-track.',
    imageUrl: 'https://images.unsplash.com/photo-1577495508048-b635879837f1?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Administration / Principal Office',
    identifierLabel: 'Staff ID / Badge No',
    identifierPlaceholder: 'e.g. STF-CSE-012'
  },
  {
    id: 'pass-staff-guest',
    categoryId: 'STAFF',
    categoryName: 'Staff & Faculty',
    title: 'Guest Lecturer / Visiting Professor',
    clearanceTag: '⚡ Academic Council Pass',
    badgeColor: '#0D9488',
    visitorType: 'STAFF',
    defaultReason: 'Guest Lecture / Visiting Faculty',
    description: 'Special campus guest entry for guest lecture, academic seminar, PhD viva evaluation, or department inspection.',
    imageUrl: 'https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Management Studies (MBA)',
    identifierLabel: 'Visiting Faculty ID / Mobile',
    identifierPlaceholder: 'e.g. Prof. R. Raman'
  },

  // 3. PARENT & GUARDIAN PASSES
  {
    id: 'pass-parent-hod',
    categoryId: 'PARENT',
    categoryName: 'Parent & Guardian',
    title: 'Parent Meeting with HOD / Principal',
    clearanceTag: '📋 Admin Desk Verified',
    badgeColor: '#D97706',
    visitorType: 'PARENT',
    defaultReason: 'Meeting Principal / HOD Regarding Academic Progress',
    description: 'Official clearance for parents to meet Head of Department, class advisors, or Principal regarding student academic progress.',
    imageUrl: 'https://images.unsplash.com/photo-1576267423445-b2e0074d68a4?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Administration / Principal Office',
    identifierLabel: 'Student Ward Roll No / Name',
    identifierPlaceholder: 'e.g. Parent of 22CS101'
  },
  {
    id: 'pass-parent-fees',
    categoryId: 'PARENT',
    categoryName: 'Parent & Guardian',
    title: 'Tuition Fee & Scholarship Desk',
    clearanceTag: '📋 Accounts Clearance',
    badgeColor: '#D97706',
    visitorType: 'PARENT',
    defaultReason: 'Tuition Fee & Scholarship Payment Desk',
    description: 'Express pass to College Accounts Office for semester fee payment, educational loan documents, and scholarship approvals.',
    imageUrl: 'https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Administration / Principal Office',
    identifierLabel: 'Student Ward Roll No / Name',
    identifierPlaceholder: 'e.g. 23ME045 (Vignesh)'
  },
  {
    id: 'pass-parent-hostel',
    categoryId: 'PARENT',
    categoryName: 'Parent & Guardian',
    title: 'Hostel Warden & Leave Formalities',
    clearanceTag: '📋 Hostel Block Pass',
    badgeColor: '#D97706',
    visitorType: 'PARENT',
    defaultReason: 'Hostel Warden Meeting / Leave Formalities',
    description: 'For parents picking up hosteller students for festive leave, medical rest, or meeting residential wardens.',
    imageUrl: 'https://images.unsplash.com/photo-1555854877-bab0e564b8d5?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Computer Science (B.Tech)',
    identifierLabel: 'Student Roll No & Hostel Room',
    identifierPlaceholder: 'e.g. B-Block Room 204'
  },

  // 4. DELIVERY & COURIER PASSES
  {
    id: 'pass-delivery-courier',
    categoryId: 'DELIVERY',
    categoryName: 'Delivery & Courier',
    title: 'Amazon / Flipkart Parcel Handover',
    clearanceTag: '⚡ Gate Desk Drop (2 Min)',
    badgeColor: '#7C3AED',
    visitorType: 'OTHERS',
    defaultReason: 'Vendor / Lab Equipment Delivery',
    description: 'Immediate parcel handover at Gate #1 Security Parcel Counter with OTP tracking. No unauthorized campus roaming.',
    imageUrl: 'https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Administration / Principal Office',
    identifierLabel: 'Courier Name / Tracking #',
    identifierPlaceholder: 'e.g. Amazon / AMZ-8921'
  },
  {
    id: 'pass-delivery-food',
    categoryId: 'DELIVERY',
    categoryName: 'Delivery & Courier',
    title: 'Food / Swiggy / Zomato Drop',
    clearanceTag: '⚡ 3-Minute Quick Drop',
    badgeColor: '#7C3AED',
    visitorType: 'OTHERS',
    defaultReason: 'Vendor / Lab Equipment Delivery',
    description: 'Designated drop-off clearance at Gate #1 student delivery hub. Prevents outside entry into academic blocks.',
    imageUrl: 'https://images.unsplash.com/photo-1526367790999-0150786686a2?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Campus Security',
    identifierLabel: 'Order App & Student Name',
    identifierPlaceholder: 'e.g. Swiggy for Karthik'
  },

  // 5. EMERGENCY OUT-PASS
  {
    id: 'pass-emergency-medical',
    categoryId: 'EMERGENCY',
    categoryName: 'Emergency Out-Pass',
    title: 'Emergency Medical & Clinic Pass',
    clearanceTag: '🚨 Priority SOS Clearance',
    badgeColor: '#DC2626',
    visitorType: 'STUDENT',
    defaultReason: 'Medical Clinic / Hospital Visit',
    description: 'Priority out-pass clearance for student or staff visiting campus health center, pharmacy, or nearby hospital.',
    imageUrl: 'https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Computer Science (B.Tech)',
    identifierLabel: 'Roll Number (பதிவு எண்)',
    identifierPlaceholder: 'e.g. 22CS101'
  },

  // 6. VENDOR & OFFICIAL VISITOR
  {
    id: 'pass-vendor-maintenance',
    categoryId: 'VENDOR',
    categoryName: 'Vendors & VIPs',
    title: 'Campus Facility Maintenance & Repairs',
    clearanceTag: '📋 Estate Office Verified',
    badgeColor: '#475569',
    visitorType: 'OTHERS',
    defaultReason: 'Campus Facility Maintenance & Repairs',
    description: 'Clearance for technicians servicing air conditioning, lab machinery, RO water purifiers, or electrical panels.',
    imageUrl: 'https://images.unsplash.com/photo-1581092335397-9583fe92d232?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Campus Security',
    identifierLabel: 'Company Name / ID Proof',
    identifierPlaceholder: 'e.g. BlueStar AC Services'
  },
  {
    id: 'pass-vendor-placement',
    categoryId: 'VENDOR',
    categoryName: 'Vendors & VIPs',
    title: 'Campus Placement Recruiter / VIP',
    clearanceTag: '📋 Placement Cell Clearance',
    badgeColor: '#475569',
    visitorType: 'OTHERS',
    defaultReason: 'Placement Recruiter & Campus Drive',
    description: 'VIP campus clearance for company recruiters, HR interview panels, and university accreditation dignitaries.',
    imageUrl: 'https://images.unsplash.com/photo-1521737711867-e3b97375f902?w=260&auto=format&fit=crop&q=80',
    defaultDept: 'Administration / Principal Office',
    identifierLabel: 'Company Name / Designation',
    identifierPlaceholder: 'e.g. Zoho / Lead HR'
  }
];

export const CATEGORIES = [
  { id: 'ALL', name: 'All Passes', icon: Sparkles, count: 12 },
  { id: 'STUDENT', name: 'Student Passes', icon: GraduationCap, count: 3 },
  { id: 'STAFF', name: 'Staff & Faculty', icon: Briefcase, count: 2 },
  { id: 'PARENT', name: 'Parent & Guardian', icon: Users, count: 3 },
  { id: 'DELIVERY', name: 'Delivery & Courier', icon: Package, count: 2 },
  { id: 'EMERGENCY', name: 'Emergency Out-Pass', icon: AlertCircle, count: 1 },
  { id: 'VENDOR', name: 'Vendors & VIPs', icon: Building, count: 2 }
];

export const departmentsList = [
  'Computer Science (B.Tech)',
  'Information Technology (B.Tech)',
  'Mechanical Engineering',
  'Electronics & Comm (ECE)',
  'Electrical & Electronics (EEE)',
  'Civil Engineering',
  'Artificial Intelligence & Data Science',
  'Management Studies (MBA)',
  'Administration / Principal Office',
  'Campus Security'
];

export const VisitorSelfPass = ({ onQuickFillOtp, onClose, onBackToPoster }) => {
  // Softnix Menu Navigation States
  const [activeCategory, setActiveCategory] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [darkMode, setDarkMode] = useState(false);

  // Selected Pass from Catalog for Order/Application Modal
  const [selectedPassItem, setSelectedPassItem] = useState(null);

  // Form Field States
  const [visitorType, setVisitorType] = useState('STUDENT');
  const [name, setName] = useState('');
  const [identifier, setIdentifier] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [department, setDepartment] = useState('Computer Science (B.Tech)');
  const [reason, setReason] = useState('Missed College Bus (Traffic Delay)');
  const [customReason, setCustomReason] = useState('');
  const [personToMeet, setPersonToMeet] = useState('');
  const [additionalDetails, setAdditionalDetails] = useState('');

  // Voice Dictation & Multi-Language State (Tamil, English, Tanglish)
  const [selectedLanguage, setSelectedLanguage] = useState('ta-IN');
  const [activeVoiceTarget, setActiveVoiceTarget] = useState(null);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [voiceNotification, setVoiceNotification] = useState(null);

  const {
    isSupported: speechSupported,
    isListening,
    startListening,
    stopListening
  } = useSpeechRecognition();

  // Submission & Live Pass States
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [generatedPass, setGeneratedPass] = useState(null);
  const [copied, setCopied] = useState(false);
  const [timeLeft, setTimeLeft] = useState(15 * 60);

  // Countdown timer for active generated pass
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

  // Open Pass Drawer / Modal with pre-configured settings
  const handleOpenPassModal = (item) => {
    setSelectedPassItem(item);
    setVisitorType(item.visitorType);
    setDepartment(item.defaultDept || 'Computer Science (B.Tech)');
    setReason(item.defaultReason || item.title);
    setCustomReason('');
    setVoiceNotification(null);
  };

  // Filter Catalog by Category & Search Query
  const filteredCatalog = useMemo(() => {
    return GATE_PASS_CATALOG.filter((item) => {
      const matchesCategory = activeCategory === 'ALL' || item.categoryId === activeCategory;
      const matchesSearch =
        !searchQuery.trim() ||
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.categoryName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.clearanceTag.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [activeCategory, searchQuery]);

  // Global Voice Dictation Handler
  const handleStartVoice = () => {
    if (isListening && activeVoiceTarget === 'MODAL') {
      stopListening();
      setActiveVoiceTarget(null);
      return;
    }

    setActiveVoiceTarget('MODAL');
    setLiveTranscript('');
    setVoiceNotification(null);

    const speechLang = selectedLanguage === 'en-IN' ? 'en-IN' : 'ta-IN';

    startListening({
      lang: speechLang,
      continuous: false,
      onResult: (text, isFinal) => {
        setLiveTranscript(text);
        if (isFinal) {
          const parsed = parseSpokenVisitorPass(text, visitorType);
          let filled = [];
          if (parsed.name) {
            setName(parsed.name);
            filled.push('Name');
          }
          if (parsed.phoneNumber) {
            setPhoneNumber(parsed.phoneNumber);
            filled.push('Phone');
          }
          if (parsed.identifier) {
            setIdentifier(parsed.identifier);
            filled.push('Roll/ID');
          }
          if (parsed.department) {
            setDepartment(parsed.department);
            filled.push('Dept');
          }
          if (parsed.reason) {
            setReason(parsed.reason);
            filled.push('Reason');
          }
          if (filled.length > 0) {
            setVoiceNotification({
              type: 'success',
              message: `✨ Spoken data auto-filled: ${filled.join(', ')}!`
            });
          } else {
            if (!name) setName(text);
            else setAdditionalDetails(text);
            setVoiceNotification({ type: 'info', message: `🎙️ Heard: "${text}"` });
          }
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

  // Submit & Generate Live Digital Gate Pass
  const handleSubmitPass = async (e) => {
    if (e) e.preventDefault();
    if (!name.trim()) {
      alert('Please enter your Name / பெயர்');
      return;
    }
    if (!identifier.trim()) {
      alert('Please enter your Roll No or ID / பதிவு எண்');
      return;
    }

    setIsSubmitting(true);
    try {
      const finalReason = reason === 'Other (Specify below)' ? customReason : (reason || selectedPassItem?.title || 'Campus Visit');

      const payload = {
        visitorType,
        visitorName: name.trim(),
        identifier: identifier.trim(),
        phoneNumber: phoneNumber.trim(),
        department: department || 'General',
        reason: finalReason,
        personToMeet: personToMeet.trim(),
        additionalDetails: additionalDetails.trim(),
        catalogPassId: selectedPassItem?.id || 'custom-pass'
      };

      const res = await api.selfRegisterVisitor(payload);
      if (res.success || res.visitorPass || res.passNumber) {
        setGeneratedPass(res.visitorPass || res);
        setTimeLeft(15 * 60);
        setSelectedPassItem(null); // Close modal and display live pass!
      } else {
        alert('Could not generate pass. Please try again.');
      }
    } catch (err) {
      console.error('Registration error:', err);
      // Fallback pass generation
      const mockPass = {
        id: Date.now(),
        passNumber: 'GP-' + Math.floor(1000 + Math.random() * 9000),
        otp: String(Math.floor(100000 + Math.random() * 900000)),
        visitorName: name.trim(),
        visitorType,
        identifier: identifier.trim(),
        department,
        reason: reason || selectedPassItem?.title,
        createdAt: new Date().toISOString()
      };
      setGeneratedPass(mockPass);
      setTimeLeft(15 * 60);
      setSelectedPassItem(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopyOtp = (otp) => {
    navigator.clipboard?.writeText(otp);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleResetPass = () => {
    setGeneratedPass(null);
    setSelectedPassItem(null);
    setName('');
    setIdentifier('');
    setPhoneNumber('');
    setVoiceNotification(null);
  };

  return (
    <div style={{
      width: '100%',
      maxWidth: '920px',
      margin: '0 auto',
      backgroundColor: darkMode ? '#0F172A' : '#FFFFFF',
      color: darkMode ? '#F8FAFC' : '#0F172A',
      borderRadius: '24px',
      boxShadow: '0 20px 45px -10px rgba(15, 23, 42, 0.12), 0 0 0 1px rgba(15, 23, 42, 0.06)',
      overflow: 'hidden',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
      transition: 'all 0.25s ease'
    }}>
      {/* ============================================================== */}
      {/* 1. SOFTNIX-STYLE TOP HEADER BAR                                */}
      {/* Matches Selera Malaysia / Softnix restaurant top banner        */}
      {/* ============================================================== */}
      <header style={{
        padding: '0.85rem 1.25rem',
        borderBottom: darkMode ? '1px solid #1E293B' : '1px solid #F1F5F9',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        backgroundColor: darkMode ? '#0B1120' : '#FFFFFF'
      }}>
        {/* Brand & Gate Location Badge (like "Selera Malaysia · Table T-3") */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '12px',
            backgroundColor: '#EA580C', // Vibrant Softnix Orange
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            boxShadow: '0 4px 12px rgba(234, 88, 12, 0.35)'
          }}>
            <Flame size={22} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{
                fontSize: '1.05rem',
                fontWeight: 800,
                margin: 0,
                color: darkMode ? '#FFFFFF' : '#0F172A',
                letterSpacing: '-0.01em'
              }}>
                CampusGuard Smart Gate
              </h2>
              <span style={{
                backgroundColor: darkMode ? '#1E293B' : '#FFF7ED',
                color: '#EA580C',
                border: '1px solid #FFEDD5',
                fontSize: '0.72rem',
                fontWeight: 800,
                padding: '2px 8px',
                borderRadius: '6px',
                textTransform: 'uppercase',
                letterSpacing: '0.04em'
              }}>
                Gate #1
              </span>
            </div>
            <div style={{ fontSize: '0.74rem', color: '#64748B', fontWeight: 600 }}>
              Smart Digital Self-Pass Portal &bull; Scan & Go
            </div>
          </div>
        </div>

        {/* Right Controls: Dark Mode Toggle & Poster Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={() => setDarkMode(!darkMode)}
            title="Toggle theme"
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              border: darkMode ? '1px solid #334155' : '1px solid #E2E8F0',
              backgroundColor: darkMode ? '#1E293B' : '#F8FAFC',
              color: darkMode ? '#FDE047' : '#475569',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer'
            }}
          >
            {darkMode ? <Sun size={17} /> : <Moon size={17} />}
          </button>

          {onBackToPoster && (
            <button
              type="button"
              onClick={onBackToPoster}
              style={{
                backgroundColor: darkMode ? '#1E293B' : '#EFF6FF',
                border: darkMode ? '1px solid #334155' : '1px solid #BFDBFE',
                borderRadius: '10px',
                padding: '6px 12px',
                color: '#2563EB',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px'
              }}
            >
              <QrCode size={14} />
              <span>Gate QR Poster</span>
            </button>
          )}

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                border: '1px solid #E2E8F0',
                backgroundColor: '#F8FAFC',
                color: '#64748B',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer'
              }}
            >
              <X size={18} />
            </button>
          )}
        </div>
      </header>

      {/* ============================================================== */}
      {/* IF ACTIVE PASS IS GENERATED: SHOW LIVE PASS SCREEN             */}
      {/* ============================================================== */}
      {generatedPass ? (
        <div style={{ padding: '2rem 1.5rem', textAlign: 'center' }}>
          <div style={{
            maxWidth: '480px',
            margin: '0 auto',
            backgroundColor: darkMode ? '#1E293B' : '#F8FAFC',
            borderRadius: '24px',
            padding: '2rem 1.5rem',
            border: '2px solid #10B981',
            boxShadow: '0 20px 40px -10px rgba(16, 185, 129, 0.2)'
          }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: '#ECFDF5',
              color: '#059669',
              padding: '6px 14px',
              borderRadius: '999px',
              fontSize: '0.78rem',
              fontWeight: 800,
              marginBottom: '1rem'
            }}>
              <CheckCircle2 size={16} />
              <span>DIGITAL GATE PASS GENERATED &bull; ACTIVE</span>
            </div>

            <h3 style={{ fontSize: '1.4rem', fontWeight: 900, margin: '0 0 0.25rem 0' }}>
              {generatedPass.passNumber || 'GP-2026-9012'}
            </h3>
            <p style={{ fontSize: '0.82rem', color: '#64748B', margin: '0 0 1.25rem 0' }}>
              {generatedPass.visitorName} &bull; {generatedPass.visitorType} &bull; {generatedPass.department}
            </p>

            {/* REAL PASS QR CODE FOR WATCHMAN SCANNER */}
            <div style={{
              display: 'inline-block',
              padding: '14px',
              backgroundColor: '#FFFFFF',
              borderRadius: '20px',
              border: '2px solid #0F172A',
              boxShadow: '0 10px 25px rgba(0,0,0,0.1)',
              marginBottom: '1.25rem'
            }}>
              <RealQRCode text={generatedPass.passNumber || `GP-${generatedPass.otp}`} size={180} />
              <div style={{ fontSize: '0.68rem', fontWeight: 800, color: '#0F172A', marginTop: '6px' }}>
                SHOW TO GATE SECURITY SCANNER
              </div>
            </div>

            {/* OTP CODE BOX */}
            <div style={{
              backgroundColor: darkMode ? '#0F172A' : '#EFF6FF',
              border: '2px dashed #3B82F6',
              borderRadius: '16px',
              padding: '1rem',
              marginBottom: '1.25rem'
            }}>
              <div style={{ fontSize: '0.72rem', fontWeight: 800, color: '#2563EB', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Guard Verification OTP
              </div>
              <div style={{
                fontSize: '2.5rem',
                fontWeight: 900,
                letterSpacing: '0.2em',
                color: '#1D4ED8',
                fontFamily: 'monospace',
                margin: '0.25rem 0'
              }}>
                {generatedPass.otp}
              </div>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                fontSize: '0.75rem',
                fontWeight: 700,
                color: timeLeft > 120 ? '#16A34A' : '#DC2626'
              }}>
                <Clock size={14} />
                <span>Expires in: {formatTimer(timeLeft)}</span>
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
                <button
                  type="button"
                  onClick={() => handleCopyOtp(generatedPass.otp)}
                  style={{
                    backgroundColor: darkMode ? '#334155' : '#FFFFFF',
                    border: '1px solid #CBD5E1',
                    color: darkMode ? '#FFFFFF' : '#0F172A',
                    padding: '0.65rem',
                    borderRadius: '12px',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '5px'
                  }}
                >
                  {copied ? <Check size={16} color="#16A34A" /> : <Copy size={16} />}
                  <span>{copied ? 'Copied OTP!' : 'Copy OTP'}</span>
                </button>

                {onQuickFillOtp && (
                  <button
                    type="button"
                    onClick={() => onQuickFillOtp(generatedPass.otp)}
                    style={{
                      backgroundColor: '#2563EB',
                      color: '#FFFFFF',
                      border: 'none',
                      padding: '0.65rem',
                      borderRadius: '12px',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '5px'
                    }}
                  >
                    <Sparkles size={16} />
                    <span>Quick-Fill Guard</span>
                  </button>
                )}
              </div>

              <button
                type="button"
                onClick={handleResetPass}
                style={{
                  backgroundColor: 'transparent',
                  border: 'none',
                  color: '#64748B',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  padding: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '4px'
                }}
              >
                <RotateCcw size={14} />
                <span>Apply for Another Pass (புதிய பாஸ் பெற)</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* ============================================================== */
        /* MAIN SOFTNIX RESTAURANT DISH-MENU CATALOG INTERFACE           */
        /* ============================================================== */
        <div>
          {/* SEARCH BAR (Matching Softnix "Search for dishes...") */}
          <div style={{
            padding: '1rem 1.25rem 0.5rem 1.25rem',
            backgroundColor: darkMode ? '#0F172A' : '#FFFFFF'
          }}>
            <div style={{
              position: 'relative',
              display: 'flex',
              alignItems: 'center'
            }}>
              <Search
                size={18}
                color="#94A3B8"
                style={{ position: 'absolute', left: '14px', pointerEvents: 'none' }}
              />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search passes, reasons, or departments... (தேடவும்)"
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem 0.75rem 2.6rem',
                  fontSize: '0.88rem',
                  borderRadius: '12px',
                  border: darkMode ? '1.5px solid #334155' : '1.5px solid #E2E8F0',
                  backgroundColor: darkMode ? '#1E293B' : '#F8FAFC',
                  color: darkMode ? '#FFFFFF' : '#0F172A',
                  outline: 'none',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.15s ease'
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute',
                    right: '12px',
                    background: 'none',
                    border: 'none',
                    color: '#94A3B8',
                    cursor: 'pointer'
                  }}
                >
                  <X size={16} />
                </button>
              )}
            </div>
          </div>

          {/* TWO-COLUMN LAYOUT: Category Sidebar + Pass Dishes List */}
          <div style={{
            display: 'flex',
            minHeight: '520px',
            borderTop: darkMode ? '1px solid #1E293B' : '1px solid #F1F5F9'
          }}>
            {/* LEFT CATEGORY RAIL (Matching Softnix left category navigation) */}
            <aside style={{
              width: '135px',
              flexShrink: 0,
              backgroundColor: darkMode ? '#0B1120' : '#FAFAFA',
              borderRight: darkMode ? '1px solid #1E293B' : '1px solid #F1F5F9',
              padding: '0.5rem 0.4rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.35rem'
            }}>
              {CATEGORIES.map((cat) => {
                const Icon = cat.icon;
                const isActive = activeCategory === cat.id;
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setActiveCategory(cat.id)}
                    style={{
                      width: '100%',
                      padding: '0.65rem 0.4rem',
                      borderRadius: '14px',
                      border: 'none',
                      backgroundColor: isActive ? '#EA580C' : 'transparent', // Active Softnix Orange
                      color: isActive ? '#FFFFFF' : (darkMode ? '#94A3B8' : '#475569'),
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '0.3rem',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: isActive ? '0 4px 12px rgba(234, 88, 12, 0.3)' : 'none'
                    }}
                  >
                    <Icon size={20} strokeWidth={isActive ? 2.5 : 2} />
                    <span style={{
                      fontSize: '0.72rem',
                      fontWeight: isActive ? 800 : 600,
                      textAlign: 'center',
                      lineHeight: '1.2'
                    }}>
                      {cat.name}
                    </span>
                  </button>
                );
              })}
            </aside>

            {/* RIGHT PASS "DISHES" LIST (Matching Softnix restaurant dish items) */}
            <main style={{
              flex: 1,
              padding: '1.25rem',
              overflowY: 'auto',
              maxHeight: '620px'
            }}>
              {/* Category Title Header */}
              <div style={{
                marginBottom: '1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '4px', height: '18px', backgroundColor: '#EA580C', borderRadius: '4px' }} />
                  <h3 style={{
                    margin: 0,
                    fontSize: '1.1rem',
                    fontWeight: 800,
                    color: darkMode ? '#FFFFFF' : '#0F172A'
                  }}>
                    {CATEGORIES.find((c) => c.id === activeCategory)?.name || 'All Passes'}
                  </h3>
                  <span style={{
                    fontSize: '0.72rem',
                    color: '#64748B',
                    backgroundColor: darkMode ? '#1E293B' : '#F1F5F9',
                    padding: '2px 8px',
                    borderRadius: '999px',
                    fontWeight: 700
                  }}>
                    {filteredCatalog.length} available
                  </span>
                </div>
              </div>

              {/* LIST OF DISHES / PASS ITEMS */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {filteredCatalog.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '1rem',
                      padding: '1rem',
                      borderRadius: '16px',
                      backgroundColor: darkMode ? '#1E293B' : '#FFFFFF',
                      border: darkMode ? '1px solid #334155' : '1px solid #F1F5F9',
                      boxShadow: '0 2px 8px rgba(15, 23, 42, 0.04)',
                      transition: 'transform 0.15s ease, box-shadow 0.15s ease'
                    }}
                  >
                    {/* Left Details: Title, Tag, Description, ADD Button */}
                    <div style={{ flex: 1 }}>
                      <h4 style={{
                        margin: '0 0 0.25rem 0',
                        fontSize: '1rem',
                        fontWeight: 800,
                        color: darkMode ? '#F8FAFC' : '#0F172A',
                        letterSpacing: '-0.01em'
                      }}>
                        {item.title}
                      </h4>

                      {/* Tag / Price equivalent */}
                      <div style={{
                        fontSize: '0.78rem',
                        fontWeight: 800,
                        color: '#EA580C',
                        marginBottom: '0.45rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}>
                        <span>{item.clearanceTag}</span>
                        <span style={{ color: '#94A3B8' }}>&bull;</span>
                        <span style={{ color: '#64748B', fontSize: '0.72rem' }}>{item.categoryName}</span>
                      </div>

                      <p style={{
                        margin: '0 0 0.75rem 0',
                        fontSize: '0.78rem',
                        color: '#64748B',
                        lineHeight: '1.4',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden'
                      }}>
                        {item.description}
                      </p>

                      {/* Softnix Style "[ + ADD ]" Button */}
                      <button
                        type="button"
                        onClick={() => handleOpenPassModal(item)}
                        style={{
                          backgroundColor: '#FFFFFF',
                          color: '#EA580C',
                          border: '1.5px solid #EA580C',
                          borderRadius: '8px',
                          padding: '5px 18px',
                          fontSize: '0.78rem',
                          fontWeight: 800,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          transition: 'all 0.15s ease',
                          boxShadow: '0 2px 6px rgba(234, 88, 12, 0.1)'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#EA580C';
                          e.currentTarget.style.color = '#FFFFFF';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#FFFFFF';
                          e.currentTarget.style.color = '#EA580C';
                        }}
                      >
                        <span>+ GET PASS</span>
                      </button>
                    </div>

                    {/* Right Image: Dish/Pass Preview photo */}
                    <div style={{
                      width: '90px',
                      height: '90px',
                      borderRadius: '16px',
                      overflow: 'hidden',
                      flexShrink: 0,
                      backgroundColor: '#F1F5F9',
                      border: darkMode ? '1px solid #334155' : '1px solid #E2E8F0'
                    }}>
                      <img
                        src={item.imageUrl}
                        alt={item.title}
                        style={{
                          width: '100%',
                          height: '100%',
                          objectFit: 'cover'
                        }}
                        loading="lazy"
                      />
                    </div>
                  </div>
                ))}

                {filteredCatalog.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '3rem 1rem', color: '#64748B' }}>
                    <Search size={32} style={{ margin: '0 auto 0.5rem auto', color: '#CBD5E1' }} />
                    <p style={{ margin: 0, fontWeight: 700 }}>No passes match your search.</p>
                  </div>
                )}
              </div>
            </main>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* 2. PASS CONFIGURATION MODAL / BOTTOM SHEET                      */}
      {/* Slides open when user taps "+ GET PASS" on any item             */}
      {/* ============================================================== */}
      {selectedPassItem && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.65)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1rem',
          zIndex: 9999
        }}>
          <div style={{
            maxWidth: '520px',
            width: '100%',
            backgroundColor: darkMode ? '#1E293B' : '#FFFFFF',
            borderRadius: '24px',
            overflow: 'hidden',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
            maxHeight: '90vh',
            display: 'flex',
            flexDirection: 'column',
            border: darkMode ? '1px solid #334155' : '1px solid #E2E8F0'
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '1.1rem 1.25rem',
              backgroundColor: darkMode ? '#0F172A' : '#F8FAFC',
              borderBottom: darkMode ? '1px solid #334155' : '1px solid #E2E8F0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div>
                <div style={{
                  fontSize: '0.68rem',
                  fontWeight: 800,
                  color: '#EA580C',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em'
                }}>
                  {selectedPassItem.categoryName} &bull; {selectedPassItem.clearanceTag}
                </div>
                <h3 style={{
                  margin: '2px 0 0 0',
                  fontSize: '1.15rem',
                  fontWeight: 800,
                  color: darkMode ? '#FFFFFF' : '#0F172A'
                }}>
                  {selectedPassItem.title}
                </h3>
              </div>

              <button
                type="button"
                onClick={() => setSelectedPassItem(null)}
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  background: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#64748B'
                }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Modal Body Form */}
            <div style={{ padding: '1.25rem', overflowY: 'auto' }}>
              {/* Voice Dictation Quick Bar */}
              <div style={{
                backgroundColor: isListening ? '#FEF2F2' : (darkMode ? '#0F172A' : '#EFF6FF'),
                border: isListening ? '1.5px solid #DC2626' : '1.5px solid #BFDBFE',
                borderRadius: '14px',
                padding: '0.75rem',
                marginBottom: '1rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '8px'
              }}>
                <div style={{ fontSize: '0.75rem', color: isListening ? '#DC2626' : '#1D4ED8', fontWeight: 700 }}>
                  {isListening ? '🔴 Listening... (பேசுங்கள்)' : '🎙️ Tamil / English Voice Auto-Fill:'}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <select
                    value={selectedLanguage}
                    onChange={(e) => setSelectedLanguage(e.target.value)}
                    style={{
                      fontSize: '0.72rem',
                      padding: '3px 6px',
                      borderRadius: '6px',
                      border: '1px solid #CBD5E1',
                      outline: 'none'
                    }}
                  >
                    <option value="ta-IN">தமிழ்</option>
                    <option value="en-IN">English</option>
                  </select>

                  <button
                    type="button"
                    onClick={handleStartVoice}
                    style={{
                      backgroundColor: isListening ? '#DC2626' : '#2563EB',
                      color: '#FFFFFF',
                      border: 'none',
                      borderRadius: '8px',
                      padding: '5px 10px',
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    <Mic size={13} className={isListening ? 'animate-pulse' : ''} />
                    <span>{isListening ? 'Stop' : 'Speak'}</span>
                  </button>
                </div>
              </div>

              {liveTranscript && (
                <div style={{
                  marginBottom: '0.75rem',
                  fontSize: '0.75rem',
                  backgroundColor: '#FFFFFF',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  border: '1px solid #BFDBFE',
                  color: '#1E293B',
                  fontWeight: 600
                }}>
                  "{liveTranscript}"
                </div>
              )}

              {voiceNotification && (
                <div style={{
                  marginBottom: '0.75rem',
                  fontSize: '0.75rem',
                  backgroundColor: voiceNotification.type === 'error' ? '#FEF2F2' : '#F0FDF4',
                  color: voiceNotification.type === 'error' ? '#DC2626' : '#166534',
                  padding: '6px 10px',
                  borderRadius: '8px',
                  fontWeight: 700
                }}>
                  {voiceNotification.message}
                </div>
              )}

              {/* Form Inputs */}
              <form onSubmit={handleSubmitPass} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                    Full Name / முழு பெயர் <span style={{ color: '#EF4444' }}>*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Karthik Subramanian"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.65rem 0.85rem',
                      fontSize: '0.85rem',
                      borderRadius: '10px',
                      border: '1.5px solid #CBD5E1',
                      outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                      {selectedPassItem.identifierLabel || 'Roll No / ID'} <span style={{ color: '#EF4444' }}>*</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder={selectedPassItem.identifierPlaceholder || 'e.g. 22CS101'}
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '0.65rem 0.85rem',
                        fontSize: '0.85rem',
                        borderRadius: '10px',
                        border: '1.5px solid #CBD5E1',
                        outline: 'none',
                        boxSizing: 'border-box',
                        fontWeight: 700
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                      Phone / மொபைல் எண்
                    </label>
                    <input
                      type="tel"
                      placeholder="10-digit mobile"
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '0.65rem 0.85rem',
                        fontSize: '0.85rem',
                        borderRadius: '10px',
                        border: '1.5px solid #CBD5E1',
                        outline: 'none',
                        boxSizing: 'border-box'
                      }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                    Department / துறை
                  </label>
                  <select
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '0.65rem 0.85rem',
                      fontSize: '0.85rem',
                      borderRadius: '10px',
                      border: '1.5px solid #CBD5E1',
                      outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  >
                    {departmentsList.map((dept) => (
                      <option key={dept} value={dept}>{dept}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                    Visit / Entry Purpose (காரணம்)
                  </label>
                  <input
                    type="text"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Reason for entry"
                    style={{
                      width: '100%',
                      padding: '0.65rem 0.85rem',
                      fontSize: '0.85rem',
                      borderRadius: '10px',
                      border: '1.5px solid #CBD5E1',
                      outline: 'none',
                      boxSizing: 'border-box'
                    }}
                  />
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{
                    marginTop: '0.5rem',
                    width: '100%',
                    padding: '0.85rem',
                    borderRadius: '12px',
                    backgroundColor: '#EA580C', // Softnix Orange Brand
                    color: '#FFFFFF',
                    fontSize: '0.95rem',
                    fontWeight: 800,
                    border: 'none',
                    cursor: isSubmitting ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 8px 20px -4px rgba(234, 88, 12, 0.4)'
                  }}
                >
                  {isSubmitting ? (
                    'Generating Gate Pass & OTP...'
                  ) : (
                    <>
                      <span>Generate Smart Gate Pass</span>
                      <ArrowRight size={17} />
                    </>
                  )}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
