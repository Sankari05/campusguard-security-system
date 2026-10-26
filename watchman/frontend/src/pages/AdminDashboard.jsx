import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Users,
  ShieldCheck,
  AlertTriangle,
  Building,
  ArrowUpRight,
  ArrowDownLeft,
  FileText,
  CheckCircle2,
  Phone,
  Printer,
  Sparkles,
  ClipboardCheck,
  Clock,
  Car,
  Package,
  AlertOctagon,
  Check,
  ChevronRight,
  RefreshCw,
  ExternalLink,
  SlidersHorizontal,
  Mail,
  UserPlus,
  Plus,
  Trash2,
  GraduationCap,
  Factory,
  HeartPulse,
  Building2,
  Home,
  BarChart3,
  Activity,
  TrendingUp,
  Gauge,
  Zap,
  CheckCheck
} from 'lucide-react';

export const AdminDashboard = ({ setActiveTab: setAppTab }) => {
  const { language, t, stats, outPasses, parcels, setActiveDashboard } = useAuth();
  const [activeAdminSection, setActiveAdminSection] = useState('overview'); // 'overview', 'guards', 'compliance', 'overdues', 'shifts', 'sectors', 'analytics'
  const [handovers, setHandovers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [supervisorSigned, setSupervisorSigned] = useState(false);
  const [showPrintModal, setShowPrintModal] = useState(false);
  const [notificationSent, setNotificationSent] = useState(null);

  // Cross-Sector Adaptive Engine State
  const [selectedSector, setSelectedSector] = useState(() => {
    return localStorage.getItem('guardmate_active_sector') || 'COLLEGE';
  });
  const [sectorProfiles, setSectorProfiles] = useState([]);
  const [testPassIssued, setTestPassIssued] = useState(null);

  // Gate Congestion & Workload Analytics State
  const [congestionData, setCongestionData] = useState(null);
  const [reserveLaneOpen, setReserveLaneOpen] = useState(false);
  const [floatingGuardDispatched, setFloatingGuardDispatched] = useState(false);


  // Security Guards & Watchmen Roster State
  const [guards, setGuards] = useState(() => {
    const saved = localStorage.getItem('campusguard_custom_guards');
    if (saved) {
      try { return JSON.parse(saved); } catch {}
    }
    return [
      { id: 1, name: 'Ramasamy K.', username: 'watchman1', gate: 'Main Gate 1', phone: '9876543210', shift: 'Morning Shift (06:00 - 14:00)', status: 'ON_DUTY' },
      { id: 2, name: 'Murugan P.', username: 'watchman2', gate: 'North Gate 2', phone: '9876543211', shift: 'Afternoon Shift (14:00 - 22:00)', status: 'SCHEDULED' },
      { id: 3, name: 'Velusamy S.', username: 'watchman3', gate: 'Hostel Gate', phone: '9876543212', shift: 'Night Shift (22:00 - 06:00)', status: 'OFF_DUTY' }
    ];
  });
  const [showAddGuardModal, setShowAddGuardModal] = useState(false);
  const [newGuardName, setNewGuardName] = useState('');
  const [newGuardUsername, setNewGuardUsername] = useState('');
  const [newGuardGate, setNewGuardGate] = useState('Main Gate 1');
  const [newGuardPhone, setNewGuardPhone] = useState('');
  const [newGuardPassword, setNewGuardPassword] = useState('password123');
  const [newGuardShift, setNewGuardShift] = useState('Morning Shift (06:00 - 14:00)');

  const handleAddGuard = (e) => {
    e.preventDefault();
    if (!newGuardName.trim() || !newGuardUsername.trim()) {
      alert(language === 'ta' ? 'வாட்ச்மேன் பெயர் மற்றும் Username உள்ளிடவும்.' : 'Please enter Guard Name and Username.');
      return;
    }
    const newGuard = {
      id: Date.now(),
      name: newGuardName.trim(),
      username: newGuardUsername.trim().toLowerCase(),
      gate: newGuardGate,
      phone: newGuardPhone.trim() || '9876500000',
      shift: newGuardShift,
      status: 'ON_DUTY'
    };
    const updated = [newGuard, ...guards];
    setGuards(updated);
    localStorage.setItem('campusguard_custom_guards', JSON.stringify(updated));
    setShowAddGuardModal(false);
    setNewGuardName('');
    setNewGuardUsername('');
    setNewGuardPhone('');
    setNotificationSent(language === 'ta' ? `புதிய வாட்ச்மேன் "${newGuard.name}" (${newGuard.username}) சேர்க்கப்பட்டார்!` : `New Watchman "${newGuard.name}" (${newGuard.username}) added to Security Roster!`);
    setTimeout(() => setNotificationSent(null), 4000);
  };

  const handleDeleteGuard = (guardId, guardName) => {
    if (window.confirm(language === 'ta' ? `நிச்சயமாக ${guardName} நீக்க வேண்டுமா?` : `Remove ${guardName} from security staff?`)) {
      const updated = guards.filter(g => g.id !== guardId);
      setGuards(updated);
      localStorage.setItem('campusguard_custom_guards', JSON.stringify(updated));
      setNotificationSent(language === 'ta' ? `${guardName} நீக்கப்பட்டார்.` : `${guardName} removed from roster.`);
      setTimeout(() => setNotificationSent(null), 4000);
    }
  };


  // Fetch handover records, sectors, and analytics for admin governance
  useEffect(() => {
    fetchHandovers();
    fetchSectorProfiles();
    fetchCongestionAnalytics();
  }, []);

  const fetchSectorProfiles = async () => {
    try {
      const data = await api.getSectorProfiles();
      setSectorProfiles(data || []);
    } catch (e) {
      console.warn('Error fetching sector profiles:', e);
    }
  };

  const fetchCongestionAnalytics = async () => {
    try {
      const data = await api.getGateCongestionAnalytics();
      setCongestionData(data);
    } catch (e) {
      console.warn('Error fetching congestion data:', e);
    }
  };

  const handleSwitchSector = (secId) => {
    setSelectedSector(secId);
    localStorage.setItem('guardmate_active_sector', secId);
    setNotificationSent(language === 'ta' ? `பாதுகாப்பு கட்டமைப்பு "${secId}" முறைக்கு மாற்றப்பட்டது.` : `GuardMate Security Architecture switched to "${secId}" mode.`);
    setTimeout(() => setNotificationSent(null), 4000);
  };

  const handleIssueTestPass = (sec) => {
    setTestPassIssued({
      id: `PASS-${Date.now().toString().slice(-6)}`,
      sector: sec.name,
      entity: sec.sample_pass_preview.holder,
      passName: sec.sample_pass_preview.pass_type,
      destination: sec.sample_pass_preview.destination,
      validity: sec.sample_pass_preview.valid_until,
      verification: sec.sample_pass_preview.verification,
      issuedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    });
    setNotificationSent(language === 'ta' ? `மாதிரி டிஜிட்டல் பாஸ் உருவாக்கப்பட்டது!` : `Live test ${sec.gate_pass_name} issued successfully!`);
    setTimeout(() => setNotificationSent(null), 4500);
  };

  const handleToggleReserveLane = () => {
    setReserveLaneOpen(!reserveLaneOpen);
    setNotificationSent(!reserveLaneOpen ? 'Reserve Boom Barrier Lane 3 OPENED. Queue delay mitigation active.' : 'Reserve Lane 3 CLOSED. Normal 2-lane operation restored.');
    setTimeout(() => setNotificationSent(null), 4000);
  };

  const handleDispatchGuard = () => {
    setFloatingGuardDispatched(true);
    setNotificationSent('Reserve Guard "Velusamy" dispatched to Main Gate 1 for peak traffic manual assistance.');
    setTimeout(() => setNotificationSent(null), 4000);
  };

  const fetchHandovers = async () => {
    setLoading(true);
    try {
      const data = await api.getShiftHandovers();
      setHandovers(data || []);
    } catch (e) {
      console.warn('Error fetching handovers for admin:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSupervisorSignOff = async (handoverId) => {
    try {
      await api.supervisorSignOffHandover(handoverId, {
        supervisorName: 'Dr. K. Sundararajan (Campus Director / Admin)',
        supervisorNotes: 'Shift handover verified and approved. Security log audited.'
      });
      setSupervisorSigned(true);
      fetchHandovers();
      setTimeout(() => setSupervisorSigned(false), 4000);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSendHODAlert = (dept) => {
    setNotificationSent(`Attendance warning email dispatched to ${dept} HOD & Faculty Advisors.`);
    setTimeout(() => setNotificationSent(null), 4000);
  };

  const handleSendParentAlert = (studentName, rollNo) => {
    setNotificationSent(`Curfew alert SMS & WhatsApp notice sent to parents of ${studentName} (${rollNo}).`);
    setTimeout(() => setNotificationSent(null), 4000);
  };

  // Essential Admin Data: Late Arrival breakdown by Department
  const deptLateData = [
    { dept: 'Computer Science (CSE)', count: 11, pct: 46, reason: 'Bus #14 breakdown at Tambaram junction', hod: 'Prof. Meenakshi' },
    { dept: 'Mechanical Engg (MECH)', count: 6, pct: 25, reason: 'Heavy traffic on GST road', hod: 'Dr. Ramesh' },
    { dept: 'Electronics & Comm (ECE)', count: 4, pct: 17, reason: 'Suburban train delay', hod: 'Dr. Senthil' },
    { dept: 'Civil Engineering', count: 3, pct: 12, reason: 'Personal / Rain delay', hod: 'Prof. Anitha' },
  ];

  // Essential Admin Data: Overdue Out-Passes (Curfew Violations)
  const overduePasses = [
    {
      id: 101,
      rollNumber: '22CS101',
      name: 'Karthik Subramanian',
      dept: 'CSE - 3rd Year',
      destination: 'Ritchie Street, Chennai',
      purpose: 'IoT Hardware Project Components',
      outTime: 'Today 04:00 PM',
      expectedIn: 'Today 08:30 PM',
      overdueDuration: '1h 45m Overdue',
      parentPhone: '+91 98456 12340',
      parentName: 'Subramanian (Father)',
      status: 'OVERDUE'
    },
    {
      id: 102,
      rollNumber: '23ME045',
      name: 'Vigneshwaran K',
      dept: 'Mech - 2nd Year',
      destination: 'Apollo Hospital, Greams Road',
      purpose: 'Medical Specialist Consultation',
      outTime: 'Today 05:00 PM',
      expectedIn: 'Today 09:00 PM',
      overdueDuration: '35m Overdue',
      parentPhone: '+91 98456 12342',
      parentName: 'Kumaresan (Father)',
      status: 'OVERDUE'
    }
  ];

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

      {/* TOP EXECUTIVE BANNER */}
      <div style={{
        background: 'linear-gradient(135deg, #0F172A 0%, #1E293B 100%)',
        borderRadius: '16px',
        padding: '1.5rem 1.75rem',
        color: '#ffffff',
        boxShadow: '0 10px 25px -5px rgba(15, 23, 42, 0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
        border: '1px solid rgba(255, 255, 255, 0.1)'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.4rem' }}>
            <span style={{
              backgroundColor: 'rgba(99, 102, 241, 0.25)',
              border: '1px solid #818CF8',
              color: '#C7D2FE',
              padding: '2px 10px',
              borderRadius: '999px',
              fontSize: '0.72rem',
              fontWeight: 800,
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}>
              🏛️ Campus Executive Oversight
            </span>
            <span style={{ fontSize: '0.78rem', color: '#94A3B8' }}>
              Academic Year 2026-2027 &bull; Real-time Governance
            </span>
          </div>

          <h2 style={{ fontSize: '1.55rem', fontWeight: 900, margin: 0, letterSpacing: '-0.02em', color: '#FFFFFF' }}>
            Campus Administration & Security Oversight
          </h2>
          <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.85rem', color: '#94A3B8' }}>
            Executive pulse for Principal & Campus Director: Student population health, late arrival trends, curfew violations, and guard shift audits.
          </p>
        </div>

        {/* Executive Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setShowPrintModal(true)}
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              color: '#FFFFFF',
              padding: '0.6rem 1rem',
              borderRadius: '10px',
              fontSize: '0.82rem',
              fontWeight: 800,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s ease'
            }}
          >
            <Printer size={15} />
            <span>Export Daily Security Digest</span>
          </button>
        </div>
      </div>

      {/* NOTIFICATION TOAST */}
      {notificationSent && (
        <div className="animate-fade-in" style={{
          backgroundColor: '#ECFDF5',
          border: '1.5px solid #10B981',
          borderRadius: '12px',
          padding: '0.75rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          color: '#065F46',
          fontSize: '0.85rem',
          fontWeight: 700
        }}>
          <CheckCircle2 size={18} color="#10B981" />
          <span>{notificationSent}</span>
        </div>
      )}

      {/* ESSENTIAL ADMIN KPIS - 4 EXECUTIVE CARDS */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '1rem'
      }}>
        {/* KPI 1: Live Campus Population */}
        <div className="card" style={{ padding: '1rem 1.2rem', border: '1px solid #E2E8F0', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 800, color: '#64748B' }}>
              Campus Population Pulse
            </span>
            <div style={{ width: '34px', height: '34px', borderRadius: '8px', backgroundColor: '#EFF6FF', color: '#2563EB', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Users size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#0F172A', lineHeight: 1.1 }}>
            1,842
          </div>
          <div style={{ fontSize: '0.74rem', color: '#64748B', marginTop: '0.35rem' }}>
            <strong style={{ color: '#2563EB' }}>1,620</strong> Students &bull; <strong style={{ color: '#059669' }}>185</strong> Staff &bull; <strong style={{ color: '#D97706' }}>37</strong> Visitors
          </div>
          <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#059669', marginTop: '0.3rem' }}>
            71% Capacity &bull; Safe Occupancy
          </div>
        </div>

        {/* KPI 2: Today's Late Inflow */}
        <div className="card" style={{ padding: '1rem 1.2rem', border: '1px solid #E2E8F0', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 800, color: '#64748B' }}>
              Today's Late Arrivals (&gt;9 AM)
            </span>
            <div style={{ width: '34px', height: '34px', borderRadius: '8px', backgroundColor: '#FEF3C7', color: '#D97706', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Clock size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#D97706', lineHeight: 1.1 }}>
            24 <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#64748B' }}>Students</span>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#64748B', marginTop: '0.35rem' }}>
            Top Dept: <strong>CSE (11)</strong>, MECH (6), ECE (4)
          </div>
          <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#DC2626', marginTop: '0.3rem' }}>
            Cutoff Policy: 09:00 AM Gate Lock
          </div>
        </div>

        {/* KPI 3: Curfew Overdues (Critical Safety) */}
        <div className="card" style={{
          padding: '1rem 1.2rem',
          border: '1.5px solid #FECACA',
          backgroundColor: '#FFF5F5',
          borderRadius: '14px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 800, color: '#991B1B' }}>
              Curfew Overdues (Violations)
            </span>
            <div style={{ width: '34px', height: '34px', borderRadius: '8px', backgroundColor: '#FEE2E2', color: '#DC2626', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <AlertTriangle size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#DC2626', lineHeight: 1.1 }}>
            {overduePasses.length} <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#991B1B' }}>Unreturned</span>
          </div>
          <div style={{ fontSize: '0.74rem', color: '#7F1D1D', marginTop: '0.35rem' }}>
            22CS101 (1h 45m past curfew)
          </div>
          <div style={{ fontSize: '0.7rem', fontWeight: 800, color: '#DC2626', marginTop: '0.3rem' }}>
            ⚠️ Disciplinary Review Required
          </div>
        </div>

        {/* KPI 4: Guard Shift Handover Governance */}
        <div className="card" style={{ padding: '1rem 1.2rem', border: '1px solid #E2E8F0', borderRadius: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 800, color: '#64748B' }}>
              Guard Shift Governance
            </span>
            <div style={{ width: '34px', height: '34px', borderRadius: '8px', backgroundColor: '#ECFDF5', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ClipboardCheck size={18} />
            </div>
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: 900, color: '#065F46', lineHeight: 1.1 }}>
            Gate 1 &bull; Audited
          </div>
          <div style={{ fontSize: '0.74rem', color: '#64748B', marginTop: '0.35rem' }}>
            Ramasamy &rarr; Murugan (Shift Handover)
          </div>
          <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#059669', marginTop: '0.3rem' }}>
            Checklist 100% OK &bull; 0 Unresolved Threats
          </div>
        </div>
      </div>

      {/* SECTION NAVIGATION TABS FOR ADMIN */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid #E2E8F0',
        gap: '0.5rem'
      }}>
        {[
          { id: 'overview', label: 'Executive Overview', icon: Building },
          { id: 'sectors', label: 'Cross-Sector Adaptive Engine (5)', icon: SlidersHorizontal },
          { id: 'analytics', label: 'Gate Congestion & Workload', icon: BarChart3 },
          { id: 'guards', label: `Security Staff & Watchmen (${guards.length})`, icon: ShieldCheck },
          { id: 'compliance', label: 'Late Arrivals & Dept Compliance', icon: Clock },
          { id: 'overdues', label: `Curfew Overdues (${overduePasses.length})`, icon: AlertTriangle, badgeColor: '#DC2626' },
          { id: 'shifts', label: 'Guard Shift Handover Audit', icon: ClipboardCheck }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeAdminSection === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveAdminSection(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '0.75rem 1.25rem',
                border: 'none',
                background: 'none',
                borderBottom: isActive ? '3px solid #0F172A' : '3px solid transparent',
                color: isActive ? '#0F172A' : '#64748B',
                fontWeight: isActive ? 800 : 600,
                fontSize: '0.88rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <Icon size={16} color={isActive ? '#0F172A' : '#64748B'} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB: ADAPTIVE CROSS-SECTOR WORKFLOWS */}
      {activeAdminSection === 'sectors' && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Header Banner */}
          <div className="card" style={{
            background: 'linear-gradient(135deg, #1E1B4B 0%, #312E81 100%)',
            color: '#FFFFFF',
            padding: '1.5rem',
            border: '1px solid #4338CA',
            borderRadius: '16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.35rem' }}>
                <span style={{ backgroundColor: '#4F46E5', color: '#EEF2FF', padding: '3px 10px', borderRadius: '12px', fontSize: '0.72rem', fontWeight: 800 }}>
                  ENV-ADAPTIVE ARCHITECTURE
                </span>
                <span style={{ fontSize: '0.8rem', color: '#C7D2FE' }}>
                  Cross-Sector Re-Configurability
                </span>
              </div>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 900, margin: 0 }}>
                {language === 'ta' ? 'சுற்றுச்சூழல் ஏற்பு பாதுகாப்பு இயந்திரம் (5 களங்கள்)' : 'Adaptive Cross-Sector Workflows & Compliance Engine'}
              </h2>
              <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.85rem', color: '#E0E7FF', maxWidth: '720px', lineHeight: 1.45 }}>
                {language === 'ta'
                  ? 'GuardMate வெவ்வேறு களங்களுக்கு (கல்லூரி, தொழிற்சாலை, மருத்துவமனை, ஐடி பார்க், குடியிருப்பு) தானாகவே படிவங்கள், விதிகள் மற்றும் சொற்களை மாற்றியமைக்கிறது.'
                  : 'GuardMate eliminates fragmented silos by dynamically adapting verification chains, compliance rules, and digital passes across College, Industrial Plant, Hospital, Corporate IT Park, and Gated Township archetypes.'}
              </p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.75rem', color: '#C7D2FE', textTransform: 'uppercase', fontWeight: 700 }}>
                Active Profile
              </div>
              <div style={{ fontSize: '1.25rem', fontWeight: 900, color: '#38BDF8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCheck size={20} color="#38BDF8" />
                <span>{selectedSector} MODE</span>
              </div>
            </div>
          </div>

          {/* 5 Sector Archetype Selector Cards */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
            gap: '1rem'
          }}>
            {[
              { id: 'COLLEGE', name: 'Educational Campus', icon: GraduationCap, entity: 'Students & Faculty', badge: 'College / School', color: '#2563EB', pass: 'Student Outpass' },
              { id: 'FACTORY', name: 'Industrial Hub', icon: Factory, entity: 'Contractors & Freight', badge: 'Plant / Warehouse', color: '#D97706', pass: 'Material RGP/NRGP' },
              { id: 'HOSPITAL', name: 'Healthcare Facility', icon: HeartPulse, entity: 'Patients & Attendants', badge: 'Hospital / Clinic', color: '#DC2626', pass: 'Attendant 24/7 Badge' },
              { id: 'OFFICE', name: 'Corporate IT Park', icon: Building2, entity: 'Employees & Guests', badge: 'Tech Park / SEZ', color: '#7C3AED', pass: 'Visitor NDA Pass' },
              { id: 'SOCIETY', name: 'Gated Residential', icon: Home, entity: 'Residents & Deliveries', badge: 'Township / Villa', color: '#059669', pass: 'Guest Pass / Staff' }
            ].map((sec) => {
              const IconComp = sec.icon;
              const isSelected = selectedSector === sec.id;
              return (
                <div
                  key={sec.id}
                  onClick={() => handleSwitchSector(sec.id)}
                  style={{
                    backgroundColor: isSelected ? '#FFFFFF' : '#F8FAFC',
                    border: isSelected ? `2.5px solid ${sec.color}` : '1.5px solid #E2E8F0',
                    borderRadius: '14px',
                    padding: '1.1rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: isSelected ? `0 8px 20px -4px ${sec.color}33` : 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    position: 'relative'
                  }}
                >
                  {isSelected && (
                    <div style={{
                      position: 'absolute',
                      top: '10px',
                      right: '10px',
                      backgroundColor: sec.color,
                      color: '#ffffff',
                      borderRadius: '50%',
                      width: '22px',
                      height: '22px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}>
                      <Check size={14} strokeWidth={3} />
                    </div>
                  )}

                  <div>
                    <div style={{
                      width: '40px',
                      height: '40px',
                      borderRadius: '10px',
                      backgroundColor: `${sec.color}15`,
                      color: sec.color,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      marginBottom: '0.75rem'
                    }}>
                      <IconComp size={22} />
                    </div>
                    <div style={{ fontSize: '0.7rem', fontWeight: 800, color: sec.color, textTransform: 'uppercase' }}>
                      {sec.badge}
                    </div>
                    <div style={{ fontSize: '1rem', fontWeight: 900, color: '#0F172A', marginTop: '2px' }}>
                      {sec.name}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '4px' }}>
                      Entity: <strong>{sec.entity}</strong>
                    </div>
                  </div>

                  <div style={{ marginTop: '1rem', paddingTop: '0.65rem', borderTop: '1px solid #E2E8F0', fontSize: '0.72rem', color: '#475569' }}>
                    Default Pass: <strong style={{ color: '#0F172A' }}>{sec.pass}</strong>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Detailed Sector Profile Deep-Dive */}
          {(() => {
            const currentProfile = sectorProfiles.find(p => p.sector_id === selectedSector) || {
              sector_id: selectedSector,
              name: selectedSector === 'COLLEGE' ? 'Higher Education & Campus' : `${selectedSector} Profile`,
              description: 'Real-world dynamic rules, permissions and gate pass schema adapted for this facility archetype.',
              primary_entity: 'Campus Population',
              gate_pass_name: 'Standard Digital Gate Pass',
              key_workflows: [
                'Automated Ingress Verification & Barrier Integration',
                'Curfew / Expiry Departure Alerts',
                'Emergency First-Responder Green Corridor Priority'
              ],
              compliance_rules: [
                'Identity verification mandatory prior to pass issuance',
                'Authorized host approval logged in immutable audit trail'
              ],
              stat_labels: {
                primary_count: 'Active Badged Population',
                movement_count: 'Daily Gate Movements',
                overdue_count: 'Compliance Exceptions'
              },
              sample_pass_preview: {
                pass_type: 'Digital Security Pass',
                holder: 'Authorized Entrant',
                destination: 'Main Campus Facility',
                valid_until: 'Today 08:30 PM',
                verification: 'Security Supervisor Approved'
              }
            };

            return (
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.25rem', alignItems: 'start' }}>
                {/* Left Column: Workflows, Compliance & Terminology */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {/* Card 1: Key Automated Workflows */}
                  <div className="card" style={{ padding: '1.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.85rem' }}>
                      <SlidersHorizontal size={18} color="#2563EB" />
                      <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 900, color: '#0F172A' }}>
                        Automated Workflows for {currentProfile.name}
                      </h4>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                      {currentProfile.key_workflows?.map((wf, idx) => (
                        <div key={idx} style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          padding: '0.65rem 0.85rem',
                          backgroundColor: '#F8FAFC',
                          borderRadius: '8px',
                          border: '1px solid #E2E8F0',
                          fontSize: '0.82rem',
                          color: '#1E293B'
                        }}>
                          <CheckCircle2 size={16} color="#059669" style={{ flexShrink: 0 }} />
                          <span style={{ fontWeight: 600 }}>{wf}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Card 2: Sector Compliance & Enforcement Rules */}
                  <div className="card" style={{ padding: '1.25rem', border: '1.5px solid #FDE68A', backgroundColor: '#FFFDF5' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.85rem' }}>
                      <AlertTriangle size={18} color="#D97706" />
                      <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 900, color: '#92400E' }}>
                        Mandatory Compliance Rules & Guard Checks
                      </h4>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                      {currentProfile.compliance_rules?.map((rule, idx) => (
                        <div key={idx} style={{
                          display: 'flex',
                          alignItems: 'start',
                          gap: '8px',
                          fontSize: '0.8rem',
                          color: '#78350F',
                          lineHeight: 1.4
                        }}>
                          <span style={{ color: '#D97706', fontWeight: 900 }}>&bull;</span>
                          <span>{rule}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Card 3: Dynamic Metric Re-labeling */}
                  <div className="card" style={{ padding: '1.25rem' }}>
                    <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', fontWeight: 800, color: '#475569' }}>
                      Dynamic Metric Terminology Adaptation
                    </h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem' }}>
                      <div style={{ padding: '0.6rem', backgroundColor: '#EFF6FF', borderRadius: '8px', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: '#1E40AF', fontWeight: 700 }}>Primary Counter</div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 900, color: '#0F172A', marginTop: '2px' }}>
                          {currentProfile.stat_labels?.primary_count || 'Registered Population'}
                        </div>
                      </div>
                      <div style={{ padding: '0.6rem', backgroundColor: '#ECFDF5', borderRadius: '8px', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: '#065F46', fontWeight: 700 }}>Pass Movements</div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 900, color: '#0F172A', marginTop: '2px' }}>
                          {currentProfile.stat_labels?.movement_count || 'Active Passes'}
                        </div>
                      </div>
                      <div style={{ padding: '0.6rem', backgroundColor: '#FEF2F2', borderRadius: '8px', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.7rem', color: '#991B1B', fontWeight: 700 }}>Risk Exceptions</div>
                        <div style={{ fontSize: '0.78rem', fontWeight: 900, color: '#0F172A', marginTop: '2px' }}>
                          {currentProfile.stat_labels?.overdue_count || 'Violations'}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right Column: Live Dynamic Pass Simulator */}
                <div className="card" style={{
                  padding: '1.5rem',
                  border: '2px solid #2563EB',
                  borderRadius: '16px',
                  backgroundColor: '#FFFFFF',
                  boxShadow: '0 10px 25px -5px rgba(37, 99, 235, 0.15)'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <div>
                      <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#2563EB', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Live Digital Pass Generator
                      </span>
                      <h3 style={{ margin: '2px 0 0 0', fontSize: '1.15rem', fontWeight: 900, color: '#0F172A' }}>
                        {currentProfile.gate_pass_name}
                      </h3>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleIssueTestPass(currentProfile)}
                      className="btn btn-primary"
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', padding: '0.5rem 0.9rem', fontWeight: 800 }}
                    >
                      <Sparkles size={15} />
                      <span>Issue Live Test Pass</span>
                    </button>
                  </div>

                  {/* Rendered Physical / Mobile Pass Card */}
                  <div style={{
                    border: '1.5px dashed #CBD5E1',
                    borderRadius: '14px',
                    padding: '1.25rem',
                    backgroundColor: '#F8FAFC',
                    position: 'relative'
                  }}>
                    {/* Header of Pass */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', paddingBottom: '0.75rem', marginBottom: '0.85rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: '#0F172A', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 900 }}>
                          GM
                        </div>
                        <div>
                          <div style={{ fontSize: '0.75rem', fontWeight: 900, color: '#0F172A' }}>GUARDMATE SECURE PASS</div>
                          <div style={{ fontSize: '0.65rem', color: '#64748B' }}>Domain: {currentProfile.name}</div>
                        </div>
                      </div>
                      <span style={{ backgroundColor: '#DCFCE7', color: '#166534', padding: '3px 8px', borderRadius: '6px', fontSize: '0.7rem', fontWeight: 800 }}>
                        ● VERIFIED ACTIVE
                      </span>
                    </div>

                    {/* Pass Fields */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '1rem' }}>
                      <div>
                        <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700 }}>PASS HOLDER</div>
                        <div style={{ fontSize: '0.88rem', fontWeight: 800, color: '#0F172A' }}>
                          {testPassIssued?.entity || currentProfile.sample_pass_preview?.holder}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700 }}>PASS CLASSIFICATION</div>
                        <div style={{ fontSize: '0.88rem', fontWeight: 800, color: '#2563EB' }}>
                          {testPassIssued?.passName || currentProfile.sample_pass_preview?.pass_type}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700 }}>AUTHORIZED DESTINATION</div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155' }}>
                          {testPassIssued?.destination || currentProfile.sample_pass_preview?.destination}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700 }}>VALIDITY EXPIRY</div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#DC2626' }}>
                          {testPassIssued?.validity || currentProfile.sample_pass_preview?.valid_until}
                        </div>
                      </div>
                    </div>

                    {/* Barcode & Security Seal */}
                    <div style={{
                      backgroundColor: '#FFFFFF',
                      borderRadius: '8px',
                      padding: '0.75rem',
                      border: '1px solid #E2E8F0',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <div>
                        <div style={{ fontSize: '0.65rem', color: '#64748B', fontWeight: 700 }}>AUTHORIZATION STAMP</div>
                        <div style={{ fontSize: '0.75rem', fontWeight: 800, color: '#059669' }}>
                          ✓ {testPassIssued?.verification || currentProfile.sample_pass_preview?.verification}
                        </div>
                        <div style={{ fontSize: '0.65rem', color: '#94A3B8', marginTop: '2px' }}>
                          ID: {testPassIssued?.id || 'GM-984210'} &bull; Issued: {testPassIssued?.issuedAt || 'Live Auto'}
                        </div>
                      </div>
                      {/* Barcode graphic */}
                      <div style={{ display: 'flex', gap: '3px', alignItems: 'center', height: '28px' }}>
                        {[4, 2, 5, 2, 6, 3, 2, 5, 3, 4, 2, 5, 2, 6, 3].map((h, i) => (
                          <div key={i} style={{ width: '2.5px', height: `${h * 4.5}px`, backgroundColor: '#0F172A' }} />
                        ))}
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: '0.85rem', fontSize: '0.75rem', color: '#64748B', textAlign: 'center' }}>
                    Scan QR / Barcode at any boom barrier or pedestrian turnstile for instant 1-second gate grant.
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* TAB: GATE CONGESTION & WORKLOAD ANALYTICS */}
      {activeAdminSection === 'analytics' && (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Header Banner */}
          <div className="card" style={{
            background: 'linear-gradient(135deg, #064E3B 0%, #065F46 100%)',
            color: '#FFFFFF',
            padding: '1.5rem',
            border: '1px solid #059669',
            borderRadius: '16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem'
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.35rem' }}>
                <span style={{ backgroundColor: '#10B981', color: '#064E3B', padding: '3px 10px', borderRadius: '12px', fontSize: '0.72rem', fontWeight: 800 }}>
                  TELEMETRY ENGINE
                </span>
                <span style={{ fontSize: '0.8rem', color: '#A7F3D0' }}>
                  Live ANPR & Queue Analytics
                </span>
              </div>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 900, margin: 0 }}>
                {language === 'ta' ? 'கேட் நெரிசல் & பணிச்சுமை பகுப்பாய்வு' : 'Gate Congestion & Workload Throughput Analytics'}
              </h2>
              <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.85rem', color: '#D1FAE5', maxWidth: '720px', lineHeight: 1.45 }}>
                {language === 'ta'
                  ? 'வாகனங்கள் மற்றும் பார்வையாளர்கள் கேட் கடக்கும் வேகம், உச்ச நேர நெரிசல் கணிப்பு மற்றும் கூடுதல் வாட்ச்மேன் தேவை தானாக கணக்கிடப்படுகிறது.'
                  : 'Real-time telemetry measuring entry/exit throughput, queue clearance speedups with automated ANPR, and predictive staffing recommendations to avoid peak-hour bottleneck delays.'}
              </p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.75rem', color: '#A7F3D0', textTransform: 'uppercase', fontWeight: 700 }}>
                Automation Boost
              </div>
              <div style={{ fontSize: '1.35rem', fontWeight: 900, color: '#6EE7B7' }}>
                92.8% Time Saved
              </div>
            </div>
          </div>

          {/* 4 Analytics KPIs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
            <div className="card" style={{ padding: '1rem 1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#64748B' }}>Hourly Ingress Rate</span>
                <ArrowDownLeft size={18} color="#2563EB" />
              </div>
              <div style={{ fontSize: '1.85rem', fontWeight: 900, color: '#0F172A' }}>
                {congestionData?.current_ingress_rate_per_hour || 380}
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#64748B', marginLeft: '6px' }}>pass/hr</span>
              </div>
              <div style={{ fontSize: '0.74rem', color: '#D97706', fontWeight: 800, marginTop: '0.35rem' }}>
                ▲ Morning Rush Window (08:00 - 09:30 AM)
              </div>
            </div>

            <div className="card" style={{ padding: '1rem 1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#64748B' }}>Hourly Egress Rate</span>
                <ArrowUpRight size={18} color="#059669" />
              </div>
              <div style={{ fontSize: '1.85rem', fontWeight: 900, color: '#0F172A' }}>
                {congestionData?.current_egress_rate_per_hour || 45}
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#64748B', marginLeft: '6px' }}>pass/hr</span>
              </div>
              <div style={{ fontSize: '0.74rem', color: '#059669', fontWeight: 700, marginTop: '0.35rem' }}>
                Normal exit flow (Dispersal at 04:30 PM)
              </div>
            </div>

            <div className="card" style={{ padding: '1rem 1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#64748B' }}>Boom Barrier Lanes</span>
                <Gauge size={18} color="#7C3AED" />
              </div>
              <div style={{ fontSize: '1.85rem', fontWeight: 900, color: '#7C3AED' }}>
                {reserveLaneOpen ? '3 Active' : '2 Active + 1 Stby'}
              </div>
              <div style={{ fontSize: '0.74rem', color: reserveLaneOpen ? '#059669' : '#D97706', fontWeight: 800, marginTop: '0.35rem' }}>
                {reserveLaneOpen ? '● Reserve Lane 3 Active' : '⚠️ Recommendation: Open Lane 3'}
              </div>
            </div>

            <div className="card" style={{ padding: '1rem 1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 800, color: '#64748B' }}>Clearance Latency</span>
                <Zap size={18} color="#059669" />
              </div>
              <div style={{ fontSize: '1.85rem', fontWeight: 900, color: '#059669' }}>
                3.2s
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#64748B', marginLeft: '6px' }}>vs 45s Manual</span>
              </div>
              <div style={{ fontSize: '0.74rem', color: '#059669', fontWeight: 800, marginTop: '0.35rem' }}>
                ✓ Zero congestion backlog
              </div>
            </div>
          </div>

          {/* Hourly Ingress Throughput Bar Chart */}
          <div className="card" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 900, color: '#0F172A' }}>
                  24-Hour Campus Ingress Traffic Distribution Curve
                </h3>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: '#64748B' }}>
                  Hourly flow measured across Main Gate 1 and North Gate 2 cameras with automated ANPR classification
                </p>
              </div>
              <div style={{ display: 'flex', gap: '12px', fontSize: '0.78rem', fontWeight: 700 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: '#2563EB' }} />
                  <span>Normal Inflow</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: '#DC2626' }} />
                  <span>Peak Rush (&gt;350/hr)</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: '12px', height: '12px', borderRadius: '3px', backgroundColor: '#10B981' }} />
                  <span>Outflow Dispersal</span>
                </div>
              </div>
            </div>

            {/* Custom Interactive CSS Bar Visualization */}
            <div style={{
              display: 'flex',
              alignItems: 'flex-end',
              gap: '12px',
              height: '180px',
              paddingTop: '20px',
              borderBottom: '2px solid #CBD5E1',
              paddingBottom: '8px'
            }}>
              {(congestionData?.hourly_distribution || [
                { hour: '06 AM', inflow: 42, outflow: 8 },
                { hour: '07 AM', inflow: 95, outflow: 18 },
                { hour: '08 AM', inflow: 380, outflow: 45 },
                { hour: '09 AM', inflow: 410, outflow: 62 },
                { hour: '10 AM', inflow: 110, outflow: 78 },
                { hour: '11 AM', inflow: 85, outflow: 92 },
                { hour: '12 PM', inflow: 120, outflow: 145 },
                { hour: '01 PM', inflow: 150, outflow: 160 },
                { hour: '02 PM', inflow: 75, outflow: 90 },
                { hour: '03 PM', inflow: 95, outflow: 110 },
                { hour: '04 PM', inflow: 115, outflow: 310 },
                { hour: '05 PM', inflow: 82, outflow: 395 },
                { hour: '06 PM', inflow: 65, outflow: 220 },
                { hour: '07 PM', inflow: 45, outflow: 85 },
                { hour: '08 PM', inflow: 35, outflow: 40 }
              ]).map((item, idx) => {
                const maxVal = 420;
                const inHeightPct = Math.min(100, Math.round((item.inflow / maxVal) * 100));
                const isPeak = item.inflow >= 350;
                return (
                  <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                    <div style={{ fontSize: '0.65rem', fontWeight: 800, color: isPeak ? '#DC2626' : '#64748B', marginBottom: '4px' }}>
                      {item.inflow}
                    </div>
                    <div
                      title={`${item.hour}: ${item.inflow} entries, ${item.outflow} exits`}
                      style={{
                        width: '100%',
                        maxWidth: '34px',
                        height: `${inHeightPct}%`,
                        backgroundColor: isPeak ? '#DC2626' : '#2563EB',
                        borderRadius: '6px 6px 0 0',
                        transition: 'all 0.3s ease',
                        boxShadow: isPeak ? '0 4px 10px rgba(220, 38, 38, 0.4)' : 'none'
                      }}
                    />
                    <div style={{ fontSize: '0.68rem', fontWeight: 700, color: '#64748B', marginTop: '6px', whiteSpace: 'nowrap' }}>
                      {item.hour.replace(':00', '')}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* AI Staffing Advisor & Lane Optimization Controls */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '1.25rem' }}>
            {/* AI Advisor Card */}
            <div className="card" style={{
              padding: '1.4rem',
              backgroundColor: '#F0FDF4',
              border: '1.5px solid #86EFAC',
              borderRadius: '14px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.6rem' }}>
                  <Sparkles size={20} color="#059669" />
                  <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 900, color: '#065F46' }}>
                    AI Guard Workload & Peak Staffing Forecast
                  </h4>
                </div>
                <p style={{ margin: '0 0 1rem 0', fontSize: '0.85rem', color: '#166534', lineHeight: 1.5 }}>
                  {congestionData?.staffing_forecast || 'Deploy 1 additional reserve watchman to Main Gate 1 during 08:00-09:30 AM window to maintain sub-4s clearance.'}
                </p>
                <div style={{ fontSize: '0.78rem', color: '#065F46', padding: '0.65rem 0.85rem', backgroundColor: '#FFFFFF', borderRadius: '8px', border: '1px solid #BBF7D0' }}>
                  <strong>Queue Mitigation Status:</strong> {reserveLaneOpen ? '✓ Reserve Lane 3 is handling 35% of morning bus and car queue.' : '⚠️ Backlog risk detected at Lane 1. Action recommended.'}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={handleToggleReserveLane}
                  className={reserveLaneOpen ? "btn btn-secondary" : "btn btn-primary"}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800, padding: '0.65rem 1.15rem' }}
                >
                  <Gauge size={16} />
                  <span>{reserveLaneOpen ? 'Close Reserve Barrier Lane 3' : 'Open Reserve Barrier Lane 3 Now'}</span>
                </button>

                <button
                  type="button"
                  onClick={handleDispatchGuard}
                  disabled={floatingGuardDispatched}
                  className="btn btn-secondary"
                  style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800, padding: '0.65rem 1.15rem' }}
                >
                  <Users size={16} />
                  <span>{floatingGuardDispatched ? '✓ Guard Velusamy Deployed' : 'Dispatch Floating Guard'}</span>
                </button>
              </div>
            </div>

            {/* Clearance Speed Comparison */}
            <div className="card" style={{ padding: '1.4rem' }}>
              <h4 style={{ margin: '0 0 0.85rem 0', fontSize: '0.95rem', fontWeight: 900, color: '#0F172A' }}>
                Throughput Speedup Benchmarking
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ padding: '0.75rem', backgroundColor: '#ECFDF5', borderRadius: '8px', border: '1px solid #A7F3D0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 800 }}>
                    <span style={{ color: '#065F46' }}>Automated ANPR Camera</span>
                    <span style={{ color: '#059669' }}>3.2s / check-in</span>
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#047857', marginTop: '2px' }}>
                    100% contactless OCR license plate reading
                  </div>
                </div>

                <div style={{ padding: '0.75rem', backgroundColor: '#EFF6FF', borderRadius: '8px', border: '1px solid #BFDBFE' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 800 }}>
                    <span style={{ color: '#1E40AF' }}>Self-Service Digital Pass QR</span>
                    <span style={{ color: '#2563EB' }}>12.5s / check-in</span>
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#1D4ED8', marginTop: '2px' }}>
                    72% faster than manual visitor register
                  </div>
                </div>

                <div style={{ padding: '0.75rem', backgroundColor: '#FEF2F2', borderRadius: '8px', border: '1px solid #FECACA' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 800 }}>
                    <span style={{ color: '#991B1B' }}>Legacy Paper Register</span>
                    <span style={{ color: '#DC2626' }}>45.0s / check-in</span>
                  </div>
                  <div style={{ fontSize: '0.7rem', color: '#B91C1C', marginTop: '2px' }}>
                    Severe bottleneck &amp; illegible manual handwriting
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB: SECURITY STAFF & WATCHMEN MANAGEMENT */}
      {activeAdminSection === 'guards' && (

        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Header Card with Add Watchman Button */}
          <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 900, color: '#0F172A', margin: 0 }}>
                {language === 'ta' ? 'கல்லூரி வாட்ச்மேன் & பாதுகாப்புப் பணியாளர்கள்' : 'Campus Security Guards & Watchman Management'}
              </h3>
              <p style={{ margin: '3px 0 0 0', fontSize: '0.82rem', color: '#64748B' }}>
                {language === 'ta' ? 'அனைத்து கேட் வாட்ச்மேன்களை நிர்வகிக்கலாம் மற்றும் புதிய வாட்ச்மேனைச் சேர்க்கலாம்.' : 'Manage security personnel deployed across Main Gate 1, North Gate 2, and Hostel checkpoints.'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowAddGuardModal(true)}
              className="btn btn-primary"
              style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0.65rem 1.25rem', fontWeight: 800 }}
            >
              <UserPlus size={18} />
              <span>{language === 'ta' ? '+ புதிய வாட்ச்மேனைச் சேர்' : '+ Add New Watchman'}</span>
            </button>
          </div>

          {/* Guards Grid / Table */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1.5px solid #E2E8F0', color: '#475569', fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  <th style={{ padding: '0.85rem 1.25rem' }}>Guard Name</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Login Username</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Assigned Post</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Contact Phone</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Current Shift</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Status</th>
                  <th style={{ padding: '0.85rem 1.25rem', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {guards.map((g) => (
                  <tr key={g.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                    <td style={{ padding: '1rem 1.25rem', fontWeight: 800, color: '#0F172A' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{ width: '36px', height: '36px', borderRadius: '50%', backgroundColor: '#EFF6FF', color: '#2563EB', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900 }}>
                          {g.name.charAt(0)}
                        </div>
                        <div>
                          <div>{g.name}</div>
                          <div style={{ fontSize: '0.74rem', color: '#64748B', fontWeight: 500 }}>ID: SEC-{g.id.toString().slice(-4)}</div>
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '1rem', fontFamily: 'monospace', fontWeight: 700, color: '#2563EB' }}>
                      @{g.username}
                    </td>
                    <td style={{ padding: '1rem', fontWeight: 600, color: '#334155' }}>
                      🏢 {g.gate}
                    </td>
                    <td style={{ padding: '1rem', color: '#64748B' }}>
                      📞 {g.phone}
                    </td>
                    <td style={{ padding: '1rem', fontSize: '0.8rem', color: '#475569' }}>
                      {g.shift}
                    </td>
                    <td style={{ padding: '1rem' }}>
                      <span style={{
                        padding: '3px 10px',
                        borderRadius: '999px',
                        fontSize: '0.72rem',
                        fontWeight: 800,
                        backgroundColor: g.status === 'ON_DUTY' ? '#DCFCE7' : '#F1F5F9',
                        color: g.status === 'ON_DUTY' ? '#15803D' : '#64748B'
                      }}>
                        {g.status === 'ON_DUTY' ? '● ON DUTY' : g.status}
                      </span>
                    </td>
                    <td style={{ padding: '1rem 1.25rem', textAlign: 'right' }}>
                      <button
                        type="button"
                        onClick={() => handleDeleteGuard(g.id, g.name)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#EF4444',
                          cursor: 'pointer',
                          padding: '6px',
                          borderRadius: '6px',
                          display: 'inline-flex',
                          alignItems: 'center'
                        }}
                        title="Remove Guard"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 1: EXECUTIVE OVERVIEW */}
      {activeAdminSection === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: '1.25rem' }}>

          {/* Left Column: Department Tardiness Breakdown */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                  Department-Wise Late Arrivals Breakdown
                </h3>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: '#64748B' }}>
                  Students checked in after 09:00 AM cutoff today (Total: 24)
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleSendHODAlert('All')}
                className="btn btn-secondary"
                style={{ fontSize: '0.78rem', padding: '0.45rem 0.85rem' }}
              >
                <Mail size={14} />
                <span>Notify All HODs</span>
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
              {deptLateData.map((d, idx) => (
                <div key={idx} style={{
                  padding: '0.85rem 1rem',
                  borderRadius: '10px',
                  backgroundColor: '#F8FAFC',
                  border: '1px solid #E2E8F0'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                    <div>
                      <span style={{ fontSize: '0.85rem', fontWeight: 800, color: '#1E293B' }}>
                        {d.dept}
                      </span>
                      <span style={{ fontSize: '0.74rem', color: '#64748B', marginLeft: '6px' }}>
                        (HOD: {d.hod})
                      </span>
                    </div>
                    <span style={{ fontSize: '0.85rem', fontWeight: 900, color: '#D97706' }}>
                      {d.count} Students ({d.pct}%)
                    </span>
                  </div>

                  {/* Progress Meter */}
                  <div style={{ width: '100%', height: '8px', backgroundColor: '#E2E8F0', borderRadius: '999px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${d.pct}%`,
                      height: '100%',
                      backgroundColor: d.pct > 30 ? '#DC2626' : '#D97706',
                      borderRadius: '999px'
                    }} />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.4rem' }}>
                    <span style={{ fontSize: '0.72rem', color: '#64748B' }}>
                      Primary Reason: <em>{d.reason}</em>
                    </span>
                    <button
                      type="button"
                      onClick={() => handleSendHODAlert(d.dept)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#2563EB',
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        padding: 0
                      }}
                    >
                      Email HOD &rarr;
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Column: Live Curfew Overdue Alerts & Guard Audit Card */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

            {/* Overdue Passes High Alert */}
            <div className="card" style={{ border: '2px solid #FECACA', backgroundColor: '#FEF2F2' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.6rem' }}>
                <AlertOctagon size={20} color="#DC2626" />
                <h4 style={{ margin: 0, fontSize: '0.98rem', fontWeight: 800, color: '#991B1B' }}>
                  Safety Alert: {overduePasses.length} Students Overdue Past Curfew
                </h4>
              </div>
              <p style={{ margin: '0 0 0.85rem 0', fontSize: '0.78rem', color: '#7F1D1D', lineHeight: 1.45 }}>
                Students who left on approved out-passes but have not checked in back at the gate. Immediate contact recommended.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {overduePasses.map((p) => (
                  <div key={p.id} style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '8px',
                    padding: '0.7rem 0.85rem',
                    border: '1px solid #FECACA'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>
                          {p.name} ({p.rollNumber})
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#64748B' }}>
                          {p.dept} &bull; Expected: {p.expectedIn}
                        </div>
                      </div>
                      <span className="badge badge-red" style={{ fontSize: '0.7rem' }}>
                        {p.overdueDuration}
                      </span>
                    </div>

                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                      <button
                        type="button"
                        onClick={() => handleSendParentAlert(p.name, p.rollNumber)}
                        style={{
                          flex: 1,
                          padding: '4px 8px',
                          borderRadius: '6px',
                          backgroundColor: '#FEE2E2',
                          border: '1px solid #FCA5A5',
                          color: '#991B1B',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          cursor: 'pointer'
                        }}
                      >
                        Call Parent ({p.parentPhone})
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Shift Handover Status */}
            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ClipboardCheck size={18} color="#059669" />
                  <h4 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: '#0F172A' }}>
                    Gate 1 Shift Handover Status
                  </h4>
                </div>
                <span className="badge badge-green">Morning Shift A</span>
              </div>

              <div style={{ fontSize: '0.82rem', color: '#334155', lineHeight: 1.5, marginBottom: '0.75rem' }}>
                <div><strong>Outgoing Guard:</strong> Ramasamy (Main Gate)</div>
                <div><strong>Incoming Guard:</strong> Murugan (Gate Guard - Shift B)</div>
                <div><strong>Handover Checklist:</strong> Hydraulic Barrier, ANPR Camera, Keys, 4 Radios (100% Verified)</div>
                <div><strong>Gate Parcel Desk:</strong> 2 Packages securely logged in Locker #2</div>
              </div>

              <button
                type="button"
                onClick={() => handleSupervisorSignOff(handovers[0]?.id || 1001)}
                style={{
                  width: '100%',
                  padding: '0.65rem',
                  borderRadius: '8px',
                  backgroundColor: supervisorSigned ? '#ECFDF5' : '#0F172A',
                  color: supervisorSigned ? '#065F46' : '#FFFFFF',
                  border: supervisorSigned ? '1.5px solid #10B981' : 'none',
                  fontSize: '0.82rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                {supervisorSigned ? (
                  <>
                    <CheckCircle2 size={16} color="#10B981" />
                    <span>Supervisor Audit Approved!</span>
                  </>
                ) : (
                  <>
                    <Check size={16} />
                    <span>Supervisor Sign-Off / Audit Verified</span>
                  </>
                )}
              </button>
            </div>

          </div>
        </div>
      )}

      {/* TAB 2: LATE ARRIVALS & COMPLIANCE */}
      {activeAdminSection === 'compliance' && (
        <div className="card animate-fade-in">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                Student Late Arrival Log & Disciplinary Audit
              </h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: '#64748B' }}>
                Cutoff policy: 09:00 AM. Total 24 students admitted under late policy clearance today.
              </p>
            </div>
            <button
              type="button"
              onClick={() => handleSendHODAlert('All')}
              className="btn btn-primary"
              style={{ fontSize: '0.82rem' }}
            >
              <Mail size={15} />
              <span>Dispatch Attendance Flags to All HODs</span>
            </button>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '2px solid #E2E8F0', color: '#64748B' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Roll Number</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Student Name</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Department</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Arrival Time</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Recorded Reason</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Gate Officer</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Disciplinary Action</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid #E2E8F0' }}>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 800, color: '#2563EB' }}>23CSE001</td>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Example Student</td>
                  <td style={{ padding: '0.75rem 1rem' }}>Computer Science (CSE)</td>
                  <td style={{ padding: '0.75rem 1rem', color: '#D97706', fontWeight: 800 }}>09:30 AM (+30m)</td>
                  <td style={{ padding: '0.75rem 1rem' }}>College bus missed (Bus #14 breakdown at Tambaram)</td>
                  <td style={{ padding: '0.75rem 1rem' }}>Ramasamy (Gate 1)</td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <span className="badge badge-green">Bus Exception Approved</span>
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid #E2E8F0' }}>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 800, color: '#2563EB' }}>22CS102</td>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Priya Anbarasan</td>
                  <td style={{ padding: '0.75rem 1rem' }}>Computer Science (CSE)</td>
                  <td style={{ padding: '0.75rem 1rem', color: '#D97706', fontWeight: 800 }}>09:22 AM (+22m)</td>
                  <td style={{ padding: '0.75rem 1rem' }}>Suburban train delay (Beach - Tambaram route)</td>
                  <td style={{ padding: '0.75rem 1rem' }}>Ramasamy (Gate 1)</td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <span className="badge badge-amber">Warning 1 Issued</span>
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid #E2E8F0' }}>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 800, color: '#2563EB' }}>23ME045</td>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 700 }}>Vigneshwaran K</td>
                  <td style={{ padding: '0.75rem 1rem' }}>Mechanical Engg</td>
                  <td style={{ padding: '0.75rem 1rem', color: '#DC2626', fontWeight: 800 }}>09:45 AM (+45m)</td>
                  <td style={{ padding: '0.75rem 1rem' }}>Overslept in hostel / Late morning wake-up</td>
                  <td style={{ padding: '0.75rem 1rem' }}>Ramasamy (Gate 1)</td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <span className="badge badge-red">HOD Escalate Notice</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: CURFEW OVERDUES */}
      {activeAdminSection === 'overdues' && (
        <div className="card animate-fade-in">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#991B1B', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={20} color="#DC2626" />
                <span>Active Curfew Violations & Overdue Out-Passes</span>
              </h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: '#64748B' }}>
                Students who have exited the campus on out-pass but have NOT returned before curfew time.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {overduePasses.map((p) => (
              <div key={p.id} style={{
                border: '1.5px solid #FECACA',
                backgroundColor: '#FFF5F5',
                borderRadius: '12px',
                padding: '1.25rem',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '1rem'
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1.05rem', fontWeight: 900, color: '#0F172A' }}>
                      {p.name}
                    </span>
                    <span className="badge badge-blue">{p.rollNumber}</span>
                    <span className="badge badge-red">{p.overdueDuration}</span>
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#64748B', marginTop: '4px' }}>
                    <strong>{p.dept}</strong> &bull; Reason: {p.purpose} &bull; Destination: {p.destination}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#991B1B', marginTop: '4px', fontWeight: 700 }}>
                    Departed: {p.outTime} &bull; Curfew Return Was: {p.expectedIn}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#334155', marginTop: '4px' }}>
                    Parent: <strong>{p.parentName}</strong> ({p.parentPhone})
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => handleSendParentAlert(p.name, p.rollNumber)}
                    className="btn btn-primary"
                    style={{ fontSize: '0.82rem' }}
                  >
                    <Phone size={14} />
                    <span>Alert Parent ({p.parentPhone})</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSendHODAlert(p.dept)}
                    className="btn btn-secondary"
                    style={{ fontSize: '0.82rem' }}
                  >
                    <Mail size={14} />
                    <span>Notify Warden</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: GUARD SHIFT HANDOVER AUDIT */}
      {activeAdminSection === 'shifts' && (
        <div className="card animate-fade-in">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                Security Guard Shift Handover Governance & Audits
              </h3>
              <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: '#64748B' }}>
                Shift transfer accountability log between outgoing and incoming guards with equipment checklists.
              </p>
            </div>
            <button
              type="button"
              onClick={fetchHandovers}
              className="btn btn-secondary"
              style={{ fontSize: '0.8rem' }}
            >
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              <span>Refresh Records</span>
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{
              border: '1.5px solid #DBEAFE',
              backgroundColor: '#F8FAFC',
              borderRadius: '12px',
              padding: '1.25rem'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <span style={{ fontSize: '1rem', fontWeight: 900, color: '#0F172A' }}>
                    Shift Handover HO-2026-8812 &bull; Gate 1
                  </span>
                  <span className="badge badge-green">ACKNOWLEDGED & VERIFIED</span>
                </div>
                <span style={{ fontSize: '0.8rem', color: '#64748B', fontWeight: 700 }}>
                  Today 02:00 PM
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1rem', fontSize: '0.82rem' }}>
                <div>
                  <span style={{ color: '#64748B' }}>Outgoing Guard:</span><br />
                  <strong>Ramasamy (Main Gate Security)</strong>
                </div>
                <div>
                  <span style={{ color: '#64748B' }}>Incoming Guard:</span><br />
                  <strong>Murugan (Gate Guard - Shift B)</strong>
                </div>
                <div>
                  <span style={{ color: '#64748B' }}>Shift Time:</span><br />
                  <strong>Morning (06:00 - 14:00) &rarr; Evening</strong>
                </div>
              </div>

              <div style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '8px',
                padding: '0.85rem',
                border: '1px solid #E2E8F0',
                fontSize: '0.8rem',
                marginBottom: '1rem'
              }}>
                <div style={{ fontWeight: 800, color: '#0F172A', marginBottom: '4px' }}>
                  ✅ Physical Equipment & Safety Checklist:
                </div>
                <div style={{ color: '#475569', lineHeight: 1.5 }}>
                  &bull; Hydraulic Boom Barrier tested 15 cycles (Smooth operation)<br />
                  &bull; Gate 1 ANPR Optical Camera lens cleaned & calibrated<br />
                  &bull; 4 UHF Security Walkie-Talkies charged and accounted for<br />
                  &bull; Gate master keys and visitor badges (1-50) verified in cabinet
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleSupervisorSignOff(1001)}
                style={{
                  padding: '0.65rem 1.25rem',
                  borderRadius: '8px',
                  backgroundColor: supervisorSigned ? '#ECFDF5' : '#0F172A',
                  color: supervisorSigned ? '#065F46' : '#FFFFFF',
                  border: supervisorSigned ? '1.5px solid #10B981' : 'none',
                  fontSize: '0.82rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                {supervisorSigned ? (
                  <>
                    <CheckCircle2 size={16} color="#10B981" />
                    <span>Supervisor Audit Approved by Dr. Sundararajan!</span>
                  </>
                ) : (
                  <>
                    <Check size={16} />
                    <span>Click to Sign-Off & Audit as Campus Administrator</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* PRINTABLE DAILY SECURITY EXECUTIVE DIGEST MODAL */}
      {showPrintModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1rem'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            maxWidth: '650px',
            width: '100%',
            padding: '2rem',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <div style={{ textAlign: 'center', borderBottom: '2px solid #0F172A', paddingBottom: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#0F172A' }}>
                CAMPUSGUARD DAILY SECURITY EXECUTIVE DIGEST
              </div>
              <div style={{ fontSize: '0.85rem', color: '#64748B' }}>
                Campus Director & Chief Security Officer &bull; Date: {new Date().toLocaleDateString()}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', marginBottom: '1.25rem', fontSize: '0.85rem' }}>
              <div style={{ padding: '0.75rem', backgroundColor: '#F8FAFC', borderRadius: '8px' }}>
                <span style={{ color: '#64748B' }}>Total Campus Occupancy:</span><br />
                <strong style={{ fontSize: '1.1rem', color: '#0F172A' }}>1,842 Persons</strong>
              </div>
              <div style={{ padding: '0.75rem', backgroundColor: '#F8FAFC', borderRadius: '8px' }}>
                <span style={{ color: '#64748B' }}>Late Arrivals (&gt;09:00 AM):</span><br />
                <strong style={{ fontSize: '1.1rem', color: '#D97706' }}>24 Students Flagged</strong>
              </div>
              <div style={{ padding: '0.75rem', backgroundColor: '#F8FAFC', borderRadius: '8px' }}>
                <span style={{ color: '#64748B' }}>Curfew Overdue Breaches:</span><br />
                <strong style={{ fontSize: '1.1rem', color: '#DC2626' }}>{overduePasses.length} Unreturned</strong>
              </div>
              <div style={{ padding: '0.75rem', backgroundColor: '#F8FAFC', borderRadius: '8px' }}>
                <span style={{ color: '#64748B' }}>Gate Guard Handover:</span><br />
                <strong style={{ fontSize: '1.1rem', color: '#059669' }}>Audited & Verified</strong>
              </div>
            </div>

            <div style={{ fontSize: '0.85rem', color: '#334155', lineHeight: 1.5, marginBottom: '1.5rem' }}>
              <strong>Executive Summary:</strong> Gate 1 and Gate 2 operations remained normal throughout the day. 24 students admitted under late policy clearance due to Tambaram bus delay. 2 students currently overdue past curfew; parents notified.
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setShowPrintModal(false)}
                className="btn btn-secondary"
              >
                Close
              </button>
              <button
                type="button"
                onClick={() => window.print()}
                className="btn btn-primary"
                style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <Printer size={16} />
                <span>Print Document</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ADD NEW WATCHMAN / GUARD MODAL */}
      {showAddGuardModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1rem'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '20px',
            maxWidth: '520px',
            width: '100%',
            padding: '2rem',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.3)',
            border: '2px solid #2563EB'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '1.25rem' }}>
              <div style={{ width: '42px', height: '42px', borderRadius: '12px', backgroundColor: '#EFF6FF', color: '#2563EB', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <UserPlus size={22} />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 900, color: '#0F172A' }}>
                  {language === 'ta' ? 'புதிய வாட்ச்மேனைச் சேர்க்க' : 'Add New Security Watchman'}
                </h3>
                <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: '#64748B' }}>
                  {language === 'ta' ? 'புதிய வாட்ச்மேன் ஐடி & விவரங்களை உள்ளிடவும்' : 'Register a new guard to access the Gate Kiosk system'}
                </p>
              </div>
            </div>

            <form onSubmit={handleAddGuard}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '0.85rem' }}>
                <div>
                  <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                    {language === 'ta' ? 'வாட்ச்மேன் பெயர்' : 'Full Name *'}
                  </label>
                  <input
                    type="text"
                    required
                    className="input-field"
                    placeholder="e.g. Murugan P."
                    value={newGuardName}
                    onChange={(e) => setNewGuardName(e.target.value)}
                  />
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                    {language === 'ta' ? 'Username (லாகின் ஐடி) *' : 'Login Username *'}
                  </label>
                  <input
                    type="text"
                    required
                    className="input-field"
                    placeholder="e.g. watchman2"
                    value={newGuardUsername}
                    onChange={(e) => setNewGuardUsername(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '0.85rem' }}>
                <div>
                  <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                    {language === 'ta' ? 'அளிக்கப்படும் கேட் (Post)' : 'Assigned Gate / Post'}
                  </label>
                  <select
                    className="input-field"
                    value={newGuardGate}
                    onChange={(e) => setNewGuardGate(e.target.value)}
                  >
                    <option value="Main Gate 1">Main Gate 1 (Front Entrance)</option>
                    <option value="North Gate 2">North Gate 2 (Commercial Vehicles)</option>
                    <option value="Hostel Gate">Hostel Checkpoint</option>
                    <option value="Library Checkpoint">Library Checkpoint</option>
                  </select>
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                    {language === 'ta' ? 'மொபைல் எண்' : 'Phone Number'}
                  </label>
                  <input
                    type="tel"
                    className="input-field"
                    placeholder="e.g. 9876543211"
                    value={newGuardPhone}
                    onChange={(e) => setNewGuardPhone(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '1.25rem' }}>
                <div>
                  <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                    {language === 'ta' ? 'பணி நேரம் (Shift)' : 'Shift Allocation'}
                  </label>
                  <select
                    className="input-field"
                    value={newGuardShift}
                    onChange={(e) => setNewGuardShift(e.target.value)}
                  >
                    <option value="Morning Shift (06:00 - 14:00)">Morning (06:00 - 14:00)</option>
                    <option value="Afternoon Shift (14:00 - 22:00)">Afternoon (14:00 - 22:00)</option>
                    <option value="Night Shift (22:00 - 06:00)">Night (22:00 - 06:00)</option>
                  </select>
                </div>
                <div>
                  <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                    {language === 'ta' ? 'கடவுச்சொல் (Password)' : 'Default Password'}
                  </label>
                  <input
                    type="text"
                    className="input-field"
                    value={newGuardPassword}
                    onChange={(e) => setNewGuardPassword(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', borderTop: '1px solid #E2E8F0', paddingTop: '1rem' }}>
                <button
                  type="button"
                  onClick={() => setShowAddGuardModal(false)}
                  className="btn btn-secondary"
                >
                  {language === 'ta' ? 'ரத்து' : 'Cancel'}
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 800 }}
                >
                  <Plus size={16} />
                  <span>{language === 'ta' ? 'வாட்ச்மேனைச் சேர்' : 'Save & Register Guard'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
