import React from 'react';
import { ShieldCheck, ArrowRight } from 'lucide-react';
import { isAttackClass } from '../../utils/format';

export default function HashChainVisual({ records = [] }) {
  const displayRecords = records.slice(-4); // show last 4 records

  if (displayRecords.length === 0) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
        No ledger blocks found in the sequence.
      </div>
    );
  }

  return (
    <div style={{ width: '100%', overflowX: 'auto', paddingBottom: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: '700px' }}>
        {displayRecords.map((rec, index) => {
          const isGenesis = rec.sequence_number === 1;
          const shortRecordHash = rec.record_hash ? `${rec.record_hash.substring(0, 8)}...${rec.record_hash.substring(rec.record_hash.length - 6)}` : 'GENESIS';

          return (
            <React.Fragment key={rec.id || rec.sequence_number || index}>
              <div
                style={{
                  flex: 1,
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-medium)',
                  borderRadius: 'var(--radius-md)',
                  padding: '14px',
                  boxShadow: '0 4px 16px rgba(0, 0, 0, 0.2)',
                  position: 'relative',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--cyan-neon)' }}>
                    BLOCK #{rec.sequence_number}
                  </span>
                  <span className="badge badge-benign" style={{ fontSize: '0.65rem' }}>
                    <ShieldCheck size={10} /> Verified
                  </span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.72rem' }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Class: </span>
                    <span style={{ color: isAttackClass(rec.payload?.predicted_class) ? 'var(--status-attack)' : 'var(--status-benign)', fontWeight: '600' }}>
                      {rec.payload?.predicted_class ?? (isGenesis ? 'GENESIS' : '—')}
                    </span>
                  </div>

                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Record SHA: </span>
                    <span className="hash-pill" style={{ fontSize: '0.68rem', color: 'var(--cyan-neon)' }}>{shortRecordHash}</span>
                  </div>
                </div>
              </div>

              {index < displayRecords.length - 1 && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', color: 'var(--cyan-neon)' }}>
                  <ArrowRight size={18} />
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px' }}>Link</span>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
