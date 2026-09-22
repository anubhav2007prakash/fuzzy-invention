import React, { useEffect, useState } from 'react';
import { BookOpenCheck, FlaskConical, Play, ShieldCheck, AlertTriangle, ArrowRight } from 'lucide-react';
import Alert from '../components/common/Alert';
import Loader from '../components/common/Loader';
import StatusBadge from '../components/common/StatusBadge';
import { experimentsApi } from '../api/experiments';

function Section({ title, icon: Icon, children }) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title">
          <Icon size={16} style={{ color: 'var(--cyan-neon)' }} />
          {title}
        </div>
      </div>
      {children}
    </div>
  );
}

export default function ProfessorMode() {
  const [summary, setSummary] = useState(null);
  const [expC, setExpC] = useState(null);
  const [loading, setLoading] = useState(true);
  const [runningDemo, setRunningDemo] = useState(false);
  const [error, setError] = useState(null);

  const loadSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await experimentsApi.presentationSummary();
      setSummary(data);
    } catch (err) {
      setError(err.message || 'Failed to load presentation summary.');
    } finally {
      setLoading(false);
    }
  };

  const runTamperDemo = async () => {
    setRunningDemo(true);
    setError(null);
    try {
      const result = await experimentsApi.run('EXP-C', { n_blocks: 50, random_state: 42 });
      setExpC(result);
      await loadSummary();
    } catch (err) {
      setError(err.message || 'Failed to run EXP-C tamper demonstration.');
    } finally {
      setRunningDemo(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, []);

  if (loading) {
    return <Loader text="Loading professor presentation mode..." />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>Professor Mode</h2>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-muted)' }}>
            A compact research presentation view backed by stored SentinelCrypt experiment evidence.
          </p>
        </div>
        <button className="btn btn-primary" onClick={runTamperDemo} disabled={runningDemo}>
          <Play size={14} className={runningDemo ? 'spinner' : ''} />
          {runningDemo ? 'Running EXP-C...' : 'Run Tamper Demo'}
        </button>
      </div>

      {error && <Alert type="danger" title="Professor Mode Error">{error}</Alert>}

      <Section title="Research Question" icon={BookOpenCheck}>
        <div style={{ fontSize: '1rem', color: 'var(--text-primary)', lineHeight: 1.6 }}>
          {summary?.research_question}
        </div>
      </Section>

      <div className="grid-2">
        <Section title="Methodology" icon={FlaskConical}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {(summary?.methodology || []).map((item, index) => (
              <div key={item} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                <span className="badge badge-info">{index + 1}</span>
                <span>{item}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Trustworthy ML Pipeline" icon={ShieldCheck}>
          <div className="table-container">
            <table className="table">
              <tbody>
                <tr><td>Datasets</td><td>{(summary?.datasets || []).map((d) => `${d.name} (${d.status})`).join(', ')}</td></tr>
                <tr><td>Models</td><td>{(summary?.models || []).join(', ')}</td></tr>
                <tr><td>XAI Method</td><td>{summary?.xai_method}</td></tr>
                <tr><td>Evidence</td><td>{summary?.cryptographic_evidence}</td></tr>
              </tbody>
            </table>
          </div>
        </Section>
      </div>

      <Section title="Experiments and Results" icon={FlaskConical}>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Experiment</th>
                <th>Status</th>
                <th>Latest Evidence Highlight</th>
              </tr>
            </thead>
            <tbody>
              {(summary?.experiments || []).map((experiment) => (
                <tr key={experiment.experiment_id}>
                  <td className="font-mono">{experiment.experiment_id}</td>
                  <td><StatusBadge status={experiment.status === 'COMPLETED' ? 'success' : 'pending'} label={experiment.status} /></td>
                  <td>{experiment.highlight}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Controlled Tampering Demonstration" icon={AlertTriangle}>
        {!expC ? (
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.86rem' }}>
            Run EXP-C to build a synthetic ledger, verify it, simulate controlled tampering, and show the detected failure locations.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <span className="badge badge-benign">Clean Chain: {expC.metrics?.clean_chain_valid ? 'Verified' : 'Failed'}</span>
              <span className="badge badge-info">Detection Rate: {expC.metrics?.tamper_detection_rate}</span>
              <span className="hash-pill">{expC.result_hash}</span>
            </div>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th>Target</th>
                    <th>Detected At</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(expC.metrics?.attacks_simulated || []).map((attack) => (
                    <tr key={attack.attack_type}>
                      <td>{attack.attack_type}</td>
                      <td className="font-mono">#{attack.tampered_sequence}</td>
                      <td className="font-mono">#{attack.detected_at_sequence}</td>
                      <td><StatusBadge status={attack.detected ? 'verified' : 'failed'} label={attack.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Section>

      <div className="grid-2">
        <Section title="Limitations" icon={AlertTriangle}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(summary?.limitations || []).map((item) => (
              <div key={item} style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                <ArrowRight size={13} style={{ marginRight: '8px', color: 'var(--status-warning)' }} />
                {item}
              </div>
            ))}
          </div>
        </Section>

        <Section title="Future Work" icon={BookOpenCheck}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(summary?.future_work || []).map((item) => (
              <div key={item} style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                <ArrowRight size={13} style={{ marginRight: '8px', color: 'var(--cyan-neon)' }} />
                {item}
              </div>
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}
