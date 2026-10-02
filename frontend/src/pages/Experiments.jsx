import React, { useState, useEffect } from 'react';
import { FlaskConical, Play, Download, RefreshCw, BarChart2, Settings2, PackageCheck } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import Alert from '../components/common/Alert';
import TrustProfileBars from '../components/research/TrustProfileBars';
import ReproducibilityPanel from '../components/research/ReproducibilityPanel';
import ReliabilityDiagram from '../components/charts/ReliabilityDiagram';
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
  {
    id: 'EXP-F',
    title: 'Component Ablation Study',
    question: 'Which components actually contribute what — what happens to detection quality, calibration, and latency when XAI, evidence, preprocessing, or calibration is removed?',
    badge: 'EXP-F',
    description: 'Paired A–E comparison of ML, XAI, cryptographic evidence, and experiment provenance, including quality and system costs.',
  },
  {
    id: 'EXP-G',
    title: 'Cryptographic Integrity Architecture Comparison',
    question: 'Hash chain vs Merkle tree: full-verify time, membership-proof cost, storage overhead, and tamper detection at increasing payload counts.',
    badge: 'EXP-G',
    description: 'Head-to-head integrity architecture measurement on identical canonical payloads, with scaling exponents across a size ladder.',
  },
  {
    id: 'EXP-H',
    title: 'Cross-Method Explanation Agreement',
    question: 'Do SHAP, permutation, and built-in importances agree on the same features — and does that agreement survive noise?',
    badge: 'EXP-H',
    description: 'Agreement matrix (top-k overlap, Spearman, consensus ranking) across explanation methods, optionally repeated under noise levels.',
  },
  {
    id: 'EXP-ROBUSTNESS',
    title: 'Bounded-Perturbation Sensitivity',
    question: 'How do predictions, confidence, explanations, and holdout metrics change under bounded synthetic feature perturbations?',
    badge: 'EXP-ROBUSTNESS',
    description: 'Offline sensitivity measurements on controlled synthetic data; results are not a robustness guarantee.',
  },
  {
    id: 'EXP-CALIBRATION',
    title: 'Prediction Probability Calibration Laboratory',
    question: 'Do predicted positive-class probabilities correspond to observed positive frequencies on an untouched test partition, and how do Brier score and ECE change after post-hoc calibration?',
    badge: 'EXP-CALIBRATION',
    description: 'Compares raw and calibrated probabilities on the same held-out synthetic observations; not a real-world calibration guarantee.',
  },
];

const DEFAULT_CONFIGS = {
  'EXP-A': { n_samples: 1200, random_state: 42 },
  'EXP-B': { noise_levels: '0.01, 0.05, 0.10, 0.20', n_repetitions: 8, random_state: 42 },
  'EXP-C': { n_blocks: 50, random_state: 42 },
  'EXP-D': { n_samples: 1500, random_state: 42 },
  'EXP-F': { n_samples: 1200, random_state: 42 },
  'EXP-G': { sizes: '100, 500, 2000', random_state: 42 },
  'EXP-H': { n_samples: 800, top_k: 5, noise_levels: '0.0, 0.05, 0.10', random_state: 42 },
  'EXP-ROBUSTNESS': {
    n_samples: 500,
    n_probe: 6,
    epsilon_levels: '0.02, 0.05, 0.10',
    n_repeats: 2,
    model_type: 'random_forest',
    with_explanations: true,
    random_state: 42,
  },
  'EXP-CALIBRATION': { n_samples: 1200, method: 'sigmoid', random_state: 42 },
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

  if (expId === 'EXP-F' || expId === 'EXP-H') {
    const sampleError = parsePositiveInteger(form.n_samples, 'Sample count');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (sampleError) errors.push(sampleError);
    if (seedError) errors.push(seedError);
    config.n_samples = Number.parseInt(form.n_samples, 10);
    config.random_state = Number.parseInt(form.random_state, 10);
  }

  if (expId === 'EXP-H') {
    const topKError = parsePositiveInteger(form.top_k, 'Top-K');
    if (topKError) errors.push(topKError);
    config.top_k = Number.parseInt(form.top_k, 10);
    const levels = String(form.noise_levels || '')
      .split(',')
      .map((value) => Number.parseFloat(value.trim()))
      .filter((value) => !Number.isNaN(value) && value >= 0);
    if (levels.length) config.noise_levels = levels;
  }

  if (expId === 'EXP-ROBUSTNESS') {
    const sampleError = parsePositiveInteger(form.n_samples, 'Sample count');
    const probeError = parsePositiveInteger(form.n_probe, 'Probe count');
    const repeatError = parsePositiveInteger(form.n_repeats, 'Repeats');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (sampleError) errors.push(sampleError);
    if (probeError) errors.push(probeError);
    if (repeatError) errors.push(repeatError);
    if (seedError) errors.push(seedError);
    config.n_samples = Number.parseInt(form.n_samples, 10);
    config.n_probe = Number.parseInt(form.n_probe, 10);
    config.n_repeats = Number.parseInt(form.n_repeats, 10);
    config.random_state = Number.parseInt(form.random_state, 10);
    const levelInputs = String(form.epsilon_levels || '').split(',');
    const levels = levelInputs.map((value) => Number.parseFloat(value.trim()));
    if (!levels.length || levels.some((value) => !Number.isFinite(value) || value <= 0 || value > 0.2)) {
      errors.push('Epsilon levels must be unique numbers greater than 0 and at most 0.20.');
    } else if (new Set(levels).size !== levels.length) {
      errors.push('Epsilon levels must be unique numbers greater than 0 and at most 0.20.');
    }
    config.epsilon_levels = levels;
    config.model_type = form.model_type;
    config.with_explanations = Boolean(form.with_explanations);
  }

  if (expId === 'EXP-CALIBRATION') {
    const sampleError = parsePositiveInteger(form.n_samples, 'Sample count');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (sampleError || Number.parseInt(form.n_samples, 10) < 400 || Number.parseInt(form.n_samples, 10) > 20000) {
      errors.push('Sample count must be between 400 and 20,000.');
    }
    if (seedError) errors.push(seedError);
    if (!['sigmoid', 'isotonic'].includes(form.method)) errors.push('Choose sigmoid or isotonic calibration.');
    config.n_samples = Number.parseInt(form.n_samples, 10);
    config.method = form.method;
    config.random_state = Number.parseInt(form.random_state, 10);
  }

  if (expId === 'EXP-G') {
    const sizes = String(form.sizes)
      .split(',')
      .map((value) => Number.parseInt(value.trim(), 10))
      .filter((value) => Number.isInteger(value) && value > 0);
    if (!sizes.length) errors.push('Sizes must be positive integers separated by commas.');
    const seedError = parseInteger(form.random_state, 'Seed');
    if (seedError) errors.push(seedError);
    config.sizes = sizes;
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
                    <input className="form-input" type="number" min={selectedExpId === 'EXP-CALIBRATION' ? '400' : '1'} max={selectedExpId === 'EXP-CALIBRATION' ? '20000' : undefined} value={configForms[selectedExpId].n_samples} onChange={(e) => updateConfig(selectedExpId, 'n_samples', e.target.value)} />
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
                {(selectedExpId === 'EXP-F' || selectedExpId === 'EXP-H' || selectedExpId === 'EXP-ROBUSTNESS' || selectedExpId === 'EXP-CALIBRATION') && (
                  <div className="form-group">
                    <label className="form-label">Samples</label>
                    <input className="form-input" type="number" min="1" value={configForms[selectedExpId].n_samples} onChange={(e) => updateConfig(selectedExpId, 'n_samples', e.target.value)} />
                  </div>
                )}
                {selectedExpId === 'EXP-H' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Top-K Features</label>
                      <input className="form-input" type="number" min="1" value={configForms[selectedExpId].top_k} onChange={(e) => updateConfig(selectedExpId, 'top_k', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Noise Levels</label>
                      <input className="form-input" value={configForms[selectedExpId].noise_levels} onChange={(e) => updateConfig(selectedExpId, 'noise_levels', e.target.value)} />
                    </div>
                  </>
                )}
                {selectedExpId === 'EXP-ROBUSTNESS' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Probe Samples</label>
                      <input className="form-input" type="number" min="1" max="100" value={configForms[selectedExpId].n_probe} onChange={(e) => updateConfig(selectedExpId, 'n_probe', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Repeats</label>
                      <input className="form-input" type="number" min="1" max="10" value={configForms[selectedExpId].n_repeats} onChange={(e) => updateConfig(selectedExpId, 'n_repeats', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Epsilon Levels (max 0.20)</label>
                      <input className="form-input" value={configForms[selectedExpId].epsilon_levels} onChange={(e) => updateConfig(selectedExpId, 'epsilon_levels', e.target.value)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Model</label>
                      <select className="form-input" value={configForms[selectedExpId].model_type} onChange={(e) => updateConfig(selectedExpId, 'model_type', e.target.value)}>
                        <option value="random_forest">Random Forest</option>
                        <option value="logistic_regression">Logistic Regression</option>
                      </select>
                    </div>
                    <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <input type="checkbox" checked={configForms[selectedExpId].with_explanations} onChange={(e) => updateConfig(selectedExpId, 'with_explanations', e.target.checked)} />
                      Measure explanation stability
                    </label>
                  </>
                )}
                {selectedExpId === 'EXP-CALIBRATION' && (
                  <div className="form-group">
                    <label className="form-label">Calibration Method</label>
                    <select className="form-input" value={configForms[selectedExpId].method} onChange={(e) => updateConfig(selectedExpId, 'method', e.target.value)}>
                      <option value="sigmoid">Sigmoid (Platt scaling)</option>
                      <option value="isotonic">Isotonic (requires ≥1,000 calibration rows)</option>
                    </select>
                  </div>
                )}
                {selectedExpId === 'EXP-G' && (
                  <div className="form-group">
                    <label className="form-label">Payload-Count Sizes (comma-separated)</label>
                    <input className="form-input" value={configForms[selectedExpId].sizes} onChange={(e) => updateConfig(selectedExpId, 'sizes', e.target.value)} />
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

                {/* EXP-F Specific View — ablation */}
                {selectedExpId === 'EXP-F' && selectedResult.metrics?.variants && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div className="table-container">
                      <table className="table">
                        <thead>
                          <tr><th>Variant</th><th>Precision</th><th>Recall</th><th>F1</th><th>Macro-F1</th><th>PR-AUC</th><th>ΔF1 vs A</th><th>Inference ms/sample</th><th>XAI ms/sample</th><th>Evidence gen ms</th><th>Lineage gen ms</th><th>Verification ms</th><th>Traced peak MB</th><th>Storage bytes</th></tr>
                        </thead>
                        <tbody>
                          {Object.entries(selectedResult.metrics.variants).map(([name, v]) => (
                            <tr key={name} style={name === 'E' || name === 'full' ? { background: 'rgba(0, 242, 254, 0.06)' } : undefined}>
                              <td className="font-mono">{v.name || name}</td>
                              <td className="font-mono">{v.metrics?.precision?.toFixed(4) ?? '—'}</td>
                              <td className="font-mono">{v.metrics?.recall?.toFixed(4) ?? '—'}</td>
                              <td className="font-mono">{v.metrics?.f1?.toFixed(4)}</td>
                              <td className="font-mono">{v.metrics?.f1_macro?.toFixed(4)}</td>
                              <td className="font-mono">{v.metrics?.pr_auc?.toFixed(4) ?? '—'}</td>
                              <td className="font-mono">{name === 'A' ? '—' : selectedResult.metrics.deltas_vs_A?.[name]?.f1?.toFixed(4)}</td>
                              <td className="font-mono">{v.performance?.inference_latency_ms_per_sample?.mean?.toFixed(4) ?? '—'}</td>
                              <td className="font-mono">{v.performance?.explanation_latency_ms_per_sample?.mean?.toFixed(4) ?? '—'}</td>
                              <td className="font-mono">{v.performance?.evidence_generation_latency_ms?.mean?.toFixed(2) ?? '—'}</td>
                              <td className="font-mono">{v.performance?.lineage_generation_latency_ms?.mean?.toFixed(2) ?? '—'}</td>
                              <td className="font-mono">{v.performance?.verification_latency_ms?.mean?.toFixed(2) ?? '—'}</td>
                              <td className="font-mono">{v.performance?.peak_traced_memory_mb?.mean?.toFixed(4) ?? '—'}</td>
                              <td className="font-mono">{v.performance?.storage_bytes?.mean?.toFixed(0) ?? '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem' }}>
                      Paired A–E study: predictive metrics use the same fitted model and held-out predictions within each run. XAI/evidence costs are measured separately; blank latency fields mean that component is not included in that arm.
                    </div>
                    {Object.keys(selectedResult.metrics.errors || {}).length > 0 && (
                      <Alert type="warning" title="Some variants could not run">
                        {Object.entries(selectedResult.metrics.errors).map(([k, v]) => `${k}: ${v}`).join(' · ')}
                      </Alert>
                    )}
                  </div>
                )}

                {/* EXP-G Specific View — chain vs Merkle */}
                {selectedExpId === 'EXP-G' && selectedResult.metrics?.points && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div className="table-container">
                      <table className="table">
                        <thead>
                          <tr><th>Payloads</th><th>Chain verify (ms)</th><th>Merkle verify (ms)</th><th>Chain proof (ms)</th><th>Merkle proof (ms)</th><th>Storage M/C</th></tr>
                        </thead>
                        <tbody>
                          {selectedResult.metrics.points.map((p) => (
                            <tr key={p.n_payloads}>
                              <td className="font-mono">{p.n_payloads}</td>
                              <td className="font-mono">{p.chain?.verify_ms?.toFixed(3)}</td>
                              <td className="font-mono" style={{ color: 'var(--cyan-neon)' }}>{p.merkle?.verify_ms?.toFixed(3)}</td>
                              <td className="font-mono">{p.chain?.membership_proof_ms?.toFixed(3)}</td>
                              <td className="font-mono">{p.merkle?.membership_proof_ms?.toFixed(4)}</td>
                              <td className="font-mono">{p.verdict?.storage_ratio_merkle_over_chain}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {Object.entries(selectedResult.metrics.scaling_exponents || {}).map(([k, v]) => (
                        <span key={k} className="badge badge-info">{k}: {v}</span>
                      ))}
                      <span className={`badge ${selectedResult.metrics.tamper_detection?.mutation_all_sizes ? 'badge-benign' : 'badge-attack'}`}>
                        Mutation detection: {selectedResult.metrics.tamper_detection?.mutation_all_sizes ? 'all sizes' : 'GAP'}
                      </span>
                    </div>
                    <Alert type="info">{selectedResult.metrics.interpretation}</Alert>
                  </div>
                )}

                {/* EXP-H Specific View — agreement matrix */}
                {selectedExpId === 'EXP-H' && selectedResult.metrics?.clean_agreement && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div className="grid-2">
                      <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Mean Top-K Overlap (clean)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--status-benign)', fontFamily: 'monospace' }}>
                          {selectedResult.metrics.clean_agreement.mean_topk_overlap?.toFixed(4)}
                        </div>
                      </div>
                      <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Mean Spearman ρ (clean)</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--cyan-neon)', fontFamily: 'monospace' }}>
                          {selectedResult.metrics.clean_agreement.mean_spearman?.toFixed(4)}
                        </div>
                      </div>
                    </div>
                    <div className="table-container">
                      <table className="table">
                        <thead><tr><th>Method pair</th><th>Top-K overlap</th><th>Spearman ρ</th></tr></thead>
                        <tbody>
                          {(selectedResult.metrics.clean_agreement.pairs || []).map((p) => (
                            <tr key={p.pair}>
                              <td className="font-mono">{p.pair}</td>
                              <td className="font-mono">{p.topk_overlap?.toFixed(4)}</td>
                              <td className="font-mono">{p.spearman?.toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {(selectedResult.metrics.clean_agreement.consensus_ranking || []).map((f, i) => (
                        <span key={f} className="badge badge-purple">#{i + 1} {f}</span>
                      ))}
                    </div>
                    {selectedResult.metrics.interpretation && <Alert type="info">{selectedResult.metrics.interpretation}</Alert>}
                  </div>
                )}

                {selectedExpId === 'EXP-ROBUSTNESS' && selectedResult.metrics?.conditions && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div className="table-container">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Epsilon</th>
                            <th>Prediction stability</th>
                            <th>Confidence change</th>
                            <th>Explanation stability</th>
                            <th>Δ F1</th>
                            <th>Max range fraction</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedResult.metrics.conditions.map((condition) => (
                            <tr key={condition.epsilon}>
                              <td className="font-mono">{condition.epsilon}</td>
                              <td className="font-mono">{condition.prediction_stability.mean?.toFixed(4)}</td>
                              <td className="font-mono">{condition.confidence_change.mean?.toFixed(4)}</td>
                              <td className="font-mono">{condition.explanation_stability?.mean?.toFixed(4) ?? 'Not measured'}</td>
                              <td className="font-mono">{condition.metric_changes.f1.mean?.toFixed(4)}</td>
                              <td className="font-mono">{condition.maximum_perturbation_fraction_of_train_range.toFixed(4)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <Alert type="info">{selectedResult.interpretation}</Alert>
                    <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem' }}>
                      Synthetic offline fixture only. These measurements do not establish robustness on real data or against external systems.
                    </div>
                  </div>
                )}

                {selectedExpId === 'EXP-CALIBRATION' && selectedResult.metrics?.before && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <ReliabilityDiagram
                      before={selectedResult.metrics.before}
                      after={selectedResult.metrics.after}
                    />
                    <div className="table-container">
                      <table className="table">
                        <thead>
                          <tr><th>Measurement</th><th>Raw probabilities</th><th>After calibration</th></tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>Brier score</td>
                            <td className="font-mono">{selectedResult.metrics.before.brier_score?.toFixed(5)}</td>
                            <td className="font-mono">{selectedResult.metrics.after.brier_score?.toFixed(5)}</td>
                          </tr>
                          <tr>
                            <td>Expected calibration error</td>
                            <td className="font-mono">{selectedResult.metrics.before.expected_calibration_error?.toFixed(5)}</td>
                            <td className="font-mono">{selectedResult.metrics.after.expected_calibration_error?.toFixed(5)}</td>
                          </tr>
                          <tr>
                            <td>Evaluation rows</td>
                            <td className="font-mono">{selectedResult.metrics.before.sample_count}</td>
                            <td className="font-mono">{selectedResult.metrics.after.sample_count}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <Alert type="info">{selectedResult.interpretation}</Alert>
                    <div style={{ background: 'var(--bg-surface)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem' }}>
                      Calibration is fitted on a separate partition and compared on identical untouched test observations. Reliability bins include sample counts. Raw probabilities are not automatically real-world confidence.
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
