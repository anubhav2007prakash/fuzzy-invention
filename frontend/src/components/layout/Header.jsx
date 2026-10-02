import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { healthApi } from '../../api/health';
import { RefreshCw, Search, ChevronRight } from 'lucide-react';

// First page of each nav section — where a breadcrumb section click lands.
const SECTION_HOME = {
  Workspace: '/',
  'Core Pipelines': '/datasets',
  'Research Suite': '/experiments',
};

export default function Header({ pageTitle, pageSection = 'Workspace' }) {
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
      {/* Qronos Breadcrumb Navigation */}
      <div className="header-breadcrumbs">
        <Link to="/" className="breadcrumb-link">SentinelCrypt</Link>
        <ChevronRight size={12} className="breadcrumb-separator" />
        {SECTION_HOME[pageSection] ? (
          <Link to={SECTION_HOME[pageSection]} className="breadcrumb-link">{pageSection}</Link>
        ) : (
          <span className="breadcrumb-root">{pageSection}</span>
        )}
        <ChevronRight size={12} className="breadcrumb-separator" />
        <span className="breadcrumb-current">{pageTitle}</span>
      </div>

      <div className="header-right">
        {/* Qronos Signature Star Button */}
        <button
          className="qronos-star-button"
          onClick={checkHealth}
          disabled={isRefreshing}
          title="Trigger cryptographic health check"
        >
          <RefreshCw size={12} className={isRefreshing ? 'spinner' : ''} />
          <span>{isRefreshing ? 'Syncing...' : 'Sync Telemetry »'}</span>
        </button>

        {/* API Health Pill */}
        <div className={`health-pill ${!isHealthy ? 'badge-attack' : ''}`}>
          <div
            className="health-pulse"
            style={{
              background: isHealthy ? 'var(--status-benign)' : 'var(--status-attack)',
              boxShadow: `0 0 10px ${isHealthy ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)'}`,
            }}
          />
          <span>API: {isHealthy ? 'ONLINE' : 'OFFLINE'}</span>
        </div>
      </div>
    </header>
  );
}
