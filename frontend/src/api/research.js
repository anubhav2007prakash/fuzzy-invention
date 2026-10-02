import { fetchApi } from './client';

/**
 * Research Suite API — benchmark, challenges, provenance, trust, notary,
 * reproducibility, plugins, modes, and collaboration/review.
 */

export const benchmarkApi = {
  /** Run the standardized protocol across sources */
  run: (config = {}) =>
    fetchApi('/benchmark/run', { method: 'POST', body: config }),

  /** Latest machine-generated benchmark report */
  report: () => fetchApi('/benchmark/report', { method: 'GET' }),

  /** Data sources + honest provenance labels */
  sources: () => fetchApi('/benchmark/sources', { method: 'GET' }),

  /** Pipeline stage timing breakdown */
  pipeline: (config = {}) =>
    fetchApi('/benchmark/pipeline', { method: 'POST', body: config }),

  /** Scalability sweep across data sizes */
  scalability: (config = {}) =>
    fetchApi('/benchmark/scalability', { method: 'POST', body: config }),

  /** Transparent experimental table with filters */
  leaderboard: (filters = {}) =>
    fetchApi('/benchmark/leaderboard', { params: filters }),
};

export const challengesApi = {
  presets: () => fetchApi('/research/challenges/presets'),
  define: (spec) => fetchApi('/research/challenges/define', { method: 'POST', body: spec }),
  run: (spec) => fetchApi('/research/challenges/run', { method: 'POST', body: spec }),
  list: () => fetchApi('/research/challenges'),
  get: (id) => fetchApi(`/research/challenges/${id}`),
};

export const provenanceApi = {
  graph: () => fetchApi('/research/provenance/graph'),
  lineage: () => fetchApi('/research/lineage'),
  node: (nodeId) => fetchApi(`/research/provenance/node/${encodeURIComponent(nodeId)}`),
  predictionTrust: (predictionId) =>
    fetchApi(`/research/trust/prediction/${predictionId}`),
  /** Transparent evidence checklist for an experiment node */
  experimentTrust: (expId) => fetchApi(`/experiments/${expId}/trust-checklist`),
};

export const notaryApi = {
  publicKey: () => fetchApi('/research/notary/public-key'),
  signExperiment: (experimentId) =>
    fetchApi('/research/notary/sign-experiment', { method: 'POST', body: { experiment_id: experimentId } }),
  verify: (artifact) =>
    fetchApi('/research/notary/verify', { method: 'POST', body: artifact }),
};

export const researchApi = {
  modelSelection: (config = {}) =>
    fetchApi('/research/model-selection/run', { method: 'POST', body: config }),
  modelCandidates: () => fetchApi('/research/model-selection/candidates'),
  robustness: (config = {}) =>
    fetchApi('/research/robustness/run', { method: 'POST', body: config }),
  manifest: (params = {}) =>
    fetchApi('/research/reproducibility/manifest', { params }),
  compareManifests: (a, b) =>
    fetchApi('/research/reproducibility/compare', { method: 'POST', body: { a, b } }),
  plugins: (kind) => fetchApi('/research/plugins', { params: kind ? { kind } : {} }),
  discoverPlugins: () => fetchApi('/research/plugins/discover', { method: 'POST', body: {} }),
  exportReproducibilityPackage: (expId, config = {}) =>
    fetchApi(`/experiments/${expId}/reproducibility-package`, { method: 'POST', body: config }),
};

export const modeApi = {
  get: () => fetchApi('/research/mode'),
  set: (mode) => fetchApi('/research/mode', { method: 'POST', body: { mode } }),
};

export const reviewApi = {
  record: (spec) => fetchApi('/collaboration/reviews', { method: 'POST', body: spec }),
  list: (filters = {}) => fetchApi('/collaboration/reviews', { params: filters }),
  stats: () => fetchApi('/collaboration/reviews/stats'),
};

export const collaborationApi = {
  status: (expId) => fetchApi(`/collaboration/experiments/${expId}/status`),
  updateState: (expId, spec) =>
    fetchApi(`/collaboration/experiments/${expId}/review-state`, { method: 'PUT', body: spec }),
  addComment: (expId, spec) =>
    fetchApi(`/collaboration/experiments/${expId}/comments`, { method: 'POST', body: spec }),
  comments: (expId) => fetchApi(`/collaboration/experiments/${expId}/comments`),
};
