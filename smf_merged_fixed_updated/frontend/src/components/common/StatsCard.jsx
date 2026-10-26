import React from 'react';

export default function StatsCard({
  id,
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  color = 'var(--primary)',
}) {
  return (
    <div
      className="glass-panel"
      style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '8px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 500 }}>
          {title}
        </span>
        {Icon && (
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-md)',
              background: `color-mix(in srgb, ${color} 15%, transparent)`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: color,
            }}
          >
            <Icon size={18} />
          </div>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px' }}>
        <span
          id={id}
          style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: 'var(--text-main)',
          }}
        >
          {value ?? '—'}
        </span>
        {trend && (
          <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>
            {trend}
          </span>
        )}
      </div>
      {subtitle && (
        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{subtitle}</span>
      )}
    </div>
  );
}
