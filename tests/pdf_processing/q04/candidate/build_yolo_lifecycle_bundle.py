"""Create an immutable candidate bundle without modifying frozen Q04 inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


BASELINE_INPUTS_SHA256 = "9e46ad75379dffed05c5e25ec36b22fdf0d680e30e7d2b298d5ac355d0e039f2"
CANDIDATE_VERSION = "q04-yolo-lifecycle-v1"
EXPECTED_CHANGED_PRODUCER_FILES = {
    "compatibility.py",
    "execution.py",
    "parse.py",
    "supervision.py",
}
REQUIRED_CANDIDATE_HARNESS_FILES = {
    "tests/pdf_processing/q04/candidate/yolo_lifecycle.py",
    "tests/pdf_processing/q04/candidate/yolo_candidate_measure.py",
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def tree_digest(root, *, exclude=()):
    excluded = set(exclude)
    entries = {
        str(path.relative_to(root)): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and str(path.relative_to(root)) not in excluded
    }
    return hashlib.sha256(canonical(entries).encode()).hexdigest()


def build(source, destination, producer_root):
    source_inputs = source / "inputs.json"
    if sha256(source_inputs) != BASELINE_INPUTS_SHA256:
        raise ValueError("frozen baseline inputs changed")
    if destination.exists():
        raise ValueError("candidate destination must be absent")
    baseline = json.loads(source_inputs.read_text())
    repository = producer_root.resolve().parents[1]
    producer = {
        path.name: sha256(path)
        for path in sorted(producer_root.glob("*.py"))
    }
    changed = sorted(
        name
        for name in set(baseline["producer"]) | set(producer)
        if baseline["producer"].get(name) != producer.get(name)
    )
    if set(changed) != EXPECTED_CHANGED_PRODUCER_FILES:
        raise ValueError(f"unexpected producer impact: {changed}")

    shutil.copytree(source, destination, copy_function=shutil.copy2)
    candidate = json.loads((destination / "inputs.json").read_text())
    candidate["producer"] = producer
    harness_names = sorted(
        set(baseline["test_files"]) | REQUIRED_CANDIDATE_HARNESS_FILES
    )
    candidate["test_files"] = {
        name: sha256(repository / name)
        for name in harness_names
    }
    (destination / "inputs.json").write_text(json.dumps(candidate, indent=2) + "\n")
    source_payload = tree_digest(source, exclude={"inputs.json"})
    candidate_payload = tree_digest(destination, exclude={"inputs.json"})
    if source_payload != candidate_payload:
        raise ValueError("fixture/oracle payload changed")

    for path in sorted(destination.rglob("*"), reverse=True):
        path.chmod(0o555 if path.is_dir() else 0o444)
    destination.chmod(0o555)
    return {
        "schema_version": 1,
        "candidate_version": CANDIDATE_VERSION,
        "source_bundle": str(source.resolve()),
        "candidate_bundle": str(destination.resolve()),
        "baseline_inputs_sha256": BASELINE_INPUTS_SHA256,
        "candidate_inputs_sha256": sha256(destination / "inputs.json"),
        "payload_tree_sha256": candidate_payload,
        "producer_manifest_sha256": hashlib.sha256(canonical(producer).encode()).hexdigest(),
        "producer": producer,
        "changed_producer_files": changed,
        "test_files": candidate["test_files"],
        "changed_test_files": sorted(
            name
            for name in set(baseline["test_files"]) | set(candidate["test_files"])
            if baseline["test_files"].get(name) != candidate["test_files"].get(name)
        ),
        "fixture_oracle_payload_unchanged": True,
        "profile_release": "derive a new q04-* release from this producer and the newly captured immutable source versions during candidate init",
        "runtime_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--producer-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build(args.source, args.destination, args.producer_root)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
