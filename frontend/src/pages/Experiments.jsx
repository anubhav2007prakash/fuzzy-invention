import React, { useState, useEffect } from 'react';
import { FlaskConical, Play, Download, RefreshCw, BarChart2, Settings2, PackageCheck } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import Alert from '../components/common/Alert';
import TrustProfileBars from '../components/research/TrustProfileBars';
import ReproducibilityPanel from '../components/research/ReproducibilityPanel';
import { experimentsApi } from '../api/experiments';

const EXPERIMENTS_META = [
  {
    id: 'EXP-A',
    title: 'Cross-Dataset Generalization Gap',
    question: 'How significantly does detection accuracy degrade when a model trained on UNSW-NB15 is evaluated on CICIDS2017 distribution?',
    badge: 'EXP-A',
    description: 'Measures transferability and false-positive spikes across heterogeneous network traffic captures.',
  },
  {
    id: 'EXP-B',
    title: 'XAI Attribution Stability under Perturbation',
    question: 'Do local SHAP explanations remain stable (Cosine Similarity > 0.85) under Gaussian noise perturbations (sigma = 0.01 to 0.20)?',
    badge: 'EXP-B',
    description: 'Evaluates robustness of feature rankings when raw telemetry contains minor sensor jitter or packet jitter.',
  },
  {
    id: 'EXP-C',
    title: 'Cryptographic Audit Integrity & Adversarial Attacks',
    question: 'Does the verification engine achieve 100% detection rate of single-bit payload mutations and broken hash chain pointers with exact sequence localization?',
    badge: 'EXP-C',
    description: 'Simulates bit-flip attacks, sequence deletion, and retro-fitting attacks on the SHA-256 forward-linked audit ledger.',
  },
  {
    id: 'EXP-D',
    title: 'Model Architecture & Runtime Overhead Comparison',
    question: 'What is the end-to-end latency overhead of canonicalizing and SHA-256 hash-linking each prediction compared to bare model inference?',
    badge: 'EXP-D',
    description: 'Measures microseconds per inference for bare forward-pass vs canonical JSON serialization vs full hash chain commit.',
  },
];

const DEFAULT_CONFIGS = {
  'EXP-A': { n_samples: 1200, random_state: 42 },
  'EXP-B': { noise_levels: '0.01, 0.05, 0.10, 0.20', n_repetitions: 8, random_state: 42 },
  'EXP-C': { n_blocks: 50, random_state: 42 },
  'EXP-D': { n_samples: 1500, random_state: 42 },
};

function parsePositiveInteger(value, label) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed <= 0) return `${label} must be a positive integer.`;
  return null;
}

function parseInteger(value, label) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed)) return `${label} must be an integer.`;
  return null;
}

function buildConfig(expId, form) {
  const errors = [];
  const config = {};

  if (expId === 'EXP-A' || expId === 'EXP-D') {
    const sampleError = parsePositiveInteger(form.n_samples, 'Sample count');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (sampleError) errors.push(sampleError);
    if (seedError) errors.push(seedError);
    config.n_samples = Number.parseInt(form.n_samples, 10);
    config.random_state = Number.parseInt(form.random_state, 10);
  }

  if (expId === 'EXP-B') {
    const levels = String(form.noise_levels)
      .split(',')
      .map((value) => Number.parseFloat(value.trim()))
      .filter((value) => !Number.isNaN(value));
    if (!levels.length || levels.some((value) => value <= 0)) errors.push('Noise levels must be positive numbers separated by commas.');
    const repetitionError = parsePositiveInteger(form.n_repetitions, 'Repetitions');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (repetitionError) errors.push(repetitionError);
    if (seedError) errors.push(seedError);
    config.noise_levels = levels;
    config.n_repetitions = Number.parseInt(form.n_repetitions, 10);
    config.random_state = Number.parseInt(form.random_state, 10);
  }

  if (expId === 'EXP-C') {
    const blockError = parsePositiveInteger(form.n_blocks, 'Ledger blocks');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (blockError) errors.push(blockError);
    if (seedError) errors.push(seedError);
    config.n_blocks = Number.parseInt(form.n_blocks, 10);
    config.random_state = Number.parseInt(form.random_state, 10);
  }

  return { config, errors };
}

export default function Experiments() {
  const [selectedExpId, setSelectedExpId] = useState('EXP-A');
  const [experimentsData, setExperimentsData] = useState({});
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [configForms, setConfigForms] = useState(DEFAULT_CONFIGS);
  const [validationErrors, setValidationErrors] = useState([]);
  const [evidenceExport, setEvidenceExport] = useState(null);

  const loadAllExperiments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await experimentsApi.list();
      const map = {};
      (res?.experiments || []).forEach((e) => {
        if (e.experiment_id) {
          map[e.experiment_id] = e;
        }
      });
      setExperimentsData(map);
    } catch (err) {
      console.error('Failed to load experiment status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllExperiments();
  }, []);

  const handleRunExperiment = async (expId) => {
    const { config, errors } = buildConfig(expId, configForms[expId]);
    setValidationErrors(errors);
    setEvidenceExport(null);
    if (errors.length) return;

    setRunning(true);
    setError(null);
    try {
      const result = await experimentsApi.run(expId, config);
      setExperimentsData((prev) => ({ ...prev, [expId]: result }));
    } catch (err) {
      setError(err.message || `Failed to run ${expId}.`);
    } finally {
      setRunning(false);
    }
  };

  const handleExportEvidence = async (expId) => {
    const { config, errors } = buildConfig(expId, configForms[expId]);
    setValidationErrors(errors);
    if (errors.length) return;

    setError(null);
    try {
      const exported = await experimentsApi.exportEvidence(expId, config);
      setEvidenceExport(exported);
    } catch (err) {
      setError(err.message || `Failed to export evidence for ${expId}.`);
    }
  };

  const updateConfig = (expId, key, value) => {
    setConfigForms((prev) => ({
      ...prev,
      [expId]: {
        ...prev[expId],
        [key]: value,
      },
    }));
  };

  const selectedMeta = EXPERIMENTS_META.find((m) => m.id === selectedExpId) || EXPERIMENTS_META[0];
  const selectedResult = experimentsData[selectedExpId];
  const isCompleted = selectedResult?.status === 'COMPLETED';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
            Research Lab
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Deterministic scientific experiments evaluating generalization gap, explanation stability, ledger integrity, and runtime overhead.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={loadAllExperiments} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spinner' : ''} /> Refresh
          </button>
          <button
            className="btn btn-primary"
            onClick={() => handleRunExperiment(selectedExpId)}
            disabled={running}
          >
            <Play size={14} className={running ? 'spinner' : ''} />
            {running ? `Executing ${selectedExpId}...` : `Run ${selectedExpId} Live`}
          </button>
        </div>
      </div>

      {error && (
        <Alert type="danger" title="Experiment Execution Error">
          {error}
        </Alert>
      )}

      <div className="grid-2" style={{ gridTemplateColumns: '1.1fr 1.3fr', alignItems: 'start' }}>
        {/* Left: Experiment Selection Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {EXPERIMENTS_META.map((meta) => {
            const isSelected = selectedExpId === meta.id;
            const res = experimentsData[meta.id];
            const hasRun = res?.status === 'COMPLETED';

            return (
              <div
                key={meta.id}
                className="card"
                onClick={() => setSelectedExpId(meta.id)}
                style={{
                  cursor: 'pointer',
                  borderColor: isSelected ? 'var(--cyan-neon)' : undefined,
                  background: isSelected ? 'rgba(0, 242, 254, 0.06)' : undefined,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span className="badge badge-purple">{meta.badge}</span>
                  <StatusBadge
                    status={hasRun ? 'success' : 'pending'}
                    label={hasRun ? 'Results Available' : 'Ready to Run'}
                  />
                </div>

                <div style={{ fontWeight: '700', fontSize: '0.95rem', color: isSelected ? 'var(--cyan-neon)' : 'var(--text-primary)', marginBottom: '4px' }}>
                  {meta.title}
                </div>

                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                  {meta.description}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: Live Experiment Telemetry & Results View */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title" style={{ color: 'var(--cyan-neon)' }}>
                {selectedMeta.badge}: {selectedMeta.title}
              </div>
              <div className="card-subtitle">
                Scientific Protocol & Quantitative Measurements
              </div>
            </div>
            {isCompleted && <StatusBadge status="verified" label="Validated" />}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Research Question */}
            <div>
              <div style={{ fontSize: '0.72rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
                Research Question:
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontStyle: 'italic', background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                "{selectedMeta.question}"
              </div>
            </div>

            {/* Experiment Configuration */}
            <div className="card" style={{ background: 'var(--bg-surface)', padding: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--text-primary)', fontWeight: 700 }}>
                <Settings2 size={16} style={{ color: 'var(--cyan-neon)' }} />
                Experiment Configuration
              </div>

              <div className="grid-2">
                {(selectedExpId === 'EXP-A' || selectedExpId === 'EXP-D') && (
                  <div className="form-group">
                    <label className="form-label">Samples</label>
                    <input className="form-input" type="number" min="1" value={configForms[selectedExpId].n_samples} onChange={(e) => updateConfig(selectedExpId, 'n_samples', e.target.value)} />
                  </div>
                )}
                {selectedExpId === 'EXP-B' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Noise Levels</label>
                      <input className="form-input" value={configForms[selectedExpId].noise_levels} onChange={(e) => updateConfig(selectedExpId, 'noise_levels', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Repetitions</label>
                      <input className="form-input" type="number" min="1" value={configForms[selectedExpId].n_repetitions} onChange={(e) => updateConfig(selectedExpId, 'n_repetitions', e.target.value)} />
                    </div>
                  </>
                )}
                {selectedExpId === 'EXP-C' && (
                  <div className="form-group">
                    <label className="form-label">Ledger Blocks</label>
                    <input className="form-input" type="number" min="1" value={configForms[selectedExpId].n_blocks} onChange={(e) => updateConfig(selectedExpId, 'n_blocks', e.target.value)} />
                  </div>
                )}
                <div className="form-group">
                  <label className="form-label">Seed</label>
                  <input className="form-input" type="number" value={configForms[selectedExpId].random_state} onChange={(e) => updateConfig(selectedExpId, 'random_state', e.target.value)} />
                </div>
              </div>

              {validationErrors.length > 0 && (
                <Alert type="warning" title="Invalid configuration">
                  {validationErrors.join(' ')}
                </Alert>
              )}
            </div>

            {/* Results Details according to Experiment Type */}
            {isCompleted ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ fontWeight: '600', fontSize: '0.85rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <BarChart2 size={16} style={{ color: 'var(--cyan-neon)' }} />
                  Quantitative Results (Persisted to results/)
                </div>

                {/* EXP-A Specific View */}
                {selectedExpId === 'EXP-A' && selectedResult.metrics && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div className="grid-2">
                      <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>In-Distribution F1</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--status-benign)', fontFamily: 'monospace' }}>
                          {(selectedResult.metrics.in_distribution?.f1_score * 100).toFixed(2)}%
                        </div>
                      </div>
                      <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Out-of-Distribution F1</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--status-warning)', fontFamily: 'monospace' }}>
                          {(selectedResult.metrics.out_of_distribution?.f1_score * 100).toFixed(2)}%
                        </div>
                      </div>
                    </div>

                    <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem' }}>
                      <span style={{ fontWeight: '600', color: 'var(--cyan-neon)' }}>Generalization Gap (Delta F1): </span>
                      <span style={{ fontFamily: 'monospace', fontWeight: '700' }}>
                        {(selectedResult.metrics.generalization_gap?.delta_f1 * 100).toFixed(2)}%
                      </span>
                    </div>
                  </div>
                )}

                {/* EXP-B Specific View */}
                {selectedExpId === 'EXP-B' && selectedResult.metrics && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Overall Mean Cosine Stability</div>
                      <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--status-benign)', fontFamily: 'monospace' }}>
                        {selectedResult.metrics.overall_mean_stability?.toFixed(4)}
                      </div>
                    </div>

                    <div className="table-container">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Noise (sigma)</th>
                            <th>Cosine Stability</th>
                            <th>Std Dev</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedResult.metrics.stability_curve || []).map((row, i) => (
                            <tr key={i}>
                              <td style={{ fontFamily: 'monospace' }}>{row.noise_std}</td>
                              <td style={{ fontFamily: 'monospace', color: 'var(--cyan-neon)' }}>{row.stability_score?.toFixed(4)}</td>
                              <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{row.std?.toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* EXP-C Specific View */}
                {selectedExpId === 'EXP-C' && selectedResult.metrics && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div className="grid-2">
                      <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Clean Chain Verification</div>
                        <div style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--status-benign)' }}>
                          {selectedResult.metrics.clean_chain_valid ? 'VALID (0 Corruptions)' : 'FAILED'}
                        </div>
                      </div>
                      <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Tamper Detection Rate</div>
                        <div style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--cyan-neon)', fontFamily: 'monospace' }}>
                          {selectedResult.metrics.tamper_detection_rate}
                        </div>
                      </div>
                    </div>

                    <div className="table-container">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Adversarial Attack</th>
                            <th>Sequence</th>
                            <th>Detected</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedResult.metrics.attacks_simulated || []).map((a, i) => (
                            <tr key={i}>
                              <td style={{ fontSize: '0.75rem' }}>{a.attack_type}</td>
                              <td style={{ fontFamily: 'monospace' }}>#{a.tampered_sequence}</td>
                              <td>{a.detected ? 'YES' : 'NO'}</td>
                              <td><StatusBadge status="verified" label={a.status} /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* EXP-D Specific View */}
                {selectedExpId === 'EXP-D' && selectedResult.comparison && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div className="table-container">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Metric</th>
                            <th>Logistic Regression</th>
                            <th>Random Forest</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>Accuracy</td>
                            <td style={{ fontFamily: 'monospace' }}>{(selectedResult.comparison.logistic_regression?.accuracy * 100).toFixed(2)}%</td>
                            <td style={{ fontFamily: 'monospace', color: 'var(--cyan-neon)' }}>{(selectedResult.comparison.random_forest?.accuracy * 100).toFixed(2)}%</td>
                          </tr>
                          <tr>
                            <td>F1-Score</td>
                            <td style={{ fontFamily: 'monospace' }}>{(selectedResult.comparison.logistic_regression?.f1_score * 100).toFixed(2)}%</td>
                            <td style={{ fontFamily: 'monospace', color: 'var(--cyan-neon)' }}>{(selectedResult.comparison.random_forest?.f1_score * 100).toFixed(2)}%</td>
                          </tr>
                          <tr>
                            <td>Inference Latency</td>
                            <td style={{ fontFamily: 'monospace' }}>{selectedResult.comparison.logistic_regression?.inference_time_us?.toFixed(1)} us</td>
                            <td style={{ fontFamily: 'monospace' }}>{selectedResult.comparison.random_forest?.inference_time_us?.toFixed(1)} us</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem' }}>
                      Cryptographic Anchoring Overhead: <strong className="font-mono" style={{ color: 'var(--cyan-neon)' }}>{selectedResult.comparison.cryptographic_overhead?.canonicalization_and_sha256_us} us/sample</strong> ({selectedResult.comparison.cryptographic_overhead?.relative_overhead_pct})
                    </div>
                  </div>
                )}

                {/* Model Trust Profile */}
                {selectedResult?.trust_profile && (
                  <TrustProfileBars dimensions={selectedResult.trust_profile} />
                )}

                {/* Reproducibility Manifest */}
                {selectedResult?.run_manifest && (
                  <ReproducibilityPanel result={selectedResult} />
                )}

                {/* Evidence Package */}
                {selectedResult?.run_manifest && (
                  <div className="card" style={{ background: 'var(--bg-surface)' }}>
                    <div className="card-header">
                      <div>
                        <div className="card-title">
                          <PackageCheck size={16} style={{ color: 'var(--cyan-neon)' }} />
                          Evidence Package
                        </div>
                        <div className="card-subtitle">Export structured evidence for independent inspection</div>
                      </div>
                      <button className="btn btn-secondary" onClick={() => handleExportEvidence(selectedExpId)}>
                        <Download size={14} />
                        Export Evidence
                      </button>
                    </div>
                    {evidenceExport && evidenceExport.experiment_id === selectedExpId && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem' }}>
                        <div>Package Path: <span className="hash-pill">{evidenceExport.package_path}</span></div>
                        <div>Package Hash: <span className="hash-pill">{evidenceExport.package_hash}</span></div>
                        <div>Files: {evidenceExport.files.join(', ')}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '32px 16px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                <FlaskConical size={32} style={{ color: 'var(--cyan-neon)', margin: '0 auto 12px auto', opacity: 0.7 }} />
                <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Experiment Not Yet Executed
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
                  Click the button below to launch automated reproducible benchmark runner.
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => handleRunExperiment(selectedExpId)}
                  disabled={running}
                >
                  <Play size={14} className={running ? 'spinner' : ''} />
                  {running ? `Executing ${selectedExpId}...` : `Run ${selectedExpId} Benchmark`}
                </button>
              </div>
            )}

            <Alert type="info">
              Research Lab v1 uses deterministic experiment configurations, canonical SHA-256 result hashes, and reproducibility manifests. Current benchmark datasets are synthetic unless a manifest states otherwise.
            </Alert>
          </div>
        </div>
      </div>
    </div>
  );
}
