import React, { useEffect, useState } from 'react';
import { Gauge, Play, RefreshCw, Timer, TrendingUp, Trophy, Loader2 } from 'lucide-react';
import Alert from '../components/common/Alert';
import StatusBadge from '../components/common/StatusBadge';
import { benchmarkApi } from '../api/research';

function MetricTile({ label, value, unit = '', accent }) {
  return (
    <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: '2px' }}>{label}</div>
      <div style={{ fontSize: '1.15rem', fontWeight: 700, fontFamily: 'monospace', color: accent || 'var(--cyan-neon)' }}>
        {value === null || value === undefined ? '—' : `${value}${unit}`}
      </div>
    </div>
  );
}

export default function Benchmark() {
  const [sources, setSources] = useState([]);
  const [report, setReport] = useState(null);
  const [pipeline, setPipeline] = useState(null);
  const [scalability, setScalability] = useState(null);
  const [leaderboard, setLeaderboard] = useState(null);
  const [running, setRunning] = useState(null);
  const [error, setError] = useState(null);

  const loadStatic = async () => {
    try {
      const [src, board] = await Promise.all([
        benchmarkApi.sources(),
        benchmarkApi.leaderboard(),
      ]);
      setSources(src.sources || []);
      setLeaderboard(board);
    } catch (err) {
      setError(err.message);
    }
    try {
      setReport(await benchmarkApi.report());
    } catch {
      setReport(null); // no report yet — not an error state
    }
  };

  useEffect(() => { loadStatic(); }, []);

  const runFull = async () => {
    setRunning('protocol');
    setError(null);
    try {
      setReport(await benchmarkApi.run({ n_samples: 1200, repeats: 2 }));
      setLeaderboard(await benchmarkApi.leaderboard());
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(null);
    }
  };

  const runPipeline = async () => {
    setRunning('pipeline');
    setError(null);
    try {
      setPipeline(await benchmarkApi.pipeline({ n_samples: 600 }));
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(null);
    }
  };

  const runScalability = async () => {
    setRunning('scalability');
    setError(null);
    try {
      setScalability(await benchmarkApi.scalability({ sizes: [10000, 50000, 100000] }));
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            <Gauge size={18} style={{ color: 'var(--cyan-neon)', marginRight: '8px', verticalAlign: '-3px' }} />
            SentinelCrypt Benchmark
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            One standardized protocol across UNSW-NB15, CICIDS2017, and controlled test data —
            detection, calibration, latency, memory, stability, OOD, ledger overhead, reproducibility.
          </p>
        </div>
        <button className="btn btn-primary" onClick={runFull} disabled={running !== null}>
          {running === 'protocol' ? <Loader2 size={14} className="spinner" /> : <Play size={14} />}
          {running === 'protocol' ? 'Running protocol…' : 'Run Benchmark Protocol'}
        </button>
      </div>

      {error && <Alert type="danger" title="Benchmark Error">{error}</Alert>}

      {/* Data sources with honest provenance */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Data Sources &amp; Provenance</div>
          <div className="card-subtitle">Proxy sources are labelled synthetic — never presented as real captures</div>
        </div>
        <div className="table-container">
          <table className="table">
            <thead><tr><th>Key</th><th>Label</th><th>Origin</th><th>Note</th></tr></thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.key}>
                  <td className="font-mono">{s.key}</td>
                  <td>{s.label}</td>
                  <td><StatusBadge status={s.origin === 'uploaded' ? 'verified' : 'pending'} label={s.origin} /></td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{s.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Report */}
      {report && (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title" style={{ color: 'var(--cyan-neon)' }}>{report.benchmark_id}</div>
              <div className="card-subtitle">
                Seed {report.protocol?.seed} · repeats {report.protocol?.repeats} · hash <span className="hash-pill">{report.report_hash?.slice(0, 16)}…</span>
              </div>
            </div>
            <StatusBadge status="verified" label="Report ready" />
          </div>

          {(report.sources || []).map((row) => {
            const ind = row.in_distribution || {};
            return (
              <div key={row.source} style={{ marginBottom: '14px' }}>
                <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: '8px' }}>{row.provenance?.name}</div>
                <div className="grid-2" style={{ gap: '10px' }}>
                  <MetricTile label="F1" value={ind.f1 != null ? ind.f1.toFixed(4) : null} accent="var(--status-benign)" />
                  <MetricTile label="Macro-F1" value={ind.f1_macro != null ? ind.f1_macro.toFixed(4) : null} />
                  <MetricTile label="PR-AUC" value={ind.pr_auc != null ? ind.pr_auc.toFixed(4) : null} />
                  <MetricTile label="ECE (calibration)" value={ind.ece != null ? ind.ece.toFixed(4) : null} accent="var(--status-warning)" />
                  <MetricTile label="Precision" value={ind.precision != null ? ind.precision.toFixed(4) : null} />
                  <MetricTile label="Recall" value={ind.recall != null ? ind.recall.toFixed(4) : null} />
                  <MetricTile label="Latency (ms/row)" value={ind.inference_latency_ms != null ? ind.inference_latency_ms.toFixed(4) : null} />
                  <MetricTile label="Peak mem (MB)" value={ind.train_peak_memory_mb} accent="var(--purple-accent)" />
                  <MetricTile label="XAI stability" value={ind.explanation_stability != null ? ind.explanation_stability.toFixed(4) : null} />
                  <MetricTile label="OOD ΔF1" value={row.generalization_gap?.delta_f1 != null ? row.generalization_gap.delta_f1.toFixed(4) : null} accent="var(--status-attack)" />
                  <MetricTile label="Ledger verify (µs/blk)" value={row.ledger_overhead?.verify_us_per_block} />
                  <MetricTile label="F1 spread (reruns)" value={row.reproducibility?.f1_spread} accent="var(--status-benign)" />
                </div>
                {row.reproducibility?.bit_identical_across_runs && (
                  <div style={{ fontSize: '0.74rem', color: 'var(--status-benign)', marginTop: '6px' }}>
                    ✓ deterministic reruns: quality metrics bit-identical across {row.reproducibility.repeats} repeats
                  </div>
                )}
              </div>
            );
          })}
          <Alert type="info">
            Report persisted to <span className="hash-pill">results/reports/benchmark_latest.md</span> — machine-generated Markdown table included.
          </Alert>
        </div>
      )}

      {/* Pipeline timing */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title"><Timer size={16} style={{ color: 'var(--cyan-neon)' }} /> Pipeline Stage Latency</div>
            <div className="card-subtitle">End-to-end cost of XAI + cryptographic evidence</div>
          </div>
          <button className="btn btn-secondary" onClick={runPipeline} disabled={running !== null}>
            {running === 'pipeline' ? <Loader2 size={14} className="spinner" /> : <Play size={14} />} Measure
          </button>
        </div>
        {pipeline && (
          <>
            <div className="table-container">
              <table className="table">
                <thead><tr><th>Stage</th><th>Latency (ms)</th><th>Share</th></tr></thead>
                <tbody>
                  {Object.entries(pipeline.stages_ms || {}).map(([stage, ms]) => (
                    <tr key={stage}>
                      <td className="font-mono">{stage}</td>
                      <td className="font-mono">{ms?.toFixed(3)}</td>
                      <td>
                        <div style={{ background: 'var(--bg-input)', borderRadius: '999px', height: '8px', overflow: 'hidden' }}>
                          <div style={{ width: `${Math.min(100, (ms / (pipeline.end_to_end_ms || 1)) * 100)}%`, height: '100%', background: 'linear-gradient(90deg, var(--cyan-neon), var(--status-benign))' }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '10px' }}>
              <span className="badge badge-info">End-to-end: {pipeline.end_to_end_ms?.toFixed(2)} ms</span>
              <span className="badge badge-purple">XAI overhead: {pipeline.xai_overhead_pct}%</span>
              <span className="badge badge-benign">Crypto overhead: {pipeline.crypto_overhead_pct}%</span>
            </div>
          </>
        )}
      </div>

      {/* Scalability */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title"><TrendingUp size={16} style={{ color: 'var(--cyan-neon)' }} /> Scalability Sweep</div>
            <div className="card-subtitle">Training time, throughput, memory, explanation &amp; ledger cost vs data size</div>
          </div>
          <button className="btn btn-secondary" onClick={runScalability} disabled={running !== null}>
            {running === 'scalability' ? <Loader2 size={14} className="spinner" /> : <Play size={14} />} Run sweep
          </button>
        </div>
        {scalability && (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr><th>Samples</th><th>Train (s)</th><th>Throughput (rows/s)</th><th>Peak mem (MB)</th><th>SHAP (ms)</th><th>Ledger (µs/blk)</th><th>DB (bytes)</th></tr>
              </thead>
              <tbody>
                {(scalability.points || []).map((p) => (
                  <tr key={p.n_samples}>
                    <td className="font-mono">{p.n_samples.toLocaleString()}</td>
                    <td className="font-mono">{p.train_time_s}</td>
                    <td className="font-mono">{p.predict_throughput_rows_per_s?.toLocaleString()}</td>
                    <td className="font-mono">{p.peak_memory_mb}</td>
                    <td className="font-mono">{p.explanation_time_ms ?? '—'}</td>
                    <td className="font-mono">{p.ledger_verify_us_per_block}</td>
                    <td className="font-mono">{p.db_size_bytes_projected?.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Leaderboard */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title"><Trophy size={16} style={{ color: 'var(--cyan-neon)' }} /> Experimental Leaderboard</div>
            <div className="card-subtitle">Transparent table of measured runs — not a universal "best model" claim</div>
          </div>
          <button className="btn btn-secondary" onClick={loadStatic}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
        {leaderboard && (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr><th>Experiment</th><th>Dataset</th><th>Model</th><th>F1</th><th>Latency (µs)</th><th>XAI stability</th></tr>
              </thead>
              <tbody>
                {(leaderboard.rows || []).map((row, i) => (
                  <tr key={`${row.experiment}-${i}`}>
                    <td className="font-mono">{row.experiment}</td>
                    <td style={{ fontSize: '0.78rem' }}>{row.dataset}</td>
                    <td className="font-mono">{row.model ?? '—'}</td>
                    <td className="font-mono">{row.f1 != null ? row.f1.toFixed(4) : '—'}</td>
                    <td className="font-mono">{row.latency_us ?? '—'}</td>
                    <td className="font-mono">{row.xai_stability != null ? row.xai_stability.toFixed(4) : '—'}</td>
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
