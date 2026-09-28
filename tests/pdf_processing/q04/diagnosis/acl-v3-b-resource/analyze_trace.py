"""Verify and replay the immutable ACL v3-b cgroup-guard evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from typing import Any


DEFAULT_EVIDENCE = Path("/private/tmp/q04-acl-window-20260917-v3-b")
EXPECTED_TAR_SHA256 = "7e5f1733622aa750784834742692acb126f9c7efe1076e9cf58f82ff8817c829"
SAMPLES_MEMBER = "./state/acl-window-v3-b/worker-1/samples.jsonl"
FAILURE_MEMBER = "./state/acl-window-v3-b/fresh-09/failure.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(root: Path) -> dict[str, str]:
    manifest = json.loads((root / "artifact-manifest.json").read_text())
    observed: dict[str, str] = {}
    for artifact in manifest["artifacts"]:
        path = root / artifact["name"]
        assert path.stat().st_size == artifact["bytes"], artifact["name"]
        digest = sha256(path)
        assert digest == artifact["sha256"], artifact["name"]
        observed[artifact["name"]] = digest
    assert observed["remote-evidence.tar"] == EXPECTED_TAR_SHA256
    return observed


def member_json(archive: tarfile.TarFile, name: str) -> Any:
    stream = archive.extractfile(name)
    assert stream is not None, name
    return json.loads(stream.read())


def member_rows(archive: tarfile.TarFile, name: str) -> list[dict[str, Any]]:
    stream = archive.extractfile(name)
    assert stream is not None, name
    return [json.loads(line) for line in stream if line.strip()]


def summarize(root: Path) -> dict[str, Any]:
    hashes = verify_manifest(root)
    capacity = json.loads((root / "capacity.json").read_text())
    workflow = json.loads((root / "fresh-workflow-summary.json").read_text())
    runtime_precheck = json.loads((root / "runtime-precheck.json").read_text())
    archive_path = root / "remote-evidence.tar"

    with tarfile.open(archive_path) as archive:
        samples = member_rows(archive, SAMPLES_MEMBER)
        failure = member_json(archive, FAILURE_MEMBER)
        member_names = archive.getnames()

    assert len(samples) >= 2
    assert all(b["time"] > a["time"] for a, b in zip(samples, samples[1:]))
    assert failure == {
        "type": "ValueError",
        "reason": "cgroup budget exceeded",
        "injection": None,
    }
    ceiling = capacity["max_cgroup_bytes"]
    breaches = [row for row in samples if row["memory_current"] > ceiling]
    assert breaches, "captured trace no longer reproduces the cgroup rejection"
    first = breaches[0]
    peak = max(samples, key=lambda row: row["memory_current"])
    started = workflow["workflow_started_at"]
    active_start = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
    active = [row for row in samples if row["time"] >= active_start]
    assert peak in active

    vm_oom = sorted({row["vm_oom_kill"] for row in samples})
    cgroup_oom = sorted(
        {row["memory_events"].get("oom_kill", 0) for row in samples}
    )
    psi = max(row["psi_full_avg10"] for row in samples)
    sample_fields = set().union(*(row.keys() for row in samples))
    archive_has_decomposition = any(
        term in name.lower()
        for name in member_names
        for term in ("memory.stat", "smaps", "rss", "pss", "memory.peak")
    )

    return {
        "verdict": "RED_CGROUP_GUARD_REJECTED",
        "evidence": {
            "artifact_count": len(hashes),
            "remote_tar_sha256": hashes["remote-evidence.tar"],
            "manifest_verified": True,
        },
        "guard": {
            "kind": "qualification_sampled_ceiling",
            "ceiling_bytes": ceiling,
            "kernel_memory_max": runtime_precheck["cgroup"]["memory.max"].strip(),
            "kernel_memory_high": runtime_precheck["cgroup"]["memory.high"].strip(),
        },
        "trace": {
            "sample_count": len(samples),
            "active_sample_count": len(active),
            "maximum_sample_gap_seconds": max(
                b["time"] - a["time"] for a, b in zip(samples, samples[1:])
            ),
            "first_breach_time": first["time"],
            "first_breach_bytes": first["memory_current"],
            "first_breach_stage": first["parser"].get("stage"),
            "observed_maximum_bytes": peak["memory_current"],
            "observed_maximum_stage": peak["parser"].get("stage"),
            "maximum_observed_bytes_over_ceiling": peak["memory_current"] - ceiling,
            "minimum_available_bytes": min(row["available"] for row in active),
            "maximum_psi_full_avg10": psi,
            "vm_oom_kill_values": vm_oom,
            "cgroup_oom_kill_values": cgroup_oom,
            "censored_at_guard_stop": True,
        },
        "measurement_scope": {
            "proc_cgroup": runtime_precheck["proc_cgroup"].strip(),
            "observed_metric": "/sys/fs/cgroup/memory.current",
            "process_rss_or_pss_present": bool(
                {"rss", "pss", "process_rss", "process_pss"} & sample_fields
            ),
            "memory_stat_or_peak_present": archive_has_decomposition,
            "exclusive_parser_attribution_supported": False,
        },
        "workflow": {
            "started_at": started,
            "temporal_status": workflow["temporal_status"],
            "application_status": workflow["application_result"]["status"],
            "processing_complete": workflow["application_result"][
                "processing_complete"
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument(
        "--require-within-guard",
        action="store_true",
        help="require an all-green trace; intentionally exits nonzero for v3-b",
    )
    args = parser.parse_args()
    result = summarize(args.evidence_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.require_within_guard:
        print(result["verdict"], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
