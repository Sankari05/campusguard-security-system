import React from 'react';
import StatusBadge from '../common/StatusBadge';

export default function StudentTable({ students = [], loading }) {
  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading student roster from database...
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          textAlign: 'left',
          fontSize: '0.875rem',
        }}
      >
        <thead>
          <tr
            style={{
              borderBottom: '1px solid var(--border-subtle)',
              color: 'var(--text-dim)',
              fontSize: '0.75rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            <th style={{ padding: '12px 16px' }}>Reg Number</th>
            <th style={{ padding: '12px 16px' }}>Full Name</th>
            <th style={{ padding: '12px 16px' }}>Department</th>
            <th style={{ padding: '12px 16px' }}>Year / Sec</th>
            <th style={{ padding: '12px 16px' }}>Status</th>
            <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {students.length > 0 ? (
            students.map((st, idx) => (
              <tr
                key={st.register_number || st.id || idx}
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  transition: 'background var(--transition-fast)',
                }}
              >
                <td
                  style={{
                    padding: '14px 16px',
                    fontFamily: 'var(--font-mono)',
                    fontWeight: 600,
                    color: 'var(--accent-cyan)',
                  }}
                >
                  {st.register_number || st.roll_number || 'REG-00' + idx}
                </td>
                <td style={{ padding: '14px 16px', fontWeight: 600, color: 'var(--text-main)' }}>
                  {st.name ||
                    `${st.first_name || ''} ${st.last_name || ''}`.trim() ||
                    'Student ' + (idx + 1)}
                </td>
                <td style={{ padding: '14px 16px', color: 'var(--text-muted)' }}>
                  {st.department || 'CSE'}
                </td>
                <td style={{ padding: '14px 16px', color: 'var(--text-muted)' }}>
                  {st.year || 'III'} - {st.section || 'A'}
                </td>
                <td style={{ padding: '14px 16px' }}>
                  <StatusBadge status={st.status || 'Active'} />
                </td>
                <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                  >
                    View Profile
                  </button>
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td
                colSpan="6"
                style={{ padding: '30px', textAlign: 'center', color: 'var(--text-dim)' }}
              >
                No student records found in database.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
