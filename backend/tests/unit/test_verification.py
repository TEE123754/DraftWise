import pytest

from app.domain.models import FieldName
from app.services.normalization import containers, weight
from app.services.verification import verify


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("22,000 KG", "22000"),
        ("22 MT", "22000"),
        ("22.000,50 kg", "22000.5"),
        ("100 lb", "45.359237"),
        ("22.000 kg", None),
        ("22", None),
        ("-3 kg", None),
        ("0 kg", None),
        ("1,23,000 kg", None),
    ],
)
def test_weight_units_and_ambiguity(raw, expected):
    assert weight(raw).value == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("3 x 40'HC", 3),
        ("2x20GP + 1x40HC", 3),
        ("3", 3),
        ("40HC", None),
        ("100 packages", None),
        ("6 TEU", None),
        ("0", None),
    ],
)
def test_explicit_container_quantities(raw, expected):
    assert containers(raw).value == expected


def test_equal_units_match(document_factory):
    si, q1 = document_factory()
    bl, q2 = document_factory("BL", gross_weight_kg="22 MT")
    assert verify(si, bl, evidence_quality=q1 | q2).status == "OK"


def test_two_missing_values_do_not_match(document_factory):
    si, q1 = document_factory(gross_weight_kg=None)
    bl, q2 = document_factory("BL", gross_weight_kg=None, container_count="4")
    report = verify(si, bl, evidence_quality=q1 | q2)
    # A clear mismatch is not hidden by an unrelated unresolved field.
    assert report.status == "MISMATCH"
    assert not report.complete
    rows = {row.field: row for row in report.comparisons}
    assert rows[FieldName.CONTAINERS].decision == "mismatch"
    assert rows[FieldName.WEIGHT].decision == "missing"


def test_evidence_quality_cannot_be_omitted(document_factory):
    si, _ = document_factory()
    bl, _ = document_factory("BL")
    assert verify(si, bl).status == "NEEDS_REVIEW"


def test_same_as_consignee_uses_bl_only(document_factory):
    si, q1 = document_factory(notify_party="SAME AS CONSIGNEE")
    bl, q2 = document_factory(
        "BL", consignee="Different Buyer GmbH", notify_party="SAME AS CONSIGNEE"
    )
    report = verify(si, bl, evidence_quality=q1 | q2)
    assert (
        next(row for row in report.comparisons if row.field == FieldName.NOTIFY).decision
        == "mismatch"
    )


def test_similar_party_requires_review(document_factory):
    si, q1 = document_factory()
    bl, q2 = document_factory("BL", shipper="Example Export Ltd Indonesia")
    report = verify(si, bl, evidence_quality=q1 | q2)
    assert (
        next(row for row in report.comparisons if row.field == FieldName.SHIPPER).decision
        != "match"
    )


def test_port_locode_aliases_match(document_factory):
    si, q1 = document_factory(port_of_discharge="CALLAO, PERU")
    bl, q2 = document_factory("BL", port_of_discharge="PECLL")
    report = verify(si, bl, evidence_quality=q1 | q2)
    pod_row = next(row for row in report.comparisons if row.field == FieldName.POD)
    assert pod_row.decision == "match"
    assert pod_row.si.normalized == "PECLL"
    assert pod_row.bl.normalized == "PECLL"


def test_party_multiline_and_suffix_match(document_factory):
    si, q1 = document_factory(consignee="AL GURG STATIONERY LLC\nP.O. BOX 5069\nDUBAI, UAE")
    bl, q2 = document_factory("BL", consignee="AL GURG STATIONERY LLC")
    report = verify(si, bl, evidence_quality=q1 | q2)
    consignee_row = next(row for row in report.comparisons if row.field == FieldName.CONSIGNEE)
    assert consignee_row.decision == "match"


def test_approved_equivalence_rule_matches_in_verify(document_factory):
    from uuid import uuid4

    from app.services.equivalence_rules import EquivalenceRule
    ws_id = uuid4()
    cust_id = uuid4()
    rule_id = uuid4()
    rule = EquivalenceRule(
        id=rule_id,
        workspace_id=ws_id,
        customer_id=cust_id,
        field=FieldName.SHIPPER,
        left="Example Export Ltd",
        right="Example Export Global Trading",
        evidence_ids=("doc:1",),
        rationale="Customer confirmed trading entity rename",
        version=1,
        state="approved",
    )
    si, q1 = document_factory(shipper="Example Export Ltd")
    bl, q2 = document_factory("BL", shipper="Example Export Global Trading")
    report = verify(
        si,
        bl,
        evidence_quality=q1 | q2,
        equivalence_rules=(rule,),
        workspace_id=ws_id,
        customer_id=cust_id,
    )
    shipper_row = next(row for row in report.comparisons if row.field == FieldName.SHIPPER)
    assert shipper_row.decision == "match"
    assert shipper_row.rule == "equivalence_rule_v1"
    assert str(rule_id) in shipper_row.evidence_ids
    assert "doc:1" in shipper_row.evidence_ids




@pytest.mark.parametrize(
    ("raw", "context", "counterpart", "expected", "rule"),
    [
        # The field's own label states the unit.
        ("341715", "Gross Weight (KGS) 341715", "", "341715", "decimal_unit_exact_v1"),
        ("24.5", "Gross Weight (MT) 24.5", "", "24500", "decimal_unit_exact_v1"),
        # The other document states it.
        ("24.5", "GROSS WEIGHT 24.5", "24.5 MT", "24500", "decimal_unit_exact_v1"),
        # Neither states it: kilograms, the field's defined unit, but only where plausibly kg.
        ("341715", "GROSS WEIGHT 341715", "", "341715", "decimal_unit_assumed_kg_v1"),
        ("22", "GROSS WEIGHT 22", "", None, "weight_unresolved_v1"),
        # Conflicting unit words give no unit to inherit.
        ("22", "Gross Weight (KG) (MT)", "", None, "weight_unresolved_v1"),
    ],
)
def test_bare_weight_takes_unit_from_label_then_counterpart_then_kilograms(
    raw, context, counterpart, expected, rule
):
    result = weight(raw, context, counterpart)
    assert (result.value, result.rule) == (expected, rule)


def test_bare_weights_in_both_documents_compare_as_kilograms(document_factory):
    si, q1 = document_factory(gross_weight_kg="63954")
    bl, q2 = document_factory("BL", gross_weight_kg="63954")
    assert verify(si, bl, evidence_quality=q1 | q2).status == "OK"
    bl, q2 = document_factory("BL", gross_weight_kg="64954")
    report = verify(si, bl, evidence_quality=q1 | q2)
    assert report.status == "MISMATCH"
    assert [row.field.value for row in report.comparisons if row.decision == "mismatch"] == [
        "gross_weight_kg"
    ]


def test_fcl_container_counts_are_explicit_quantities():
    assert containers("12 x 20'FCL").value == 12


def test_party_name_ignores_how_the_address_is_attached():
    from app.services.normalization import party

    joined = party("APRIL FINE PAPER TRADING | ON BEHALF OF VITAL SOLUTIONS PTE LTD | 77 ROBINSON ROAD")
    stacked = party("APRIL FINE PAPER TRADING\nON BEHALF OF VITAL SOLUTIONS PTE LTD\n77 ROBINSON ROAD")
    assert joined.value == stacked.value == "april fine paper trading"
    assert party("KTP CO., LTD").value != party("VITAL SOLUTIONS PTE. LTD.").value


@pytest.mark.parametrize(
    ("si", "bl", "same"),
    [
        ("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)", "PORT KLANG (WESTPORT), MALAYSIA (MYPKG)", True),
        ("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)", "Port Klang", True),
        # The name changed but the trailing code was left behind: a real difference.
        ("PORT KLANG (WESTPORT), MALAYSIA (MYPKG)", "SINGAPORE, SINGAPORE (MYPKG)", False),
        ("SINGAPORE (SGSIN)", "PORT KLANG (WESTPORT), MALAYSIA (SGSIN)", False),
        # An unknown name still resolves through its code.
        ("SOMEWHERE NEW (SGSIN)", "SINGAPORE", True),
    ],
)
def test_port_name_governs_over_a_stale_trailing_code(si, bl, same):
    from app.services.normalization import port_locode

    assert (port_locode(si).value == port_locode(bl).value) is same


@pytest.mark.parametrize(
    ("si", "bl", "same"),
    [
        ("Colombo, Sri Lanka", "COLOMBO", True),
        ("COLOMBO (LKCMB)", "Colombo, Sri Lanka", True),
        ("Los Angeles, USA", "LOS ANGELES (USLAX)", True),
        ("Colombo, Sri Lanka", "Chittagong, Bangladesh", False),
        ("Santos, Brazil", "Salvador, Brazil", False),
    ],
)
def test_ports_outside_the_alias_table_compare_by_name_not_by_suffix(si, bl, same):
    from app.services.normalization import port_locode

    assert (port_locode(si).value == port_locode(bl).value) is same
