import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import QuickFind from '../components/layout/QuickFind';

// Mock the entity APIs QuickFind deep-searches.
vi.mock('../api/datasets', () => ({
  datasetsApi: { list: vi.fn().mockResolvedValue({ datasets: [{ id: 'ds-1', name: 'UNSW-NB15 capture', row_count: 257673, validation_status: 'VALID' }] }) },
}));
vi.mock('../api/models', () => ({
  modelsApi: { list: vi.fn().mockResolvedValue({ models: [{ id: 'm-1', name: 'Random Forest (UNSW)', version: 'v1.0.0' }] }) },
}));
vi.mock('../api/predictions', () => ({
  predictionsApi: { list: vi.fn().mockResolvedValue({ predictions: [{ prediction_id: 'p-abc123', predicted_class: '1', confidence: 0.91, created_at: '2026-09-23T10:00:00Z' }] }) },
}));
vi.mock('../api/experiments', () => ({
  experimentsApi: { list: vi.fn().mockResolvedValue({ experiments: [{ experiment_id: 'EXP-A', status: 'COMPLETED', title: 'Cross-Dataset Generalization Gap' }] }) },
}));

const mockedNav = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockedNav };
});

function renderPalette() {
  return render(
    <MemoryRouter>
      <QuickFind />
    </MemoryRouter>
  );
}

describe('QuickFind', () => {
  beforeEach(() => {
    mockedNav.mockClear();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('does not render until opened', () => {
    renderPalette();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Search pages/)).not.toBeInTheDocument();
  });

  it('opens on the synthetic sidebar event (ctrl+meta+k) and real Ctrl+K', async () => {
    renderPalette();
    // Synthetic event dispatched by the sidebar button.
    fireEvent.keyDown(window, { key: 'k', metaKey: true, ctrlKey: true });
    expect(screen.getByPlaceholderText(/Search pages, datasets/)).toBeInTheDocument();
    // Toggle closed with a real-ish Ctrl+K.
    fireEvent.keyDown(window, { key: 'K', metaKey: true, ctrlKey: true });
    expect(screen.queryByPlaceholderText(/Search pages, datasets/)).not.toBeInTheDocument();
  });

  it('filters pages by query and navigates on Enter', async () => {
    const user = userEvent.setup();
    renderPalette();
    fireEvent.keyDown(window, { key: 'k', metaKey: true, ctrlKey: true });
    await user.type(screen.getByPlaceholderText(/Search pages, datasets/), 'audit');
    expect(screen.getByText('Audit Ledger')).toBeInTheDocument();
    expect(screen.queryByText('Model Lab')).not.toBeInTheDocument();
    await user.keyboard('{Enter}');
    expect(mockedNav).toHaveBeenCalledWith('/audit');
  });

  it('deep-searches registered entities and navigates to their landing routes', async () => {
    const user = userEvent.setup();
    renderPalette();
    fireEvent.keyDown(window, { key: 'k', metaKey: true, ctrlKey: true });
    await user.type(screen.getByPlaceholderText(/Search pages, datasets/), 'unsw');
    // Entity results load async after the palette opens.
    expect(await screen.findByText('UNSW-NB15 capture')).toBeInTheDocument();
    await user.keyboard('{Enter}');
    expect(mockedNav).toHaveBeenCalledWith('/datasets');
  });

  it('finds predictions by class/id and routes to SHAP explainability', async () => {
    const user = userEvent.setup();
    renderPalette();
    fireEvent.keyDown(window, { key: 'k', metaKey: true, ctrlKey: true });
    await user.type(screen.getByPlaceholderText(/Search pages, datasets/), 'p-abc');
    expect(await screen.findByText(/p-abc123/)).toBeInTheDocument();
    await user.keyboard('{Enter}');
    expect(mockedNav).toHaveBeenCalledWith('/explainability?prediction_id=p-abc123');
  });

  it('shows an empty state for unmatched queries', async () => {
    const user = userEvent.setup();
    renderPalette();
    fireEvent.keyDown(window, { key: 'k', metaKey: true, ctrlKey: true });
    await user.type(screen.getByPlaceholderText(/Search pages, datasets/), 'zzzznothing');
    expect(screen.getByText(/No pages or records match/)).toBeInTheDocument();
  });
});
