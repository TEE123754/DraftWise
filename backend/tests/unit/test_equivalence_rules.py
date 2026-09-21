from dataclasses import replace
from uuid import uuid4

import pytest

from app.domain.errors import DomainError
from app.domain.models import FieldName
from app.services.equivalence_rules import EquivalenceRule, approve_rule, match_rule, revoke_rule
from app.services.rule_impact import EquivalenceFixture, evaluate_rule


def proposed():
    return EquivalenceRule(
        uuid4(),
        uuid4(),
        uuid4(),
        FieldName.SHIPPER,
        "Example Export Limited",
        "Example Export Ltd",
        ("source:1",),
        "Both spellings confirmed by customer",
    )


def approved():
    rule = proposed()
    evaluation = evaluate_rule(
        rule,
        (
            EquivalenceFixture(rule.left, rule.right, True),
            EquivalenceFixture(rule.left, "Unrelated Company", False),
        ),
    )
    return approve_rule(rule, evaluation)


def test_alias_cannot_cross_workspace_or_customer():
    rule = approved()
    context = dict(
        workspace_id=rule.workspace_id,
        customer_id=rule.customer_id,
        field=rule.field,
        left=rule.left,
        right=rule.right,
    )
    assert match_rule((rule,), **context) == rule
    assert match_rule((rule,), **(context | {"workspace_id": uuid4()})) is None
    assert match_rule((rule,), **(context | {"customer_id": uuid4()})) is None
    assert match_rule((rule,), **(context | {"customer_id": None})) is None
    assert match_rule((revoke_rule(rule, "Customer withdrew approval"),), **context) is None


def test_empty_or_only_positive_validation_cannot_approve():
    rule = proposed()
    for fixtures in ((), (EquivalenceFixture(rule.left, rule.right, True),)):
        with pytest.raises(DomainError):
            approve_rule(rule, evaluate_rule(rule, fixtures))


def test_changed_rule_cannot_reuse_evaluation():
    rule = proposed()
    evaluation = evaluate_rule(
        rule,
        (
            EquivalenceFixture(rule.left, rule.right, True),
            EquivalenceFixture(rule.left, "Other", False),
        ),
    )
    with pytest.raises(DomainError):
        approve_rule(replace(rule, right="Different Alias"), evaluation)


def test_numeric_and_unauthoritative_port_rules_are_rejected():
    rule = proposed()
    with pytest.raises(DomainError):
        replace(rule, field=FieldName.WEIGHT)
    with pytest.raises(DomainError):
        replace(rule, field=FieldName.POL)
    with pytest.raises(DomainError):
        replace(rule, left="Company 123", right="Company 456")
