"""Deterministic candidate claim extraction; results always retain evidence links."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimCandidate:
    claim_type: str
    value: str
    context: str


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("monetary_amount", re.compile(r"(?:₹|\bINR\b|\bUSD\b|\bRs\.?\s*|[$€£])\s*[-+]?\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|crore|million|thousand))?|\b\d[\d,]*(?:\.\d+)?\s*(?:INR|USD|rupees?|dollars?)\b", re.I)),
    ("date", re.compile(r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b", re.I)),
    ("percentage", re.compile(r"\b\d+(?:\.\d+)?\s*%")),
    ("invoice_number", re.compile(r"\b(?:invoice|inv)\s*(?:no\.?|number|#|:)?\s*([A-Z]{0,8}[-/]?\d[A-Z0-9/-]*)\b", re.I)),
    ("project_id", re.compile(r"\bproject\s*(?:(?:id|code)\b|[:#])\s*[:#-]?\s*([A-Z]{2,10}[-/][A-Z0-9]{2,}(?:[-/][A-Z0-9]+)*)\b", re.I)),
    ("approval_reference", re.compile(r"\b(?:approval|approved|sanction)\s*(?:ref(?:erence)?|no\.?|number|#|id)\s*[:#-]?\s*([A-Z]{0,8}[-/]?\d[A-Z0-9/-]*)\b", re.I)),
    ("quantity", re.compile(r"\b(?:qty|quantity|units?|count)\s*[:=#-]?\s*\d+(?:\.\d+)?\s*[A-Za-z]*\b|\b\d+(?:\.\d+)?\s*(?:units?|items?|pieces?|pcs|employees?|days?|hours?|kg|g|km|meters?|metres?|liters?|litres?|tons?|tonnes?|miles?|acres?|hectares?)\b", re.I)),
    ("status_phrase", re.compile(r"\b(?:pending approval|approved|rejected|in progress|on hold|completed|cancelled|canceled|paid|unpaid|overdue|submitted)\b", re.I)),
    ("named_entity_candidate", re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,3}\b")),
)


def extract_claim_candidates(text: str, context: str | None = None) -> list[ClaimCandidate]:
    if not text.strip():
        return []
    search_text = context or text
    result: list[ClaimCandidate] = []
    seen: set[tuple[str, str]] = set()
    for claim_type, pattern in PATTERNS:
        for match in pattern.finditer(search_text):
            value = match.group(1) if claim_type in {"invoice_number", "project_id", "approval_reference"} and match.lastindex else match.group(0)
            value = value.strip()
            key = (claim_type, value.casefold())
            if key not in seen:
                seen.add(key)
                result.append(ClaimCandidate(claim_type, value, search_text[:2000]))
    return result
