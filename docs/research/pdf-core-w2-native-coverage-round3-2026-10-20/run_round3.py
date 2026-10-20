"""One fresh CPU4 worker per document; reuse frozen round2 observer, no retries."""
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import psutil

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PREV = HERE.parent / "pdf-core-w2-native-coverage-round2-2026-10-20"
JOBS = json.loads((PREV / "jobs.json").read_text())["jobs"]
DEADLINE = datetime.datetime.fromisoformat("2026-10-20T08:18:38+00:00").timestamp()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str)+"\n")
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_options(value):
    if isinstance(value, dict):
        return {k: sorted(v) if k == "supported_engines" and isinstance(v, list)
                else canonical_options(v) for k, v in value.items()}
    if isinstance(value, list): return [canonical_options(v) for v in value]
    return value


def plan(name):
    return json.loads((HERE / "plans" / f"{name}.json").read_text())


def child(name, jobid):
    spec = importlib.util.spec_from_file_location("readonly_round2_worker", PREV / "run_full.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = plan(name)
    job = next(j for j in JOBS if j["id"] == jobid)
    assert sha(job["pdf"]) == job["pdf_sha256"]
    base_options = module.options
    def options():
        opts = base_options()
        opts.generate_page_images = False
        opts.generate_picture_images = False
        if config["variant"] == "V1":
            opts.use_reading_order_separators = False
        elif config["variant"] == "V2":
            from docling.datamodel.pipeline_options import LayoutObjectDetectionOptions
            previous_layout=opts.layout_options.model_dump(mode="json")
            opts.layout_options = LayoutObjectDetectionOptions.from_preset("layout_egret_medium")
            current_layout=opts.layout_options.model_dump(mode="json")
            assert {k:v for k,v in previous_layout.items() if k!="model_spec"} == {k:v for k,v in current_layout.items() if k!="model_spec"}
        else:
            assert config["variant"] == "baseline_noimages"
        actual = opts.model_dump(mode="json", serialize_as_any=True)
        previous = json.loads((PREV / "effective-options.json").read_text())
        a, b = canonical_options(actual), canonical_options(previous)
        changed = sorted(k for k in a if a[k] != b[k])
        expected = ["generate_page_images", "generate_picture_images"]
        if config["variant"] == "V1": expected += ["use_reading_order_separators"]
        if config["variant"] == "V2": expected += ["layout_options"]
        assert changed == sorted(expected), changed
        save(HERE / "runs" / name / "option-diff.json", dict(changed_top_level_keys=changed,
             previous={k:previous[k] for k in changed}, effective={k:actual[k] for k in changed}))
        return opts
    folder = HERE / "runs" / name
    module.HERE = folder
    module.JOBS = [job]
    module.options = options
    module.verify_registration = lambda: config
    module.worker(0)
    identity=json.loads((folder/"runtime-identity.json").read_text())
    identity.update(models_unchanged=config["variant"]!="V2", round3_variant=config["variant"],
                    round3_runner_sha256=sha(__file__), original_observer_sha256=sha(PREV/"run_full.py"))
    save(folder/"runtime-identity.json",identity)
    save(folder/"jobs"/jobid/"runtime-identity.json",identity)
    save(folder / "jobs" / jobid / "round3-provenance.json", dict(
        observer_sha256=sha(PREV / "run_full.py"), runner_sha256=sha(__file__),
        isolated_document_worker=True, variant=config["variant"], model_downloads=0,
        note="Unmodified round2 worker function, redirected globals and official options only."))


def run(name):
    config = plan(name)
    folder = HERE / "runs" / name
    assert not folder.exists(), "Never rerun a registered run"
    if config.get("purpose") != "equivalence_control":
        assert json.loads((HERE / "controls-equivalence.json").read_text())["equivalent"] is True
    if config["variant"] == "V2":
        availability = json.loads((HERE / "diagnostics/egret-medium-local.json").read_text())
        assert availability
    folder.mkdir(parents=True)
    (folder / "jobs").mkdir()
    for part in ("cache", "tmp"):
        (HERE / part).mkdir(exist_ok=True)
    env = os.environ | dict(PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4", HF_HOME="/private/tmp/pdf-core-native-20261017/hf",
        MPLCONFIGDIR=str(HERE / "cache"), XDG_CACHE_HOME=str(HERE / "cache"), TMPDIR=str(HERE / "tmp"))
    allsamples, records = [], []
    begin = time.monotonic()
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "r") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for jobid in config["job_ids"]:
            if time.time() >= DEADLINE or psutil.virtual_memory().available < 4*2**30:
                break
            job = next(j for j in JOBS if j["id"] == jobid)
            save(folder / "stage.json", dict(stage="initialize", job=jobid, started=time.monotonic(), limit=180))
            start = time.monotonic()
            reason = None
            samples = []
            with (folder / f"{jobid}.log").open("w") as log:
                proc = subprocess.Popen(["rtk", "proxy", sys.executable, str(Path(__file__).resolve()), "--child", name, jobid],
                    env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    while proc.poll() is None:
                        try:
                            root = psutil.Process(proc.pid)
                            processes = [root] + root.children(recursive=True)
                            rss = sum(p.memory_info().rss for p in processes if p.is_running())
                            cpu = sum(sum(p.cpu_times()[:2]) for p in processes if p.is_running())
                        except psutil.NoSuchProcess:
                            rss, cpu = 0, 0
                        stage = json.loads((folder / "stage.json").read_text())
                        available = psutil.virtual_memory().available
                        sample = dict(monotonic=time.monotonic(), job=jobid, rss=rss, cpu_sample_seconds=cpu,
                                      available=available, stage=stage["stage"])
                        samples.append(sample)
                        if time.time() >= DEADLINE: reason = "budget_stop"
                        elif rss > 12*2**30: reason = "rss_stop"
                        elif available < 4*2**30: reason = "available_memory_stop"
                        elif time.monotonic()-stage["started"] > stage["limit"]: reason = "document_timeout"
                        if reason: break
                        time.sleep(.1)
                finally:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
            dest = folder / "jobs" / jobid
            dest.mkdir(exist_ok=True)
            cp = dest / "conversion.json"
            if not cp.exists():
                save(cp, dict(id=jobid, status=reason or "worker_error", retries=0, exit_code=proc.returncode))
            status = json.loads(cp.read_text())["status"]
            record = dict(id=jobid, status=status, stop=reason, exit_code=proc.returncode,
                          attempt_wall_seconds=time.monotonic()-start, pages=job["last"]-job["first"]+1,
                          peak_tree_rss_bytes=max((s["rss"] for s in samples), default=0),
                          sampled_cpu_seconds=max((s["cpu_sample_seconds"] for s in samples), default=0), retries=0)
            for artifact in ("initialization-00.json", "effective-options.json", "option-diff.json", "reading-order-options.json"):
                source = folder / artifact
                if source.exists(): (dest / artifact).write_bytes(source.read_bytes())
            save(dest / "supervision.json", record)
            records.append(record)
            allsamples.extend(samples)
            save(folder / "progress.json", dict(records=records, selected=len(config["job_ids"])))
            print(json.dumps(record), flush=True)
            if reason in {"budget_stop", "available_memory_stop"}: break
    save(folder / "execution.json", dict(wall_seconds=time.monotonic()-begin, records=records,
        selected_jobs=len(config["job_ids"]), completed_attempts=len(records), samples=allsamples,
        peak_tree_rss_bytes=max((s["rss"] for s in allsamples),default=0), automatic_retries=0))


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        assert len(JOBS)==36 and sum(j["last"]-j["first"]+1 for j in JOBS)==715
        assert canonical_options({"supported_engines":["b","a"]}) == {"supported_engines":["a","b"]}
        print("36/715 registration; one fresh worker per document; 12/4GiB guard; no retry")
    elif sys.argv[1:2] == ["--child"]: child(sys.argv[2],sys.argv[3])
    elif sys.argv[1:2] == ["--run"]: run(sys.argv[2])
    else: raise SystemExit("--selfcheck, --run name, --child name jobid")
