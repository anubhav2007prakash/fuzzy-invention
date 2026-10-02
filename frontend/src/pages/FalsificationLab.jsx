import React, { useState, useEffect } from 'react';
import {
  FlaskConical,
  Play,
  Download,
  RefreshCw,
  BarChart2,
  Settings2,
  Flag,
  Alert,
  StatusBadge,
  Box,
  Input,
  Select,
} from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import Alert from '../components/common/Alert';
import TrustProfileBars from '../components/research/TrustProfileBars';
import ReproducibilityPanel from '../components/research/ReproducibilityPanel';
import { experimentsApi } from '../api/experiments';
import { falsificationApi } from '../api/falsification';

const DEFAULT_CONFIGS = {
  n_samples: 1200,
  random_state: 42,
  noise_levels: '0.01, 0.05, 0.10, 0.20',
  n_repetitions: 8,
  n_blocks: 50,
  perturbation_type: 'gaussian_noise',
  perturbation_strength: 0.1,
  n_repeats: 3,
};

function parsePositiveInteger(value, label) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed <= 0) return `${label} must be a positive integer.`;
  return null;
}

function parseFloatValue(value, label) {
  const parsed = Number.parseFloat(value);
  if (isNaN(parsed) || parsed < 0) return `${label} must be a non-negative number.`;
  return null;
}

function parsePerturbationType(value) {
  const validTypes = ['gaussian_noise', 'feature_dropout'];
  if (!validTypes.includes(value)) return `Perturbation type must be one of: ${validTypes.join(', ')}.`;
  return null;
}

function buildConfig(form) {
  const errors = [];
  const config = {};

  // Basic config
  const sampleError = parsePositiveInteger(form.n_samples, 'Sample count');
  const seedError = parsePositiveInteger(form.random_state, 'Seed');
  if (sampleError) errors.push(sampleError);
  if (seedError) errors.push(seedError);
  config.n_samples = Number.parseInt(form.n_samples, 10);
  config.random_state = Number.parseInt(form.random_state, 10);

  // Perturbation config
  const perturbTypeError = parsePerturbationType(form.perturbation_type);
  if (perturbTypeError) errors.push(perturbTypeError);
  config.perturbation_type = form.perturbation_type;
  
  const perturbStrengthError = parseFloatValue(form.perturbation_strength, 'Perturbation strength');
  if (perturbStrengthError) errors.push(perturbStrengthError);
  config.perturbation_strength = Number.parseFloat(form.perturbation_strength);

  // Repeats
  const repeatsError = parsePositiveInteger(form.n_repeats, 'Repeats');
  if (repeatsError) errors.push(repeatsError);
  config.n_repeats = Number.parseInt(form.n_repeats, 10);

  return { config, errors };
}

export default function FalsificationLab() {
  const [selectedClaimId, setSelectedClaimId] = useState('');
  const [claimsData, setClaimsData] = useState({});
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [configForms, setConfigForms] = useState(DEFAULT_CONFIGS);
  const [validationErrors, setValidationErrors] = useState([]);
  const [evidenceExport, setEvidenceExport] = useState(null);
  const [conclusionStatuses, setConclusionStatuses] = useState(null);

  const loadAllClaims = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await falsificationApi.listClaims();
      const map = {};
      (res?.experiments || []).forEach((e) => {
        if (e.claim_id) {
          map[e.claim_id] = e;
        }
      });
      setClaimsData(map);
      setSelectedClaimId(Object.keys(map)[0] || '');
    } catch (err) {
      console.error('Failed to load claims:', err);
      setError(err.message || 'Failed to load claims.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllClaims();
  }, []);

  const handleRunExperiment = async (claimId) => {
    const { config, errors } = buildConfig(configForms[claimId]);
    setValidationErrors(errors);
    setEvidenceExport(null);
    if (errors.length) return;

    setRunning(true);
    setError(null);
    try {
      const result = await falsificationApi.runClaimExperiment(claimId, config);
      setClaimsData((prev) => ({ ...prev, [claimId]: result }));
    } catch (err) {
      setError(err.message || `Failed to run ${claimId}.`);
    } finally {
      setRunning(false);
    }
  };

  const handleExportEvidence = async (claimId) => {
    const { config, errors } = buildConfig(configForms[claimId]);
    setValidationErrors(errors);
    if (errors.length) return;

    setError(null);
    try {
      const exported = await falsificationApi.exportEvidence(claimId, config);
      setEvidenceExport(exported);
    } catch (err) {
      setError(err.message || `Failed to export evidence for ${claimId}.`);
    }
  };

  const updateConfig = (claimId, key, value) => {
    setConfigForms((prev) => ({
      ...prev,
      [claimId]: {
        ...prev[claimId],
        [key]: value,
      },
    }));
  };

  const selectedClaim = claimsData[selectedClaimId] || {};
  const statisticalDifference = selectedClaim.derived_metrics?.difference || {};
  const f1DropInterval = statisticalDifference.f1_drop_confidence_interval;
  const isCompleted = selectedClaim.status === 'COMPLETED';
  const hasRun = selectedClaim.status === 'COMPLETED' && selectedClaim.conclusion_status;

  // Load conclusion statuses
  useEffect(() => {
    falsificationApi.getConclusionStatuses().then(
      (res) => setConclusionStatuses(res),
      (err) => console.error('Failed to load conclusion statuses:', err)
    );
  }, []);

  const conclusionLabels = {
    SUPPORTED: 'SUPPORTED',
    PARTIALLY_SUPPORTED: 'PARTIALLY_SUPPORTED',
    NOT_SUPPORTED: 'NOT_SUPPORTED',
    INCONCLUSIVE: 'INCONCLUSIVE',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', padding: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
            Falsification Lab
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Allow researchers to deliberately attempt to disprove SentinelCrypt research claims.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={loadAllClaims} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spinner' : ''} /> Refresh
          </button>
          <button
            className="btn btn-primary"
            onClick={() => handleRunExperiment(selectedClaimId)}
            disabled={running || !selectedClaimId}
          >
            <Play size={14} className={running ? 'spinner' : ''} />
            {running ? `Executing ${selectedClaimId}...` : `Run Falsification ${selectedClaimId}`}
          </button>
        </div>
      </div>

      {error && (
        <Alert type="danger" title="Experiment Execution Error">
          {error}
        </Alert>
      )}

      <div style={{ marginBottom: '24px' }}>
        <h3 style={{ fontSize: '0.9rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '8px' }}>
          Research Claims
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {Object.keys(claimsData).length === 0 && (
            <div style={{ padding: '20px', background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)' }}>
              <FlaskConical size={24} style={{ color: 'var(--cyan-neon)', margin: '0 auto 8px auto', opacity: 0.7 }} />
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                No claims registered yet. Use the form below to create a new falsification claim.
              </p>
            </div>
          )}

          {Object.keys(claimsData).map((claimId) => {
            const claim = claimsData[claimId];
            const isSelected = selectedClaimId === claimId;

            return (
              <div
                key={claimId}
                style={{
                  cursor: 'pointer',
                  borderColor: isSelected ? 'var(--cyan-neon)' : undefined,
                  background: isSelected ? 'rgba(0, 242, 254, 0.04)' : undefined,
                  padding: '16px',
                  borderRadius: 'var(--radius-sm)',
                  border: isSelected ? '1px solid var(--cyan-neon)' : 'none',
                }}
                onClick={() => setSelectedClaimId(claimId)}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontWeight: '700', fontSize: '0.95rem', color: isSelected ? 'var(--cyan-neon)' : 'var(--text-primary)' }}>
                    {claim.claim_id || claimId}
                  </span>
                  <StatusBadge
                    status={claim.conclusion_status || 'pending'}
                    label={claim.conclusion_status || 'Pending'}
                    style={{ marginLeft: '8px' }}
                  />
                </div>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.4', margin: '4px 0 0 0' }}>
                  {claim.claim_statement || 'No description'}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Claim Creation Form */}
      <div style={{ background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', padding: '20px', marginBottom: '24px' }}>
        <h3 style={{ fontSize: '0.9rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '12px' }}>
          Create New Falsification Claim
        </h3>
        <form
          style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}
          onSubmit={(e) => {
            e.preventDefault();
            // Form submission handled separately
          }}
        >
          <div style={{ display: 'grid', gap: '8px' }}>
            <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Claim ID</label>
            <Input
              type="text"
              defaultValue="CLAIM-001"
              style={{ padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
              placeholder="CLAIM-001"
            />
            <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Claim Statement</label>
            <Input
              type="text"
              defaultValue="The model's detection accuracy degrades significantly under distribution shift."
              style={{ padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
              placeholder="The model's detection accuracy degrades significantly under distribution shift."
            />
            <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Baseline Configuration (JSON)</label>
            <Input
              type="textarea"
              defaultValue='{"n_samples": 1200, "random_state": 42}'
              style={{ padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', height: '100px' }}
              placeholder='{"n_samples": 1200, "random_state": 42}'
            />
            <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Alternative Configuration (JSON)</label>
            <Input
              type="textarea"
              defaultValue='{"n_samples": 1200, "random_state": 420}'
              style={{ padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', height: '100px' }}
              placeholder='{"n_samples": 1200, "random_state": 420}'
            />
            <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Perturbation Type</label>
            <Select
              value={configForms.perturbation_type}
              onValueChange={(value) => updateConfig(selectedClaimId || 'NEW', 'perturbation_type', value)}
              style={{ padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
            >
              <option value="gaussian_noise">gaussian_noise</option>
              <option value="feature_dropout">feature_dropout</option>
            </Select>
            <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Perturbation Strength</label>
            <Input
              type="number"
              step="0.1"
              defaultValue={configForms.perturbation_strength}
              style={{ padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
              placeholder="0.1"
            />
            <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Repeated Runs (n)</label>
            <Input
              type="number"
              min="1"
              defaultValue={configForms.n_repeats}
              style={{ padding: '8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
              placeholder="3"
            />
          </div>
          <button
            type="submit"
            style={{
              marginTop: '8px',
              padding: '8px 16px',
              background: 'var(--cyan-neon)',
              color: 'var(--bg-dark)',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              fontWeight: '600',
              fontSize: '0.85rem',
            }}
            disabled={loading}
          >
            {loading ? 'Creating...' : 'Create Claim'}
          </button>
        </form>
      </div>

      {/* Right: Live Falsification Telemetry & Results View */}
      {selectedClaimId && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
            <div>
              <h2 style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                {selectedClaimId}: {selectedClaim.claim_statement || 'Research Claim'}
              </h2>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                Configuring falsification experiment to disprove this claim...
              </p>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              {conclusionStatuses && (
                <>
                  <select
                    style={{
                      padding: '6px 10px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border)',
                      background: 'var(--bg-input)',
                      fontSize: '0.75rem',
                    }}
                    onChange={(e) => updateConfig(selectedClaimId || 'NEW', 'conclusion_status', e.target.value)}
                  >
                    <option value="">-- Conclusion Status --</option>
                    {Object.entries(conclusionLabels).map(([key, label]) => (
                      <option key={value} value={key}>{label}</option>
                    ))}
                  </select>
                </>
              )}
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)', padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--text-primary)', fontWeight: 700 }}>
              <Settings2 size={16} style={{ color: 'var(--cyan-neon)' }} />
              Experiment Configuration
            </div>

            <div style={{ display: 'grid', gap: '12px', marginBottom: '16px' }}>
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Samples</label>
                <Input
                  type="number"
                  min="1"
                  defaultValue={configForms.n_samples}
                  onChange={(e) => updateConfig(selectedClaimId || 'NEW', 'n_samples', e.target.value)}
                  style={{ padding: '6px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Seed</label>
                <Input
                  type="number"
                  min="0"
                  defaultValue={configForms.random_state}
                  onChange={(e) => updateConfig(selectedClaimId || 'NEW', 'random_state', e.target.value)}
                  style={{ padding: '6px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Perturbation Type</label>
                <Select
                  value={configForms.perturbation_type}
                  onValueChange={(value) => updateConfig(selectedClaimId || 'NEW', 'perturbation_type', value)}
                  style={{ padding: '6px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
                >
                  <option value="gaussian_noise">gaussian_noise</option>
                  <option value="feature_dropout">feature_dropout</option>
                </Select>
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Perturbation Strength</label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  defaultValue={String(configForms.perturbation_strength)}
                  onChange={(e) => updateConfig(selectedClaimId || 'NEW', 'perturbation_strength', e.target.value)}
                  style={{ padding: '6px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Repeated Runs</label>
                <Input
                  type="number"
                  min="1"
                  defaultValue={String(configForms.n_repeats)}
                  onChange={(e) => updateConfig(selectedClaimId || 'NEW', 'n_repeats', e.target.value)}
                  style={{ padding: '6px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}
                />
              </div>
            </div>

            {validationErrors.length > 0 && (
              <Alert type="warning" title="Invalid configuration">
                {validationErrors.join(' ')}
              </Alert>
            )}

            {/* Results Details */}
            {isCompleted ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ fontWeight: '600', fontSize: '0.85rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <BarChart2 size={16} style={{ color: 'var(--cyan-neon)' }} />
                  Falsification Results
                </div>

                <div style={{ background: 'var(--bg-surface)', padding: '16px', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <span style={{ fontWeight: '600', color: 'var(--cyan-neon)' }}>Conclusion Status:</span>
                    <StatusBadge
                      status={selectedClaim.conclusion_status || 'INCONCLUSIVE'}
                      label={conclusionLabels[selectedClaim.conclusion_status] || selectedClaim.conclusion_status}
                    />
                  </div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '0' }}>
                    {selectedClaim.conclusion_justification || 'No justification recorded.'}
                  </p>
                </div>

                <div style={{ background: 'var(--bg-surface)', padding: '16px', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <span style={{ fontWeight: '600', color: 'var(--cyan-neon)' }}>F1 Drop:</span>
                    <span style={{ fontFamily: 'monospace', color: 'var(--status-warning)' }}>
                      {Number.isFinite(statisticalDifference.f1_drop)
                        ? `${(statisticalDifference.f1_drop * 100).toFixed(2)}%`
                        : '—'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <span style={{ fontWeight: '600', color: 'var(--cyan-neon)' }}>95% bootstrap interval for F1 drop:</span>
                    <span style={{ fontFamily: 'monospace', color: 'var(--cyan-neon)' }}>
                      {f1DropInterval
                        ? `[${(f1DropInterval.low * 100).toFixed(2)}%, ${(f1DropInterval.high * 100).toFixed(2)}%]`
                        : 'Unavailable (<2 trials per group)'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: '600', color: 'var(--cyan-neon)' }}>Cohen's d (alternative − baseline):</span>
                    <span style={{ fontFamily: 'monospace', color: 'var(--cyan-neon)' }}>
                      {Number.isFinite(statisticalDifference.cohens_d)
                        ? statisticalDifference.cohens_d.toFixed(4)
                        : 'Unavailable'}
                    </span>
                  </div>
                  <p style={{ marginTop: '12px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    Independent trial-level bootstrap; no hypothesis test or significance claim is made.
                  </p>
                </div>

                <div style={{ background: 'var(--bg-surface)', padding: '16px', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '8px' }}>Metrics Series</div>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {[
                      ...new Set([
                        ...(selectedClaim.baseline_metrics?.f1_series || []),
                        ...(selectedClaim.alternative_metrics?.f1_series || []),
                      ]).values].map((f1, i) => (
                        <span key={i} className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
                          F1 {f1?.toFixed(4)}
                        </span>
                      ))}
                  </div>
                </div>

                {/* Evidence Package */}
                {selectedClaim.evidence && (
                  <div className="card" style={{ background: 'var(--bg-surface)' }}>
                    <div className="card-header">
                      <div>
                        <div className="card-title">
                          <PackageCheck size={16} style={{ color: 'var(--cyan-neon)' }} />
                          Evidence Package
                        </div>
                        <div className="card-subtitle">Export structured evidence for independent inspection</div>
                      </div>
                      <button className="btn btn-secondary" onClick={() => handleExportEvidence(selectedClaimId)}>
                        <Download size={14} />
                        Export Evidence
                      </button>
                    </div>
                    {evidenceExport && evidenceExport.experiment_id === selectedClaimId && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem' }}>
                        <div>Package Path: <span className="hash-pill">{evidenceExport.package_path}</span></div>
                        <div>Package Hash: <span className="hash-pill">{evidenceExport.package_hash}</span></div>
                        <div>Files: {evidenceExport.files.join(', ')}</div>
                      </div>
                    )}
                  </div>
                )}

                {/* Reproducibility Manifest */}
                {selectedClaim.run_manifest && (
                  <ReproducibilityPanel result={selectedClaim} />
                )}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '32px 16px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)' }}>
                <FlaskConical size={32} style={{ color: 'var(--cyan-neon)', margin: '0 auto 12px auto', opacity: 0.7 }} />
                <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Claim Not Yet Executed
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
                  Click the button below to launch the automated falsification experiment runner.
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => handleRunExperiment(selectedClaimId)}
                  disabled={running}
                >
                  <Play size={14} className={running ? 'spinner' : ''} />
                  {running ? `Executing ${selectedClaimId}...` : `Run Falsification ${selectedClaimId}`}
                </button>
              </div>
            )}
          </div>
        </div>
      )} {/* End selectedClaimId check */}
    </div>
  );
}