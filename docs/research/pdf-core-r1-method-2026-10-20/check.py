"""Read-only evidence check; never regenerate a seal or invoke inference."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import producer
import bundle


def guard(event, args):
    if event in {"socket.connect", "socket.getaddrinfo"}:
        raise RuntimeError("network forbidden")
    if event == "open" and isinstance(args[0], (str, bytes)):
        name = os.fsdecode(args[0])
        if "holdout" in name or any(c in (args[1] or "") for c in "wax+"):
            raise RuntimeError("read-only non-holdout checker")


def main():
    producer.verify()
    seal = producer.read(HERE / "artifact-seal.json")
    if not seal:
        raise ValueError("empty seal")
    for name, expected in seal.items():
        path = (HERE / name).resolve()
        if not path.is_relative_to(HERE) or producer.sha(path) != expected:
            raise ValueError("changed R1 evidence: " + name)
    for name, expected in producer.read(HERE / "planning/method-hashes.json").items():
        if producer.sha(producer.ROOT / name) != expected:
            raise ValueError("changed planned method: " + name)
    jobs = producer.read(HERE / "planning/jobs.json")
    if (len(jobs["jobs"]) != 43 or jobs["live_ready"] or jobs["new_model_calls"]
            or len({j["job_id"] for j in jobs["jobs"]}) != 43):
        raise ValueError("candidate scope/state changed")
    for job in jobs["jobs"]:
        if job["state"] != "NOT_RUN":
            raise ValueError("unexpected model execution")
        for asset in job["image_assets"]:
            if producer.sha(HERE / "production" / asset["asset"]) != asset["sha256"]:
                raise ValueError("changed job pixels")
    results = {}
    for directory in sorted((HERE / "relocated-bundles").iterdir()):
        revision = producer.read(directory / "binding.json")["source_revision"]
        results[directory.name] = bundle.verify(directory, revision)
    if len(results) != 2:
        raise ValueError("missing actual-source MOCK bundle")
    print(json.dumps({"status": "passed", "sealed_files": len(seal),
        "candidate_jobs": 43, "relocated_MOCK_bundles": results,
        "new_inference_calls": 0, "model_quality": "NOT_VERIFIED"}))


if __name__ == "__main__":
    os.environ.pop("OPENAI_API_KEY", None)
    sys.addaudithook(guard)
    main()
