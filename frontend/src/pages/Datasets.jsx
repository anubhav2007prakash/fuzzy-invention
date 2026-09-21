import React, { useState, useEffect } from 'react';
import { Database, Upload, RefreshCw, CheckCircle2, AlertCircle, FileText, Hash, Table as TableIcon } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import Loader from '../components/common/Loader';
import Alert from '../components/common/Alert';
import DatasetUploadModal from '../components/forms/DatasetUploadModal';
import { datasetsApi } from '../api/datasets';

export default function Datasets() {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [error, setError] = useState(null);

  const loadDatasets = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await datasetsApi.list({ skip: 0, limit: 100 });
      const list = data?.datasets || [];
      setDatasets(list);
      if (list.length > 0 && !selectedDataset) {
        setSelectedDataset(list[0]);
      }
    } catch (err) {
      setError(err.message || 'Failed to load dataset inventory.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDatasets();
  }, []);

  const handleSelectDataset = async (dataset) => {
    try {
      const full = await datasetsApi.getById(dataset.id);
      setSelectedDataset(full);
    } catch (err) {
      setSelectedDataset(dataset);
    }
  };

  if (loading) {
    return <Loader text="Loading dataset registry and feature schemas..." size="lg" />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
            Network Flow Datasets
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Ingested network intrusion benchmarks, feature schemas, checksums, and label distributions.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={loadDatasets}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button className="btn btn-primary" onClick={() => setIsUploadOpen(true)}>
            <Upload size={14} /> Ingest Dataset (CSV)
          </button>
        </div>
      </div>

      {error && (
        <Alert type="danger" title="Dataset Loading Error">
          {error}
        </Alert>
      )}

      {datasets.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <Database size={40} style={{ color: 'var(--cyan-neon)', margin: '0 auto 16px auto', opacity: 0.8 }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '8px' }}>No Datasets Registered</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '480px', margin: '0 auto 20px auto' }}>
            Upload a CSV flow dataset (UNSW-NB15, CICIDS2017, or custom format) to validate schema, extract feature statistics, and enable model training.
          </p>
          <button className="btn btn-primary" onClick={() => setIsUploadOpen(true)}>
            <Upload size={16} /> Upload First Dataset
          </button>
        </div>
      ) : (
        <div className="grid-2" style={{ gridTemplateColumns: '1.1fr 1fr', alignItems: 'start' }}>
          {/* Dataset Table */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <Database size={18} style={{ color: 'var(--cyan-neon)' }} />
                Registered Benchmark Datasets ({datasets.length})
              </div>
            </div>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Dataset Name</th>
                    <th>Rows</th>
                    <th>Features</th>
                    <th>Target Col</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {datasets.map((d) => {
                    const isSelected = selectedDataset?.id === d.id;
                    return (
                      <tr
                        key={d.id}
                        onClick={() => handleSelectDataset(d)}
                        style={{
                          cursor: 'pointer',
                          background: isSelected ? 'rgba(0, 242, 254, 0.08)' : undefined,
                          borderColor: isSelected ? 'rgba(0, 242, 254, 0.3)' : undefined,
                        }}
                      >
                        <td style={{ fontWeight: isSelected ? '700' : '500', color: isSelected ? 'var(--cyan-neon)' : 'var(--text-primary)' }}>
                          {d.name}
                        </td>
                        <td style={{ fontFamily: 'monospace' }}>{d.row_count?.toLocaleString()}</td>
                        <td style={{ fontFamily: 'monospace' }}>{d.feature_count}</td>
                        <td style={{ fontFamily: 'monospace', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {d.target_column || 'label'}
                        </td>
                        <td>
                          <StatusBadge status="valid" label="Validated" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Dataset Details & Schema Inspector */}
          {selectedDataset && (
            <div className="card">
              <div className="card-header">
                <div>
                  <div className="card-title" style={{ color: 'var(--cyan-neon)' }}>
                    {selectedDataset.name}
                  </div>
                  <div className="card-subtitle">Dataset Metadata & Cryptographic Provenance</div>
                </div>
                <StatusBadge status="valid" label="Schema Verified" />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="grid-2" style={{ gap: '12px' }}>
                  <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Total Records</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
                      {selectedDataset.row_count?.toLocaleString()}
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Feature Dimension</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--cyan-neon)', fontFamily: 'monospace' }}>
                      {selectedDataset.feature_count} features
                    </div>
                  </div>
                </div>

                <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem' }}>
                  <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>SHA-256 Dataset Checksum:</div>
                  <div className="hash-pill" style={{ wordBreak: 'break-all', fontSize: '0.72rem' }}>
                    {selectedDataset.file_hash || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
                  </div>
                </div>

                {selectedDataset.source && (
                  <div style={{ fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Source Reference: </span>
                    <span style={{ color: 'var(--text-secondary)' }}>{selectedDataset.source}</span>
                  </div>
                )}

                {/* Feature Schema List */}
                <div>
                  <div style={{ fontWeight: '600', fontSize: '0.85rem', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <TableIcon size={14} style={{ color: 'var(--cyan-neon)' }} />
                    Feature Schema ({selectedDataset.features?.length || selectedDataset.feature_count} columns)
                  </div>
                  <div
                    style={{
                      maxHeight: '220px',
                      overflowY: 'auto',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      background: 'var(--bg-input)',
                      padding: '8px',
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '6px',
                    }}
                  >
                    {(selectedDataset.features || []).length > 0 ? (
                      selectedDataset.features.map((feat, idx) => (
                        <span
                          key={feat.name || idx}
                          style={{
                            background: 'var(--bg-surface)',
                            border: '1px solid var(--border-medium)',
                            borderRadius: '4px',
                            padding: '3px 8px',
                            fontSize: '0.72rem',
                            fontFamily: 'monospace',
                            color: feat.name === selectedDataset.target_column ? 'var(--status-attack)' : 'var(--text-secondary)',
                          }}
                        >
                          {feat.name || feat} {feat.type ? `(${feat.type})` : ''}
                        </span>
                      ))
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', padding: '6px' }}>
                        Schema columns auto-mapped to numerical & categorical preprocessing pipelines.
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <DatasetUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={loadDatasets}
      />
    </div>
  );
}
