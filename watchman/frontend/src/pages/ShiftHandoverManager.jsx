import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  ClipboardCheck,
  Clock,
  User,
  Users,
  Package,
  AlertTriangle,
  AlertOctagon,
  ShieldCheck,
  CheckCircle2,
  Check,
  X,
  Plus,
  RefreshCw,
  Search,
  Filter,
  FileText,
  Radio,
  ArrowRight,
  Shield,
  Layers,
  ArrowLeftRight,
  CheckSquare,
  Square,
  AlertCircle,
  Eye,
  SlidersHorizontal,
  ChevronDown,
  Sparkles
} from 'lucide-react';

export const ShiftHandoverManager = () => {
  const { user, t, language } = useAuth();

  // Active view role: 'OUTGOING', 'INCOMING', 'SUPERVISOR'
  const [viewRole, setViewRole] = useState('OUTGOING');

  // Live Handover state
  const [currentHandover, setCurrentHandover] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [allHandovers, setAllHandovers] = useState([]);
  const [loading, setLoading] = useState(false);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState('ALL'); // ALL, VISITORS, PARCELS, INCIDENTS, EQUIPMENT
  const [selectedStatus, setSelectedStatus] = useState('ALL'); // ALL, OPEN, IN_PROGRESS, RESOLVED
  const [selectedPriority, setSelectedPriority] = useState('ALL'); // ALL, HIGH, MEDIUM, LOW
  const [searchQuery, setSearchQuery] = useState('');

  // Create Handover Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [autoDetectedTasks, setAutoDetectedTasks] = useState([]);
  const [selectedTaskCodes, setSelectedTaskCodes] = useState([]);
  const [newShiftName, setNewShiftName] = useState('Morning Shift (06:00 AM - 02:00 PM)');
  const [newIncomingId, setNewIncomingId] = useState('WM-02');
  const [newIncomingName, setNewIncomingName] = useState('Murugan (Gate Guard - Shift B)');
  const [handoverNotes, setHandoverNotes] = useState('');
  const [submittingHandover, setSubmittingHandover] = useState(false);

  // Task Resolution Modal
  const [resolvingTask, setResolvingTask] = useState(null);
  const [resolutionNotes, setResolutionNotes] = useState('');

  // Supervisor Sign-off Modal
  const [signingHandover, setSigningHandover] = useState(null);
  const [supervisorNotes, setSupervisorNotes] = useState('');

  // Notification Banner
  const [toastMessage, setToastMessage] = useState(null);

  // Fetch current handover and tasks
  const loadHandoverData = async () => {
    setLoading(true);
    try {
      const [currentRes, allRes, tasksRes] = await Promise.all([
        api.getCurrentShiftHandover(),
        api.getAllShiftHandovers(),
        api.getUnresolvedHandoverTasks()
      ]);

      if (currentRes && currentRes.hasActiveHandover) {
        setCurrentHandover(currentRes.handover);
        setTasks(currentRes.tasks || []);
      } else {
        setCurrentHandover(null);
        setTasks(tasksRes || []);
      }

      setAllHandovers(allRes || []);
    } catch (e) {
      console.warn('Error loading handover data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHandoverData();

    const handleCreated = () => loadHandoverData();
    const handleAcknowledged = () => loadHandoverData();
    const handleUpdated = () => loadHandoverData();

    window.addEventListener('campusguard_handover_created', handleCreated);
    window.addEventListener('campusguard_handover_acknowledged', handleAcknowledged);
    window.addEventListener('campusguard_task_updated', handleUpdated);
    window.addEventListener('storage', handleCreated);

    return () => {
      window.removeEventListener('campusguard_handover_created', handleCreated);
      window.removeEventListener('campusguard_handover_acknowledged', handleAcknowledged);
      window.removeEventListener('campusguard_task_updated', handleUpdated);
      window.removeEventListener('storage', handleCreated);
    };
  }, []);

  // Open Create Handover Modal and auto-aggregate tasks from existing modules
  const handleOpenCreateModal = async () => {
    try {
      const detected = await api.generateShiftPendingTasks();
      setAutoDetectedTasks(detected);
      setSelectedTaskCodes(detected.map((t) => t.taskCode));
      setShowCreateModal(true);
    } catch (e) {
      console.warn('Error detecting tasks:', e);
    }
  };

  // Submit Shift Handover (Feature B)
  const handleSubmitHandover = async (e) => {
    e.preventDefault();
    if (submittingHandover) return;

    setSubmittingHandover(true);
    try {
      const chosenTasks = autoDetectedTasks.filter((t) => selectedTaskCodes.includes(t.taskCode));

      const payload = {
        shiftName: newShiftName,
        gateLocation: 'Main Gate 1',
        outgoingWatchmanId: user?.username === 'watchman1' ? 'WM-01' : (user?.id ? `WM-${user.id}` : 'WM-01'),
        outgoingWatchmanName: user?.fullName || 'Ramasamy (Main Gate Security)',
        incomingWatchmanId: newIncomingId,
        incomingWatchmanName: newIncomingName,
        handoverNotes: handoverNotes.trim(),
        tasks: chosenTasks
      };

      const res = await api.createShiftHandover(payload);
      if (res.success) {
        setShowCreateModal(false);
        setToastMessage('✅ Shift Handover Created! Awaiting incoming guard acknowledgement.');
        loadHandoverData();
      } else {
        alert(res.error || 'Failed to create handover.');
      }
    } catch (err) {
      console.error('Handover creation error:', err);
      alert('Error saving handover.');
    } finally {
      setSubmittingHandover(false);
    }
  };

  // Incoming Guard Acknowledges Handover (Feature C)
  const handleAcknowledge = async () => {
    if (!currentHandover) return;
    try {
      const res = await api.acknowledgeShiftHandover(currentHandover.id, {
        watchmanId: 'WM-02',
        watchmanName: 'Murugan (Gate Guard - Shift B)'
      });

      if (res.success) {
        setToastMessage('🎉 Handover Acknowledged! Shift transfer complete. All unresolved tasks remain active.');
        loadHandoverData();
      }
    } catch (e) {
      console.error('Acknowledgement error:', e);
    }
  };

  // Update Task Status (Feature D)
  const handleUpdateStatus = async (taskCode, newStatus) => {
    if (newStatus === 'RESOLVED') {
      const task = tasks.find((t) => t.taskCode === taskCode);
      setResolvingTask(task);
      setResolutionNotes('');
      return;
    }

    try {
      await api.updateHandoverTaskStatus(taskCode, {
        status: newStatus,
        resolvedBy: user?.fullName || 'Ramasamy (Main Gate Security)'
      });
      loadHandoverData();
    } catch (e) {
      console.error('Task status update error:', e);
    }
  };

  // Confirm Task Resolution
  const handleConfirmResolve = async () => {
    if (!resolvingTask) return;
    try {
      await api.updateHandoverTaskStatus(resolvingTask.taskCode, {
        status: 'RESOLVED',
        resolvedBy: user?.fullName || 'Ramasamy (Main Gate Security)',
        notes: resolutionNotes.trim() || 'Task checked and resolved on duty.'
      });
      setResolvingTask(null);
      setToastMessage(`✅ Task ${resolvingTask.taskCode} marked as RESOLVED.`);
      loadHandoverData();
    } catch (e) {
      console.error('Resolution error:', e);
    }
  };

  // Supervisor Sign-off (Feature E)
  const handleSupervisorSignOff = async (e) => {
    e.preventDefault();
    if (!signingHandover) return;
    try {
      await api.supervisorSignOffHandover(signingHandover.id, {
        supervisorName: 'Dr. Sundaram (Chief Security Officer)',
        supervisorNotes: supervisorNotes.trim() || 'Verified all pending tasks and shift logs.'
      });
      setSigningHandover(null);
      setToastMessage('👔 Supervisor sign-off approved and logged.');
      loadHandoverData();
    } catch (e) {
      console.error('Sign-off error:', e);
    }
  };

  // Filter tasks
  const filteredTasks = tasks.filter((t) => {
    if (selectedCategory !== 'ALL' && t.category !== selectedCategory) return false;
    if (selectedStatus !== 'ALL' && t.status !== selectedStatus) return false;
    if (selectedPriority !== 'ALL' && t.priority !== selectedPriority) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        t.title?.toLowerCase().includes(q) ||
        t.taskCode?.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q) ||
        t.sourceReferenceId?.toLowerCase().includes(q)
      );
    }
    return true;
  });

  // Calculate categorized metrics
  const visitorCount = tasks.filter((t) => t.category === 'VISITORS' && t.status !== 'RESOLVED').length;
  const parcelCount = tasks.filter((t) => t.category === 'PARCELS' && t.status !== 'RESOLVED').length;
  const incidentCount = tasks.filter((t) => t.category === 'INCIDENTS' && t.status !== 'RESOLVED').length;
  const equipmentCount = tasks.filter((t) => t.category === 'EQUIPMENT').length;

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

      {/* HEADER BANNER */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '16px',
        padding: '1.25rem 1.75rem',
        border: '1px solid #E2E8F0',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.35rem' }}>
            <span style={{
              backgroundColor: '#EFF6FF',
              color: '#1D4ED8',
              fontSize: '0.72rem',
              fontWeight: 800,
              padding: '3px 10px',
              borderRadius: '999px',
              display: 'flex',
              alignItems: 'center',
              gap: '5px'
            }}>
              <ClipboardCheck size={13} />
              DIGITAL SHIFT HANDOVER
            </span>

            <span style={{
              backgroundColor: '#F1F5F9',
              color: '#0F172A',
              fontSize: '0.72rem',
              fontWeight: 800,
              padding: '3px 10px',
              borderRadius: '999px'
            }}>
              Main Gate 1 &bull; Active Shift: Morning (06:00 AM - 02:00 PM)
            </span>
          </div>

          <h2 style={{ fontSize: '1.45rem', fontWeight: 900, color: '#0F172A', margin: 0, letterSpacing: '-0.02em' }}>
            Smart Digital Shift Handover
          </h2>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.88rem', color: '#64748B' }}>
            Seamless shift transition. Auto-aggregates pending visitors, uncollected parcels, incidents & equipment tasks across shifts.
          </p>
        </div>

        {/* Role Switcher & Action Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Simulated Guard Role Toggle */}
          <div style={{
            display: 'flex',
            backgroundColor: '#F1F5F9',
            padding: '4px',
            borderRadius: '10px',
            border: '1px solid #E2E8F0'
          }}>
            {[
              { id: 'OUTGOING', label: 'Outgoing Guard (Shift A)' },
              { id: 'INCOMING', label: 'Incoming Guard (Shift B)' },
              { id: 'SUPERVISOR', label: 'Supervisor (Audit)' }
            ].map((role) => (
              <button
                key={role.id}
                type="button"
                onClick={() => setViewRole(role.id)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '8px',
                  border: 'none',
                  fontSize: '0.78rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  backgroundColor: viewRole === role.id ? '#ffffff' : 'transparent',
                  color: viewRole === role.id ? '#0F172A' : '#64748B',
                  boxShadow: viewRole === role.id ? '0 2px 4px rgba(0,0,0,0.06)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                {role.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={handleOpenCreateModal}
            style={{
              backgroundColor: '#2563EB',
              color: '#ffffff',
              padding: '0.65rem 1.15rem',
              borderRadius: '10px',
              fontSize: '0.85rem',
              fontWeight: 800,
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: '0 8px 16px -4px rgba(37, 99, 235, 0.4)'
            }}
          >
            <Plus size={16} />
            <span>Create Shift Handover</span>
          </button>
        </div>
      </div>

      {/* TOAST NOTIFICATION */}
      {toastMessage && (
        <div className="animate-fade-in" style={{
          backgroundColor: '#ECFDF5',
          border: '1.5px solid #10B981',
          borderRadius: '12px',
          padding: '0.9rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          color: '#065F46',
          fontSize: '0.88rem',
          fontWeight: 700
        }}>
          <span>{toastMessage}</span>
          <button
            type="button"
            onClick={() => setToastMessage(null)}
            style={{ background: 'none', border: 'none', color: '#059669', cursor: 'pointer', fontWeight: 800 }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* FEATURE A & C: ACTIVE HANDOVER STATUS CARD */}
      {currentHandover && (
        <div className="card animate-fade-in" style={{
          border: currentHandover.status === 'PENDING_ACKNOWLEDGEMENT' ? '2px solid #F59E0B' : '2px solid #10B981',
          backgroundColor: '#ffffff',
          boxShadow: '0 8px 24px -4px rgba(15, 23, 42, 0.08)'
        }}>
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            borderBottom: '1px solid #E2E8F0',
            paddingBottom: '1rem',
            marginBottom: '1rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                width: '42px',
                height: '42px',
                borderRadius: '12px',
                backgroundColor: currentHandover.status === 'PENDING_ACKNOWLEDGEMENT' ? '#FEF3C7' : '#D1FAE5',
                color: currentHandover.status === 'PENDING_ACKNOWLEDGEMENT' ? '#B45309' : '#059669',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <ArrowLeftRight size={22} />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1.15rem', fontWeight: 900, color: '#0F172A' }}>
                    {currentHandover.handoverCode}
                  </span>
                  <span style={{
                    fontSize: '0.75rem',
                    fontWeight: 800,
                    padding: '3px 10px',
                    borderRadius: '999px',
                    backgroundColor: currentHandover.status === 'PENDING_ACKNOWLEDGEMENT' ? '#FEF3C7' : '#D1FAE5',
                    color: currentHandover.status === 'PENDING_ACKNOWLEDGEMENT' ? '#B45309' : '#065F46',
                    textTransform: 'uppercase'
                  }}>
                    {currentHandover.status === 'PENDING_ACKNOWLEDGEMENT' ? '⏳ Awaiting Acknowledgement' : '✅ Handover Acknowledged'}
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#64748B', marginTop: '2px' }}>
                  {currentHandover.shiftName} &bull; Handover at {new Date(currentHandover.handoverTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>

            {/* In-Card Action for Incoming Guard */}
            {currentHandover.status === 'PENDING_ACKNOWLEDGEMENT' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.72rem', color: '#D97706', fontWeight: 800, textTransform: 'uppercase' }}>
                    Action Required
                  </div>
                  <div style={{ fontSize: '0.82rem', color: '#78350F', fontWeight: 700 }}>
                    Incoming Guard ({currentHandover.incomingWatchmanName})
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleAcknowledge}
                  style={{
                    backgroundColor: '#059669',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '10px',
                    padding: '0.75rem 1.25rem',
                    fontSize: '0.88rem',
                    fontWeight: 900,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    boxShadow: '0 8px 16px -4px rgba(5, 150, 105, 0.4)'
                  }}
                >
                  <CheckCircle2 size={18} />
                  <span>Acknowledge & Accept Shift</span>
                </button>
              </div>
            )}
          </div>

          {/* Handover Details Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
            <div style={{ backgroundColor: '#F8FAFC', padding: '0.75rem', borderRadius: '10px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 800, textTransform: 'uppercase' }}>
                Outgoing Guard
              </div>
              <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#0F172A', marginTop: '2px' }}>
                {currentHandover.outgoingWatchmanName}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748B' }}>ID: {currentHandover.outgoingWatchmanId}</div>
            </div>

            <div style={{ backgroundColor: '#F8FAFC', padding: '0.75rem', borderRadius: '10px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 800, textTransform: 'uppercase' }}>
                Incoming Guard
              </div>
              <div style={{ fontSize: '0.92rem', fontWeight: 800, color: '#0F172A', marginTop: '2px' }}>
                {currentHandover.incomingWatchmanName}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748B' }}>ID: {currentHandover.incomingWatchmanId}</div>
            </div>

            <div style={{ backgroundColor: '#F8FAFC', padding: '0.75rem', borderRadius: '10px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 800, textTransform: 'uppercase' }}>
                Acknowledgement
              </div>
              <div style={{ fontSize: '0.88rem', fontWeight: 800, color: currentHandover.acknowledgedAt ? '#059669' : '#D97706', marginTop: '2px' }}>
                {currentHandover.acknowledgedAt
                  ? `Signed at ${new Date(currentHandover.acknowledgedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                  : 'Pending Guard Sign-off'}
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748B' }}>
                {currentHandover.acknowledgedByWatchmanName || 'Awaiting Shift B'}
              </div>
            </div>

            <div style={{ backgroundColor: '#F8FAFC', padding: '0.75rem', borderRadius: '10px', border: '1px solid #E2E8F0' }}>
              <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 800, textTransform: 'uppercase' }}>
                Unresolved Tasks
              </div>
              <div style={{ fontSize: '1.1rem', fontWeight: 900, color: '#DC2626', marginTop: '2px' }}>
                {tasks.filter((t) => t.status !== 'RESOLVED').length} Active Tasks
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748B' }}>Continuity preserved across shifts</div>
            </div>
          </div>

          {/* Outgoing Guard Handover Notes */}
          {currentHandover.handoverNotes && (
            <div style={{
              backgroundColor: '#EFF6FF',
              border: '1px solid #BFDBFE',
              borderRadius: '10px',
              padding: '0.85rem 1rem',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.6rem'
            }}>
              <FileText size={18} color="#2563EB" style={{ marginTop: '2px', flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#1E40AF', textTransform: 'uppercase' }}>
                  Outgoing Guard Shift Notes (முந்தைய வாட்ச்மேன் குறிப்பு)
                </div>
                <div style={{ fontSize: '0.86rem', color: '#1E3A8A', marginTop: '2px' }}>
                  {currentHandover.handoverNotes}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 4 CATEGORY METRIC PILLS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
        {[
          { id: 'VISITORS', label: 'Visitors Inside Campus', count: visitorCount, icon: Users, color: '#2563EB', bg: '#EFF6FF' },
          { id: 'PARCELS', label: 'Uncollected Parcels', count: parcelCount, icon: Package, color: '#D97706', bg: '#FEF3C7' },
          { id: 'INCIDENTS', label: 'Incidents & Alerts', count: incidentCount, icon: AlertOctagon, color: '#DC2626', bg: '#FEE2E2' },
          { id: 'EQUIPMENT', label: 'Gate Equipment', count: equipmentCount, icon: ShieldCheck, color: '#0D9488', bg: '#CCFBF1' }
        ].map((cat) => {
          const Icon = cat.icon;
          const isSelected = selectedCategory === cat.id;
          return (
            <div
              key={cat.id}
              onClick={() => setSelectedCategory(selectedCategory === cat.id ? 'ALL' : cat.id)}
              style={{
                backgroundColor: '#ffffff',
                borderRadius: '14px',
                padding: '1rem 1.25rem',
                border: isSelected ? `2px solid ${cat.color}` : '1px solid #E2E8F0',
                boxShadow: isSelected ? `0 8px 16px -4px ${cat.color}30` : '0 2px 4px rgba(0,0,0,0.04)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '10px',
                  backgroundColor: cat.bg,
                  color: cat.color,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <Icon size={20} />
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 800, color: '#64748B', textTransform: 'uppercase' }}>
                    {cat.label}
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 900, color: '#0F172A', marginTop: '2px' }}>
                    {cat.count}
                  </div>
                </div>
              </div>
              <span style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                color: isSelected ? cat.color : '#94A3B8'
              }}>
                {isSelected ? 'Filtered' : 'Click to filter'}
              </span>
            </div>
          );
        })}
      </div>

      {/* FILTER & SEARCH BAR */}
      <div style={{
        backgroundColor: '#ffffff',
        borderRadius: '14px',
        padding: '0.85rem 1.25rem',
        border: '1px solid #E2E8F0',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '0.75rem'
      }}>
        {/* Search Input */}
        <div style={{ position: 'relative', flex: '1', minWidth: '220px' }}>
          <Search size={16} color="#94A3B8" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input
            type="text"
            className="input-field"
            placeholder="Search tasks by ID, visitor name, parcel #..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: '36px', marginBottom: 0, height: '38px' }}
          />
        </div>

        {/* Filter controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <select
            className="input-field"
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            style={{ marginBottom: 0, height: '38px', fontSize: '0.8rem', fontWeight: 700 }}
          >
            <option value="ALL">All Categories</option>
            <option value="VISITORS">Visitors Inside</option>
            <option value="PARCELS">Gate Parcels</option>
            <option value="INCIDENTS">Incidents & SOS</option>
            <option value="EQUIPMENT">Equipment Checks</option>
          </select>

          <select
            className="input-field"
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            style={{ marginBottom: 0, height: '38px', fontSize: '0.8rem', fontWeight: 700 }}
          >
            <option value="ALL">All Statuses</option>
            <option value="OPEN">Open Tasks</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="RESOLVED">Resolved Tasks</option>
          </select>

          <select
            className="input-field"
            value={selectedPriority}
            onChange={(e) => setSelectedPriority(e.target.value)}
            style={{ marginBottom: 0, height: '38px', fontSize: '0.8rem', fontWeight: 700 }}
          >
            <option value="ALL">All Priorities</option>
            <option value="HIGH">High Priority</option>
            <option value="MEDIUM">Medium Priority</option>
            <option value="LOW">Low Priority</option>
          </select>

          {(selectedCategory !== 'ALL' || selectedStatus !== 'ALL' || selectedPriority !== 'ALL' || searchQuery) && (
            <button
              type="button"
              onClick={() => {
                setSelectedCategory('ALL');
                setSelectedStatus('ALL');
                setSelectedPriority('ALL');
                setSearchQuery('');
              }}
              style={{
                background: '#F1F5F9',
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                padding: '8px 12px',
                fontSize: '0.78rem',
                fontWeight: 700,
                color: '#64748B',
                cursor: 'pointer'
              }}
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* FEATURE D: TASK CONTINUITY LIST */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
              Shift Task Continuity Register (தொடரும் பணிகள்)
            </h3>
            <span className="badge badge-blue">{filteredTasks.length} Tasks Listed</span>
          </div>
          <span style={{ fontSize: '0.78rem', color: '#64748B' }}>
            Tasks remain active across subsequent shifts until formally resolved.
          </span>
        </div>

        {filteredTasks.length === 0 ? (
          <div className="card" style={{ padding: '2.5rem', textAlign: 'center', backgroundColor: '#F8FAFC' }}>
            <CheckCircle2 size={36} color="#10B981" style={{ margin: '0 auto 0.5rem auto' }} />
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 800, color: '#0F172A' }}>
              No Tasks Matching Current Filters
            </h4>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.82rem', color: '#64748B' }}>
              All items in this view are cleared.
            </p>
          </div>
        ) : (
          filteredTasks.map((task) => {
            const isResolved = task.status === 'RESOLVED';
            const isHigh = task.priority === 'HIGH';

            return (
              <div
                key={task.taskCode}
                className="card animate-fade-in"
                style={{
                  backgroundColor: isResolved ? '#F8FAFC' : '#ffffff',
                  border: isHigh && !isResolved ? '2px solid #F87171' : '1px solid #E2E8F0',
                  opacity: isResolved ? 0.75 : 1,
                  padding: '1.25rem 1.5rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                  boxShadow: isHigh && !isResolved ? '0 6px 16px -4px rgba(239, 68, 68, 0.15)' : '0 2px 4px rgba(0,0,0,0.03)'
                }}
              >
                {/* Task Top Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span style={{
                      backgroundColor: task.category === 'VISITORS' ? '#EFF6FF' :
                                       task.category === 'PARCELS' ? '#FEF3C7' :
                                       task.category === 'INCIDENTS' ? '#FEE2E2' : '#CCFBF1',
                      color: task.category === 'VISITORS' ? '#1D4ED8' :
                             task.category === 'PARCELS' ? '#B45309' :
                             task.category === 'INCIDENTS' ? '#DC2626' : '#0F766E',
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      padding: '2px 8px',
                      borderRadius: '6px',
                      textTransform: 'uppercase'
                    }}>
                      {task.category}
                    </span>

                    <code style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0F172A' }}>
                      {task.taskCode}
                    </code>

                    {task.sourceReferenceId && (
                      <span style={{ fontSize: '0.74rem', color: '#64748B' }}>
                        Ref: <strong>{task.sourceReferenceId}</strong>
                      </span>
                    )}

                    <span style={{
                      fontSize: '0.68rem',
                      fontWeight: 800,
                      padding: '2px 6px',
                      borderRadius: '4px',
                      backgroundColor: task.priority === 'HIGH' ? '#FEF2F2' : task.priority === 'MEDIUM' ? '#FFFBEB' : '#F1F5F9',
                      color: task.priority === 'HIGH' ? '#DC2626' : task.priority === 'MEDIUM' ? '#D97706' : '#475569'
                    }}>
                      {task.priority} PRIORITY
                    </span>
                  </div>

                  {/* Status Badge */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{
                      fontSize: '0.75rem',
                      fontWeight: 800,
                      padding: '3px 10px',
                      borderRadius: '999px',
                      backgroundColor: isResolved ? '#D1FAE5' : task.status === 'IN_PROGRESS' ? '#DBEAFE' : '#FEE2E2',
                      color: isResolved ? '#065F46' : task.status === 'IN_PROGRESS' ? '#1E40AF' : '#991B1B'
                    }}>
                      {task.status}
                    </span>
                  </div>
                </div>

                {/* Task Title & Description */}
                <div>
                  <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: '#0F172A' }}>
                    {task.title}
                  </h4>
                  <p style={{ margin: '3px 0 0 0', fontSize: '0.85rem', color: '#475569' }}>
                    {task.description}
                  </p>
                </div>

                {/* Next Action Box */}
                {task.nextRequiredAction && (
                  <div style={{
                    backgroundColor: isResolved ? '#F1F5F9' : '#FEF3C7',
                    border: isResolved ? '1px solid #E2E8F0' : '1px solid #FDE68A',
                    borderRadius: '8px',
                    padding: '0.6rem 0.85rem',
                    fontSize: '0.8rem',
                    color: isResolved ? '#475569' : '#92400E',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}>
                    <Clock size={14} />
                    <span><strong>Next Required Action:</strong> {task.nextRequiredAction}</span>
                  </div>
                )}

                {/* Audit & Action Buttons */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderTop: '1px solid #F1F5F9',
                  paddingTop: '0.6rem',
                  fontSize: '0.74rem',
                  color: '#64748B'
                }}>
                  <div>
                    {isResolved ? (
                      <span style={{ color: '#059669', fontWeight: 700 }}>
                        Resolved by {task.resolvedBy} at {task.resolvedAt ? new Date(task.resolvedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'earlier'}.
                        {task.resolutionNotes && ` ("${task.resolutionNotes}")`}
                      </span>
                    ) : (
                      <span>Created: {new Date(task.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} &bull; Last checked on shift</span>
                    )}
                  </div>

                  {/* Task Action Buttons */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    {!isResolved && task.status === 'OPEN' && (
                      <button
                        type="button"
                        onClick={() => handleUpdateStatus(task.taskCode, 'IN_PROGRESS')}
                        style={{
                          background: '#EFF6FF',
                          border: '1px solid #BFDBFE',
                          borderRadius: '6px',
                          padding: '4px 8px',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          color: '#1D4ED8',
                          cursor: 'pointer'
                        }}
                      >
                        Mark In Progress
                      </button>
                    )}

                    {!isResolved ? (
                      <button
                        type="button"
                        onClick={() => handleUpdateStatus(task.taskCode, 'RESOLVED')}
                        style={{
                          backgroundColor: '#059669',
                          border: 'none',
                          borderRadius: '6px',
                          padding: '4px 10px',
                          fontSize: '0.75rem',
                          fontWeight: 800,
                          color: '#ffffff',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                      >
                        <Check size={12} />
                        <span>Resolve Task</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleUpdateStatus(task.taskCode, 'OPEN')}
                        style={{
                          background: '#F1F5F9',
                          border: '1px solid #CBD5E1',
                          borderRadius: '6px',
                          padding: '3px 8px',
                          fontSize: '0.72rem',
                          color: '#64748B',
                          cursor: 'pointer'
                        }}
                      >
                        Re-open
                      </button>
                    )}
                  </div>
                </div>

              </div>
            );
          })
        )}
      </div>

      {/* FEATURE E: SUPERVISOR AUDIT & SHIFT HISTORY TABLE */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
              Supervisor Audit & Shift Handover History (மேற்பார்வையாளர் தணிக்கை)
            </h3>
            <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: '#64748B' }}>
              Permanent record of shift handovers, outgoing/incoming guard signatures, and supervisor reviews.
            </p>
          </div>
          <span className="badge badge-blue">{allHandovers.length} Total Handovers</span>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Shift</th>
                <th>Outgoing Guard</th>
                <th>Incoming Guard</th>
                <th>Handover Time</th>
                <th>Acknowledged Time</th>
                <th>Status</th>
                <th>Supervisor Review</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {allHandovers.map((h) => (
                <tr key={h.id}>
                  <td>
                    <code style={{ fontWeight: 800, color: '#2563EB' }}>{h.handoverCode}</code>
                  </td>
                  <td style={{ fontSize: '0.82rem', fontWeight: 600 }}>{h.shiftName}</td>
                  <td style={{ fontSize: '0.82rem' }}>
                    <strong>{h.outgoingWatchmanName}</strong>
                    <div style={{ fontSize: '0.7rem', color: '#64748B' }}>{h.outgoingWatchmanId}</div>
                  </td>
                  <td style={{ fontSize: '0.82rem' }}>
                    <strong>{h.incomingWatchmanName}</strong>
                    <div style={{ fontSize: '0.7rem', color: '#64748B' }}>{h.incomingWatchmanId}</div>
                  </td>
                  <td style={{ fontSize: '0.8rem', color: '#475569' }}>
                    {new Date(h.handoverTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td style={{ fontSize: '0.8rem' }}>
                    {h.acknowledgedAt ? (
                      <span style={{ color: '#059669', fontWeight: 700 }}>
                        {new Date(h.acknowledgedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    ) : (
                      <span style={{ color: '#D97706', fontWeight: 700 }}>Pending</span>
                    )}
                  </td>
                  <td>
                    <span style={{
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      padding: '2px 8px',
                      borderRadius: '999px',
                      backgroundColor: h.status === 'SUPERVISOR_REVIEWED' ? '#EFF6FF' :
                                       h.status === 'ACKNOWLEDGED' ? '#D1FAE5' : '#FEF3C7',
                      color: h.status === 'SUPERVISOR_REVIEWED' ? '#1D4ED8' :
                             h.status === 'ACKNOWLEDGED' ? '#065F46' : '#B45309'
                    }}>
                      {h.status}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.78rem' }}>
                    {h.supervisorSignedBy ? (
                      <span style={{ color: '#1D4ED8', fontWeight: 700 }}>
                        {h.supervisorSignedBy}
                      </span>
                    ) : (
                      <span style={{ color: '#94A3B8' }}>Awaiting Sign-off</span>
                    )}
                  </td>
                  <td>
                    {!h.supervisorSignedBy && (
                      <button
                        type="button"
                        onClick={() => {
                          setSigningHandover(h);
                          setSupervisorNotes('');
                        }}
                        style={{
                          background: '#EFF6FF',
                          border: '1px solid #BFDBFE',
                          borderRadius: '6px',
                          padding: '4px 8px',
                          fontSize: '0.74rem',
                          fontWeight: 700,
                          color: '#1D4ED8',
                          cursor: 'pointer'
                        }}
                      >
                        Sign Off
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* MODAL 1: CREATE SHIFT HANDOVER MODAL (FEATURE B) */}
      {showCreateModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(6px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '1rem'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '20px',
            maxWidth: '680px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '1.75rem',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <div style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '10px',
                  backgroundColor: '#EFF6FF',
                  color: '#2563EB',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <Plus size={20} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.2rem', fontWeight: 800, margin: 0, color: '#0F172A' }}>
                    Create Digital Shift Handover
                  </h3>
                  <span style={{ fontSize: '0.78rem', color: '#64748B' }}>
                    Auto-includes pending tasks from Visitors, Parcels & Equipment
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                style={{ background: 'none', border: 'none', color: '#64748B', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmitHandover} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Shift & Relieving Guard */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '0.75rem' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label" style={{ fontWeight: 700 }}>Current Shift</label>
                  <select
                    className="input-field"
                    value={newShiftName}
                    onChange={(e) => setNewShiftName(e.target.value)}
                  >
                    <option value="Morning Shift (06:00 AM - 02:00 PM)">Morning Shift (06:00 AM - 02:00 PM)</option>
                    <option value="Evening Shift (02:00 PM - 10:00 PM)">Evening Shift (02:00 PM - 10:00 PM)</option>
                    <option value="Night Shift (10:00 PM - 06:00 AM)">Night Shift (10:00 PM - 06:00 AM)</option>
                  </select>
                </div>

                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label" style={{ fontWeight: 700 }}>Incoming Guard (Relief)</label>
                  <select
                    className="input-field"
                    value={newIncomingId}
                    onChange={(e) => {
                      setNewIncomingId(e.target.value);
                      if (e.target.value === 'WM-02') setNewIncomingName('Murugan (Gate Guard - Shift B)');
                      if (e.target.value === 'WM-03') setNewIncomingName('Selvam (Night Security)');
                    }}
                  >
                    <option value="WM-02">Murugan (Gate Guard - Shift B)</option>
                    <option value="WM-03">Selvam (Night Security - Shift C)</option>
                  </select>
                </div>
              </div>

              {/* Handover Notes */}
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label" style={{ fontWeight: 700 }}>
                  Outgoing Guard Shift Notes (முக்கிய அறிவிப்புகள்)
                </label>
                <textarea
                  rows={3}
                  className="input-field"
                  placeholder="e.g. Principal instructed strict student checking today; Gate boom barrier sensor cleaned; All radios charged."
                  value={handoverNotes}
                  onChange={(e) => setHandoverNotes(e.target.value)}
                  style={{ resize: 'vertical' }}
                />
              </div>

              {/* Auto-Aggregated Tasks List */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <label className="form-label" style={{ fontWeight: 700, margin: 0 }}>
                    Select Unresolved Tasks to Hand Over ({selectedTaskCodes.length}/{autoDetectedTasks.length})
                  </label>
                  <span style={{ fontSize: '0.74rem', color: '#2563EB', fontWeight: 700 }}>
                    Auto-scanned from active campus modules
                  </span>
                </div>

                <div style={{
                  maxHeight: '220px',
                  overflowY: 'auto',
                  border: '1px solid #E2E8F0',
                  borderRadius: '10px',
                  padding: '0.5rem'
                }}>
                  {autoDetectedTasks.map((task) => {
                    const isChecked = selectedTaskCodes.includes(task.taskCode);
                    return (
                      <div
                        key={task.taskCode}
                        onClick={() => {
                          if (isChecked) {
                            setSelectedTaskCodes(selectedTaskCodes.filter((c) => c !== task.taskCode));
                          } else {
                            setSelectedTaskCodes([...selectedTaskCodes, task.taskCode]);
                          }
                        }}
                        style={{
                          padding: '0.6rem 0.75rem',
                          borderRadius: '8px',
                          backgroundColor: isChecked ? '#EFF6FF' : '#ffffff',
                          border: isChecked ? '1px solid #BFDBFE' : '1px solid #F1F5F9',
                          marginBottom: '0.4rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.6rem'
                        }}
                      >
                        <div style={{ color: isChecked ? '#2563EB' : '#94A3B8' }}>
                          {isChecked ? <CheckSquare size={18} /> : <Square size={18} />}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontSize: '0.7rem', fontWeight: 800, color: '#64748B' }}>
                              [{task.category}] {task.taskCode}
                            </span>
                            <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0F172A' }}>
                              {task.title}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.74rem', color: '#64748B', marginTop: '2px' }}>
                            {task.nextRequiredAction || task.description}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Submit Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn btn-secondary"
                  style={{ fontWeight: 700 }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingHandover}
                  className="btn btn-primary"
                  style={{ fontWeight: 800 }}
                >
                  {submittingHandover ? 'Saving Handover...' : 'Submit Handover for Incoming Shift'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: RESOLVE TASK MODAL */}
      {resolvingTask && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(6px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '1rem'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            maxWidth: '500px',
            width: '100%',
            padding: '1.5rem',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.15rem', fontWeight: 800, color: '#0F172A' }}>
              Confirm Task Resolution
            </h3>
            <p style={{ margin: '0 0 1rem 0', fontSize: '0.85rem', color: '#64748B' }}>
              Resolving <strong>{resolvingTask.taskCode}</strong>: {resolvingTask.title}
            </p>

            <div className="form-group">
              <label className="form-label" style={{ fontWeight: 700 }}>Resolution Notes</label>
              <textarea
                rows={3}
                required
                className="input-field"
                placeholder="e.g. Student departed via Gate 1; badge returned / Parcel collected by recipient with OTP."
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem' }}>
              <button
                type="button"
                onClick={() => setResolvingTask(null)}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmResolve}
                className="btn btn-primary"
                style={{ backgroundColor: '#059669', borderColor: '#059669', fontWeight: 800 }}
              >
                Mark Task Resolved
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: SUPERVISOR SIGN-OFF MODAL (FEATURE E) */}
      {signingHandover && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(6px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '1rem'
        }}>
          <div style={{
            backgroundColor: '#ffffff',
            borderRadius: '16px',
            maxWidth: '500px',
            width: '100%',
            padding: '1.5rem',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
          }}>
            <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.15rem', fontWeight: 800, color: '#0F172A' }}>
              Supervisor Sign-off & Audit
            </h3>
            <p style={{ margin: '0 0 1rem 0', fontSize: '0.85rem', color: '#64748B' }}>
              Approving Shift Handover <strong>{signingHandover.handoverCode}</strong> ({signingHandover.shiftName}).
            </p>

            <form onSubmit={handleSupervisorSignOff}>
              <div className="form-group">
                <label className="form-label" style={{ fontWeight: 700 }}>Supervisor Audit Remarks</label>
                <textarea
                  rows={3}
                  className="input-field"
                  placeholder="e.g. All gate registers, visitor badges, and barrier operations verified."
                  value={supervisorNotes}
                  onChange={(e) => setSupervisorNotes(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem' }}>
                <button
                  type="button"
                  onClick={() => setSigningHandover(null)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{ fontWeight: 800 }}
                >
                  Approve Sign-off
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
