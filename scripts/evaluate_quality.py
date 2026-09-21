"""Generate frozen rule predictions, then load expectations only for scoring.

This tiny synthetic development set is not a real-world accuracy benchmark.
Run from repository root: backend/.venv/Scripts/python scripts/evaluate_quality.py
"""
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))

from app.ai.grounding import ground_extraction
from app.config import Settings
from app.parsers.registry import parse_document
from app.services.classification import classify_explicit
from app.services.extraction import extract_labelled
from app.services.quality import score_predictions
from app.services.verification import verify


def main():
    dataset=ROOT/"benchmark/quality-v1"
    inputs=json.loads((dataset/"inputs.json").read_text(encoding="utf-8"))
    predictions=[]
    for item in inputs["items"]:
        started=time.perf_counter()
        category=classify_explicit(item["subject"],item["body"])
        row={"id":item["id"],"category":category.category if category else None,"method":"rules","fields":{},"comparisons":{}}
        if category and category.category=="BL_COMPARISON" and "si" in item and "bl" in item:
            docs=[];quality={}
            for role in ("SI","BL"):
                doc=parse_document(item[role.lower()].encode(),source_id=item["id"]+role,settings=Settings())
                extraction=extract_labelled(doc);docs.append(extraction)
                quality.update(ground_extraction(extraction,doc))
                row["fields"].update({f"{role}.{name}":field.raw_value for name,field in extraction.fields.items()})
            report=verify(*docs,email_id=item["id"],evidence_quality=quality)
            row["comparisons"]={str(c.field):c.decision for c in report.comparisons}
        row["latency_ms"]=round((time.perf_counter()-started)*1000,2)
        predictions.append(row)
    output=ROOT/"artifacts/quality";output.mkdir(parents=True,exist_ok=True)
    (output/"predictions-v1.json").write_text(json.dumps(predictions,indent=2),encoding="utf-8")
    expected=json.loads((dataset/"expectations.json").read_text(encoding="utf-8"))
    report={"version":inputs["version"],"method":"rules","scope":"Synthetic development checks, not held-out real-world accuracy",**score_predictions(expected["items"],predictions)}
    (output/"report-v1.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
