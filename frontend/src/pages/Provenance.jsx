import React, { useEffect, useMemo, useState } from 'react';
import { Network, ShieldCheck, RefreshCw, Link2 } from 'lucide-react';
import Alert from '../components/common/Alert';
import { provenanceApi } from '../api/research';

const TYPE_META = {
  dataset: { color: 'var(--cyan-neon)', icon: '📥', title: 'Datasets' },
  raw_dataset: { color: 'var(--cyan-neon)', icon: '📥', title: 'Raw Dataset' },
  validated_dataset: { color: 'var(--cyan-neon)', icon: '✓', title: 'Validated Dataset' },
  processed_dataset: { color: 'var(--cyan-neon)', icon: '⚙', title: 'Processed Dataset' },
  training_configuration: { color: 'var(--purple-accent)', icon: '⚙', title: 'Training Configuration' },
  model: { color: 'var(--purple-accent)', icon: '🧠', title: 'Models' },
  experiment: { color: 'var(--status-warning)', icon: '🧪', title: 'Experiments' },
  prediction: { color: 'var(--status-benign)', icon: '📊', title: 'Predictions' },
  explanation: { color: 'var(--cyan-neon)', icon: '🔍', title: 'Explanations' },
  evidence: { color: 'var(--status-attack)', icon: '🔐', title: 'Evidence blocks' },
  package: { color: 'var(--purple-accent)', icon: '📦', title: 'Evidence packages' },
  report: { color: 'var(--text-primary)', icon: '📄', title: 'Reports' },
};

const LINEAGE_STAGES = [
  'raw_dataset', 'validated_dataset', 'processed_dataset',
  'training_configuration', 'experiment', 'model', 'prediction',
  'explanation', 'results', 'report',
];

function ArtifactLineageGraph({ lineage, onSelect }) {
  const nodes = lineage?.nodes || [];
  if (!nodes.length) {
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>No artifact lineage has been recorded yet.</p>;
  }

  const stages = [...LINEAGE_STAGES, ...new Set(
    nodes.map((node) => node.artifact_type).filter((type) => !LINEAGE_STAGES.includes(type)),
  )];
  const groups = stages.map((type) => nodes.filter((node) => node.artifact_type === type));
  const positions = new Map();
  groups.forEach((group, column) => group.forEach((node, row) => {
    positions.set(node.artifact_id, { x: column * 220 + 12, y: row * 100 + 48 });
  }));
  const width = Math.max(220, groups.length * 220);
  const height = Math.max(320, ...groups.map((group) => group.length * 100 + 72));

  return (
    <div style={{ overflowX: 'auto', paddingBottom: '8px' }} aria-label="Artifact lineage graph">
      <div style={{ position: 'relative', width, height, minWidth: '100%' }}>
        <svg aria-hidden="true" width={width} height={height} style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
        }}>
          <defs>
            <marker id="lineage-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill="var(--cyan-neon)" />
            </marker>
          </defs>
          {(lineage.edges || []).map((edge) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) return null;
            return (
              <path
                key={`${edge.source}->${edge.target}`}
                d={`M ${source.x + 184} ${source.y + 27} C ${source.x + 205} ${source.y + 27}, ${target.x - 18} ${target.y + 27}, ${target.x - 5} ${target.y + 27}`}
                fill="none"
                stroke="var(--cyan-neon)"
                strokeOpacity="0.55"
                strokeWidth="2"
                markerEnd="url(#lineage-arrow)"
              />
            );
          })}
        </svg>
        {groups.map((group, column) => {
          const type = stages[column];
          const meta = TYPE_META[type] || { color: 'var(--text-muted)', title: type };
          return (
            <section key={type} aria-label={meta.title} style={{
              position: 'absolute', left: column * 220, top: 0, width: 210, height: '100%',
            }}>
              <h4 style={{
                color: meta.color, fontSize: '0.7rem', textTransform: 'uppercase',
                letterSpacing: '0.04em', margin: '8px 0',
              }}>{meta.title}</h4>
              {group.map((node, row) => (
                <button
                  key={node.artifact_id}
                  type="button"
                  onClick={() => onSelect({
                    id: node.artifact_id,
                    type: node.artifact_type,
                    label: node.artifact_id,
                    provenance: 'lineage',
                    metadata: {
                      parent_artifact_id: node.parent_artifact_id,
                      created_at: node.created_at,
                      version: node.version,
                      sha256: node.sha256,
                      git_commit: node.git_commit,
                      experiment_id: node.experiment_id,
                      ...node.metadata,
                    },
                  })}
                  title={`${node.artifact_id} · SHA-256 ${node.sha256}`}
                  style={{
                    position: 'absolute', top: 40 + row * 100, left: 0, width: 194,
                    minHeight: 58, padding: '8px', textAlign: 'left',
                    background: 'var(--bg-surface)', color: 'var(--text-primary)',
                    border: `1px solid ${meta.color}`, borderRadius: 'var(--radius-sm)',
                    cursor: 'pointer', zIndex: 1,
                  }}
                >
                  <span style={{
                    display: 'block', fontSize: '0.72rem', fontWeight: 700, overflowWrap: 'anywhere',
                  }}>{node.artifact_id}</span>
                  <span style={{
                    display: 'block', fontSize: '0.62rem', color: 'var(--text-muted)', fontFamily: 'monospace',
                  }}>SHA-256 {node.sha256.slice(0, 12)}…</span>
                </button>
              ))}
            </section>
          );
        })}
      </div>
    </div>
  );
}

function TrustChecklist({ trust }) {
  if (!trust) return null;
  return (
    <div style={{ marginTop: '14px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
      <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: '8px', color: 'var(--cyan-neon)' }}>
        <ShieldCheck size={14} style={{ verticalAlign: '-2px' }} /> {trust.title}
        <span style={{ marginLeft: '8px', color: 'var(--text-muted)', fontWeight: 400, fontSize: '0.75rem' }}>
          {trust.checks_passed}/{trust.checks_total} checks pass
        </span>
      </div>
      {(trust.checks || []).map((c) => (
        <div key={c.check} style={{ padding: '5px 0', borderBottom: '1px dashed var(--border-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem' }}>
            <span style={{ fontWeight: 600 }}>{c.check}</span>
            <span style={{ color: c.passed ? 'var(--status-benign)' : 'var(--status-warning)' }}>
              {c.passed ? '✓ pass' : '⚠ missing'}
            </span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{c.evidence}</div>
          <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>source: {c.source}</div>
        </div>
      ))}
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '8px' }}>
        {trust.scoring_note}
      </div>
    </div>
  );
}

export default function Provenance() {
  const [graph, setGraph] = useState(null);
  const [lineage, setLineage] = useState(null);
  const [selected, setSelected] = useState(null);
  const [trust, setTrust] = useState(null);
  const [error, setError] = useState(null);

  const load = async () => {
    try {
      setError(null);
      const [provenanceGraph, artifactGraph] = await Promise.all([
        provenanceApi.graph(),
        provenanceApi.lineage(),
      ]);
      setGraph(provenanceGraph);
      setLineage(artifactGraph);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => { load(); }, []);

  const byType = useMemo(() => {
    const groups = {};
    for (const node of graph?.nodes || []) {
      (groups[node.type] = groups[node.type] || []).push(node);
    }
    return groups;
  }, [graph]);

  const edgesFor = useMemo(() => {
    if (!selected) return { upstream: [], downstream: [] };
    const upstream = [];
    const downstream = [];
    for (const e of [...(graph?.edges || []), ...(lineage?.edges || [])]) {
      if (e.source === selected.id) downstream.push(e);
      if (e.target === selected.id) upstream.push(e);
    }
    return { upstream, downstream };
  }, [graph, lineage, selected]);

  const labelOf = (nodeId) =>
    [...(graph?.nodes || []), ...(lineage?.nodes || []).map((n) => ({
      id: n.artifact_id, label: n.artifact_id,
    }))].find((n) => n.id === nodeId)?.label || nodeId;

  const inspect = async (node) => {
    setSelected(node);
    setTrust(null);
    try {
      if (node.provenance !== 'lineage' && node.type === 'prediction') {
        setTrust(await provenanceApi.predictionTrust(node.id.replace('prediction:', '')));
      } else if (node.provenance !== 'lineage' && node.type === 'experiment') {
        setTrust(await provenanceApi.experimentTrust(node.id.replace('experiment:', '')));
      }
    } catch {
      setTrust(null); // checklist is best-effort
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            <Network size={18} style={{ color: 'var(--cyan-neon)', marginRight: '8px', verticalAlign: '-3px' }} />
            Provenance Graph
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Dataset → model → experiment → prediction → explanation → evidence, built from actual stored
            records. Click any node to inspect its metadata and trust evidence.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={load}><RefreshCw size={14} /> Refresh</button>
      </div>

      {error && <Alert type="danger" title="Provenance Error">{error}</Alert>}

      <div className="card">
        <div className="card-header">
          <div className="card-title">Cryptographic Artifact Lineage</div>
          <div className="card-subtitle">
            {lineage?.nodes?.length || 0} persisted artifacts · integrity {lineage?.integrity || 'loading'}
          </div>
        </div>
        <ArtifactLineageGraph lineage={lineage} onSelect={inspect} />
      </div>

      <div className="grid-2" style={{ alignItems: 'start', gap: '20px' }}>
        {/* Graph — grouped by node type */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Graph</div>
            <div className="card-subtitle">
              {graph ? `${graph.nodes?.length || 0} nodes · ${graph.edges?.length || 0} edges` : 'Loading…'}
            </div>
          </div>
          {!graph ? (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Loading…</p>
          ) : (graph.nodes || []).length === 0 ? (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              No provenance nodes yet — upload a dataset or run an experiment first.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {Object.entries(byType).map(([type, nodes]) => {
                const meta = TYPE_META[type] || { color: 'var(--text-muted)', icon: '•', title: type };
                return (
                  <div key={type}>
                    <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', color: meta.color, marginBottom: '6px' }}>
                      {meta.icon} {meta.title} ({nodes.length})
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {nodes.slice(0, 24).map((node) => (
                        <button
                          key={node.id}
                          onClick={() => inspect(node)}
                          title={node.id}
                          style={{
                            background: selected?.id === node.id ? 'var(--bg-input)' : 'var(--bg-surface)',
                            border: `1px solid ${selected?.id === node.id ? meta.color : 'var(--border-subtle)'}`,
                            borderRadius: 'var(--radius-sm)',
                            padding: '6px 10px',
                            cursor: 'pointer',
                            textAlign: 'left',
                            color: 'var(--text-primary)',
                          }}
                        >
                          <div style={{ fontSize: '0.76rem', fontWeight: 600 }}>{node.label}</div>
                          <div className="hash-pill" style={{ fontSize: '0.6rem' }}>{node.id.slice(0, 20)}</div>
                        </button>
                      ))}
                      {nodes.length > 24 && (
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', alignSelf: 'center' }}>
                          +{nodes.length - 24} more
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Node inspector */}
        <div className="card">
          <div className="card-header"><div className="card-title">Node Inspector</div></div>
          {!selected ? (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Select a node to inspect its metadata.</p>
          ) : (
            <>
              <div style={{ marginBottom: '10px' }}>
                <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>
                  {TYPE_META[selected.type]?.icon} {selected.label}
                </span>
                <div className="hash-pill" style={{ marginTop: '4px' }}>{selected.id}</div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>provenance: {selected.provenance}</div>
              </div>

              {(edgesFor.upstream.length > 0 || edgesFor.downstream.length > 0) && (
                <div style={{ marginBottom: '10px', fontSize: '0.76rem' }}>
                  <div style={{ color: 'var(--text-muted)', fontWeight: 700, marginBottom: '4px' }}>
                    <Link2 size={12} style={{ verticalAlign: '-2px' }} /> Edges
                  </div>
                  {edgesFor.upstream.map((e, i) => (
                    <div key={`u${i}`}>⬅ {labelOf(e.source)} <span style={{ color: 'var(--text-muted)' }}>({e.type})</span></div>
                  ))}
                  {edgesFor.downstream.map((e, i) => (
                    <div key={`d${i}`}>➡ {labelOf(e.target)} <span style={{ color: 'var(--text-muted)' }}>({e.type})</span></div>
                  ))}
                </div>
              )}

              <pre style={{
                background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', padding: '10px',
                fontSize: '0.72rem', overflow: 'auto', maxHeight: '300px', fontFamily: 'monospace',
                color: 'var(--cyan-neon)',
              }}>
                {JSON.stringify(selected.metadata ?? {}, null, 2)}
              </pre>

              {selected.provenance !== 'lineage' && selected.type === 'prediction' && !trust && (
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '8px' }}>
                  No trust checklist available for this prediction.
                </p>
              )}
              <TrustChecklist trust={trust} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
