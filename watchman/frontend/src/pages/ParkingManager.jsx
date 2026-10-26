import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Car,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Bike,
  Plus,
  RefreshCw,
  LogOut,
  ShieldAlert,
  Search,
  User,
  Phone,
  LayoutGrid,
  X,
  Shield,
  Volume2,
  Clock,
  ArrowRight
} from 'lucide-react';

export const ParkingManager = () => {
  const { language } = useAuth();
  const [slots, setSlots] = useState([]);
  const [summary, setSummary] = useState({ total_slots: 10, occupied_slots: 5, available_slots: 5, unauthorized_count: 1 });
  const [loading, setLoading] = useState(false);
  const [selectedZone, setSelectedZone] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [reviewAlertSlot, setReviewAlertSlot] = useState(null);
  const [lastUpdated, setLastUpdated] = useState('11:51 PM');
  const [sirenPlaying, setSirenPlaying] = useState(false);

  // Modal Form for Occupying
  const [vehicleNumber, setVehicleNumber] = useState('');
  const [driverName, setDriverName] = useState('');
  const [phone, setPhone] = useState('');
  const [isUnauthorized, setIsUnauthorized] = useState(false);

  const fetchParkingData = async () => {
    setLoading(true);
    try {
      const [slotsData, sumData] = await Promise.all([
        api.getParkingSlots(),
        api.getParkingSummary()
      ]);
      if (Array.isArray(slotsData) && slotsData.length > 0) {
        setSlots(slotsData);
      }
      if (sumData) {
        setSummary(sumData);
      }
      setLastUpdated(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    } catch {
      // Keep existing slots or default
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchParkingData();
  }, []);

  const handleOccupy = async (e) => {
    e.preventDefault();
    if (!selectedSlot || !vehicleNumber.trim()) return;

    try {
      await api.occupyParkingSlot(selectedSlot.id, {
        vehicle_number: vehicleNumber.toUpperCase().replace(/\s/g, ''),
        driver_name: driverName || 'Campus Visitor',
        phone_number: phone || '9876543210',
        is_unauthorized: isUnauthorized
      });
    } catch {
      // Local optimistic update
      setSlots(prev => prev.map(s => {
        if (s.id === selectedSlot.id) {
          return {
            ...s,
            is_occupied: true,
            vehicle_number: vehicleNumber.toUpperCase().replace(/\s/g, ''),
            driver_name: driverName || 'Campus Visitor',
            phone_number: phone || '9876543210',
            is_unauthorized: isUnauthorized
          };
        }
        return s;
      }));
    }

    setSelectedSlot(null);
    setVehicleNumber('');
    setDriverName('');
    setPhone('');
    setIsUnauthorized(false);
    fetchParkingData();
  };

  const handleVacate = async (slotId) => {
    try {
      await api.vacateParkingSlot(slotId);
    } catch {
      // Local optimistic update
      setSlots(prev => prev.map(s => {
        if (s.id === slotId) {
          return {
            ...s,
            is_occupied: false,
            vehicle_number: null,
            driver_name: null,
            phone_number: null,
            is_unauthorized: false
          };
        }
        return s;
      }));
    }
    fetchParkingData();
  };

  // Play warning alert sound
  const handleTriggerSiren = (slot) => {
    setSirenPlaying(true);
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(800, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(400, audioCtx.currentTime + 0.3);
      osc.frequency.exponentialRampToValueAtTime(800, audioCtx.currentTime + 0.6);
      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 1.2);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 1.2);
    } catch {}

    if ('speechSynthesis' in window) {
      const msg = new SpeechSynthesisUtterance(
        language === 'ta'
          ? `எச்சரிக்கை! ஸ்லாட் ${slot.slot_code}-ல் அனுமதியில்லா வாகனம் ${slot.vehicle_number} நிறுத்தப்பட்டுள்ளது.`
          : `Alert! Unauthorized vehicle ${slot.vehicle_number} detected in slot ${slot.slot_code}.`
      );
      msg.lang = language === 'ta' ? 'ta-IN' : 'en-US';
      window.speechSynthesis.speak(msg);
    }

    setTimeout(() => setSirenPlaying(false), 2000);
  };

  // Filter slots by Zone & Search Query
  const filteredSlots = slots.filter((s) => {
    // 1. Zone filter
    const matchesZone =
      selectedZone === 'ALL' ||
      s.zone === selectedZone ||
      (selectedZone === 'STAFF' && s.zone === 'STAFF') ||
      (selectedZone === 'ZONE_A' && (s.zone === 'ZONE_A' || s.slot_type === 'EV_CHARGING')) ||
      (selectedZone === 'ZONE_B' && (s.zone === 'ZONE_B' || s.slot_type === 'TWO_WHEELER'));

    // 2. Search query filter
    const q = searchQuery.trim().toLowerCase();
    const matchesSearch =
      !q ||
      s.slot_code.toLowerCase().includes(q) ||
      (s.vehicle_number && s.vehicle_number.toLowerCase().includes(q)) ||
      (s.driver_name && s.driver_name.toLowerCase().includes(q));

    return matchesZone && matchesSearch;
  });

  const renderSlotIcon = (slot) => {
    if (slot.slot_type === 'EV_CHARGING') {
      return (
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          backgroundColor: '#F3E8FF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#7E22CE',
          flexShrink: 0
        }}>
          <Zap size={16} strokeWidth={2.4} />
        </div>
      );
    }

    if (slot.slot_type === 'TWO_WHEELER') {
      return (
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          backgroundColor: '#E0F2FE',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#0284C7',
          flexShrink: 0
        }}>
          <Bike size={16} strokeWidth={2.4} />
        </div>
      );
    }

    if (slot.is_unauthorized) {
      return (
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          backgroundColor: '#FEE2E2',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#DC2626',
          flexShrink: 0
        }}>
          <Car size={16} strokeWidth={2.4} />
        </div>
      );
    }

    if (slot.is_occupied) {
      return (
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          backgroundColor: '#EFF6FF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#2563EB',
          flexShrink: 0
        }}>
          <Car size={16} strokeWidth={2.4} />
        </div>
      );
    }

    // Available 4-wheeler
    return (
      <div style={{
        width: '32px',
        height: '32px',
        borderRadius: '50%',
        backgroundColor: '#DCFCE7',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#16A34A',
        flexShrink: 0
      }}>
        <Car size={16} strokeWidth={2.4} />
      </div>
    );
  };

  return (
    <div className="animate-fade-in" style={{ padding: '0.25rem 0', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* ── Top Header ────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '10px',
            backgroundColor: '#E0F2FE',
            border: '1px solid #BAE6FD',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#0284C7'
          }}>
            <Car size={24} strokeWidth={2.4} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
              {language === 'ta' ? 'ஸ்மார்ட் பார்க்கிங் மேலாண்மை' : 'Smart Campus Parking Management'}
            </h1>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Live Last updated badge with pulsing green indicator */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.8rem',
            color: '#64748B',
            fontWeight: 600,
            backgroundColor: '#F8FAFC',
            padding: '0.35rem 0.75rem',
            borderRadius: '8px',
            border: '1px solid #E2E8F0'
          }}>
            <span>{language === 'ta' ? 'கடைசியாக புதுப்பிக்கப்பட்டது:' : 'Last updated:'}</span>
            <strong style={{ color: '#0F172A' }}>{lastUpdated}</strong>
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: '#16A34A',
              display: 'inline-block',
              boxShadow: '0 0 6px #16A34A'
            }} />
          </div>

          <button
            onClick={fetchParkingData}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '0.45rem 0.95rem',
              borderRadius: '8px',
              backgroundColor: '#FFFFFF',
              color: '#2563EB',
              border: '1.5px solid #BFDBFE',
              fontWeight: 700,
              fontSize: '0.825rem',
              cursor: 'pointer',
              transition: 'all 0.15s ease'
            }}
          >
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            <span>{language === 'ta' ? 'வரைபடம் புதுப்பி' : 'Refresh Map'}</span>
          </button>
        </div>
      </div>

      {/* ── Summary Counters (4 KPI Cards Matching Proposed UI) ── */}
      <div className="responsive-kpi-4">
        {/* Card 1: Total Capacity */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1.5px solid #E2E8F0',
          padding: '1.1rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '10px',
            backgroundColor: '#EFF6FF',
            border: '1.5px solid #BFDBFE',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#2563EB',
            flexShrink: 0
          }}>
            <LayoutGrid size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748B' }}>
              {language === 'ta' ? 'மொத்த கொள்ளளவு' : 'Total Capacity'}
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#0F172A', lineHeight: 1.15 }}>
              {summary.total_slots || slots.length || 10}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94A3B8', marginTop: '2px' }}>
              {language === 'ta' ? 'பார்க்கிங் இடங்கள்' : 'Parking Slots'}
            </div>
          </div>
        </div>

        {/* Card 2: Available Slots */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1.5px solid #E2E8F0',
          padding: '1.1rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '10px',
            backgroundColor: '#DCFCE7',
            border: '1.5px solid #86EFAC',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#16A34A',
            flexShrink: 0
          }}>
            <CheckCircle2 size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#059669' }}>
              {language === 'ta' ? 'காலியிடங்கள்' : 'Available Slots'}
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#059669', lineHeight: 1.15 }}>
              {slots.length > 0 ? slots.filter((s) => !s.is_occupied).length : (summary.available_slots || 5)}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94A3B8', marginTop: '2px' }}>
              {language === 'ta' ? 'இடங்கள் தயார்' : 'Slots Available'}
            </div>
          </div>
        </div>

        {/* Card 3: Occupied Slots */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1.5px solid #E2E8F0',
          padding: '1.1rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '10px',
            backgroundColor: '#EFF6FF',
            border: '1.5px solid #BFDBFE',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#2563EB',
            flexShrink: 0
          }}>
            <Car size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#2563EB' }}>
              {language === 'ta' ? 'நிரம்பிய இடங்கள்' : 'Occupied Slots'}
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#1D4ED8', lineHeight: 1.15 }}>
              {slots.length > 0 ? slots.filter((s) => s.is_occupied).length : (summary.occupied_slots || 5)}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94A3B8', marginTop: '2px' }}>
              {language === 'ta' ? 'வாகனங்கள் நிற்கின்றன' : 'Slots Occupied'}
            </div>
          </div>
        </div>

        {/* Card 4: Unauthorized Parking */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1.5px solid #E2E8F0',
          padding: '1.1rem 1.25rem',
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
        }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '10px',
            backgroundColor: '#FEE2E2',
            border: '1.5px solid #FECACA',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#DC2626',
            flexShrink: 0
          }}>
            <AlertTriangle size={22} />
          </div>
          <div>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#DC2626' }}>
              {language === 'ta' ? 'அனுமதியில்லா பார்க்கிங்' : 'Unauthorized Parking'}
            </div>
            <div style={{ fontSize: '1.75rem', fontWeight: 900, color: '#DC2626', lineHeight: 1.15 }}>
              {slots.length > 0 ? slots.filter((s) => s.is_unauthorized).length : (summary.unauthorized_count || 1)}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#94A3B8', marginTop: '2px' }}>
              {language === 'ta' ? 'கவனிக்கப்பட வேண்டும்' : 'Needs Attention'}
            </div>
          </div>
        </div>
      </div>

      {/* ── Search Bar & Zone Filter Tabs ──────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem'
      }}>
        {/* Search Input on Left - Prominent, User-Friendly & Highly Visible */}
        <div style={{
          position: 'relative',
          flex: '1 1 340px',
          maxWidth: '460px',
          minWidth: '280px'
        }}>
          <Search
            size={18}
            color="#2563EB"
            style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              pointerEvents: 'none'
            }}
          />
          <input
            type="text"
            style={{
              width: '100%',
              padding: '0.65rem 2.4rem 0.65rem 2.5rem',
              fontSize: '0.88rem',
              fontWeight: 500,
              color: '#0F172A',
              borderRadius: '10px',
              border: '1.5px solid #94A3B8',
              backgroundColor: '#FFFFFF',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.04)',
              outline: 'none',
              transition: 'border-color 0.15s ease, box-shadow 0.15s ease'
            }}
            onFocus={(e) => {
              e.target.style.borderColor = '#2563EB';
              e.target.style.boxShadow = '0 0 0 3px rgba(37, 99, 235, 0.14)';
            }}
            onBlur={(e) => {
              e.target.style.borderColor = '#94A3B8';
              e.target.style.boxShadow = '0 2px 6px rgba(0, 0, 0, 0.04)';
            }}
            placeholder={language === 'ta' ? 'ஸ்லாட் எண் (எ.கா: A-01) அல்லது வண்டி எண் தேடுக...' : 'Search by Slot ID (e.g. A-01), Vehicle #, or Driver...'}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <div style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{
                fontSize: '0.72rem',
                fontWeight: 800,
                color: '#2563EB',
                backgroundColor: '#EFF6FF',
                padding: '2px 7px',
                borderRadius: '999px',
                border: '1px solid #BFDBFE'
              }}>
                {filteredSlots.length}
              </span>
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                title="Clear search"
                style={{
                  width: '20px',
                  height: '20px',
                  borderRadius: '50%',
                  background: '#F1F5F9',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#64748B',
                  cursor: 'pointer',
                  padding: 0
                }}
              >
                <X size={13} />
              </button>
            </div>
          )}
        </div>

        {/* Filter Pills on Right */}
        <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap' }}>
          {[
            { id: 'ALL', labelTa: 'அனைத்து இடங்கள்', labelEn: 'All Bays', count: slots.length || 10 },
            { id: 'STAFF', labelTa: 'ஊழியர் ஒதுக்கப்பட்டவை', labelEn: 'Staff Reserved' },
            { id: 'ZONE_A', labelTa: 'மண்டலம் A (பார்வையாளர் & EV)', labelEn: 'Zone A (Visitor & E-V)' },
            { id: 'ZONE_B', labelTa: 'மண்டலம் B (இருசக்கர வாகனம்)', labelEn: 'Zone B (Two-Wheelers)' }
          ].map((z) => {
            const isSelected = selectedZone === z.id;
            return (
              <button
                key={z.id}
                onClick={() => setSelectedZone(z.id)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '0.45rem 0.85rem',
                  borderRadius: '999px',
                  border: isSelected ? '1.5px solid #2563EB' : '1px solid #CBD5E1',
                  backgroundColor: isSelected ? '#2563EB' : '#FFFFFF',
                  color: isSelected ? '#FFFFFF' : '#475569',
                  fontWeight: 700,
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  transition: 'all 0.15s ease'
                }}
              >
                <span>{language === 'ta' ? z.labelTa : z.labelEn}</span>
                {z.count !== undefined && (
                  <span style={{
                    backgroundColor: isSelected ? 'rgba(255,255,255,0.25)' : '#F1F5F9',
                    color: isSelected ? '#FFFFFF' : '#475569',
                    fontSize: '0.7rem',
                    fontWeight: 800,
                    padding: '0.1rem 0.45rem',
                    borderRadius: '999px'
                  }}>
                    {z.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── 4-Column Parking Slots Grid (Matching Proposed UI) ─── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 250px), 1fr))',
        gap: '1rem'
      }}>
        {filteredSlots.map((slot) => {
          const isOccupied = slot.is_occupied;
          const isUnauth = slot.is_unauthorized;

          return (
            <div
              key={slot.id}
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '14px',
                border: isUnauth
                  ? '1.5px solid #FECACA'
                  : isOccupied
                  ? '1.5px solid #E2E8F0'
                  : '1.5px solid #86EFAC',
                padding: '1.15rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '0.85rem',
                boxShadow: isUnauth
                  ? '0 2px 10px rgba(220, 38, 38, 0.08)'
                  : '0 1px 3px rgba(0,0,0,0.03)',
                transition: 'all 0.15s ease'
              }}
            >
              <div>
                {/* Header Row: Vehicle Icon + Slot ID + Status Badges */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '0.5rem'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {renderSlotIcon(slot)}
                    <span style={{
                      fontSize: '1.1rem',
                      fontWeight: 900,
                      color: isUnauth ? '#B91C1C' : '#0F172A'
                    }}>
                      {slot.slot_code}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    {/* EV Badge */}
                    {slot.slot_type === 'EV_CHARGING' && (
                      <span style={{
                        padding: '0.15rem 0.5rem',
                        backgroundColor: '#F3E8FF',
                        color: '#7E22CE',
                        borderRadius: '6px',
                        fontSize: '0.7rem',
                        fontWeight: 800,
                        border: '1px solid #D8B4FE'
                      }}>
                        ⚡ EV
                      </span>
                    )}

                    {/* 2W Badge */}
                    {slot.slot_type === 'TWO_WHEELER' && (
                      <span style={{
                        padding: '0.15rem 0.5rem',
                        backgroundColor: '#E0F2FE',
                        color: '#0369A1',
                        borderRadius: '6px',
                        fontSize: '0.7rem',
                        fontWeight: 800,
                        border: '1px solid #BAE6FD'
                      }}>
                        2W
                      </span>
                    )}

                    {/* Status Pill */}
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      padding: '0.15rem 0.55rem',
                      borderRadius: '999px',
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      backgroundColor: isOccupied
                        ? (isUnauth ? '#FEE2E2' : '#EFF6FF')
                        : '#DCFCE7',
                      color: isOccupied
                        ? (isUnauth ? '#DC2626' : '#1D4ED8')
                        : '#15803D',
                      border: `1px solid ${
                        isOccupied
                          ? (isUnauth ? '#FECACA' : '#BFDBFE')
                          : '#86EFAC'
                      }`
                    }}>
                      <span style={{
                        width: '5px',
                        height: '5px',
                        borderRadius: '50%',
                        backgroundColor: isOccupied
                          ? (isUnauth ? '#DC2626' : '#2563EB')
                          : '#16A34A'
                      }} />
                      {isOccupied
                        ? (isUnauth ? 'Unauthorized' : 'Occupied')
                        : 'Available'}
                    </span>
                  </div>
                </div>

                {/* Card Body Details */}
                {isOccupied ? (
                  <div>
                    {/* License Plate Number */}
                    <div style={{
                      fontSize: '1.15rem',
                      fontWeight: 900,
                      color: '#0F172A',
                      fontFamily: 'monospace',
                      letterSpacing: '0.04em',
                      margin: '0.2rem 0'
                    }}>
                      {slot.vehicle_number}
                    </div>

                    {/* Driver / Owner Name */}
                    <div style={{ fontSize: '0.8rem', color: '#475569', fontWeight: 600, margin: '2px 0' }}>
                      {slot.driver_name || (isUnauth ? 'Unknown Vehicle' : 'Visitor')}
                    </div>

                    {/* Contact or Warning Details */}
                    {isUnauth ? (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.75rem',
                        color: '#DC2626',
                        fontWeight: 700,
                        marginTop: '4px'
                      }}>
                        <span>⚠️</span>
                        <span>{language === 'ta' ? 'வாகன விவரங்களை சரிபார்க்கவும்' : 'Verify vehicle details'}</span>
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '2px' }}>
                        Contact: {slot.phone_number || '9876543210'}
                      </div>
                    )}
                  </div>
                ) : (
                  <div>
                    {slot.slot_type === 'EV_CHARGING' && (
                      <div style={{ fontSize: '0.85rem', fontWeight: 800, color: '#0F172A', marginBottom: '2px' }}>
                        EV Charging Bay
                      </div>
                    )}
                    <div style={{ fontSize: '0.78rem', color: '#64748B', margin: '4px 0 8px 0' }}>
                      {language === 'ta'
                        ? 'காலி இடம் புதிய வாகன வருகைக்கு தயாராக உள்ளது.'
                        : 'Empty slot ready for ingress assignment.'}
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom Action Button */}
              {isOccupied ? (
                isUnauth ? (
                  /* PROMINENT RED BUTTON FOR UNAUTHORIZED SLOTS (REVIEW ALERT) */
                  <button
                    type="button"
                    onClick={() => setReviewAlertSlot(slot)}
                    style={{
                      width: '100%',
                      padding: '0.55rem',
                      borderRadius: '8px',
                      backgroundColor: '#DC2626',
                      color: '#FFFFFF',
                      border: 'none',
                      fontWeight: 800,
                      fontSize: '0.825rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      boxShadow: '0 2px 8px rgba(220, 38, 38, 0.25)',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <ShieldAlert size={15} />
                    <span>{language === 'ta' ? 'எச்சரிக்கையை பரிசீலி' : 'Review Alert'}</span>
                  </button>
                ) : (
                  /* REGULAR VACATE BUTTON */
                  <button
                    type="button"
                    onClick={() => handleVacate(slot.id)}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      borderRadius: '8px',
                      backgroundColor: '#FFFFFF',
                      color: '#2563EB',
                      border: '1.5px solid #E2E8F0',
                      fontWeight: 800,
                      fontSize: '0.8rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '5px',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <LogOut size={14} />
                    <span>{language === 'ta' ? 'காலி செய்' : 'Mark Vacated'}</span>
                  </button>
                )
              ) : (
                /* ASSIGN VEHICLE BUTTON */
                <button
                  type="button"
                  onClick={() => setSelectedSlot(slot)}
                  style={{
                    width: '100%',
                    padding: '0.55rem',
                    borderRadius: '8px',
                    backgroundColor: '#2563EB',
                    color: '#FFFFFF',
                    border: 'none',
                    fontWeight: 800,
                    fontSize: '0.825rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '5px',
                    boxShadow: '0 2px 6px rgba(37, 99, 235, 0.25)',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <Plus size={15} />
                  <span>{language === 'ta' ? 'வாகனத்தை ஒதுக்கு' : 'Assign Vehicle'}</span>
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* ── MODAL 1: REVIEW UNAUTHORIZED PARKING ALERT ─────────── */}
      {reviewAlertSlot && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.65)',
          backdropFilter: 'blur(5px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '1rem'
        }}>
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '16px',
            width: '100%',
            maxWidth: '520px',
            boxShadow: '0 20px 40px rgba(0, 0, 0, 0.25)',
            border: '2px solid #FECACA',
            overflow: 'hidden',
            animation: 'fadeIn 0.2s ease-out'
          }}>
            {/* Modal Header */}
            <div style={{
              backgroundColor: '#DC2626',
              color: '#FFFFFF',
              padding: '1.25rem 1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(255, 255, 255, 0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#FFFFFF'
                }}>
                  <ShieldAlert size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, color: '#FFFFFF' }}>
                    {language === 'ta'
                      ? `அனுமதியில்லா பார்க்கிங் எச்சரிக்கை - ${reviewAlertSlot.slot_code}`
                      : `Unauthorized Parking Alert - Slot ${reviewAlertSlot.slot_code}`}
                  </h3>
                  <p style={{ fontSize: '0.75rem', color: '#FEE2E2', margin: 0 }}>
                    {language === 'ta'
                      ? 'அனுமதியில்லாத வாகனம் கண்டறியப்பட்டது. பாதுகாப்பு நடவடிக்கை எடுக்கவும்.'
                      : 'Unregistered vehicle occupying designated parking bay.'}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setReviewAlertSlot(null)}
                style={{
                  backgroundColor: 'transparent',
                  border: 'none',
                  color: '#FFFFFF',
                  cursor: 'pointer',
                  padding: '0.35rem'
                }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* License Plate Display */}
              <div style={{
                backgroundColor: '#FEF2F2',
                border: '2px solid #FCA5A5',
                borderRadius: '10px',
                padding: '0.85rem 1rem',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '0.72rem', color: '#B91C1C', fontWeight: 700, textTransform: 'uppercase' }}>
                  {language === 'ta' ? 'அனுமதியில்லாத வாகன எண்' : 'Detected Unauthorized Vehicle Plate'}
                </div>
                <div style={{
                  fontFamily: 'monospace',
                  fontWeight: 900,
                  fontSize: '1.6rem',
                  color: '#991B1B',
                  letterSpacing: '0.08em',
                  marginTop: '2px'
                }}>
                  {reviewAlertSlot.vehicle_number}
                </div>
                <div style={{ fontSize: '0.8rem', color: '#7F1D1D', marginTop: '2px' }}>
                  Slot: <strong>{reviewAlertSlot.slot_code}</strong> ({reviewAlertSlot.zone}) • Driver: <strong>{reviewAlertSlot.driver_name || 'Unknown'}</strong>
                </div>
              </div>

              {/* Alert Details Box */}
              <div style={{
                backgroundColor: '#F8FAFC',
                borderRadius: '8px',
                padding: '0.85rem',
                border: '1px solid #E2E8F0',
                fontSize: '0.825rem',
                color: '#475569',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.35rem'
              }}>
                <div>• <strong>Violation:</strong> Parking in faculty/restricted zone without valid permit.</div>
                <div>• <strong>Camera Verification:</strong> Auto-flagged by Gate Ingress ANPR Scanner.</div>
                <div>• <strong>Status:</strong> Immediate watchman verification required.</div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <button
                  type="button"
                  onClick={() => handleTriggerSiren(reviewAlertSlot)}
                  style={{
                    padding: '0.7rem',
                    borderRadius: '8px',
                    backgroundColor: sirenPlaying ? '#B91C1C' : '#DC2626',
                    color: '#FFFFFF',
                    border: 'none',
                    fontWeight: 800,
                    fontSize: '0.875rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    boxShadow: '0 4px 12px rgba(220, 38, 38, 0.3)'
                  }}
                >
                  <Volume2 size={18} />
                  <span>{language === 'ta' ? '🚨 எச்சரிக்கை அலாரம் ஒலி எழுப்பு (Siren)' : '🚨 Sound Guard Alert Siren'}</span>
                </button>

                <div style={{ display: 'flex', gap: '0.65rem' }}>
                  <button
                    type="button"
                    onClick={() => {
                      handleVacate(reviewAlertSlot.id);
                      setReviewAlertSlot(null);
                    }}
                    style={{
                      flex: 1,
                      padding: '0.65rem',
                      borderRadius: '8px',
                      backgroundColor: '#FFFFFF',
                      color: '#16A34A',
                      border: '1.5px solid #86EFAC',
                      fontWeight: 800,
                      fontSize: '0.825rem',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '5px'
                    }}
                  >
                    <CheckCircle2 size={16} />
                    <span>{language === 'ta' ? 'அகற்றப்பட்டது (Vacated)' : 'Clear / Mark Vacated'}</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setReviewAlertSlot(null)}
                    style={{
                      flex: 1,
                      padding: '0.65rem',
                      borderRadius: '8px',
                      backgroundColor: '#FFFFFF',
                      color: '#475569',
                      border: '1.5px solid #CBD5E1',
                      fontWeight: 700,
                      fontSize: '0.825rem',
                      cursor: 'pointer'
                    }}
                  >
                    {language === 'ta' ? 'மூடு' : 'Close'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL 2: ASSIGN PARKING SLOT ──────────────────────── */}
      {selectedSlot && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(15, 23, 42, 0.65)',
          backdropFilter: 'blur(5px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '1rem'
        }}>
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '16px',
            width: '100%',
            maxWidth: '480px',
            boxShadow: '0 20px 40px rgba(0, 0, 0, 0.25)',
            border: '2px solid #E2E8F0',
            overflow: 'hidden',
            animation: 'fadeIn 0.2s ease-out'
          }}>
            {/* Modal Header */}
            <div style={{
              backgroundColor: '#0F172A',
              color: '#FFFFFF',
              padding: '1.25rem 1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '10px',
                  backgroundColor: '#1E293B',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#38BDF8'
                }}>
                  <Car size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 800, margin: 0, color: '#FFFFFF' }}>
                    {language === 'ta' ? 'வாகன இட ஒதுக்கீடு' : 'Assign Parking Slot'}
                  </h3>
                  <p style={{ fontSize: '0.75rem', color: '#94A3B8', margin: 0 }}>
                    Slot: <strong>{selectedSlot.slot_code}</strong> ({selectedSlot.zone})
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setSelectedSlot(null)}
                style={{
                  backgroundColor: 'transparent',
                  border: 'none',
                  color: '#94A3B8',
                  cursor: 'pointer',
                  padding: '0.35rem'
                }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleOccupy} style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 800, color: '#334155', marginBottom: '0.35rem' }}>
                  {language === 'ta' ? '1. வாகன பதிவு எண் *' : '1. Vehicle Registration Plate *'}
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g., TN09CA1234 / TN 65 BT 2946"
                  value={vehicleNumber}
                  onChange={(e) => setVehicleNumber(e.target.value.toUpperCase())}
                  style={{
                    width: '100%',
                    padding: '0.65rem',
                    borderRadius: '8px',
                    border: '1.5px solid #CBD5E1',
                    fontFamily: 'monospace',
                    fontWeight: 900,
                    fontSize: '1.1rem',
                    letterSpacing: '0.04em',
                    backgroundColor: '#FEF08A',
                    color: '#000000',
                    border: '2px solid #000000'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 800, color: '#334155', marginBottom: '0.35rem' }}>
                  {language === 'ta' ? '2. ஓட்டுநர் / உரிமையாளர் பெயர்' : '2. Driver / Owner Name'}
                </label>
                <input
                  type="text"
                  placeholder="e.g., Dr. Sundaram / Guest Lecturer"
                  value={driverName}
                  onChange={(e) => setDriverName(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.65rem',
                    borderRadius: '8px',
                    border: '1.5px solid #CBD5E1',
                    fontSize: '0.85rem',
                    fontWeight: 600
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 800, color: '#334155', marginBottom: '0.35rem' }}>
                  {language === 'ta' ? '3. தொலைபேசி எண்' : '3. Contact Phone Number'}
                </label>
                <input
                  type="tel"
                  placeholder="e.g., 9876543210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.65rem',
                    borderRadius: '8px',
                    border: '1.5px solid #CBD5E1',
                    fontSize: '0.85rem'
                  }}
                />
              </div>

              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '0.65rem',
                borderRadius: '8px',
                backgroundColor: isUnauthorized ? '#FEF2F2' : '#F8FAFC',
                border: isUnauthorized ? '1px solid #FCA5A5' : '1px solid #E2E8F0'
              }}>
                <input
                  type="checkbox"
                  id="unauthFlag"
                  checked={isUnauthorized}
                  onChange={(e) => setIsUnauthorized(e.target.checked)}
                  style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                />
                <label htmlFor="unauthFlag" style={{ fontSize: '0.825rem', color: isUnauthorized ? '#DC2626' : '#475569', fontWeight: 700, cursor: 'pointer' }}>
                  {language === 'ta' ? 'அனுமதியில்லாத பார்க்கிங் என கொடியிடு' : 'Flag as Unauthorized / Non-Permitted Vehicle'}
                </label>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem', borderTop: '1px solid #F1F5F9', paddingTop: '1rem' }}>
                <button
                  type="button"
                  onClick={() => setSelectedSlot(null)}
                  style={{
                    flex: 1,
                    padding: '0.65rem',
                    borderRadius: '8px',
                    border: '1px solid #CBD5E1',
                    backgroundColor: '#FFFFFF',
                    color: '#475569',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  {language === 'ta' ? 'ரத்து' : 'Cancel'}
                </button>

                <button
                  type="submit"
                  style={{
                    flex: 2,
                    padding: '0.65rem',
                    borderRadius: '8px',
                    backgroundColor: '#16A34A',
                    color: '#FFFFFF',
                    border: 'none',
                    fontWeight: 800,
                    fontSize: '0.9rem',
                    cursor: 'pointer',
                    boxShadow: '0 4px 12px rgba(22, 163, 74, 0.3)'
                  }}
                >
                  {language === 'ta' ? '✓ பார்க்கிங்கை உறுதிசெய்' : '✓ Confirm & Assign Slot'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
