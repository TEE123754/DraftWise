import pytest
from pydantic import ValidationError

from app.api.dashboard import DashboardView
from app.services.email_state import ATTENTION_ORDER, STATES


def test_every_dashboard_panel_can_be_saved_in_any_order():
    view = DashboardView(sections=["states", "attention", "quality", "metrics", "guidance"])
    assert view.sections == ["states", "attention", "quality", "metrics", "guidance"]
    assert DashboardView().sections == ["attention", "states", "metrics", "guidance", "quality"]


@pytest.mark.parametrize("sections", [["metrics", "metrics"], ["nonsense"], ["metrics"] * 6])
def test_bad_panel_lists_are_rejected(sections):
    with pytest.raises(ValidationError):
        DashboardView(sections=sections)


def test_attention_states_are_real_states_and_exclude_waiting_and_finished_mail():
    assert set(ATTENTION_ORDER) <= set(STATES)
    assert not {"waiting_for_draft", "checked", "classified", "spam", "processing"} & set(ATTENTION_ORDER)
