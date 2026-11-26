import { useCallback, useEffect, useState } from 'react'
import { Check, CircleAlert, RefreshCw, ShieldQuestion } from 'lucide-react'
import { motion } from 'framer-motion'
import { api, pretty } from '../services/api'
import { EmptyState, ErrorState, LoadingBlock, StatePill } from '../components/Primitives'
import HolographicConflictView from '../components/HolographicConflictView'

const FILTERS = ['all', 'open', 'under_review', 'resolved', 'dismissed']

export default function ContradictionsPage({ onOpenDocument }) {
  const [items, setItems] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try { const result = await api(`/api/contradictions?limit=200${filter === 'all' ? '' : `&status=${filter}`}`); setItems(result.items) }
    catch (cause) { setError(cause.message) } finally { setLoading(false) }
  }, [filter])
  useEffect(() => { refresh() }, [refresh])

  async function analyzeClaims() {
    setAnalyzing(true); setError(''); setNotice('')
    try {
      const result = await api('/api/claims/normalize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
      setNotice(`${result.normalized} new claims normalized · ${result.conflicts_created} findings created · graph now has ${result.graph_nodes} nodes and ${result.graph_edges} links.`)
      await refresh()
    } catch (cause) { setError(cause.message) } finally { setAnalyzing(false) }
  }

  async function setStatus(conflict, status) {
    setBusyId(conflict.id); setError(''); setNotice('')
    try {
      await api(`/api/contradictions/${conflict.id}/resolve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, note: null }) })
      setNotice(`Finding #${conflict.id} moved to ${pretty(status)}. The backend recorded the review action.`)
      await refresh()
    } catch (cause) { setError(cause.message) } finally { setBusyId(null) }
  }

  return <div className="page-stack">
    <div className="page-intro"><div><div className="eyebrow">PHASE 5 · HUMAN REVIEW</div><h1>Contradiction centre</h1><p>Compare both claims with source provenance. Findings describe differences; the system does not choose which source is true.</p></div><div className="page-intro-actions"><button className="button secondary" onClick={analyzeClaims} disabled={analyzing} aria-label="Normalize new claims and detect contradictions">{analyzing ? <><RefreshCw size={14} className="spin" /> Analyzing…</> : <><ShieldQuestion size={14} /> Analyze new claims</>}</button><button className="icon-button" onClick={refresh} aria-label="Refresh conflict findings"><RefreshCw size={16} /></button></div></div>
    <div className="conflict-toolbar panel"><div className="filter-tabs" role="tablist" aria-label="Filter findings">{FILTERS.map((status) => <button key={status} className={filter === status ? 'active' : ''} role="tab" aria-selected={filter === status} onClick={() => setFilter(status)}>{status === 'all' ? 'All findings' : pretty(status)}</button>)}</div><span><ShieldQuestion size={14} /> Review outcomes are auditable</span></div>
    {notice && <div className="notice-banner" role="status">{notice}</div>}{error && <ErrorState message={error} onRetry={refresh} />}
    {loading ? <LoadingBlock label="Loading conflict findings" /> : items.length ? <div className="conflict-list">{items.map((conflict) => <ConflictCard key={conflict.id} conflict={conflict} busy={busyId === conflict.id} onOpenDocument={onOpenDocument} onSetStatus={setStatus} />)}</div> : <EmptyState icon={CircleAlert} title="No findings in this view" detail={filter === 'all' ? 'No conflict findings are stored yet. Process and normalize evidence to create deterministic comparisons.' : `There are no ${pretty(filter).toLowerCase()} findings.`} />}
  </div>
}

function ConflictCard({ conflict, busy, onOpenDocument, onSetStatus }) {
  const a = conflict.claim_a, b = conflict.claim_b
  return <motion.article className="panel conflict-card" layout>
    <div className="conflict-card-heading"><div><span className="conflict-id">FINDING #{conflict.id}</span><h3>{pretty(conflict.classification)}</h3></div><StatePill state={conflict.status}>{pretty(conflict.status)}</StatePill></div>
    <div className="conflict-tags"><span>{pretty(conflict.conflict_category || 'unclassified')}</span>{conflict.confidence != null && <span>Heuristic {Math.round(conflict.confidence * 100)}%</span>}<small>{conflict.confidence_note}</small></div>
    <HolographicConflictView conflict={conflict} onOpenDocument={onOpenDocument} />
    {conflict.explanation && <p className="conflict-explanation"><strong>Why it was flagged</strong>{conflict.explanation}</p>}
    <div className="conflict-actions"><span>{conflict.detection_method ? `Detected by ${pretty(conflict.detection_method)}` : 'Deterministic Phase 5 comparison'} · {new Date(conflict.created_at).toLocaleString()}</span><div>
      {conflict.status !== 'under_review' && <button className="button subtle" disabled={busy} onClick={() => onSetStatus(conflict, 'under_review')}>Review</button>}
      {conflict.status !== 'resolved' && <button className="button success" disabled={busy} onClick={() => onSetStatus(conflict, 'resolved')}><Check size={13} /> Resolve</button>}
      {conflict.status !== 'dismissed' && <button className="button subtle" disabled={busy} onClick={() => onSetStatus(conflict, 'dismissed')}>Dismiss</button>}
      {busy && <span className="small-busy">Saving…</span>}
    </div></div>
  </motion.article>
}

