import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from typing import Literal
from uuid import UUID

from app.domain.errors import DomainError
from app.domain.models import PARTIES, PORTS, FieldName
from app.services.normalization import text_key


@dataclass(frozen=True)
class EquivalenceRule:
    id: UUID
    workspace_id: UUID
    customer_id: UUID
    field: FieldName
    left: str
    right: str
    evidence_ids: tuple[str, ...]
    rationale: str
    version: int = 1
    state: Literal["proposed", "approved", "revoked"] = "proposed"
    canonical_port_code: str | None = None
    authority_reference: str | None = None

    def __post_init__(self):
        if self.field not in PARTIES | PORTS:
            raise DomainError(
                "RULE_FIELD_UNSUPPORTED", "Numeric or missing-value equivalence rules are forbidden"
            )
        if (
            not self.left.strip()
            or not self.right.strip()
            or not self.evidence_ids
            or not self.rationale.strip()
        ):
            raise DomainError(
                "RULE_EVIDENCE_REQUIRED",
                "A rule requires both identities, source evidence and a rationale",
            )
        if self.left.strip().casefold() in {
            "n/a",
            "unknown",
            "-",
        } or self.right.strip().casefold() in {"n/a", "unknown", "-"}:
            raise DomainError("RULE_VALUE_INVALID", "Placeholders cannot be made equivalent")
        if set(re.findall(r"\d+", self.left)) != set(re.findall(r"\d+", self.right)):
            raise DomainError(
                "RULE_IDENTITY_CONFLICT",
                "An equivalence cannot erase conflicting numeric identity tokens",
            )
        if self.field in PORTS and (
            not self.canonical_port_code
            or not re.fullmatch(r"[A-Z]{2}[A-Z2-9]{3}", self.canonical_port_code)
            or not self.authority_reference
        ):
            raise DomainError(
                "RULE_PORT_AUTHORITY_REQUIRED",
                "Port equivalence requires an authoritative common port identity",
            )

    @property
    def content_hash(self) -> str:
        content = asdict(self)
        content.pop("state")
        return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class RuleEvaluation:
    rule_id: UUID
    rule_version: int
    content_hash: str
    fixture_count: int
    positive_matches: int
    false_matches: int


def approve_rule(rule: EquivalenceRule, evaluation: RuleEvaluation) -> EquivalenceRule:
    if (
        rule.state != "proposed"
        or evaluation.rule_id != rule.id
        or evaluation.rule_version != rule.version
        or evaluation.content_hash != rule.content_hash
    ):
        raise DomainError(
            "STALE_RULE_EVALUATION",
            "Evaluate the current proposed rule before approval",
            status=409,
        )
    if (
        evaluation.fixture_count < 2
        or evaluation.positive_matches < 1
        or evaluation.false_matches != 0
    ):
        raise DomainError(
            "RULE_VALIDATION_FAILED",
            "Approval requires positive and negative validation with no false matches",
        )
    return replace(rule, state="approved")


def revoke_rule(rule: EquivalenceRule, rationale: str) -> EquivalenceRule:
    if not rationale.strip():
        raise DomainError("RULE_RATIONALE_REQUIRED", "Revocation requires a reason")
    return replace(rule, state="revoked", version=rule.version + 1, rationale=rationale)


def match_rule(
    rules: tuple[EquivalenceRule, ...],
    *,
    workspace_id: UUID | None,
    customer_id: UUID | None,
    field: FieldName,
    left: str,
    right: str,
) -> EquivalenceRule | None:
    if workspace_id is None or customer_id is None:
        return None
    pair = frozenset((text_key(left), text_key(right)))
    for rule in rules:
        if (
            rule.state == "approved"
            and rule.workspace_id == workspace_id
            and rule.customer_id == customer_id
            and rule.field == field
        ):
            if pair == frozenset((text_key(rule.left), text_key(rule.right))):
                return rule
    return None
