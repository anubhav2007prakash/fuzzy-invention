import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'cyan' }) {
  const colorMap = {
    cyan: { bg: 'rgba(0, 242, 254, 0.12)', color: 'var(--cyan-neon)', border: 'rgba(0, 242, 254, 0.25)' },
    blue: { bg: 'rgba(59, 130, 246, 0.12)', color: 'var(--blue-primary)', border: 'rgba(59, 130, 246, 0.25)' },
    green: { bg: 'var(--status-benign-bg)', color: 'var(--status-benign)', border: 'rgba(16, 185, 129, 0.25)' },
    red: { bg: 'var(--status-attack-bg)', color: 'var(--status-attack)', border: 'rgba(239, 68, 68, 0.25)' },
    amber: { bg: 'var(--status-warning-bg)', color: 'var(--status-warning)', border: 'rgba(245, 158, 11, 0.25)' },
    purple: { bg: 'var(--purple-glow)', color: 'var(--purple-accent)', border: 'rgba(168, 85, 247, 0.25)' },
  };

  const scheme = colorMap[color] || colorMap.cyan;

  return (
    <div className="stat-card">
      <div>
        <div className="stat-label">{title}</div>
        <div className="stat-value">{value ?? '—'}</div>
        {subtitle && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{subtitle}</div>}
      </div>
      {Icon && (
        <div
          className="stat-icon-wrapper"
          style={{
            background: scheme.bg,
            color: scheme.color,
            border: `1px solid ${scheme.border}`,
          }}
        >
          <Icon size={22} />
        </div>
      )}
    </div>
  );
}
