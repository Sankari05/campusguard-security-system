import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import {
  Sparkles,
  HelpCircle,
  PackageCheck,
  Search,
  Plus,
  RefreshCw,
  Phone,
  User,
  MapPin,
  CheckCircle2,
  AlertCircle,
  Tag
} from 'lucide-react';

export const LostFoundManager = () => {
  const { language } = useAuth();
  const [activeTab, setActiveTab] = useState('FOUND'); // 'FOUND', 'LOST', 'MATCHES'
  const [lostItems, setLostItems] = useState([]);
  const [foundItems, setFoundItems] = useState([]);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(false);

  // Found registration modal
  const [showFoundModal, setShowFoundModal] = useState(false);
  const [foundName, setFoundName] = useState('');
  const [foundCategory, setFoundCategory] = useState('ELECTRONICS');
  const [foundDesc, setFoundDesc] = useState('');
  const [foundLoc, setFoundLoc] = useState('');
  const [storedAt, setStoredAt] = useState('Main Gate Locker #3');

  // Claim modal
  const [claimingItem, setClaimingItem] = useState(null);
  const [claimerName, setClaimerName] = useState('');
  const [claimerPhone, setClaimerPhone] = useState('');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [lost, found, match] = await Promise.all([
        api.getLostItems(),
        api.getFoundItems(),
        api.getSmartItemMatches()
      ]);
      setLostItems(lost || []);
      setFoundItems(found || []);
      setMatches(match || []);
    } catch {
      setLostItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRegisterFound = async (e) => {
    e.preventDefault();
    if (!foundName.trim()) return;

    await api.registerFoundItem({
      item_name: foundName,
      category: foundCategory,
      description: foundDesc,
      found_location: foundLoc,
      stored_at: storedAt
    });

    setFoundName('');
    setFoundDesc('');
    setFoundLoc('');
    setShowFoundModal(false);
    fetchData();
  };

  const handleClaim = async (e) => {
    e.preventDefault();
    if (!claimingItem || !claimerName.trim()) return;

    await api.claimFoundItem(claimingItem.id, {
      claimed_by_name: claimerName,
      claimed_by_phone: claimerPhone
    });

    setClaimingItem(null);
    setClaimerName('');
    setClaimerPhone('');
    fetchData();
  };

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* ── Top Header ────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ padding: '0.5rem', background: '#ecfdf5', borderRadius: '10px', color: '#059669' }}>
              <PackageCheck size={26} strokeWidth={2.4} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
                {language === 'ta' ? 'ஸ்மார்ட் தொலைந்தவை & கண்டெடுக்கப்பட்டவை' : 'Smart Campus Lost and Found Repository'}
              </h1>
              <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '0.2rem 0 0' }}>
                {language === 'ta' ? 'பொருட்கள் பதிவு, தானியங்கி மேட்சிங் & உரிமையாளர் சரிபார்ப்பு (Pillar 9)' : 'Pillar 9: AI/Tag-based matching suggestion, student claim verification, and gate locker custody'}
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={fetchData}
            className="btn btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700 }}
          >
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            {language === 'ta' ? 'புதுப்பி' : 'Refresh'}
          </button>
          <button
            onClick={() => setShowFoundModal(true)}
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 800, background: '#059669', borderColor: '#059669' }}
          >
            <Plus size={18} />
            {language === 'ta' ? '+ கிடைத்த பொருள் பதிவு' : '+ Register Found Item'}
          </button>
        </div>
      </div>

      {/* ── Smart Match Detection Banner ──────────────────────── */}
      {matches.length > 0 && (
        <div style={{ padding: '1.1rem 1.35rem', background: 'linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%)', borderRadius: '16px', border: '1.5px solid #6ee7b7', marginBottom: '1.5rem', boxShadow: '0 4px 14px rgba(5, 150, 105, 0.08)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Sparkles size={18} color="#059669" />
            <span style={{ fontSize: '0.88rem', fontWeight: 800, color: '#065f46', letterSpacing: '0.04em' }}>
              SMART AI MATCH DETECTED ({matches.length})
            </span>
          </div>
          {matches.map((m, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', background: 'white', padding: '0.85rem 1rem', borderRadius: '12px', border: '1px solid #d1fae5', marginTop: '0.5rem' }}>
              <div>
                <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#0f172a' }}>{m.item_name}</div>
                <div style={{ fontSize: '0.82rem', color: '#047857' }}>{m.suggested_action}</div>
              </div>
              <span style={{ fontSize: '0.75rem', fontWeight: 800, background: '#dcfce7', color: '#166534', padding: '0.25rem 0.65rem', borderRadius: '999px' }}>
                {(m.confidence_score * 100).toFixed(0)}% MATCH CONFIDENCE
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Sub Tabs ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem' }}>
        <button
          onClick={() => setActiveTab('FOUND')}
          style={{
            padding: '0.6rem 1.25rem',
            borderRadius: '10px',
            border: activeTab === 'FOUND' ? '2px solid #059669' : '1px solid #cbd5e1',
            background: activeTab === 'FOUND' ? '#ecfdf5' : 'white',
            color: activeTab === 'FOUND' ? '#065f46' : '#475569',
            fontWeight: 800,
            cursor: 'pointer'
          }}
        >
          Found Items in Locker ({foundItems.length})
        </button>
        <button
          onClick={() => setActiveTab('LOST')}
          style={{
            padding: '0.6rem 1.25rem',
            borderRadius: '10px',
            border: activeTab === 'LOST' ? '2px solid #059669' : '1px solid #cbd5e1',
            background: activeTab === 'LOST' ? '#ecfdf5' : 'white',
            color: activeTab === 'LOST' ? '#065f46' : '#475569',
            fontWeight: 800,
            cursor: 'pointer'
          }}
        >
          Student Lost Reports ({lostItems.length})
        </button>
      </div>

      {/* ── Items Grid ───────────────────────────────────────── */}
      {activeTab === 'FOUND' ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
          {foundItems.map((item) => (
            <div
              key={item.id}
              style={{
                background: 'white',
                borderRadius: '16px',
                border: '1px solid #e2e8f0',
                padding: '1.25rem',
                boxShadow: '0 4px 12px rgba(0,0,0,0.03)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#475569', letterSpacing: '0.04em' }}>
                    {item.item_code}
                  </span>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 800,
                      padding: '0.2rem 0.55rem',
                      borderRadius: '999px',
                      background: item.status === 'RETURNED' ? '#dcfce7' : '#fef3c7',
                      color: item.status === 'RETURNED' ? '#166534' : '#92400e'
                    }}
                  >
                    {item.status}
                  </span>
                </div>

                <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f172a', margin: '0 0 0.35rem' }}>
                  {item.item_name}
                </h3>

                <p style={{ fontSize: '0.82rem', color: '#64748b', lineHeight: 1.5, margin: '0 0 0.75rem' }}>
                  {item.description}
                </p>

                <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '0.4rem' }}>
                  📍 Found at: <strong>{item.found_location}</strong>
                </div>
                <div style={{ fontSize: '0.8rem', color: '#059669', marginBottom: '1rem', fontWeight: 700 }}>
                  🔒 Custody: {item.stored_at}
                </div>

                {item.status === 'RETURNED' && item.claimed_by_name && (
                  <div style={{ padding: '0.5rem 0.75rem', background: '#f8fafc', borderRadius: '8px', fontSize: '0.78rem', color: '#334155', marginBottom: '0.75rem' }}>
                    Returned to: <strong>{item.claimed_by_name}</strong> ({item.claimed_by_phone})
                  </div>
                )}
              </div>

              {item.status !== 'RETURNED' && (
                <button
                  onClick={() => setClaimingItem(item)}
                  className="btn btn-primary"
                  style={{ width: '100%', fontSize: '0.82rem', fontWeight: 800, background: '#059669', borderColor: '#059669' }}
                >
                  Verify & Handover to Student
                </button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
          {lostItems.map((item) => (
            <div
              key={item.id}
              style={{
                background: 'white',
                borderRadius: '16px',
                border: '1px solid #e2e8f0',
                padding: '1.25rem',
                boxShadow: '0 4px 12px rgba(0,0,0,0.03)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 800, padding: '0.2rem 0.5rem', background: '#fee2e2', color: '#991b1b', borderRadius: '6px' }}>
                  LOST REPORT
                </span>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  {new Date(item.date_lost).toLocaleDateString()}
                </span>
              </div>

              <h3 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f172a', margin: '0 0 0.35rem' }}>
                {item.item_name}
              </h3>

              <p style={{ fontSize: '0.82rem', color: '#64748b', lineHeight: 1.5, margin: '0 0 0.75rem' }}>
                {item.description}
              </p>

              <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '0.25rem' }}>
                Student: <strong>{item.reported_by_name}</strong>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#2563eb' }}>
                Phone: {item.contact_phone}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Register Found Modal ──────────────────────────────── */}
      {showFoundModal && (
        <div className="modal-backdrop">
          <div className="modal-content" style={{ maxWidth: '480px', borderRadius: '20px' }}>
            <h2 style={{ fontSize: '1.3rem', fontWeight: 800, margin: '0 0 1rem' }}>
              Register Found Campus Item
            </h2>

            <form onSubmit={handleRegisterFound}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                  Item Name
                </label>
                <input
                  type="text"
                  placeholder="e.g., Dell 65W Laptop Charger"
                  value={foundName}
                  onChange={(e) => setFoundName(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                  Category
                </label>
                <select
                  value={foundCategory}
                  onChange={(e) => setFoundCategory(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1' }}
                >
                  <option value="ELECTRONICS">Electronics (Laptops, Chargers, Earphones)</option>
                  <option value="BOOKS">Books & Lab Records</option>
                  <option value="ID_CARD">College ID Card & Badges</option>
                  <option value="WALLET">Wallets & Purses</option>
                  <option value="ACCESSORY">Bottles & Accessories</option>
                </select>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                  Found Location
                </label>
                <input
                  type="text"
                  placeholder="e.g., Central Library Table 14"
                  value={foundLoc}
                  onChange={(e) => setFoundLoc(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                  Locker Custody Box
                </label>
                <input
                  type="text"
                  value={storedAt}
                  onChange={(e) => setStoredAt(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                  Description / Identifying Marks
                </label>
                <textarea
                  rows="2"
                  placeholder="Any unique serial number, color, sticker or marks..."
                  value={foundDesc}
                  onChange={(e) => setFoundDesc(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setShowFoundModal(false)}
                  className="btn btn-secondary"
                  style={{ fontWeight: 700 }}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" style={{ fontWeight: 800, background: '#059669', borderColor: '#059669' }}>
                  Save to Locker
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Handover Claim Modal ──────────────────────────────── */}
      {claimingItem && (
        <div className="modal-backdrop">
          <div className="modal-content" style={{ maxWidth: '440px', borderRadius: '20px' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: '0 0 0.5rem' }}>
              Handover Verification
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1.25rem' }}>
              Handing over: <strong>{claimingItem.item_name}</strong> (#{claimingItem.item_code})
            </p>

            <form onSubmit={handleClaim}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                  Student / Receiver Name
                </label>
                <input
                  type="text"
                  placeholder="e.g., Vigneshwaran K"
                  value={claimerName}
                  onChange={(e) => setClaimerName(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1' }}
                  required
                />
              </div>

              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.4rem' }}>
                  Student Contact Phone
                </label>
                <input
                  type="text"
                  placeholder="e.g., 9845612342"
                  value={claimerPhone}
                  onChange={(e) => setClaimerPhone(e.target.value)}
                  style={{ width: '100%', padding: '0.65rem', borderRadius: '10px', border: '1px solid #cbd5e1' }}
                  required
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => setClaimingItem(null)}
                  className="btn btn-secondary"
                  style={{ fontWeight: 700 }}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" style={{ fontWeight: 800, background: '#059669', borderColor: '#059669' }}>
                  Confirm Return
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
