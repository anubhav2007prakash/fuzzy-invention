import { fetchApi } from './client';

export const healthApi = {
  check: () => {
    return fetchApi('/health', { method: 'GET' });
  },

  /**
   * Detailed health: DB connectivity, alembic version, component counts
   */
  detailed: () => {
    return fetchApi('/health/detailed', { method: 'GET' });
  },
};
