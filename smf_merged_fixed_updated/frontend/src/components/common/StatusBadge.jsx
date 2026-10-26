import React from 'react';

export default function StatusBadge({ status }) {
  const norm = (status || '').toLowerCase();

  if (norm === 'present' || norm === 'active') {
    return <span className="badge badge-present">● {status}</span>;
  }
  if (norm === 'absent' || norm === 'inactive') {
    return <span className="badge badge-absent">● {status}</span>;
  }
  if (norm === 'od' || norm === 'on-duty') {
    return <span className="badge badge-od">★ {status}</span>;
  }
  return (
    <span
      className="badge"
      style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--text-muted)' }}
    >
      {status || 'Unknown'}
    </span>
  );
}
