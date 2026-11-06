"""report.md §2.6: re-send 15 dev items with Q2 only and compare with the dev run (Q1+Q2 in one request).

    scripts/heavy-lock 166-d3-recheck -- D3_PYTHON docs/research/d3-summary-router-2026-11-05/recheck.py

Dev items only; no test item is sent again. Run 2026-11-06 from the session scratchpad with the
output beside the script; only the repo path and the output path differ from the run.
"""
import json, os, random, secrets, socket, subprocess, sys, time
from pathlib import Path
import httpx

OUT = Path.home() / "archive/research/166-d3-router"
PKG = Path.home() / "models/issue84/d3-flash"
HERE = REPO = Path(__file__).resolve().parent
PORT = 8166
q2 = {"Q2": json.loads((REPO / "questions.json").read_text())["Q2"]}
items = {i["id"]: i for i in json.loads((OUT / "items.json").read_text()) if i["split"] == "dev"}
ids = random.Random(166).sample(sorted(items), 15)
with socket.socket() as probe:
    assert probe.connect_ex(("127.0.0.1", PORT)) != 0, "port taken"
key = secrets.token_hex(16)
env = {**os.environ, "DECISION_API_KEY": key, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
       "PYTORCH_ENABLE_MPS_FALLBACK": "0"}
log = (OUT / "runs" / "recheck-server.log").open("w")
server = subprocess.Popen([sys.executable, str(PKG / "d3_server.py"), "--device", "mps", "--batch-size", "1",
                           "--port", str(PORT), "--name", "d3-flash"], env=env, stdout=log, stderr=subprocess.STDOUT)
rows = []
try:
    with httpx.Client(timeout=600, headers={"Authorization": f"Bearer {key}"}) as http:
        t0 = time.monotonic()
        while True:
            assert server.poll() is None
            try:
                if http.get(f"http://127.0.0.1:{PORT}/health").json().get("status") == "ready":
                    break
            except httpx.TransportError:
                pass
            assert time.monotonic() - t0 < 1800
            time.sleep(5)
        for i in ids:
            old = json.loads((OUT / "runs/dev/items" / f"{i}.json").read_text())
            t = time.monotonic()
            r = http.post(f"http://127.0.0.1:{PORT}/v1/systemone", json={"state": items[i]["state"], "questions": q2})
            s = time.monotonic() - t
            assert r.status_code == 200, r.text[:500]
            b = r.json()
            rows.append({"id": i, "old_q2": old["scores"]["Q2"], "new_q2": b["answers"]["Q2"]["noul"],
                         "old_seconds_two_q": old["seconds"], "new_seconds_one_q": s,
                         "old_tokens": old["usage"]["input_tokens"], "new_tokens": b["usage"]["input_tokens"]})
            print(json.dumps(rows[-1]), flush=True)
finally:
    server.terminate(); server.wait(60)
(HERE / "recheck-dev.json").write_text(json.dumps(rows, indent=1))
d = [abs(r["old_q2"] - r["new_q2"]) for r in rows]
print("max |delta|", max(d), "median one-q seconds", sorted(r["new_seconds_one_q"] for r in rows)[7],
      "median old two-q seconds", sorted(r["old_seconds_two_q"] for r in rows)[7])
