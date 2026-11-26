import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Background, Controls, ReactFlow } from '@xyflow/react'
import { Box, FileText, RefreshCw, RotateCcw, Share2 } from 'lucide-react'
import { api, pretty, sourceLocation } from '../services/api'
import { EmptyState, ErrorState, LoadingBlock, StatePill } from '../components/Primitives'
import '@xyflow/react/dist/style.css'

const Graph3D = lazy(() => import('../components/EvidenceGalaxy.jsx'))
const PALETTE = { document: '#2563eb', claim: '#00c8ff', evidence: '#16a34a', event: '#f59e0b', conflict: '#ef4444', entity: '#8b5cf6' }

export default function KnowledgeGraphPage({ onOpenDocument }) {
  const [graph, setGraph] = useState(null)
  const [selected, setSelected] = useState(null)
  const [selectedNeighborhood, setSelectedNeighborhood] = useState(null)
  const [mode, setMode] = useState('3d')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const orbitControlsRef = useRef(null)
  const flowInstanceRef = useRef(null)

  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try { setGraph(await api('/api/knowledge-graph?limit=500')); setSelected(null); setSelectedNeighborhood(null) }
    catch (cause) { setError(cause.message) } finally { setLoading(false) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
    if (!gl) setMode('2d')
    else gl.getExtension('WEBGL_lose_context')?.loseContext()
  }, [])

  const onSelect = useCallback(async (node) => {
    setSelected(node); setSelectedNeighborhood(null)
    if (!node?.id) return
    try { setSelectedNeighborhood(await api(`/api/knowledge-graph/entities/${node.id}`)) }
    catch (cause) { setError(cause.message) }
  }, [])

  const resetView = useCallback(() => {
    if (mode === '3d') orbitControlsRef.current?.reset()
    else flowInstanceRef.current?.fitView({ padding: 0.2 })
  }, [mode])

  const clearSelection = () => {
    setSelected(null)
    setSelectedNeighborhood(null)
  }

  const visible = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] }
    const nodes = graph.nodes.slice(0, 120)
    const ids = new Set(nodes.map((node) => node.id))
    return { nodes, edges: graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)).slice(0, 360) }
  }, [graph])

  const flow = useMemo(() => {
    const columns = Math.max(1, Math.ceil(Math.sqrt(visible.nodes.length)))
    const flowNodes = visible.nodes.map((node, index) => ({ id: String(node.id), position: { x: (index % columns) * 205, y: Math.floor(index / columns) * 125 }, data: { label: node.label }, style: { color: '#e5f1fa', background: '#111c30', border: `1px solid ${PALETTE[node.type] || PALETTE.entity}`, borderRadius: 10, padding: '11px 13px', width: 180, fontSize: 11, boxShadow: node.id === selected?.id ? '0 0 0 1px #00c8ff88, 0 0 18px #00c8ff33' : 'none' } }))
    const flowEdges = visible.edges.map((edge) => ({ id: String(edge.id), source: String(edge.source), target: String(edge.target), animated: edge.relationship?.includes('CONFLICT'), style: { stroke: edge.relationship?.includes('CONFLICT') ? '#ef4444' : '#3b82a0' } }))
    return { nodes: flowNodes, edges: flowEdges }
  }, [visible, selected])

  const selectedLocation = selected ? sourceLocation(selected.metadata?.source_location || selected.metadata || {}) : ''

  return <div className="page-stack graph-page">
    <div className="page-intro"><div><div className="eyebrow">PERSISTED NETWORKX DATA</div><h1>Knowledge graph</h1><p>Explore actual document, evidence, claim, conflict, and entity records. Every displayed relationship comes from an evidence-backed API edge.</p></div><button className="icon-button" onClick={refresh} aria-label="Refresh graph"><RefreshCw size={16} /></button></div>
    {error && <ErrorState message={error} onRetry={refresh} />}
    {loading ? <LoadingBlock label="Building the persisted graph view" /> : graph && <>
      <div className="graph-toolbar panel">
        <div className="graph-counts"><span><b>{graph.node_count}</b> nodes</span><span><b>{graph.edge_count}</b> relationships</span>{graph.nodes.length > visible.nodes.length && <small>Rendering {visible.nodes.length} nodes for performance</small>}</div>
        <div className="graph-actions">
          <div className="view-toggle" role="group" aria-label="Graph rendering mode">
            <button type="button" className={mode === '3d' ? 'active' : ''} aria-pressed={mode === '3d'} onClick={() => setMode('3d')}><Box size={14} /> 3D</button>
            <button type="button" className={mode === '2d' ? 'active' : ''} aria-pressed={mode === '2d'} onClick={() => setMode('2d')}><Share2 size={14} /> 2D</button>
          </div>
          <button type="button" className="button secondary graph-reset" onClick={resetView} title={mode === '3d' ? 'Reset camera position' : 'Fit all visible nodes'}><RotateCcw size={13} /> Reset view</button>
        </div>
      </div>
      {!visible.nodes.length ? <EmptyState icon={Share2} title="The knowledge graph is empty" detail="Process documents and normalize their candidate claims to create evidence-linked graph records." /> : <div className="graph-layout">
        <section className="panel graph-panel">
          <div className="graph-legend">{Object.entries(PALETTE).map(([type, color]) => <span key={type}><i style={{ background: color }} />{pretty(type)}</span>)}</div>
          <div className="graph-viewport">
            {mode === '3d' ? <Suspense fallback={<LoadingBlock label="Loading local 3D graph" />}><Graph3D nodes={visible.nodes} edges={visible.edges} selectedId={selected?.id} onSelect={onSelect} controlsRef={orbitControlsRef} /></Suspense> : <div className="graph-canvas graph-canvas-2d"><ReactFlow nodes={flow.nodes} edges={flow.edges} fitView minZoom={0.15} maxZoom={2} onInit={(instance) => { flowInstanceRef.current = instance }} onNodeClick={(_, node) => { const item = visible.nodes.find((entry) => String(entry.id) === node.id); if (item) onSelect(item) }}><Background color="#1c2b3b" gap={24} /><Controls /></ReactFlow></div>}
          </div>
          <div className="graph-relationship-note"><i /> Conflicting relationships are highlighted in red.</div>
        </section>
        <aside className="panel entity-panel"><div className="panel-heading"><div><div className="eyebrow">ENTITY INSPECTOR</div><h3>{selected?.label || 'Select a node'}</h3></div>{selected && <div className="entity-heading-actions"><StatePill state={selected.type}>{pretty(selected.type)}</StatePill><button type="button" className="text-button graph-clear-selection" onClick={clearSelection} aria-label="Clear selected graph node">Clear</button></div>}</div>
          {!selected ? <EmptyState icon={RotateCcw} title="No node selected" detail="Select a graph node to inspect its actual database identifiers and adjacent evidence-backed relationships." /> : <>
            <dl className="entity-details"><dt>Graph node</dt><dd>#{selected.id} · {selected.key}</dd>{selected.entity_type && <><dt>Entity category</dt><dd>{pretty(selected.entity_type)}</dd></>}{selected.document_id && <><dt>Document ID</dt><dd className="break-id">{selected.document_id}</dd></>}{selected.claim_id && <><dt>Claim ID</dt><dd>#{selected.claim_id}</dd></>}{selected.evidence_id && <><dt>Evidence ID</dt><dd>#{selected.evidence_id}</dd></>}{selected.conflict_id && <><dt>Conflict ID</dt><dd>#{selected.conflict_id}</dd></>}{selected.metadata?.date && <><dt>Event date</dt><dd>{selected.metadata.date}</dd></>}{selectedLocation !== 'Location not provided by source' && <><dt>Source location</dt><dd>{selectedLocation}</dd></>}</dl>
            {selected.type === 'evidence' && <div className="entity-source-excerpt">{selected.label}</div>}
            {selected.document_id && <button className="button secondary full-width" onClick={() => onOpenDocument(selected.document_id)}><FileText size={14} /> Open source document</button>}
            {selectedNeighborhood && <div className="adjacency-list"><div className="eyebrow">CONNECTED RELATIONSHIPS · {selectedNeighborhood.edges.length}</div>{selectedNeighborhood.edges.slice(0, 12).map((edge) => <div className="adjacency-item" key={edge.id}><span>{pretty(edge.relationship)}</span><small>Evidence #{edge.evidence_id}</small><p>{edge.explanation}</p></div>)}</div>}
            {selectedNeighborhood && selectedNeighborhood.edges.length === 0 && <p className="honesty-note">No adjacent relationships were returned for this node.</p>}
          </>}
        </aside>
      </div>}
    </>}
  </div>
}
