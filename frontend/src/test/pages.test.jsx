import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from '../pages/Dashboard';
import Predictions from '../pages/Predictions';

// The pages pull four API modules; stub them all with the REAL response shapes
// from the backend schemas so any dead-field read shows up as '—' or a crash.
vi.mock('../api/datasets', () => ({
  datasetsApi: { list: vi.fn().mockResolvedValue({ datasets: [] }) },
}));
vi.mock('../api/models', () => ({
  modelsApi: {
    list: vi.fn().mockResolvedValue({
      models: [
        {
          id: 'm-1',
          name: 'Random Forest (synthetic)',
          version: 'v1.0.0',
          metrics: { accuracy: 0.9731, f1_macro: 0.9587, precision_macro: 0.9612 },
          feature_schema: [],
        },
      ],
    }),
  },
}));
vi.mock('../api/predictions', () => ({
  predictionsApi: {
    list: vi.fn().mockResolvedValue({
      predictions: [
        {
          prediction_id: 'p-1',
          model_id: 'm-1',
          predicted_class: '1',
          prediction_label: 1,
          probabilities: { '0': 0.05, '1': 0.95 },
          confidence: null,
          is_uncertain: false,
          input_hash: 'ab'.repeat(32),
          latency_ms: 3.2,
          created_at: '2026-09-23T10:00:00Z',
        },
      ],
    }),
    predict: vi.fn(),
  },
}));
vi.mock('../api/audit', () => ({
  auditApi: {
    getStatus: vi.fn().mockResolvedValue({
      total_records: 3,
      latest_sequence: 3,
      latest_record_hash: 'cd'.repeat(32),
      genesis_previous_hash: '0'.repeat(64),
      tamper_detected: false,
      is_intact: true,
      verification_message: 'ok',
    }),
    listRecords: vi.fn().mockResolvedValue({
      records: [
        {
          id: 'r-1',
          sequence_number: 1,
          prediction_id: 'p-1',
          payload_json: JSON.stringify({ predicted_class: '1', prediction_id: 'p-1' }),
          previous_hash: '0'.repeat(64),
          record_hash: 'cd'.repeat(32),
          created_at: '2026-09-23T10:00:00Z',
        },
      ],
      total: 1,
    }),
    verifyChain: vi.fn().mockResolvedValue({ verified: true, checked_records: 3, failed_records: [] }),
    exportLedger: vi.fn(),
  },
}));

function renderAt(node) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

describe('Dashboard dead-field regression', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders model rows from the metrics dict (accuracy/f1_macro), not dead top-level fields', async () => {
    renderAt(<Dashboard />);
    await waitFor(() => expect(screen.getByText('Random Forest (synthetic)')).toBeInTheDocument());
    // 97.31% comes from metrics.accuracy — a dead m.accuracy would render '—'.
    expect(screen.getByText('97.31%')).toBeInTheDocument();
    expect(screen.getByText('95.87%')).toBeInTheDocument();
  });

  it('renders recent-inference confidence from probabilities when confidence is null', async () => {
    renderAt(<Dashboard />);
    await waitFor(() => expect(screen.getByText('95.0%')).toBeInTheDocument());
  });

  it('marks the chain healthy from is_intact (dead is_valid would force healthy even when tampered)', async () => {
    renderAt(<Dashboard />);
    await waitFor(() => expect(screen.getByText(/SHA-256 Forward Linked/)).toBeInTheDocument());
  });
});

describe('Predictions dead-field regression', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the model option with name + metrics-dict F1 (no dead model_type/accuracy)', async () => {
    renderAt(<Predictions />);
    await waitFor(() =>
      expect(screen.getByRole('option', { name: /Random Forest \(synthetic\) — F1: 95\.9%/ })).toBeInTheDocument()
    );
  });

  it('renders history Prob column from probabilities (dead p.probability rendered — forever)', async () => {
    renderAt(<Predictions />);
    await waitFor(() => expect(screen.getByText('95.0%')).toBeInTheDocument());
    expect(screen.queryByText('—')).not.toBeInTheDocument();
  });
});
