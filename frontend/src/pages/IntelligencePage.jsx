import { useEffect, useRef, useState } from 'react'
import { ArrowUp, BrainCircuit, CircleAlert, FileSearch, LoaderCircle, MessageSquareText, RotateCcw, Search, ShieldCheck } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import { api, sourceLocation } from '../services/api'
import { EmptyState, ErrorState, StatePill } from '../components/Primitives'

export default function IntelligencePage({ onOpenDocument }) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [modelStatus, setModelStatus] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchBusy, setSearchBusy] = useState(false)
  const [searchError, setSearchError] = useState('')
  const endRef = useRef(null)

  useEffect(() => {
    api('/api/retrieval/status').then(setModelStatus).catch((cause) => setError(cause.message))
  }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [messages, busy])

  async function searchEvidence(event) {
    event.preventDefault()
    const query = searchQuery.trim()
    if (query.length < 2 || searchBusy) return
    setSearchBusy(true); setSearchError(''); setSearchResults(null)
    try {
      const result = await api('/api/search', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, top_k: 8 }) })
      setSearchResults(result)
    } catch (cause) { setSearchError(cause.message) } finally { setSearchBusy(false) }
  }

  async function ask(event) {
    event.preventDefault()
    const prompt = question.trim()
    if (prompt.length < 3 || busy) return
    const userMessage = { id: `u-${Date.now()}`, role: 'user', text: prompt }
    setMessages((current) => [...current, userMessage]); setQuestion(''); setBusy(true); setError('')
    try {
      const answer = await api('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: prompt, top_k: 8 }) })
      setMessages((current) => [...current, { id: answer.question_id || `a-${Date.now()}`, role: 'assistant', ...answer }])
    } catch (cause) {
      setError(cause.message)
    } finally { setBusy(false) }
  }

  return <div className="page-stack intelligence-page">
    <div className="page-intro"><div><div className="eyebrow">LOCAL Q&A · CITATIONS REQUIRED</div><h1>Intelligence workspace</h1><p>Ask questions about stored documents. Answers come from retrieved evidence through the configured local model, with citations supplied by the backend.</p></div><span className="model-chip"><BrainCircuit size={15} /> {modelStatus?.chat_model || 'Checking local model'}</span></div>
    <section className="panel evidence-search-panel" aria-labelledby="evidence-search-title">
      <div className="panel-heading"><div><div className="eyebrow">LOCAL HYBRID RETRIEVAL</div><h3 id="evidence-search-title">Search stored evidence</h3></div>{searchResults && <StatePill state="ready">{searchResults.items.length} MATCHES</StatePill>}</div>
      <form className="evidence-search-controls" onSubmit={searchEvidence}><label className="sr-only" htmlFor="evidence-search-input">Search indexed document evidence</label><input id="evidence-search-input" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} minLength={2} maxLength={2000} placeholder="Search facts, names, amounts, or dates…" /><button className="button primary" disabled={searchBusy || searchQuery.trim().length < 2}>{searchBusy ? <><LoaderCircle size={14} className="spin" /> Searching…</> : <><Search size={14} /> Search</>}</button></form>
      {searchError && <ErrorState message={searchError} />}
      {searchResults && <div className="evidence-search-output" aria-live="polite"><div className="search-result-summary"><span>Query: “{searchResults.query}” · {searchResults.retrieval_method.replaceAll('_', ' ')}</span><span>{searchResults.items.length} result{searchResults.items.length === 1 ? '' : 's'}</span></div>
        {searchResults.diagnostics?.length > 0 && <ul className="search-diagnostics">{searchResults.diagnostics.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>}
        {searchResults.items.length ? <div className="evidence-search-results">{searchResults.items.map((item) => <article className="evidence-search-result" key={`${item.document_id}-${item.evidence_id}`}><div className="evidence-card-top"><span className="evidence-id">Evidence #{item.evidence_id}</span><span className="source-location">{sourceLocation(item)}</span></div><button className="search-result-source" onClick={() => onOpenDocument(item.document_id)}>{item.filename}</button><p>{item.text}</p><div className="evidence-card-foot"><span>{item.retrieval_method?.replaceAll('_', ' ') || 'Evidence retrieval'}{item.score != null ? ` · score ${item.score}` : ''}</span><span>{item.extraction_method.replaceAll('_', ' ')}</span></div></article>)}</div> : <div className="search-empty">No evidence matched this query. Check that documents are processed and indexed.</div>}
      </div>}
    </section>
    <section className="panel chat-panel">
      <div className="chat-header"><div className="chat-avatar"><BrainCircuit size={17} /></div><div><strong>CERBERUS-X Evidence Assistant</strong><small>{modelStatus ? `${modelStatus.strategy.replaceAll('_', ' ')} · ${modelStatus.indexed_chunks} indexed chunks` : 'Checking retrieval configuration'}</small></div><StatePill state={modelStatus ? 'ready' : 'checking'}>{modelStatus ? 'LOCAL RETRIEVAL' : 'CHECKING'}</StatePill></div>
      <div className="chat-history" aria-live="polite">
        {!messages.length && <div className="chat-welcome"><span className="welcome-icon"><MessageSquareText size={23} /></span><h2>Ask with your sources in view</h2><p>The assistant can only cite evidence returned by the local API. If support is missing, expect an explicit limitation or abstention.</p><div className="suggestion-row"><button onClick={() => setQuestion('What key dates and deadlines appear in my documents?')}>Find key dates</button><button onClick={() => setQuestion('What evidence supports the recorded project budget?')}>Review a budget</button></div></div>}
        <AnimatePresence initial={false}>{messages.map((message) => message.role === 'user'
          ? <motion.div key={message.id} className="chat-message user-message" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}><span>{message.text}</span></motion.div>
          : <motion.article key={message.id} className={`chat-message assistant-message ${message.abstained ? 'abstained-message' : ''}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div className="answer-heading">{message.abstained ? <CircleAlert size={16} /> : <ShieldCheck size={16} />}<strong>{message.abstained ? 'Insufficient evidence' : 'Evidence-grounded response'}</strong><span>{message.confidence}</span></div>
            <p className="answer-text">{message.answer}</p>
            {message.citations?.length > 0 && <div className="citation-grid"><div className="eyebrow">SOURCE CITATIONS · {message.citations.length}</div>{message.citations.map((citation) => <button key={`${message.id}-${citation.evidence_id}-${citation.citation_order}`} className="citation-card" onClick={() => onOpenDocument(citation.document_id)}>
              <span className="citation-mark">[{citation.citation_order}]</span><span className="citation-body"><strong>{citation.filename}</strong><small>Evidence #{citation.evidence_id} · {sourceLocation(citation)}</small><q>{citation.quoted_text || citation.text}</q></span><FileSearch size={15} />
            </button>)}</div>}
            {!message.citations?.length && <div className="no-citation-note">No source citations were returned for this answer.</div>}
            {message.limitations?.length > 0 && <details className="limitations"><summary>Limitations</summary><ul>{message.limitations.map((item) => <li key={item}>{item}</li>)}</ul></details>}
            <div className="answer-footer"><span>Model: {message.model_used}</span><span>Retrieval: {message.retrieval_method.replaceAll('_', ' ')}</span></div>
          </motion.article>)}
        </AnimatePresence>
        {busy && <div className="thinking-row"><span className="thinking-orb"><LoaderCircle size={16} className="spin" /></span><span>Waiting for the local model and retrieval service…</span></div>}
        {error && <ErrorState message={error} />}
        <div ref={endRef} />
      </div>
      <form className="chat-composer" onSubmit={ask}><label className="sr-only" htmlFor="ask-input">Ask a question about your evidence</label><textarea id="ask-input" value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form.requestSubmit() } }} maxLength={2000} placeholder="Ask about your stored evidence…" /><button className="send-button" aria-label="Send question" disabled={busy || question.trim().length < 3}><ArrowUp size={17} /></button></form>
      <div className="chat-disclaimer"><RotateCcw size={12} /> Answers and citations are returned by the local backend. No answer is generated in the browser.</div>
    </section>
  </div>
}
