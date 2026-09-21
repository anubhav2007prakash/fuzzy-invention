import React, { useEffect, useState } from 'react';
import { healthApi } from '../../api/health';
import { ShieldCheck, AlertCircle, RefreshCw } from 'lucide-react';

export default function Header({ pageTitle }) {
  const [health, setHealth] = useState({ status: 'checking', service: 'SentinelCrypt AI' });
  const [isRefreshing, setIsRefreshing] = useState(false);

  const checkHealth = async () => {
    setIsRefreshing(true);
    try {
      const data = await healthApi.check();
      setHealth(data);
    } catch (err) {
      setHealth({ status: 'offline', error: err.message });
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const isHealthy = health.status === 'healthy';

  return (
    <header className="top-header">
      <div className="header-left">
        <h1 className="page-title">{pageTitle || 'Dashboard'}</h1>
      </div>

      <div className="header-right">
        <button
          className="btn btn-secondary"
          onClick={checkHealth}
          disabled={isRefreshing}
          style={{ padding: '6px 12px', fontSize: '0.78rem' }}
          title="Refresh backend status"
        >
          <RefreshCw size={14} className={isRefreshing ? 'spinner' : ''} />
          <span>Sync Status</span>
        </button>

        <div className={`health-pill ${!isHealthy ? 'badge-attack' : ''}`}>
          <div
            className="health-pulse"
            style={{
              background: isHealthy ? 'var(--status-benign)' : 'var(--status-attack)',
              boxShadow: `0 0 8px ${isHealthy ? 'var(--status-benign)' : 'var(--status-attack)'}`,
            }}
          />
          <span>API: {isHealthy ? 'ONLINE' : 'DISCONNECTED'}</span>
        </div>
      </div>
    </header>
  );
}
