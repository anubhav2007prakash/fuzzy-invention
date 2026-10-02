import React, { useEffect, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
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
  Gauge,
  GitBranch,
  Network,
  UserCheck,
} from 'lucide-react';

export default function Sidebar() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const headerRef = useRef(null);

  // Close the workspace menu on outside click or Escape.
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onPointerDown = (e) => {
      if (headerRef.current && !headerRef.current.contains(e.target)) setMenuOpen(false);
    };
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [menuOpen]);

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
    { name: 'Benchmark', path: '/benchmark', icon: Gauge },
    { name: 'Challenges', path: '/challenges', icon: GitBranch },
    { name: 'Provenance', path: '/provenance', icon: Network },
    { name: 'Review & Collab', path: '/review', icon: UserCheck },
    { name: 'Professor Mode', path: '/professor-mode', icon: Presentation },
    { name: 'Documentation', path: '/docs', icon: FileText },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <aside className="sidebar">
      {/* Qronos Brand Header */}
      <div className="sidebar-header" ref={headerRef} style={{ position: 'relative' }}>
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
        <button
          type="button"
          aria-label="Workspace menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
          style={{
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '6px',
            borderRadius: 'var(--radius-sm)',
            display: 'flex',
            alignItems: 'center',
            color: 'inherit',
          }}
        >
          <ChevronDown
            size={14}
            style={{
              color: 'var(--text-muted)',
              transform: menuOpen ? 'rotate(180deg)' : 'none',
              transition: 'transform 0.15s ease',
            }}
          />
        </button>

        {menuOpen && (
          <div
            style={{
              position: 'absolute',
              top: 'calc(100% - 6px)',
              right: '10px',
              zIndex: 60,
              minWidth: '180px',
              background: 'var(--bg-surface, #121218)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-sm)',
              boxShadow: '0 12px 32px rgba(0, 0, 0, 0.5)',
              padding: '4px',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {[
              { label: 'Quick Find…', action: () => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, ctrlKey: true })), icon: Search },
              { label: 'Professor Mode', action: () => navigate('/professor-mode'), icon: Presentation },
              { label: 'Documentation', action: () => navigate('/docs'), icon: FileText },
              { label: 'Settings', action: () => navigate('/settings'), icon: Settings },
            ].map(({ label, action, icon: Icon }) => (
              <button
                key={label}
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  action();
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 10px',
                  background: 'transparent',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-secondary)',
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <Icon size={13} /> {label}
              </button>
            ))}
          </div>
        )}
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
