from app.services.classification import classify_explicit
from app.services.disambiguation import email_senses
from app.services.email_safety import assess_email
from app.services.quality import assess_windows, distribution, score_predictions


def test_current_action_wins_over_stale_action_subject():
    result=classify_explicit("Request BL draft","Please cancel this invoice.\nOn Monday Sam wrote:\nCheck draft BL.")
    assert result.category=="INVOICE_QUERY"
    assert result.evidence_span_ids==("current",)


def test_word_senses_require_shipping_context():
    assert all(s["sense"] for s in email_senses("","Please compare the SI and draft BL for shipment A."))
    assert email_senses("","Please send POD.")[0]["state"]=="needs_review"


def test_no_phishing_from_billing_language_alone():
    assert not assess_email("billing@example.test",None,"Invoice","Please explain these bank transfer charges.",[]).held_for_review
    assert assess_email("x@example.test",None,"Account","Verify your account immediately at https://example.test",[]).held_for_review


def test_drift_requires_baseline_and_two_independent_windows():
    base=distribution(["GENERAL"]*20)
    assert assess_windows(None,[],[])["state"]=="baseline_required"
    assert assess_windows(base,["SPAM"]*19,["SPAM"]*20)["state"]=="insufficient_data"
    assert assess_windows(base,["GENERAL"]*20,["SPAM"]*20)["state"]=="stable"
    result=assess_windows(base,["SPAM"]*20,["SPAM"]*20)
    assert result["state"]=="suspected_shift"
    assert result["concept_drift_confirmed"] is False


def test_evaluation_counts_abstention_and_missing_fields_as_errors():
    expected=[{"id":"1","category":"GENERAL","fields":{"gross_weight_kg":"12"}},{"id":"2","category":"SPAM"}]
    report=score_predictions(expected,[{"id":"1","category":"GENERAL","latency_ms":10}])
    assert report["coverage"]==0.5
    assert report["abstention_rate"]==0.5
    assert report["extraction_accuracy"]==0
    assert report["comparison_accuracy"] is None
    assert report["confusion_matrix"]["SPAM"]["ABSTAIN"]==1
