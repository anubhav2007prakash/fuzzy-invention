import React from 'react';
import { Shield } from 'lucide-react';

export default function Loader({ text = 'Initializing telemetry...', size = 'md' }) {
  const isLarge = size === 'lg';
  const isSmall = size === 'sm';

  if (isSmall) {
    return (
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)' }}>
        <div className="spinner" style={{ width: '15px', height: '15px', color: 'var(--cyan-neon)' }} />
        {text && <span style={{ fontSize: '0.78rem' }}>{text}</span>}
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: isLarge ? '56px 24px' : '36px 20px',
        gap: '16px',
        color: 'var(--text-muted)',
      }}
    >
      <div
        style={{
          position: 'relative',
          width: isLarge ? '56px' : '44px',
          height: isLarge ? '56px' : '44px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* Outer glowing pulsing ring */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            border: '2px dashed rgba(0, 242, 254, 0.4)',
            animation: 'spin 8s linear infinite',
          }}
        />
        {/* Inner high-speed spinner */}
        <div
          className="spinner"
          style={{
            width: isLarge ? '40px' : '30px',
            height: isLarge ? '40px' : '30px',
            color: 'var(--cyan-neon)',
            borderTopColor: 'var(--blue-primary)',
          }}
        />
        {/* Center icon */}
        <div style={{ position: 'absolute', color: 'var(--cyan-neon)', opacity: 0.85 }}>
          <Shield size={isLarge ? 18 : 14} />
        </div>
      </div>

      {text && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
          <span
            style={{
              fontSize: '0.82rem',
              fontWeight: 600,
              color: 'var(--text-secondary)',
              letterSpacing: '0.3px',
              fontFamily: 'var(--font-mono, monospace)',
            }}
          >
            {text}
          </span>
          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
            Cryptographic handshake in progress
          </span>
        </div>
      )}
    </div>
  );
}
