import React, { useEffect, useState } from 'react';
import { FlaskConical, Play, Plus, Loader2, FileArchive } from 'lucide-react';
import Alert from '../components/common/Alert';
import StatusBadge from '../components/common/StatusBadge';
import { challengesApi } from '../api/research';

const EXPERIMENT_CHOICES = ['EXP-A', 'EXP-B', 'EXP-C', 'EXP-D', 'EXP-E', 'EXP-F', 'EXP-G', 'EXP-H', 'BENCHMARK'];

const EMPTY_SPEC = {
  title: '',
  hypothesis: '',
  experiment: 'EXP-A',
  kind: 'standard',
  n_runs: 3,
};

export default function Challenges() {
  const [presets, setPresets] = useState([]);
  const [list, setList] = useState([]);
  const [spec, setSpec] = useState(EMPTY_SPEC);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);

  const load = async () => {
    try {
      const [p, l] = await Promise.all([challengesApi.presets(), challengesApi.list()]);
      setPresets(p.presets || []);
      setList(l.challenges || []);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => { load(); }, []);

  const runPreset = async (p) => {
    setBusy(p.id);
    setError(null);
    setResult(null);
    try {
      setResult(await challengesApi.run({ preset: p.id }));
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  const runCustom = async () => {
    if (!spec.title.trim() || spec.hypothesis.trim().length < 10) {
      setError('A challenge needs a title and a hypothesis of at least 10 characters.');
      return;
    }
    setBusy('custom');
    setError(null);
    setResult(null);
    try {
      setResult(await challengesApi.run({
        title: spec.title,
        hypothesis: spec.hypothesis,
        experiment: spec.experiment,
        kind: spec.kind,
        n_runs: spec.n_runs,
      }));
      setSpec(EMPTY_SPEC);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  };

  const metricStats = result?.analysis?.metric_stats || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          <FlaskConical size={18} style={{ color: 'var(--cyan-neon)', marginRight: '8px', verticalAlign: '-3px' }} />
          Research Challenges
        </h2>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
          Define a question — SentinelCrypt structures the full investigation: hypothesis → dataset →
          configuration → repeated runs → statistical analysis → results → evidence hash → persisted JSON.
        </p>
      </div>

      {error && <Alert type="danger" title="Challenge Error">{error}</Alert>}

      {/* Presets Q1–Q5 */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Research Questions (Q1–Q5)</div>
          <div className="card-subtitle">One click runs the full structured investigation behind each question</div>
        </div>
        <div className="grid-2" style={{ gap: '12px' }}>
          {presets.map((p) => (
            <div key={p.id} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '14px' }}>
              <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: '4px', color: 'var(--cyan-neon)' }}>
                {p.id}
              </div>
              <div style={{ fontSize: '0.8rem', marginBottom: '6px' }}>{p.question}</div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginBottom: '10px' }}>
                <em>Hypothesis:</em> {p.hypothesis}
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                <span className="badge badge-info">{p.kind}</span>
                <span className="badge badge-neutral">runs {p.experiment}</span>
              </div>
              <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => runPreset(p)} disabled={busy !== null}>
                {busy === p.id ? <Loader2 size={14} className="spinner" /> : <Play size={14} />}
                {busy === p.id ? 'Running…' : 'Run Challenge'}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Custom challenge */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><Plus size={16} /> Define Your Own</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <input
            className="input"
            placeholder="Challenge title — e.g. Does feature dropout degrade explanation stability?"
            value={spec.title}
            onChange={(e) => setSpec({ ...spec, title: e.target.value })}
          />
          <textarea
            className="input"
            rows={2}
            placeholder="Hypothesis — what do you expect and why? (min 10 characters)"
            value={spec.hypothesis}
            onChange={(e) => setSpec({ ...spec, hypothesis: e.target.value })}
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Underlying experiment
              <select className="input" value={spec.experiment} onChange={(e) => setSpec({ ...spec, experiment: e.target.value })}>
                {EXPERIMENT_CHOICES.map((x) => <option key={x} value={x}>{x}</option>)}
              </select>
            </label>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Kind
              <select className="input" value={spec.kind} onChange={(e) => setSpec({ ...spec, kind: e.target.value })}>
                <option value="standard">standard</option>
                <option value="longitudinal">longitudinal</option>
                <option value="reproducibility">reproducibility</option>
              </select>
            </label>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Repeated runs
              <input className="input" type="number" min={1} max={10} value={spec.n_runs}
                onChange={(e) => setSpec({ ...spec, n_runs: parseInt(e.target.value, 10) || 3 })} />
            </label>
          </div>
          <button className="btn btn-primary" onClick={runCustom} disabled={busy !== null}>
            {busy === 'custom' ? <Loader2 size={14} className="spinner" /> : <Play size={14} />}
            {busy === 'custom' ? 'Running…' : 'Run Custom Challenge'}
          </button>
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="card" style={{ borderColor: 'var(--cyan-neon)' }}>
          <div className="card-header">
            <div>
              <div className="card-title" style={{ color: 'var(--cyan-neon)' }}>{result.challenge_id}</div>
              <div className="card-subtitle">{result.title}</div>
            </div>
            <StatusBadge status={result.status === 'COMPLETED' ? 'verified' : 'pending'} label={result.status} />
          </div>

          <div style={{ marginBottom: '12px', fontSize: '0.85rem' }}>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', textTransform: 'uppercase' }}>Hypothesis</div>
            {result.hypothesis}
          </div>

          {result.analysis?.determinism_classification && (
            <Alert type="info" title="Determinism classification">
              {result.analysis.determinism_classification}
            </Alert>
          )}

          {/* Metric statistics across repeated runs */}
          {Object.keys(metricStats).length > 0 && (
            <div className="table-container" style={{ marginTop: '10px' }}>
              <table className="table">
                <thead><tr><th>Metric</th><th>n</th><th>Mean</th><th>σ</th><th>Min</th><th>Max</th><th>95% bootstrap CI</th></tr></thead>
                <tbody>
                  {Object.entries(metricStats).slice(0, 12).map(([path, s]) => (
                    <tr key={path}>
                      <td className="font-mono" style={{ fontSize: '0.72rem' }}>{path}</td>
                      <td>{s.n}</td>
                      <td className="font-mono">{s.mean?.toFixed?.(4) ?? s.mean}</td>
                      <td className="font-mono">{s.std?.toFixed?.(4) ?? s.std}</td>
                      <td className="font-mono">{s.min?.toFixed?.(4) ?? s.min}</td>
                      <td className="font-mono">{s.max?.toFixed?.(4) ?? s.max}</td>
                      <td className="font-mono" style={{ fontSize: '0.72rem' }}>
                        {s.confidence_interval
                          ? `[${s.confidence_interval.low.toFixed(4)}, ${s.confidence_interval.high.toFixed(4)}]`
                          : 'Not estimated'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {result.analysis?.runtime_ms && (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '10px' }}>
              <span className="badge badge-info">Runtime mean {result.analysis.runtime_ms.mean?.toFixed?.(1)} ms</span>
              {result.analysis.drift_slope_per_run !== undefined && (
                <span className="badge badge-purple">Drift slope/run {result.analysis.drift_slope_per_run}</span>
              )}
              {result.analysis.hash_identical_across_runs !== undefined && (
                <span className={`badge ${result.analysis.hash_identical_across_runs ? 'badge-benign' : 'badge-warning'}`}>
                  Result hash {result.analysis.hash_identical_across_runs ? 'identical across runs' : 'differs across runs'}
                </span>
              )}
            </div>
          )}

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '10px', alignItems: 'center' }}>
            <span className="badge badge-benign">Evidence hash {result.evidence_hash?.slice(0, 16)}…</span>
            <span className="badge badge-neutral"><FileArchive size={11} /> {result.persisted_to}</span>
          </div>
        </div>
      )}

      {/* History */}
      <div className="card">
        <div className="card-header"><div className="card-title">Challenge History</div></div>
        {list.length === 0 ? (
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>No challenges run yet.</p>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead><tr><th>ID</th><th>Challenge</th><th>Kind</th><th>Status</th><th>Evidence hash</th></tr></thead>
              <tbody>
                {list.map((c) => (
                  <tr key={c.challenge_id}>
                    <td className="font-mono" style={{ fontSize: '0.72rem' }}>{c.challenge_id}</td>
                    <td style={{ fontSize: '0.78rem' }}>{c.title}</td>
                    <td><span className="badge badge-info">{c.kind}</span></td>
                    <td><StatusBadge status={c.status === 'COMPLETED' ? 'verified' : 'pending'} label={c.status} /></td>
                    <td className="hash-pill">{c.evidence_hash?.slice(0, 12) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
