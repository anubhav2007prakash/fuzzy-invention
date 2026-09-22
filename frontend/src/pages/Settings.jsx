import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Server, Shield, RefreshCw, CheckCircle2, AlertCircle, Activity } from 'lucide-react';
import Alert from '../components/common/Alert';
import StatusBadge from '../components/common/StatusBadge';
import { healthApi } from '../api/health';
import { BASE_URL } from '../api/client';

const formatUptime = (seconds) => {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
};

export default function Settings() {
  const [health, setHealth] = useState(null);
  const [details, setDetails] = useState(null);
  const [checking, setChecking] = useState(false);

  const checkConnectivity = async () => {
    setChecking(true);
    try {
      const [data, det] = await Promise.all([
        healthApi.check(),
        healthApi.detailed().catch(() => null),
      ]);
      setHealth(data);
      setDetails(det);
    } catch (err) {
      setHealth({ status: 'offline', error: err.message });
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkConnectivity();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '800px' }}>
      {/* Header */}
      <div>
        <h2 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
          System Settings & Environment
        </h2>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
          Configure API endpoints, verify backend connectivity, and inspect system telemetry.
        </p>
      </div>

      {/* Connectivity Check */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Server size={18} style={{ color: 'var(--cyan-neon)' }} />
            FastAPI Backend Service Connection
          </div>
          <button
            className="btn btn-secondary"
            onClick={checkConnectivity}
            disabled={checking}
            style={{ fontSize: '0.78rem', padding: '6px 12px' }}
          >
            <RefreshCw size={14} className={checking ? 'spinner' : ''} />
            Test Connection
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {health ? (
            <Alert
              type={health.status === 'healthy' ? 'success' : 'danger'}
              title={health.status === 'healthy' ? 'Connected to SentinelCrypt Backend' : 'Connection Offline'}
            >
              {health.status === 'healthy' ? (
                <div>
                  Service: <strong>{health.service}</strong> | Environment: <strong>{health.environment}</strong> | Version: <strong>{health.api_version}</strong>
                </div>
              ) : (
                <div>
                  Could not reach backend API at <code>{BASE_URL}</code>. Ensure the FastAPI backend server is running on port 8000.
                </div>
              )}
            </Alert>
          ) : null}

          <div className="form-group">
            <label className="form-label">API Gateway Base URL</label>
            <input
              type="text"
              className="form-input font-mono"
              value={BASE_URL}
              readOnly
            />
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Configured via Vite proxy: <code>http://localhost:8000/api/v1</code>
            </span>
          </div>
        </div>
      </div>

      {/* System Diagnostics (/health/detailed) */}
      {details && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Activity size={18} style={{ color: 'var(--cyan-neon)' }} />
              System Health Diagnostics
            </div>
            <StatusBadge
              status={details.status === 'healthy' ? 'healthy' : 'failed'}
              label={details.status === 'healthy' ? 'Healthy' : 'Degraded'}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.82rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Database</span>
              <span
                className="font-mono"
                style={{ color: details.database?.status === 'connected' ? 'var(--cyan-neon)' : 'var(--status-attack)' }}
              >
                {details.database?.status}
                {details.database?.url ? ` (${details.database.url})` : ''}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Alembic Migration</span>
              <span className="font-mono" style={{ color: 'var(--cyan-neon)' }}>{details.alembic_version}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Service Uptime</span>
              <span className="font-mono">{formatUptime(details.uptime_seconds || 0)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Python Runtime</span>
              <span className="font-mono">{details.python_version}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Registry Counts</span>
              <span className="font-mono">
                {details.datasets_count ?? '—'} datasets · {details.models_count ?? '—'} models · {details.predictions_count ?? '—'} predictions · {details.audit_records_count ?? '—'} audit records
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Engine Parameters */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Shield size={18} style={{ color: 'var(--purple-accent)' }} />
            Cryptographic Engine Parameters
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <span>Hash Primitive</span>
            <span className="font-mono" style={{ color: 'var(--cyan-neon)' }}>SHA-256 (NIST FIPS 180-4)</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <span>Canonical Serializer</span>
            <span className="font-mono">Deterministic RFC 8785 JSON</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
            <span>Reproducibility Seed</span>
            <span className="font-mono">random_state = 42</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0' }}>
            <span>XAI Methodologies</span>
            <span className="font-mono">TreeSHAP / LinearSHAP</span>
          </div>
        </div>
      </div>
    </div>
  );
}
