import { fetchApi } from './client';

export const modelsApi = {
  /**
   * List trained models
   */
  list: (params = { skip: 0, limit: 100 }) => {
    return fetchApi('/models', { method: 'GET', params });
  },

  /**
   * Get model metadata
   */
  getById: (modelId) => {
    return fetchApi(`/models/${modelId}`, { method: 'GET' });
  },

  /**
   * Get comprehensive metrics and confusion matrix
   */
  getMetrics: (modelId) => {
    return fetchApi(`/models/${modelId}/metrics`, { method: 'GET' });
  },

  /**
   * Train a new model
   */
  train: (payload) => {
    return fetchApi('/models/train', {
      method: 'POST',
      body: payload,
    });
  },

  /**
   * Delete a model
   */
  delete: (modelId) => {
    return fetchApi(`/models/${modelId}`, { method: 'DELETE' });
  },
};
