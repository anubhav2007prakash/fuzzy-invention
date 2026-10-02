import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Database,
  BrainCircuit,
  Activity,
  ShieldCheck,
  Upload,
  Play,
  ArrowRight,
  Shield,
  Layers,
  Sparkles,
  Zap,
} from 'lucide-react';
import StatCard from '../components/common/StatCard';
import StatusBadge from '../components/common/StatusBadge';
import HashChainVisual from '../components/charts/HashChainVisual';
import Loader from '../components/common/Loader';
import Alert from '../components/common/Alert';
import DatasetUploadModal from '../components/forms/DatasetUploadModal';
import ModelTrainModal from '../components/forms/ModelTrainModal';

import { formatPercent, resolveConfidence, isAttackClass, modelArchitecture } from '../utils/format';
import { datasetsApi } from '../api/datasets';
import { modelsApi } from '../api/models';
import { predictionsApi } from '../api/predictions';
import { auditApi } from '../api/audit';

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [datasets, setDatasets] = useState([]);
  const [models, setModels] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [auditStatus, setAuditStatus] = useState(null);
  const [auditRecords, setAuditRecords] = useState([]);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);

  const [activePipelineTab, setActivePipelineTab] = useState('guardrails');
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isTrainOpen, setIsTrainOpen] = useState(false);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [dRes, mRes, pRes, aStatus, aRecs] = await Promise.allSettled([
        datasetsApi.list({ skip: 0, limit: 10 }),
        modelsApi.list({ skip: 0, limit: 10 }),
        predictionsApi.list({ skip: 0, limit: 10 }),
        auditApi.getStatus(),
        auditApi.listRecords({ skip: 0, limit: 5 }),
      ]);

      if (dRes.status === 'fulfilled') setDatasets(dRes.value?.datasets || []);
      if (mRes.status === 'fulfilled') setModels(mRes.value?.models || []);
      if (pRes.status === 'fulfilled') setPredictions(pRes.value?.predictions || []);
      if (aStatus.status === 'fulfilled') setAuditStatus(aStatus.value);
      if (aRecs.status === 'fulfilled') setAuditRecords(aRecs.value?.records || []);
    } catch (err) {
      console.error('Failed to load dashboard telemetry:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const handleVerifyLedger = async () => {
    setIsVerifying(true);
    setVerifyResult(null);
    try {
      const result = await auditApi.verifyChain({ verify_entire_chain: true });
      setVerifyResult(result);
    } catch (err) {
      setVerifyResult({ verified: false, message: err.message });
    } finally {
      setIsVerifying(false);
    }
  };

  if (loading) {
    return <Loader text="Synchronizing autonomous runtime state..." size="lg" />;
  }

  const isChainValid = auditStatus?.is_intact !== false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Qronos Hero Operational Banner */}
      <div
        className="card"
        style={{
          padding: '28px',
          background: 'radial-gradient(circle at 50% 0%, rgba(255, 255, 255, 0.05) 0%, transparent 65%), linear-gradient(#0a0a0e, #07070a)',
          borderColor: 'rgba(255, 255, 255, 0.12)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span className="badge badge-info">STATEFUL RUNTIME</span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>SHA-256 FORWARD LINKED</span>
            </div>
            <h2 style={{ fontSize: '1.45rem', fontWeight: '800', letterSpacing: '-0.4px', color: '#ffffff', marginBottom: '6px' }}>
              Cryptographic Guardrails for Autonomous Network Defense
            </h2>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', maxWidth: '640px', lineHeight: '1.5' }}>
              Coordinate traffic ingestion, real-time ML inference pipelines, and immutable cryptographic evidence blocks across every governed network flow.
            </p>
          </div>

          {/* Qronos Star CTA Button */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
            <button className="qronos-star-button" onClick={handleVerifyLedger} disabled={isVerifying}>
              <ShieldCheck size={14} className={isVerifying ? 'spinner' : ''} />
              <span>{isVerifying ? 'Verifying Hashes...' : 'Verify Entire Ledger »'}</span>
            </button>
            <Link to="/predictions" className="btn btn-secondary">
              <Play size={13} /> Predict Flow
            </Link>
          </div>
        </div>

        {/* Qronos Pipeline Preview Tabs */}
        <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
          <div className="qronos-pipeline-tabs">
            <button
              className={`qronos-pipeline-tab ${activePipelineTab === 'guardrails' ? 'active' : ''}`}
              onClick={() => setActivePipelineTab('guardrails')}
            >
              <ShieldCheck size={13} /> Cryptographic Guardrails
            </button>
            <button
              className={`qronos-pipeline-tab ${activePipelineTab === 'models' ? 'active' : ''}`}
              onClick={() => setActivePipelineTab('models')}
            >
              <BrainCircuit size={13} /> Model Registry
            </button>
            <button
              className={`qronos-pipeline-tab ${activePipelineTab === 'datasets' ? 'active' : ''}`}
              onClick={() => setActivePipelineTab('datasets')}
            >
              <Database size={13} /> Flow Ingestion
            </button>
            <button
              className={`qronos-pipeline-tab ${activePipelineTab === 'xai' ? 'active' : ''}`}
              onClick={() => setActivePipelineTab('xai')}
            >
              <Sparkles size={13} /> SHAP Attribution
            </button>
          </div>

          {/* Tab Previews */}
          {activePipelineTab === 'guardrails' && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <div>Forward-Linkage Status: <strong style={{ color: isChainValid ? 'var(--status-benign)' : 'var(--status-attack)' }}>{isChainValid ? '100% Mathematically Anchored (0 Tampering)' : 'Chain Mutation Flagged'}</strong></div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 10px' }} onClick={() => setIsUploadOpen(true)}>
                  <Upload size={12} /> Ingest Dataset
                </button>
                <button className="btn btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 10px' }} onClick={() => setIsTrainOpen(true)}>
                  <BrainCircuit size={12} /> Train Model
                </button>
              </div>
            </div>
          )}

          {activePipelineTab === 'models' && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <div>Active Baselines: <strong style={{ color: '#ffffff' }}>{models.length} Trained Classifiers (Random Forest & Logistic Regression)</strong></div>
              <Link to="/models" className="btn btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 10px' }}>
                Open Model Lab →
              </Link>
            </div>
          )}

          {activePipelineTab === 'datasets' && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <div>Registered Telemetry: <strong style={{ color: '#ffffff' }}>{datasets.length} Traffic Benchmarks Ingested</strong></div>
              <button className="btn btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 10px' }} onClick={() => setIsUploadOpen(true)}>
                <Upload size={12} /> Ingest CSV →
              </button>
            </div>
          )}

          {activePipelineTab === 'xai' && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <div>Explainability Engine: <strong style={{ color: 'var(--purple-accent)' }}>Local TreeSHAP & LinearSHAP Attribution</strong></div>
              <Link to="/explainability" className="btn btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 10px' }}>
                Open Waterfall View →
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Top Stat Grid (Qronos KPI Cards) */}
      <div className="grid-4">
        <StatCard
          title="Registered Datasets"
          value={datasets.length}
          subtitle="Validated traffic captures"
          icon={Database}
          color="cyan"
        />
        <StatCard
          title="Active Model Baselines"
          value={models.length}
          subtitle="Trained classifiers"
          icon={BrainCircuit}
          color="blue"
        />
        <StatCard
          title="Total Inferences"
          value={predictions.length}
          subtitle="Classified network flows"
          icon={Activity}
          color="purple"
        />
        <StatCard
          title="Audit Ledger Blocks"
          value={auditStatus?.total_records ?? auditRecords.length}
          subtitle={isChainValid ? 'SHA-256 Forward Linked' : 'Tampering Detected'}
          icon={ShieldCheck}
          color={isChainValid ? 'green' : 'red'}
        />
      </div>

      {/* Verification Result Banner */}
      {verifyResult && (
        <Alert
          type={verifyResult.verified ? 'success' : 'danger'}
          title={verifyResult.verified ? 'Ledger Chain Mathematically Verified' : 'Cryptographic Verification Failure'}
        >
          {verifyResult.verified ? (
            <div>
              Verified <strong>{verifyResult.checked_records}</strong> consecutive blocks. All forward-linkage SHA-256 hashes matched expected canonical state with 0 corrupted records.
            </div>
          ) : (
            <div>
              Verification error: {verifyResult.message || 'Hash mismatch detected.'}
            </div>
          )}
        </Alert>
      )}

      {/* Hash Chain Visualizer */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">
              <ShieldCheck size={16} style={{ color: 'var(--cyan-neon)' }} />
              Live Cryptographic Audit Ledger
            </div>
            <div className="card-subtitle">
              SHA-256 forward-linked evidence anchoring every network flow prediction
            </div>
          </div>
          <Link to="/audit" className="btn btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 10px' }}>
            View Full Ledger <ArrowRight size={13} />
          </Link>
        </div>

        <HashChainVisual records={auditRecords} />
      </div>

      {/* Split Grid: Recent Inferences & Active Models */}
      <div className="grid-2">
        {/* Recent Inferences */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">
                <Activity size={16} style={{ color: 'var(--blue-primary)' }} />
                Recent Inferences
              </div>
              <div className="card-subtitle">Latest classified network flow traffic</div>
            </div>
            <Link to="/predictions" className="btn btn-secondary" style={{ fontSize: '0.72rem', padding: '4px 9px' }}>
              Workspace
            </Link>
          </div>

          {predictions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
              No inferences run yet. Navigate to Prediction Workspace to classify network flow samples.
            </div>
          ) : (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Classification</th>
                    <th>Confidence</th>
                    <th>Proof</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.slice(0, 5).map((p) => {
                    return (
                      <tr key={p.prediction_id}>
                        <td style={{ fontSize: '0.74rem' }}>
                          {p.created_at ? new Date(p.created_at).toLocaleTimeString() : 'Recent'}
                        </td>
                        <td>
                          <StatusBadge status={isAttackClass(p.predicted_class) ? 'ATTACK' : 'BENIGN'} />
                        </td>
                        <td style={{ fontWeight: '600', fontFamily: 'monospace', color: '#ffffff' }}>
                          {formatPercent(resolveConfidence(p))}
                        </td>
                        <td>
                          <Link to="/audit" style={{ color: 'var(--cyan-neon)', textDecoration: 'none', fontSize: '0.72rem' }}>
                            View Proof →
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Model Lab Summary */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">
                <BrainCircuit size={16} style={{ color: 'var(--purple-accent)' }} />
                Registered Model Baselines
              </div>
              <div className="card-subtitle">Active intrusion detection algorithms</div>
            </div>
            <Link to="/models" className="btn btn-secondary" style={{ fontSize: '0.72rem', padding: '4px 9px' }}>
              Model Lab
            </Link>
          </div>

          {models.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)' }}>
              No models trained yet. Click "Train Model" above to evaluate a classifier on registered datasets.
            </div>
          ) : (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Model Name</th>
                    <th>Type</th>
                    <th>Accuracy</th>
                    <th>F1-Score</th>
                  </tr>
                </thead>
                <tbody>
                  {models.slice(0, 5).map((m) => (
                    <tr key={m.id}>
                      <td style={{ fontWeight: '600', color: '#ffffff' }}>{m.name}</td>
                      <td>
                        <StatusBadge status={modelArchitecture(m)} />
                      </td>
                      <td style={{ fontFamily: 'monospace' }}>
                        {formatPercent(m.metrics?.accuracy, 2)}
                      </td>
                      <td style={{ fontFamily: 'monospace', color: 'var(--cyan-neon)' }}>
                        {formatPercent(m.metrics?.f1_macro, 2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <DatasetUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={loadDashboardData}
      />
      <ModelTrainModal
        isOpen={isTrainOpen}
        onClose={() => setIsTrainOpen(false)}
        datasets={datasets}
        onTrainSuccess={loadDashboardData}
      />
    </div>
  );
}
