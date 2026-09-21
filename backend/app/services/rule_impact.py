from dataclasses import dataclass, replace

from app.services.equivalence_rules import EquivalenceRule, RuleEvaluation, match_rule


@dataclass(frozen=True)
class EquivalenceFixture:
    left: str
    right: str
    equivalent: bool


def evaluate_rule(
    rule: EquivalenceRule, fixtures: tuple[EquivalenceFixture, ...]
) -> RuleEvaluation:
    candidate = replace(rule, state="approved")
    positive, false = 0, 0
    # A useful fixture suite must include both a supported alias and a non-alias.
    balanced = any(f.equivalent for f in fixtures) and any(not f.equivalent for f in fixtures)
    for fixture in fixtures:
        matches = (
            match_rule(
                (candidate,),
                workspace_id=rule.workspace_id,
                customer_id=rule.customer_id,
                field=rule.field,
                left=fixture.left,
                right=fixture.right,
            )
            is not None
        )
        positive += int(matches and fixture.equivalent)
        false += int(matches and not fixture.equivalent)
    return RuleEvaluation(
        rule.id, rule.version, rule.content_hash, len(fixtures) if balanced else 0, positive, false
    )
