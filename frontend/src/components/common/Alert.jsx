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
      <div>
        {title && <div style={{ fontWeight: '600', marginBottom: '2px' }}>{title}</div>}
        <div>{children}</div>
      </div>
    </div>
  );
}
