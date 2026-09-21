import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Activity, Play, Sparkles, ShieldCheck, RefreshCw, Zap, Layers, AlertCircle } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import Loader from '../components/common/Loader';
import Alert from '../components/common/Alert';
import { modelsApi } from '../api/models';
import { predictionsApi } from '../api/predictions';

const PRESETS = {
  benign_web: {
    name: 'Normal HTTPS Traffic (Benign)',
    features: {
      dur: 0.000011,
      spkts: 2,
      dpkts: 0,
      sbytes: 496,
      dbytes: 0,
      rate: 90909.09,
      sttl: 254,
      dttl: 0,
      sload: 180363632.0,
      dload: 0.0,
      sloss: 0,
      dloss: 0,
      sinpkt: 0.011,
      dinpkt: 0.0,
      sjit: 0.0,
      djit: 0.0,
      swin: 255,
      stcpb: 2884726144,
      dtcpb: 0,
      dwin: 255,
      tcprtt: 0.0,
      synack: 0.0,
      ackdat: 0.0,
      smean: 248,
      dmean: 0,
      trans_depth: 0,
      response_body_len: 0,
      ct_srv_src: 2,
      ct_state_ttl: 2,
      ct_dst_ltm: 1,
      ct_src_dport_ltm: 1,
      ct_dst_sport_ltm: 1,
      ct_dst_src_ltm: 2,
      is_ftp_login: 0,
      ct_ftp_cmd: 0,
      ct_flw_http_mthd: 0,
      ct_src_ltm: 1,
      ct_srv_dst: 2,
      is_sm_ips_ports: 0,
    },
  },
  dos_syn: {
    name: 'SYN Flood DoS Attack (High Vol/Rate)',
    features: {
      dur: 0.000008,
      spkts: 2,
      dpkts: 0,
      sbytes: 200,
      dbytes: 0,
      rate: 125000.0,
      sttl: 254,
      dttl: 0,
      sload: 100000000.0,
      dload: 0.0,
      sloss: 0,
      dloss: 0,
      sinpkt: 0.008,
      dinpkt: 0.0,
      sjit: 0.0,
      djit: 0.0,
      swin: 0,
      stcpb: 0,
      dtcpb: 0,
      dwin: 0,
      tcprtt: 0.0,
      synack: 0.0,
      ackdat: 0.0,
      smean: 100,
      dmean: 0,
      trans_depth: 0,
      response_body_len: 0,
      ct_srv_src: 40,
      ct_state_ttl: 2,
      ct_dst_ltm: 35,
      ct_src_dport_ltm: 35,
      ct_dst_sport_ltm: 35,
      ct_dst_src_ltm: 40,
      is_ftp_login: 0,
      ct_ftp_cmd: 0,
      ct_flw_http_mthd: 0,
      ct_src_ltm: 35,
      ct_srv_dst: 40,
      is_sm_ips_ports: 0,
    },
  },
  recon_portscan: {
    name: 'Port Scan Reconnaissance (High Port Count)',
    features: {
      dur: 0.000002,
      spkts: 1,
      dpkts: 0,
      sbytes: 44,
      dbytes: 0,
      rate: 500000.0,
      sttl: 64,
      dttl: 0,
      sload: 88000000.0,
      dload: 0.0,
      sloss: 0,
      dloss: 0,
      sinpkt: 0.002,
      dinpkt: 0.0,
      sjit: 0.0,
      djit: 0.0,
      swin: 1024,
      stcpb: 1000,
      dtcpb: 0,
      dwin: 0,
      tcprtt: 0.0,
      synack: 0.0,
      ackdat: 0.0,
      smean: 44,
      dmean: 0,
      trans_depth: 0,
      response_body_len: 0,
      ct_srv_src: 1,
      ct_state_ttl: 1,
      ct_dst_ltm: 12,
      ct_src_dport_ltm: 12,
      ct_dst_sport_ltm: 1,
      ct_dst_src_ltm: 1,
      is_ftp_login: 0,
      ct_ftp_cmd: 0,
      ct_flw_http_mthd: 0,
      ct_src_ltm: 12,
      ct_srv_dst: 1,
      is_sm_ips_ports: 0,
    },
  },
};

export default function Predictions() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectedModelId = searchParams.get('model_id');

  const [models, setModels] = useState([]);
  const [selectedModelId, setSelectedModelId] = useState(preselectedModelId || '');
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [predicting, setPredicting] = useState(false);

  // Form State
  const [featureJson, setFeatureJson] = useState(JSON.stringify(PRESETS.benign_web.features, null, 2));
  const [activePreset, setActivePreset] = useState('benign_web');
  const [latestResult, setLatestResult] = useState(null);
  const [error, setError] = useState(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [mRes, pRes] = await Promise.all([
        modelsApi.list({ skip: 0, limit: 100 }),
        predictionsApi.list({ skip: 0, limit: 50 }),
      ]);
      const mList = mRes?.models || [];
      setModels(mList);
      if (mList.length > 0 && !selectedModelId) {
        setSelectedModelId(mList[0].id);
      }
      setPredictions(pRes?.predictions || []);
    } catch (err) {
      setError(err.message || 'Failed to load models and prediction history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApplyPreset = (key) => {
    setActivePreset(key);
    if (PRESETS[key]) {
      setFeatureJson(JSON.stringify(PRESETS[key].features, null, 2));
    }
  };

  const handlePredict = async (e) => {
    e.preventDefault();
    if (!selectedModelId) {
      setError('Please select an active ML model from the registry.');
      return;
    }

    let parsedFeatures;
    try {
      parsedFeatures = JSON.parse(featureJson);
    } catch (err) {
      setError('Invalid JSON format for feature inputs.');
      return;
    }

    setPredicting(true);
    setError(null);
    setLatestResult(null);

    try {
      const payload = {
        model_id: selectedModelId,
        features: parsedFeatures,
        include_explanation: false,
      };
      const result = await predictionsApi.predict(payload);
      setLatestResult(result);
      loadData();
    } catch (err) {
      setError(err.message || 'Prediction failed.');
    } finally {
      setPredicting(false);
    }
  };

  if (loading) {
    return <Loader text="Loading inference workspace..." size="lg" />;
  }

  const isLatestAttack = latestResult?.predicted_class === 1 || latestResult?.predicted_class === 'ATTACK';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
            Inference & Prediction Workspace
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Classify network flow records, compute attack probability, and anchor every classification into the cryptographic audit ledger.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={loadData}>
          <RefreshCw size={14} /> Refresh History
        </button>
      </div>

      {error && (
        <Alert type="danger" title="Inference Error">
          {error}
        </Alert>
      )}

      {models.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <Activity size={40} style={{ color: 'var(--blue-primary)', margin: '0 auto 16px auto' }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '8px' }}>No Trained Models Available</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '480px', margin: '0 auto 20px auto' }}>
            To execute inference, train at least one Random Forest or Logistic Regression model in the Model Lab.
          </p>
          <button className="btn btn-primary" onClick={() => navigate('/models')}>
            Go to Model Lab
          </button>
        </div>
      ) : (
        <div className="grid-2" style={{ gridTemplateColumns: '1.2fr 1fr', alignItems: 'start' }}>
          {/* Inference Control Form */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <Play size={18} style={{ color: 'var(--cyan-neon)' }} />
                Network Flow Inference Console
              </div>
            </div>

            <form onSubmit={handlePredict}>
              <div className="form-group">
                <label className="form-label">Select Trained Model</label>
                <select
                  className="form-select"
                  value={selectedModelId}
                  onChange={(e) => setSelectedModelId(e.target.value)}
                  required
                >
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.model_type}) — Acc: {(m.accuracy * 100).toFixed(1)}%
                    </option>
                  ))}
                </select>
              </div>

              {/* Sample Preset Buttons */}
              <div className="form-group">
                <label className="form-label">Load Traffic Pattern Preset</label>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {Object.entries(PRESETS).map(([key, p]) => (
                    <button
                      type="button"
                      key={key}
                      className={`btn ${activePreset === key ? 'btn-primary' : 'btn-secondary'}`}
                      style={{ fontSize: '0.75rem', padding: '6px 10px' }}
                      onClick={() => handleApplyPreset(key)}
                    >
                      <Zap size={12} /> {p.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Feature Input JSON */}
              <div className="form-group">
                <label className="form-label">Flow Sample Features (JSON Schema)</label>
                <textarea
                  className="form-textarea font-mono"
                  rows={10}
                  value={featureJson}
                  onChange={(e) => setFeatureJson(e.target.value)}
                  style={{ fontSize: '0.78rem', lineHeight: '1.4' }}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                disabled={predicting || !selectedModelId}
                style={{ width: '100%', padding: '12px' }}
              >
                <Play size={16} className={predicting ? 'spinner' : ''} />
                {predicting ? 'Executing Inference & Hash Anchoring...' : 'Classify Traffic Flow'}
              </button>
            </form>
          </div>

          {/* Inference Result & Action Cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {latestResult ? (
              <div
                className="card"
                style={{
                  borderColor: isLatestAttack ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)',
                  background: isLatestAttack ? 'rgba(239, 68, 68, 0.05)' : 'rgba(16, 185, 129, 0.05)',
                }}
              >
                <div className="card-header">
                  <div className="card-title">
                    <Activity size={18} style={{ color: isLatestAttack ? 'var(--status-attack)' : 'var(--status-benign)' }} />
                    Inference Output
                  </div>
                  <StatusBadge status={isLatestAttack ? 'ATTACK' : 'BENIGN'} size="lg" />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div className="grid-2">
                    <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Classification</div>
                      <div
                        style={{
                          fontSize: '1.4rem',
                          fontWeight: '800',
                          color: isLatestAttack ? 'var(--status-attack)' : 'var(--status-benign)',
                        }}
                      >
                        {isLatestAttack ? 'ATTACK' : 'BENIGN'}
                      </div>
                    </div>

                    <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Confidence Score</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: '800', fontFamily: 'monospace', color: 'var(--cyan-neon)' }}>
                        {latestResult.probability !== undefined ? `${(latestResult.probability * 100).toFixed(2)}%` : '—'}
                      </div>
                    </div>
                  </div>

                  <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    <div>Prediction ID: <span className="hash-pill">{latestResult.id}</span></div>
                    <div style={{ marginTop: '4px' }}>Model: <span style={{ color: 'var(--text-primary)', fontWeight: '600' }}>{latestResult.model_name || selectedModelId}</span></div>
                  </div>

                  {/* Immediate Action Buttons */}
                  <div style={{ display: 'flex', gap: '10px', paddingTop: '8px' }}>
                    <button
                      className="btn btn-secondary"
                      style={{ flex: 1, fontSize: '0.78rem' }}
                      onClick={() => navigate(`/explainability?prediction_id=${latestResult.id}`)}
                    >
                      <Sparkles size={14} style={{ color: 'var(--purple-accent)' }} />
                      Explain with SHAP
                    </button>
                    <button
                      className="btn btn-secondary"
                      style={{ flex: 1, fontSize: '0.78rem' }}
                      onClick={() => navigate(`/audit?prediction_id=${latestResult.id}`)}
                    >
                      <ShieldCheck size={14} style={{ color: 'var(--cyan-neon)' }} />
                      View Audit Block
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="card" style={{ textAlign: 'center', padding: '36px 20px', color: 'var(--text-muted)' }}>
                <Activity size={32} style={{ margin: '0 auto 12px auto', opacity: 0.5 }} />
                <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
                  Awaiting Inference Execution
                </div>
                <div style={{ fontSize: '0.8rem' }}>
                  Select a preset and click "Classify Traffic Flow" to inspect prediction and generate cryptographic audit proof.
                </div>
              </div>
            )}

            {/* Prediction History Table */}
            <div className="card">
              <div className="card-header">
                <div className="card-title">
                  <Layers size={16} style={{ color: 'var(--text-muted)' }} />
                  Recent Inferences ({predictions.length})
                </div>
              </div>

              <div className="table-container" style={{ maxHeight: '280px', overflowY: 'auto' }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Class</th>
                      <th>Prob</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {predictions.slice(0, 10).map((p) => {
                      const isAtk = p.predicted_class === 1 || p.predicted_class === 'ATTACK';
                      return (
                        <tr key={p.id}>
                          <td style={{ fontSize: '0.72rem' }}>
                            {p.created_at ? new Date(p.created_at).toLocaleTimeString() : 'Recent'}
                          </td>
                          <td>
                            <StatusBadge status={isAtk ? 'ATTACK' : 'BENIGN'} />
                          </td>
                          <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                            {p.probability !== undefined ? `${(p.probability * 100).toFixed(1)}%` : '—'}
                          </td>
                          <td>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '3px 8px', fontSize: '0.68rem' }}
                              onClick={() => navigate(`/explainability?prediction_id=${p.id}`)}
                            >
                              SHAP
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
