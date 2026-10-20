"""Read public source PDFs and compare bytes; no inference requests or credentials."""
import hashlib
import json
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
registry = json.loads((REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json").read_text())
records = []
with httpx.Client(timeout=40, follow_redirects=True, trust_env=False) as client:
    for source_id in ["SRC07", "SRC11"]:
        source = next(s for s in registry["sources"] if s["id"] == source_id)
        response = client.get(source["source_url"])
        digest = hashlib.sha256(response.content).hexdigest()
        record = {"source_id": source_id, "url": source["source_url"], "final_url": str(response.url),
                  "http_status": response.status_code, "content_type": response.headers.get("content-type"),
                  "bytes": len(response.content), "download_sha256": digest,
                  "frozen_sha256": source["sha256"], "byte_equal_frozen_source": digest == source["sha256"]}
        records.append(record)
        print(json.dumps(record), flush=True)
(HERE / "public-arxiv.json").write_text(json.dumps(records, indent=2) + "\n")
assert all(r["http_status"] == 200 and r["byte_equal_frozen_source"] for r in records)
