"""Last bounded configuration: change reasoning effort only; reuse the frozen runner."""
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARENT = HERE.parent / "pdf-core-g2-official-method-2026-10-15"
spec = importlib.util.spec_from_file_location("frozen_official_candidate2", PARENT / "run.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
original_options = base.options


def options(credential=""):
    configured = original_options(credential)
    configured.vlm_options.engine_options.params["reasoning_effort"] = "medium"
    return configured


def self_check():
    a, b = original_options(), options()
    old = a.vlm_options.engine_options.params
    new = b.vlm_options.engine_options.params
    assert old["reasoning_effort"] == "low" and new["reasoning_effort"] == "medium"
    assert {**old, "reasoning_effort": "medium"} == new
    assert a.model_dump(mode="json") == b.model_dump(mode="json"), "Base-typed serialization should otherwise match"
    registration = json.loads((HERE / "registration.json").read_text())
    assert hashlib.sha256((PARENT / "run.py").read_bytes()).hexdigest() == registration["parent_runner_ref"]["sha256"]
    assert hashlib.sha256((HERE / "review/contract.json").read_bytes()).hexdigest() == registration["source_contract_sha256"]
    return frozen_check()


frozen_check = base.self_check
base.HERE = HERE
base.__file__ = str(Path(__file__).resolve())
base.options = options
base.self_check = self_check

if __name__ == "__main__":
    self_check()
    if sys.argv[1:] == ["--self-check"]:
        print("Only low-to-medium reasoning changed; no API call")
    else:
        assert not sys.argv[1:]
        with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            base.main()
