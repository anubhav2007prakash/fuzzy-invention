/**
 * Shared formatting helpers — the single client-side map of backend response
 * shapes (PredictionResponse, ModelResponse, AuditRecordResponse). Pages must
 * read response fields through these helpers instead of guessing field names.
 */

/**
 * Prediction confidence: `confidence` is only set when a threshold was used,
 * so fall back to the max of the `probabilities` distribution.
 */
export function resolveConfidence(p) {
  if (!p) return undefined;
  if (typeof p.confidence === 'number') return p.confidence;
  if (p.probabilities && typeof p.probabilities === 'object') {
    const values = Object.values(p.probabilities).filter((v) => typeof v === 'number');
    if (values.length) return Math.max(...values);
  }
  return undefined;
}

/** Percent formatter that renders '—' for absent metrics. */
export function formatPercent(value, digits = 1) {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${(value * 100).toFixed(digits)}%`
    : '—';
}

/** predicted_class is stored as the strings '0'/'1'/'UNCERTAIN'. */
export function isAttackClass(predictedClass) {
  const s = String(predictedClass ?? '');
  return s === '1' || s.toUpperCase().includes('ATTACK');
}

export function isUncertainClass(predictedClass) {
  return String(predictedClass ?? '').toUpperCase().includes('UNCERTAIN');
}

/** ModelResponse has no model_type field; the name encodes it ("Random Forest (dataset)"). */
export function modelArchitecture(model) {
  return model?.name ? String(model.name).split(' (')[0] : '';
}

/** Audit payloads are persisted as canonical JSON strings. */
export function parseEvidencePayload(payloadJson) {
  if (!payloadJson) return null;
  if (typeof payloadJson === 'object') return payloadJson;
  try {
    return JSON.parse(payloadJson);
  } catch {
    return null;
  }
}
