import React, { useState, useRef } from 'react';
import Modal from '../common/Modal';
import { datasetsApi } from '../../api/datasets';
import { Upload, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import Alert from '../common/Alert';

export default function DatasetUploadModal({ isOpen, onClose, onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [datasetName, setDatasetName] = useState('');
  const [source, setSource] = useState('');
  const [targetColumn, setTargetColumn] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      if (!datasetName) {
        setDatasetName(selected.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a CSV dataset file.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    if (datasetName) formData.append('dataset_name', datasetName);
    if (source) formData.append('source', source);
    if (targetColumn) formData.append('target_column', targetColumn);

    try {
      const response = await datasetsApi.upload(formData);
      setIsSubmitting(false);
      onClose();
      if (onUploadSuccess) onUploadSuccess(response);
    } catch (err) {
      setIsSubmitting(false);
      setError(err.message || 'Failed to upload and validate dataset.');
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Upload & Ingest Network Flow Dataset"
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={isSubmitting || !file}>
            {isSubmitting ? 'Validating & Registering...' : 'Upload & Validate'}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit}>
        {error && (
          <Alert type="danger" title="Validation Failed">
            {error}
          </Alert>
        )}

        <div
          style={{
            border: '2px dashed var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '24px',
            textAlign: 'center',
            background: 'var(--bg-input)',
            cursor: 'pointer',
            marginBottom: '16px',
          }}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".csv"
            style={{ display: 'none' }}
          />
          <Upload size={32} style={{ color: 'var(--cyan-neon)', margin: '0 auto 10px auto' }} />
          {file ? (
            <div style={{ color: 'var(--status-benign)', fontWeight: '600' }}>
              Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
            </div>
          ) : (
            <div>
              <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
                Click to browse or drop CSV file
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Supports UNSW-NB15, CICIDS2017, and standard network flow schemas
              </div>
            </div>
          )}
        </div>

        <div className="form-group">
          <label className="form-label">Dataset Display Name</label>
          <input
            type="text"
            className="form-input"
            placeholder="e.g. UNSW-NB15 Flow Sample"
            value={datasetName}
            onChange={(e) => setDatasetName(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Source / Provenance</label>
          <input
            type="text"
            className="form-input"
            placeholder="e.g. Australian Centre for Cyber Security"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Custom Target Column (Optional)</label>
          <input
            type="text"
            className="form-input"
            placeholder="Auto-detected if blank (label, attack, class, target)"
            value={targetColumn}
            onChange={(e) => setTargetColumn(e.target.value)}
          />
        </div>
      </form>
    </Modal>
  );
}
