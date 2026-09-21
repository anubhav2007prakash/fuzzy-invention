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
  FileText,
  Settings,
  Shield,
} from 'lucide-react';

export default function Sidebar() {
  const mainNav = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Datasets', path: '/datasets', icon: Database },
    { name: 'Model Lab', path: '/models', icon: BrainCircuit },
    { name: 'Predictions', path: '/predictions', icon: Activity },
    { name: 'Explainability', path: '/explainability', icon: Sparkles },
    { name: 'Audit Ledger', path: '/audit', icon: ShieldCheck },
  ];

  const researchNav = [
    { name: 'Experiments', path: '/experiments', icon: FlaskConical },
    { name: 'Documentation', path: '/docs', icon: FileText },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-icon">
          <Shield size={20} />
        </div>
        <div>
          <div className="brand-title">SentinelCrypt</div>
          <span className="brand-badge">RESEARCH v1.0</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-title">Core Operations</div>
        {mainNav.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={18} />
              <span>{item.name}</span>
            </NavLink>
          );
        })}

        <div className="nav-section-title">Research & Specs</div>
        {researchNav.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={18} />
              <span>{item.name}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ color: 'var(--cyan-neon)' }}>●</span>
          <span>Ledger Engine: Active</span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
          SHA-256 Forward Linkage
        </div>
      </div>
    </aside>
  );
}
