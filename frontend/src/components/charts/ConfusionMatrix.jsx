import React from 'react';

export default function ConfusionMatrix({ matrix }) {
  if (!matrix) {
    return <div style={{ color: 'var(--text-muted)' }}>No confusion matrix data.</div>;
  }

  // Expecting { tn, fp, fn, tp } or 2x2 array [[tn, fp], [fn, tp]]
  let tn = 0, fp = 0, fn = 0, tp = 0;
  if (Array.isArray(matrix)) {
    tn = matrix[0]?.[0] || 0;
    fp = matrix[0]?.[1] || 0;
    fn = matrix[1]?.[0] || 0;
    tp = matrix[1]?.[1] || 0;
  } else {
    tn = matrix.tn ?? matrix.true_negative ?? 0;
    fp = matrix.fp ?? matrix.false_positive ?? 0;
    fn = matrix.fn ?? matrix.false_negative ?? 0;
    tp = matrix.tp ?? matrix.true_positive ?? 0;
  }

  const total = tn + fp + fn + tp || 1;
  const accuracy = ((tp + tn) / total) * 100;
  const precision = tp + fp > 0 ? (tp / (tp + fp)) * 100 : 0;
  const recall = tp + fn > 0 ? (tp / (tp + fn)) * 100 : 0;
  const fpr = fp + tn > 0 ? (fp / (fp + tn)) * 100 : 0;

  return (
    <div style={{ width: '100%' }}>
      <div className="confusion-matrix-grid">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Actual \ Pred
        </div>
        <div style={{ fontWeight: '600', fontSize: '0.78rem', color: 'var(--status-benign)' }}>
          Predicted BENIGN
        </div>
        <div style={{ fontWeight: '600', fontSize: '0.78rem', color: 'var(--status-attack)' }}>
          Predicted ATTACK
        </div>

        {/* Row 1: Actual BENIGN */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '600', fontSize: '0.78rem', color: 'var(--status-benign)' }}>
          Actual BENIGN
        </div>
        <div className="cm-cell highlight">
          <div className="cm-value" style={{ color: 'var(--status-benign)' }}>{tn.toLocaleString()}</div>
          <div className="cm-subtext">True Negative (TN)</div>
        </div>
        <div className="cm-cell" style={{ background: fp > 0 ? 'rgba(239, 68, 68, 0.08)' : undefined }}>
          <div className="cm-value" style={{ color: fp > 0 ? 'var(--status-attack)' : 'var(--text-primary)' }}>{fp.toLocaleString()}</div>
          <div className="cm-subtext">False Positive (FP)</div>
        </div>

        {/* Row 2: Actual ATTACK */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: '600', fontSize: '0.78rem', color: 'var(--status-attack)' }}>
          Actual ATTACK
        </div>
        <div className="cm-cell" style={{ background: fn > 0 ? 'rgba(245, 158, 11, 0.08)' : undefined }}>
          <div className="cm-value" style={{ color: fn > 0 ? 'var(--status-warning)' : 'var(--text-primary)' }}>{fn.toLocaleString()}</div>
          <div className="cm-subtext">False Negative (FN)</div>
        </div>
        <div className="cm-cell highlight">
          <div className="cm-value" style={{ color: 'var(--cyan-neon)' }}>{tp.toLocaleString()}</div>
          <div className="cm-subtext">True Positive (TP)</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginTop: '16px' }}>
        <div style={{ background: 'var(--bg-surface)', padding: '8px 12px', borderRadius: '4px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Accuracy</div>
          <div style={{ fontWeight: '700', fontSize: '0.9rem', color: 'var(--text-primary)' }}>{accuracy.toFixed(2)}%</div>
        </div>
        <div style={{ background: 'var(--bg-surface)', padding: '8px 12px', borderRadius: '4px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Precision</div>
          <div style={{ fontWeight: '700', fontSize: '0.9rem', color: 'var(--text-primary)' }}>{precision.toFixed(2)}%</div>
        </div>
        <div style={{ background: 'var(--bg-surface)', padding: '8px 12px', borderRadius: '4px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Recall / TPR</div>
          <div style={{ fontWeight: '700', fontSize: '0.9rem', color: 'var(--text-primary)' }}>{recall.toFixed(2)}%</div>
        </div>
        <div style={{ background: 'var(--bg-surface)', padding: '8px 12px', borderRadius: '4px', textAlign: 'center' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>FPR</div>
          <div style={{ fontWeight: '700', fontSize: '0.9rem', color: 'var(--status-warning)' }}>{fpr.toFixed(2)}%</div>
        </div>
      </div>
    </div>
  );
}
