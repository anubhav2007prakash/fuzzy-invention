import { fetchApi } from './client';

export const predictionsApi = {
  /**
   * Execute single prediction
   */
  predict: (payload) => {
    return fetchApi('/predictions', {
      method: 'POST',
      body: payload,
    });
  },

  /**
   * Execute batch prediction
   */
  predictBatch: (payload) => {
    return fetchApi('/predictions/batch', {
      method: 'POST',
      body: payload,
    });
  },

  /**
   * List historical predictions
   */
  list: (params = { skip: 0, limit: 100, model_id: null }) => {
    return fetchApi('/predictions', { method: 'GET', params });
  },

  /**
   * Get single prediction by ID
   */
  getById: (predictionId) => {
    return fetchApi(`/predictions/${predictionId}`, { method: 'GET' });
  },
};
