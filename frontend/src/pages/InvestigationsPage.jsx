import { useCallback, useEffect, useState } from 'react'
import { Activity, AlertTriangle, ArrowDownToLine, FilePlus2, FileText, LoaderCircle, RefreshCw, Search, ShieldAlert, ShieldCheck } from 'lucide-react'
import { api, downloadApiFile, pretty, sourceLocation } from '../services/api'
import { EmptyState, ErrorState, LoadingBlock, StatePill } from '../components/Primitives'

export default function InvestigationsPage({ onOpenDocument }) {
  const [documents, setDocuments] = useState([])
  const [investigations, setInvestigations] = useState([])
  const [active, setActive] = useState(null)
  const [title, setTitle] = useState('')
  const [question, setQuestion] = useState('')
  const [scope, setScope] = useState('all')
  const [selectedIds, setSelectedIds] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [documentPayload, investigationPayload] = await Promise.all([
        api('/api/documents?limit=100'), api('/api/investigations?limit=50'),
      ])
      setDocuments(documentPayload.items || [])
      setInvestigations(investigationPayload.items || [])
    } catch (cause) { setError(cause.message) } finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])

  async function openInvestigation(item) {
    setBusy(`load:${item.id}`); setError(''); setNotice('')
    try { setActive(await api(`/api/investigations/${item.id}`)) }
    catch (cause) { setError(cause.message) } finally { setBusy('') }
  }

  async function createInvestigation(event) {
    event.preventDefault()
    if (scope === 'selected' && !selectedIds.length) { setError('Select at least one document or choose the whole collection.'); return }
    setBusy('create'); setError(''); setNotice('')
    try {
      const created = await api('/api/investigations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, question, document_ids: scope === 'selected' ? selectedIds : null, top_k: 12 }),
      })
      setActive(created)
      setNotice('Investigation saved. Gathering local evidence and generating a cited report?')
      const generated = await api(`/api/investigations/${created.id}/generate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      })
      setActive(generated)
      setNotice(generated.report?.conclusion?.abstained
        ? 'Report saved with an explicit abstention because the evidence did not support a safe conclusion.'
        : 'Evidence report generated and saved locally.')
      setTitle(''); setQuestion(''); setSelectedIds([])
      await refresh()
    } catch (cause) { setError(cause.message); await refresh() } finally { setBusy('') }
  }

  async function regenerate() {
    if (!active) return
    setBusy(`generate:${active.id}`); setError(''); setNotice('')
    try {
      const result = await api(`/api/investigations/${active.id}/generate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      })
      setActive(result); setNotice(result.report?.conclusion?.abstained ? 'Report refreshed with an evidence-based abstention.' : 'Report refreshed from current local evidence.')
      await refresh()
    } catch (cause) { setError(cause.message) } finally { setBusy('') }
  }

  async function exportPdf() {
    if (!active?.report) return
    setBusy(`pdf:${active.id}`); setError('')
    try { await downloadApiFile(`/api/investigations/${active.id}/report.pdf`, `cerberus_x_investigation_${active.id}.pdf`); setNotice('PDF report downloaded from the local API.') }
    catch (cause) { setError(cause.message) } finally { setBusy('') }
  }

  function toggleDocument(id) {
    setSelectedIds((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id)
      if (current.length >= 50) { setError('Select no more than 50 documents for one investigation.'); return current }
      return [...current, id]
    })
  }

  const report = active?.report
  return <div className="page-stack investigation-page">
    <div className="page-intro"><div><div className="eyebrow"><Activity size={12} /> PHASE 8 ? EVIDENCE-LED ANALYSIS</div><h1>Investigation workspace</h1><p>Build a saved investigation from local documents. Reports preserve original evidence, locations, conflicts, reliability explanations, and citation-checked conclusions.</p></div><button className="icon-button" onClick={refresh} aria-label="Refresh investigations"><RefreshCw size={16} /></button></div>
    {error && <ErrorState message={error} onRetry={refresh} />}{notice && <div className="notice-banner" role="status">{notice}</div>}
    <div className="investigation-layout">
      <aside className="panel investigation-sidebar">
        <div className="panel-heading"><div><div className="eyebrow">SAVED WORK</div><h3>Investigations</h3></div><span className="count-tag">{investigations.length}</span></div>
        {loading ? <LoadingBlock label="Loading saved investigations" /> : investigations.length ? <div className="investigation-list">{investigations.map((item) => <button key={item.id} className={`investigation-list-item ${active?.id === item.id ? 'active' : ''}`} onClick={() => openInvestigation(item)} disabled={busy === `load:${item.id}`}><span><strong>{item.title}</strong><small>{item.question}</small></span><StatePill state={item.status}>{pretty(item.status)}</StatePill></button>)}</div> : <EmptyState icon={Search} title="No saved investigations" detail="Create an investigation to save a question and evidence scope." />}
      </aside>
      <div className="investigation-workbench">
        <form className="panel investigation-create" onSubmit={createInvestigation}>
          <div className="panel-heading"><div><div className="eyebrow">NEW INVESTIGATION</div><h3>Define the question and source scope</h3></div><FilePlus2 size={18} /></div>
          <div className="investigation-fields"><label>Investigation title<input required minLength={3} maxLength={160} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Example: Project Orion approval review" /></label><label>Investigation question<textarea required minLength={3} maxLength={2000} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What do the stored records say, and what evidence supports or opposes that account?" /></label></div>
          <fieldset className="investigation-scope"><legend>Source scope</legend><label className="scope-option"><input type="radio" name="scope" value="all" checked={scope === 'all'} onChange={() => setScope('all')} /><span><strong>Whole document collection</strong><small>Search all available local evidence; use the backend's reported keyword fallback when needed.</small></span></label><label className="scope-option"><input type="radio" name="scope" value="selected" checked={scope === 'selected'} onChange={() => setScope('selected')} /><span><strong>Selected documents</strong><small>Limit retrieval, claims, conflicts, and sources to the checked documents.</small></span></label>
            {scope === 'selected' && <div className="investigation-document-picker">{documents.length ? documents.map((document) => <label key={document.id} className="document-choice"><input type="checkbox" checked={selectedIds.includes(document.id)} onChange={() => toggleDocument(document.id)} /><span>{document.original_filename}<small>{pretty(document.processing_status)}</small></span></label>) : <p>No documents are stored yet.</p>}</div>}
          </fieldset>
          <div className="investigation-create-footer"><small>Local Qwen answers abstain when retrieved evidence is missing, conflicting, or cannot be cited exactly.</small><button className="button primary" disabled={busy === 'create' || loading || (scope === 'selected' && !selectedIds.length)}>{busy === 'create' ? <><LoaderCircle size={14} className="spin" /> Investigating?</> : <><Search size={14} /> Create & generate report</>}</button></div>
        </form>
        {active && <div className="investigation-detail">
          <div className="panel investigation-report-heading"><div><div className="eyebrow">INVESTIGATION #{active.id} ? {active.report?.retrieval_method ? pretty(active.report.retrieval_method) : 'DRAFT'}</div><h2>{active.title}</h2><p>{active.question}</p><small>{active.document_ids?.length ? `${active.document_ids.length} selected document(s)` : 'Whole collection'}{active.report?.generated_at ? ` ? Generated ${new Date(active.report.generated_at).toLocaleString()}` : ''}</small></div><div className="investigation-report-actions"><StatePill state={active.status}>{pretty(active.status)}</StatePill><button className="button secondary" onClick={regenerate} disabled={busy.startsWith('generate:')}>{busy.startsWith('generate:') ? <><LoaderCircle size={13} className="spin" /> Updating?</> : <><RefreshCw size={13} /> Regenerate</>}</button><button className="button primary" onClick={exportPdf} disabled={!report || busy.startsWith('pdf:')}>{busy.startsWith('pdf:') ? <><LoaderCircle size={13} className="spin" /> Preparing?</> : <><ArrowDownToLine size={13} /> Export PDF</>}</button></div></div>
          {!report ? <LoadingBlock label="Waiting for the local report" /> : <>
            <ReportSection title="1. Investigation question" icon={Search}><p>{report.question}</p><small>{report.scope?.document_count ?? 0} stored documents in scope</small></ReportSection>
            <ReportSection title="2. Executive summary" icon={Activity}><p>{report.executive_summary?.text}</p>{report.executive_summary?.abstained && <div className="investigation-warning"><AlertTriangle size={14} /> The local assistant abstained; this summary does not assert a supported factual conclusion.</div>}{report.executive_summary?.citations?.length > 0 && <EvidenceList items={report.executive_summary.citations.map((item) => ({ ...item, quote: item.quoted_text }))} onOpenDocument={onOpenDocument} />}</ReportSection>
            <div className="investigation-report-grid"><ReportSection title="3. Supporting evidence" icon={ShieldCheck}><EvidenceList items={report.supporting_evidence} onOpenDocument={onOpenDocument} /><ClaimList items={report.supporting_claims} onOpenDocument={onOpenDocument} /></ReportSection><ReportSection title="4. Opposing evidence" icon={ShieldAlert}><EvidenceList items={report.opposing_evidence} onOpenDocument={onOpenDocument} /><ClaimList items={report.opposing_claims} onOpenDocument={onOpenDocument} /></ReportSection></div>
            {(report.context_evidence?.length > 0 || report.context_claims?.length > 0) && <ReportSection title="Context and uncertain passages" icon={FileText}><EvidenceList items={report.context_evidence} onOpenDocument={onOpenDocument} /><ClaimList items={report.context_claims} onOpenDocument={onOpenDocument} /></ReportSection>}
            <ReportSection title="5. Contradictions and unresolved issues" icon={AlertTriangle}>{report.contradictions?.length ? <div className="investigation-findings">{report.contradictions.map((item) => <article key={item.id} className="investigation-finding"><div><StatePill state={item.classification}>{pretty(item.classification)}</StatePill><span>Finding #{item.id} ? {pretty(item.status)}{item.confidence != null ? ` ? ${Math.round(item.confidence * 100)}% heuristic` : ''}{item.confidence_note ? ` ? ${item.confidence_note}` : ''}</span></div><p>{item.explanation}</p><div className="investigation-claim-pair">{[item.claim_a, item.claim_b].filter(Boolean).map((claim) => <button key={claim.id} onClick={() => onOpenDocument(claim.document_id)}><strong>{claim.filename}</strong><small>Document {claim.document_id} ? Claim #{claim.id} ? Evidence #{claim.evidence_id} ? {sourceLocation(claim.source_location)}</small><q>{claim.value}</q><small>Normalized: {claim.object_value || claim.normalized_value}</small></button>)}</div></article>)}</div> : <EmptyState icon={ShieldCheck} title="No comparison findings" detail="No conflict or mismatch was returned for the retrieved, normalized claims." />}</ReportSection>
            <ReportSection title="6. Source reliability explanations" icon={ShieldCheck}>{report.source_reliability?.length ? <div className="investigation-sources">{report.source_reliability.map((item) => <article key={item.document_id}><button onClick={() => onOpenDocument(item.document_id)}>{item.filename}</button><StatePill state={item.approval_status}>{pretty(item.approval_status)} ? {Math.round(item.heuristic_score * 100)} heuristic points</StatePill><p>{item.explanation}</p></article>)}</div> : <EmptyState icon={FileText} title="No source evaluation" detail="Reliability is only shown for sources returned by verification." />}</ReportSection>
            <ReportSection title="7. Missing evidence" icon={AlertTriangle}>{report.missing_evidence?.length ? <ul className="investigation-missing">{report.missing_evidence.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul> : <p>No missing-evidence notes were returned. This is not proof that unindexed or unreviewed sources do not exist.</p>}</ReportSection>
            <ReportSection title="8. Conclusion and limitations" icon={Activity}><p>{report.conclusion?.text}</p>{report.conclusion?.abstained && <div className="investigation-warning"><AlertTriangle size={14} /> Abstained: the available evidence did not support a safe conclusion.</div>}{report.conclusion?.citations?.length > 0 && <EvidenceList items={report.conclusion.citations.map((item) => ({ ...item, quote: item.quoted_text }))} onOpenDocument={onOpenDocument} />}{report.limitations?.length > 0 && <ul className="investigation-missing">{report.limitations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>}</ReportSection>
          </>}
        </div>}
      </div>
    </div>
  </div>
}

function ReportSection({ title, icon: Icon, children }) {
  return <section className="panel investigation-section"><div className="panel-heading"><div><div className="eyebrow">EVIDENCE REPORT</div><h3>{title}</h3></div><Icon size={16} /></div><div className="investigation-section-body">{children}</div></section>
}

function ClaimList({ items = [], onOpenDocument }) {
  if (!items.length) return null
  return <div className="investigation-claims"><strong>Linked extracted claims</strong>{items.map((item) => <article key={item.id}><button onClick={() => onOpenDocument(item.document_id)}>{item.filename} ? Document {item.document_id}</button><span>Claim #{item.id} ? Evidence #{item.evidence_id} ? {sourceLocation(item.source_location)}</span><q>{item.value}</q><small>Normalized: {item.object_value || item.normalized_value}{item.currency ? ` ${item.currency}` : ''}{item.unit ? ` / ${item.unit}` : ''}</small></article>)}</div>
}

function EvidenceList({ items = [], onOpenDocument }) {
  if (!items.length) return <EmptyState icon={FileText} title="No cited passages" detail="No source passage in this section passed evidence validation." />
  return <div className="investigation-evidence-list">{items.map((item, index) => <article key={`${item.evidence_id}-${index}`}><div className="evidence-card-top"><span className="evidence-id">[E{item.evidence_id}] ? {pretty(item.stance || 'cited')}</span><span className="source-location">{sourceLocation(item.source_location || item)}</span></div><button onClick={() => onOpenDocument(item.document_id)}>{item.filename} ? open source</button><q>{item.quote || item.quoted_text}</q><small>{item.classification_note || `Quote checked against source evidence #${item.evidence_id}.`}</small></article>)}</div>
}

