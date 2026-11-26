import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import { Activity, ArrowRight, BrainCircuit, Database, FileText, RefreshCw, ShieldAlert, ShieldCheck, Workflow } from 'lucide-react'
import { motion } from 'framer-motion'
import { api, pretty } from '../services/api'
import { ErrorState, LoadingBlock, StatePill } from '../components/Primitives'
const HologramScene = lazy(() => import('../components/3d/HologramScene.jsx'))

const metricItems = [
  ['total_documents', 'Documents', FileText, 'documents'],
  ['total_evidence', 'Evidence records', Database, 'documents'],
  ['total_contradictions', 'Conflict findings', ShieldAlert, 'contradictions'],
  ['active_jobs', 'Active jobs', Activity, 'documents'],
]

export default function Dashboard({ onNavigate, onOpenDocument }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [analytics, system, embeddings, retrieval, documents] = await Promise.all([
        api('/api/analytics'), api('/api/system/status'), api('/api/embeddings/status'),
        api('/api/retrieval/status'), api('/api/documents?limit=5'),
      ])
      setData({ analytics, system, embeddings, retrieval, documents: documents.items })
    } catch (cause) { setError(cause.message) } finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])

  return <div className="page-stack">
    <section className="dashboard-hero panel">
      <div className="hero-copy">
        <div className="eyebrow"><span className="eyebrow-dot" /> CERBERUS-X / EVIDENCE INTELLIGENCE</div>
        <h1>Local evidence.<br /><em>Clear decisions.</em></h1>
        <p>One workspace for document ingestion, grounded answers, conflict review, and source traceability.</p>
        <div className="hero-actions">
          <button className="button primary" onClick={() => onNavigate('documents')}>Explore documents <ArrowRight size={15} /></button>
          <button className="button secondary" onClick={() => onNavigate('intelligence')}><BrainCircuit size={15} /> Ask local AI</button>
        </div>
      </div>
      <div className="hero-visual"><Suspense fallback={<div className="orb-fallback"><div className="fallback-core" /></div>}><HologramScene /></Suspense><div className="orbit-note">LOCAL MODEL<br /><strong>{data?.retrieval?.chat_model || 'Checking configuration'}</strong></div></div>
    </section>

    <div className="section-title-row"><div><div className="eyebrow">LIVE SNAPSHOT</div><h2>System overview</h2></div><button className="icon-button" onClick={refresh} aria-label="Refresh dashboard" title="Refresh"><RefreshCw size={16} className={loading ? 'spin' : ''} /></button></div>
    {error ? <ErrorState message={error} onRetry={refresh} /> : loading && !data ? <LoadingBlock /> : data && <>
      <section className="metric-grid dashboard-metrics" aria-label="Live database metrics">
        {metricItems.map(([key, label, Icon, route], index) => <motion.button type="button" className="metric-card panel" key={key} onClick={() => onNavigate(route)} aria-label={`Open ${label} in ${route === 'contradictions' ? 'Contradiction centre' : 'Document explorer'}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.05 }}>
          <span className="metric-icon"><Icon size={17} /></span><span className="metric-label">{label}</span><strong>{data.analytics[key]}</strong><ArrowRight className="metric-action" size={14} aria-hidden="true" />
        </motion.button>)}
      </section>
      <section className="dashboard-lower">
        <article className="panel system-panel">
          <div className="panel-heading"><div><div className="eyebrow">LOCAL RUNTIME</div><h3>Service readiness</h3></div><StatePill state={data.system.status}>{pretty(data.system.status)}</StatePill></div>
          <div className="service-list">
            <ServiceRow icon={Database} label="SQLite database" value={data.system.database} />
            <ServiceRow icon={FileText} label="Upload storage" value={data.system.upload_storage} />
            <ServiceRow icon={Workflow} label="Document extraction" value={data.system.document_processing} />
            <ServiceRow icon={BrainCircuit} label={`Embedding · ${data.embeddings.embedding_model}`} value={data.embeddings.embedding_model_installed ? 'available' : 'unavailable'} detail={`${data.embeddings.indexed_chunks} indexed chunks`} />
            <ServiceRow icon={ShieldCheck} label={`Local chat · ${data.retrieval.chat_model}`} value={data.embeddings.ollama_reachable ? 'Ollama reachable' : 'Ollama unavailable'} />
            <ServiceRow icon={Activity} label="OCR engine" value={data.system.ocr_engine} />
          </div>
          {!data.embeddings.embedding_model_installed && <p className="inline-note warning">The configured embedding model is not installed. Retrieval may use the backend’s reported fallback.</p>}
          <p className="honesty-note">Service and count values are read from the local API. A reachable Ollama service does not by itself prove every model call succeeds.</p>
        </article>
        <article className="panel recent-panel">
          <div className="panel-heading"><div><div className="eyebrow">RECENT SOURCES</div><h3>Document activity</h3></div><button className="text-button" onClick={() => onNavigate('documents')}>All documents <ArrowRight size={13} /></button></div>
          {data.documents.length ? <div className="recent-list">{data.documents.map((document) => <button className="recent-document" key={document.id} onClick={() => onOpenDocument(document.id)}>
            <span className="file-symbol"><FileText size={16} /></span><span className="recent-copy"><strong>{document.original_filename}</strong><small>{document.extension.toUpperCase()} · {formatBytes(document.size_bytes)}</small></span><StatePill state={document.processing_status}>{pretty(document.processing_status)}</StatePill>
          </button>)}</div> : <div className="empty-small">No documents stored yet. Upload a source to begin.</div>}
          <div className="status-foot"><span>Queued <b>{data.analytics.uploaded_documents}</b></span><span>Processed <b>{data.analytics.processed_documents}</b></span><span>Failed <b>{data.analytics.failed_documents}</b></span></div>
        </article>
      </section>
    </>}
  </div>
}

function ServiceRow({ icon: Icon, label, value, detail }) {
  return <div className="service-row"><span className="service-icon"><Icon size={15} /></span><span className="service-label">{label}{detail && <small>{detail}</small>}</span><StatePill state={value}>{pretty(value)}</StatePill></div>
}

function formatBytes(bytes = 0) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
