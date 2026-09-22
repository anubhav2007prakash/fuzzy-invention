import { fetchApi } from './client';

export const auditApi = {
  /**
   * List sequential audit records
   */
  listRecords: (params = { skip: 0, limit: 100 }) => {
    return fetchApi('/audit/records', { method: 'GET', params });
  },

  /**
   * Get audit record by record ID
   */
  getRecord: (recordId) => {
    return fetchApi(`/audit/records/${recordId}`, { method: 'GET' });
  },

  /**
   * Get audit record by prediction ID
   */
  getRecordByPrediction: (predictionId) => {
    return fetchApi(`/audit/predictions/${predictionId}`, { method: 'GET' });
  },

  /**
   * Get ledger health and latest status
   */
  getStatus: () => {
    return fetchApi('/audit/status', { method: 'GET' });
  },

  /**
   * Mathematically verify ledger chain integrity
   */
  verifyChain: (payload = { verify_entire_chain: true }) => {
    return fetchApi('/audit/verify', {
      method: 'POST',
      body: payload,
    });
  },

  /**
   * Export ledger records as JSON or CSV (returns file contents as text)
   */
  exportLedger: (format = 'json', params = {}) => {
    return fetchApi('/audit/export', {
      method: 'GET',
      params: { format, ...params },
    });
  },
};
