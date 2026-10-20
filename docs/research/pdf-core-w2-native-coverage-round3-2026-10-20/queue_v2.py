"""Wait for the single V1 worker to finish, then launch V2 once, never retry."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
while not (HERE/"runs/V1/execution.json").exists():
    if time.time()>1792484318: raise SystemExit("round deadline")
    time.sleep(2)
execution=json.loads((HERE/"runs/V1/execution.json").read_text())
assert execution["completed_attempts"]==36, "V1 stopped early; do not launch next full run"
inventory=json.loads((HERE/"diagnostics/egret-medium-local.json").read_text())
assert inventory["required_files_present"]
for item in inventory["files"]:
    assert hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()==item["sha256"], item["name"]
print("V1 complete; Egret local hashes verified; starting V2 once",flush=True)
raise SystemExit(subprocess.call(["rtk","proxy",sys.executable,str(HERE/"run_round3.py"),"--run","V2"]))
