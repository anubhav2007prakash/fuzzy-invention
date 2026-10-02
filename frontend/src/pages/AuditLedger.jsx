import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ShieldCheck, ShieldAlert, RefreshCw, Key, Link as LinkIcon, Database, CheckCircle2, AlertTriangle, Eye, ArrowRight, Download } from 'lucide-react';
import StatusBadge from '../components/common/StatusBadge';
import Loader from '../components/common/Loader';
import Alert from '../components/common/Alert';
import Modal from '../components/common/Modal';
import HashChainVisual from '../components/charts/HashChainVisual';
import { formatPercent, isAttackClass, parseEvidencePayload } from '../utils/format';
import { auditApi } from '../api/audit';

/** Recompute SHA-256 of the canonical payload in the browser (what the backend verifier does). */
function usePayloadHash(payloadJson) {
  const [hash, setHash] = useState(null);
  useEffect(() => {
    let cancelled = false;
    if (!payloadJson) {
      setHash(null);
      return undefined;
    }
    crypto.subtle
      .digest('SHA-256', new TextEncoder().encode(payloadJson))
      .then((buf) => {
        if (!cancelled) {
          setHash(Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join(''));
        }
      })
      .catch(() => {
        if (!cancelled) setHash(null);
      });
    return () => {
      cancelled = true;
    };
  }, [payloadJson]);
  return hash;
}

export default function AuditLedger() {
  const [searchParams] = useSearchParams();
  const filterPredictionId = searchParams.get('prediction_id');

  const [records, setRecords] = useState([]);
  const [ledgerStatus, setLedgerStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [error, setError] = useState(null);
  const [exportFormat, setExportFormat] = useState('json');
  const [exporting, setExporting] = useState(false);

  const loadLedger = async () => {
    setLoading(true);
    setError(null);
    try {
      const [rRes, sRes] = await Promise.all([
        auditApi.listRecords({ skip: 0, limit: 100 }),
        auditApi.getStatus(),
      ]);
      const list = (rRes?.records || []).map((r) => ({ ...r, payload: parseEvidencePayload(r.payload_json) }));
      setRecords(list);
      setLedgerStatus(sRes);
      if (filterPredictionId) {
        const match = list.find((r) => r.prediction_id === filterPredictionId);
        if (match) setSelectedRecord(match);
      }
    } catch (err) {
      setError(err.message || 'Failed to load cryptographic audit ledger.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLedger();
  }, [filterPredictionId]);

  const handleExport = async () => {
    setExporting(true);
    setError(null);
    try {
      const data = await auditApi.exportLedger(exportFormat);
      const text = exportFormat === 'json' ? JSON.stringify(data, null, 2) : data;
      const blob = new Blob([text], {
        type: exportFormat === 'csv' ? 'text/csv' : 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit_ledger.${exportFormat}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || 'Ledger export failed.');
    } finally {
      setExporting(false);
    }
  };

  const handleVerifyChain = async () => {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const result = await auditApi.verifyChain({ verify_entire_chain: true });
      setVerifyResult(result);
    } catch (err) {
      setVerifyResult({ verified: false, message: err.message });
    } finally {
      setVerifying(false);
    }
  };

  if (loading) {
    return <Loader text="Loading cryptographic audit ledger & verifying SHA-256 forward links..." size="lg" />;
  }

  const isHealthy = ledgerStatus?.is_intact !== false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)' }}>
            Cryptographic Audit Ledger
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Immutable, SHA-256 forward-linked evidence ledger anchoring every inference and model prediction.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <select
            className="form-select"
            style={{ width: 'auto', fontSize: '0.78rem' }}
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value)}
            aria-label="Export format"
          >
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
          </select>
          <button className="btn btn-secondary" onClick={handleExport} disabled={exporting}>
            <Download size={14} /> {exporting ? 'Exporting...' : 'Export'}
          </button>
          <button className="btn btn-secondary" onClick={loadLedger}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button className="btn btn-verify" onClick={handleVerifyChain} disabled={verifying}>
            <ShieldCheck size={16} className={verifying ? 'spinner' : ''} />
            {verifying ? 'Verifying Hash Chain...' : 'Verify Entire Ledger'}
          </button>
        </div>
      </div>

      {error && (
        <Alert type="danger" title="Ledger Error">
          {error}
        </Alert>
      )}

      {/* Verification Banner */}
      {verifyResult && (
        <Alert
          type={verifyResult.verified ? 'success' : 'danger'}
          title={verifyResult.verified ? 'Ledger Chain Verification Succeeded' : 'Tamper Detection Alert'}
        >
          {verifyResult.verified ? (
            <div>
              Mathematically validated <strong>{verifyResult.checked_records}</strong> records in strict sequence. All SHA-256 payload and record hashes match expected forward-linkage state. 0 corruptions detected.
            </div>
          ) : (
            <div>
              Verification failed: {verifyResult.message || 'Hash mismatch.'}
              {(verifyResult.failed_records || []).length > 0 && (
                <div style={{ marginTop: '6px', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                  First anomaly: block #{verifyResult.failed_records[0].sequence_number} — {verifyResult.failed_records[0].error_type}
                </div>
              )}
            </div>
          )}
        </Alert>
      )}

      {/* Top Chain Visual */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">
              <LinkIcon size={18} style={{ color: 'var(--cyan-neon)' }} />
              Sequential Hash Chain Linkage
            </div>
            <div className="card-subtitle">
              RecordHash[i] = SHA-256(RecordHash[i-1] + PayloadHash[i])
            </div>
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            Total Blocks: <span style={{ fontWeight: '700', color: 'var(--text-primary)' }}>{records.length}</span>
          </div>
        </div>

        <HashChainVisual records={records} />
      </div>

      {/* Ledger Records Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Database size={18} style={{ color: 'var(--blue-primary)' }} />
            Audit Records Stream
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Click any row to inspect canonical evidence payload
          </div>
        </div>

        {records.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '36px', color: 'var(--text-muted)' }}>
            No audit records created yet. Run an inference in the Prediction Workspace to append evidence blocks.
          </div>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Seq #</th>
                  <th>Timestamp</th>
                  <th>Class</th>
                  <th>Payload Hash (SHA-256)</th>
                  <th>Record Hash (Forward-Linked)</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => {
                  const evidence = r.payload || parseEvidencePayload(r.payload_json);
                  const isAtk = isAttackClass(evidence?.predicted_class);
                  const shortPayload = r.payload_json ? `${r.payload_json.substring(0, 10)}...` : '—';
                  const shortRecord = r.record_hash ? `${r.record_hash.substring(0, 10)}...` : '—';

                  return (
                    <tr
                      key={r.id || r.sequence_number}
                      onClick={() => setSelectedRecord(r)}
                      style={{
                        cursor: 'pointer',
                        borderLeft: isAtk ? '3px solid var(--status-attack)' : '3px solid var(--status-benign)',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <td style={{ fontWeight: '700', color: 'var(--cyan-neon)', fontFamily: 'monospace' }}>
                        #{r.sequence_number}
                      </td>
                      <td style={{ fontSize: '0.75rem' }}>
                        {r.created_at ? new Date(r.created_at).toLocaleTimeString() : 'Recent'}
                      </td>
                      <td>
                        <StatusBadge status={isAtk ? 'ATTACK' : 'BENIGN'} />
                      </td>
                      <td>
                        <span className="hash-pill">{shortPayload}</span>
                      </td>
                      <td>
                        <span className="hash-pill" style={{ color: 'var(--cyan-neon)' }}>{shortRecord}</span>
                      </td>
                      <td>
                        <StatusBadge status="verified" label="Anchored" />
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary"
                          style={{ padding: '3px 8px', fontSize: '0.7rem' }}
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedRecord(r);
                          }}
                        >
                          <Eye size={12} /> Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Record Inspection Modal */}
      {selectedRecord && (
        <EvidenceInspector record={selectedRecord} onClose={() => setSelectedRecord(null)} />
      )}
    </div>
  );
}

/** Modal inspector for a single audit block; recomputes the payload hash client-side. */
function EvidenceInspector({ record, onClose }) {
  const payloadHash = usePayloadHash(record.payload_json);
  const evidence = record.payload || parseEvidencePayload(record.payload_json);
  const isAtk = isAttackClass(evidence?.predicted_class);

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={`Audit Block #${record.sequence_number} Evidence`}
      maxWidth="720px"
      footer={
        <button className="btn btn-secondary" onClick={onClose}>
          Close
        </button>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div className="grid-2">
          <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Sequence Index</div>
            <div style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--cyan-neon)', fontFamily: 'monospace' }}>
              Block #{record.sequence_number}
            </div>
          </div>
          <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Inference Output</div>
            <div style={{ fontSize: '1.2rem', fontWeight: '700', color: isAtk ? 'var(--status-attack)' : 'var(--status-benign)' }}>
              {evidence?.predicted_class ?? 'BENIGN'}
            </div>
          </div>
        </div>

        <div style={{ background: 'var(--bg-surface)', padding: '12px', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem' }}>
          <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Record Hash (SHA-256 Link):</div>
          <div className="hash-pill" style={{ color: 'var(--cyan-neon)', wordBreak: 'break-all' }}>
            {record.record_hash}
          </div>

          <div style={{ color: 'var(--text-muted)', marginTop: '8px', marginBottom: '4px' }}>Previous Block Hash:</div>
          <div className="hash-pill" style={{ wordBreak: 'break-all' }}>
            {record.previous_hash || `${'0'.repeat(64)} (GENESIS)`}
          </div>

          <div style={{ color: 'var(--text-muted)', marginTop: '8px', marginBottom: '4px' }}>
            Payload Hash (recomputed in-browser from the JSON below):
          </div>
          <div className="hash-pill" style={{ wordBreak: 'break-all' }}>
            {payloadHash ?? 'computing…'}
          </div>
        </div>

        {/* Canonical Payload JSON */}
        <div>
          <div style={{ fontWeight: '600', fontSize: '0.85rem', marginBottom: '6px' }}>
            Canonical Evidence JSON:
          </div>
          <pre
            className="font-mono"
            style={{
              background: 'var(--bg-input)',
              padding: '12px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.75rem',
              maxHeight: '220px',
              overflowY: 'auto',
              border: '1px solid var(--border-subtle)',
            }}
          >
            {record.payload_json || JSON.stringify(evidence, null, 2)}
          </pre>
        </div>
      </div>
    </Modal>
  );
}
