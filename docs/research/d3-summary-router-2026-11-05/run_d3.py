"""#166 d3 inference: the model package's d3_server.py on MPS, reached only at POST /v1/systemone.

    scripts/heavy-lock 166-d3-flash -- D3_PYTHON run_d3.py OUT SPLIT --package DIR [--resume]

D3_PYTHON is the d3 runtime's python (#153's venv, transformers 5.17.0); DIR the d3-flash package
(d3_server.py beside the weights). Before the server starts: freeze.json's hashes must match, every
file of weights-d3-flash.json must match on disk, and for SPLIT test selection.json and
test-launch.json must be committed unchanged, with test-launch naming selection's hash. The
server runs with --device mps --batch-size 1, HF offline, a bearer key made for the run, on a
port of its own (refused when taken). Requests go one at a time: dev items carry both questions,
test items only the selected one. One result per item under OUT/runs/SPLIT/items/; a run that
finds results refuses to start, except --resume, which sends only the items without a result
(no item is ever sent twice). A non-2xx reply or a malformed answer stops the run (stop.json);
so does host available memory under 4 GiB.
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
PORT = 8166


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 24):
            digest.update(chunk)
    return digest.hexdigest()


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def score(question: str, answer: dict) -> float:
    if question == "Q1":
        probabilities = answer["probabilities"]
        assert set(probabilities) == {"supported", "partly_supported", "unsupported"}, answer
        assert abs(sum(probabilities.values()) - 1) < 1e-5, answer
        value = probabilities["supported"]
    else:
        value = answer["noul"]
    assert 0 <= value <= 1, answer
    return value


def committed(path: Path) -> bool:
    git = ["git", "-C", str(HERE)]
    tracked = subprocess.run([*git, "ls-files", "--error-unmatch", path.name], capture_output=True)
    clean = subprocess.run([*git, "diff", "--quiet", "HEAD", "--", path.name])
    return tracked.returncode == 0 and clean.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("split", choices=["dev", "test"])
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    a = parser.parse_args()
    out = a.out.resolve()
    for file, digest in json.loads((HERE / "freeze.json").read_text())["files"].items():
        path = Path(file).expanduser()
        assert sha(path if path.is_absolute() else HERE / path) == digest, file
    questions = json.loads((HERE / "questions.json").read_text())
    if a.split == "test":
        selection, launch = HERE / "selection.json", HERE / "test-launch.json"
        assert committed(selection) and committed(launch), "selection and launch must be committed"
        assert json.loads(launch.read_text())["selection_sha256"] == sha(selection)
        chosen = json.loads(selection.read_text())["question"]
        questions = {chosen: questions[chosen]}
    manifest = json.loads((HERE / "weights-d3-flash.json").read_text())
    assert not manifest["mismatches"]
    for f in manifest["files"]:
        if "sha256" in f:
            assert sha(a.package / f["file"]) == f["sha256"], f["file"]

    base = out / "runs" / a.split
    (base / "items").mkdir(parents=True, exist_ok=True)
    done = {p.stem for p in (base / "items").glob("*.json")}
    assert a.resume or not done, "results exist; one execution per split (--resume sends the rest)"
    rows = [r for r in json.loads((out / "items.json").read_text())
            if r["split"] == a.split and r["id"] not in done]  # fmt: skip
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
        with httpx.Client(timeout=600, headers={"Authorization": f"Bearer {key}"}) as http:
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
                  {"seconds": time.monotonic() - started,
                   "models": http.get(f"{url}/v1/models").json()})  # fmt: skip
            for n, row in enumerate(rows):
                if psutil.virtual_memory().available < 4 * 1024**3:
                    stop = {"reason": "MEMORY_FENCE", "remaining": len(rows) - n}
                    break
                t = time.monotonic()
                reply = http.post(f"{url}/v1/systemone",
                                  json={"state": row["state"], "questions": questions})  # fmt: skip
                seconds = time.monotonic() - t
                if reply.status_code != 200:
                    stop = {"reason": "HTTP", "id": row["id"], "status": reply.status_code,
                            "body": reply.text[:2000]}  # fmt: skip
                    break
                body = reply.json()
                try:
                    scores = {q: score(q, body["answers"][q]) for q in questions}
                except (AssertionError, KeyError, TypeError) as exc:
                    stop = {"reason": "MALFORMED", "id": row["id"], "error": repr(exc)}
                    break
                write(base / "items" / f"{row['id']}.json",
                      {"id": row["id"], "split": a.split, "questions": list(questions),
                       "seconds": seconds, "scores": scores, "usage": body.get("usage"),
                       "answers": body["answers"]})  # fmt: skip
                print(json.dumps({"split": a.split, "completed": n + 1, "total": len(rows),
                                  "seconds": round(seconds, 3)}), flush=True)  # fmt: skip
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
