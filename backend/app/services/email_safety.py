"""Static, explainable signals. No links are fetched and no HTML is executed."""

import re
from dataclasses import asdict, dataclass

from app.services.classification import segment_email


@dataclass
class SafetyResult:
    risk_state: str
    severity: str
    held_for_review: bool
    signals: list

    def to_dict(self):
        return asdict(self)


def assess_email(sender, reply_to, subject, body_text, attachment_names, previous_thread=False):
    text = subject + "\n" + segment_email(subject, body_text)[1]["text"]
    signals = []
    credential = re.search(
        r"\b(?:enter|send|share|verify|reset|confirm)\b.{0,45}\b(?:password|credentials|account)\b",
        text,
        re.I,
    )
    urgency = re.search(
        r"\b(?:immediately|suspended|suspension|deactivation|locked|urgent)\b", text, re.I
    )
    link = re.search(r"https?://[^\s<>]+", text, re.I)
    risky = [
        n for n in attachment_names if re.search(r"\.(exe|scr|bat|vbs|js|hta|ps1|msi)$", n, re.I)
    ]
    if credential:
        signals.append(
            {
                "signal_type": "credential_request",
                "description": "Request to provide or verify account credentials",
                "evidence": credential[0],
            }
        )
    if credential and (urgency or link):
        signals.append(
            {
                "signal_type": "credential_pressure",
                "description": "Credential request combined with urgency or a link",
                "evidence": urgency[0] if urgency else link[0],
            }
        )
    if risky:
        signals.append(
            {
                "signal_type": "executable_attachment",
                "description": "Executable attachment requires review",
                "evidence": ", ".join(risky),
            }
        )
    lure = re.search(
        r"\b(?:you have won|claim now|guaranteed.{0,15}(?:profit|return)|exclusive offer|this is a promotional)\b",
        text,
        re.I,
    )
    if lure:
        signals.append(
            {
                "signal_type": "spam_lure",
                "description": "Promotional or prize language",
                "evidence": lure[0],
            }
        )
    held = bool(risky or (credential and (urgency or link)))
    state = (
        "suspected_phishing"
        if held
        else "spam"
        if lure
        else "clear"
        if text.strip()
        else "insufficient_evidence"
    )
    return SafetyResult(state, "high" if held else "low" if lure else "none", held, signals)
