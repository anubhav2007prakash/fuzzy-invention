import React, { useState, useEffect } from 'react';
import { BrainCircuit, Play, Trash2, RefreshCw, BarChart2, ShieldCheck, CheckCircle2, Award } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import Loader from '../components/common/Loader';
import Alert from '../components/common/Alert';
import ConfusionMatrix from '../components/charts/ConfusionMatrix';
import ReliabilityDiagram from '../components/charts/ReliabilityDiagram';
import ModelTrainModal from '../components/forms/ModelTrainModal';
import { formatPercent, modelArchitecture } from '../utils/format';
import { modelsApi } from '../api/models';
import { datasetsApi } from '../api/datasets';

export default function Models() {
  const [models, setModels] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [modelMetrics, setModelMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [isTrainOpen, setIsTrainOpen] = useState(false);
  const [error, setError] = useState(null);

  const loadModels = async () => {
    setLoading(true);
    setError(null);
    try {
      const [mRes, dRes] = await Promise.all([
        modelsApi.list({ skip: 0, limit: 100 }),
        datasetsApi.list({ skip: 0, limit: 100 }),
      ]);
      const list = mRes?.models || [];
      setModels(list);
      setDatasets(dRes?.datasets || []);
      if (list.length > 0 && !selectedModel) {
        handleSelectModel(list[0]);
      }
    } catch (err) {
      setError(err.message || 'Failed to load model registry.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadModels();
  }, []);

  const handleSelectModel = async (model) => {
    setSelectedModel(model);
    setMetricsLoading(true);
    try {
      const metrics = await modelsApi.getMetrics(model.id);
      setModelMetrics(metrics);
    } catch (err) {
      setModelMetrics(null);
    } finally {
      setMetricsLoading(false);
    }
  };

  const handleDeleteModel = async (modelId, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this trained model?')) return;

    try {
      await modelsApi.delete(modelId);
      if (selectedModel?.id === modelId) {
        setSelectedModel(null);
        setModelMetrics(null);
      }
      loadModels();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  if (loading) {
    return <Loader text="Loading model baselines & evaluation metrics..." size="lg" />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
            Model Lab & Evaluator
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Train, evaluate, and compare baseline ML classifiers (Random Forest & Logistic Regression) on network flow datasets.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={loadModels}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button className="btn btn-primary" onClick={() => setIsTrainOpen(true)}>
            <BrainCircuit size={14} /> Train New Model
          </button>
        </div>
      </div>

      {error && (
        <Alert type="danger" title="Error">
          {error}
        </Alert>
      )}

      {models.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <BrainCircuit size={40} style={{ color: 'var(--purple-accent)', margin: '0 auto 16px auto' }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '8px' }}>No Trained Models in Registry</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '480px', margin: '0 auto 20px auto' }}>
            Train a Logistic Regression or Random Forest model on an ingested dataset to evaluate performance and enable real-time predictions.
          </p>
          <button className="btn btn-primary" onClick={() => setIsTrainOpen(true)}>
            <BrainCircuit size={16} /> Train First Model
          </button>
        </div>
      ) : (
        <div className="grid-2" style={{ gridTemplateColumns: '1fr 1.3fr', alignItems: 'start' }}>
          {/* Model Registry List */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <BrainCircuit size={18} style={{ color: 'var(--purple-accent)' }} />
                Model Registry ({models.length})
              </div>
            </div>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Model Name</th>
                    <th>Type</th>
                    <th>F1 Score</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m) => {
                    const isSelected = selectedModel?.id === m.id;
                    return (
                      <tr
                        key={m.id}
                        onClick={() => handleSelectModel(m)}
                        style={{
                          cursor: 'pointer',
                          background: isSelected ? 'rgba(168, 85, 247, 0.1)' : undefined,
                          borderLeft: isSelected ? '3px solid var(--purple-accent)' : '3px solid transparent',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <td style={{ fontWeight: isSelected ? '700' : '500', color: isSelected ? 'var(--purple-accent)' : 'var(--text-primary)' }}>
                          {m.name}
                        </td>
                        <td>
                          <StatusBadge status={modelArchitecture(m)} />
                        </td>
                        <td style={{ fontFamily: 'monospace', color: 'var(--cyan-neon)' }}>
                          {formatPercent(m.metrics?.f1_macro)}
                        </td>
                        <td>
                          <button
                            className="btn btn-danger"
                            onClick={(e) => handleDeleteModel(m.id, e)}
                            style={{ padding: '4px 8px', fontSize: '0.7rem' }}
                            title="Delete model"
                          >
                            <Trash2 size={12} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Model Metrics & Confusion Matrix */}
          {selectedModel && (
            <div className="card">
              <div className="card-header">
                <div>
                  <div className="card-title" style={{ color: 'var(--purple-accent)' }}>
                    {selectedModel.name}
                  </div>
                  <div className="card-subtitle">Architecture: {modelArchitecture(selectedModel)} · Version: {selectedModel.version}</div>
                </div>
                <StatusBadge status="model" label="Active Baseline" />
              </div>

              {metricsLoading ? (
                <Loader text="Loading evaluation breakdown..." size="sm" />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {/* KPI Cards */}
                  <div className="grid-3" style={{ gap: '10px' }}>
                    <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Accuracy</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                        {formatPercent(modelMetrics?.metrics?.accuracy ?? selectedModel.metrics?.accuracy, 2)}
                      </div>
                    </div>
                    <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>F1-Score (macro)</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--cyan-neon)', fontFamily: 'monospace' }}>
                        {formatPercent(modelMetrics?.metrics?.f1_macro ?? selectedModel.metrics?.f1_macro, 2)}
                      </div>
                    </div>
                    <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Precision (macro)</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--blue-primary)', fontFamily: 'monospace' }}>
                        {formatPercent(modelMetrics?.metrics?.precision_macro ?? selectedModel.metrics?.precision_macro, 2)}
                      </div>
                    </div>
                  </div>

                  {/* Confusion Matrix */}
                  <div>
                    <div style={{ fontWeight: '600', fontSize: '0.85rem', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <BarChart2 size={16} style={{ color: 'var(--cyan-neon)' }} />
                      Confusion Matrix Breakdown
                    </div>
                    <ConfusionMatrix matrix={modelMetrics?.confusion_matrix} />
                  </div>

                  {modelMetrics?.calibration?.before && (
                    <section style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontWeight: '600', fontSize: '0.85rem', marginBottom: '8px' }}>
                        Probability Calibration
                      </div>
                      <div className="grid-2" style={{ gap: '12px', alignItems: 'center' }}>
                        <ReliabilityDiagram
                          before={modelMetrics.calibration.before}
                          after={modelMetrics.calibration.after}
                        />
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                          <div>Method: <strong>{modelMetrics.calibration.method}</strong></div>
                          <div>Held-out rows: <strong>{modelMetrics.calibration.before.sample_count}</strong></div>
                          <div>Before Brier: <strong>{modelMetrics.calibration.before.brier_score?.toFixed(4)}</strong></div>
                          <div>Before ECE: <strong>{modelMetrics.calibration.before.expected_calibration_error?.toFixed(4)}</strong></div>
                          {modelMetrics.calibration.after && (
                            <>
                              <div>After Brier: <strong>{modelMetrics.calibration.after.brier_score?.toFixed(4)}</strong></div>
                              <div>After ECE: <strong>{modelMetrics.calibration.after.expected_calibration_error?.toFixed(4)}</strong></div>
                            </>
                          )}
                          <p style={{ margin: '8px 0 0', fontSize: '0.72rem' }}>
                            Measurements use the same held-out test set. Calibration is distribution-specific; model probabilities are not guarantees of real-world confidence.
                          </p>
                        </div>
                      </div>
                    </section>
                  )}

                  {/* Context */}
                  <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem' }}>
                    <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>Recorded Metrics:</div>
                    <div className="font-mono" style={{ color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
                      {JSON.stringify(
                        Object.fromEntries(
                          Object.entries(modelMetrics?.metrics ?? selectedModel.metrics ?? {}).filter(
                            ([, v]) => typeof v === 'number'
                          )
                        ),
                        null,
                        2
                      )}
                    </div>
                  </div>

                  <Alert type="info">
                    Model evaluation is computed on the held-out test split (random_state=42). Results reflect statistical detection capacity on selected traffic distribution.
                  </Alert>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <ModelTrainModal
        isOpen={isTrainOpen}
        onClose={() => setIsTrainOpen(false)}
        datasets={datasets}
        onTrainSuccess={loadModels}
      />
    </div>
  );
}
