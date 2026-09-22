import React from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';

export default function StatusBadge({ status, label, size = 'sm' }) {
  const norm = String(status || label || '').toLowerCase();

  let badgeClass = 'badge-info';
  let Icon = Info;
  let text = label || status;
  let pulseDotColor = null;

  if (
    norm.includes('benign') ||
    norm.includes('verified') ||
    norm.includes('valid') ||
    norm.includes('normal') ||
    norm.includes('healthy') ||
    norm.includes('success')
  ) {
    badgeClass = 'badge-benign';
    Icon = CheckCircle2;
    pulseDotColor = 'var(--status-benign)';
  } else if (
    norm.includes('attack') ||
    norm.includes('tamper') ||
    norm.includes('fail') ||
    norm.includes('corrupt') ||
    norm.includes('malicious') ||
    norm.includes('dos') ||
    norm.includes('exploit')
  ) {
    badgeClass = 'badge-attack';
    Icon = ShieldAlert;
    pulseDotColor = 'var(--status-attack)';
  } else if (
    norm.includes('warn') ||
    norm.includes('suspicious') ||
    norm.includes('pending') ||
    norm.includes('training')
  ) {
    badgeClass = 'badge-warning';
    Icon = AlertTriangle;
    pulseDotColor = 'var(--status-warning)';
  } else if (
    norm.includes('shap') ||
    norm.includes('xai') ||
    norm.includes('rf') ||
    norm.includes('model')
  ) {
    badgeClass = 'badge-purple';
    Icon = ShieldCheck;
    pulseDotColor = 'var(--purple-accent)';
  }

  return (
    <span
      className={`badge ${badgeClass}`}
      style={{
        fontSize: size === 'lg' ? '0.82rem' : '0.7rem',
        padding: size === 'lg' ? '5px 12px' : '3px 9px',
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
      }}
    >
      {pulseDotColor && (
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: pulseDotColor,
            boxShadow: `0 0 6px ${pulseDotColor}`,
            flexShrink: 0,
          }}
        />
      )}
      <Icon size={size === 'lg' ? 14 : 11} />
      <span>{text}</span>
    </span>
  );
}
