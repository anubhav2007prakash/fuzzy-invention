import React from 'react';
import { Fingerprint } from 'lucide-react';

function Row({ label, value }) {
  return (
    <tr>
      <td>{label}</td>
      <td className="font-mono" style={{ wordBreak: 'break-all' }}>{value ?? 'unknown'}</td>
    </tr>
  );
}

export default function ReproducibilityPanel({ result }) {
  const manifest = result?.run_manifest || {};
  const environment = manifest.environment || {};
  const git = manifest.git || {};

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Fingerprint size={16} style={{ color: 'var(--cyan-neon)' }} />
            Reproducibility Manifest
          </div>
          <div className="card-subtitle">Configuration, environment, code version, and canonical hashes</div>
        </div>
      </div>

      <div className="table-container">
        <table className="table">
          <tbody>
            <Row label="Result Hash" value={result?.result_hash} />
            <Row label="Configuration Hash" value={result?.configuration_hash} />
            <Row label="Seed" value={manifest.random_seed} />
            <Row label="Result Artifact" value={manifest.result_artifact} />
            <Row label="Dataset Scope" value={manifest.dataset_scope} />
            <Row label="Git Commit" value={git.commit} />
            <Row label="Git Branch" value={git.branch} />
            <Row label="Dirty Worktree" value={String(git.dirty_worktree)} />
            <Row label="Python" value={environment.python_version} />
            <Row label="Platform" value={environment.platform} />
            <Row label="NumPy" value={environment.numpy_version} />
            <Row label="pandas" value={environment.pandas_version} />
            <Row label="scikit-learn" value={environment.sklearn_version} />
            <Row label="SHAP" value={environment.shap_version} />
          </tbody>
        </table>
      </div>
    </div>
  );
}
