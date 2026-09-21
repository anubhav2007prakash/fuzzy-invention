import React from 'react';

export default function Loader({ text = 'Loading...', size = 'md' }) {
  const spinnerSize = size === 'sm' ? '16px' : size === 'lg' ? '32px' : '22px';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '32px',
        gap: '12px',
        color: 'var(--text-muted)',
      }}
    >
      <div
        className="spinner"
        style={{ width: spinnerSize, height: spinnerSize, color: 'var(--cyan-neon)' }}
      />
      {text && <span style={{ fontSize: '0.85rem' }}>{text}</span>}
    </div>
  );
}
