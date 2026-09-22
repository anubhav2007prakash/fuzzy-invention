/**
 * SentinelCrypt AI API Client
 */

/**
 * API base URL — single source for fetchApi and Settings.
 *
 * VITE_API_URL may be an origin (`http://backend:8000`) or a full base
 * (`http://backend:8000/api/v1`); the `/api/v1` prefix is appended when
 * missing so configuration can never silently drop it.
 */
function resolveBaseUrl() {
  const raw = import.meta.env.VITE_API_URL;
  if (!raw) return '/api/v1';
  const trimmed = raw.replace(/\/+$/, '');
  return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`;
}

export const BASE_URL = resolveBaseUrl();

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export async function fetchApi(endpoint, options = {}) {
  const { params, body, headers, ...customConfig } = options;
  
  let url = `${BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, value);
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString;
    }
  }

  const isFormData = body instanceof FormData;
  const config = {
    method: options.method || (body ? 'POST' : 'GET'),
    headers: {
      ...(!isFormData && { 'Content-Type': 'application/json' }),
      ...headers,
    },
    ...customConfig,
  };

  if (body) {
    config.body = isFormData ? body : JSON.stringify(body);
  }

  try {
    const response = await fetch(url, config);
    
    // Handle 204 No Content
    if (response.status === 204) {
      return null;
    }

    let data;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      // ApiError.message must always be a string: FastAPI error envelopes put
      // structured objects under `detail` (e.g. {detail: {error: {...}}}), and
      // an object rendered inside Alert blanks the page.
      const detail = data?.detail;
      const detailMessage =
        typeof detail === 'string'
          ? detail
          : detail && typeof detail === 'object'
            ? detail?.error?.message || JSON.stringify(detail)
            : null;
      const errorMessage =
        data?.error?.message ||
        detailMessage ||
        `HTTP Error ${response.status}: ${response.statusText}`;
      throw new ApiError(String(errorMessage), response.status, data);
    }

    return data;
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(err.message || 'Network connection failed', 0, null);
  }
}
