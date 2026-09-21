import React, { useState } from 'react';
import Modal from '../common/Modal';
import { modelsApi } from '../../api/models';
import Alert from '../common/Alert';

export default function ModelTrainModal({ isOpen, onClose, datasets = [], onTrainSuccess }) {
  const [datasetId, setDatasetId] = useState(datasets[0]?.id || '');
  const [modelType, setModelType] = useState('random_forest');
  const [modelName, setModelName] = useState('Sentinel-RF-Classifier');
  const [testSize, setTestSize] = useState(0.2);
  const [randomState, setRandomState] = useState(42);
  const [isTraining, setIsTraining] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!datasetId) {
      setError('Please select a dataset to train on.');
      return;
    }

    setIsTraining(true);
    setError(null);

    const payload = {
      dataset_id: datasetId,
      model_type: modelType,
      name: modelName || `${modelType}-${Date.now()}`,
      hyperparameters: {
        test_size: parseFloat(testSize),
        random_state: parseInt(randomState, 10),
      },
    };

    try {
      const response = await modelsApi.train(payload);
      setIsTraining(false);
      onClose();
      if (onTrainSuccess) onTrainSuccess(response);
    } catch (err) {
      setIsTraining(false);
      setError(err.message || 'Model training failed.');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Train Intrusion Detection Model"
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose} disabled={isTraining}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={isTraining || !datasetId}>
            {isTraining ? 'Training & Evaluating...' : 'Start Training'}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit}>
        {error && (
          <Alert type="danger" title="Training Error">
            {error}
          </Alert>
        )}

        <div className="form-group">
          <label className="form-label">Target Dataset</label>
          <select
            className="form-select"
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
            required
          >
            <option value="">Select a registered dataset...</option>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.row_count?.toLocaleString()} rows, {d.feature_count} features)
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Algorithm Architecture</label>
          <select
            className="form-select"
            value={modelType}
            onChange={(e) => {
              setModelType(e.target.value);
              setModelName(e.target.value === 'random_forest' ? 'Sentinel-RF-Classifier' : 'Sentinel-LR-Classifier');
            }}
          >
            <option value="random_forest">Random Forest Classifier (Ensemble)</option>
            <option value="logistic_regression">Logistic Regression (Linear Baseline)</option>
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Model Identifier Name</label>
          <input
            type="text"
            className="form-input"
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            required
          />
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">Test Split Ratio</label>
            <input
              type="number"
              step="0.05"
              min="0.1"
              max="0.5"
              className="form-input"
              value={testSize}
              onChange={(e) => setTestSize(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Deterministic Seed (random_state)</label>
            <input
              type="number"
              className="form-input"
              value={randomState}
              onChange={(e) => setRandomState(e.target.value)}
            />
          </div>
        </div>

        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '8px' }}>
          * Evaluates precision, recall, F1, ROC-AUC, FPR, and persists trained weights into Model Registry.
        </div>
      </form>
    </Modal>
  );
}
