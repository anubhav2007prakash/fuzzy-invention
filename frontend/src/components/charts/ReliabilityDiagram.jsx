import React from 'react';

const PLOT = { left: 34, top: 12, width: 200, height: 180 };

function points(report) {
  return (report?.reliability_diagram?.bins || [])
    .filter((bin) => bin.sample_count > 0)
    .map((bin) => ({
      x: PLOT.left + bin.mean_predicted_probability * PLOT.width,
      y: PLOT.top + (1 - bin.observed_positive_frequency) * PLOT.height,
      count: bin.sample_count,
      predicted: bin.mean_predicted_probability,
      observed: bin.observed_positive_frequency,
    }));
}

function seriesPath(values) {
  return values.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ');
}

export default function ReliabilityDiagram({ before, after }) {
  const beforePoints = points(before);
  const afterPoints = points(after);

  if (!beforePoints.length && !afterPoints.length) return null;

  return (
    <div>
      <svg
        viewBox="0 0 250 220"
        role="img"
        aria-label="Reliability diagram comparing predicted positive probability with observed positive frequency"
        style={{ width: '100%', maxWidth: '360px', display: 'block', margin: '0 auto' }}
      >
        <line x1={PLOT.left} y1={PLOT.top} x2={PLOT.left} y2={PLOT.top + PLOT.height} stroke="var(--border-color)" />
        <line x1={PLOT.left} y1={PLOT.top + PLOT.height} x2={PLOT.left + PLOT.width} y2={PLOT.top + PLOT.height} stroke="var(--border-color)" />
        <line
          x1={PLOT.left}
          y1={PLOT.top + PLOT.height}
          x2={PLOT.left + PLOT.width}
          y2={PLOT.top}
          stroke="var(--text-muted)"
          strokeDasharray="4 4"
        />
        {[0, 0.5, 1].map((tick) => (
          <g key={tick}>
            <text x={PLOT.left - 7} y={PLOT.top + (1 - tick) * PLOT.height + 3} textAnchor="end" fontSize="8" fill="var(--text-muted)">{tick}</text>
            <text x={PLOT.left + tick * PLOT.width} y={PLOT.top + PLOT.height + 14} textAnchor="middle" fontSize="8" fill="var(--text-muted)">{tick}</text>
          </g>
        ))}
        {beforePoints.length > 1 && <path d={seriesPath(beforePoints)} fill="none" stroke="var(--blue-primary)" strokeWidth="1.5" />}
        {afterPoints.length > 1 && <path d={seriesPath(afterPoints)} fill="none" stroke="var(--cyan-neon)" strokeWidth="1.5" />}
        {beforePoints.map((point, index) => (
          <circle key={`before-${index}`} cx={point.x} cy={point.y} r="3" fill="var(--blue-primary)">
            <title>{`Before: predicted ${point.predicted.toFixed(3)}, observed ${point.observed.toFixed(3)}, n=${point.count}`}</title>
          </circle>
        ))}
        {afterPoints.map((point, index) => (
          <circle key={`after-${index}`} cx={point.x} cy={point.y} r="3" fill="var(--cyan-neon)">
            <title>{`After: predicted ${point.predicted.toFixed(3)}, observed ${point.observed.toFixed(3)}, n=${point.count}`}</title>
          </circle>
        ))}
        <text x="134" y="216" textAnchor="middle" fontSize="9" fill="var(--text-muted)">Mean predicted positive probability</text>
        <text transform="translate(9 105) rotate(-90)" textAnchor="middle" fontSize="9" fill="var(--text-muted)">Observed positive frequency</text>
      </svg>
      <div style={{ display: 'flex', justifyContent: 'center', gap: '14px', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
        <span><span style={{ color: 'var(--blue-primary)' }}>●</span> Before</span>
        {after && <span><span style={{ color: 'var(--cyan-neon)' }}>●</span> After calibration</span>}
        <span>Diagonal = ideal on evaluated sample</span>
      </div>
    </div>
  );
}
