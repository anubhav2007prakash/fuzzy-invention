import { describe, it, expect } from 'vitest';
import {
  resolveConfidence,
  formatPercent,
  isAttackClass,
  isUncertainClass,
  modelArchitecture,
  parseEvidencePayload,
} from '../utils/format';

describe('resolveConfidence', () => {
  it('prefers the explicit confidence field (PredictionResponse.confidence)', () => {
    expect(resolveConfidence({ confidence: 0.87, probabilities: { '0': 0.13, '1': 0.87 } })).toBe(0.87);
  });

  it('falls back to max of the probabilities dict when confidence is absent (no threshold used)', () => {
    expect(resolveConfidence({ probabilities: { '0': 0.2, '1': 0.8 } })).toBe(0.8);
  });

  it('returns undefined for the dead `probability` field shape that used to break history tables', () => {
    // Regression: pages read p.probability which the API never returns.
    expect(resolveConfidence({ probability: 0.9 })).toBeUndefined();
    expect(resolveConfidence(null)).toBeUndefined();
  });
});

describe('formatPercent', () => {
  it('formats numbers as percentages', () => {
    expect(formatPercent(0.9234)).toBe('92.3%');
    expect(formatPercent(0.9234, 2)).toBe('92.34%');
  });

  it('renders an em-dash for absent/invalid values instead of NaN%', () => {
    expect(formatPercent(undefined)).toBe('—');
    expect(formatPercent(null)).toBe('—');
    expect(formatPercent('0.9')).toBe('—');
    expect(formatPercent(NaN)).toBe('—');
  });
});

describe('class-label classification', () => {
  it('treats string "1" and ATTACK as attacks (predicted_class is a string)', () => {
    expect(isAttackClass('1')).toBe(true);
    expect(isAttackClass('ATTACK')).toBe(true);
    expect(isAttackClass('0')).toBe(false);
    expect(isAttackClass('UNCERTAIN')).toBe(false);
  });

  it('detects UNCERTAIN regardless of case', () => {
    expect(isUncertainClass('UNCERTAIN')).toBe(true);
    expect(isUncertainClass('uncertain')).toBe(true);
    expect(isUncertainClass('0')).toBe(false);
  });
});

describe('modelArchitecture', () => {
  it('extracts the architecture from the encoded model name', () => {
    // Training service names models "Random Forest (dataset)".
    expect(modelArchitecture({ name: 'Random Forest (synthetic_flows)' })).toBe('Random Forest');
    expect(modelArchitecture({ name: 'Logistic Regression (ds)' })).toBe('Logistic Regression');
  });

  it('handles missing names', () => {
    expect(modelArchitecture(undefined)).toBe('');
    expect(modelArchitecture({})).toBe('');
  });
});

describe('parseEvidencePayload', () => {
  it('parses the canonical payload_json string from AuditRecordResponse', () => {
    const payload = { predicted_class: '1', prediction_id: 'abc' };
    expect(parseEvidencePayload(JSON.stringify(payload))).toEqual(payload);
  });

  it('passes through objects and returns null for garbage', () => {
    expect(parseEvidencePayload({ a: 1 })).toEqual({ a: 1 });
    expect(parseEvidencePayload('not json')).toBeNull();
    expect(parseEvidencePayload(null)).toBeNull();
  });
});
