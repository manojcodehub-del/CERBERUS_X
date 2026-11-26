import { AlertTriangle, CheckCircle2, CircleDashed, LoaderCircle, WifiOff } from 'lucide-react'

export function StatePill({ state, children }) {
  const normalized = String(state || 'unknown').toLowerCase()
  const Icon = ['ok', 'online', 'ready', 'connected', 'available', 'processed', 'completed'].includes(normalized)
    ? CheckCircle2
    : ['checking', 'processing', 'running', 'queued', 'validating'].includes(normalized)
      ? LoaderCircle
      : ['offline', 'unavailable', 'failed', 'error', 'degraded'].includes(normalized)
        ? (normalized === 'offline' || normalized === 'unavailable' ? WifiOff : AlertTriangle)
        : CircleDashed
  return <span className={`state-pill state-${normalized}`}><Icon size={13} />{children || normalized}</span>
}

export function LoadingBlock({ label = 'Loading local data' }) {
  return <div className="loading-block"><LoaderCircle className="spin" size={18} />{label}</div>
}

export function EmptyState({ title, detail, icon: Icon = CircleDashed }) {
  return <div className="empty-state"><Icon size={24} /><strong>{title}</strong><span>{detail}</span></div>
}

export function ErrorState({ message, onRetry }) {
  return <div className="error-state" role="alert"><AlertTriangle size={18} /><div><strong>Local request failed</strong><span>{message}</span></div>{onRetry && <button className="button subtle" onClick={onRetry}>Retry</button>}</div>
}
