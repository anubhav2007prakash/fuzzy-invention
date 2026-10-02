import { fetchApi } from './client';

export const falsificationApi = {
  /**
   * Create a new falsification claim
   */
  createClaim: (claimId, claimStatement, baselineConfiguration, alternativeConfiguration, perturbationConfiguration, alternativeDatasetId, nRepeats, randomSeed) => {
    return fetchApi('/falsification/claims', {
      method: 'POST',
      body: {
        claim_id: claimId,
        claim_statement: claimStatement,
        baseline_configuration: baselineConfiguration,
        alternative_configuration: alternativeConfiguration,
        perturbation_configuration: perturbationConfiguration,
        alternative_dataset_id: alternativeDatasetId,
        n_repeats: nRepeats,
        random_seed: randomSeed,
      },
    });
  },

  /**
   * List all falsification claims
   */
  listClaims: () => {
    return fetchApi('/falsification/claims', { method: 'GET' });
  },

  /**
   * Get a specific falsification claim details
   */
  getClaim: (claimId) => {
    return fetchApi(`/falsification/claims/${claimId}`, { method: 'GET' });
  },

  /**
   * Execute falsification experiment for a claim
   */
  runClaimExperiment: (claimId, config) => {
    return fetchApi(`/falsification/claims/${claimId}/run`, {
      method: 'POST',
      body: config,
    });
  },

  /**
   * Set acceptance criteria for a claim
   */
  setAcceptanceCriteria: (claimId, criteria) => {
    return fetchApi(`/falsification/claims/${claimId}/acceptance-criteria`, {
      method: 'POST',
      body: criteria,
    });
  },

  /**
   * Get valid conclusion status values
   */
  getConclusionStatuses: () => {
    return fetchApi('/falsification/conclusion-statuses', { method: 'GET' });
  },
};