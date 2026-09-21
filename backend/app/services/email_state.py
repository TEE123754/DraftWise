"""One review state per email, derived from facts already in the database.

Pure and local: no I/O and no AI. The inbox, its filters and its counts all use this one function,
so a row's colour, reasons and recommended action can never disagree with each other.
"""

from dataclasses import dataclass

from app.services.classification import attachments_expected, requests_draft

RED, YELLOW, GREEN, GREY = "red", "yellow", "green", "grey"

STATES = {
    "spam": ("Spam", RED),
    "held": ("Held for safety", RED),
    "processing": ("Processing", GREY),
    "needs_documents": ("Needs documents", YELLOW),
    "waiting_for_draft": ("Waiting for draft", YELLOW),
    "needs_review": ("Needs review", YELLOW),
    "mismatch_found": ("Mismatch found", YELLOW),
    "checked": ("Checked", GREEN),
    "classified": ("Classified", GREEN),
}

# The states that need a person, most urgent first. Waiting for a draft is not here: nothing can be done
# until the sender replies.
ATTENTION_ORDER = ("held", "mismatch_found", "needs_review", "needs_documents")

REASONS = {
    "safety_hold": "Held for safety review",
    "unclassified": "The request type could not be decided",
    "missing_si": "Shipping instructions not found",
    "missing_bl": "Draft bill of lading not found",
    "attachments_absent": "The email says files are attached, but none arrived",
    "awaiting_draft": "Asks for the draft BL to be sent; nothing to compare yet",
    "wrong_doc_type": "A document is not shipping instructions or a draft BL",
    "unrecognised_document": "A document's type could not be recognised",
    "unreadable": "A file could not be read",
    "processing_failed": "Processing failed",
    "documents_unread": "The documents have not been read yet",
    "not_compared": "Documents read but not compared yet",
}

# What to do next, by category, when nothing else applies.
CATEGORY_ACTIONS = {
    "SI_REQUEST": ("reply_si", "Send the shipping instruction template or prepare the SI"),
    "INVOICE_QUERY": ("reply_invoice", "Review the charges and reply to the sender"),
    "GENERAL": ("none", "No action needed: read and archive"),
}
OTHER_DOCUMENT_ROLES = {"INVOICE", "PACKING_LIST", "CERTIFICATE"}


@dataclass(frozen=True)
class EmailFacts:
    category: str | None  # None when unclassified or ambiguous
    risk_state: str | None = None  # email_safety.risk_state
    held: bool = False
    attachment_count: int = 0
    quarantined: int = 0  # attachments that failed validation
    unread: int = 0  # attachments with no extraction yet
    roles: tuple[str, ...] = ()  # document role of each read attachment
    job_active: bool = False
    job_state: str | None = None  # state of the latest job for this email
    report_status: str | None = None  # OK | MISMATCH | NEEDS_REVIEW
    mismatch_fields: tuple[str, ...] = ()
    unresolved_fields: tuple[str, ...] = ()
    subject: str = ""
    body_head: str = ""  # start of the body, only needed for BL emails with no attachments


@dataclass(frozen=True)
class EmailState:
    state: str
    reasons: tuple[dict, ...]
    action: dict

    @property
    def label(self) -> str:
        return STATES[self.state][0]

    @property
    def tone(self) -> str:
        return STATES[self.state][1]

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "state_label": self.label,
            "tone": self.tone,
            "reasons": list(self.reasons),
            "action": self.action,
        }


def _reason(code: str, fields: tuple[str, ...] = (), label: str | None = None) -> dict:
    item = {"code": code, "label": label or REASONS[code]}
    if fields:
        item["fields"] = list(fields)
    return item


def _names(fields) -> str:
    return ", ".join(field.replace("_", " ") for field in fields)


def _state(state: str, reasons, kind: str, title: str) -> EmailState:
    return EmailState(state, tuple(reasons), {"kind": kind, "title": title})


def missing_documents_action(reasons: set[str]) -> tuple[str, str]:
    if "attachments_absent" in reasons:
        return "resend", "The attachments never arrived: ask the sender to resend them"
    si, bl = "missing_si" in reasons, "missing_bl" in reasons
    if si and bl:
        return "request_both", "Ask the sender for the shipping instructions and the draft BL"
    if si:
        return "request_si", "Ask the sender for the shipping instructions"
    return "request_bl", "Ask the sender for the draft BL"


def derive_state(facts: EmailFacts) -> EmailState:
    if facts.held:
        return _state(
            "held", [_reason("safety_hold")], "review_safety",
            "Inspect the safety signals, then release or delete the email",
        )
    if facts.category == "SPAM" or (facts.category is None and facts.risk_state == "spam"):
        return _state("spam", [], "confirm_spam", "Confirm it is spam and delete it, or mark it not spam")
    if facts.job_active:
        return _state("processing", [], "wait", "Reading the email and its documents")
    if facts.category is None:
        return _state(
            "needs_review", [_reason("unclassified")], "classify",
            "Classify this email with the rules or the AI to decide the next step",
        )
    if facts.category != "BL_COMPARISON":
        kind, title = CATEGORY_ACTIONS[facts.category]
        return _state("classified", [], kind, title)
    return _derive_comparison(facts)


def _derive_comparison(facts: EmailFacts) -> EmailState:
    if facts.attachment_count == 0:
        claims = attachments_expected(facts.subject, facts.body_head)
        if requests_draft(facts.subject, facts.body_head) and not claims:
            return _state(
                "waiting_for_draft", [_reason("awaiting_draft")], "await_draft",
                "Waiting for the carrier's draft BL: chase it, then reopen when it arrives",
            )
        codes = {"missing_si", "missing_bl"} | ({"attachments_absent"} if claims else set())
        reasons = [_reason(c) for c in ("attachments_absent", "missing_si", "missing_bl") if c in codes]
        return _state("needs_documents", reasons, *missing_documents_action(codes))

    if facts.unread:
        if facts.job_state == "succeeded":
            # The job ran and still produced nothing for a file: it could not be opened.
            return _state(
                "needs_review", [_reason("unreadable")], "request_readable", "Ask the sender for a readable copy"
            )
        code = "processing_failed" if facts.job_state == "failed" else "documents_unread"
        return _state("needs_review", [_reason(code)], "process", "Read the attached documents")

    roles = set(facts.roles)
    codes = set()
    if "SI" not in roles:
        codes.add("missing_si")
    if "BL" not in roles:
        codes.add("missing_bl")
    if codes:
        if roles & OTHER_DOCUMENT_ROLES:
            codes.add("wrong_doc_type")
        if "UNKNOWN" in roles:
            codes.add("unrecognised_document")
        if facts.quarantined:
            codes.add("unreadable")
        order = ("missing_si", "missing_bl", "wrong_doc_type", "unrecognised_document", "unreadable")
        return _state(
            "needs_documents", [_reason(c) for c in order if c in codes], *missing_documents_action(codes)
        )
    if facts.quarantined:
        return _state(
            "needs_review", [_reason("unreadable")], "request_readable", "Ask the sender for a readable copy"
        )
    if facts.report_status is None:
        return _state("needs_review", [_reason("not_compared")], "compare", "Compare the documents")
    if facts.report_status == "OK":
        return _state("checked", [], "view_checks", "All seven fields match the shipping instructions")
    if facts.report_status == "MISMATCH":
        fields = facts.mismatch_fields
        return _state(
            "mismatch_found",
            [_reason("mismatch", fields, f"Differences in: {_names(fields)}")],
            "preview_corrections",
            "Preview the correction request",
        )
    fields = facts.unresolved_fields
    label = f"Needs confirmation: {_names(fields)}" if fields else "A required value needs confirmation"
    return _state(
        "needs_review", [_reason("missing_value", fields, label)], "review_evidence",
        "Confirm the uncertain values against the source documents",
    )
