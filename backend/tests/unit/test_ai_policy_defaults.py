"""AI runs only when the person asks: request bodies that omit prefer_ai must mean rules only."""

from app.api.demo import SampleFetch
from app.api.emails import ProcessEmail


def test_sample_fetch_defaults_to_rules_only():
    assert SampleFetch().prefer_ai is False
    assert SampleFetch(email_id="email_002").prefer_ai is False


def test_process_defaults_to_rules_only():
    assert ProcessEmail().prefer_ai is False
    assert ProcessEmail(prefer_ai=True).prefer_ai is True
