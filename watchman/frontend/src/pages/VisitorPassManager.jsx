import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { VisitorSelfPass } from '../components/VisitorSelfPass';
import {
  Users,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ExternalLink,
  Search,
  Filter,
  Check,
  X,
  RefreshCw,
  LogOut,
  Sparkles,
  Volume2,
  VolumeX,
  ChevronDown,
  ChevronUp,
  KeyRound,
  Copy,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  User,
  SlidersHorizontal
} from 'lucide-react';

// Seed Initial Data matching the exact Proposed UI Screenshot
const SEED_REQUESTS = [
  {
    id: 101,
    passNumber: 'GP-3517',
    visitorName: 'Suganya',
    visitorType: 'STUDENT',
    department: 'CSE',
    reason: 'College visit',
    arrivalTime: '07:36 AM',
    approvalStatus: 'APPROVAL_PENDING',
    status: 'PENDING',
    identifier: '23cs086'
  },
  {
    id: 102,
    passNumber: 'GP-3489',
    visitorName: 'Karthick Sakthivelan',
    visitorType: 'STUDENT',
    department: 'Mechanical',
    reason: 'Official work',
    arrivalTime: '09:15 AM',
    approvalStatus: 'APPROVAL_PENDING',
    status: 'PENDING',
    identifier: '22ME045'
  },
  {
    id: 103,
    passNumber: 'GP-3478',
    visitorName: 'Vignesh',
    visitorType: 'STUDENT',
    department: 'ECE',
    reason: 'Meeting',
    arrivalTime: '10:22 AM',
    approvalStatus: 'APPROVAL_PENDING',
    status: 'PENDING',
    identifier: '22EC091'
  },
  {
    id: 104,
    passNumber: 'GP-3461',
    visitorName: 'Senthil Nathan & Selvi',
    visitorType: 'VISITOR',
    department: 'External',
    reason: 'Campus tour',
    arrivalTime: '11:06 AM',
    approvalStatus: 'APPROVAL_PENDING',
    status: 'PENDING',
    identifier: 'Parent of Priya'
  },
  {
    id: 105,
    passNumber: 'GP-3440',
    visitorName: 'Gopinath',
    visitorType: 'STAFF',
    department: 'Physics',
    reason: 'Department work',
    arrivalTime: '12:01 PM',
    approvalStatus: 'APPROVAL_PENDING',
    status: 'PENDING',
    identifier: 'STF-PHY-09'
  },
  // 24 Approved passes for today to match 24 Approved stat
  ...Array.from({ length: 21 }, (_, i) => ({
    id: 200 + i,
    passNumber: `GP-${3430 - i * 7}`,
    visitorName: ['Dr. Ramesh K', 'Priya Dharshini', 'Arun Kumar', 'Muthu Vel', 'Sangeetha R', 'Saravanan B', 'Deepa M'][i % 7],
    visitorType: ['FACULTY', 'STUDENT', 'VISITOR', 'STAFF', 'PARENT'][i % 5],
    department: ['CSE', 'ECE', 'Mechanical', 'Civil', 'Physics', 'Administration'][i % 6],
    reason: ['OS Lab Session', 'Campus Interview', 'Library Study', 'Guest Lecture', 'Admission Inquiry'][i % 5],
    arrivalTime: `${String(8 + Math.floor(i / 3)).padStart(2, '0')}:${String((i * 12) % 60).padStart(2, '0')} AM`,
    approvalStatus: 'APPROVED',
    status: 'APPROVED',
    identifier: `ID-${1000 + i}`
  })),
  // 2 Rejected passes to match 02 Rejected / Alerts stat
  {
    id: 301,
    passNumber: 'GP-3390',
    visitorName: 'Manoj K',
    visitorType: 'VISITOR',
    department: 'External',
    reason: 'Unauthorized entry attempt',
    arrivalTime: '08:45 AM',
    approvalStatus: 'REJECTED',
    status: 'REJECTED',
    identifier: 'EXT-9912'
  },
  {
    id: 302,
    passNumber: 'GP-3382',
    visitorName: 'Dinesh R',
    visitorType: 'STUDENT',
    department: 'Civil',
    reason: 'Late entry beyond cutoff without letter',
    arrivalTime: '09:50 AM',
    approvalStatus: 'REJECTED',
    status: 'REJECTED',
    identifier: '22CE012'
  }
];

const SEED_INSIDE_VISITORS = [
  {
    id: 401,
    passNumber: 'GP-3142',
    visitorName: 'Dr. Rajesh Kumar',
    visitorType: 'Faculty',
    department: 'CSE',
    reason: 'Meeting',
    entryTime: '09:12 AM',
    approvedBy: 'Admin',
    status: 'Inside',
    isVip: true
  },
  {
    id: 402,
    passNumber: 'GP-3125',
    visitorName: 'Meena S',
    visitorType: 'Student',
    department: 'ECE',
    reason: 'Lab Work',
    entryTime: '09:45 AM',
    approvedBy: 'HOD',
    status: 'Inside',
    isVip: false
  },
  {
    id: 403,
    passNumber: 'GP-3107',
    visitorName: 'Suresh Babu',
    visitorType: 'Visitor',
    department: 'External',
    reason: 'Delivery',
    entryTime: '10:20 AM',
    approvedBy: 'Security',
    status: 'Inside',
    isVip: false
  },
  {
    id: 404,
    passNumber: 'GP-3095',
    visitorName: 'Kavitha M',
    visitorType: 'Faculty',
    department: 'Physics',
    reason: 'Guest Lecture',
    entryTime: '10:35 AM',
    approvedBy: 'Dean',
    status: 'Inside',
    isVip: true
  },
  {
    id: 405,
    passNumber: 'GP-3088',
    visitorName: 'Praveen Kumar',
    visitorType: 'Student',
    department: 'Mechanical',
    reason: 'Robotics Workshop',
    entryTime: '10:48 AM',
    approvedBy: 'HOD',
    status: 'Inside',
    isVip: false
  },
  {
    id: 406,
    passNumber: 'GP-3074',
    visitorName: 'Anand & Revathi',
    visitorType: 'Parent',
    department: 'CSE',
    reason: 'Fee Clearance',
    entryTime: '11:00 AM',
    approvedBy: 'Admin',
    status: 'Inside',
    isVip: false
  },
  {
    id: 407,
    passNumber: 'GP-3061',
    visitorName: 'Narayanan R',
    visitorType: 'Visitor',
    department: 'Administration',
    reason: 'Auditing',
    entryTime: '11:15 AM',
    approvedBy: 'Principal',
    status: 'Inside',
    isVip: true
  },
  {
    id: 408,
    passNumber: 'GP-3052',
    visitorName: 'Deepak V',
    visitorType: 'Student',
    department: 'Civil',
    reason: 'Survey Project',
    entryTime: '11:30 AM',
    approvedBy: 'Faculty',
    status: 'Inside',
    isVip: false
  },
  {
    id: 409,
    passNumber: 'GP-3040',
    visitorName: 'Aishwarya K',
    visitorType: 'Faculty',
    department: 'Biotech',
    reason: 'Research Review',
    entryTime: '11:42 AM',
    approvedBy: 'HOD',
    status: 'Inside',
    isVip: true
  }
];

export const VisitorPassManager = () => {
  const { user, language, addGateLog } = useAuth();

  // Storage synced lists
  const [allPasses, setAllPasses] = useState(() => {
    try {
      const saved = localStorage.getItem('campusguard_all_passes');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return SEED_REQUESTS;
  });

  const [activeVisitors, setActiveVisitors] = useState(() => {
    try {
      const saved = localStorage.getItem('campusguard_inside_visitors');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return SEED_INSIDE_VISITORS;
  });

  useEffect(() => {
    try {
      localStorage.setItem('campusguard_all_passes', JSON.stringify(allPasses));
    } catch {}
  }, [allPasses]);

  useEffect(() => {
    try {
      localStorage.setItem('campusguard_inside_visitors', JSON.stringify(activeVisitors));
    } catch {}
  }, [activeVisitors]);

  // Tab & Filters
  const [activeTab, setActiveTab] = useState('INCOMING'); // 'INCOMING' | 'APPROVED' | 'REJECTED'
  const [statusFilter, setStatusFilter] = useState('PENDING'); // 'ALL' | 'PENDING' | 'APPROVED' | 'REJECTED'
  const [searchQuery, setSearchQuery] = useState('');
  const [visitorTypeFilter, setVisitorTypeFilter] = useState('ALL');
  const [departmentFilter, setDepartmentFilter] = useState('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedRequests, setSelectedRequests] = useState([]);

  // Inside campus filters
  const [insideSearch, setInsideSearch] = useState('');
  const [insideVipOnly, setInsideVipOnly] = useState(false);
  const [selectedInside, setSelectedInside] = useState([]);

  // Audio & Notification
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [successBanner, setSuccessBanner] = useState(null);
  const [loading, setLoading] = useState(false);

  // Optional OTP security panel
  const [showManualOtpConsole, setShowManualOtpConsole] = useState(false);
  const [manualOtp, setManualOtp] = useState('');
  const [otpVerifyResult, setOtpVerifyResult] = useState(null);
  const [verifyingOtp, setVerifyingOtp] = useState(false);

  // Web Audio Chimes
  const playChime = () => {
    if (!soundEnabled) return;
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(587.33, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.35);
    } catch {}
  };

  const playBarrierChime = () => {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(523.25, audioCtx.currentTime);
      osc.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.1);
      osc.frequency.setValueAtTime(783.99, audioCtx.currentTime + 0.2);
      gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.45);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.45);
    } catch {}
  };

  // Sync with API polling & storage events
  const fetchLiveData = async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    try {
      const [pending, active] = await Promise.all([
        api.getLiveGatePassRequests(),
        api.getActiveVisitors()
      ]);

      if (pending && Array.isArray(pending) && pending.length > 0) {
        setAllPasses(prev => {
          const map = new Map(prev.map(p => [p.id, p]));
          pending.forEach(p => map.set(p.id, { ...p, status: p.status || 'PENDING' }));
          return Array.from(map.values());
        });
      }

      if (active && Array.isArray(active) && active.length > 0) {
        setActiveVisitors(prev => {
          const map = new Map(prev.map(v => [v.id, v]));
          active.forEach(v => map.set(v.id, { ...v, status: 'Inside' }));
          return Array.from(map.values());
        });
      }
    } catch (e) {
      console.warn('Live data sync error:', e);
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  useEffect(() => {
    const handlePassCreated = (e) => {
      playChime();
      if (e.detail) {
        setAllPasses(prev => [e.detail, ...prev]);
      }
    };
    window.addEventListener('campusguard_pass_created', handlePassCreated);
    return () => window.removeEventListener('campusguard_pass_created', handlePassCreated);
  }, []);

  // Action: Approve Entry
  const handleAllowEntry = async (pass) => {
    const watchmanId = user?.username === 'watchman1' ? 'WM-01' : (user?.id ? `WM-${user.id}` : 'WM-01');
    const watchmanName = user?.fullName || 'Ramasamy (Main Gate Security)';
    const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    playBarrierChime();
    setSuccessBanner({
      passNumber: pass.passNumber,
      visitorName: pass.visitorName,
      identifier: pass.identifier || pass.passNumber,
      checkInTime: nowTime,
      watchman: watchmanName
    });

    setAllPasses(prev => prev.map(p => {
      if (p.id === pass.id) {
        return {
          ...p,
          status: 'APPROVED',
          approvalStatus: 'APPROVED',
          checkInStatus: 'INSIDE_CAMPUS',
          checkInTime: nowTime
        };
      }
      return p;
    }));

    setActiveVisitors(prev => [{
      id: pass.id || Date.now(),
      passNumber: pass.passNumber,
      visitorName: pass.visitorName,
      visitorType: pass.visitorType || 'Visitor',
      department: pass.department || 'General',
      reason: pass.reason || pass.purpose || 'Campus Entry',
      entryTime: nowTime,
      approvedBy: 'Security',
      status: 'Inside',
      isVip: false
    }, ...prev]);

    addGateLog({
      id: Date.now(),
      direction: 'IN',
      rollOrId: pass.identifier || pass.passNumber,
      personName: pass.visitorName,
      category: pass.visitorType || 'STUDENT',
      purpose: pass.reason || 'Campus Entry',
      entryTime: nowTime,
      status: 'APPROVED',
      verifiedBy: `${watchmanName} (${watchmanId})`
    });

    try {
      await api.allowPassEntry(pass.id, { watchmanId, watchmanName });
    } catch {}
  };

  // Action: Wait / Keep in Approval Pending
  const handleSetApprovalPending = async (pass) => {
    setAllPasses(prev => prev.map(p => {
      if (p.id === pass.id) {
        return {
          ...p,
          status: 'PENDING',
          approvalStatus: 'APPROVAL_PENDING',
          policyAlert: 'Approval Pending from HOD / Warden / Admin Office.'
        };
      }
      return p;
    }));
    try {
      await api.setPassApprovalPending(pass.id, {
        policyAlert: 'Approval Pending from HOD / Warden / Admin Office.'
      });
    } catch {}
  };

  // Action: Reject
  const handleReject = async (pass) => {
    const reason = prompt('Enter rejection reason (e.g. Unauthorized entry / Invalid college identity):', 'Unauthorized entry attempt');
    if (!reason) return;

    setAllPasses(prev => prev.map(p => {
      if (p.id === pass.id) {
        return {
          ...p,
          status: 'REJECTED',
          approvalStatus: 'REJECTED',
          checkInStatus: 'REJECTED',
          policyAlert: reason
        };
      }
      return p;
    }));

    try {
      await api.rejectPassEntry(pass.id, { reason });
    } catch {}
  };

  // Action: Check Out
  const handleCheckout = async (id) => {
    setActiveVisitors(prev => prev.filter(v => v.id !== id));
    try {
      await api.checkOutVisitorPass(id);
    } catch {}
  };

  // Simulation: Late Student
  const simulateExampleStudent = async () => {
    const newPass = {
      id: Date.now(),
      visitorType: 'STUDENT',
      visitorName: 'Example Student',
      identifier: '23CSE001',
      phoneNumber: '+91 98456 99881',
      department: 'CSE',
      reason: 'College bus missed',
      additionalDetails: 'Bus #14 breakdown at Tambaram junction',
      passNumber: 'GP-' + Math.floor(1000 + Math.random() * 9000),
      arrivalTime: '09:30 AM',
      approvalStatus: 'APPROVAL_PENDING',
      status: 'PENDING',
      policyAlert: 'Arrived after 09:00 AM cutoff. Requires watchman check or HOD clearance.'
    };
    setAllPasses(prev => [newPass, ...prev]);
    playChime();
    try {
      await api.selfRegisterVisitor(newPass);
    } catch {}
  };

  // Manual OTP Verify
  const handleManualOtpVerify = async (e) => {
    if (e) e.preventDefault();
    if (!manualOtp.trim()) return;
    setVerifyingOtp(true);
    setOtpVerifyResult(null);
    try {
      const res = await api.verifyVisitorOtp(manualOtp.trim());
      setOtpVerifyResult(res);
      if (res && res.success && res.visitorPass) {
        handleAllowEntry(res.visitorPass);
      }
    } finally {
      setVerifyingOtp(false);
    }
  };

  // Copy Public Link Helper
  const handleCopyPublicLink = () => {
    const url = window.location.origin + '/self-pass';
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url);
      alert('✓ Copied Public Self-Pass URL to clipboard:\n' + url);
    }
  };

  // Counts Calculation
  const pendingCount = allPasses.filter(p => p.status === 'PENDING' || p.approvalStatus === 'APPROVAL_PENDING').length;
  const approvedCount = allPasses.filter(p => p.status === 'APPROVED' || p.approvalStatus === 'APPROVED').length;
  const rejectedCount = allPasses.filter(p => p.status === 'REJECTED' || p.approvalStatus === 'REJECTED').length;
  const totalCount = allPasses.length;
  const insideCount = activeVisitors.length;

  // Requests Table Filtering
  const filteredRequests = allPasses.filter(p => {
    const isPending = p.status === 'PENDING' || p.approvalStatus === 'APPROVAL_PENDING';
    const isApproved = p.status === 'APPROVED' || p.approvalStatus === 'APPROVED';
    const isRejected = p.status === 'REJECTED' || p.approvalStatus === 'REJECTED';

    // 1. Tab & Status Pill filtering
    if (statusFilter === 'PENDING' && !isPending) return false;
    if (statusFilter === 'APPROVED' && !isApproved) return false;
    if (statusFilter === 'REJECTED' && !isRejected) return false;

    if (activeTab === 'INCOMING' && !isPending && statusFilter === 'ALL') return false;
    if (activeTab === 'APPROVED' && !isApproved && statusFilter === 'ALL') return false;
    if (activeTab === 'REJECTED' && !isRejected && statusFilter === 'ALL') return false;

    // 2. Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = (p.visitorName || '').toLowerCase().includes(q);
      const matchPass = (p.passNumber || '').toLowerCase().includes(q);
      const matchId = (p.identifier || '').toLowerCase().includes(q);
      const matchDept = (p.department || '').toLowerCase().includes(q);
      const matchReason = (p.reason || '').toLowerCase().includes(q);
      if (!matchName && !matchPass && !matchId && !matchDept && !matchReason) return false;
    }

    // 3. Visitor Type Filter
    if (visitorTypeFilter !== 'ALL') {
      if ((p.visitorType || '').toUpperCase() !== visitorTypeFilter.toUpperCase()) return false;
    }

    // 4. Department Filter
    if (departmentFilter !== 'ALL') {
      if (!(p.department || '').toLowerCase().includes(departmentFilter.toLowerCase())) return false;
    }

    return true;
  });

  // Pagination
  const PAGE_SIZE = 5;
  const totalPages = Math.max(1, Math.ceil(filteredRequests.length / PAGE_SIZE));
  const paginatedRequests = filteredRequests.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  // Inside Table Filtering
  const filteredInside = activeVisitors.filter(v => {
    if (insideVipOnly && !v.isVip && v.visitorType !== 'Faculty') return false;
    if (insideSearch.trim()) {
      const q = insideSearch.toLowerCase();
      const matchName = (v.visitorName || '').toLowerCase().includes(q);
      const matchPass = (v.passNumber || '').toLowerCase().includes(q);
      const matchDept = (v.department || '').toLowerCase().includes(q);
      const matchReason = (v.reason || '').toLowerCase().includes(q);
      if (!matchName && !matchPass && !matchDept && !matchReason) return false;
    }
    return true;
  });

  // Checkbox helpers
  const handleToggleSelectAllRequests = () => {
    if (selectedRequests.length === paginatedRequests.length) {
      setSelectedRequests([]);
    } else {
      setSelectedRequests(paginatedRequests.map(p => p.id));
    }
  };

  const handleToggleSelectRequest = (id) => {
    setSelectedRequests(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const handleToggleSelectAllInside = () => {
    if (selectedInside.length === filteredInside.length) {
      setSelectedInside([]);
    } else {
      setSelectedInside(filteredInside.map(v => v.id));
    }
  };

  const handleToggleSelectInside = (id) => {
    setSelectedInside(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

      {/* 1. TOP HEADER: TITLE + CONTROLS */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
        padding: '0.25rem 0'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            backgroundColor: '#EFF6FF',
            border: '1.5px solid #BFDBFE',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#2563EB',
            boxShadow: '0 2px 6px rgba(37, 99, 235, 0.1)'
          }}>
            <Users size={24} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 900, color: '#0F172A', margin: 0, letterSpacing: '-0.02em' }}>
              {language === 'ta' ? 'பார்வையாளர் மேலாண்மை' : 'Visitor Management'}
            </h2>

          </div>
        </div>

        {/* Top Action Triggers */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setSoundEnabled(!soundEnabled)}
            style={{
              background: soundEnabled ? '#FFFFFF' : '#FEF2F2',
              border: '1.5px solid #E2E8F0',
              borderRadius: '8px',
              padding: '0.55rem 0.85rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.8rem',
              fontWeight: 700,
              color: soundEnabled ? '#475569' : '#DC2626'
            }}
          >
            {soundEnabled ? <Volume2 size={16} color="#16A34A" /> : <VolumeX size={16} color="#DC2626" />}
            <span>{soundEnabled ? 'Sound ON' : 'Muted'}</span>
          </button>

          <button
            type="button"
            onClick={simulateExampleStudent}
            style={{
              backgroundColor: '#EFF6FF',
              border: '1.5px solid #BFDBFE',
              color: '#1D4ED8',
              padding: '0.55rem 0.95rem',
              borderRadius: '8px',
              fontSize: '0.825rem',
              fontWeight: 800,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Sparkles size={16} />
            <span>Simulate 9:30 AM Late Student (23CSE001)</span>
          </button>
        </div>
      </div>

      {/* SUCCESS CONFIRMATION BANNER */}
      {successBanner && (
        <div className="animate-fade-in" style={{
          backgroundColor: '#ECFDF5',
          border: '1.5px solid #10B981',
          borderRadius: '12px',
          padding: '1rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          boxShadow: '0 4px 14px rgba(16, 185, 129, 0.15)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '50%',
              backgroundColor: '#10B981',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Check size={22} strokeWidth={3} />
            </div>
            <div>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: '#065F46' }}>
                🎉 Gate Barrier Opened! Entry Approved ({successBanner.visitorName})
              </div>
              <div style={{ fontSize: '0.8rem', color: '#047857', marginTop: '2px' }}>
                Pass: <strong>{successBanner.passNumber}</strong> &bull; Roll/ID: <strong>{successBanner.identifier}</strong> &bull; Checked-in at <strong>{successBanner.checkInTime}</strong> by <strong>{successBanner.watchman}</strong>.
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSuccessBanner(null)}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#059669',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '0.825rem'
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 2. FIVE TOP SUMMARY CARDS (MATCHING PROPOSED UI EXACTLY) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
        gap: '1rem',
        alignItems: 'stretch'
      }}>
        {/* Card 1: Waiting at Gate */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1.5px solid #E2E8F0',
          padding: '1.15rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '0.75rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              backgroundColor: '#FEF3C7',
              border: '1px solid #FDE68A',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#D97706',
              flexShrink: 0
            }}>
              <Clock size={22} />
            </div>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#64748B' }}>
                Waiting at Gate
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#0F172A', lineHeight: 1.1 }}>
                {String(pendingCount).padStart(2, '0')}
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <button
              type="button"
              onClick={() => {
                setStatusFilter('PENDING');
                setActiveTab('INCOMING');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#D97706',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px'
              }}
            >
              <span>View all</span>
              <span>&rarr;</span>
            </button>
          </div>
        </div>

        {/* Card 2: Approved Today */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1.5px solid #E2E8F0',
          padding: '1.15rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '0.75rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              backgroundColor: '#DCFCE7',
              border: '1px solid #BBF7D0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#16A34A',
              flexShrink: 0
            }}>
              <CheckCircle2 size={22} />
            </div>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#64748B' }}>
                Approved Today
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#16A34A', lineHeight: 1.1 }}>
                {String(approvedCount).padStart(2, '0')}
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <button
              type="button"
              onClick={() => {
                setStatusFilter('APPROVED');
                setActiveTab('APPROVED');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#16A34A',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px'
              }}
            >
              <span>View all</span>
              <span>&rarr;</span>
            </button>
          </div>
        </div>

        {/* Card 3: Inside Campus */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1.5px solid #E2E8F0',
          padding: '1.15rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '0.75rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              backgroundColor: '#EFF6FF',
              border: '1px solid #BFDBFE',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#2563EB',
              flexShrink: 0
            }}>
              <Users size={22} />
            </div>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#64748B' }}>
                Inside Campus
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#2563EB', lineHeight: 1.1 }}>
                {String(insideCount).padStart(2, '0')}
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <button
              type="button"
              onClick={() => {
                const el = document.getElementById('currently-inside-section');
                if (el) el.scrollIntoView({ behavior: 'smooth' });
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#2563EB',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px'
              }}
            >
              <span>View all</span>
              <span>&rarr;</span>
            </button>
          </div>
        </div>

        {/* Card 4: Rejected / Alerts */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1.5px solid #E2E8F0',
          padding: '1.15rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '0.75rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              backgroundColor: '#FEE2E2',
              border: '1px solid #FECACA',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#DC2626',
              flexShrink: 0
            }}>
              <AlertTriangle size={22} />
            </div>
            <div>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#64748B' }}>
                Rejected / Alerts
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#DC2626', lineHeight: 1.1 }}>
                {String(rejectedCount).padStart(2, '0')}
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <button
              type="button"
              onClick={() => {
                setStatusFilter('REJECTED');
                setActiveTab('REJECTED');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#DC2626',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px'
              }}
            >
              <span>View all</span>
              <span>&rarr;</span>
            </button>
          </div>
        </div>

        {/* Card 5: Separate Public Portal (Compact Section) */}
        <div style={{
          backgroundColor: '#F8FAFC',
          borderRadius: '12px',
          border: '1.5px solid #DBEAFE',
          padding: '1.15rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '0.75rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          minWidth: '260px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              backgroundColor: '#2563EB',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0
            }}>
              <ExternalLink size={18} />
            </div>
            <div>
              <h4 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 800, color: '#0F172A' }}>
                Separate Public Portal
              </h4>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.72rem', color: '#64748B', lineHeight: 1.3 }}>
                Visitor self-registration and QR/OTP verification
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <a
              href="/self-pass"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                flex: 1.4,
                backgroundColor: '#2563EB',
                color: '#FFFFFF',
                borderRadius: '6px',
                padding: '0.45rem 0.65rem',
                fontSize: '0.75rem',
                fontWeight: 800,
                textAlign: 'center',
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px'
              }}
            >
              <ExternalLink size={12} />
              <span>Open /self-pass ↗</span>
            </a>
            <button
              type="button"
              onClick={handleCopyPublicLink}
              style={{
                flex: 1,
                backgroundColor: '#FFFFFF',
                border: '1px solid #CBD5E1',
                color: '#334155',
                borderRadius: '6px',
                padding: '0.45rem 0.65rem',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px'
              }}
            >
              <Copy size={12} />
              <span>Copy Link</span>
            </button>
          </div>
        </div>
      </div>

      {/* 3. SEARCH AND FILTER CONTROLS BAR (MATCHING PROPOSED UI) */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.85rem',
        backgroundColor: '#FFFFFF',
        padding: '0.85rem 1.15rem',
        borderRadius: '12px',
        border: '1.5px solid #E2E8F0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.02)'
      }}>
        {/* Search input */}
        <div style={{ position: 'relative', flex: '1 1 260px', maxWidth: '380px' }}>
          <input
            type="text"
            className="input-field"
            placeholder={language === 'ta' ? 'பெயர், பாஸ் எண் அல்லது ரோல் எண் தேடுங்கள்...' : 'Search by name, pass ID or roll number...'}
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            style={{
              padding: '0.45rem 0.65rem 0.45rem 2.2rem',
              fontSize: '0.825rem',
              borderRadius: '8px',
              border: '1.5px solid #CBD5E1',
              width: '100%'
            }}
          />
          <Search size={15} color="#94A3B8" style={{ position: 'absolute', left: '9px', top: '50%', transform: 'translateY(-50%)' }} />
        </div>

        {/* Filter Badges: All (28), Pending (5), Approved (24), Rejected (2) */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => {
              setStatusFilter('ALL');
              setActiveTab('INCOMING');
              setCurrentPage(1);
            }}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '999px',
              border: statusFilter === 'ALL' ? '1.5px solid #2563EB' : '1.5px solid #E2E8F0',
              backgroundColor: statusFilter === 'ALL' ? '#2563EB' : '#FFFFFF',
              color: statusFilter === 'ALL' ? '#FFFFFF' : '#475569',
              fontWeight: 800,
              fontSize: '0.78rem',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            All ({totalCount})
          </button>

          <button
            type="button"
            onClick={() => {
              setStatusFilter('PENDING');
              setActiveTab('INCOMING');
              setCurrentPage(1);
            }}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '999px',
              border: statusFilter === 'PENDING' ? '1.5px solid #F59E0B' : '1.5px solid #FEF3C7',
              backgroundColor: statusFilter === 'PENDING' ? '#FEF3C7' : '#FFFFFF',
              color: '#B45309',
              fontWeight: 800,
              fontSize: '0.78rem',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            Pending ({pendingCount})
          </button>

          <button
            type="button"
            onClick={() => {
              setStatusFilter('APPROVED');
              setActiveTab('APPROVED');
              setCurrentPage(1);
            }}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '999px',
              border: statusFilter === 'APPROVED' ? '1.5px solid #16A34A' : '1.5px solid #DCFCE7',
              backgroundColor: statusFilter === 'APPROVED' ? '#DCFCE7' : '#FFFFFF',
              color: '#15803D',
              fontWeight: 800,
              fontSize: '0.78rem',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            Approved ({approvedCount})
          </button>

          <button
            type="button"
            onClick={() => {
              setStatusFilter('REJECTED');
              setActiveTab('REJECTED');
              setCurrentPage(1);
            }}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: '999px',
              border: statusFilter === 'REJECTED' ? '1.5px solid #DC2626' : '1.5px solid #FEE2E2',
              backgroundColor: statusFilter === 'REJECTED' ? '#FEE2E2' : '#FFFFFF',
              color: '#B91C1C',
              fontWeight: 800,
              fontSize: '0.78rem',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            Rejected ({rejectedCount})
          </button>
        </div>

        {/* Dropdowns: Visitor Type, Department, Filter button */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
          <select
            value={visitorTypeFilter}
            onChange={(e) => {
              setVisitorTypeFilter(e.target.value);
              setCurrentPage(1);
            }}
            style={{
              padding: '0.45rem 0.65rem',
              borderRadius: '8px',
              border: '1.5px solid #CBD5E1',
              fontSize: '0.78rem',
              fontWeight: 700,
              color: '#334155',
              backgroundColor: '#FFFFFF',
              cursor: 'pointer'
            }}
          >
            <option value="ALL">Visitor Type</option>
            <option value="STUDENT">Student</option>
            <option value="STAFF">Staff</option>
            <option value="VISITOR">Visitor</option>
            <option value="FACULTY">Faculty</option>
            <option value="PARENT">Parent</option>
          </select>

          <select
            value={departmentFilter}
            onChange={(e) => {
              setDepartmentFilter(e.target.value);
              setCurrentPage(1);
            }}
            style={{
              padding: '0.45rem 0.65rem',
              borderRadius: '8px',
              border: '1.5px solid #CBD5E1',
              fontSize: '0.78rem',
              fontWeight: 700,
              color: '#334155',
              backgroundColor: '#FFFFFF',
              cursor: 'pointer'
            }}
          >
            <option value="ALL">Department</option>
            <option value="CSE">CSE</option>
            <option value="Mechanical">Mechanical</option>
            <option value="ECE">ECE</option>
            <option value="Physics">Physics</option>
            <option value="Civil">Civil</option>
            <option value="External">External</option>
          </select>

          <button
            type="button"
            onClick={() => {
              setSearchQuery('');
              setVisitorTypeFilter('ALL');
              setDepartmentFilter('ALL');
              setStatusFilter('PENDING');
              setActiveTab('INCOMING');
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '0.45rem 0.75rem',
              borderRadius: '8px',
              border: '1.5px solid #CBD5E1',
              backgroundColor: '#FFFFFF',
              color: '#475569',
              fontSize: '0.78rem',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            <Filter size={13} color="#64748B" />
            <span>Filter</span>
          </button>
        </div>
      </div>

      {/* 4. MAIN COMPACT DATA TABLE: INCOMING REQUESTS / APPROVED / REJECTED */}
      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '14px',
        border: '1.5px solid #E2E8F0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        overflow: 'hidden'
      }}>
        {/* Table Subtabs Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '1.5rem',
          padding: '0.85rem 1.25rem',
          borderBottom: '1.5px solid #E2E8F0',
          backgroundColor: '#FAFAFA'
        }}>
          <button
            type="button"
            onClick={() => {
              setActiveTab('INCOMING');
              setStatusFilter('PENDING');
              setCurrentPage(1);
            }}
            style={{
              background: 'none',
              border: 'none',
              padding: '0.35rem 0',
              fontSize: '0.88rem',
              fontWeight: 800,
              color: activeTab === 'INCOMING' ? '#2563EB' : '#64748B',
              borderBottom: activeTab === 'INCOMING' ? '2.5px solid #2563EB' : '2.5px solid transparent',
              cursor: 'pointer'
            }}
          >
            Incoming Requests ({pendingCount})
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('APPROVED');
              setStatusFilter('APPROVED');
              setCurrentPage(1);
            }}
            style={{
              background: 'none',
              border: 'none',
              padding: '0.35rem 0',
              fontSize: '0.88rem',
              fontWeight: 800,
              color: activeTab === 'APPROVED' ? '#2563EB' : '#64748B',
              borderBottom: activeTab === 'APPROVED' ? '2.5px solid #2563EB' : '2.5px solid transparent',
              cursor: 'pointer'
            }}
          >
            Approved ({approvedCount})
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('REJECTED');
              setStatusFilter('REJECTED');
              setCurrentPage(1);
            }}
            style={{
              background: 'none',
              border: 'none',
              padding: '0.35rem 0',
              fontSize: '0.88rem',
              fontWeight: 800,
              color: activeTab === 'REJECTED' ? '#2563EB' : '#64748B',
              borderBottom: activeTab === 'REJECTED' ? '2.5px solid #2563EB' : '2.5px solid transparent',
              cursor: 'pointer'
            }}
          >
            Rejected ({rejectedCount})
          </button>
        </div>

        {/* Data Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.825rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#64748B', fontWeight: 800 }}>
                <th style={{ padding: '0.75rem 1rem', width: '35px' }}>
                  <input
                    type="checkbox"
                    checked={selectedRequests.length > 0 && selectedRequests.length === paginatedRequests.length}
                    onChange={handleToggleSelectAllRequests}
                    style={{ cursor: 'pointer' }}
                  />
                </th>
                <th style={{ padding: '0.75rem 1rem' }}>Pass ID</th>
                <th style={{ padding: '0.75rem 1rem' }}>Visitor Name</th>
                <th style={{ padding: '0.75rem 1rem' }}>Type</th>
                <th style={{ padding: '0.75rem 1rem' }}>Department</th>
                <th style={{ padding: '0.75rem 1rem' }}>Purpose</th>
                <th style={{ padding: '0.75rem 1rem' }}>Arrival Time</th>
                <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {paginatedRequests.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '2.5rem', color: '#94A3B8', fontWeight: 600 }}>
                    No requests match your current filters.
                  </td>
                </tr>
              ) : (
                paginatedRequests.map((pass) => {
                  const isSelected = selectedRequests.includes(pass.id);
                  const isPending = pass.status === 'PENDING' || pass.approvalStatus === 'APPROVAL_PENDING';
                  const isApproved = pass.status === 'APPROVED' || pass.approvalStatus === 'APPROVED';
                  const isRejected = pass.status === 'REJECTED' || pass.approvalStatus === 'REJECTED';

                  return (
                    <tr
                      key={pass.id}
                      style={{
                        borderBottom: '1px solid #F1F5F9',
                        backgroundColor: isSelected ? '#EFF6FF' : '#FFFFFF',
                        transition: 'background-color 0.15s ease'
                      }}
                      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = '#F8FAFC'; }}
                      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = '#FFFFFF'; }}
                    >
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSelectRequest(pass.id)}
                          style={{ cursor: 'pointer' }}
                        />
                      </td>

                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', fontWeight: 800, color: '#2563EB' }}>
                        {pass.passNumber}
                      </td>

                      <td style={{ padding: '0.75rem 1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <div style={{
                            width: '28px',
                            height: '28px',
                            borderRadius: '50%',
                            backgroundColor: '#EFF6FF',
                            border: '1px solid #BFDBFE',
                            color: '#1D4ED8',
                            fontSize: '0.75rem',
                            fontWeight: 800,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0
                          }}>
                            {pass.visitorName ? pass.visitorName.charAt(0).toUpperCase() : 'V'}
                          </div>
                          <div>
                            <div style={{ fontWeight: 800, color: '#0F172A' }}>
                              {pass.visitorName}
                            </div>
                            {pass.identifier && (
                              <div style={{ fontSize: '0.7rem', color: '#94A3B8', fontFamily: 'monospace' }}>
                                {pass.identifier}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>

                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{
                          fontSize: '0.72rem',
                          fontWeight: 800,
                          padding: '2px 8px',
                          borderRadius: '999px',
                          backgroundColor: pass.visitorType === 'STUDENT' ? '#EFF6FF' :
                                           pass.visitorType === 'STAFF' ? '#CCFBF1' :
                                           pass.visitorType === 'FACULTY' ? '#EFF6FF' :
                                           pass.visitorType === 'PARENT' ? '#FEF3C7' : '#F3E8FF',
                          color: pass.visitorType === 'STUDENT' ? '#1D4ED8' :
                                 pass.visitorType === 'STAFF' ? '#0F766E' :
                                 pass.visitorType === 'FACULTY' ? '#2563EB' :
                                 pass.visitorType === 'PARENT' ? '#B45309' : '#6B21A8'
                        }}>
                          {pass.visitorType === 'STUDENT' ? 'Student' :
                           pass.visitorType === 'STAFF' ? 'Staff' :
                           pass.visitorType === 'FACULTY' ? 'Faculty' :
                           pass.visitorType === 'PARENT' ? 'Parent' : 'Visitor'}
                        </span>
                      </td>

                      <td style={{ padding: '0.75rem 1rem', color: '#334155', fontWeight: 600 }}>
                        {pass.department || 'CSE'}
                      </td>

                      <td style={{ padding: '0.75rem 1rem', color: '#64748B', maxWidth: '180px' }}>
                        {pass.reason || pass.purpose || 'College visit'}
                      </td>

                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: '#475569', fontWeight: 700 }}>
                        {pass.arrivalTime || '09:00 AM'}
                      </td>

                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '2px 8px',
                          borderRadius: '999px',
                          fontSize: '0.72rem',
                          fontWeight: 800,
                          backgroundColor: isApproved ? '#DCFCE7' : isRejected ? '#FEE2E2' : '#FEF3C7',
                          color: isApproved ? '#166534' : isRejected ? '#991B1B' : '#92400E'
                        }}>
                          <span style={{
                            width: '5px',
                            height: '5px',
                            borderRadius: '50%',
                            backgroundColor: isApproved ? '#16A34A' : isRejected ? '#DC2626' : '#D97706'
                          }} />
                          {isApproved ? 'Approved' : isRejected ? 'Rejected' : 'Pending'}
                        </span>
                      </td>

                      <td style={{ padding: '0.75rem 1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                          <button
                            type="button"
                            onClick={() => handleAllowEntry(pass)}
                            style={{
                              backgroundColor: '#16A34A',
                              color: '#FFFFFF',
                              border: 'none',
                              borderRadius: '6px',
                              padding: '0.35rem 0.75rem',
                              fontSize: '0.75rem',
                              fontWeight: 800,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              boxShadow: '0 1px 3px rgba(22, 163, 74, 0.2)'
                            }}
                          >
                            <Check size={12} strokeWidth={3} />
                            <span>Approve</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => handleSetApprovalPending(pass)}
                            style={{
                              backgroundColor: '#FFFBEB',
                              color: '#B45309',
                              border: '1px solid #FCD34D',
                              borderRadius: '6px',
                              padding: '0.35rem 0.65rem',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '3px'
                            }}
                          >
                            <Clock size={12} />
                            <span>Wait</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => handleReject(pass)}
                            style={{
                              backgroundColor: '#FEF2F2',
                              color: '#DC2626',
                              border: '1px solid #FECACA',
                              borderRadius: '6px',
                              padding: '0.35rem 0.65rem',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '3px'
                            }}
                          >
                            <X size={12} />
                            <span>Reject</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Table Footer: Showing X of Y requests & Pagination */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.75rem 1.25rem',
          borderTop: '1px solid #E2E8F0',
          backgroundColor: '#FFFFFF',
          fontSize: '0.78rem',
          color: '#64748B'
        }}>
          <div>
            Showing {filteredRequests.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1} to {Math.min(currentPage * PAGE_SIZE, filteredRequests.length)} of {filteredRequests.length} requests
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <button
              type="button"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
                color: currentPage <= 1 ? '#CBD5E1' : '#334155',
                cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <ChevronLeft size={14} />
            </button>

            {Array.from({ length: totalPages }, (_, i) => i + 1).map((num) => (
              <button
                key={num}
                type="button"
                onClick={() => setCurrentPage(num)}
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '6px',
                  border: currentPage === num ? '1.5px solid #2563EB' : '1px solid #CBD5E1',
                  backgroundColor: currentPage === num ? '#2563EB' : '#FFFFFF',
                  color: currentPage === num ? '#FFFFFF' : '#334155',
                  fontWeight: 800,
                  fontSize: '0.75rem',
                  cursor: 'pointer'
                }}
              >
                {num}
              </button>
            ))}

            <button
              type="button"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
                color: currentPage >= totalPages ? '#CBD5E1' : '#334155',
                cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* 5. CURRENTLY INSIDE CAMPUS TABLE (MATCHING PROPOSED UI EXACTLY) */}
      <div id="currently-inside-section" style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '14px',
        border: '1.5px solid #E2E8F0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        overflow: 'hidden'
      }}>
        {/* Header with Title + Search + VIP filter + Refresh */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          padding: '0.85rem 1.25rem',
          borderBottom: '1.5px solid #E2E8F0',
          backgroundColor: '#FAFAFA'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
              Currently Inside Campus ({activeVisitors.length})
            </h3>
            <span style={{ fontSize: '0.75rem', color: '#64748B' }}>
              (வளாகத்தில் உள்ள நபர்கள்)
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            {/* Search inside campus input */}
            <div style={{ position: 'relative', width: '220px' }}>
              <input
                type="text"
                placeholder="Search inside campus..."
                value={insideSearch}
                onChange={(e) => setInsideSearch(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.35rem 0.65rem 0.35rem 2rem',
                  fontSize: '0.78rem',
                  borderRadius: '6px',
                  border: '1.5px solid #CBD5E1',
                  backgroundColor: '#FFFFFF'
                }}
              />
              <Search size={13} color="#94A3B8" style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)' }} />
            </div>

            {/* VIPs Filter Pill */}
            <button
              type="button"
              onClick={() => setInsideVipOnly(!insideVipOnly)}
              style={{
                padding: '0.35rem 0.75rem',
                borderRadius: '999px',
                border: insideVipOnly ? '1.5px solid #2563EB' : '1.5px solid #CBD5E1',
                backgroundColor: insideVipOnly ? '#EFF6FF' : '#FFFFFF',
                color: insideVipOnly ? '#2563EB' : '#475569',
                fontSize: '0.75rem',
                fontWeight: 700,
                cursor: 'pointer'
              }}
            >
              VIPs
            </button>


          </div>
        </div>

        {/* Inside Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.825rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#64748B', fontWeight: 800 }}>
                <th style={{ padding: '0.75rem 1rem', width: '35px' }}>
                  <input
                    type="checkbox"
                    checked={selectedInside.length > 0 && selectedInside.length === filteredInside.length}
                    onChange={handleToggleSelectAllInside}
                    style={{ cursor: 'pointer' }}
                  />
                </th>
                <th style={{ padding: '0.75rem 1rem' }}>Pass ID</th>
                <th style={{ padding: '0.75rem 1rem' }}>Visitor Name</th>
                <th style={{ padding: '0.75rem 1rem' }}>Type</th>
                <th style={{ padding: '0.75rem 1rem' }}>Department</th>
                <th style={{ padding: '0.75rem 1rem' }}>Purpose</th>
                <th style={{ padding: '0.75rem 1rem' }}>Entry Time</th>
                <th style={{ padding: '0.75rem 1rem' }}>Approved By</th>
                <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredInside.length === 0 ? (
                <tr>
                  <td colSpan="10" style={{ textAlign: 'center', padding: '2.5rem', color: '#94A3B8', fontWeight: 600 }}>
                    No visitors currently inside matching your search.
                  </td>
                </tr>
              ) : (
                filteredInside.map((v) => {
                  const isSelected = selectedInside.includes(v.id);
                  return (
                    <tr
                      key={v.id}
                      style={{
                        borderBottom: '1px solid #F1F5F9',
                        backgroundColor: isSelected ? '#EFF6FF' : '#FFFFFF',
                        transition: 'background-color 0.15s ease'
                      }}
                      onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = '#F8FAFC'; }}
                      onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = '#FFFFFF'; }}
                    >
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSelectInside(v.id)}
                          style={{ cursor: 'pointer' }}
                        />
                      </td>

                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', fontWeight: 800, color: '#2563EB' }}>
                        {v.passNumber}
                      </td>

                      <td style={{ padding: '0.75rem 1rem', fontWeight: 800, color: '#0F172A' }}>
                        {v.visitorName}
                      </td>

                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{
                          fontSize: '0.72rem',
                          fontWeight: 800,
                          padding: '2px 8px',
                          borderRadius: '999px',
                          backgroundColor: v.visitorType === 'Faculty' ? '#EFF6FF' :
                                           v.visitorType === 'Student' ? '#EFF6FF' :
                                           v.visitorType === 'Parent' ? '#FEF3C7' : '#F3E8FF',
                          color: v.visitorType === 'Faculty' ? '#2563EB' :
                                 v.visitorType === 'Student' ? '#1D4ED8' :
                                 v.visitorType === 'Parent' ? '#B45309' : '#6B21A8'
                        }}>
                          {v.visitorType}
                        </span>
                      </td>

                      <td style={{ padding: '0.75rem 1rem', color: '#334155', fontWeight: 600 }}>
                        {v.department}
                      </td>

                      <td style={{ padding: '0.75rem 1rem', color: '#64748B' }}>
                        {v.reason}
                      </td>

                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: '#059669', fontWeight: 700 }}>
                        {v.entryTime}
                      </td>

                      <td style={{ padding: '0.75rem 1rem', color: '#475569', fontWeight: 600 }}>
                        {v.approvedBy}
                      </td>

                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '2px 8px',
                          borderRadius: '999px',
                          fontSize: '0.72rem',
                          fontWeight: 800,
                          backgroundColor: '#DCFCE7',
                          color: '#166534'
                        }}>
                          <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: '#16A34A' }} />
                          Inside
                        </span>
                      </td>

                      <td style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>
                        <button
                          type="button"
                          onClick={() => handleCheckout(v.id)}
                          style={{
                            backgroundColor: '#FEF2F2',
                            color: '#DC2626',
                            border: '1px solid #FECACA',
                            borderRadius: '6px',
                            padding: '0.35rem 0.75rem',
                            fontSize: '0.75rem',
                            fontWeight: 800,
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            transition: 'all 0.15s ease'
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#DC2626'; e.currentTarget.style.color = '#FFFFFF'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#FEF2F2'; e.currentTarget.style.color = '#DC2626'; }}
                        >
                          <LogOut size={12} />
                          <span>Check Out</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6. OPTIONAL COLLAPSIBLE SECURITY STEP (QR / OTP MANUAL VERIFY) */}
      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '12px',
        border: '1px solid #E2E8F0',
        padding: '0.85rem 1.25rem',
        boxShadow: '0 1px 3px rgba(0,0,0,0.02)'
      }}>
        <div
          onClick={() => setShowManualOtpConsole(!showManualOtpConsole)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            userSelect: 'none'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <KeyRound size={16} color="#64748B" />
            <div>
              <span style={{ fontSize: '0.85rem', fontWeight: 800, color: '#334155' }}>
                Optional: Additional Security Step
              </span>
              <span style={{ fontSize: '0.72rem', color: '#64748B', marginLeft: '8px' }}>
                (தேவையான நேரத்தில் மட்டும் QR / OTP verify செய்யலாம்)
              </span>
            </div>
          </div>
          {showManualOtpConsole ? <ChevronUp size={16} color="#64748B" /> : <ChevronDown size={16} color="#64748B" />}
        </div>

        {showManualOtpConsole && (
          <div className="animate-fade-in" style={{ marginTop: '0.85rem', paddingTop: '0.85rem', borderTop: '1px solid #F1F5F9' }}>
            <form onSubmit={handleManualOtpVerify} style={{ display: 'flex', gap: '0.5rem', maxWidth: '400px' }}>
              <input
                type="text"
                maxLength={6}
                placeholder="Enter 6-digit OTP..."
                className="input-field"
                value={manualOtp}
                onChange={(e) => setManualOtp(e.target.value.replace(/\D/g, ''))}
                style={{ fontSize: '0.95rem', fontWeight: 800, letterSpacing: '0.15em', textAlign: 'center', padding: '0.45rem' }}
              />
              <button
                type="submit"
                disabled={verifyingOtp || !manualOtp.trim()}
                className="btn btn-primary"
                style={{ padding: '0 1.15rem', fontSize: '0.825rem', fontWeight: 800 }}
              >
                {verifyingOtp ? '...' : 'Verify'}
              </button>
            </form>

            {otpVerifyResult && (
              <div style={{
                marginTop: '0.65rem',
                padding: '0.65rem',
                borderRadius: '8px',
                fontSize: '0.78rem',
                backgroundColor: otpVerifyResult.success ? '#ECFDF5' : '#FEF2F2',
                border: otpVerifyResult.success ? '1px solid #A7F3D0' : '1px solid #FECACA',
                color: otpVerifyResult.success ? '#065F46' : '#991B1B'
              }}>
                {otpVerifyResult.success ? (
                  <div>
                    <strong>✅ Verified Pass:</strong> {otpVerifyResult.visitorPass?.passNumber} - {otpVerifyResult.visitorPass?.visitorName}
                  </div>
                ) : (
                  <div>
                    <strong>❌ Error:</strong> {otpVerifyResult.error || 'Invalid OTP code'}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
};
