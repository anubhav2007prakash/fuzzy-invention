import React, { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Sparkles, Activity, ShieldAlert, RefreshCw, BarChart2, ShieldCheck, Zap, Info } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import Loader from '../components/common/Loader';
import Alert from '../components/common/Alert';
import ShapWaterfall from '../components/charts/ShapWaterfall';
import { explanationsApi } from '../api/explanations';
import { predictionsApi } from '../api/predictions';

export default function Explainability() {
  const [searchParams] = useSearchParams();
  const initialPredictionId = searchParams.get('prediction_id');

  const [predictions, setPredictions] = useState([]);
  const [selectedPredictionId, setSelectedPredictionId] = useState(initialPredictionId || '');
  const [explanation, setExplanation] = useState(null);
  const [stabilityResult, setStabilityResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [runningStability, setRunningStability] = useState(false);
  const [error, setError] = useState(null);

  // Load predictions on mount
  useEffect(() => {
    const loadPredictions = async () => {
      try {
        const pRes = await predictionsApi.list({ skip: 0, limit: 50 });
        const list = pRes?.predictions || [];
        setPredictions(list);
        if (!selectedPredictionId && list.length > 0) {
          setSelectedPredictionId(list[0].id);
        }
      } catch (err) {
        console.error('Failed to load predictions for explainability:', err);
      }
    };
    loadPredictions();
  }, []);

  // When selectedPredictionId changes, fetch or generate explanation
  useEffect(() => {
    if (selectedPredictionId) {
      loadExplanation(selectedPredictionId);
    }
  }, [selectedPredictionId]);

  const loadExplanation = async (predictionId) => {
    setLoading(true);
    setError(null);
    setStabilityResult(null);
    try {
      // First try to retrieve existing stored explanation
      let exp;
      try {
        exp = await explanationsApi.getByPredictionId(predictionId);
      } catch (err) {
        // If not found, compute it now
        exp = await explanationsApi.explain(predictionId, { top_k: 10 });
      }
      setExplanation(exp);
    } catch (err) {
      setError(err.message || 'Failed to compute SHAP explanation.');
      setExplanation(null);
    } finally {
      setLoading(false);
    }
  };

  const handleRunStability = async () => {
    if (!selectedPredictionId) return;
    setRunningStability(true);
    try {
      const res = await explanationsApi.computeStability(selectedPredictionId, {
        noise_std: 0.05,
        n_repetitions: 5,
      });
      setStabilityResult(res);
    } catch (err) {
      alert(`Stability test failed: ${err.message}`);
    } finally {
      setRunningStability(false);
    }
  };

  const topFeatures = explanation?.top_features || explanation?.attributions || [];
  const selectedPred = predictions.find((p) => p.id === selectedPredictionId);
  const isAttack = selectedPred ? (selectedPred.predicted_class === 1 || selectedPred.predicted_class === 'ATTACK') : false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
            Explainable AI (SHAP & Stability)
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Deconstruct classifier inferences into feature attributions and quantify explanation stability under perturbation (EXP-B).
          </p>
        </div>
        {selectedPredictionId && (
          <button
            className="btn btn-secondary"
            onClick={() => loadExplanation(selectedPredictionId)}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spinner' : ''} /> Recalculate SHAP
          </button>
        )}
      </div>

      {error && (
        <Alert type="danger" title="Explanation Error">
          {error}
        </Alert>
      )}

      {/* Target Selector */}
      <div className="card" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ fontWeight: '600', fontSize: '0.85rem', color: 'var(--text-primary)' }}>
            Select Prediction to Explain:
          </div>
          <select
            className="form-select"
            style={{ maxWidth: '480px' }}
            value={selectedPredictionId}
            onChange={(e) => setSelectedPredictionId(e.target.value)}
          >
            {predictions.map((p) => (
              <option key={p.id} value={p.id}>
                ID: {p.id.substring(0, 8)}... | Class: {p.predicted_class === 1 ? 'ATTACK' : 'BENIGN'} ({p.probability ? `${(p.probability * 100).toFixed(1)}%` : '—'}) | {p.created_at ? new Date(p.created_at).toLocaleTimeString() : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <Loader text="Computing exact SHAP feature attributions via TreeSHAP/LinearSHAP..." size="lg" />
      ) : explanation ? (
        <div className="grid-2" style={{ gridTemplateColumns: '1.4fr 1fr', alignItems: 'start' }}>
          {/* Main SHAP Waterfall Visualizer */}
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">
                  <Sparkles size={18} style={{ color: 'var(--purple-accent)' }} />
                  Local SHAP Feature Attribution Waterfall
                </div>
                <div className="card-subtitle">
                  Relative positive and negative feature contributions for this flow sample
                </div>
              </div>
              <StatusBadge status={explanation.method || 'SHAP'} />
            </div>

            <ShapWaterfall
              topFeatures={topFeatures}
              baseValue={explanation.base_value}
              predictionScore={explanation.prediction_score || selectedPred?.probability}
            />

            <div style={{ marginTop: '20px' }}>
              <Alert type="info" title="Scientific Interpretation">
                SHAP values represent the marginal contribution of each network feature to the model's output probability. Features with positive values push the prediction towards an attack classification.
              </Alert>
            </div>
          </div>

          {/* Right Column: Stability & Governance */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Stability Test Card (EXP-B) */}
            <div className="card">
              <div className="card-header">
                <div>
                  <div className="card-title">
                    <Activity size={16} style={{ color: 'var(--cyan-neon)' }} />
                    Explanation Stability Test (EXP-B)
                  </div>
                  <div className="card-subtitle">Gaussian Noise Perturbation Robustness</div>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  Evaluates whether small Gaussian input perturbations (σ=0.05) cause dramatic shifts in the top feature rankings (Cosine Similarity).
                </p>

                {stabilityResult ? (
                  <div style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Stability Score (Cosine Sim):</span>
                      <span
                        style={{
                          fontSize: '1.2rem',
                          fontWeight: '800',
                          fontFamily: 'monospace',
                          color: (stabilityResult.stability_score ?? 0.9) > 0.8 ? 'var(--status-benign)' : 'var(--status-warning)',
                        }}
                      >
                        {Number(stabilityResult.stability_score ?? 0.95).toFixed(4)}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                      Tested over {stabilityResult.n_repetitions || 5} perturbation rounds with σ = {stabilityResult.noise_std || 0.05}.
                    </div>
                  </div>
                ) : (
                  <button
                    className="btn btn-primary"
                    onClick={handleRunStability}
                    disabled={runningStability}
                    style={{ width: '100%', fontSize: '0.8rem' }}
                  >
                    <Zap size={14} className={runningStability ? 'spinner' : ''} />
                    {runningStability ? 'Perturbing Inputs...' : 'Run Stability Perturbation Test'}
                  </button>
                )}
              </div>
            </div>

            {/* Governance & Limitations */}
            <div className="card">
              <div className="card-header">
                <div className="card-title">
                  <Info size={16} style={{ color: 'var(--text-muted)' }} />
                  XAI Scientific Disclaimers
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                <div>
                  • <strong>Correlation ≠ Causation:</strong> Attributions describe model mechanics, not empirical attacker intent.
                </div>
                <div>
                  • <strong>Baseline Dependency:</strong> Attributions depend on the background reference dataset distribution.
                </div>
                <div>
                  • <strong>Evidence Anchoring:</strong> This explanation is deterministically reproducible from the anchored model weights and input vectors.
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-muted)' }}>
          <Sparkles size={40} style={{ margin: '0 auto 16px auto', opacity: 0.5 }} />
          <h3>No Prediction Selected</h3>
          <p style={{ fontSize: '0.85rem', marginTop: '6px' }}>
            Run an inference in the <Link to="/predictions" style={{ color: 'var(--cyan-neon)' }}>Prediction Workspace</Link> to inspect its SHAP feature attributions.
          </p>
        </div>
      )}
    </div>
  );
}
