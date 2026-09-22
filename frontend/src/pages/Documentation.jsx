import React from 'react';
import { FileText, ShieldCheck, Key, BrainCircuit, Activity, Sparkles, BookOpen, Layers } from 'lucide-react';
import Alert from '../components/common/Alert';

export default function Documentation() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1000px' }}>
      {/* Header */}
      <div>
        <h2 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
          SentinelCrypt Architecture & System Documentation
        </h2>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
          Technical specifications, cryptographic ledger mathematics, XAI methodology, and development rules.
        </p>
      </div>

      {/* Section 1: Executive Overview */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <BookOpen size={18} style={{ color: 'var(--cyan-neon)' }} />
            System Architecture Overview
          </div>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          <strong>SentinelCrypt AI</strong> is a defensive cybersecurity and machine-learning research platform that solves the dual problems of <em>explainability opacity</em> and <em>alert tampering vulnerability</em> in AI-driven Network Intrusion Detection Systems (NIDS).
        </p>
      </div>

      {/* Section 2: Cryptographic Ledger Mathematics */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <ShieldCheck size={18} style={{ color: 'var(--status-benign)' }} />
            Cryptographic Audit Ledger Specification
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          <div>
            Every inference creates a canonical JSON evidence bundle containing:
            <ul style={{ paddingLeft: '24px', marginTop: '6px' }}>
              <li><strong>Sequence Number ($i$):</strong> Strictly monotonic integer identifier.</li>
              <li><strong>Timestamp:</strong> UTC ISO-8601 creation time.</li>
              <li><strong>Model Metadata:</strong> Model ID, architecture type, weights SHA-256 hash.</li>
              <li><strong>Input Features:</strong> Canonicalized dictionary of normalized flow attributes.</li>
              <li><strong>Inference Output:</strong> Predicted class and probability distribution.</li>
            </ul>
          </div>

          <div style={{ background: 'var(--bg-input)', padding: '14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontWeight: '700', color: 'var(--cyan-neon)', marginBottom: '6px' }}>
              Mathematical Hash Chain Forward-Linkage Formula:
            </div>
            <div className="font-mono" style={{ fontSize: '0.82rem', color: 'var(--text-primary)' }}>
              RecordHash[0] = SHA-256("GENESIS")<br />
              PayloadHash[i] = SHA-256(CanonicalJSON(Payload[i]))<br />
              RecordHash[i] = SHA-256(RecordHash[i-1] + PayloadHash[i])
            </div>
          </div>

          <Alert type="info">
            Any modification to past payload data ($Payload[i]$) or sequence alteration immediately invalidates the entire subsequent hash chain ($RecordHash[k]$ for all $k \ge i$), localizing the exact point of tampering.
          </Alert>
        </div>
      </div>

      {/* Section 3: Explainable AI */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Sparkles size={18} style={{ color: 'var(--purple-accent)' }} />
            Explainable AI (SHAP & Stability)
          </div>
        </div>

        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          <p>
            SentinelCrypt AI employs exact <strong>TreeSHAP</strong> (for Random Forest) and <strong>LinearSHAP</strong> (for Logistic Regression) to compute Shapley values $\phi_j(x)$ for each flow feature $x_j$, quantifying its positive (attack) or negative (benign) contribution to the decision boundary.
          </p>
        </div>
      </div>

      {/* Section 4: 7-Phase Roadmap */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Layers size={18} style={{ color: 'var(--blue-primary)' }} />
            7-Phase Research Roadmap
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: 'var(--status-benign)', fontWeight: '700' }}>✓ Phase 1:</span> Core Foundation & Dataset Ingestion
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: 'var(--status-benign)', fontWeight: '700' }}>✓ Phase 2:</span> Machine Learning Preprocessing & Model Registry
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: 'var(--status-benign)', fontWeight: '700' }}>✓ Phase 3:</span> Prediction & Business Services
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: 'var(--status-benign)', fontWeight: '700' }}>✓ Phase 4:</span> Cryptographic Audit Engine & Tamper Verifier
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: 'var(--status-benign)', fontWeight: '700' }}>✓ Phase 5:</span> Explainable AI (XAI) Engine & Stability Test
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: 'var(--status-benign)', fontWeight: '700' }}>✓ Phase 6:</span> React 18 + Vite Frontend Interface (Qronos Design System)
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: 'var(--status-benign)', fontWeight: '700' }}>✓ Phase 7:</span> Research Experiments (EXP-A to EXP-D), Evidence Export & Professor Mode
          </div>

        </div>
      </div>
    </div>
  );
}
