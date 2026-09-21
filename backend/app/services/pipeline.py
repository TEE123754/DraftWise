"""End-to-end processing pipeline from inbox record to discrepancy report and submission prediction."""

from dataclasses import dataclass
from typing import Callable

from app.ai.grounding import ground_extraction
from app.benchmark.export import Prediction, ReviewReason, export_prediction
from app.config import Settings
from app.domain.errors import DomainError
from app.domain.models import VerificationReport
from app.infrastructure.parsing import parse_bounded
from app.parsers.registry import parse_document
from app.services.ai_fallback import fill_missing_with_ai
from app.services.classification import (
    attachments_expected,
    classify_explicit,
    classify_intent_safe,
    requests_draft,
)
from app.services.dataset_import import InputEmail
from app.services.email_extraction import extract_email_body
from app.services.extraction import extract_labelled
from app.services.pairing import pair_within_email
from app.services.verification import verify


@dataclass(frozen=True)
class PipelineResult:
    email_id: str
    prediction: Prediction
    report: VerificationReport | None = None
    category: str = "GENERAL"


def no_attachment_prediction(subject: str, body: str) -> Prediction:
    """A comparison email with no files: a request that the draft be sent is only waiting; any other
    request to check documents that never arrived needs a person."""
    if requests_draft(subject, body) and not attachments_expected(subject, body):
        return export_prediction("BL_COMPARISON", awaiting_documents=True)
    return export_prediction("BL_COMPARISON", review_reason="missing_attachment")


def process_email_record(
    email: dict,
    read_attachment_bytes: Callable[[str], bytes],
    settings: Settings | None = None,
    ai=None,
) -> PipelineResult:
    """Execute the complete 4-stage verification workflow for a single email record."""
    settings = settings or Settings()
    if isinstance(email, InputEmail):
        return process_typed_record(email, read_attachment_bytes, settings)
    email_id = str(email.get("email_id") or email.get("id") or "unknown")
    subject = str(email.get("subject", ""))
    body = str(email.get("body", ""))
    attachments = list(email.get("attachments") or [])

    # -------------------------------------------------------------------------
    # Stage 1: Classification & Intent Gating
    # -------------------------------------------------------------------------
    classification = classify_intent_safe(subject, body)
    if classification.ambiguous:
        raise DomainError("UNRESOLVED_CLASSIFICATION", "Review email intent before exporting a prediction")
    category = classification.category

    # Gate downstream checks: Only BL_COMPARISON proceeds to document verification
    if category != "BL_COMPARISON":
        pred = export_prediction(category=category)
        return PipelineResult(email_id=email_id, prediction=pred, category=category)

    # -------------------------------------------------------------------------
    # Stage 2: Attachment Retrieval, Parsing & Field Extraction
    # -------------------------------------------------------------------------
    if not attachments:
        pred = no_attachment_prediction(subject, body)
        return PipelineResult(email_id=email_id, prediction=pred, category=category)

    parsed_docs = []
    extractions = []
    qualities = {}
    has_unreadable = False

    for att_path in attachments:
        try:
            raw_bytes = read_attachment_bytes(att_path)
            doc = parse_document(raw_bytes, source_id=att_path, settings=settings)
            parsed_docs.append(doc)
            ext = extract_labelled(doc)
            # AI fills only fields the labelled extractor missed; failures leave `ext` unchanged.
            ext = fill_missing_with_ai(ext, doc, settings, ai)
            extractions.append(ext)
            qualities.update(ground_extraction(ext, doc))
            scanned = any(b.kind == "ocr" for b in doc.blocks)
            if scanned and (ext.document_type == "UNKNOWN" or any(b.quality == 0.0 for b in doc.blocks)):
                # A scan whose type cannot even be recognised is unreadable, not a wrong document.
                has_unreadable = True
        except Exception:
            # File reading or parsing failure triggers unreadable review
            has_unreadable = True

    # Document pairing (SI vs BL)
    pair = pair_within_email(extractions)
    if pair.si is None or pair.bl is None:
        # A file that arrived but could not be opened is unreadable, not a missing attachment.
        reason_str = "unreadable" if has_unreadable else (pair.review_reason or "missing_attachment")
        valid_reason: ReviewReason = (
            reason_str if reason_str in {"wrong_doc_type", "missing_attachment", "unreadable", "missing_value"}
            else "missing_attachment"
        )
        pred = export_prediction("BL_COMPARISON", report=None, review_reason=valid_reason)
        return PipelineResult(email_id=email_id, prediction=pred, category=category)

    # -------------------------------------------------------------------------
    # Stage 3: Field-by-Field Verification & Exception Handling
    # -------------------------------------------------------------------------
    report = verify(pair.si, pair.bl, email_id=email_id, evidence_quality=qualities)

    # -------------------------------------------------------------------------
    # Stage 4: Compile Verification Report & Benchmark Prediction
    # -------------------------------------------------------------------------
    review_reason: ReviewReason | None = None
    if report.status == "NEEDS_REVIEW":
        review_reason = "unreadable" if has_unreadable else "missing_value"

    pred = export_prediction("BL_COMPARISON", report=report, review_reason=review_reason)
    return PipelineResult(email_id=email_id, prediction=pred, report=report, category=category)


def process_typed_record(email, read_attachment_bytes, settings):
    """Maintain the typed input runner contract with explicit unresolved results."""
    result = {"email_id": email.email_id, "prediction": None, "errors": [],
              "body_extraction": extract_email_body(email.email_id, email.subject, email.body)}
    classification = classify_explicit(email.subject, email.body)
    if classification is None:
        result["review_reason"] = "unresolved_classification"
        return result
    category = classification.category
    if category != "BL_COMPARISON":
        result["prediction"] = export_prediction(category).model_dump(mode="json")
        return result
    documents, qualities = [], {}
    for path in email.attachments:
        try:
            document = parse_bounded(read_attachment_bytes(path), path, settings)
            extraction = extract_labelled(document)
            qualities.update(ground_extraction(extraction, document))
            documents.append(extraction)
        except (DomainError, OSError, ValueError) as exc:
            result["errors"].append({"attachment": path, "code": getattr(exc,"code","FILE_ERROR")})
    si = [doc for doc in documents if doc.document_type == "SI"]
    bl = [doc for doc in documents if doc.document_type == "BL"]
    reason = "unreadable" if result["errors"] else "wrong_doc_type" if len(si) != 1 or len(bl) != 1 else None
    if not email.attachments:
        prediction = no_attachment_prediction(email.subject, email.body)
    elif reason:
        prediction = export_prediction(category, review_reason=reason)
    else:
        report = verify(si[0], bl[0], email_id=email.email_id, evidence_quality=qualities)
        result["report"] = report.model_dump(mode="json")
        prediction = export_prediction(category, report)
    result["prediction"] = prediction.model_dump(mode="json")
    return result
