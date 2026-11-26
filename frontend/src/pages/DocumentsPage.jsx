import { useCallback, useEffect, useRef, useState } from 'react'
import { Database, FileText, FileUp, FolderOpen, LoaderCircle, RefreshCw, Search, ShieldCheck, Trash2, UploadCloud } from 'lucide-react'
import { motion } from 'framer-motion'
import { api, pretty, sourceLocation } from '../services/api'
import { EmptyState, ErrorState, LoadingBlock, StatePill } from '../components/Primitives'
import DocumentScanner from '../components/DocumentScanner'

const ACCEPTED = '.pdf,.docx,.txt,.csv,.xlsx,.png,.jpg,.jpeg'

export default function DocumentsPage({ requestedDocumentId, onDocumentOpened }) {
  const inputRef = useRef(null)
  const [documents, setDocuments] = useState([])
  const [selectedFiles, setSelectedFiles] = useState([])
  const [evidence, setEvidence] = useState([])
  const [evidenceLoading, setEvidenceLoading] = useState(false)
  const [evidenceError, setEvidenceError] = useState('')
  const [active, setActive] = useState(null)
  const evidenceRequest = useRef(0)
  const [search, setSearch] = useState('')
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)

  const loadDocuments = useCallback(async () => {
    setLoading(true); setError('')
    try { const payload = await api('/api/documents?limit=100'); setDocuments(payload.items) }
    catch (cause) { setError(cause.message) } finally { setLoading(false) }
  }, [])

  const openDocument = useCallback(async (document) => {
    const requestId = ++evidenceRequest.current
    setActive(document)
    setEvidence([])
    setEvidenceLoading(true)
    setEvidenceError('')
    setError('')
    try {
      const payload = await api(`/api/documents/${encodeURIComponent(document.id)}/evidence`)
      if (requestId !== evidenceRequest.current) return
      if (!Array.isArray(payload.items) || payload.items.some((item) => item.document_id !== document.id)) {
        throw new Error('The evidence response did not match the selected document.')
      }
      setEvidence(payload.items)
    } catch (cause) {
      if (requestId === evidenceRequest.current) setEvidenceError(cause.message)
    } finally {
      if (requestId === evidenceRequest.current) setEvidenceLoading(false)
    }
  }, [])

  useEffect(() => { loadDocuments() }, [loadDocuments])
  useEffect(() => {
    if (!requestedDocumentId || !documents.length) return
    const target = documents.find((document) => document.id === requestedDocumentId)
    if (target) { openDocument(target); onDocumentOpened?.() }
  }, [requestedDocumentId, documents, openDocument, onDocumentOpened])

  const chooseFiles = (files) => {
    const next = [...files]
    setSelectedFiles(next); setNotice(''); setError('')
  }

  async function uploadFiles(event) {
    event.preventDefault()
    if (!selectedFiles.length) return
    setBusy('upload'); setError(''); setNotice('')
    const form = new FormData()
    selectedFiles.forEach((file) => form.append('files', file))
    try {
      const result = await api('/api/documents/upload', { method: 'POST', body: form })
      setNotice(`${result.total} file${result.total === 1 ? '' : 's'} stored and validated locally. Processing remains a separate action.`)
      setSelectedFiles([])
      if (inputRef.current) inputRef.current.value = ''
      await loadDocuments()
    } catch (cause) { setError(cause.message) } finally { setBusy('') }
  }

  async function processDocument(document) {
    setBusy(document.id); setError(''); setNotice('')
    try {
      const result = await api(`/api/documents/${encodeURIComponent(document.id)}/process`, { method: 'POST' })
      setNotice(`${document.original_filename}: ${pretty(result.status)} · ${result.evidence_count} evidence records · ${result.claim_count} candidate claims${result.warnings.length ? ` · ${result.warnings.join('; ')}` : ''}`)
      await loadDocuments()
      const updated = await api(`/api/documents/${encodeURIComponent(document.id)}`)
      await openDocument(updated)
    } catch (cause) { setError(cause.message) } finally { setBusy('') }
  }

  async function indexDocument(document) {
    setBusy('index:' + document.id); setError(''); setNotice('')
    try {
      const result = await api('/api/embeddings/index', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_ids: [document.id] }),
      })
      const indexed = result.documents?.find((item) => item.document_id === document.id)
      if (result.status !== 'completed' || indexed?.status !== 'completed') {
        throw new Error(indexed?.message || 'The document could not be indexed with the configured local embedding model.')
      }
      setNotice(document.original_filename + ': indexed ' + indexed.chunk_count + ' chunks · ' +
        result.generated_embeddings + ' vectors generated · ' + result.reused_embeddings + ' reused locally.')
    } catch (cause) { setError(cause.message) } finally { setBusy('') }
  }

  async function removeDocument(document) {
    if (!window.confirm(`Delete ${document.original_filename} and its stored metadata?`)) return
    setBusy(document.id); setError('')
    try {
      await api(`/api/documents/${encodeURIComponent(document.id)}`, { method: 'DELETE' })
      if (active?.id === document.id) {
        evidenceRequest.current += 1
        setActive(null)
        setEvidence([])
        setEvidenceLoading(false)
        setEvidenceError('')
      }
      setNotice(`${document.original_filename} was deleted.`)
      await loadDocuments()
    } catch (cause) { setError(cause.message) } finally { setBusy('') }
  }

  const visible = documents.filter((document) => `${document.original_filename} ${document.extension} ${document.processing_status}`.toLowerCase().includes(search.toLowerCase()))

  return <div className="page-stack">
    <PageIntro eyebrow="SOURCE MANAGEMENT" title="Document explorer" description="Validate and store local sources, run extraction when you choose, then inspect the evidence and its original location." action={<button className="icon-button" onClick={loadDocuments} aria-label="Refresh documents"><RefreshCw size={16} /></button>} />
    <section className="panel upload-panel">
      <form onSubmit={uploadFiles}>
        <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFiles(event.dataTransfer.files) }}>
          <input ref={inputRef} type="file" accept={ACCEPTED} multiple onChange={(event) => chooseFiles(event.target.files)} aria-label="Choose documents to upload" />
          <span className="upload-icon"><UploadCloud size={24} /></span>
          <strong>Drop source documents here</strong><span>PDF · DOCX · TXT · CSV · XLSX · PNG · JPG · JPEG</span>
          <button type="button" className="button secondary" onClick={() => inputRef.current?.click()}><FolderOpen size={15} /> Browse files</button>
        </div>
        {selectedFiles.length > 0 && <div className="selected-files">{selectedFiles.map((file, index) => <span key={`${file.name}-${index}`}><FileText size={14} />{file.name}<small>{formatBytes(file.size)}</small></span>)}</div>}
        <div className="upload-actions"><span><ShieldCheck size={14} /> Files are validated and kept in local storage. Upload does not start extraction.</span><button className="button primary" disabled={!selectedFiles.length || busy === 'upload'}>{busy === 'upload' ? <><LoaderCircle size={15} className="spin" /> Uploading</> : <><FileUp size={15} /> Upload selected</>}</button></div>
      </form>
    </section>
    {notice && <div className="notice-banner" role="status">{notice}</div>}
    {error && <ErrorState message={error} onRetry={loadDocuments} />}
    <div className="document-layout">
      <section className="panel document-list-panel">
        <div className="panel-heading"><div><div className="eyebrow">LOCAL LIBRARY</div><h3>Stored documents <span className="count-tag">{documents.length}</span></h3></div><label className="search-box"><Search size={14} /><input aria-label="Search documents" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filter sources" /></label></div>
        {loading ? <LoadingBlock label="Reading document metadata" /> : visible.length ? <div className="document-list">{visible.map((document) => <motion.article layout className={`document-row ${active?.id === document.id ? 'selected' : ''} ${busy === document.id ? 'processing-row' : ''}`} key={document.id}>
          <button className="document-select" onClick={() => openDocument(document)}><span className="file-symbol"><FileText size={17} /></span><span className="doc-main"><strong>{document.original_filename}</strong><small>{document.extension.toUpperCase()} · {formatBytes(document.size_bytes)} · {new Date(document.created_at).toLocaleDateString()}</small></span><StatePill state={document.processing_status}>{pretty(document.processing_status)}</StatePill></button>
          <div className="document-actions"><button className="text-button" disabled={['processed', 'completed'].includes(document.processing_status.toLowerCase()) || busy === document.id} onClick={() => processDocument(document)}>{busy === document.id ? <><LoaderCircle size={13} className="spin" /> Processing</> : 'Process'}</button>{['completed', 'partially_completed'].includes(document.processing_status.toLowerCase()) && <button className="text-button" title="Generate or reuse local embeddings for search and Q&A" disabled={busy === document.id || busy === ('index:' + document.id)} onClick={() => indexDocument(document)}>{busy === ('index:' + document.id) ? <><LoaderCircle size={12} className="spin" /> Indexing</> : <><Database size={12} /> Index</>}</button>}<button className="icon-button danger-hover" aria-label={`Delete ${document.original_filename}`} title="Delete document" disabled={busy === document.id} onClick={() => removeDocument(document)}><Trash2 size={14} /></button></div>
        </motion.article>)}</div> : <EmptyState icon={FileText} title={search ? 'No matching sources' : 'No documents yet'} detail={search ? 'Try a different filename or status.' : 'Upload a supported file to start building your local evidence library.'} />}
      </section>
      <section className="panel evidence-panel">
        <div className="panel-heading"><div><div className="eyebrow">EXTRACTION PREVIEW</div><h3>{active?.original_filename || 'Select a document'}</h3></div>{active && <span className="format-badge">{active.extension.toUpperCase()}</span>}</div>
        <label className="evidence-document-picker">Select a document to preview
          <select aria-label="Select a document to preview extracted evidence" value={active?.id || ''} disabled={loading || !documents.length} onChange={(event) => {
            const selected = documents.find((document) => document.id === event.target.value)
            if (selected) openDocument(selected)
          }}>
            <option value="" disabled>{loading ? 'Loading documents…' : documents.length ? 'Choose a stored document' : 'No documents available'}</option>
            {documents.map((document) => <option key={document.id} value={document.id}>{document.original_filename} · {pretty(document.processing_status)} · {document.id.slice(0, 8)}</option>)}
          </select>
        </label>
        {active ? <>
          <div className="document-meta"><span>SHA-256</span><code>{active.sha256}</code><span>Stored size</span><b>{formatBytes(active.size_bytes)}</b><span>Processing</span><StatePill state={active.processing_status}>{pretty(active.processing_status)}</StatePill></div>
          <DocumentScanner active={busy === active.id} filename={active.original_filename} />
          {evidenceLoading ? <LoadingBlock label={`Loading evidence for ${active.original_filename}`} /> : evidenceError ? <ErrorState message={evidenceError} onRetry={() => openDocument(active)} /> : !evidence.length ? <EmptyState icon={Search} title="No extracted evidence available" detail="No evidence records are stored for this document. Run document processing to extract its text and source locations." /> : <div className="evidence-list">{evidence.map((item) => <article className="evidence-card" key={item.id}>
            <div className="evidence-card-top"><span className="evidence-id">Evidence #{item.id}</span><span className="source-location">{sourceLocation(item)}</span></div>
            <p>{item.extracted_text || item.original_text || item.context_text || 'No text was returned for this evidence record.'}</p>
            {item.context_text && item.context_text !== item.extracted_text && <small className="context-line">Context: {item.context_text}</small>}
            <div className="evidence-card-foot"><span>{pretty(item.extraction_method)}{item.extraction_confidence != null ? ` · ${Math.round(item.extraction_confidence * 100)}% extraction confidence` : ''}</span><span>{item.claims.length} linked claims</span></div>
          </article>)}</div>}
        </> : <EmptyState icon={FileText} title="Source details appear here" detail="Select any stored document to inspect its processing state and evidence records." />}
      </section>
    </div>
  </div>
}

function PageIntro({ eyebrow, title, description, action }) {
  return <div className="page-intro"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>
}

function formatBytes(bytes = 0) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
