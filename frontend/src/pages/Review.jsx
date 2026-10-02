import React, { useEffect, useState } from 'react';
import { UserCheck, Users, Loader2, Send, MessageSquare } from 'lucide-react';
import Alert from '../components/common/Alert';
import StatusBadge from '../components/common/StatusBadge';
import { reviewApi, collaborationApi } from '../api/research';

const REVIEW_STATUSES = ['draft', 'under_review', 'changes_requested', 'approved'];

export default function Review() {
  // ── HITL state ──────────────────────────────────────────────────────────
  const [reviewForm, setReviewForm] = useState({ prediction_id: '', decision: 'confirmed', analyst: '', notes: '' });
  const [reviews, setReviews] = useState([]);
  const [stats, setStats] = useState(null);
  const [busyReview, setBusyReview] = useState(false);

  // ── Collaboration state ─────────────────────────────────────────────────
  const [expId, setExpId] = useState('EXP-A');
  const [expStatus, setExpStatus] = useState(null);
  const [stateForm, setStateForm] = useState({ owner: '', review_status: 'under_review', reviewer: '', approve: false });
  const [commentDraft, setCommentDraft] = useState({ author: '', body: '' });
  const [busyExp, setBusyExp] = useState(false);

  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const loadReviews = async () => {
    try {
      const [list, s] = await Promise.all([reviewApi.list({ limit: 50 }), reviewApi.stats()]);
      setReviews(list.reviews || []);
      setStats(s);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => { loadReviews(); }, []);

  const submitReview = async () => {
    if (!reviewForm.prediction_id.trim()) {
      setError('A prediction ID is required to record a review.');
      return;
    }
    setBusyReview(true);
    setError(null);
    setNotice(null);
    try {
      await reviewApi.record({
        prediction_id: reviewForm.prediction_id.trim(),
        decision: reviewForm.decision,
        analyst: reviewForm.analyst.trim() || 'analyst',
        notes: reviewForm.notes.trim() || null,
      });
      setNotice(`Review recorded for prediction ${reviewForm.prediction_id.slice(0, 8)}…`);
      setReviewForm({ prediction_id: '', decision: 'confirmed', analyst: reviewForm.analyst, notes: '' });
      await loadReviews();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyReview(false);
    }
  };

  const loadExpStatus = async (id = expId) => {
    setBusyExp(true);
    setError(null);
    try {
      const status = await collaborationApi.status(id.trim().toUpperCase());
      setExpStatus(status);
      setStateForm({
        owner: status.owner || '',
        review_status: status.review_status || 'under_review',
        reviewer: '',
        approve: false,
      });
    } catch (err) {
      setExpStatus(null);
      setError(err.message);
    } finally {
      setBusyExp(false);
    }
  };

  const saveState = async () => {
    setBusyExp(true);
    setError(null);
    try {
      setExpStatus(await collaborationApi.updateState(expId.trim().toUpperCase(), {
        owner: stateForm.owner.trim() || null,
        review_status: stateForm.review_status,
        reviewer: stateForm.reviewer.trim() || null,
        approve: stateForm.approve || null,
      }));
      setNotice(`Review state updated for ${expId.toUpperCase()}.`);
      await loadExpStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyExp(false);
    }
  };

  const addComment = async () => {
    if (!commentDraft.body.trim()) {
      setError('Comment body is required.');
      return;
    }
    setBusyExp(true);
    setError(null);
    try {
      setExpStatus(await collaborationApi.addComment(expId.trim().toUpperCase(), {
        author: commentDraft.author.trim() || 'researcher',
        body: commentDraft.body.trim(),
      }));
      setCommentDraft({ author: commentDraft.author, body: '' });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyExp(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          <UserCheck size={18} style={{ color: 'var(--cyan-neon)', marginRight: '8px', verticalAlign: '-3px' }} />
          Human Review &amp; Collaboration
        </h2>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
          Analyst decisions on model predictions (human-in-the-loop) and researcher collaboration
          states on experiments — ownership, review status, approval, and discussion threads.
        </p>
      </div>

      {error && <Alert type="danger" title="Error">{error}</Alert>}
      {notice && <Alert type="success">{notice}</Alert>}

      <div className="grid-2" style={{ alignItems: 'start', gap: '20px' }}>
        {/* HITL — record a review */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Record an Analyst Review</div>
            <div className="card-subtitle">Model prediction + explanation + human decision + audit evidence are stored together</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <input
              className="input"
              placeholder="Prediction ID (UUID)"
              value={reviewForm.prediction_id}
              onChange={(e) => setReviewForm({ ...reviewForm, prediction_id: e.target.value })}
            />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Decision
                <select className="input" value={reviewForm.decision}
                  onChange={(e) => setReviewForm({ ...reviewForm, decision: e.target.value })}>
                  <option value="confirmed">confirmed (agree with model)</option>
                  <option value="rejected">rejected (disagree with model)</option>
                </select>
              </label>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Analyst
                <input className="input" placeholder="name" value={reviewForm.analyst}
                  onChange={(e) => setReviewForm({ ...reviewForm, analyst: e.target.value })} />
              </label>
            </div>
            <textarea className="input" rows={2} placeholder="Notes (optional)"
              value={reviewForm.notes}
              onChange={(e) => setReviewForm({ ...reviewForm, notes: e.target.value })} />
            <button className="btn btn-primary" onClick={submitReview} disabled={busyReview}>
              {busyReview ? <Loader2 size={14} className="spinner" /> : <Send size={14} />} Record Review
            </button>
          </div>

          {/* Disagreement stats */}
          {stats && (
            <div style={{ marginTop: '14px', paddingTop: '12px', borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: '8px' }}>Model-vs-Human Disagreement</div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '8px' }}>
                <span className="badge badge-info">{stats.total_reviews} reviews</span>
                <span className="badge badge-benign">{stats.confirmed} confirmed</span>
                <span className="badge badge-attack">{stats.rejected} rejected</span>
                <span className="badge badge-warning">
                  Disagreement rate: {(100 * stats.disagreement_rate).toFixed(1)}%
                </span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{stats.interpretation}</div>
            </div>
          )}
        </div>

        {/* Collaboration — experiment review state */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><Users size={15} /> Experiment Collaboration</div>
            <div className="card-subtitle">Ownership · review workflow · evidence status</div>
          </div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <input className="input" placeholder="Experiment ID (e.g. EXP-A)" value={expId}
              onChange={(e) => setExpId(e.target.value)} />
            <button className="btn btn-secondary" onClick={() => loadExpStatus()} disabled={busyExp}>
              {busyExp ? <Loader2 size={14} className="spinner" /> : <Send size={14} />} Load
            </button>
          </div>

          {!expStatus ? (
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Load an experiment to view and edit its collaboration state.
            </p>
          ) : (
            <>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                <span className="badge badge-neutral">owner: {expStatus.owner || '—'}</span>
                <StatusBadge status={expStatus.review_status === 'approved' ? 'verified' : expStatus.review_status}
                  label={expStatus.review_status} />
                <span className="badge badge-info">evidence: {expStatus.evidence_status}</span>
                <span className="badge badge-purple">repro: {expStatus.reproducibility_status}</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '10px' }}>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Owner
                  <input className="input" value={stateForm.owner}
                    onChange={(e) => setStateForm({ ...stateForm, owner: e.target.value })} />
                </label>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Review status
                  <select className="input" value={stateForm.review_status}
                    onChange={(e) => setStateForm({ ...stateForm, review_status: e.target.value })}>
                    {REVIEW_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </label>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Reviewer
                  <input className="input" placeholder="name (required to approve)" value={stateForm.reviewer}
                    onChange={(e) => setStateForm({ ...stateForm, reviewer: e.target.value })} />
                </label>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'end', gap: '6px' }}>
                  <input type="checkbox" checked={stateForm.approve}
                    onChange={(e) => setStateForm({ ...stateForm, approve: e.target.checked })} />
                  Approve experiment
                </label>
              </div>
              <button className="btn btn-primary" onClick={saveState} disabled={busyExp} style={{ marginBottom: '14px' }}>
                {busyExp ? <Loader2 size={14} className="spinner" /> : <Send size={14} />} Save State
              </button>

              {/* Comments thread */}
              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
                <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: '8px' }}>
                  <MessageSquare size={13} style={{ verticalAlign: '-2px' }} /> Discussion ({expStatus.comments?.length || 0})
                </div>
                {(expStatus.comments || []).map((c) => (
                  <div key={c.id} style={{ fontSize: '0.76rem', padding: '5px 0', borderBottom: '1px dashed var(--border-subtle)' }}>
                    <span style={{ fontWeight: 700, color: 'var(--cyan-neon)' }}>{c.author}</span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: '6px' }}>{c.created_at?.slice(0, 19)}</span>
                    <div>{c.body}</div>
                  </div>
                ))}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px', marginTop: '10px' }}>
                  <input className="input" placeholder="author" value={commentDraft.author}
                    onChange={(e) => setCommentDraft({ ...commentDraft, author: e.target.value })} />
                  <input className="input" placeholder="add a comment…" value={commentDraft.body}
                    onChange={(e) => setCommentDraft({ ...commentDraft, body: e.target.value })}
                    onKeyDown={(e) => { if (e.key === 'Enter') addComment(); }} />
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Recent reviews table */}
      <div className="card">
        <div className="card-header"><div className="card-title">Recent Reviews</div></div>
        {reviews.length === 0 ? (
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            No reviews recorded yet — run a prediction in the Inference Console, then review it here.
          </p>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr><th>Prediction</th><th>Model said</th><th>Human decision</th><th>Analyst</th><th>Explanation</th><th>When</th></tr>
              </thead>
              <tbody>
                {reviews.map((r) => (
                  <tr key={r.id}>
                    <td className="hash-pill">{r.prediction_id?.slice(0, 12)}…</td>
                    <td><StatusBadge status={String(r.model_predicted_class).includes('attack') ? 'attack' : 'benign'}
                      label={r.model_predicted_class} /></td>
                    <td>
                      <span className={`badge ${r.human_decision === 'rejected' ? 'badge-attack' : 'badge-benign'}`}>
                        {r.human_decision}{r.disagrees_with_model ? ' (disagrees)' : ''}
                      </span>
                    </td>
                    <td>{r.analyst}</td>
                    <td style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      {r.explanation ? `${r.explanation.method} · stability ${r.explanation.stability_score ?? '—'}` : '—'}
                    </td>
                    <td style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{r.created_at?.slice(0, 19)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
