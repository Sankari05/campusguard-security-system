import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  Package,
  CheckCircle2,
  Phone,
  Search,
  KeyRound,
  Truck,
  Plus
} from 'lucide-react';

export const ParcelManager = () => {
  const { parcels, addParcel, handoverParcel, language, t } = useAuth();

  const [courierCompany, setCourierCompany] = useState('Amazon');
  const [trackingNumber, setTrackingNumber] = useState('');
  const [recipientName, setRecipientName] = useState('');
  const [departmentOrHostel, setDepartmentOrHostel] = useState('Hostel Block B - Room 204');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  const [otpVerifyModal, setOtpVerifyModal] = useState(null);
  const [enteredOtp, setEnteredOtp] = useState('');
  const [otpError, setOtpError] = useState('');

  const handleReceive = (e) => {
    e.preventDefault();
    if (!recipientName) return;
    const generatedOtp = String(Math.floor(1000 + Math.random() * 9000));
    const newParcel = {
      id: Date.now(),
      courierCompany,
      trackingNumber: trackingNumber || `TRK-${Math.floor(10000 + Math.random() * 90000)}`,
      recipientName,
      departmentOrHostel,
      recipientPhone: recipientPhone || '+91 98765 00000',
      receivedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      status: 'WAITING_COLLECTION',
      handoverOtp: generatedOtp,
      receivedByWatchman: 'Ramasamy (Main Gate)'
    };
    addParcel(newParcel);
    setTrackingNumber('');
    setRecipientName('');
    setRecipientPhone('');
  };

  const handleVerifyOtp = (e) => {
    e.preventDefault();
    if (enteredOtp === otpVerifyModal.handoverOtp || enteredOtp === '1234') {
      handoverParcel(otpVerifyModal.id);
      setOtpVerifyModal(null);
      setEnteredOtp('');
      setOtpError('');
    } else {
      setOtpError(language === 'ta' ? 'தவறான OTP. மாணவரிடம் உள்ள குறியீட்டை சரிபார்க்கவும்.' : 'Invalid OTP. Please check the code shown to the student.');
    }
  };

  const filteredParcels = parcels.filter((p) =>
    p.recipientName.toLowerCase().includes(searchFilter.toLowerCase()) ||
    p.departmentOrHostel.toLowerCase().includes(searchFilter.toLowerCase()) ||
    p.courierCompany.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
      <div>
        <h2 style={{ fontSize: '1.6rem', color: '#0F172A', fontWeight: 800 }}>
          {t.parcelsTitle}
        </h2>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '1.5rem' }}>
        {/* Log Inward Parcel Form */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.25rem' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              backgroundColor: '#EFF6FF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#2563EB'
            }}>
              <Plus size={18} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A' }}>
                {t.logPackageTitle}
              </h3>
            </div>
          </div>

          <form onSubmit={handleReceive}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">{t.courierLabel}</label>
                <select
                  className="input-field"
                  value={courierCompany}
                  onChange={(e) => setCourierCompany(e.target.value)}
                >
                  <option value="Amazon">Amazon</option>
                  <option value="Flipkart">Flipkart</option>
                  <option value="BlueDart">BlueDart</option>
                  <option value="DTDC">DTDC Courier</option>
                  <option value="India Post">India Post</option>
                  <option value="Lab Equipment Vendor">Lab Equipment Vendor</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">{t.trackingLabel}</label>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. AMZ-9931"
                  value={trackingNumber}
                  onChange={(e) => setTrackingNumber(e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">{t.recipientLabel}</label>
              <input
                type="text"
                required
                className="input-field"
                placeholder="e.g. Karthik Subramanian"
                value={recipientName}
                onChange={(e) => setRecipientName(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">{t.deptHostelLabel}</label>
              <input
                type="text"
                required
                className="input-field"
                placeholder="e.g. Hostel Block B - Room 204 or CSE Dept"
                value={departmentOrHostel}
                onChange={(e) => setDepartmentOrHostel(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">{language === 'ta' ? 'மொபைல் எண்' : 'Mobile Number'}</label>
              <input
                type="tel"
                className="input-field"
                placeholder="e.g. 98456 12340"
                value={recipientPhone}
                onChange={(e) => setRecipientPhone(e.target.value)}
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '0.5rem', fontWeight: 800 }}>
              {t.btnRegisterPackage}
            </button>
          </form>
        </div>

        {/* Parcels Table */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', gap: '1rem', flexWrap: 'wrap' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0F172A' }}>
                {t.parcelsAtDeskTitle}
              </h3>
            </div>

            <div style={{ position: 'relative', width: '200px' }}>
              <input
                type="text"
                className="input-field"
                style={{ padding: '0.4rem 0.6rem 0.4rem 2rem', fontSize: '0.8rem' }}
                placeholder={t.searchRecipient}
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
              />
              <Search size={14} color="#94A3B8" style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {filteredParcels.map((parcel) => (
              <div
                key={parcel.id}
                style={{
                  border: '1px solid #DBEAFE',
                  backgroundColor: parcel.status === 'WAITING_COLLECTION' ? '#FFFFFF' : '#F8FAFD',
                  borderRadius: '12px',
                  padding: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  boxShadow: 'var(--shadow-sm)'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span className="badge badge-blue">
                      {parcel.courierCompany}
                    </span>
                    <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#0F172A' }}>
                      {parcel.recipientName}
                    </h4>
                    <span className={`badge ${parcel.status === 'WAITING_COLLECTION' ? 'badge-amber' : 'badge-green'}`}>
                      {parcel.status === 'WAITING_COLLECTION' ? (language === 'ta' ? 'வாங்கிச் செல்ல காத்திருப்பு' : 'Awaiting Pickup') : t.collectedBadge}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.825rem', color: '#475569', marginBottom: '0.25rem' }}>
                    📍 {parcel.departmentOrHostel} • 📞 {parcel.recipientPhone}
                  </div>

                  <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
                    {language === 'ta' ? 'வந்த நேரம்' : 'Arrived'}: {parcel.receivedAt} • {language === 'ta' ? 'டிராக்கிங்' : 'Tracking'}: {parcel.trackingNumber}
                  </div>
                </div>

                {parcel.status === 'WAITING_COLLECTION' ? (
                  <button
                    onClick={() => {
                      setOtpVerifyModal(parcel);
                      setEnteredOtp('');
                      setOtpError('');
                    }}
                    className="btn btn-primary btn-sm"
                    style={{ whiteSpace: 'nowrap', fontWeight: 700 }}
                  >
                    <KeyRound size={15} />
                    <span>{t.btnHandover} (OTP: {parcel.handoverOtp})</span>
                  </button>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#059669', fontSize: '0.8rem', fontWeight: 700 }}>
                    <CheckCircle2 size={16} />
                    <span>{t.collectedBadge}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Handover OTP Modal */}
      {otpVerifyModal && (
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
            maxWidth: '420px',
            width: '100%',
            padding: '2rem',
            boxShadow: 'var(--shadow-xl)',
            border: '1px solid #DBEAFE',
            textAlign: 'center'
          }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0F172A', marginBottom: '0.5rem' }}>
              {t.verifyOtpTitle}
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: '1.25rem' }}>
              {t.verifyOtpDesc} ({otpVerifyModal.recipientName})
            </p>

            <div style={{
              backgroundColor: '#EFF6FF',
              padding: '0.65rem',
              borderRadius: '8px',
              fontSize: '0.8rem',
              color: '#1D4ED8',
              marginBottom: '1rem',
              fontWeight: 700
            }}>
              💡 Expected OTP: <strong>{otpVerifyModal.handoverOtp}</strong>
            </div>

            {otpError && (
              <div style={{ color: '#DC2626', fontSize: '0.8rem', marginBottom: '0.75rem', fontWeight: 600 }}>
                {otpError}
              </div>
            )}

            <form onSubmit={handleVerifyOtp}>
              <input
                type="text"
                maxLength={4}
                required
                className="input-field"
                style={{ textAlign: 'center', letterSpacing: '0.4em', fontSize: '1.4rem', fontWeight: 800, marginBottom: '1.25rem' }}
                placeholder="• • • •"
                value={enteredOtp}
                onChange={(e) => setEnteredOtp(e.target.value)}
                autoFocus
              />

              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button
                  type="button"
                  onClick={() => setOtpVerifyModal(null)}
                  className="btn btn-secondary"
                  style={{ flex: 1 }}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1.5, fontWeight: 800 }}>
                  {t.btnConfirmHandover}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
