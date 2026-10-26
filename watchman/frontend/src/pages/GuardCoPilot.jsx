import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Sparkles,
  Mic,
  MicOff,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Clock,
  Send,
  Shield,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Check,
  X,
  Lock,
  Wrench,
  Building,
  Info,
  FileText,
  Volume2
} from 'lucide-react';

export const GuardCoPilot = () => {
  const { user, language } = useAuth();

  // ── Situation Card State ────────────────────────────────────
  const [selectedLocation, setSelectedLocation] = useState('North Parking Bay & Drainage');
  const [situationToast, setSituationToast] = useState(null);

  // ── Recent Situations List (Initialized to match mockup) ──
  const [recentSituations, setRecentSituations] = useState([
    {
      id: 1,
      title: 'Unauthorized vehicle detected at North Parking Bay',
      subtext: 'Vehicle: KA01MJ7766 • 12:32 PM',
      status: 'Critical',
      color: '#DC2626',
      badgeBg: '#FEE2E2',
      badgeColor: '#DC2626'
    },
    {
      id: 2,
      title: 'Motion detected near Drainage Channel',
      subtext: 'Zone: ZB-02 • 11:48 AM',
      status: 'Attention',
      color: '#D97706',
      badgeBg: '#FEF3C7',
      badgeColor: '#D97706'
    },
    {
      id: 3,
      title: 'All clear at East Zone',
      subtext: 'Zone: EZ-01 • 10:15 AM',
      status: 'Normal',
      color: '#16A34A',
      badgeBg: '#DCFCE7',
      badgeColor: '#16A34A'
    }
  ]);

  // ── Voice Incident State ────────────────────────────────────
  const [isRecording, setIsRecording] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState('');
  const [parsedIncident, setParsedIncident] = useState(null);
  const [submittingVoice, setSubmittingVoice] = useState(false);

  // ── Priority Tasks State (Initialized to match mockup) ─────
  const [criticalTasks, setCriticalTasks] = useState([
    {
      id: 'crit-1',
      title: 'North Parking Bay — Unauthorized vehicle',
      subtext: 'Gate 1 • 12:32 PM • Verify & remove vehicle'
    },
    {
      id: 'crit-2',
      title: 'Drainage Channel — Motion detected',
      subtext: 'Zone ZB-02 • 11:48 AM • Check area'
    },
    {
      id: 'crit-3',
      title: 'Perimeter Wall — Sensor alert',
      subtext: 'Zone PW-01 • 10:20 AM • Investigate'
    }
  ]);

  const [highPriorityTasks, setHighPriorityTasks] = useState([
    {
      id: 'high-1',
      title: 'Main Gate — Visitor delay',
      subtext: 'Gate 1 • 11:05 AM • Update visitor',
      iconType: 'lock'
    },
    {
      id: 'high-2',
      title: 'West Block — Maintenance issue',
      subtext: 'Block B • 09:40 AM • Notify maintenance',
      iconType: 'wrench'
    }
  ]);

  const [routineTasks, setRoutineTasks] = useState([
    {
      id: 'rout-1',
      title: 'Canteen Area — Routine check',
      subtext: 'Zone CA • 09:15 AM • Verify CCTV',
      iconType: 'building'
    }
  ]);

  // ── Carry-Forward Handover State ─────────────────────────────
  const [showHandoverDrawer, setShowHandoverDrawer] = useState(false);
  const [handoverAcknowledged, setHandoverAcknowledged] = useState(false);
  const [carryForwardItems, setCarryForwardItems] = useState([
    {
      id: 'cf-1',
      category: 'MAINTENANCE',
      title: 'Main Gate Barrier Sensor Flickering',
      description: 'Sensor occasionally misses low-clearance scooters and requires inspection.',
      urgency: 'HIGH',
      shift: 'Shift B (Night)'
    },
    {
      id: 'cf-2',
      category: 'VISITOR_LOG',
      title: 'Pending ID Proof for Contractor Team at Block B',
      description: '4 electricians permitted on verbal clearance; physical ID copies pending.',
      urgency: 'HIGH',
      shift: 'Shift B (Night)'
    },
    {
      id: 'cf-3',
      category: 'PARCELS',
      title: 'Follow up on Uncollected Laptop Parcel #4412',
      description: 'Student promised collection at 09:00 AM. Stored in Locker #2.',
      urgency: 'NORMAL',
      shift: 'Shift B (Night)'
    }
  ]);

  const [loading, setLoading] = useState(false);

  // Sync background data
  const fetchCoPilotData = async () => {
    setLoading(true);
    try {
      const [situations, queue] = await Promise.all([
        api.getLatestSituations(),
        api.getPrioritizedTasks()
      ]);

      if (situations && situations.length > 0) {
        setRecentSituations(prev => {
          const newEntries = situations.map(s => ({
            id: s.id,
            title: `${s.location} — ${s.notes || s.status}`,
            subtext: `Zone: ${s.location} • Just now`,
            status: s.status === 'EMERGENCY' || s.status === 'SUSPICIOUS' ? 'Critical' : s.status === 'ATTENTION_NEEDED' ? 'Attention' : 'Normal',
            color: s.status === 'NORMAL' ? '#16A34A' : s.status === 'ATTENTION_NEEDED' ? '#D97706' : '#DC2626',
            badgeBg: s.status === 'NORMAL' ? '#DCFCE7' : s.status === 'ATTENTION_NEEDED' ? '#FEF3C7' : '#FEE2E2',
            badgeColor: s.status === 'NORMAL' ? '#16A34A' : s.status === 'ATTENTION_NEEDED' ? '#D97706' : '#DC2626'
          }));
          return [...newEntries, ...prev].slice(0, 5);
        });
      }

      if (queue && queue.do_first && queue.do_first.length > 0) {
        setCriticalTasks(prev => {
          const mapped = queue.do_first.map(t => ({
            id: t.id,
            title: `${t.location} — ${t.title}`,
            subtext: `${t.created_at || '12:30 PM'} • ${t.suggested_action || 'Inspect'}`
          }));
          return [...mapped, ...prev].slice(0, 4);
        });
      }
    } catch {
      // Handled via local state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCoPilotData();
  }, []);

  // 1. Record Situation Status
  const handleRecordSituation = async (status) => {
    const statusLabel =
      status === 'NORMAL' ? 'Normal' :
      status === 'ATTENTION_NEEDED' ? 'Attention' :
      status === 'SUSPICIOUS' ? 'Suspicious' : 'Emergency';

    const newUpdate = {
      id: Date.now(),
      title: `Status marked as ${statusLabel} at ${selectedLocation}`,
      subtext: `Watchman ${user?.fullName || 'Ramasamy'} • Just now`,
      status: status === 'NORMAL' ? 'Normal' : status === 'ATTENTION_NEEDED' ? 'Attention' : 'Critical',
      color: status === 'NORMAL' ? '#16A34A' : status === 'ATTENTION_NEEDED' ? '#D97706' : '#DC2626',
      badgeBg: status === 'NORMAL' ? '#DCFCE7' : status === 'ATTENTION_NEEDED' ? '#FEF3C7' : '#FEE2E2',
      badgeColor: status === 'NORMAL' ? '#16A34A' : status === 'ATTENTION_NEEDED' ? '#D97706' : '#DC2626'
    };

    setRecentSituations(prev => [newUpdate, ...prev].slice(0, 5));
    setSituationToast(`✓ Recorded "${statusLabel}" for ${selectedLocation}`);
    setTimeout(() => setSituationToast(null), 3500);

    try {
      await api.recordSituationCard({
        location: selectedLocation,
        status,
        notes: `Status marked as ${status} by watchman.`,
        recorded_by: user?.fullName || 'Ramasamy (Main Gate Security)'
      });
    } catch {}
  };

  // 2. Voice Incident Recognition
  const toggleRecording = () => {
    if (!isRecording) {
      setIsRecording(true);
      if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRec();
        recognition.lang = language === 'ta' ? 'ta-IN' : 'en-IN';
        recognition.onresult = (event) => {
          const text = event.results[0][0].transcript;
          setVoiceTranscript(text);
          setIsRecording(false);
        };
        recognition.onerror = () => setIsRecording(false);
        recognition.start();
      } else {
        // High fidelity simulation
        setTimeout(() => {
          setVoiceTranscript('Unauthorized vehicle KA01MJ7766 parked at North Parking Bay near drainage channel.');
          setIsRecording(false);
        }, 1800);
      }
    } else {
      setIsRecording(false);
    }
  };

  const handleSendVoiceIncident = async () => {
    if (!voiceTranscript.trim()) return;
    setSubmittingVoice(true);
    try {
      const res = await api.sendVoiceIncident({
        transcript: voiceTranscript,
        spoken_by: user?.fullName || 'Watchman Ramasamy'
      });
      setParsedIncident(res);
      setVoiceTranscript('');

      // Add to critical tasks automatically
      setCriticalTasks(prev => [{
        id: `inc-${Date.now()}`,
        title: `${res.location || selectedLocation} — ${res.incident_type || 'Voice Incident'}`,
        subtext: `Gate 1 • Just now • Verify & inspect`
      }, ...prev]);

      fetchCoPilotData();
    } finally {
      setSubmittingVoice(false);
    }
  };

  // 3. Acknowledge Handover
  const handleAcknowledgeHandover = () => {
    setHandoverAcknowledged(true);
    setShowHandoverDrawer(false);
    setSituationToast('✓ Handover responsibilities successfully acknowledged and signed.');
    setTimeout(() => setSituationToast(null), 3500);
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

      {/* ── 1. TOP HEADER: TITLE + REFRESH ────────────────────────── */}
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
            backgroundColor: '#4F46E5',
            backgroundImage: 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            boxShadow: '0 4px 14px rgba(124, 58, 237, 0.25)',
            flexShrink: 0
          }}>
            <Sparkles size={24} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 900, color: '#0F172A', margin: 0, letterSpacing: '-0.02em' }}>
              {language === 'ta' ? 'AI கார்டு கோ-பைலட் & நிலைமை ரேடார்' : 'AI Guard Co-Pilot & Situation Radar'}
            </h1>
          </div>
        </div>

        <button
          type="button"
          onClick={fetchCoPilotData}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '0.55rem 0.95rem',
            borderRadius: '8px',
            border: '1.5px solid #CBD5E1',
            backgroundColor: '#FFFFFF',
            color: '#334155',
            fontSize: '0.8rem',
            fontWeight: 700,
            cursor: 'pointer',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
          }}
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} color="#4F46E5" />
          <span>{language === 'ta' ? 'புதுப்பி' : 'Refresh Co-Pilot'}</span>
        </button>
      </div>

      {situationToast && (
        <div className="animate-fade-in" style={{
          padding: '0.75rem 1rem',
          backgroundColor: '#ECFDF5',
          color: '#065F46',
          borderRadius: '10px',
          border: '1.5px solid #A7F3D0',
          fontSize: '0.825rem',
          fontWeight: 700
        }}>
          {situationToast}
        </div>
      )}

      {/* ── 2. HIGH-PRIORITY ALERT BANNER (EXACT MATCH TO PROPOSED UI) ── */}
      <div style={{
        backgroundColor: '#FEF2F2',
        border: '1.5px solid #FCA5A5',
        borderRadius: '12px',
        padding: '0.85rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
        flexWrap: 'wrap'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            backgroundColor: '#DC2626',
            color: '#FFFFFF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            <AlertTriangle size={18} />
          </div>
          <span style={{ fontSize: '0.92rem', fontWeight: 800, color: '#991B1B' }}>
            North Parking Bay — 9 status changes today. Perimeter inspection recommended.
          </span>
        </div>

        <button
          type="button"
          onClick={() => setSelectedLocation('North Parking Bay & Drainage')}
          style={{
            backgroundColor: '#DC2626',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '8px',
            padding: '0.5rem 1rem',
            fontSize: '0.8rem',
            fontWeight: 800,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            boxShadow: '0 2px 6px rgba(220, 38, 38, 0.25)',
            transition: 'all 0.15s ease'
          }}
          onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#B91C1C'; }}
          onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#DC2626'; }}
        >
          <span>View alert</span>
          <ChevronRight size={14} />
        </button>
      </div>

      {/* ── 3. FOUR TOP KPI METRIC CARDS (EXACT MATCH TO PROPOSED UI) ── */}
      <div className="responsive-kpi-4" style={{ alignItems: 'stretch' }}>
        {/* Card 1: Critical */}
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
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: '#FEE2E2',
                color: '#DC2626',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <AlertTriangle size={18} />
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>
                Critical
              </div>
            </div>
            <ChevronRight size={16} color="#94A3B8" />
          </div>
          <div>
            <div style={{ fontSize: '2.1rem', fontWeight: 900, color: '#0F172A', lineHeight: 1.1 }}>
              4
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', marginTop: '4px', fontWeight: 500 }}>
              Immediate attention required
            </div>
          </div>
        </div>

        {/* Card 2: Attention */}
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
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: '#FEF3C7',
                color: '#D97706',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <AlertCircle size={18} />
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>
                Attention
              </div>
            </div>
            <ChevronRight size={16} color="#94A3B8" />
          </div>
          <div>
            <div style={{ fontSize: '2.1rem', fontWeight: 900, color: '#0F172A', lineHeight: 1.1 }}>
              1
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', marginTop: '4px', fontWeight: 500 }}>
              Needs monitoring
            </div>
          </div>
        </div>

        {/* Card 3: Routine */}
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
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: '#EFF6FF',
                color: '#2563EB',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <Info size={18} />
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>
                Routine
              </div>
            </div>
            <ChevronRight size={16} color="#94A3B8" />
          </div>
          <div>
            <div style={{ fontSize: '2.1rem', fontWeight: 900, color: '#0F172A', lineHeight: 1.1 }}>
              1
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', marginTop: '4px', fontWeight: 500 }}>
              Normal operations
            </div>
          </div>
        </div>

        {/* Card 4: Pending handover */}
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
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: '#F1F5F9',
                color: '#475569',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <Clock size={18} />
              </div>
              <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>
                Pending handover
              </div>
            </div>
            <ChevronRight size={16} color="#94A3B8" />
          </div>
          <div>
            <div style={{ fontSize: '2.1rem', fontWeight: 900, color: '#0F172A', lineHeight: 1.1 }}>
              3
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748B', marginTop: '4px', fontWeight: 500 }}>
              Awaiting acknowledgement
            </div>
          </div>
        </div>
      </div>

      {/* ── 4. MIDDLE SECTION: SECURITY SITUATION & VOICE INCIDENT REPORT ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 420px), 1fr))',
        gap: '1.25rem',
        alignItems: 'stretch'
      }}>

        {/* 🔏 LEFT CARD: SECURITY SITUATION */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '14px',
          border: '1.5px solid #E2E8F0',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '1rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div>
            {/* Header: Shield Icon + Title + Location Dropdown */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1rem',
              flexWrap: 'wrap',
              gap: '0.65rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Shield size={20} color="#2563EB" />
                <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                  Security Situation
                </h3>
              </div>

              <select
                value={selectedLocation}
                onChange={(e) => setSelectedLocation(e.target.value)}
                style={{
                  padding: '0.45rem 0.85rem',
                  borderRadius: '8px',
                  border: '1.5px solid #CBD5E1',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  color: '#334155',
                  backgroundColor: '#FFFFFF',
                  cursor: 'pointer'
                }}
              >
                <option value="North Parking Bay & Drainage">North Parking Bay & Drainage</option>
                <option value="Main Gate & Boom Barrier">Main Gate & Boom Barrier</option>
                <option value="East Zone Perimeter">East Zone Perimeter</option>
                <option value="Hostel Rear Block">Hostel Rear Block</option>
                <option value="Science & Research Labs">Science & Research Labs</option>
              </select>
            </div>



            {/* Recent updates list */}
            <div>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '0.75rem'
              }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A' }}>
                  Recent updates
                </span>
                <span style={{ fontSize: '0.78rem', color: '#2563EB', fontWeight: 700, cursor: 'pointer' }}>
                  View all &rarr;
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                {recentSituations.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.55rem 0.75rem',
                      borderRadius: '8px',
                      backgroundColor: '#F8FAFC',
                      border: '1px solid #F1F5F9'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                      <span style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: item.color,
                        flexShrink: 0
                      }} />
                      <div>
                        <div style={{ fontSize: '0.825rem', fontWeight: 800, color: '#0F172A' }}>
                          {item.title}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: '1px' }}>
                          {item.subtext}
                        </div>
                      </div>
                    </div>

                    <span style={{
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      padding: '2px 8px',
                      borderRadius: '999px',
                      backgroundColor: item.badgeBg,
                      color: item.badgeColor
                    }}>
                      {item.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* 🎤 RIGHT CARD: VOICE INCIDENT REPORT */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '14px',
          border: '1.5px solid #E2E8F0',
          padding: '1.25rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '0.85rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div>
            {/* Header: Mic Icon + Title + Listening Ready Pill */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '0.75rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Mic size={20} color="#2563EB" />
                <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                  Voice Incident Report
                </h3>
              </div>

              <span style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '2px 8px',
                borderRadius: '999px',
                fontSize: '0.72rem',
                fontWeight: 800,
                backgroundColor: '#DCFCE7',
                color: '#15803D'
              }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#16A34A' }} />
                <span>Listening Ready</span>
              </span>
            </div>

            {/* Big Mic Button in Center */}
            <div style={{
              textAlign: 'center',
              margin: '0.5rem 0 0.85rem 0',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <button
                type="button"
                onClick={toggleRecording}
                style={{
                  width: '74px',
                  height: '74px',
                  borderRadius: '50%',
                  backgroundColor: isRecording ? '#DC2626' : '#2563EB',
                  color: '#FFFFFF',
                  border: isRecording ? '4px solid #FECACA' : 'none',
                  boxShadow: isRecording ? '0 0 25px rgba(220, 38, 38, 0.45)' : '0 4px 14px rgba(37, 99, 235, 0.3)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.2s ease'
                }}
              >
                {isRecording ? <MicOff size={32} /> : <Mic size={32} />}
              </button>
              <span style={{
                fontSize: '0.85rem',
                fontWeight: 700,
                color: isRecording ? '#DC2626' : '#2563EB',
                marginTop: '6px'
              }}>
                {isRecording ? 'Listening... Speak in Tamil or English' : 'Tap to speak'}
              </span>
            </div>

            {/* Text Input with Send Icon */}
            <div style={{ position: 'relative', marginBottom: '0.75rem' }}>
              <input
                type="text"
                placeholder="Or type your incident details..."
                value={voiceTranscript}
                onChange={(e) => setVoiceTranscript(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSendVoiceIncident(); }}
                style={{
                  width: '100%',
                  padding: '0.65rem 2.5rem 0.65rem 0.85rem',
                  borderRadius: '8px',
                  border: '1.5px solid #CBD5E1',
                  fontSize: '0.825rem',
                  backgroundColor: '#FFFFFF',
                  color: '#0F172A'
                }}
              />
              <button
                type="button"
                onClick={handleSendVoiceIncident}
                disabled={submittingVoice || !voiceTranscript.trim()}
                style={{
                  position: 'absolute',
                  right: '6px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: voiceTranscript.trim() ? '#2563EB' : '#94A3B8',
                  cursor: voiceTranscript.trim() ? 'pointer' : 'default',
                  padding: '4px'
                }}
              >
                <Send size={16} />
              </button>
            </div>

            {/* Sample commands */}
            <div style={{ marginBottom: '0.85rem' }}>
              <div style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 600, marginBottom: '5px' }}>
                Sample commands
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => setVoiceTranscript('Fire near library gate')}
                  style={{
                    backgroundColor: '#EFF6FF',
                    border: '1px solid #BFDBFE',
                    borderRadius: '999px',
                    padding: '3px 10px',
                    fontSize: '0.75rem',
                    color: '#1D4ED8',
                    cursor: 'pointer',
                    fontWeight: 600
                  }}
                >
                  "Fire near library gate"
                </button>
                <button
                  type="button"
                  onClick={() => setVoiceTranscript('Suspicious person at parking')}
                  style={{
                    backgroundColor: '#EFF6FF',
                    border: '1px solid #BFDBFE',
                    borderRadius: '999px',
                    padding: '3px 10px',
                    fontSize: '0.75rem',
                    color: '#1D4ED8',
                    cursor: 'pointer',
                    fontWeight: 600
                  }}
                >
                  "Suspicious person at parking"
                </button>
              </div>
            </div>
          </div>

          {/* Bottom Solid Blue CTA Button matching Proposed UI */}
          <button
            type="button"
            onClick={handleSendVoiceIncident}
            disabled={submittingVoice || (!voiceTranscript.trim() && !isRecording)}
            style={{
              width: '100%',
              backgroundColor: '#2563EB',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              padding: '0.7rem',
              fontSize: '0.85rem',
              fontWeight: 800,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: '0 2px 6px rgba(37, 99, 235, 0.25)',
              transition: 'all 0.15s ease'
            }}
          >
            <Sparkles size={16} />
            <span>{submittingVoice ? 'Processing NLP Ticket...' : 'Extract details & create ticket'}</span>
          </button>
        </div>

      </div>

      {/* ── PARSED NLP INCIDENT TICKET NOTIFICATION (IF CREATED) ── */}
      {parsedIncident && (
        <div className="animate-fade-in" style={{
          padding: '1rem 1.25rem',
          backgroundColor: '#F0FDF4',
          borderRadius: '12px',
          border: '1.5px solid #86EFAC',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
          boxShadow: '0 2px 8px rgba(22, 163, 74, 0.08)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#166534', backgroundColor: '#DCFCE7', padding: '2px 8px', borderRadius: '999px' }}>
              AI NLP EXTRACTION SUCCESS &bull; TICKET #{parsedIncident.ticket_number}
            </span>
            <span style={{ fontSize: '0.75rem', color: '#15803D', fontWeight: 700 }}>
              Location: <strong>{parsedIncident.location}</strong> &bull; Urgency: <strong>{parsedIncident.urgency}</strong>
            </span>
          </div>

          <div style={{ fontSize: '0.9rem', fontWeight: 800, color: '#0F172A' }}>
            {parsedIncident.description}
          </div>

          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            {parsedIncident.automated_actions && parsedIncident.automated_actions.map((act, idx) => (
              <span key={idx} style={{ fontSize: '0.72rem', fontWeight: 700, backgroundColor: '#FFFFFF', color: '#15803D', border: '1px solid #BBF7D0', padding: '2px 8px', borderRadius: '4px' }}>
                ⚡ {act}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ── 5. PRIORITY TASKS SECTION (3 EQUAL COLUMNS MATCHING PROPOSED UI) ── */}
      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '14px',
        border: '1.5px solid #E2E8F0',
        padding: '1.25rem',
        boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
      }}>
        {/* Header: Clipboard Icon + Title + Pill + View All */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '1rem',
          flexWrap: 'wrap',
          gap: '0.5rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <FileText size={20} color="#2563EB" />
            <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
              Priority tasks
            </h3>
            <span style={{
              fontSize: '0.72rem',
              fontWeight: 800,
              backgroundColor: '#EFF6FF',
              color: '#2563EB',
              border: '1px solid #BFDBFE',
              padding: '2px 8px',
              borderRadius: '999px'
            }}>
              3 active
            </span>
          </div>

          <span style={{ fontSize: '0.78rem', color: '#2563EB', fontWeight: 700, cursor: 'pointer' }}>
            View all &rarr;
          </span>
        </div>

        {/* 3 Columns Grid: Critical (Red) | High priority (Amber) | Routine (Blue) */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))',
          gap: '1rem'
        }}>

          {/* COLUMN 1: DO FIRST • Critical */}
          <div style={{
            backgroundColor: '#FFF5F5',
            borderRadius: '12px',
            border: '1.5px solid #FECDD3',
            padding: '1rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  backgroundColor: '#DC2626',
                  color: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.65rem',
                  fontWeight: 900
                }}>
                  ▲
                </span>
                <span style={{ fontSize: '0.825rem', fontWeight: 800, color: '#9F1239' }}>
                  DO FIRST &bull; Critical
                </span>
              </div>
              <span style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                backgroundColor: '#EF4444',
                color: '#FFFFFF',
                fontSize: '0.7rem',
                fontWeight: 900,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                4
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {criticalTasks.map((task) => (
                <div
                  key={task.id}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '8px',
                    padding: '0.65rem 0.85rem',
                    border: '1px solid #FECDD3',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#E11D48'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#FECDD3'; }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <span style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: '#DC2626',
                      marginTop: '6px',
                      flexShrink: 0
                    }} />
                    <div>
                      <div style={{ fontSize: '0.825rem', fontWeight: 800, color: '#0F172A', lineHeight: 1.25 }}>
                        {task.title}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: '2px' }}>
                        {task.subtext}
                      </div>
                    </div>
                  </div>
                  <ChevronRight size={15} color="#94A3B8" />
                </div>
              ))}
            </div>
          </div>

          {/* COLUMN 2: DO NEXT • High priority */}
          <div style={{
            backgroundColor: '#FFFBEB',
            borderRadius: '12px',
            border: '1.5px solid #FDE68A',
            padding: '1rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  backgroundColor: '#D97706',
                  color: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.65rem',
                  fontWeight: 900
                }}>
                  ●
                </span>
                <span style={{ fontSize: '0.825rem', fontWeight: 800, color: '#92400E' }}>
                  DO NEXT &bull; High priority
                </span>
              </div>
              <span style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                backgroundColor: '#F59E0B',
                color: '#FFFFFF',
                fontSize: '0.7rem',
                fontWeight: 900,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                2
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {highPriorityTasks.map((task) => (
                <div
                  key={task.id}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '8px',
                    padding: '0.65rem 0.85rem',
                    border: '1px solid #FDE68A',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#D97706'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#FDE68A'; }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <span style={{ color: '#D97706', marginTop: '2px', flexShrink: 0 }}>
                      {task.iconType === 'wrench' ? <Wrench size={13} /> : <Lock size={13} />}
                    </span>
                    <div>
                      <div style={{ fontSize: '0.825rem', fontWeight: 800, color: '#0F172A', lineHeight: 1.25 }}>
                        {task.title}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: '2px' }}>
                        {task.subtext}
                      </div>
                    </div>
                  </div>
                  <ChevronRight size={15} color="#94A3B8" />
                </div>
              ))}
            </div>
          </div>

          {/* COLUMN 3: LATER • Routine */}
          <div style={{
            backgroundColor: '#F0F7FF',
            borderRadius: '12px',
            border: '1.5px solid #BFDBFE',
            padding: '1rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{
                  width: '18px',
                  height: '18px',
                  borderRadius: '50%',
                  backgroundColor: '#2563EB',
                  color: '#FFFFFF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.65rem',
                  fontWeight: 900
                }}>
                  ✓
                </span>
                <span style={{ fontSize: '0.825rem', fontWeight: 800, color: '#1E40AF' }}>
                  LATER &bull; Routine
                </span>
              </div>
              <span style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                backgroundColor: '#3B82F6',
                color: '#FFFFFF',
                fontSize: '0.7rem',
                fontWeight: 900,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                1
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {routineTasks.map((task) => (
                <div
                  key={task.id}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '8px',
                    padding: '0.65rem 0.85rem',
                    border: '1px solid #BFDBFE',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#2563EB'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#BFDBFE'; }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <span style={{ color: '#2563EB', marginTop: '2px', flexShrink: 0 }}>
                      <Building size={13} />
                    </span>
                    <div>
                      <div style={{ fontSize: '0.825rem', fontWeight: 800, color: '#0F172A', lineHeight: 1.25 }}>
                        {task.title}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#64748B', marginTop: '2px' }}>
                        {task.subtext}
                      </div>
                    </div>
                  </div>
                  <ChevronRight size={15} color="#94A3B8" />
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>

      {/* ── 6. CARRY-FORWARD HANDOVER BAR (INLINE COLLAPSIBLE MATCHING PROPOSED UI) ── */}
      <div style={{
        backgroundColor: '#FFFBEB',
        borderRadius: '12px',
        border: '1.5px solid #FDE68A',
        padding: '0.85rem 1.25rem',
        boxShadow: '0 1px 3px rgba(0,0,0,0.02)'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <span style={{ fontSize: '1.25rem' }}>📂</span>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.92rem', fontWeight: 800, color: '#0F172A' }}>
                  Carry-forward handover
                </span>
                <span style={{
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  backgroundColor: '#FEF3C7',
                  color: '#92400E',
                  padding: '2px 8px',
                  borderRadius: '999px',
                  border: '1px solid #FDE68A'
                }}>
                  {handoverAcknowledged ? 'Acknowledged' : `${carryForwardItems.length} items awaiting acknowledgement`}
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              type="button"
              onClick={() => setShowHandoverDrawer(!showHandoverDrawer)}
              style={{
                backgroundColor: '#2563EB',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                padding: '0.5rem 1rem',
                fontSize: '0.8rem',
                fontWeight: 800,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                boxShadow: '0 2px 6px rgba(37, 99, 235, 0.2)'
              }}
            >
              <span>Review handover</span>
              <ChevronRight size={14} />
            </button>

            <button
              type="button"
              onClick={() => setShowHandoverDrawer(!showHandoverDrawer)}
              style={{
                background: 'none',
                border: 'none',
                color: '#64748B',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                padding: '4px'
              }}
            >
              {showHandoverDrawer ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
          </div>
        </div>

        {/* Collapsible Handover Tasks Drawer */}
        {showHandoverDrawer && (
          <div className="animate-fade-in" style={{
            marginTop: '1rem',
            paddingTop: '1rem',
            borderTop: '1px solid #FDE68A',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem'
          }}>
            <div style={{ fontSize: '0.825rem', color: '#78350F', fontWeight: 600 }}>
              The previous shift guard logged incomplete tasks. Review and acknowledge to sign off on responsibility:
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: '0.75rem'
            }}>
              {carryForwardItems.map((item) => (
                <div
                  key={item.id}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '8px',
                    border: '1px solid #CBD5E1',
                    padding: '0.75rem 0.85rem'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.7rem', fontWeight: 800, color: '#2563EB' }}>
                      {item.category} &bull; {item.shift}
                    </span>
                    <span style={{
                      fontSize: '0.68rem',
                      fontWeight: 800,
                      backgroundColor: item.urgency === 'HIGH' ? '#FEE2E2' : '#F1F5F9',
                      color: item.urgency === 'HIGH' ? '#DC2626' : '#475569',
                      padding: '1px 6px',
                      borderRadius: '4px'
                    }}>
                      {item.urgency}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.825rem', fontWeight: 800, color: '#0F172A' }}>
                    {item.title}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '2px' }}>
                    {item.description}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
              <button
                type="button"
                onClick={handleAcknowledgeHandover}
                disabled={handoverAcknowledged}
                style={{
                  backgroundColor: handoverAcknowledged ? '#059669' : '#D97706',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '0.6rem 1.25rem',
                  fontSize: '0.825rem',
                  fontWeight: 800,
                  cursor: handoverAcknowledged ? 'default' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 2px 6px rgba(217, 119, 6, 0.25)'
                }}
              >
                <Check size={16} />
                <span>{handoverAcknowledged ? '✓ Handover Acknowledged' : 'Acknowledge & Sign Handover'}</span>
              </button>
            </div>
          </div>
        )}
      </div>

    </div>
  );
};
