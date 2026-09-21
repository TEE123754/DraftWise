import pytest

from app.api.document_actions import document_actions
from app.services.references import references


@pytest.mark.parametrize("si,bl,missing",[(True,False,["draft bill of lading"]),(False,True,["shipping instructions"]),(False,False,["shipping instructions","draft bill of lading"])])
def test_missing_document_reply(si,bl,missing):
    result=document_actions({"documents":{"si":si,"bl":bl},"reasons":[],"action":{"kind":"request_both","title":"Request missing documents"},"subject":"Shipment ABC"})
    assert result["missing"]==missing
    assert all(name in result["draft_reply"] for name in missing)
    assert result["method"]=="local_template"

def test_references_do_not_use_voyage_or_generic_numbers():
    assert references("Vessel EVERGREEN voyage 1234W; 25000 KG; 3 x 40HC") == []
    assert references("B/L No.: ABC-123456")[0]["code"]=="ABC123456"
    assert references("Booking ref: BK99999")[0]["kind"]=="booking"
    assert references("OC 5RSG-00133")[0]["code"]=="5RSG00133"
