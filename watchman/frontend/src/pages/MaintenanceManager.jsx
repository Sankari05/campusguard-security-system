import React, { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Wrench,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Plus,
  RefreshCw,
  Search,
  MapPin,
  Lightbulb,
  Mic,
  Snowflake,
  Lock,
  Droplets,
  User,
  Play,
  Check,
  Eye,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  X
} from 'lucide-react';

const INITIAL_MOCK_TICKETS = [
  {
    id: 1,
    ticket_number: 'MNT-261025-F4A8',
    category: 'ELECTRICAL',
    title: 'North Gate Floodlight Not Working',
    description: 'Short circuit after light rain. Floodlight flickering.',
    location: 'North Gate Bay 1',
    urgency: 'HIGH',
    status: 'IN_PROGRESS',
    reported_by: 'Ramasamy (Main Gate Security)',
    time_ago: '2h ago',
    date_str: 'Oct 26, 12:30 PM',
    assigned_to: 'Campus Electrical Team',
    created_at: '2026-10-26T12:30:00Z'
  },
  {
    id: 2,
    ticket_number: 'MNT-261025-2497',
    category: 'VOICE_REPORT',
    title: 'Voice Report: Property Damage at Block B',
    description: 'Spoken via Voice NLP by Watchman Ramasamy: "Block B-la gate damage irukku, vehicle number TN09CA1234 hit panniduchu."',
    location: 'Block B',
    urgency: 'HIGH',
    status: 'OPEN',
    reported_by: 'Watchman Ramasamy',
    time_ago: '4h ago',
    date_str: 'Oct 26, 10:15 AM',
    assigned_to: null,
    created_at: '2026-10-26T10:15:00Z'
  },
  {
    id: 3,
    ticket_number: 'MNT-261025-F6D0',
    category: 'HARDWARE',
    title: 'North Gate Floodlight Not Working',
    description: 'Short circuit after light rain. Floodlight flickering.',
    location: 'North Gate Bay 1',
    urgency: 'HIGH',
    status: 'IN_PROGRESS',
    reported_by: 'Ramasamy (Main Gate Security)',
    time_ago: '5h ago',
    date_str: 'Oct 26, 09:45 AM',
    assigned_to: 'Campus Facilities Team',
    created_at: '2026-10-26T09:45:00Z'
  },
  {
    id: 4,
    ticket_number: 'MNT-261025-4933',
    category: 'HVAC',
    title: 'AC Not Cooling in Computer Lab',
    description: 'AC unit not cooling properly. Room temperature high.',
    location: 'Computer Lab - Block C',
    urgency: 'MEDIUM',
    status: 'OPEN',
    reported_by: 'Faculty (Computer Science)',
    time_ago: '6h ago',
    date_str: 'Oct 26, 08:20 AM',
    assigned_to: null,
    created_at: '2026-10-26T08:20:00Z'
  },
  {
    id: 5,
    ticket_number: 'MNT-261025-A1C7',
    category: 'GATE_BARRIER',
    title: 'Gate Barrier Malfunction',
    description: 'Automatic barrier not opening. Manual check required.',
    location: 'Main Gate 1',
    urgency: 'MEDIUM',
    status: 'IN_PROGRESS',
    reported_by: 'Security Team',
    time_ago: '7h ago',
    date_str: 'Oct 26, 07:10 AM',
    assigned_to: 'Automation Engineers',
    created_at: '2026-10-26T07:10:00Z'
  },
  {
    id: 6,
    ticket_number: 'MNT-261025-B8E2',
    category: 'PLUMBING',
    title: 'Water Leakage in Library',
    description: 'Pipe leakage near reading hall. Fixed by maintenance team.',
    location: 'Library - Ground Floor',
    urgency: 'LOW',
    status: 'RESOLVED',
    reported_by: 'Library Staff',
    time_ago: '9h ago',
    date_str: 'Oct 26, 05:12 AM',
    assigned_to: 'Campus Plumbing Team',
    created_at: '2026-10-26T05:12:00Z'
  },
  {
    id: 7,
    ticket_number: 'MNT-261025-9910',
    category: 'VOICE_REPORT',
    title: 'Voice Report: Property Damage at Block B',
    description: 'Spoken via Voice NLP by Watchman Ramasamy: "Block B-la gate damage irukku, vehicle number TN09CA1234 hit panniduchu."',
    location: 'Block B',
    urgency: 'HIGH',
    status: 'OPEN',
    reported_by: 'Watchman Ramasamy',
    time_ago: '10h ago',
    date_str: 'Oct 26, 04:00 AM',
    assigned_to: null,
    created_at: '2026-10-26T04:00:00Z'
  },
  {
    id: 8,
    ticket_number: 'MNT-261025-75DD',
    category: 'ELECTRICAL',
    title: 'North Gate Floodlight Not Working',
    description: 'Short circuit after light rain. Floodlight flickering.',
    location: 'North Gate Bay 1',
    urgency: 'HIGH',
    status: 'IN_PROGRESS',
    reported_by: 'Ramasamy (Main Gate Security)',
    time_ago: '12h ago',
    date_str: 'Oct 26, 02:15 AM',
    assigned_to: 'Campus Maintenance Team',
    created_at: '2026-10-26T02:15:00Z'
  }
];

export const MaintenanceManager = () => {
  const { language } = useAuth();
  const [reports, setReports] = useState(INITIAL_MOCK_TICKETS);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [filterPriority, setFilterPriority] = useState('ALL');
  const [sortBy, setSortBy] = useState('NEWEST');
  const [searchQuery, setSearchQuery] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [selectedTicket, setSelectedTicket] = useState(null);

  // Form State
  const [category, setCategory] = useState('ELECTRICAL');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('North Gate Bay 1');
  const [urgency, setUrgency] = useState('HIGH');
  const [reportedBy, setReportedBy] = useState('Ramasamy (Main Gate Security)');

  const fetchReports = async () => {
    setLoading(true);
    try {
      const data = await api.getMaintenanceReports();
      if (Array.isArray(data) && data.length > 0) {
        // Merge with mock details to preserve UI rich text if properties are missing
        const mapped = data.map((item, idx) => ({
          ...item,
          time_ago: item.time_ago || `${(idx + 1) * 2}h ago`,
          date_str: item.date_str || (item.created_at ? new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Today')
        }));
        setReports(mapped);
      } else {
        setReports(INITIAL_MOCK_TICKETS);
      }
    } catch {
      setReports(INITIAL_MOCK_TICKETS);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;

    const newTicketNumber = `MNT-${new Date().toISOString().slice(2, 10).replace(/-/g, '')}-${Math.random().toString(16).substring(2, 6).toUpperCase()}`;

    try {
      await api.createMaintenanceReport({
        ticket_number: newTicketNumber,
        category,
        title,
        description,
        location,
        urgency,
        reported_by: reportedBy || 'Main Gate Watchman'
      });
    } catch {
      // Local fallback handled below
    }

    const createdItem = {
      id: Date.now(),
      ticket_number: newTicketNumber,
      category,
      title,
      description,
      location,
      urgency,
      status: 'OPEN',
      reported_by: reportedBy || 'Main Gate Watchman',
      time_ago: 'Just now',
      date_str: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      created_at: new Date().toISOString()
    };

    setReports((prev) => [createdItem, ...prev]);
    setTitle('');
    setDescription('');
    setShowModal(false);
  };

  const handleStatusUpdate = async (id, newStatus) => {
    try {
      await api.updateMaintenanceStatus(id, {
        status: newStatus,
        assigned_to: newStatus === 'IN_PROGRESS' ? 'Campus Facility Maintenance Team' : undefined
      });
    } catch {
      // Local fallback handled below
    }

    setReports((prev) =>
      prev.map((r) =>
        r.id === id
          ? {
              ...r,
              status: newStatus,
              assigned_to: newStatus === 'IN_PROGRESS' ? (r.assigned_to || 'Campus Facility Maintenance Team') : r.assigned_to
            }
          : r
      )
    );

    if (selectedTicket && selectedTicket.id === id) {
      setSelectedTicket((prev) => ({ ...prev, status: newStatus }));
    }
  };

  const getCategoryIcon = (cat, ticketTitle = '') => {
    const c = (cat || '').toUpperCase();
    const t = (ticketTitle || '').toLowerCase();

    if (c === 'VOICE_REPORT' || t.includes('voice') || c === 'VOICE_NLP') {
      return <Mic size={18} color="#2563eb" />;
    }
    if (c === 'ELECTRICAL' || t.includes('floodlight') || t.includes('light') || t.includes('circuit')) {
      return <Lightbulb size={18} color="#2563eb" />;
    }
    if (c === 'HVAC' || t.includes('ac ') || t.includes('cooling') || t.includes('temperature')) {
      return <Snowflake size={18} color="#2563eb" />;
    }
    if (c === 'GATE_BARRIER' || t.includes('barrier') || t.includes('gate') || t.includes('turnstile')) {
      return <Lock size={18} color="#2563eb" />;
    }
    if (c === 'PLUMBING' || t.includes('water') || t.includes('leak') || t.includes('drainage')) {
      return <Droplets size={18} color="#2563eb" />;
    }
    return <Wrench size={18} color="#2563eb" />;
  };

  // Filter & Sort
  const filtered = useMemo(() => {
    return reports
      .filter((r) => {
        const matchesStatus = filterStatus === 'ALL' || r.status === filterStatus;
        const matchesPriority = filterPriority === 'ALL' || (r.urgency || '').toUpperCase() === filterPriority;
        const q = searchQuery.toLowerCase().trim();
        const matchesSearch =
          !q ||
          r.title?.toLowerCase().includes(q) ||
          r.ticket_number?.toLowerCase().includes(q) ||
          r.location?.toLowerCase().includes(q) ||
          r.description?.toLowerCase().includes(q) ||
          r.reported_by?.toLowerCase().includes(q);
        return matchesStatus && matchesPriority && matchesSearch;
      })
      .sort((a, b) => {
        if (sortBy === 'OLDEST') {
          return (a.id || 0) - (b.id || 0);
        }
        if (sortBy === 'PRIORITY') {
          const pOrder = { EMERGENCY: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
          return (pOrder[b.urgency] || 0) - (pOrder[a.urgency] || 0);
        }
        // Default NEWEST
        return (b.id || 0) - (a.id || 0);
      });
  }, [reports, filterStatus, filterPriority, searchQuery, sortBy]);

  const totalCount = reports.length;
  const openCount = reports.filter((r) => r.status === 'OPEN').length;
  const inProgressCount = reports.filter((r) => r.status === 'IN_PROGRESS').length;
  const resolvedCount = reports.filter((r) => r.status === 'RESOLVED').length;

  return (
    <div style={{ padding: '1.25rem clamp(0.75rem, 2.5vw, 2rem)', maxWidth: '1440px', margin: '0 auto', fontFamily: 'inherit' }}>
      {/* ── Top Header ────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.75rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.9rem' }}>
          <div
            style={{
              width: '46px',
              height: '46px',
              borderRadius: '12px',
              background: '#2563eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              boxShadow: '0 4px 14px rgba(37, 99, 235, 0.28)',
              flexShrink: 0
            }}
          >
            <Wrench size={24} strokeWidth={2.4} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.45rem', fontWeight: 800, color: '#0f172a', margin: 0, letterSpacing: '-0.02em' }}>
              {language === 'ta' ? 'ஸ்மார்ட் வளாக பராமரிப்பு' : 'Smart Campus Maintenance'}
            </h1>
            <p style={{ fontSize: '0.86rem', color: '#64748b', margin: '0.2rem 0 0', fontWeight: 500 }}>
              {language === 'ta' ? 'வளாக வன்பொருள் குறைபாடுகளை பதிவு செய்தல், பணி ஒதுக்குதல் & தீர்வு காணுதல்' : 'Track, assign, and resolve campus hardware issues'}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button
            onClick={fetchReports}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              background: 'white',
              border: '1px solid #e2e8f0',
              color: '#2563eb',
              fontWeight: 700,
              fontSize: '0.86rem',
              padding: '0.55rem 1.15rem',
              borderRadius: '10px',
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
              transition: 'background 0.15s ease'
            }}
          >
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            {language === 'ta' ? 'புதுப்பி' : 'Refresh'}
          </button>
          <button
            onClick={() => setShowModal(true)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              background: '#2563eb',
              border: 'none',
              color: 'white',
              fontWeight: 800,
              fontSize: '0.88rem',
              padding: '0.58rem 1.35rem',
              borderRadius: '10px',
              cursor: 'pointer',
              boxShadow: '0 4px 12px rgba(37, 99, 235, 0.32)',
              transition: 'transform 0.1s ease, background 0.15s ease'
            }}
          >
            <Plus size={17} strokeWidth={2.8} />
            {language === 'ta' ? '+ பிரச்சனை பதிவு' : '+ Report Issue'}
          </button>
        </div>
      </div>

      {/* ── 4 Top KPI Metric Cards ────────────────────────────── */}
      <div className="responsive-kpi-4" style={{ marginBottom: '1.75rem' }}>
        {/* Card 1: Total Tickets */}
        <div
          style={{
            background: 'white',
            borderRadius: '16px',
            padding: '1.2rem 1.4rem',
            border: '1px solid #e2e8f0',
            boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
            display: 'flex',
            alignItems: 'center',
            gap: '1.1rem'
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: '#eff6ff',
              border: '1px solid #dbeafe',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#2563eb',
              flexShrink: 0
            }}
          >
            <ClipboardList size={24} strokeWidth={2.2} />
          </div>
          <div>
            <div style={{ fontSize: '0.82rem', color: '#64748b', fontWeight: 600 }}>Total Tickets</div>
            <div style={{ fontSize: '1.85rem', fontWeight: 900, color: '#0f172a', lineHeight: 1.15, marginTop: '2px' }}>
              {totalCount}
            </div>
          </div>
        </div>

        {/* Card 2: Open */}
        <div
          style={{
            background: '#fff5f5',
            borderRadius: '16px',
            padding: '1.2rem 1.4rem',
            border: '1px solid #fed7d7',
            display: 'flex',
            alignItems: 'center',
            gap: '1.1rem'
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: '#fee2e2',
              border: '1px solid #fecaca',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#dc2626',
              flexShrink: 0
            }}
          >
            <AlertTriangle size={24} strokeWidth={2.2} />
          </div>
          <div>
            <div style={{ fontSize: '0.82rem', color: '#dc2626', fontWeight: 700 }}>Open</div>
            <div style={{ fontSize: '1.85rem', fontWeight: 900, color: '#dc2626', lineHeight: 1.15, marginTop: '2px' }}>
              {openCount}
            </div>
          </div>
        </div>

        {/* Card 3: In Progress */}
        <div
          style={{
            background: '#fffdf5',
            borderRadius: '16px',
            padding: '1.2rem 1.4rem',
            border: '1px solid #fef3c7',
            display: 'flex',
            alignItems: 'center',
            gap: '1.1rem'
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: '#fef3c7',
              border: '1px solid #fde68a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#d97706',
              flexShrink: 0
            }}
          >
            <Clock size={24} strokeWidth={2.2} />
          </div>
          <div>
            <div style={{ fontSize: '0.82rem', color: '#d97706', fontWeight: 700 }}>In Progress</div>
            <div style={{ fontSize: '1.85rem', fontWeight: 900, color: '#d97706', lineHeight: 1.15, marginTop: '2px' }}>
              {inProgressCount}
            </div>
          </div>
        </div>

        {/* Card 4: Resolved */}
        <div
          style={{
            background: '#f0fdf4',
            borderRadius: '16px',
            padding: '1.2rem 1.4rem',
            border: '1px solid #bbf7d0',
            display: 'flex',
            alignItems: 'center',
            gap: '1.1rem'
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: '#dcfce7',
              border: '1px solid #bbf7d0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#16a34a',
              flexShrink: 0
            }}
          >
            <CheckCircle2 size={24} strokeWidth={2.2} />
          </div>
          <div>
            <div style={{ fontSize: '0.82rem', color: '#16a34a', fontWeight: 700 }}>Resolved</div>
            <div style={{ fontSize: '1.85rem', fontWeight: 900, color: '#16a34a', lineHeight: 1.15, marginTop: '2px' }}>
              {resolvedCount}
            </div>
          </div>
        </div>
      </div>

      {/* ── Search & Filter Controls Bar ──────────────────────── */}
      <div
        style={{
          display: 'flex',
          gap: '1rem',
          alignItems: 'center',
          marginBottom: '1.5rem',
          flexWrap: 'wrap'
        }}
      >
        {/* Search input */}
        <div style={{ position: 'relative', flex: 1, minWidth: '300px' }}>
          <Search
            size={18}
            color="#94a3b8"
            style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)' }}
          />
          <input
            type="text"
            placeholder={language === 'ta' ? 'டிக்கெட் எண், விவரம் அல்லது இடத்தின் மூலம் தேடுக...' : 'Search by ticket ID, description or location...'}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '0.7rem 0.85rem 0.7rem 2.6rem',
              borderRadius: '10px',
              border: '1px solid #e2e8f0',
              background: 'white',
              fontSize: '0.88rem',
              color: '#1e293b',
              outline: 'none',
              boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
            }}
          />
        </div>

        {/* Status filter pills */}
        <div
          style={{
            display: 'flex',
            background: 'white',
            border: '1px solid #e2e8f0',
            borderRadius: '10px',
            padding: '3px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)'
          }}
        >
          {[
            { id: 'ALL', label: 'All' },
            { id: 'OPEN', label: 'Open' },
            { id: 'IN_PROGRESS', label: 'In Progress' },
            { id: 'RESOLVED', label: 'Resolved' }
          ].map((tab) => {
            const active = filterStatus === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setFilterStatus(tab.id)}
                style={{
                  padding: '0.45rem 1rem',
                  borderRadius: '7px',
                  border: 'none',
                  fontSize: '0.84rem',
                  fontWeight: active ? 700 : 600,
                  cursor: 'pointer',
                  background: active ? '#2563eb' : 'transparent',
                  color: active ? '#ffffff' : '#64748b',
                  transition: 'all 0.15s ease'
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Priority dropdown */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            background: 'white',
            border: '1px solid #e2e8f0',
            borderRadius: '10px',
            padding: '0.35rem 0.85rem',
            gap: '0.55rem',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)'
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.68rem', color: '#64748b', fontWeight: 600, lineHeight: 1 }}>Priority</span>
            <select
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value)}
              style={{
                border: 'none',
                background: 'transparent',
                fontSize: '0.84rem',
                fontWeight: 700,
                color: '#1e293b',
                outline: 'none',
                cursor: 'pointer',
                paddingTop: '2px'
              }}
            >
              <option value="ALL">All</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
        </div>

        {/* Sort by dropdown */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            background: 'white',
            border: '1px solid #e2e8f0',
            borderRadius: '10px',
            padding: '0.35rem 0.85rem',
            gap: '0.55rem',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)'
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.68rem', color: '#64748b', fontWeight: 600, lineHeight: 1 }}>Sort by</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{
                border: 'none',
                background: 'transparent',
                fontSize: '0.84rem',
                fontWeight: 700,
                color: '#1e293b',
                outline: 'none',
                cursor: 'pointer',
                paddingTop: '2px'
              }}
            >
              <option value="NEWEST">Newest First</option>
              <option value="OLDEST">Oldest First</option>
              <option value="PRIORITY">Priority</option>
            </select>
          </div>
        </div>
      </div>

      {/* ── 3-Column Ticket Cards Grid ────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 350px), 1fr))', gap: '1.25rem' }}>
        {filtered.map((r) => (
          <div
            key={r.id}
            style={{
              background: 'white',
              borderRadius: '16px',
              border: '1px solid #e2e8f0',
              padding: '1.35rem',
              boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              position: 'relative'
            }}
          >
            <div>
              {/* Card Header: Icon + ID + Status Pill */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                  <div
                    style={{
                      width: '38px',
                      height: '38px',
                      borderRadius: '50%',
                      background: '#eff6ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}
                  >
                    {getCategoryIcon(r.category, r.title)}
                  </div>
                  <span style={{ fontSize: '0.84rem', fontWeight: 800, color: '#334155', letterSpacing: '0.02em' }}>
                    {r.ticket_number}
                  </span>
                </div>

                {/* Status Pill Badge */}
                {r.status === 'IN_PROGRESS' && (
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      padding: '0.22rem 0.65rem',
                      borderRadius: '999px',
                      background: '#fffdf5',
                      color: '#d97706',
                      border: '1px solid #fef3c7',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      letterSpacing: '0.02em'
                    }}
                  >
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#d97706' }} />
                    IN_PROGRESS
                  </span>
                )}

                {r.status === 'OPEN' && (
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      padding: '0.22rem 0.65rem',
                      borderRadius: '999px',
                      background: '#fff5f5',
                      color: '#dc2626',
                      border: '1px solid #fed7d7',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.3rem',
                      letterSpacing: '0.02em'
                    }}
                  >
                    <span style={{ fontSize: '0.78rem', lineHeight: 1 }}>↓</span>
                    OPEN
                  </span>
                )}

                {r.status === 'RESOLVED' && (
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      padding: '0.22rem 0.65rem',
                      borderRadius: '999px',
                      background: '#f0fdf4',
                      color: '#16a34a',
                      border: '1px solid #bbf7d0',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      letterSpacing: '0.02em'
                    }}
                  >
                    <Check size={12} strokeWidth={3} />
                    RESOLVED
                  </span>
                )}
              </div>

              {/* Title */}
              <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f172a', margin: '0 0 0.4rem', letterSpacing: '-0.01em' }}>
                {r.title}
              </h3>

              {/* Description */}
              <p style={{ fontSize: '0.83rem', color: '#64748b', lineHeight: 1.5, margin: '0 0 0.85rem', minHeight: '2.5rem' }}>
                {r.description}
              </p>

              {/* Location */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: '#64748b', marginBottom: '0.85rem' }}>
                <MapPin size={14} color="#94a3b8" />
                <span style={{ fontWeight: 500, color: '#475569' }}>{r.location}</span>
              </div>

              {/* Meta Row: Priority + Reporter + Timestamp */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap', marginBottom: '1.1rem' }}>
                <span
                  style={{
                    fontSize: '0.68rem',
                    fontWeight: 800,
                    padding: '0.2rem 0.55rem',
                    borderRadius: '6px',
                    letterSpacing: '0.04em',
                    background:
                      r.urgency === 'HIGH' || r.urgency === 'EMERGENCY'
                        ? '#fee2e2'
                        : r.urgency === 'MEDIUM'
                        ? '#fff7ed'
                        : '#f0fdf4',
                    color:
                      r.urgency === 'HIGH' || r.urgency === 'EMERGENCY'
                        ? '#dc2626'
                        : r.urgency === 'MEDIUM'
                        ? '#ea580c'
                        : '#16a34a',
                    border:
                      r.urgency === 'HIGH' || r.urgency === 'EMERGENCY'
                        ? '1px solid #fecaca'
                        : r.urgency === 'MEDIUM'
                        ? '1px solid #fed7aa'
                        : '1px solid #bbf7d0'
                  }}
                >
                  {r.urgency || 'MEDIUM'} PRIORITY
                </span>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.76rem', color: '#64748b' }}>
                  <User size={13} color="#94a3b8" />
                  <span>
                    Reported by: <strong style={{ color: '#334155', fontWeight: 600 }}>{r.reported_by}</strong>
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', color: '#94a3b8', marginLeft: 'auto' }}>
                  <Clock size={13} color="#94a3b8" />
                  <span>
                    {r.time_ago || '2h ago'}{' '}
                    <span style={{ color: '#94a3b8', fontWeight: 400 }}>({r.date_str || 'Oct 26'})</span>
                  </span>
                </div>
              </div>
            </div>

            {/* Bottom Action Area */}
            <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '0.9rem', display: 'flex', justifyContent: 'flex-end' }}>
              {r.status === 'OPEN' && (
                <button
                  onClick={() => handleStatusUpdate(r.id, 'IN_PROGRESS')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    background: '#2563eb',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '0.55rem 1.25rem',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    boxShadow: '0 2px 6px rgba(37, 99, 235, 0.25)',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Play size={13} fill="currentColor" />
                  Mark In Progress
                </button>
              )}

              {r.status === 'IN_PROGRESS' && (
                <button
                  onClick={() => handleStatusUpdate(r.id, 'RESOLVED')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    background: '#2563eb',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '0.55rem 1.25rem',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    boxShadow: '0 2px 6px rgba(37, 99, 235, 0.25)',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Check size={14} strokeWidth={2.8} />
                  Mark Resolved
                </button>
              )}

              {r.status === 'RESOLVED' && (
                <button
                  onClick={() => setSelectedTicket(r)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    background: 'white',
                    color: '#2563eb',
                    border: '1px solid #2563eb',
                    borderRadius: '8px',
                    padding: '0.55rem 1.25rem',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Eye size={14} />
                  View Details
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* ── Pagination Footer ─────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '2rem',
          padding: '0.75rem 0',
          borderTop: '1px solid #f1f5f9'
        }}
      >
        <span style={{ fontSize: '0.85rem', color: '#64748b', fontWeight: 500 }}>
          Showing 1-{Math.min(filtered.length, 8)} of {filtered.length} tickets
        </span>
        <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
          <button
            disabled
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              background: 'white',
              color: '#94a3b8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'not-allowed'
            }}
          >
            <ChevronLeft size={16} />
          </button>
          <button
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              border: 'none',
              background: '#2563eb',
              color: 'white',
              fontWeight: 700,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer'
            }}
          >
            1
          </button>
          <button
            disabled
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
              background: 'white',
              color: '#94a3b8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'not-allowed'
            }}
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* ── Report Issue Modal ────────────────────────────────── */}
      {showModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.45)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem'
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '20px',
              padding: '1.75rem',
              width: '100%',
              maxWidth: '520px',
              boxShadow: '0 20px 40px rgba(0,0,0,0.15)',
              border: '1px solid #e2e8f0'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#2563eb' }}>
                  <Wrench size={20} />
                </div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: 0, color: '#0f172a' }}>
                  {language === 'ta' ? 'புதிய குறைபாடு அறிக்கை' : 'Report Campus Hardware Defect'}
                </h2>
              </div>
              <button
                onClick={() => setShowModal(false)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreate}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.35rem' }}>
                  Category
                </label>
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1', fontSize: '0.88rem' }}
                >
                  <option value="ELECTRICAL">Electrical (Floodlights, Wiring, Circuit)</option>
                  <option value="VOICE_REPORT">Voice NLP Incident / Property Damage</option>
                  <option value="HARDWARE">Hardware / Mechanical Equipment</option>
                  <option value="HVAC">HVAC / AC Cooling Failure</option>
                  <option value="GATE_BARRIER">Gate Barrier & Turnstile Post</option>
                  <option value="PLUMBING">Plumbing (Drainage, Pipe Leakage)</option>
                  <option value="CCTV">CCTV Camera / Video Feed</option>
                  <option value="CIVIL">Civil Infrastructure & Roads</option>
                </select>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.35rem' }}>
                  Issue Title
                </label>
                <input
                  type="text"
                  placeholder="e.g., North Gate Floodlight Not Working"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1', fontSize: '0.88rem' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.35rem' }}>
                  Location
                </label>
                <input
                  type="text"
                  placeholder="e.g., North Gate Bay 1, Computer Lab - Block C"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1', fontSize: '0.88rem' }}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem', marginBottom: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.35rem' }}>
                    Priority / Urgency
                  </label>
                  <select
                    value={urgency}
                    onChange={(e) => setUrgency(e.target.value)}
                    style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1', fontSize: '0.88rem' }}
                  >
                    <option value="LOW">Low (Routine)</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High Priority</option>
                    <option value="EMERGENCY">Emergency (Immediate)</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.35rem' }}>
                    Reported By
                  </label>
                  <input
                    type="text"
                    value={reportedBy}
                    onChange={(e) => setReportedBy(e.target.value)}
                    style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1', fontSize: '0.88rem' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '0.35rem' }}>
                  Problem Description
                </label>
                <textarea
                  rows="3"
                  placeholder="Describe observed defect, physical damage or malfunction..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1', fontSize: '0.88rem', fontFamily: 'inherit' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{
                    padding: '0.55rem 1.25rem',
                    borderRadius: '8px',
                    border: '1px solid #cbd5e1',
                    background: 'white',
                    color: '#475569',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{
                    padding: '0.55rem 1.45rem',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#2563eb',
                    color: 'white',
                    fontWeight: 800,
                    cursor: 'pointer',
                    boxShadow: '0 4px 12px rgba(37, 99, 235, 0.3)'
                  }}
                >
                  Submit Ticket
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── View Details Modal ────────────────────────────────── */}
      {selectedTicket && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.45)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem'
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '20px',
              padding: '1.75rem',
              width: '100%',
              maxWidth: '540px',
              boxShadow: '0 20px 40px rgba(0,0,0,0.15)',
              border: '1px solid #e2e8f0'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {getCategoryIcon(selectedTicket.category, selectedTicket.title)}
                </div>
                <div>
                  <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#2563eb' }}>{selectedTicket.ticket_number}</div>
                  <h2 style={{ fontSize: '1.2rem', fontWeight: 800, margin: 0, color: '#0f172a' }}>{selectedTicket.title}</h2>
                </div>
              </div>
              <button
                onClick={() => setSelectedTicket(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', gap: '0.65rem', marginBottom: '1.25rem' }}>
              <span
                style={{
                  fontSize: '0.74rem',
                  fontWeight: 800,
                  padding: '0.22rem 0.65rem',
                  borderRadius: '999px',
                  background:
                    selectedTicket.status === 'RESOLVED'
                      ? '#f0fdf4'
                      : selectedTicket.status === 'IN_PROGRESS'
                      ? '#fffdf5'
                      : '#fff5f5',
                  color:
                    selectedTicket.status === 'RESOLVED'
                      ? '#16a34a'
                      : selectedTicket.status === 'IN_PROGRESS'
                      ? '#d97706'
                      : '#dc2626',
                  border:
                    selectedTicket.status === 'RESOLVED'
                      ? '1px solid #bbf7d0'
                      : selectedTicket.status === 'IN_PROGRESS'
                      ? '1px solid #fef3c7'
                      : '1px solid #fed7d7'
                }}
              >
                STATUS: {selectedTicket.status}
              </span>
              <span
                style={{
                  fontSize: '0.74rem',
                  fontWeight: 800,
                  padding: '0.22rem 0.65rem',
                  borderRadius: '999px',
                  background: '#f1f5f9',
                  color: '#475569'
                }}
              >
                {selectedTicket.urgency} PRIORITY
              </span>
            </div>

            <div style={{ background: '#f8fafc', borderRadius: '12px', padding: '1rem', border: '1px solid #e2e8f0', marginBottom: '1.25rem' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', marginBottom: '0.35rem' }}>DESCRIPTION</div>
              <p style={{ margin: 0, fontSize: '0.88rem', color: '#1e293b', lineHeight: 1.5 }}>{selectedTicket.description}</p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.25rem', fontSize: '0.82rem' }}>
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.74rem', fontWeight: 600 }}>LOCATION</span>
                <span style={{ fontWeight: 700, color: '#1e293b' }}>{selectedTicket.location}</span>
              </div>
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.74rem', fontWeight: 600 }}>REPORTED BY</span>
                <span style={{ fontWeight: 700, color: '#1e293b' }}>{selectedTicket.reported_by}</span>
              </div>
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.74rem', fontWeight: 600 }}>ASSIGNED TEAM</span>
                <span style={{ fontWeight: 700, color: '#1e293b' }}>{selectedTicket.assigned_to || 'Campus Maintenance Duty Team'}</span>
              </div>
              <div>
                <span style={{ color: '#64748b', display: 'block', fontSize: '0.74rem', fontWeight: 600 }}>TIMESTAMP</span>
                <span style={{ fontWeight: 700, color: '#1e293b' }}>{selectedTicket.date_str || selectedTicket.time_ago}</span>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', borderTop: '1px solid #f1f5f9', paddingTop: '1rem' }}>
              {selectedTicket.status !== 'RESOLVED' && (
                <button
                  onClick={() => handleStatusUpdate(selectedTicket.id, 'RESOLVED')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    background: '#2563eb',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '0.55rem 1.25rem',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  <Check size={14} />
                  Mark Resolved
                </button>
              )}
              <button
                onClick={() => setSelectedTicket(null)}
                style={{
                  padding: '0.55rem 1.25rem',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  background: 'white',
                  color: '#475569',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
