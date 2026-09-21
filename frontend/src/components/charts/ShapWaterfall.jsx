import React from 'react';

export default function ShapWaterfall({ topFeatures = [], baseValue, predictionScore }) {
  if (!topFeatures || topFeatures.length === 0) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
        No feature attributions available.
      </div>
    );
  }

  // Find max absolute attribution for relative bar width calculation
  const maxAbsVal = Math.max(...topFeatures.map((f) => Math.abs(f.shap_value || f.attribution || 0)), 0.001);

  return (
    <div style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '14px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        <span>← Pushing towards Benign (Negative Impact)</span>
        <span>Pushing towards Attack (Positive Impact) →</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {topFeatures.map((feat, idx) => {
          const val = feat.shap_value ?? feat.attribution ?? 0;
          const isPositive = val >= 0;
          const barWidthPercent = Math.min(Math.round((Math.abs(val) / maxAbsVal) * 48), 48); // max 48% of track width
          const rawVal = feat.feature_value !== undefined ? String(feat.feature_value) : '';

          return (
            <div key={feat.feature_name || idx} className="shap-bar-container">
              <div className="shap-feature-name" title={feat.feature_name}>
                {feat.feature_name}
                {rawVal && (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem', marginLeft: '6px' }}>
                    ({Number(rawVal).toFixed ? Number(rawVal).toFixed(2) : rawVal})
                  </span>
                )}
              </div>

              <div className="shap-bar-track">
                <div className="shap-zero-line" />
                <div
                  className={`shap-bar-fill ${isPositive ? 'positive' : 'negative'}`}
                  style={{
                    width: `${barWidthPercent}%`,
                  }}
                  title={`Attribution: ${val.toFixed(4)}`}
                />
              </div>

              <div className="shap-val-label" style={{ color: isPositive ? 'var(--status-attack)' : 'var(--status-benign)' }}>
                {isPositive ? `+${val.toFixed(3)}` : val.toFixed(3)}
              </div>
            </div>
          );
        })}
      </div>

      {(baseValue !== undefined || predictionScore !== undefined) && (
        <div
          style={{
            marginTop: '16px',
            paddingTop: '12px',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.78rem',
            color: 'var(--text-secondary)',
          }}
        >
          {baseValue !== undefined && <div>Base / Expected Value: <span className="font-mono">{Number(baseValue).toFixed(4)}</span></div>}
          {predictionScore !== undefined && <div>Model Output Probability: <span className="font-mono">{Number(predictionScore).toFixed(4)}</span></div>}
        </div>
      )}
    </div>
  );
}
