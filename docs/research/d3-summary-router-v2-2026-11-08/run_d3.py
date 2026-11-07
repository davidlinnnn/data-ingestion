"""#174 d3 inference: the model package's d3_server.py on MPS, reached only at POST /v1/systemone.

    scripts/heavy-lock 174-d3-flash -- D3_PYTHON run_d3.py OUT RUN --package DIR [--resume]

RUN is one of (freeze.md §5):
  fmt-json, fmt-text  dev, the format subset (OUT/dev/format-subset.json), question G only
  dev                 dev, every item, every question, in format.json's format (committed)
  test                heldout, every item, selection.json's questions and format; selection.json
                      and test-launch.json committed unchanged, test-launch naming selection's
                      hash and the held-out requests' hash

One request per evidence group (OUT/SPLIT/requests.json): the evidence once in state, one
question per (sentence, question) with the sentence in its instructions. D3_PYTHON is the d3
runtime's python (#153's venv, transformers 5.17.0); DIR the d3-flash package. Before the server
starts, freeze.json's hashes and the weights in weights-d3-flash.json must match. The server runs
with --device mps --batch-size 1, HF offline, a key made for the run, on a port of its own
(refused when taken); requests go one at a time. One result per group under OUT/runs/RUN/; a run
that finds results refuses to start except with --resume, which sends only the groups without a
result (none is sent twice). A non-2xx reply, a malformed answer or host memory under 4 GiB
stops the run (stop-*.json).
"""

import argparse
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil

HERE = Path(__file__).resolve().parent
PORT = 8174
RUNS = {"fmt-json": "dev", "fmt-text": "dev", "dev": "dev", "test": "heldout"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 24):
            digest.update(chunk)
    return digest.hexdigest()


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def committed(path: Path) -> bool:
    git = ["git", "-C", str(HERE)]
    tracked = subprocess.run([*git, "ls-files", "--error-unmatch", path.name], capture_output=True)
    clean = subprocess.run([*git, "diff", "--quiet", "HEAD", "--", path.name])
    return tracked.returncode == 0 and clean.returncode == 0


def plan(out: Path, run: str) -> tuple[str, list[str], set[str] | None]:
    """The run's state format, question names and item subset (None: every item)."""
    if run.startswith("fmt-"):
        return run[4:], ["G"], set(json.loads((out / "dev" / "format-subset.json").read_text()))
    if run == "dev":
        assert committed(HERE / "format.json"), "format.json must be committed before the dev run"
        return json.loads((HERE / "format.json").read_text())["format"], list("GCSQE"), None
    selection, launch = HERE / "selection.json", HERE / "test-launch.json"
    assert committed(selection) and committed(launch), "selection and launch must be committed"
    launched = json.loads(launch.read_text())
    assert launched["selection_sha256"] == sha(selection)
    assert launched["heldout_requests_sha256"] == sha(out / "heldout" / "requests.json")
    chosen = json.loads(selection.read_text())
    return chosen["format"], chosen["questions"], None


def questions_for(group: dict, names: list[str], subset: set[str] | None, spec: dict) -> dict:
    return {f"{i['id']}.{q}": {"type": "noul",
                              "instructions": spec["preamble"].format(sentence=i["sentence"])
                              + spec["questions"][q]}
            for i in group["items"] if subset is None or i["id"] in subset for q in names}  # fmt: skip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("run", choices=list(RUNS))
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    a = parser.parse_args()
    out = a.out.expanduser().resolve()
    for file, digest in json.loads((HERE / "freeze.json").read_text())["files"].items():
        path = Path(file).expanduser()
        assert sha(path if path.is_absolute() else HERE / path) == digest, file
    manifest = json.loads((HERE / "weights-d3-flash.json").read_text())
    assert not manifest["mismatches"]
    for f in manifest["files"]:
        if "sha256" in f:
            assert sha(a.package / f["file"]) == f["sha256"], f["file"]
    fmt, names, subset = plan(out, a.run)
    spec = json.loads((HERE / "questions.json").read_text())
    groups = json.loads((out / RUNS[a.run] / "requests.json").read_text())
    groups = [g for g in groups if subset is None or any(i["id"] in subset for i in g["items"])]

    base = out / "runs" / a.run
    (base / "groups").mkdir(parents=True, exist_ok=True)
    done = {p.stem for p in (base / "groups").glob("*.json")}
    assert a.resume or not done, "results exist; one execution per run (--resume sends the rest)"
    rows = [g for g in groups if g["id"] not in done]
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", PORT)) != 0, f"port {PORT} is taken"

    key = secrets.token_hex(16)
    log = (base / f"server-{int(time.time())}.log").open("w")
    command = [sys.executable, str(a.package / "d3_server.py"), "--device", "mps",
               "--batch-size", "1", "--port", str(PORT), "--name", "d3-flash"]  # fmt: skip
    env = {**os.environ, "DECISION_API_KEY": key, "HF_HUB_OFFLINE": "1",
           "TRANSFORMERS_OFFLINE": "1", "PYTORCH_ENABLE_MPS_FALLBACK": "0"}  # fmt: skip
    started = time.monotonic()
    server = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{PORT}"
    stop = None
    try:
        with httpx.Client(timeout=1800, headers={"Authorization": f"Bearer {key}"}) as http:
            while True:
                assert server.poll() is None, "d3_server.py exited; see the server log"
                try:
                    if http.get(f"{url}/health").json().get("status") == "ready":
                        break
                except httpx.TransportError:
                    pass
                assert time.monotonic() - started < 1800, "server not ready in 30 minutes"
                time.sleep(5)
            write(base / f"load-{int(time.time())}.json",
                  {"seconds": time.monotonic() - started, "format": fmt, "questions": names,
                   "models": http.get(f"{url}/v1/models").json()})  # fmt: skip
            for n, group in enumerate(rows):
                if psutil.virtual_memory().available < 4 * 1024**3:
                    stop = {"reason": "MEMORY_FENCE", "remaining": len(rows) - n}
                    break
                questions = questions_for(group, names, subset, spec)
                state = group["state_json"] if fmt == "json" else group["state_text"]
                t = time.monotonic()
                reply = http.post(f"{url}/v1/systemone", json={"state": state, "questions": questions})
                seconds = time.monotonic() - t
                if reply.status_code != 200:
                    stop = {"reason": "HTTP", "id": group["id"], "status": reply.status_code,
                            "body": reply.text[:2000]}  # fmt: skip
                    break
                body = reply.json()
                scores: dict[str, dict[str, float]] = {}
                try:
                    for qid in questions:
                        value = body["answers"][qid]["noul"]
                        assert 0 <= value <= 1, qid
                        item, q = qid.split(".")
                        scores.setdefault(item, {})[q] = value
                except (AssertionError, KeyError, TypeError) as exc:
                    stop = {"reason": "MALFORMED", "id": group["id"], "error": repr(exc)}
                    break
                write(base / "groups" / f"{group['id']}.json",
                      {"id": group["id"], "run": a.run, "format": fmt, "questions": names,
                       "seconds": seconds, "scores": scores, "usage": body.get("usage")})  # fmt: skip
                print(json.dumps({"run": a.run, "completed": n + 1, "total": len(rows),
                                  "questions": len(questions), "seconds": round(seconds, 2)}), flush=True)  # fmt: skip
    finally:
        server.terminate()
        server.wait(60)
    if stop:
        write(base / f"stop-{int(time.time())}.json", stop)
        print(json.dumps(stop), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
