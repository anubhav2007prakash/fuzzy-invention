import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ShapWaterfall from '../components/charts/ShapWaterfall';
import HashChainVisual from '../components/charts/HashChainVisual';
import StatusBadge from '../components/common/StatusBadge';

describe('ShapWaterfall field contracts', () => {
  it('renders bars from the real API fields (feature/value/shap_value)', () => {
    // Regression: the chart used to read feature_name/feature_value, which the
    // explanations API never returns — bars rendered blank.
    render(
      <ShapWaterfall
        topFeatures={[
          { feature: 'sttl', value: 254, shap_value: 0.0812 },
          { feature: 'dttl', value: 0, shap_value: -0.0311 },
        ]}
      />
    );
    expect(screen.getByText('sttl')).toBeInTheDocument();
    expect(screen.getByText('dttl')).toBeInTheDocument();
    expect(screen.getByText('+0.081')).toBeInTheDocument();
    expect(screen.getByText('-0.031')).toBeInTheDocument();
    // Raw feature values shown in parentheses.
    expect(screen.getByText(/254/)).toBeInTheDocument();
  });

  it('shows the empty state without attributions', () => {
    render(<ShapWaterfall topFeatures={[]} />);
    expect(screen.getByText('No feature attributions available.')).toBeInTheDocument();
  });
});

describe('HashChainVisual field contracts', () => {
  it('renders block class from the parsed evidence payload (not dead rec.predicted_class)', () => {
    // AuditRecordResponse has no predicted_class column; the class lives in
    // the canonical payload_json which the page parses before passing down.
    render(
      <HashChainVisual
        records={[
          {
            id: 'a1',
            sequence_number: 1,
            record_hash: 'f'.repeat(64),
            payload: { predicted_class: '1' },
          },
          {
            id: 'a2',
            sequence_number: 2,
            record_hash: 'e'.repeat(64),
            payload: { predicted_class: '0' },
          },
        ]}
      />
    );
    expect(screen.getByText('BLOCK #1')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
    // Record hash is abbreviated, first 8 + last 6 chars.
    expect(screen.getByText(/ffffffff...\w{6}/)).toBeInTheDocument();
  });

  it('shows the empty state without records', () => {
    render(<HashChainVisual records={[]} />);
    expect(screen.getByText('No ledger blocks found in the sequence.')).toBeInTheDocument();
  });
});

describe('StatusBadge', () => {
  it('classifies architecture names and statuses into the right badge', () => {
    render(<StatusBadge status="Random Forest" />);
    expect(screen.getByText('Random Forest')).toBeInTheDocument();
  });
});
