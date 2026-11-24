"""#81: canonical-mapping's build and validate over the Processing Results #233 registered for
the 20 corpus papers and W2, read from that run's kept object store. No model is called and
nothing is written to that store: each content is built and validated in memory.

    uv run python docs/validation/81/map_corpus.py RUN OUT [INDEX...]

RUN is #233's OUT (requests.json and s3/, outside git); OUT (outside the repo) gets each
content object as OUT/<index>.json. Its own copy of RUN/s3 is served by an S3 stand-in (the
image of tests/s3/compose.yaml) on a free port and removed after. Writes evidence.json here:
per paper the outcome, the sizes, the counts that show the #81 scope §2 rows on real papers,
the content's sha256 and two negative controls, each a change that validate must refuse with
its check (COVERAGE: a body text block dropped; REFERENCE_UNLISTED: a manifest entry dropped).

The Processing Result inlines an enrichment's content up to 16 KB; a larger one is read whole
from its outcome record (result_ref), as finalize hands the mapping the whole content.
"""

import asyncio
import copy
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import warnings
from pathlib import Path

import yaml

from kp_canonicalization.identity import canonical_json
from kp_canonicalization.methods import canonical_mapping as mapping
from kp_canonicalization.ports.object_store import S3ObjectStore
from kp_canonicalization.stages import ProcessingFailure

# docling-core clamps provenance boxes outside the page when it loads a document; known, noisy.
warnings.filterwarnings("ignore", "Provenance bbox", UserWarning)
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def s3_up(data: Path) -> tuple[str, int]:
    image = yaml.safe_load((REPO / "tests/s3/compose.yaml").read_text())["services"]["rustfs"]
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    name = f"kp-s3-81-{port}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:9000",
                    *[a for k, v in image["environment"].items() for a in ("-e", f"{k}={v}")],
                    "-v", f"{data}:/data", image["image"]], check=True, capture_output=True)  # fmt: skip
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2):
                return name, port
        except OSError:
            time.sleep(1)
    raise SystemExit("S3 stand-in not healthy after 60 s")


async def whole(store: S3ObjectStore, result: dict) -> dict:
    """The result with each enrichment's content whole."""
    for e in result["enrichments"]:
        if e["content"] is None:
            record = json.loads(await store.get(e["result_ref"]))
            field = e["item_id"].rpartition("/")[2] if "fields" in record else None
            e["content"] = record["fields"][field]["content"] if field else record["content"]
    return result


async def refused(content, result, document, store, change) -> str | None:
    """The check validate names for the changed content; None when it passes."""
    changed = copy.deepcopy(content)
    change(changed)
    try:
        await mapping.validate(changed, result, document, store)
    except ProcessingFailure as failure:
        return failure.metadata.get("check")
    return None


def drop_text(content: dict) -> None:
    content["blocks"].remove(next(b for b in content["blocks"] if b["kind"] == "text"))


async def paper(store: S3ObjectStore, request_id: str, out: Path, index: str) -> dict:
    result = await whole(store, json.loads(await store.get(f"requests/{request_id}/result.json")))
    document = json.loads(await store.get(result["native"]["assembly_ref"]))["document"]
    started = time.monotonic()
    try:
        content = await mapping.build(result, document, store)
        built = time.monotonic()
        await mapping.validate(content, result, document, store)
    except ProcessingFailure as failure:
        return {"outcome": "failed", "reason": failure.reason, "metadata": failure.metadata}
    validated = time.monotonic()
    body = canonical_json(content)
    (out / f"{index}.json").write_bytes(body)
    blocks = content["blocks"]
    tables = [b for b in blocks if b["ref"].startswith("#/tables/")]
    return {
        "outcome": "valid",
        "pages": len(content["pages"]),
        "content_bytes": len(body),
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "build_s": round(built - started, 2),
        "validate_s": round(validated - built, 2),
        "blocks": len(blocks),
        "kinds": dict(sorted({b["kind"]: sum(1 for x in blocks if x["kind"] == b["kind"])
                              for b in blocks}.items())),  # fmt: skip
        "role_uncertain": sum(1 for b in blocks if b.get("role_uncertain")),
        "tables_html": sum(1 for b in tables if b["markdown"].startswith("<table")),
        "tables_markdown": sum(1 for b in tables if not b["markdown"].startswith("<table")),
        "picture_native_text": sum(len(b.get("native_text", [])) for b in blocks),
        "enrichments": len(content["enrichments"]),
        "disputed": sum(1 for e in content["enrichments"] if e["status"] == "disputed"),
        "artifacts": {kind: sum(1 for a in content["artifacts"] if a["kind"] == kind)
                      for kind in ("page_image", "picture_image", "evidence")},  # fmt: skip
        "omitted": len(content["omitted"]),
        "limitations": [(x["code"], x["scope"]) for x in content["limitations"]],
        "negative_controls": {
            "COVERAGE": await refused(content, result, document, store, drop_text),
            "REFERENCE_UNLISTED": await refused(
                content, result, document, store, lambda c: c["artifacts"].pop()
            ),
        },
    }


async def main(argv: list[str]) -> int:
    run, out = Path(argv[0]).expanduser(), Path(argv[1]).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    state = json.loads((run / "requests.json").read_text())
    indices = argv[2:] or list(state["papers"])
    clone = Path(tempfile.mkdtemp(prefix="kp-s3-81-"))
    shutil.copytree(run / "s3", clone / "s3")
    name, port = s3_up(clone / "s3")
    try:
        os.environ |= {"KP_S3_ENDPOINT": f"http://127.0.0.1:{port}", "KP_S3_BUCKET": state["bucket"],
                       "AWS_ACCESS_KEY_ID": "kpdev", "AWS_SECRET_ACCESS_KEY": "kpdev-secret"}  # fmt: skip
        store = S3ObjectStore.from_env()
        rows = {}
        for index in indices:
            row = await paper(store, state["papers"][index]["request_id"], out, index)
            rows[index] = {"sha256": state["papers"][index]["sha256"]} | row
            print(index, json.dumps({k: row.get(k) for k in ("outcome", "pages", "blocks",
                                     "build_s", "validate_s", "negative_controls")}), flush=True)  # fmt: skip
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True)
        shutil.rmtree(clone)
    if not argv[2:]:
        (HERE / "evidence.json").write_text(json.dumps(rows, indent=1) + "\n")
    valid = all(r["outcome"] == "valid" for r in rows.values())
    controls = all(r["negative_controls"] == {"COVERAGE": "COVERAGE",
                                              "REFERENCE_UNLISTED": "REFERENCE_UNLISTED"}
                   for r in rows.values() if r["outcome"] == "valid")  # fmt: skip
    print("all valid:", valid, "controls refused:", controls, flush=True)
    return 0 if valid and controls else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
