"""Normalize Phase 3 candidates while leaving their original values untouched."""

import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from app.models.claim import Claim
from app.models.document import Document
from app.models.evidence import Evidence

PROJECT_RE = re.compile(r"\b(?:project\s*(?:id|code)?\s*[:#-]?\s*)?([A-Z]{2,10}[-/][A-Z0-9]{2,}(?:[-/][A-Z0-9]+)*)\b", re.I)
MONEY_RE = re.compile(r"(?P<currency>₹|\bINR\b|\bUSD\b|\bEUR\b|\bGBP\b|\$|€|£)?\s*(?P<number>[-+]?\d[\d,]*(?:\.\d+)?)\s*(?P<scale>lakh|crore|million|thousand)?", re.I)
SCALE = {"lakh": Decimal("100000"), "crore": Decimal("10000000"), "million": Decimal("1000000"), "thousand": Decimal("1000")}
QUANTITY_UNITS = {
    "mm": ("m", Decimal("0.001")), "millimeter": ("m", Decimal("0.001")), "millimeters": ("m", Decimal("0.001")),
    "millimetre": ("m", Decimal("0.001")), "millimetres": ("m", Decimal("0.001")),
    "cm": ("m", Decimal("0.01")), "centimeter": ("m", Decimal("0.01")), "centimeters": ("m", Decimal("0.01")),
    "centimetre": ("m", Decimal("0.01")), "centimetres": ("m", Decimal("0.01")),
    "m": ("m", Decimal("1")), "meter": ("m", Decimal("1")), "meters": ("m", Decimal("1")),
    "metre": ("m", Decimal("1")), "metres": ("m", Decimal("1")),
    "km": ("m", Decimal("1000")), "kilometer": ("m", Decimal("1000")), "kilometers": ("m", Decimal("1000")),
    "kilometre": ("m", Decimal("1000")), "kilometres": ("m", Decimal("1000")),
    "mile": ("m", Decimal("1609.344")), "miles": ("m", Decimal("1609.344")),
    "mg": ("g", Decimal("0.001")), "milligram": ("g", Decimal("0.001")), "milligrams": ("g", Decimal("0.001")),
    "g": ("g", Decimal("1")), "gram": ("g", Decimal("1")), "grams": ("g", Decimal("1")),
    "kg": ("g", Decimal("1000")), "kgs": ("g", Decimal("1000")), "kilogram": ("g", Decimal("1000")), "kilograms": ("g", Decimal("1000")),
    "ml": ("ml", Decimal("1")), "milliliter": ("ml", Decimal("1")), "milliliters": ("ml", Decimal("1")),
    "millilitre": ("ml", Decimal("1")), "millilitres": ("ml", Decimal("1")),
    "l": ("ml", Decimal("1000")), "liter": ("ml", Decimal("1000")), "liters": ("ml", Decimal("1000")),
    "litre": ("ml", Decimal("1000")), "litres": ("ml", Decimal("1000")),
    "sec": ("minute", Decimal(1) / Decimal(60)), "second": ("minute", Decimal(1) / Decimal(60)), "seconds": ("minute", Decimal(1) / Decimal(60)),
    "min": ("minute", Decimal("1")), "minute": ("minute", Decimal("1")), "minutes": ("minute", Decimal("1")),
    "hour": ("minute", Decimal("60")), "hours": ("minute", Decimal("60")), "hr": ("minute", Decimal("60")), "hrs": ("minute", Decimal("60")),
    "day": ("minute", Decimal("1440")), "days": ("minute", Decimal("1440")),
    "acre": ("m2", Decimal("4046.8564224")), "acres": ("m2", Decimal("4046.8564224")),
    "hectare": ("m2", Decimal("10000")), "hectares": ("m2", Decimal("10000")),
    "unit": ("count", Decimal("1")), "units": ("count", Decimal("1")), "item": ("count", Decimal("1")),
    "items": ("count", Decimal("1")), "piece": ("count", Decimal("1")), "pieces": ("count", Decimal("1")), "pcs": ("count", Decimal("1")),
}
CURRENCY = {"₹": "INR", "INR": "INR", "RS": "INR", "$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP"}


def _currency(text: str) -> str | None:
    for marker, code in CURRENCY.items():
        found = marker in text.upper() if marker.isalpha() else marker in text
        if found:
            return code
    if re.search(r"\brupees?\b", text, re.I):
        return "INR"
    if re.search(r"\bdollars?\b", text, re.I):
        return "USD"
    return None


def _decimal_number(text: str) -> Decimal | None:
    match = MONEY_RE.search(text)
    if not match:
        return None
    raw = match.group("number").replace(",", "")
    try:
        number = Decimal(raw)
        scale = (match.group("scale") or "").casefold()
        return number * SCALE.get(scale, Decimal(1))
    except InvalidOperation:
        return None


def _normalized_date(value: str) -> str | None:
    candidates = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y")
    cleaned = value.strip().replace(",", "")
    for pattern in candidates:
        try:
            return datetime.strptime(cleaned, pattern).date().isoformat()
        except ValueError:
            continue
    try:
        return date.fromisoformat(cleaned).isoformat()
    except ValueError:
        return None


def _predicate(text: str, claim_type: str) -> tuple[str, str | None]:
    value = text.casefold()
    negated_budget = re.search(
        r"\b(?:not|never)\s+(?:(?:the|a|an)\s+)?approved\s+(?:project\s+)?budget\b"
        r"|\bapproved\s+(?:project\s+)?budget\b.{0,32}\b(?:is|was)\s+not\b",
        value,
    )
    if claim_type == "monetary_amount" and negated_budget:
        if re.search(r"\b(?:vendor\s+quotation|quotation\s+amount|quoted\s+amount)\b", value):
            return "procurement_estimate", "procurement_estimate"
        return "unapproved_budget", "unapproved_budget"
    mappings = (
        (r"approved\s+(?:project\s+)?budget|budget\s+(?:was\s+)?approved", "approved_budget"),
        (r"procurement\s+(?:estimate|budget)|vendor\s+quotation|quotation\s+amount|quoted\s+amount", "procurement_estimate"),
        (r"forecast(?:ed)?\s+(?:cost|amount|budget)|cost\s+forecast", "forecast_amount"),
        (r"invoice\s+(?:total|amount|value)|total\s+invoice", "invoice_amount"),
        (r"project\s+status|status\s*(?:is|=|:)", "project_status"),
        (r"payment\s+status|invoice\s+(?:is\s+)?(?:paid|unpaid|overdue)", "payment_status"),
        (r"(?:due|deadline|completion)\s+date|complete\s+by", "deadline"),
        (r"approval\s+date|approved\s+on", "approval_date"),
        (r"invoice\s+(?:no\.?|number|#)", "invoice_number"),
        (r"approval\s+(?:ref(?:erence)?|no\.?|number|#)", "approval_reference"),
        (r"(?:quantity|qty|units?|count)", "quantity"),
        (r"percent(?:age)?|\bof\s+total", "percentage"),
    )
    for pattern, predicate in mappings:
        if re.search(pattern, value):
            return predicate, predicate
    fallback = {
        "monetary_amount": "monetary_amount", "date": "date", "percentage": "percentage",
        "quantity": "quantity", "invoice_number": "invoice_number", "project_id": "project_identifier",
        "approval_reference": "approval_reference", "status_phrase": "status", "named_entity_candidate": "named_entity",
    }.get(claim_type, claim_type)
    return fallback, fallback


def _document_project_identifier(document: Document) -> str | None:
    identifiers: set[str] = set()
    for evidence in document.evidence:
        evidence_text = " ".join(part for part in (evidence.context_text, evidence.original_text) if part)
        identifiers.update(
            match.group(1).upper().replace("/", "-")
            for match in PROJECT_RE.finditer(evidence_text)
        )
    return next(iter(identifiers)) if len(identifiers) == 1 else None


def _source_location(evidence: Evidence) -> dict:
    return {
        "page_number": evidence.page_number,
        "sheet_name": evidence.sheet_name,
        "row_number": evidence.row_number,
        "column_name": evidence.column_name,
        "cell_coordinate": evidence.cell_coordinate,
        "paragraph_index": evidence.paragraph_index,
        "table_index": evidence.table_index,
    }


def _local_context(claim: Claim, evidence: Evidence) -> str:
    """Use the source sentence/cell containing this candidate to avoid mixing categories."""
    whole = " ".join(part for part in (claim.context, evidence.context_text, evidence.original_text) if part)
    needle = claim.value.casefold().strip()
    if not needle:
        return whole
    segments = [part.strip() for part in re.split(r"(?<=[.!?;])\s+|\n+", whole) if part.strip()]
    for segment in segments:
        if needle in segment.casefold():
            return segment[:4000]
    return whole


def normalize_claim(claim: Claim, evidence: Evidence, document: Document) -> bool:
    """Fill normalized columns once or refresh only if the source text changed."""
    full_context = " ".join(part for part in (claim.context, evidence.context_text, evidence.original_text) if part)
    context = _local_context(claim, evidence)
    predicate, category = _predicate(context, claim.claim_type)
    project_match = PROJECT_RE.search(full_context)
    project_id = project_match.group(1).upper().replace("/", "-") if project_match else None
    if project_id is None:
        project_id = _document_project_identifier(document)
    amount = _decimal_number(claim.value) if claim.claim_type == "monetary_amount" else None
    currency = _currency(claim.value) if claim.claim_type == "monetary_amount" else None
    unit = None
    object_value = claim.value.strip()
    date_value = _normalized_date(claim.value) if claim.claim_type == "date" else None

    if amount is not None:
        object_value = format(amount.normalize(), "f")
        unit = "currency"
    elif claim.claim_type == "quantity":
        match = re.search(r"([-+]?\d[\d,]*(?:\.\d+)?)\s*([A-Za-z]+)?", claim.value)
        if match:
            try:
                amount_value = Decimal(match.group(1).replace(",", ""))
                raw_unit = (match.group(2) or "count").casefold().rstrip(".")
                canonical_unit, factor = QUANTITY_UNITS.get(raw_unit, (raw_unit or "count", Decimal("1")))
                object_value = format((amount_value * factor).normalize(), "f")
                unit = canonical_unit
            except InvalidOperation:
                pass
    elif date_value:
        object_value = date_value
        unit = "date"
    elif claim.claim_type == "status_phrase":
        object_value = re.sub(r"\s+", " ", claim.value.strip().casefold())

    subject = f"Project {project_id}" if project_id else (document.original_filename[:512] if predicate == "named_entity" else None)
    full = context.casefold()
    period_match = re.search(r"\b(?:fy\s*\d{2,4}(?:[-/]\d{2,4})?|(?:q[1-4]|january|february|march|april|may|june|july|august|september|october|november|december)\s*\d{0,4})\b", full)
    period = period_match.group(0).upper() if period_match else None
    if claim.claim_type == "status_phrase" and date_value is None:
        date_match = re.search(r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})\b", context, re.I)
        date_value = _normalized_date(date_match.group(0)) if date_match else None

    changed = any((claim.normalization_method != "phase5-deterministic-v1", claim.predicate != predicate,
                   claim.object_value != object_value, claim.entity != project_id))
    claim.subject = subject
    claim.predicate = predicate
    claim.object_value = object_value
    claim.entity = project_id
    claim.category = category
    claim.unit = unit
    claim.currency = currency
    claim.claim_date = date_value
    claim.time_period = period
    claim.project_identifier = project_id
    claim.document_identifier = document.id
    claim.source_location = json.dumps(_source_location(evidence), ensure_ascii=False, sort_keys=True)
    claim.normalization_method = "phase5-deterministic-v1"
    claim.normalized_at = datetime.now(timezone.utc)
    return changed
