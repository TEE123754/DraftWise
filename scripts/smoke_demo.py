"""Exercise the local demo against real API/worker services, without provider calls."""

import time
from uuid import uuid4

import httpx


def main():
    with httpx.Client(
        base_url="http://localhost:8000/api/v1",
        headers={"Origin": "http://localhost:3000"},
        timeout=90,
    ) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        session = request("POST", "/demo/session")
        client.headers.update(
            {"X-Demo-Mode": "true", "X-Workspace-Id": session["workspace_id"]}
        )
        try:
            records = []
            offset = 0
            while True:
                page = request("GET", f"/emails?limit=100&offset={offset}")
                records.extend(page["items"])
                if page["next_cursor"] is None:
                    break
                offset = int(page["next_cursor"])
            assert len(records) == 520
            email = next(item for item in records if item["external_id"] == "email_001")
            case = request(
                "POST", "/cases", json={"email_id": email["id"], "reference": "email_001"},
                headers={"Idempotency-Key": str(uuid4())},
            )
            deadline = time.monotonic() + 90
            while True:
                detail = request("GET", f"/cases/{case['id']}")
                sources = detail["available_sources"]
                roles = {source["document_type"]: source["id"] for source in sources}
                if "SI" in roles and "BL" in roles:
                    break
                assert time.monotonic() < deadline, "Featured document extraction did not finish"
                time.sleep(2)
            request(
                "POST", f"/cases/{case['id']}/sources",
                json={"expected_version": detail["case"]["version"],
                      "si_extraction_id": roles["SI"], "bl_extraction_id": roles["BL"],
                      "reason": "Local demo smoke: select content-supported document roles"},
                headers={"Idempotency-Key": str(uuid4())},
            )
            while True:
                detail = request("GET", f"/cases/{case['id']}")
                if detail["case"]["latest_report_id"]:
                    break
                assert time.monotonic() < deadline, "Verification did not finish"
                time.sleep(2)
            print(f"PASS: {len(records)} emails browsable; real SI/BL extraction and report persisted.")
        finally:
            request("DELETE", "/demo/session")


if __name__ == "__main__":
    main()
