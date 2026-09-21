import React from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';

export default function StatusBadge({ status, label, size = 'sm' }) {
  const norm = String(status || label || '').toLowerCase();

  let badgeClass = 'badge-info';
  let Icon = Info;
  let text = label || status;

  if (norm.includes('benign') || norm.includes('verified') || norm.includes('valid') || norm.includes('normal') || norm.includes('healthy') || norm.includes('success')) {
    badgeClass = 'badge-benign';
    Icon = CheckCircle2;
  } else if (norm.includes('attack') || norm.includes('tamper') || norm.includes('fail') || norm.includes('corrupt') || norm.includes('malicious') || norm.includes('dos') || norm.includes('exploit')) {
    badgeClass = 'badge-attack';
    Icon = ShieldAlert;
  } else if (norm.includes('warn') || norm.includes('suspicious') || norm.includes('pending') || norm.includes('training')) {
    badgeClass = 'badge-warning';
    Icon = AlertTriangle;
  } else if (norm.includes('shap') || norm.includes('xai') || norm.includes('rf') || norm.includes('model')) {
    badgeClass = 'badge-purple';
    Icon = ShieldCheck;
  }

  return (
    <span className={`badge ${badgeClass}`} style={{ fontSize: size === 'lg' ? '0.85rem' : '0.72rem' }}>
      <Icon size={size === 'lg' ? 14 : 12} />
      <span>{text}</span>
    </span>
  );
}
