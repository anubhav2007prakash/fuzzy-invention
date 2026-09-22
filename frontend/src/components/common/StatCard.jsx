import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'cyan' }) {
  const accentColors = {
    cyan: '#00f2fe',
    blue: '#3b82f6',
    purple: '#a855f7',
    green: '#10b981',
    red: '#ef4444',
    amber: '#f59e0b',
  };

  const accent = accentColors[color] || '#ffffff';

  return (
    <div className="stat-card">
      {/* Top subtle glow rail */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '1px',
          background: `linear-gradient(90deg, transparent, ${accent}, transparent)`,
          opacity: 0.8,
        }}
      />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="stat-label">{title}</div>
        <div className="stat-value">{value ?? '—'}</div>
        {subtitle && (
          <div className="stat-subtitle" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '4px', height: '4px', borderRadius: '50%', backgroundColor: accent }} />
            <span>{subtitle}</span>
          </div>
        )}
      </div>

      {Icon && (
        <div
          className="stat-icon-wrapper"
          style={{
            borderColor: 'rgba(255, 255, 255, 0.12)',
          }}
        >
          <Icon size={18} style={{ color: accent }} />
        </div>
      )}
    </div>
  );
}
