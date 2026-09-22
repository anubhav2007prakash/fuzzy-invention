import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Database,
  BrainCircuit,
  Activity,
  Sparkles,
  ShieldCheck,
  FlaskConical,
  Presentation,
  FileText,
  Settings,
  Shield,
  Search,
  ChevronDown,
  Lock,
} from 'lucide-react';

export default function Sidebar() {
  const workspaceNav = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Inference Console', path: '/predictions', icon: Activity },
  ];

  const pipelineNav = [
    { name: 'Datasets (CSV)', path: '/datasets', icon: Database },
    { name: 'Model Lab', path: '/models', icon: BrainCircuit },
    { name: 'SHAP Attribution', path: '/explainability', icon: Sparkles },
    { name: 'Audit Ledger', path: '/audit', icon: ShieldCheck },
  ];

  const researchNav = [
    { name: 'Research Lab', path: '/experiments', icon: FlaskConical },
    { name: 'Professor Mode', path: '/professor-mode', icon: Presentation },
    { name: 'Documentation', path: '/docs', icon: FileText },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <aside className="sidebar">
      {/* Qronos Brand Header */}
      <div className="sidebar-header">
        <div className="brand-wrapper">
          <div className="brand-square">
            <Shield size={16} strokeWidth={2.5} />
          </div>
          <div>
            <div className="brand-name">SentinelCrypt</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginTop: '1px' }}>
              <span className="brand-badge">AI AGENT</span>
              <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>v1.0</span>
            </div>
          </div>
        </div>
        <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
      </div>

      {/* Qronos Quick Search Trigger */}
      <button
        type="button"
        className="sidebar-search-btn"
        onClick={() => {
          const evt = new KeyboardEvent('keydown', { key: 'k', metaKey: true, ctrlKey: true });
          window.dispatchEvent(evt);
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Search size={13} />
          <span>Quick Find...</span>
        </div>
        <span className="kbd-shortcut">⌘K</span>
      </button>

      {/* Navigation Groups */}
      <nav className="sidebar-nav">
        <div className="nav-section-title">Workspace</div>
        {workspaceNav.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={15} />
              <span>{item.name}</span>
            </NavLink>
          );
        })}

        <div className="nav-section-title">Core Pipelines</div>
        {pipelineNav.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={15} />
              <span>{item.name}</span>
            </NavLink>
          );
        })}

        <div className="nav-section-title">Research Suite</div>
        {researchNav.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={15} />
              <span>{item.name}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Qronos Sidebar Footer */}
      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <span className="health-pulse" />
            <span style={{ fontWeight: 600, color: '#ffffff', fontSize: '0.74rem' }}>Node #1</span>
          </div>
          <span style={{ fontSize: '0.62rem', color: 'var(--cyan-neon)', fontFamily: 'monospace' }}>SECURE</span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.66rem', display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Lock size={10} style={{ color: 'var(--cyan-neon)' }} />
          <span>SHA-256 Ledger: ONLINE</span>
        </div>
      </div>
    </aside>
  );
}
