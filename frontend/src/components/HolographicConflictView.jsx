import { ArrowLeftRight } from 'lucide-react'
import { sourceLocation } from '../services/api'

export default function HolographicConflictView({ conflict, onOpenDocument }) {
  return <div className="holographic-conflict-view">
    <ClaimSide claim={conflict.claim_a} evidenceId={conflict.evidence_a_id} label="ASSERTION A" onOpenDocument={onOpenDocument} />
    <div className="comparison-link"><span className="comparison-beam" /><ArrowLeftRight size={16} /><span>COMPARE</span></div>
    <ClaimSide claim={conflict.claim_b} evidenceId={conflict.evidence_b_id} label="ASSERTION B" onOpenDocument={onOpenDocument} />
  </div>
}

function ClaimSide({ claim, evidenceId, label, onOpenDocument }) {
  if (!claim) return <div className="claim-side missing"><span className="eyebrow">{label}</span><strong>Claim detail unavailable</strong><small>Evidence #{evidenceId}</small></div>
  const location = claim.source_location || {}
  const predicate = claim.predicate || claim.claim_type
  const subject = claim.subject || claim.entity || claim.filename || 'Claim'
  return <div className="claim-side">
    <span className="eyebrow">{label}</span>
    <strong className="claim-subject">{subject}</strong>
    <div className="claim-predicate">{predicate} <b>{claim.object_value || claim.normalized_value || claim.value}</b></div>
    <div className="claim-values"><span><small>Original value</small>{claim.value ?? 'Not provided'}</span><span><small>Normalized value</small>{claim.normalized_value ?? 'Not provided'}</span></div>
    <button className="source-link" disabled={!claim.document_id} onClick={() => onOpenDocument(claim.document_id)}><span>{claim.filename || `Document ${claim.document_id ?? 'unavailable'}`}</span><small>Evidence #{claim.evidence_id} · {sourceLocation(location)}</small></button>
  </div>
}
