import { useCallback, useEffect, useState } from 'react'
import { Activity, BrainCircuit, Database, FileCheck2, Gauge, HardDrive, RefreshCw, ShieldCheck, WifiOff } from 'lucide-react'
import { api, pretty } from '../services/api'
import { EmptyState, ErrorState, LoadingBlock, StatePill } from '../components/Primitives'

export default function ReliabilityPage({ onOpenDocument }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [sources, system, embeddings, retrieval, analytics] = await Promise.all([
        api('/api/reliability/sources'), api('/api/system/status'), api('/api/embeddings/status'),
        api('/api/retrieval/status'), api('/api/analytics'),
      ])
      setData({ sources, system, embeddings, retrieval, analytics })
    } catch (cause) { setError(cause.message) } finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])

  return <div className="page-stack">
    <div className="page-intro"><div><div className="eyebrow">SOURCE QUALITY · LOCAL RUNTIME</div><h1>Reliability & settings</h1><p>Review the actual evaluation factors and local component diagnostics. Reliability scores are heuristics for review, not calibrated probabilities.</p></div><button className="icon-button" onClick={refresh} aria-label="Refresh diagnostics"><RefreshCw size={16} /></button></div>
    {error && <ErrorState message={error} onRetry={refresh} />}{loading && !data && <LoadingBlock label="Checking source and runtime diagnostics" />}
    {data && <>
      <section className="panel runtime-panel"><div className="panel-heading"><div><div className="eyebrow">LOCAL COMPONENTS</div><h3>Runtime diagnostics</h3></div><StatePill state={data.system.status}>{pretty(data.system.status)}</StatePill></div>
        <div className="runtime-grid"><RuntimeCard icon={Database} title="Database" value={data.system.database} detail={`${data.analytics.total_evidence} evidence records · ${data.analytics.total_documents} documents`} /><RuntimeCard icon={BrainCircuit} title="Ollama / chat model" value={data.embeddings.ollama_reachable ? 'reachable' : 'unavailable'} detail={`Configured chat: ${data.retrieval.chat_model}`} /><RuntimeCard icon={Gauge} title="Embedding index" value={data.embeddings.embedding_model_installed ? 'model installed' : 'model unavailable'} detail={`${data.embeddings.indexed_chunks} indexed chunks · ${data.embeddings.vector_dimension ?? 'dimension unknown'}`} /><RuntimeCard icon={FileCheck2} title="OCR engine" value={data.system.ocr_engine} detail="Scanned PDF and image OCR depends on local engine availability." /><RuntimeCard icon={ShieldCheck} title="Upload storage" value={data.system.upload_storage} detail={`Document processing: ${pretty(data.system.document_processing)}`} /><RuntimeCard icon={HardDrive} title="Free local storage" value={data.system.storage_free_bytes == null ? 'unavailable' : 'measured'} detail={formatStorage(data.system.storage_free_bytes)} /><RuntimeCard icon={WifiOff} title="Offline readiness" value={pretty(data.system.offline_readiness || 'not_verified')} detail="Offline readiness is not claimed until a disconnected run is completed." />
        </div>
      </section>
      <section className="panel reliability-panel"><div className="panel-heading"><div><div className="eyebrow">EXPLAINABLE HEURISTIC</div><h3>Source evaluations</h3></div><span className="count-tag">{data.sources.total} sources</span></div>
        <p className="source-score-notice">{data.sources.score_notice}</p>
        {data.sources.items.length ? <div className="source-evaluations">{data.sources.items.map((source) => <article className="source-eval-card" key={source.document_id}>
          <div className="source-eval-heading"><button className="source-name-link" onClick={() => onOpenDocument(source.document_id)}>{source.filename}</button><span className="heuristic-score"><strong>{Math.round(source.heuristic_score * 100)}</strong><small>heuristic points</small></span></div>
          <div className="source-badges"><StatePill state={source.approval_status}>{pretty(source.approval_status)}</StatePill><StatePill state={source.source_type}>{pretty(source.source_type)}</StatePill>{source.duplicate_source && <span className="duplicate-flag">Duplicate source copy</span>}</div>
          <p>{source.explanation}</p>
          <div className="criteria-list">{Object.entries(source.criteria || {}).map(([key, value]) => <div className="criterion-row" key={key}><span>{pretty(key)}</span><b>{typeof value === 'object' && value !== null ? pretty(value.reason || 'No criterion explanation') : pretty(String(value))}</b><small>{typeof value === 'object' && value?.score != null ? `${Math.round(value.score * 100)} heuristic points` : source.weights?.[key] != null ? `weight ${source.weights[key]}` : ''}</small></div>)}</div>
          {source.duplicate_of_document_id && <small className="honesty-note">Same-source match references document {source.duplicate_of_document_id}; copies are not counted as independent corroboration.</small>}
        </article>)}</div> : <EmptyState icon={FileCheck2} title="No sources to evaluate" detail="Source evaluations appear when documents are present in the local database." />}
      </section>
    </>}
  </div>
}

function formatStorage(bytes) {
  if (bytes == null) return 'Free space could not be measured.'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes, index = 0
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1 }
  return `${value.toFixed(index >= 3 ? 1 : 0)} ${units[index]} free on the upload-storage volume.`
}

function RuntimeCard({ icon: Icon, title, value, detail }) {
  return <article className="runtime-card"><span className="runtime-icon"><Icon size={17} /></span><span className="runtime-title">{title}</span><StatePill state={value}>{pretty(value)}</StatePill><small>{detail}</small></article>
}
