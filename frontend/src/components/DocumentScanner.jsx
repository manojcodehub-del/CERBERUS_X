export default function DocumentScanner({ active, filename }) {
  if (!active) return null
  return <div className="document-scanner" role="status" aria-live="polite">
    <div className="scanner-visual" aria-hidden="true"><span className="scanner-sheet"><i /><i /><i /><i /></span><span className="scanner-beam" /></div>
    <span><strong>Extraction request in progress</strong><small>{filename} · waiting for the local API response</small></span>
  </div>
}
