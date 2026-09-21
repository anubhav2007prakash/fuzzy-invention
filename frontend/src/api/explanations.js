import { fetchApi } from './client';

export const explanationsApi = {
  /**
   * Generate or regenerate SHAP explanation for a prediction
   */
  explain: (predictionId, payload = {}) => {
    return fetchApi(`/explanations/${predictionId}`, {
      method: 'POST',
      body: payload,
    });
  },

  /**
   * Get stored explanation by prediction ID
   */
  getByPredictionId: (predictionId) => {
    return fetchApi(`/explanations/${predictionId}`, { method: 'GET' });
  },

  /**
   * List stored explanations
   */
  list: (params = { skip: 0, limit: 100 }) => {
    return fetchApi('/explanations', { method: 'GET', params });
  },

  /**
   * Run standalone stability analysis (EXP-B)
   */
  computeStability: (predictionId, payload = {}) => {
    return fetchApi(`/explanations/stability/${predictionId}`, {
      method: 'POST',
      body: payload,
    });
  },
};
