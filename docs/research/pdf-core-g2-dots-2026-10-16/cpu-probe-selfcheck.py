"""Check the resource guard with harmless stand-in processes, never model weights."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("probe", HERE / "cpu-probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
real_popen = subprocess.Popen
results = []
with tempfile.TemporaryDirectory(prefix="dots-guard-") as temporary:
    for name, command, timeout, minimum, expected in [
        ("success", "pass", 5, 0, "completed"),
        ("worker_error", "raise SystemExit(3)", 5, 0, "worker_error"),
        ("timeout", "import time; time.sleep(20)", .05, 0, "timeout"),
        ("prelaunch_memory", "pass", 5, 2**60, "insufficient_available_memory_before_launch"),
    ]:
        probe.OUT = Path(temporary) / name
        def standin(args, **kwargs):
            return real_popen(["rtk", "proxy", sys.executable, "-c", command], **kwargs)
        with patch.dict(probe.REG, {"max_worker_seconds": timeout, "min_prelaunch_available_bytes": minimum}), patch.object(probe.subprocess, "Popen", standin):
            probe.main()
        result = json.loads((probe.OUT / "execution.json").read_text())
        assert result["status"] == expected and result["all_owned_children_reaped"]
        results.append({"case":name,"status":result["status"],"reaped":True})
(HERE / "cpu-probe-selfcheck.json").write_text(json.dumps({"passed":True,"model_calls":0,"cases":results},indent=2)+"\n")
print("Resource guard self-check passed")
