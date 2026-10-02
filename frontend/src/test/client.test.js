import { describe, it, expect, vi, afterEach } from 'vitest';
import { ApiError, fetchApi, BASE_URL } from '../api/client';

describe('BASE_URL resolution', () => {
  it('appends /api/v1 to an origin-only VITE_API_URL so it can never be dropped', () => {
    // Regression guard for the compose misconfiguration where
    // VITE_API_URL=http://backend:8000 produced http://backend:8000/experiments.
    expect(BASE_URL).toMatch(/\/api\/v1$/);
  });
});

describe('fetchApi error coercion', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const mockJsonResponse = (payload, status = 400) =>
    ({
      ok: false,
      status,
      statusText: 'Bad Request',
      headers: { get: (k) => (k === 'content-type' ? 'application/json' : null) },
      json: () => Promise.resolve(payload),
    });

  it('throws an ApiError whose message is ALWAYS a string for object detail envelopes', async () => {
    // Regression: {detail: {error: {...}}} used to render an object inside
    // Alert, blanking the Datasets page.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(mockJsonResponse({ detail: { error: { message: 'boom' } } }))
    );
    const err = await fetchApi('/x').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(typeof err.message).toBe('string');
    expect(err.message).toBe('boom');
  });

  it('uses detail.error.message from structured FastAPI envelopes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(mockJsonResponse({ detail: { error: { message: 'structured failure' } } }))
    );
    const err = await fetchApi('/x').catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe('structured failure');
    expect(typeof err.message).toBe('string');
  });

  it('JSON.stringifies detail objects without an .error.message key', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(mockJsonResponse({ detail: { reason: 'mismatch', code: 7 } }))
    );
    const err = await fetchApi('/x').catch((e) => e);
    expect(typeof err.message).toBe('string');
    expect(err.message).toContain('mismatch');
  });

  it('passes plain string detail through unchanged', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockJsonResponse({ detail: 'Not found' }, 404)));
    const err = await fetchApi('/x').catch((e) => e);
    expect(err.message).toBe('Not found');
    expect(err.status).toBe(404);
  });

  it('returns parsed JSON on success', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: { get: (k) => (k === 'content-type' ? 'application/json' : null) },
        json: () => Promise.resolve({ records: [] }),
      })
    );
    await expect(fetchApi('/ok')).resolves.toEqual({ records: [] });
  });
});
