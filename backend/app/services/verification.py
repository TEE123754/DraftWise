from uuid import UUID

from rapidfuzz.fuzz import ratio, token_sort_ratio

from app.domain.models import (
    FIELDS,
    PARTIES,
    Comparison,
    Extraction,
    FieldName,
    Value,
    VerificationReport,
)
from app.services.equivalence_rules import EquivalenceRule, match_rule
from app.services.evidence_dependencies import resolve_field
from app.services.normalization import normalize


def verify(
    si: Extraction | None,
    bl: Extraction | None,
    *,
    email_id: str = "local",
    revision: int = 1,
    evidence_quality: dict[str, float] | None = None,
    pairing_quality: float = 1.0,
    equivalence_rules: tuple[EquivalenceRule, ...] = (),
    workspace_id: UUID | None = None,
    customer_id: UUID | None = None,
) -> VerificationReport:
    rows = []
    for field in FIELDS:
        values, evidence, qualities, reasons, normalized_rules = [], [], [], [], []
        for document, role in ((si, "SI"), (bl, "BL")):
            if document is None:
                values.append(Value(raw=None, normalized=None, extraction_id=None))
                reasons.append("missing")
                qualities.append(0.0)
                continue
            source, dependencies = resolve_field(document, field)
            evidence.extend([e.block_id for e in source.evidence] + list(dependencies))
            other = bl if role == "SI" else si
            counterpart = (
                " ".join([str(other.fields[field].raw_value or ""), *(e.quote for e in other.fields[field].evidence)])
                if other is not None
                else ""
            )
            normalized = (
                normalize(
                    field, source.raw_value, " ".join(e.quote for e in source.evidence), counterpart
                )
                if source.state == "present" and source.raw_value
                else None
            )
            normalized_rules.append(normalized.rule if normalized else None)
            values.append(
                Value(
                    raw=document.fields[field].raw_value,
                    normalized=normalized.value if normalized else None,
                    extraction_id=document.document_id,
                )
            )
            # With a quality map, blocks absent from it are plain text and trusted; only OCR/hidden
            # blocks reduce quality. With no map at all nothing is vouched for, so fail closed.
            default_quality = 1.0 if evidence_quality is not None else 0.0
            quality = (
                min((evidence_quality or {}).get(e.block_id, default_quality) for e in source.evidence)
                if source.evidence
                else 0.0
            )
            quality = (
                min(quality, *((evidence_quality or {}).get(e, default_quality) for e in dependencies))
                if dependencies
                else quality
            )
            qualities.append(quality)
            if document.document_type != role:
                reasons.append("role_uncertain")
            elif source.state == "missing":
                reasons.append("missing")
            elif source.state != "present" or not normalized or normalized.value is None:
                reasons.append("uncertain")
            elif quality < (0.85 if field in PARTIES else 0.90):
                reasons.append("evidence_quality")
        left, right = values
        confidence = min(*qualities, pairing_quality)
        rule = "evidence_gate_v1"
        both_present = left.normalized is not None and right.normalized is not None
        needs_review = bool(reasons) or pairing_quality < 0.90
        matched_rule = None
        if equivalence_rules and left.raw and right.raw:
            matched_rule = match_rule(
                equivalence_rules,
                workspace_id=workspace_id,
                customer_id=customer_id,
                field=field,
                left=str(left.raw),
                right=str(right.raw),
            )
            if not matched_rule and left.normalized and right.normalized:
                matched_rule = match_rule(
                    equivalence_rules,
                    workspace_id=workspace_id,
                    customer_id=customer_id,
                    field=field,
                    left=str(left.normalized),
                    right=str(right.normalized),
                )

        if matched_rule is not None:
            if needs_review:
                decision = "missing" if "missing" in reasons else "uncertain"
                explanation = "Source evidence requires review before equivalence rule can be applied."
            else:
                decision = "match"
                rule = "equivalence_rule_v1"
                explanation = f"Matched approved equivalence rule: {matched_rule.rationale}"
                evidence.append(str(matched_rule.id))
                evidence.extend(matched_rule.evidence_ids)
        elif both_present and left.normalized == right.normalized:
            # A clear difference is reported even on weak evidence, but agreement is only trusted
            # (OK) when the evidence behind it is reliable.
            if needs_review:
                decision = "missing" if "missing" in reasons else "uncertain"
                explanation = "Source evidence requires review before this field can be compared."
            else:
                decision = "match"
                rule = next((r for r in normalized_rules if r), rule)
                explanation = "Both source values match after deterministic normalization."
        elif both_present and field in PARTIES:
            score = max(
                ratio(str(left.normalized), str(right.normalized)),
                token_sort_ratio(str(left.normalized), str(right.normalized)),
            )
            if score >= 85:
                decision, rule = "partial_match", "unapproved_identity_candidate_v1"
                confidence = min(confidence, 0.79)
                explanation = "Names are similar; source evidence or an approved scoped equivalence is required."
            else:
                decision, rule = "mismatch", "distinct_identity_v1"
                explanation = f"{field.value.replace('_', ' ').title()} differs between SI and BL."
        elif both_present:
            decision, rule = "mismatch", "canonical_difference_v1"
            explanation = f"{field.value.replace('_', ' ').title()} differs: SI {left.normalized}; BL {right.normalized}."
        elif needs_review:
            decision = "missing" if "missing" in reasons else "uncertain"
            explanation = "Source evidence requires review before this field can be compared."
        else:
            decision = "missing"
            explanation = "At least one side has no extractable value for this field."
        rows.append(
            Comparison(
                field=field,
                si=left,
                bl=right,
                decision=decision,
                severity="none"
                if decision == "match"
                else ("medium" if field == FieldName.NOTIFY else "high"),
                confidence=confidence,
                rule=rule,
                explanation=explanation,
                evidence_ids=tuple(dict.fromkeys(evidence)),
            )
        )
    unresolved = [row.field.value for row in rows if row.decision not in {"match", "mismatch"}]
    has_mismatch = any(row.decision == "mismatch" for row in rows)
    return VerificationReport(
        email_id=email_id,
        revision=revision,
        status="MISMATCH" if has_mismatch else ("NEEDS_REVIEW" if unresolved else "OK"),
        complete=not unresolved,
        review_reasons=tuple(unresolved),
        confidence=min(row.confidence for row in rows),
        comparisons=tuple(rows),
    )
