import re
from typing import Literal

from pydantic import Field

from app.domain.models import EmailCategory, StrictModel


class Classification(StrictModel):
    category: EmailCategory
    ambiguous: bool
    evidence_span_ids: tuple[str, ...] = Field(max_length=20)
    reason_code: Literal[
        "comparison_action",
        "new_si_action",
        "billing_action",
        "informational",
        "irrelevant",
        "conflicting_intent",
    ]


def segment_email(subject: str, body: str) -> list[dict[str, str]]:
    # Keep original text elsewhere; quoted instructions do not override current intent.
    boundary = re.search(
        r"(?im)^\s*(?:on .+wrote:|from:\s|[-_]{2,}\s*(?:original|forwarded) message|>)", body
    )
    current = body[: boundary.start()] if boundary else body
    history = body[boundary.start() :] if boundary else ""
    return [
        {"id": "subject", "kind": "subject", "text": subject},
        {"id": "current", "kind": "current", "text": current},
        {"id": "history", "kind": "quoted_history", "text": history[:8000]},
    ]


# Verb stems, so "for checking" or "amendment" count as comparison actions like "check" or "amend".
_COMPARE_VERB = (
    r"(?:check(?:ing)?|compar(?:e|ing)|verif(?:y|ying|ication)|amend(?:ing|ments?)?"
    r"|review(?:ing)?|confirm(?:ing|ation)?)"
)
_BL = r"(?:draft\s+)?(?:b/?l|bill of lading)"

# Automated security banners mention "attachments" in every message; they are not a claim.
_BANNER = re.compile(r"(?im)^\s*warning:.*$")
_ATTACHMENT_CLAIM = re.compile(
    r"\b(?:attached|attachments?|enclosed|enclosure)\b|\bfind (?:the )?(?:si|bl|draft)\b", re.I
)
# A bulk reminder about every pending shipment is a notice, not a request for one shipment's SI.
_BILLING_CUE = re.compile(
    # "invoice" is deliberately absent: a Commercial Invoice is also a document people attach.
    r"\b(?:charged?|charges|fees?|refund|credit note|debit note|payment|billed)\b"
)
_BULK_REMINDER =re.compile(r"\breminder\b.{0,120}\ball\s+(?:pending|outstanding)\s+shipments?\b", re.S)


_DRAFT_REQUEST = re.compile(
    r"\b(?:send|provide|share|forward|issue)\b.{0,40}\b(?:draft\s+)?(?:b/?l|bill of lading)\b", re.I | re.S
)


def _current_message(subject: str, body: str) -> str:
    return _BANNER.sub("", segment_email(subject, body)[1]["text"])


def attachments_expected(subject: str, body: str) -> bool:
    """True when the current message itself says documents are attached."""
    return bool(_ATTACHMENT_CLAIM.search(_current_message(subject, body)))


def requests_draft(subject: str, body: str) -> bool:
    """True when the sender is asking for the draft BL to be sent, so no documents are due yet."""
    return bool(_DRAFT_REQUEST.search(_current_message(subject, body)))


def classify_explicit(subject: str, body: str) -> Classification | None:
    text = f"{subject}\n{segment_email(subject, body)[1]['text']}".casefold()
    current = segment_email(subject, body)[1]["text"].casefold()
    subject_lower = subject.casefold()

    if _BULK_REMINDER.search(current):
        return Classification(
            category="GENERAL",
            ambiguous=False,
            evidence_span_ids=("current",),
            reason_code="informational",
        )

    # 1. SPAM detection (phishing, prizes, storage scams, generic lures)
    spam_patterns = (
        r"\b(?:congratulations!?\s+you\s+have\s+won|gift\s+card|claim\s+now|parcel\s+is\s+on\s+hold)\b",
        r"\b(?:mailbox\s+(?:is\s+full|exceeded)|verify\s+account\s+immediately|avoid\s+suspension|avoid\s+deactivation)\b",
        r"\b(?:exclusive\s+offer|90%\s+off|bitcoin\s+investment|guaranteed\s+300%|hot\s+singles)\b",
        r"\b(?:urgent\s+business\s+proposal|usd\s+\d+\s+million|undelivered\s+messages\s+in\s+your\s+mailbox)\b",
        r"http://(?:bit\.ly|track-parcel|webmail-verify|free-iphone)",
    )
    if any(re.search(p, text) for p in spam_patterns):
        return Classification(
            category="SPAM",
            ambiguous=False,
            evidence_span_ids=("subject", "current"),
            reason_code="irrelevant",
        )

    # 2. High-precision rule set for operational categories
    rules = {
        "BL_COMPARISON": (
            r"\b(?:to confirm docs|request bl draft)\b|"
            rf"\b{_COMPARE_VERB}\b.{{0,80}}\b{_BL}\b|"
            rf"\b{_BL}\b.{{0,80}}\b{_COMPARE_VERB}\b|"
            r"\b(?:draft bl against the si|si and draft bl|check the draft bl)\b",
            "comparison_action",
        ),
        "SI_REQUEST": (
            r"\b(?:cust si|request si|si needed|latest si)\b|"
            r"\b(?:prepare|create|provide|submit)\b.{0,60}\b(?:si|shipping instructions?)\b|"
            r"\bshipping instructions? for\b",
            "new_si_action",
        ),
        "INVOICE_QUERY": (
            r"\b(?:missing gr|cancel invoice|local charges|d\s*&\s*d charges|total freight)\b|"
            r"\b(?:invoice|billing|payment)\b.{0,60}\b(?:query|incorrect|cancel|dispute|missing|breakdown|charges)\b|"
            r"\b(?:cancel|dispute)\b.{0,60}\binvoice\b",
            "billing_action",
        ),
        "GENERAL": (
            r"\b(?:update summary|daily berthing report|_reminder_paper|rpa bot|outstanding bl|pending bl release)\b|"
            r"\b(?:welcoming the new year|time off request|miss connection|delivery planning|automated notification|no action required)\b|"
            r"\bwishing everyone\b.{0,60}\bnew year\b|\boffice resumes\b|_rpa_",
            "informational",
        ),
    }

    matches = [
        (category, reason)
        for category, (pattern, reason) in rules.items()
        if re.search(pattern, current, re.S)
    ]
    if matches == [("BL_COMPARISON", "comparison_action")] and _BILLING_CUE.search(current):
        # A billing complaint that merely mentions the draft BL ("charged $75 for the BL amendment")
        # is not a comparison request. Defer to the AI or a person instead of answering wrongly.
        return None
    evidence = "current"
    if not matches:
        matches = [
            (category, reason)
            for category, (pattern, reason) in rules.items()
            if re.search(pattern, subject_lower, re.S)
        ]
        evidence = "subject"
    if len(matches) == 1:
        category, reason = matches[0]
        return Classification(
            category=category, ambiguous=False, evidence_span_ids=(evidence,), reason_code=reason
        )
    return None


def classify_intent_safe(subject: str, body: str) -> Classification:
    """Legacy caller contract; ambiguity must never be scored as a prediction."""
    return classify_explicit(subject,body) or Classification(
        category="GENERAL",ambiguous=True,evidence_span_ids=("current",),reason_code="conflicting_intent")
