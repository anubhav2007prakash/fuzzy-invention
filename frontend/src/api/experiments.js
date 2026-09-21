import { fetchApi } from './client';

export const experimentsApi = {
  /**
   * List all 4 research experiments and their stored status
   */
  list: () => {
    return fetchApi('/experiments', { method: 'GET' });
  },

  /**
   * Get details or stored result of an experiment
   */
  getById: (expId) => {
    return fetchApi(`/experiments/${expId}`, { method: 'GET' });
  },

  /**
   * Trigger live execution of an experiment
   */
  run: (expId, config = {}) => {
    return fetchApi(`/experiments/${expId}/run`, {
      method: 'POST',
      body: config,
    });
  },
};
