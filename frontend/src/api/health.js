import { fetchApi } from './client';

export const healthApi = {
  check: () => {
    return fetchApi('/health', { method: 'GET' });
  },
};
