import React from 'react';
import { ShieldCheck } from 'lucide-react';
import StatusBadge from '../common/StatusBadge';

function formatValue(value) {
  if (value === null || value === undefined) return 'Not evaluated';
  return `${Math.round(value * 100)}%`;
}

export default function TrustProfileBars({ dimensions = [] }) {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <ShieldCheck size={16} style={{ color: 'var(--cyan-neon)' }} />
            Model Trust Profile
          </div>
          <div className="card-subtitle">Dimension-based measurements from stored experiment evidence</div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {dimensions.map((dimension) => {
          const percent = dimension.value === null || dimension.value === undefined
            ? 0
            : Math.max(0, Math.min(100, Math.round(dimension.value * 100)));

          return (
            <div key={dimension.label}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', marginBottom: '6px' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.84rem', color: 'var(--text-primary)' }}>
                    {dimension.label}
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    {dimension.measurement}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--cyan-neon)' }}>
                    {formatValue(dimension.value)}
                  </span>
                  <StatusBadge status={dimension.status === 'measured' ? 'success' : 'pending'} label={dimension.status} />
                </div>
              </div>
              <div style={{ height: '8px', background: 'var(--bg-input)', borderRadius: '999px', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
                <div style={{ width: `${percent}%`, height: '100%', background: 'linear-gradient(90deg, var(--cyan-neon), var(--status-benign))' }} />
              </div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
                {dimension.explanation}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
