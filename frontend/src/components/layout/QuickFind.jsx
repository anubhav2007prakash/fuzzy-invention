import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, CornerDownLeft, Database, BrainCircuit, Activity, FlaskConical } from 'lucide-react';
import Modal from '../common/Modal';
import { datasetsApi } from '../../api/datasets';
import { modelsApi } from '../../api/models';
import { predictionsApi } from '../../api/predictions';
import { experimentsApi } from '../../api/experiments';
import { modelArchitecture } from '../../utils/format';

const NAV_ITEMS = [
  { name: 'Dashboard', path: '/', section: 'Workspace', hint: 'Security overview' },
  { name: 'Inference Console', path: '/predictions', section: 'Workspace', hint: 'Run single & batch predictions' },
  { name: 'Datasets (CSV)', path: '/datasets', section: 'Core Pipelines', hint: 'Upload, validate, preview' },
  { name: 'Model Lab', path: '/models', section: 'Core Pipelines', hint: 'Train and evaluate detectors' },
  { name: 'SHAP Attribution', path: '/explainability', section: 'Core Pipelines', hint: 'Feature attributions & stability' },
  { name: 'Audit Ledger', path: '/audit', section: 'Core Pipelines', hint: 'Hash-chained evidence & export' },
  { name: 'Research Lab', path: '/experiments', section: 'Research Suite', hint: 'EXP-A … EXP-H experiments' },
  { name: 'Benchmark', path: '/benchmark', section: 'Research Suite', hint: 'Standardized protocol & leaderboard' },
  { name: 'Challenges', path: '/challenges', section: 'Research Suite', hint: 'Q1–Q5 research questions' },
  { name: 'Provenance', path: '/provenance', section: 'Research Suite', hint: 'Dataset → evidence graph' },
  { name: 'Review & Collab', path: '/review', section: 'Research Suite', hint: 'HITL reviews & collaboration' },
  { name: 'Professor Mode', path: '/professor-mode', section: 'Research Suite', hint: 'Presentation summary' },
  { name: 'Documentation', path: '/docs', section: 'Research Suite', hint: 'Architecture docs' },
  { name: 'Settings', path: '/settings', section: 'Research Suite', hint: 'Connectivity, mode, diagnostics' },
];

/** Deep-search sources: registered entities, each with a landing route. */
const ENTITY_SOURCES = [
  {
    kind: 'Dataset',
    icon: Database,
    fetch: () => datasetsApi.list({ skip: 0, limit: 100 }),
    extract: (res) => (res?.datasets || []).map((d) => ({ id: d.id, title: d.name, hint: `${(d.row_count ?? 0).toLocaleString()} rows · ${d.validation_status || 'VALID'}`, path: '/datasets' })),
  },
  {
    kind: 'Model',
    icon: BrainCircuit,
    fetch: () => modelsApi.list({ skip: 0, limit: 100 }),
    extract: (res) => (res?.models || []).map((m) => ({ id: m.id, title: m.name, hint: `${modelArchitecture(m)} · ${m.version}`, path: `/models` })),
  },
  {
    kind: 'Prediction',
    icon: Activity,
    fetch: () => predictionsApi.list({ skip: 0, limit: 100 }),
    extract: (res) =>
      (res?.predictions || []).map((p) => ({
        id: p.prediction_id,
        title: `${p.predicted_class} · ${(p.confidence ?? 0).toFixed ? p.confidence.toFixed(3) : p.confidence ?? '—'}`,
        hint: `${p.prediction_id.substring(0, 8)} · ${p.created_at ? new Date(p.created_at).toLocaleString() : ''}`,
        path: `/explainability?prediction_id=${p.prediction_id}`,
      })),
  },
  {
    kind: 'Experiment',
    icon: FlaskConical,
    fetch: () => experimentsApi.list(),
    extract: (res) =>
      (res?.experiments || []).map((e) => ({
        id: e.experiment_id,
        title: `${e.experiment_id} — ${e.title || e.name || 'Experiment'}`,
        hint: e.status || 'READY',
        path: `/experiments?exp=${e.experiment_id}`,
      })),
  },
];

export default function QuickFind() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [entities, setEntities] = useState(null); // null = not yet loaded
  const entitiesLoaded = useRef(false);
  const navigate = useNavigate();

  // Open on real ⌘K / Ctrl+K and on the synthetic event dispatched by the
  // sidebar's Quick Find button (key: 'k' with metaKey+ctrlKey set).
  useEffect(() => {
    const handleKeyDown = (e) => {
      const synthetic = e.metaKey && e.ctrlKey && e.key === 'k';
      const real = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k';
      if (synthetic || real) {
        e.preventDefault();
        setIsOpen((open) => !open);
        setQuery('');
        setActiveIndex(0);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Lazy-load registered entities once, the first time the palette opens.
  useEffect(() => {
    if (!isOpen || entitiesLoaded.current) return;
    entitiesLoaded.current = true;
    Promise.all(
      ENTITY_SOURCES.map((src) =>
        src
          .fetch()
          .then((res) => ({ kind: src.kind, icon: src.icon, items: src.extract(res) }))
          .catch(() => ({ kind: src.kind, icon: src.icon, items: [] }))
      )
    ).then((groups) => {
      setEntities(groups.filter((g) => g.items.length > 0));
    });
  }, [isOpen]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pages = NAV_ITEMS.filter(
      (item) =>
        !q ||
        item.name.toLowerCase().includes(q) ||
        item.section.toLowerCase().includes(q) ||
        item.hint.toLowerCase().includes(q) ||
        item.path.toLowerCase().includes(q)
    ).map((item) => ({ ...item, type: 'page' }));

    const matches = (item) =>
      !q || item.title.toLowerCase().includes(q) || String(item.id).toLowerCase().includes(q) || String(item.hint || '').toLowerCase().includes(q);

    const entityGroups = (entities || [])
      .map((g) => ({ ...g, items: g.items.filter(matches) }))
      .filter((g) => g.items.length > 0)
      .slice(0, 3);

    return { pages, entityGroups };
  }, [query, entities]);

  // Flat result list for keyboard navigation.
  const flatResults = useMemo(() => {
    const out = results.pages.map((p) => ({ kind: 'page', ...p }));
    results.entityGroups.forEach((g) => {
      g.items.forEach((item) => out.push({ kind: 'entity', group: g.kind, icon: g.icon, ...item }));
    });
    return out;
  }, [results]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const go = (path) => {
    setIsOpen(false);
    navigate(path);
  };

  const onInputKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, flatResults.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && flatResults[activeIndex]) {
      e.preventDefault();
      go(flatResults[activeIndex].path);
    }
  };

  // Rows grouped for rendering, with running index so keyboard nav stays aligned.
  let renderIndex = -1;

  return (
    <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Quick Find" maxWidth="560px">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ position: 'relative' }}>
          <Search size={15} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            className="form-input"
            autoFocus
            placeholder="Search pages, datasets, models, predictions, experiments…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            style={{ paddingLeft: '32px' }}
          />
        </div>

        <div style={{ maxHeight: '360px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {flatResults.length === 0 ? (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', padding: '12px 4px' }}>
              No pages or records match “{query}”.
            </p>
          ) : (
            <>
              {results.pages.map((item) => {
                renderIndex += 1;
                const idx = renderIndex;
                return (
                  <button
                    key={`page-${item.path}`}
                    onClick={() => go(item.path)}
                    onMouseEnter={() => setActiveIndex(idx)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '10px',
                      padding: '9px 12px',
                      background: idx === activeIndex ? 'rgba(0, 242, 254, 0.08)' : 'transparent',
                      border: `1px solid ${idx === activeIndex ? 'rgba(0, 242, 254, 0.35)' : 'transparent'}`,
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      color: 'var(--text-primary)',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>{item.name}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {item.section} · {item.hint}
                      </div>
                    </div>
                    {idx === activeIndex && <CornerDownLeft size={13} style={{ color: 'var(--cyan-neon)', flexShrink: 0 }} />}
                  </button>
                );
              })}

              {results.entityGroups.map((group) => (
                <div key={group.kind} style={{ marginTop: '6px' }}>
                  <div style={{ fontSize: '0.66rem', fontWeight: 700, letterSpacing: '0.6px', color: 'var(--text-muted)', padding: '4px 12px 2px' }}>
                    {group.kind.toUpperCase()}S
                  </div>
                  {group.items.map((item) => {
                    renderIndex += 1;
                    const idx = renderIndex;
                    const Icon = group.icon;
                    return (
                      <button
                        key={`${group.kind}-${item.id}`}
                        onClick={() => go(item.path)}
                        onMouseEnter={() => setActiveIndex(idx)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '10px',
                          padding: '8px 12px',
                          background: idx === activeIndex ? 'rgba(0, 242, 254, 0.08)' : 'transparent',
                          border: `1px solid ${idx === activeIndex ? 'rgba(0, 242, 254, 0.35)' : 'transparent'}`,
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                          textAlign: 'left',
                          color: 'var(--text-primary)',
                          width: '100%',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '9px', minWidth: 0 }}>
                          <Icon size={13} style={{ color: 'var(--cyan-neon)', flexShrink: 0 }} />
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: '0.82rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {item.title}
                            </div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{item.hint}</div>
                          </div>
                        </div>
                        {idx === activeIndex && <CornerDownLeft size={13} style={{ color: 'var(--cyan-neon)', flexShrink: 0 }} />}
                      </button>
                    );
                  })}
                </div>
              ))}
            </>
          )}
        </div>

        <div style={{ display: 'flex', gap: '14px', fontSize: '0.68rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
          <span><span className="kbd-shortcut">↑↓</span> navigate</span>
          <span><span className="kbd-shortcut">↵</span> open</span>
          <span><span className="kbd-shortcut">esc</span> close</span>
          <span style={{ marginLeft: 'auto' }}><span className="kbd-shortcut">⌘K</span> toggle</span>
        </div>
      </div>
    </Modal>
  );
}
