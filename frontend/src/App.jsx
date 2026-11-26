import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, BrainCircuit, ChevronLeft, ChevronRight, FileSearch, FileText, LayoutDashboard, Network, PanelLeftClose, PanelLeftOpen, RefreshCw, ShieldAlert, ShieldCheck, Wifi, WifiOff } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { api } from './services/api'
import { LoadingBlock, StatePill } from './components/Primitives'
import './app.css'

const Dashboard = lazy(() => import('./pages/Dashboard.jsx'))
const DocumentsPage = lazy(() => import('./pages/DocumentsPage.jsx'))
const IntelligencePage = lazy(() => import('./pages/IntelligencePage.jsx'))
const ContradictionsPage = lazy(() => import('./pages/ContradictionsPage.jsx'))
const KnowledgeGraphPage = lazy(() => import('./pages/KnowledgeGraphPage.jsx'))
const ReliabilityPage = lazy(() => import('./pages/ReliabilityPage.jsx'))
const InvestigationsPage = lazy(() => import('./pages/InvestigationsPage.jsx'))

const NAVIGATION = [
  { id: 'dashboard', label: 'Command overview', group: 'Workspace', icon: LayoutDashboard },
  { id: 'documents', label: 'Document explorer', group: 'Workspace', icon: FileText },
  { id: 'intelligence', label: 'AI intelligence', group: 'Workspace', icon: BrainCircuit },
  { id: 'contradictions', label: 'Contradiction centre', group: 'Analysis', icon: ShieldAlert },
  { id: 'graph', label: 'Knowledge graph', group: 'Analysis', icon: Network },
  { id: 'investigations', label: 'Investigations', group: 'Analysis', icon: FileSearch },
  { id: 'reliability', label: 'Reliability & settings', group: 'System', icon: ShieldCheck },
]
const KNOWN_ROUTES = new Set(NAVIGATION.map((item) => item.id))

function routeFromHash() {
  const value = window.location.hash.replace(/^#\/?/, '').split('/')[0]
  return KNOWN_ROUTES.has(value) ? value : 'dashboard'
}

export default function App() {
  const [page, setPage] = useState(routeFromHash)
  const [compact, setCompact] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [health, setHealth] = useState({ state: 'checking', message: 'Connecting to local services' })
  const [requestedDocumentId, setRequestedDocumentId] = useState('')
  const reducedMotion = useReducedMotion()
  const current = useMemo(() => NAVIGATION.find((item) => item.id === page), [page])

  const checkHealth = useCallback(async () => {
    try {
      const [healthResult, system] = await Promise.all([api('/api/health'), api('/api/system/status')])
      setHealth({ state: system.status === 'ok' ? 'online' : 'degraded', message: `${healthResult.database} · ${system.upload_storage} storage` })
    } catch (cause) { setHealth({ state: 'offline', message: cause.message }) }
  }, [])

  useEffect(() => {
    const sync = () => { setPage(routeFromHash()); setMobileNav(false) }
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])
  useEffect(() => {
    checkHealth()
    const timer = window.setInterval(checkHealth, 30000)
    return () => window.clearInterval(timer)
  }, [checkHealth])

  const navigate = (next) => { window.location.hash = next; setPage(next); setMobileNav(false) }
  const openDocument = (documentId) => { setRequestedDocumentId(documentId); navigate('documents') }
  const clearRequestedDocument = () => setRequestedDocumentId('')

  let view
  if (page === 'documents') view = <DocumentsPage requestedDocumentId={requestedDocumentId} onDocumentOpened={clearRequestedDocument} />
  else if (page === 'intelligence') view = <IntelligencePage onOpenDocument={openDocument} />
  else if (page === 'contradictions') view = <ContradictionsPage onOpenDocument={openDocument} />
  else if (page === 'graph') view = <KnowledgeGraphPage onOpenDocument={openDocument} />
  else if (page === 'reliability') view = <ReliabilityPage onOpenDocument={openDocument} />
  else if (page === 'investigations') view = <InvestigationsPage onOpenDocument={openDocument} />
  else view = <Dashboard onNavigate={navigate} onOpenDocument={openDocument} />

  return <div className={`app-shell ${compact ? 'sidebar-compact' : ''} ${mobileNav ? 'mobile-nav-open' : ''} ${reducedMotion ? 'reduced-motion' : ''}`}>
    <aside className="sidebar" aria-label="Main navigation">
      <div className="sidebar-brand-row"><a className="brand-lockup" href="#dashboard"><span className="brand-glyph"><ShieldCheck size={19} /></span><span className="brand-name">CERBERUS<span>-X</span><small>EVIDENCE INTELLIGENCE</small></span></a><button className="collapse-button" onClick={() => setCompact((value) => !value)} aria-label={compact ? 'Expand navigation' : 'Collapse navigation'} title={compact ? 'Expand navigation' : 'Collapse navigation'}>{compact ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}</button></div>
      <div className="sidebar-overline">COMMAND SYSTEM <span>08</span></div>
      {['Workspace', 'Analysis', 'System'].map((group) => <div className="nav-group" key={group}><div className="nav-group-title">{group}</div>{NAVIGATION.filter((item) => item.group === group).map((item) => <a key={item.id} href={`#${item.id}`} className={`nav-link ${page === item.id ? 'active' : ''}`} aria-current={page === item.id ? 'page' : undefined} title={compact ? item.label : undefined} onClick={() => setMobileNav(false)}><item.icon size={17} /><span>{item.label}</span>{page === item.id && <ChevronRight size={14} className="nav-active-mark" />}</a>)}</div>)}
      <div className="sidebar-bottom"><div className={`api-mini ${health.state}`}><span className="api-dot" /><span className="api-mini-copy"><b>{health.state === 'online' ? 'Local API connected' : health.state === 'checking' ? 'Checking local API' : 'Local API unavailable'}</b><small>{health.message}</small></span></div><span className="sidebar-version">CERBERUS-X · PHASE 7</span></div>
    </aside>

    {mobileNav && <button className="mobile-scrim" onClick={() => setMobileNav(false)} aria-label="Close navigation" />}
    <div className="main-column">
      <header className="topbar"><button className="mobile-menu-button" onClick={() => setMobileNav((value) => !value)} aria-label="Toggle navigation">{mobileNav ? <ChevronLeft size={19} /> : <PanelLeftOpen size={18} />}</button><div className="breadcrumb"><span>Workspace</span><ChevronRight size={13} /><strong>{current?.label}</strong></div><div className="topbar-tools"><span className="local-pill"><span className={`api-dot ${health.state}`} /> LOCAL MODE</span><button className="topbar-refresh" title="Check API status" aria-label="Check API status" onClick={checkHealth}><RefreshCw size={15} /></button><StatePill state={health.state}>{health.state === 'online' ? 'API online' : health.state === 'checking' ? 'Checking' : health.state === 'degraded' ? 'Degraded' : 'Offline'}</StatePill></div></header>
      <main className="content-area" id="main-content" key={page}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div className="route-view" key={page} initial={reducedMotion ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={reducedMotion ? undefined : { opacity: 0, y: -4 }} transition={{ duration: reducedMotion ? 0 : 0.18 }}>
            <Suspense fallback={<LoadingBlock label="Opening workspace" />}>{view}</Suspense>
          </motion.div>
        </AnimatePresence>
      </main>
      <footer className="app-footer"><span>CERBERUS-X · LOCAL EVIDENCE INTELLIGENCE</span><span><Wifi size={12} /> Local processing · no cloud inference</span></footer>
    </div>
  </div>
}
