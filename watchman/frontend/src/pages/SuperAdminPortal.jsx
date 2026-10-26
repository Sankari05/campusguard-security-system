import React, { useState, useEffect } from 'react';
import { api } from '../services/api';

export const SuperAdminPortal = ({ onBackToLanding, onLoginAsAdmin }) => {
  const [organizations, setOrganizations] = useState([]);
  const [filter, setFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState(null);

  // Approval modal state
  const [selectedOrgForApproval, setSelectedOrgForApproval] = useState(null);
  const [adminUsername, setAdminUsername] = useState('');
  const [adminPassword, setAdminPassword] = useState('pass123');
  const [approvalResult, setApprovalResult] = useState(null);

  // Rejection modal state
  const [selectedOrgForRejection, setSelectedOrgForRejection] = useState(null);
  const [rejectionReason, setRejectionReason] = useState('');

  const fetchOrganizations = async () => {
    setLoading(true);
    try {
      const data = await api.getSuperAdminOrganizations(filter === 'ALL' ? null : filter);
      setOrganizations(data);
    } catch (err) {
      console.error('Failed to load organizations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrganizations();
  }, [filter]);

  const handleApprove = async () => {
    if (!selectedOrgForApproval) return;
    try {
      const res = await api.approveOrganization(selectedOrgForApproval.id, {
        admin_username: adminUsername || undefined,
        admin_password: adminPassword || 'pass123'
      });
      setApprovalResult(res.admin_credentials);
      fetchOrganizations();
    } catch (err) {
      alert(`Approval error: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleReject = async () => {
    if (!selectedOrgForRejection || !rejectionReason.trim()) return;
    try {
      await api.rejectOrganization(selectedOrgForRejection.id, rejectionReason.trim());
      setSelectedOrgForRejection(null);
      setRejectionReason('');
      setActionMessage('Organization marked as REJECTED.');
      fetchOrganizations();
      setTimeout(() => setActionMessage(null), 4000);
    } catch (err) {
      alert(`Rejection error: ${err.response?.data?.detail || err.message}`);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'APPROVED':
        return <span style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#10B981', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '0.25rem 0.65rem', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 800 }}>✓ APPROVED</span>;
      case 'PENDING_APPROVAL':
        return <span style={{ backgroundColor: 'rgba(245, 158, 11, 0.15)', color: '#F59E0B', border: '1px solid rgba(245, 158, 11, 0.3)', padding: '0.25rem 0.65rem', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 800 }}>⏳ PENDING REVIEW</span>;
      case 'REJECTED':
        return <span style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#EF4444', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '0.25rem 0.65rem', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 800 }}>✕ REJECTED</span>;
      default:
        return <span>{status}</span>;
    }
  };

  const getVerticalIcon = (type) => {
    switch (type) {
      case 'COLLEGE': return '🎓';
      case 'HOSPITAL': return '🏥';
      case 'APARTMENT': return '🏢';
      case 'FACTORY': return '🏭';
      case 'OFFICE': return '🏛️';
      default: return '🛡️';
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#FFFFFF',
      backgroundImage: `
        radial-gradient(circle at 10% 15%, rgba(153, 246, 228, 0.35) 0%, rgba(186, 230, 253, 0.20) 30%, transparent 60%),
        radial-gradient(circle at 50% 38%, rgba(254, 215, 170, 0.40) 0%, rgba(254, 243, 199, 0.20) 32%, transparent 65%),
        radial-gradient(circle at 85% 80%, rgba(199, 210, 254, 0.40) 0%, rgba(224, 231, 255, 0.25) 35%, transparent 65%),
        linear-gradient(to right, rgba(14, 165, 233, 0.08) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(14, 165, 233, 0.08) 1px, transparent 1px)
      `,
      backgroundSize: '100% 100%, 100% 100%, 100% 100%, 36px 36px, 36px 36px',
      backgroundAttachment: 'fixed',
      color: '#0F172A',
      fontFamily: "'Inter', -apple-system, sans-serif",
      padding: '2rem 3rem'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2.5rem', borderBottom: '1px solid #E2E8F0', paddingBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.4rem',
            color: '#FFFFFF',
            boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)'
          }}>
            ⚡
          </div>
          <div>
            <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#0F172A' }}>GuardMate Platform Super-Admin</div>
            <div style={{ fontSize: '0.8rem', color: '#64748B' }}>Tenant Vetting, Life Cycle Approvals & Multi-Organization Control</div>
          </div>
        </div>

        <button
          onClick={onBackToLanding}
          style={{
            backgroundColor: '#F1F5F9',
            border: '1px solid #CBD5E1',
            color: '#334155',
            padding: '0.6rem 1.2rem',
            borderRadius: '10px',
            fontWeight: 800,
            cursor: 'pointer',
            fontSize: '0.85rem',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)'
          }}
        >
          &larr; Back to Landing Page
        </button>
      </div>

      {actionMessage && (
        <div style={{ backgroundColor: '#ECFDF5', border: '1.5px solid #10B981', color: '#065F46', padding: '0.85rem 1.25rem', borderRadius: '12px', marginBottom: '1.5rem', fontWeight: 700 }}>
          {actionMessage}
        </div>
      )}

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '2rem' }}>
        {['ALL', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'].map((st) => (
          <button
            key={st}
            onClick={() => setFilter(st)}
            style={{
              padding: '0.6rem 1.25rem',
              borderRadius: '10px',
              border: filter === st ? '2px solid #2563EB' : '1.5px solid #CBD5E1',
              backgroundColor: filter === st ? '#EFF6FF' : '#FFFFFF',
              color: filter === st ? '#1D4ED8' : '#475569',
              fontWeight: 800,
              fontSize: '0.82rem',
              cursor: 'pointer',
              boxShadow: filter === st ? '0 4px 12px rgba(37, 99, 235, 0.15)' : '0 1px 3px rgba(0,0,0,0.03)'
            }}
          >
            {st === 'ALL' ? 'All Organizations' : st.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Organizations Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '4rem', color: '#64748B' }}>Loading tenant applications...</div>
      ) : organizations.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '4rem', backgroundColor: '#FFFFFF', borderRadius: '20px', border: '1.5px solid #E2E8F0', boxShadow: '0 4px 15px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📭</div>
          <div style={{ fontSize: '1rem', fontWeight: 700, color: '#334155' }}>No organizations found under this filter.</div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(370px, 1fr))', gap: '1.5rem' }}>
          {organizations.map((org) => (
            <div
              key={org.id}
              style={{
                backgroundColor: '#FFFFFF',
                border: '1.5px solid #E2E8F0',
                borderRadius: '20px',
                padding: '1.75rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                boxShadow: '0 10px 30px -10px rgba(15, 23, 42, 0.08)'
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1.4rem' }}>{getVerticalIcon(org.org_type)}</span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 800, color: '#0284C7', backgroundColor: '#F0F9FF', border: '1px solid #BAE6FD', padding: '0.2rem 0.5rem', borderRadius: '6px' }}>
                      {org.org_type}
                    </span>
                  </div>
                  {getStatusBadge(org.status)}
                </div>

                <h3 style={{ fontSize: '1.25rem', fontWeight: 900, color: '#0F172A', margin: '0 0 0.5rem 0' }}>
                  {org.name}
                </h3>
                <div style={{ fontSize: '0.78rem', color: '#64748B', marginBottom: '1rem' }}>
                  Slug: <code style={{ color: '#2563EB', backgroundColor: '#EFF6FF', padding: '1px 6px', borderRadius: '4px' }}>{org.slug}</code> • {org.city}
                </div>

                <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '0.85rem', fontSize: '0.82rem', color: '#334155', display: 'flex', flexDirection: 'column', gap: '0.35rem', marginBottom: '1rem' }}>
                  <div><strong>👤 Contact:</strong> {org.contact_person}</div>
                  <div><strong>✉️ Email:</strong> {org.contact_email}</div>
                  <div><strong>📞 Phone:</strong> {org.contact_phone}</div>
                  <div><strong>🚪 Gates:</strong> {org.gate_count} configured • <strong>🛡️ Guards:</strong> {org.expected_guards} expected</div>
                </div>

                {org.security_requirements && (
                  <div style={{ fontSize: '0.78rem', color: '#475569', marginBottom: '1.25rem', lineHeight: 1.5, borderLeft: '3px solid #2563EB', paddingLeft: '0.75rem', backgroundColor: '#F8FAFC', padding: '0.5rem 0.75rem', borderRadius: '0 8px 8px 0' }}>
                    <strong>Requirements:</strong> {org.security_requirements}
                  </div>
                )}

                {org.rejection_reason && (
                  <div style={{ backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '8px', padding: '0.65rem', fontSize: '0.78rem', color: '#B91C1C', marginBottom: '1rem' }}>
                    <strong>Rejection Reason:</strong> {org.rejection_reason}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: '1.25rem', display: 'flex', gap: '0.75rem' }}>
                {org.status === 'PENDING_APPROVAL' && (
                  <>
                    <button
                      onClick={() => {
                        setSelectedOrgForApproval(org);
                        setAdminUsername(`admin_${org.slug.replace(/-/g, '_').substring(0, 18)}`);
                        setApprovalResult(null);
                      }}
                      style={{
                        flex: 1,
                        background: 'linear-gradient(135deg, #059669 0%, #047857 100%)',
                        color: '#FFFFFF',
                        border: 'none',
                        padding: '0.65rem 1rem',
                        borderRadius: '10px',
                        fontSize: '0.85rem',
                        fontWeight: 800,
                        cursor: 'pointer',
                        boxShadow: '0 4px 14px rgba(5, 150, 105, 0.3)'
                      }}
                    >
                      ✓ Approve Tenant
                    </button>
                    <button
                      onClick={() => {
                        setSelectedOrgForRejection(org);
                        setRejectionReason('');
                      }}
                      style={{
                        backgroundColor: '#FEF2F2',
                        border: '1.5px solid #FCA5A5',
                        color: '#B91C1C',
                        padding: '0.65rem 1rem',
                        borderRadius: '10px',
                        fontSize: '0.85rem',
                        fontWeight: 800,
                        cursor: 'pointer'
                      }}
                    >
                      Reject
                    </button>
                  </>
                )}

                {org.status === 'APPROVED' && (
                  <button
                    onClick={() => onLoginAsAdmin && onLoginAsAdmin(org)}
                    style={{
                      width: '100%',
                      backgroundColor: '#EFF6FF',
                      border: '1.5px solid #BFDBFE',
                      color: '#1D4ED8',
                      padding: '0.65rem 1rem',
                      borderRadius: '10px',
                      fontSize: '0.85rem',
                      fontWeight: 800,
                      cursor: 'pointer',
                      boxShadow: '0 2px 6px rgba(37, 99, 235, 0.08)'
                    }}
                  >
                    Manage {org.name} Workspace &rarr;
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Approval Modal */}
      {selectedOrgForApproval && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.45)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1.5rem' }}>
          <div style={{ backgroundColor: '#FFFFFF', border: '1.5px solid #E2E8F0', borderRadius: '24px', maxWidth: '520px', width: '100%', padding: '2rem', color: '#0F172A', boxShadow: '0 25px 60px -15px rgba(15, 23, 42, 0.25)' }}>
            <h3 style={{ fontSize: '1.4rem', fontWeight: 900, marginBottom: '0.5rem', color: '#0F172A' }}>
              Approve Organization Application
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: '1.5rem' }}>
              Approving <strong>{selectedOrgForApproval.name}</strong> will automatically generate default gates, shifts, and provision an Organization Admin account.
            </p>

            {!approvalResult ? (
              <div>
                <div style={{ marginBottom: '1rem' }}>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                    Tenant Admin Username
                  </label>
                  <input
                    type="text"
                    value={adminUsername}
                    onChange={(e) => setAdminUsername(e.target.value)}
                    style={{ width: '100%', padding: '0.75rem 1rem', borderRadius: '10px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.9rem' }}
                  />
                </div>

                <div style={{ marginBottom: '1.5rem' }}>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: '#334155', marginBottom: '0.4rem' }}>
                    Initial Temporary Password
                  </label>
                  <input
                    type="text"
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    style={{ width: '100%', padding: '0.75rem 1rem', borderRadius: '10px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.9rem' }}
                  />
                </div>

                <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                  <button
                    onClick={() => setSelectedOrgForApproval(null)}
                    style={{ backgroundColor: '#F1F5F9', color: '#475569', border: '1px solid #CBD5E1', padding: '0.65rem 1.25rem', borderRadius: '10px', fontWeight: 700, cursor: 'pointer' }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleApprove}
                    style={{ background: 'linear-gradient(135deg, #059669 0%, #047857 100%)', color: '#FFFFFF', border: 'none', padding: '0.65rem 1.5rem', borderRadius: '10px', fontWeight: 800, cursor: 'pointer', boxShadow: '0 4px 14px rgba(5, 150, 105, 0.35)' }}
                  >
                    Confirm & Issue Credentials
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <div style={{ backgroundColor: '#ECFDF5', border: '1.5px solid #10B981', borderRadius: '12px', padding: '1rem', marginBottom: '1.5rem' }}>
                  <div style={{ color: '#065F46', fontWeight: 800, fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                    🎉 Tenant Admin Provisioned!
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#1E293B' }}>
                    <div><strong>Username:</strong> <code style={{ color: '#2563EB', backgroundColor: '#EFF6FF', padding: '2px 6px', borderRadius: '4px' }}>{approvalResult.username}</code></div>
                    <div><strong>Password:</strong> <code style={{ color: '#2563EB', backgroundColor: '#EFF6FF', padding: '2px 6px', borderRadius: '4px' }}>{approvalResult.temporary_password}</code></div>
                    <div><strong>Role:</strong> <code style={{ color: '#2563EB', backgroundColor: '#EFF6FF', padding: '2px 6px', borderRadius: '4px' }}>{approvalResult.role}</code></div>
                  </div>
                </div>

                <button
                  onClick={() => {
                    setSelectedOrgForApproval(null);
                    setApprovalResult(null);
                  }}
                  style={{ width: '100%', background: 'linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)', color: '#FFFFFF', border: 'none', padding: '0.75rem', borderRadius: '10px', fontWeight: 800, cursor: 'pointer', boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)' }}
                >
                  Done
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Rejection Modal */}
      {selectedOrgForRejection && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(15, 23, 42, 0.45)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1.5rem' }}>
          <div style={{ backgroundColor: '#FFFFFF', border: '1.5px solid #E2E8F0', borderRadius: '24px', maxWidth: '480px', width: '100%', padding: '2rem', color: '#0F172A', boxShadow: '0 25px 60px -15px rgba(15, 23, 42, 0.25)' }}>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 900, marginBottom: '0.5rem', color: '#0F172A' }}>
              Reject Application
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#64748B', marginBottom: '1rem' }}>
              Please specify the audit reason for rejecting <strong>{selectedOrgForRejection.name}</strong>:
            </p>

            <textarea
              rows="3"
              placeholder="e.g. Unverified corporate domain, invalid security contact details"
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              style={{ width: '100%', padding: '0.75rem 1rem', borderRadius: '10px', border: '1.5px solid #CBD5E1', backgroundColor: '#FFFFFF', color: '#0F172A', fontSize: '0.85rem', resize: 'none', marginBottom: '1.5rem' }}
            />

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setSelectedOrgForRejection(null)}
                style={{ backgroundColor: '#F1F5F9', color: '#475569', border: '1px solid #CBD5E1', padding: '0.65rem 1.25rem', borderRadius: '10px', fontWeight: 700, cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                style={{ backgroundColor: '#DC2626', color: '#FFFFFF', border: 'none', padding: '0.65rem 1.5rem', borderRadius: '10px', fontWeight: 800, cursor: 'pointer', boxShadow: '0 4px 14px rgba(220, 38, 38, 0.3)' }}
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
