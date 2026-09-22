import React from 'react';
import { AlertCircle, CheckCircle2, AlertTriangle, Info } from 'lucide-react';

export default function Alert({ type = 'info', title, children }) {
  const iconMap = {
    info: Info,
    success: CheckCircle2,
    warning: AlertTriangle,
    danger: AlertCircle,
  };

  const Icon = iconMap[type] || Info;

  return (
    <div className={`alert alert-${type}`}>
      <div style={{ flexShrink: 0, marginTop: '2px' }}>
        <Icon size={18} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {title && <div style={{ fontWeight: '700', marginBottom: '3px', fontSize: '0.86rem' }}>{title}</div>}
        <div style={{ fontSize: '0.82rem', lineHeight: '1.5' }}>{children}</div>
      </div>
    </div>
  );
}
