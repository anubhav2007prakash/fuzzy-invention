import { fetchApi } from './client';

export const datasetsApi = {
  /**
   * List registered datasets
   */
  list: (params = { skip: 0, limit: 50 }) => {
    return fetchApi('/datasets', { method: 'GET', params });
  },

  /**
   * Get dataset by ID with full column metadata
   */
  getById: (datasetId) => {
    return fetchApi(`/datasets/${datasetId}`, { method: 'GET' });
  },

  /**
   * Upload and register a new dataset CSV
   */
  upload: (formData) => {
    return fetchApi('/datasets', {
      method: 'POST',
      body: formData,
    });
  },

  /**
   * Preview first N rows + column statistics
   */
  preview: (datasetId, nRows = 10) => {
    return fetchApi(`/datasets/${datasetId}/preview`, {
      method: 'GET',
      params: { n_rows: nRows },
    });
  },
};
