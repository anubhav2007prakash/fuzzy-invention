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
  ShieldAlert,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import StatCard from '../components/common/StatCard';
import StatusBadge from '../components/common/StatusBadge';
import HashChainVisual from '../components/charts/HashChainVisual';
import Loader from '../components/common/Loader';
import Alert from '../components/common/Alert';
import DatasetUploadModal from '../components/forms/DatasetUploadModal';
import ModelTrainModal from '../components/forms/ModelTrainModal';

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
      setVerifyResult({ is_valid: false, error: err.message });
    } finally {
      setIsVerifying(false);
    }
  };

  if (loading) {
    return <Loader text="Loading cybersecurity telemetry & ledger status..." size="lg" />;
  }

  const isChainValid = auditStatus?.is_valid !== false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Stat Grid */}
      <div className="grid-4">
        <StatCard
          title="Registered Datasets"
          value={datasets.length}
          subtitle="Validated traffic datasets"
          icon={Database}
          color="cyan"
        />
        <StatCard
          title="Trained Models"
          value={models.length}
          subtitle="LR & Random Forest"
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
          subtitle={isChainValid ? 'Chain Intact (SHA-256)' : 'Tampering Detected'}
          icon={ShieldCheck}
          color={isChainValid ? 'green' : 'red'}
        />
      </div>

      {/* Quick Action Shortcuts */}
      <div className="card" style={{ background: 'linear-gradient(90deg, rgba(0, 242, 254, 0.05), rgba(59, 130, 246, 0.05))' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ fontWeight: '600', fontSize: '1rem', color: 'var(--text-primary)' }}>
              SentinelCrypt Operational Controls
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Quickly ingest datasets, trigger model evaluations, run inferences, or verify cryptographic proof.
            </div>
          </div>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <button className="btn btn-secondary" onClick={() => setIsUploadOpen(true)}>
              <Upload size={16} /> Ingest Dataset
            </button>
            <button className="btn btn-secondary" onClick={() => setIsTrainOpen(true)}>
              <BrainCircuit size={16} /> Train Model
            </button>
            <Link to="/predictions" className="btn btn-primary">
              <Play size={16} /> Predict Flow
            </Link>
            <button className="btn btn-verify" onClick={handleVerifyLedger} disabled={isVerifying}>
              <ShieldCheck size={16} className={isVerifying ? 'spinner' : ''} />
              {isVerifying ? 'Verifying Hashes...' : 'Verify Entire Ledger'}
            </button>
          </div>
        </div>
      </div>

      {/* Verification Result Banner */}
      {verifyResult && (
        <Alert
          type={verifyResult.is_valid ? 'success' : 'danger'}
          title={verifyResult.is_valid ? 'Ledger Chain Mathematically Verified' : 'Cryptographic Verification Failure'}
        >
          {verifyResult.is_valid ? (
            <div>
              Verified <strong>{verifyResult.records_verified}</strong> consecutive blocks. All forward-linkage SHA-256 hashes matched expected canonical state with 0 corrupted records.
            </div>
          ) : (
            <div>
              Verification error at sequence #{verifyResult.corrupted_sequence_number || 'Unknown'}: {verifyResult.details || verifyResult.error || 'Hash mismatch detected.'}
            </div>
          )}
        </Alert>
      )}

      {/* Hash Chain Visualizer */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">
              <ShieldCheck size={18} style={{ color: 'var(--cyan-neon)' }} />
              Live Cryptographic Audit Ledger
            </div>
            <div className="card-subtitle">
              SHA-256 forward-linked evidence anchoring every network flow prediction
            </div>
          </div>
          <Link to="/audit" className="btn btn-secondary" style={{ fontSize: '0.78rem', padding: '6px 12px' }}>
            View Full Ledger <ArrowRight size={14} />
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
                <Activity size={18} style={{ color: 'var(--blue-primary)' }} />
                Recent Inferences
              </div>
              <div className="card-subtitle">Latest classified network flow traffic</div>
            </div>
            <Link to="/predictions" className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '4px 10px' }}>
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
                    <th>Audit Proof</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.slice(0, 5).map((p) => {
                    const isAttack = p.predicted_class === 1 || p.predicted_class === 'ATTACK';
                    return (
                      <tr key={p.id}>
                        <td style={{ fontSize: '0.75rem' }}>
                          {p.created_at ? new Date(p.created_at).toLocaleTimeString() : 'Recent'}
                        </td>
                        <td>
                          <StatusBadge status={isAttack ? 'ATTACK' : 'BENIGN'} />
                        </td>
                        <td style={{ fontWeight: '600', fontFamily: 'monospace' }}>
                          {p.probability !== undefined ? `${(p.probability * 100).toFixed(1)}%` : '—'}
                        </td>
                        <td>
                          <Link to="/audit" style={{ color: 'var(--cyan-neon)', textDecoration: 'none', fontSize: '0.75rem' }}>
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
                <BrainCircuit size={18} style={{ color: 'var(--purple-accent)' }} />
                Registered Model Baselines
              </div>
              <div className="card-subtitle">Active intrusion detection algorithms</div>
            </div>
            <Link to="/models" className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '4px 10px' }}>
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
                      <td style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{m.name}</td>
                      <td>
                        <StatusBadge status={m.model_type} />
                      </td>
                      <td style={{ fontFamily: 'monospace' }}>
                        {m.accuracy !== undefined ? `${(m.accuracy * 100).toFixed(2)}%` : '—'}
                      </td>
                      <td style={{ fontFamily: 'monospace', color: 'var(--cyan-neon)' }}>
                        {m.f1_score !== undefined ? `${(m.f1_score * 100).toFixed(2)}%` : '—'}
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
