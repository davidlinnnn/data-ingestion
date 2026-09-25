"""Run the fixed YOLO launcher's generated probes without a live service.

The retained ACL snapshot supplies real accepted metadata.  A memory-only S3
stand-in reconstructs the embedded final with its recorded byte length and SHA.
The init phase uses the production init function with memory-only S3; it cannot
connect to Temporal because init returns before a client is created.
"""

import argparse
import asyncio
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from types import SimpleNamespace
from unittest import mock

from sentinel import run_yolo_matrix_a as runner

EXPECTED_LAUNCHER_SHA256 = "c2937100736b61377ad1cd5b9230d6149e4946513fa3aff2afa72494d323ef18"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class MemoryS3:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.counter = 0

    def get_bucket_versioning(self, **_kwargs):
        return {"Status": "Enabled"}

    def list_objects_v2(self, *, Prefix, MaxKeys=1000, **_kwargs):
        rows = [
            {"Key": key, "Size": len(value)}
            for key, value in self.objects.items()
            if key.startswith(Prefix)
        ]
        return {"Contents": rows[:MaxKeys]} if rows else {}

    def get_object(self, *, Key, **_kwargs):
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, *, Key, Body, **_kwargs):
        self.counter += 1
        self.objects[Key] = Body if isinstance(Body, bytes) else Body.read()
        return {"VersionId": f"offline-{self.counter:02d}"}


def retained_acl_store(snapshot):
    case = snapshot / "state/acl-option-a-window-c/fresh-09"
    accepted = json.loads((case / "accepted.json").read_text())
    registrations = json.loads((case / "registrations.json").read_text())
    operation = accepted["result"]["processing_result"]
    manifest = registrations[operation]
    final = json.dumps(
        accepted["accepted"]["final"], sort_keys=True, separators=(",", ":")
    ).encode()
    item = next(
        row for row in manifest["files"] if row["name"] == "processing-result.json"
    )
    if len(final) != item["bytes"] or sha(final) != item["sha256"]:
        raise ValueError("retained embedded ACL final does not reproduce registered bytes")
    registration_key = (
        runner.SOURCE_PREFIX + "registered/" + sha(operation.encode()) + ".json"
    )
    return accepted, {
        registration_key: json.dumps(manifest, sort_keys=True).encode(),
        item["key"]: final,
    }


def read_keynote_identity(archive):
    members = {
        "config": "./state/keynote-window-2/config.json",
        "accepted": "./state/keynote-window-2/fresh-10/accepted.json",
        "fresh_index": "./state/keynote-window-2/fresh-index.json",
    }
    raw = {}
    with tarfile.open(archive, mode="r") as retained:
        for name, member in members.items():
            stream = retained.extractfile(member)
            if stream is None:
                raise ValueError(f"missing retained Keynote member: {member}")
            raw[name] = stream.read()
    config = json.loads(raw["config"])
    accepted = json.loads(raw["accepted"])
    fresh_index = json.loads(raw["fresh_index"])
    request = accepted["request"]
    if accepted["sid"] != "10" or accepted["mode"] != "fresh":
        raise ValueError("retained Keynote record is not fresh fixture 10")
    if fresh_index != {"10": accepted["directory"]}:
        raise ValueError("retained Keynote fresh index does not bind accepted directory")
    if config["run_id"] not in accepted["workflow_id"]:
        raise ValueError("retained Keynote config/run identity mismatch")
    if not request["artifact"]["key"].startswith(config["prefix"] + "sources/"):
        raise ValueError("retained Keynote source is outside its recorded prefix")
    return {
        "fixture": accepted["sid"],
        "mode": accepted["mode"],
        "run_id": config["run_id"],
        "prefix": config["prefix"],
        "request_id": request["request_id"],
        "source_key": request["artifact"]["key"],
        "source_sha256": request["artifact"]["sha256"],
        "source_revision": request["source_revision"],
        "profile_release": accepted["profile"]["release"],
        "accepted_sha256": sha(raw["accepted"]),
        "config_sha256": sha(raw["config"]),
        "fresh_index_sha256": sha(raw["fresh_index"]),
        "archive_sha256": sha(Path(archive).read_bytes()),
    }


def write_fake_boto3(directory, objects):
    encoded = {key: base64.b64encode(value).decode() for key, value in objects.items()}
    (directory / "boto3.py").write_text(
        "import base64,io,json,os\n"
        "DATA={k:base64.b64decode(v) for k,v in json.loads(os.environ['Q04_OFFLINE_S3']).items()}\n"
        "class OfflineS3Client:\n"
        " def list_objects_v2(self,Prefix,**kw):return {'Contents':[{'Key':k} for k in DATA if k.startswith(Prefix)]}\n"
        " def get_object(self,Key,**kw):return {'Body':io.BytesIO(DATA[Key])}\n"
        "def client(*a,**kw):return OfflineS3Client()\n"
    )
    return json.dumps(encoded, sort_keys=True)


def run_old_binding(snapshot, work):
    accepted, objects = retained_acl_store(snapshot)
    fake = work / "fake"
    fake.mkdir()
    encoded = write_fake_boto3(fake, objects)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", Q04_OFFLINE_S3=encoded)
    env["PYTHONPATH"] = str(fake)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            runner.build_old_request_binding_program(
                root=str(snapshot), prefix=runner.SOURCE_PREFIX
            ),
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    result = json.loads(completed.stdout)
    if result["request_id"] != accepted["request"]["request_id"]:
        raise ValueError("generated old-binding probe did not bind retained ACL request")
    result["source_sha256"] = accepted["request"]["artifact"]["sha256"]
    result["source_revision"] = accepted["request"]["source_revision"]
    return result


def stage_tree(work, frozen_code, bundle):
    root = work / "stage"
    shutil.copytree(frozen_code, root / "code")
    shutil.copy2(
        Path(__file__).parents[1] / "q04_runtime.py",
        root / "code/tests/pdf_processing/q04/q04_runtime.py",
    )
    shutil.copytree(bundle, root / "inputs", copy_function=os.link)
    (root / "state").mkdir()
    completed = subprocess.run(
        [sys.executable, "-c", runner.build_staging_probe_program(root=str(root))],
        check=True,
        capture_output=True,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        text=True,
    )
    staged = json.loads(completed.stdout)
    bundle_json = json.loads((bundle / "inputs.json").read_text())
    runner.validate_staged_runtime(staged, bundle_json)
    return root, staged, bundle_json


def import_runtime(root):
    paths = [
        root / "code/src",
        root / "code/tests/pdf_processing/q04",
        root / "code/tests/pdf_processing/q02",
        root / "code/tests/pdf_processing/q03",
    ]
    sys.path[:0] = [str(path) for path in paths]
    for name in ("consumer", "contracts", "host", "prepare", "telemetry"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(
        "q04_offline_runtime",
        root / "code/tests/pdf_processing/q04/q04_runtime.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_offline_init(root, bundle_json):
    module_names = (
        "consumer",
        "contracts",
        "host",
        "prepare",
        "telemetry",
        "pdf_processing.object_store",
        "pdf_processing.processing_workflow",
    )
    saved_path = list(sys.path)
    saved_modules = {name: sys.modules.get(name) for name in module_names}
    try:
        runtime = import_runtime(root)
        capacity = runner.build_capacity(
            started_at=time.time(),
            owner="offline-preflight",
            approval_reference="offline-no-runtime",
        )
        capacity_path = root / "capacity.json"
        capacity_path.write_text(json.dumps(capacity))
        client = MemoryS3()
        fake_boto3 = SimpleNamespace(client=lambda *_args, **_kwargs: client)
        fake_client = SimpleNamespace(Client=object)
        fake_worker = SimpleNamespace(Worker=object)
        fake_workflow = SimpleNamespace(PDFProcessing=object)
        args = SimpleNamespace(
            phase="init",
            bundle=root / "inputs",
            state=root / "state",
            capacity=capacity_path,
            capacity_approved=True,
            temporal="offline.invalid:7233",
            endpoint="memory://s3",
            bucket="offline",
            prefix=runner.PREFIX,
            model_cache=Path("/offline/model-cache"),
            pod_namespace=None,
            trial_seconds=180,
        )
        with mock.patch.dict(
            sys.modules,
            {
                "boto3": fake_boto3,
                "temporalio.client": fake_client,
                "temporalio.worker": fake_worker,
                "pdf_processing.processing_workflow": fake_workflow,
            },
        ):
            asyncio.run(runtime.main(args))
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                runner.build_initialized_state_probe_program(root=str(root)),
            ],
            check=True,
            capture_output=True,
            text=True,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )
        initialized = json.loads(completed.stdout)
        runner.validate_initialized_state(
            initialized,
            bundle_json,
            remote_root=str(root.resolve()),
            source_run_id=runner.SOURCE_RUN_ID,
        )
        return initialized, len(client.objects)
    finally:
        sys.path[:] = saved_path
        for name, module in saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def capture_cli_argv(work, owner="offline-preflight", approval="offline-no-runtime"):
    collision = work / "claimed-output"
    collision.mkdir()
    argv = ["--execute", "--owner", owner, "--approval-reference", approval]
    wrapper = work / "capture_cli.py"
    wrapper.write_text(
        "import json,sys\n"
        "from pathlib import Path\n"
        "from sentinel import run_yolo_matrix_a as runner\n"
        "collision=sys.argv[1]\n"
        "sys.argv=[str(Path(runner.__file__).resolve()),*sys.argv[2:]]\n"
        "runner.OUT=Path(collision)\n"
        "try: runner.main()\n"
        "except FileExistsError: stopped=True\n"
        "else: stopped=False\n"
        "print(json.dumps({'argv':sys.argv,'stopped':stopped}))\n"
    )
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = str(Path(__file__).parents[1])
    completed = subprocess.run(
        [sys.executable, str(wrapper), str(collision), *argv],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    observed = json.loads(completed.stdout)
    if not observed["stopped"] or observed["argv"][1:] != argv:
        raise AssertionError("CLI did not stop at the exclusive output claim")
    return {
        "program": observed["argv"][0],
        "argv": argv,
        "parsed": True,
        "stop_point": "exclusive-output-collision-before-lock-or-remote-access",
    }


def run(snapshot, keynote_archive, frozen_code, bundle):
    fixed_before = sha(Path(runner.__file__).read_bytes())
    keynote = read_keynote_identity(keynote_archive)
    with tempfile.TemporaryDirectory(prefix="q04-yolo-offline-") as directory:
        work = Path(directory)
        old_binding = run_old_binding(snapshot, work)
        root, staged, bundle_json = stage_tree(work, frozen_code, bundle)
        initialized, uploaded_originals = run_offline_init(root, bundle_json)
        cli = capture_cli_argv(work)
    acl = {
        "fixture": "09",
        "request_id": old_binding["request_id"],
        "source_key": old_binding["source_key"],
        "source_sha256": old_binding["source_sha256"],
        "source_revision": old_binding["source_revision"],
        "profile_release": old_binding["profile_release"],
    }
    changed_fields = [
        field
        for field in ("fixture", "request_id", "source_key", "source_sha256", "source_revision", "profile_release")
        if keynote[field] != acl[field]
    ]
    if changed_fields != [
        "fixture", "request_id", "source_key", "source_sha256", "source_revision", "profile_release"
    ]:
        raise AssertionError("Keynote-to-ACL source transition was not exact and complete")
    fixed_after = sha(Path(runner.__file__).read_bytes())
    if fixed_before != fixed_after or fixed_after != EXPECTED_LAUNCHER_SHA256:
        raise AssertionError("fixed launcher changed")
    return {
        "schema_version": 1,
        "mode": "offline-no-inference-no-workflow",
        "retained_source": str(snapshot),
        "source_transition": {
            "previous_live_probe": keynote,
            "offline_retained_probe": acl,
            "changed_fields": changed_fields,
            "identity_changed": True,
        },
        "old_binding": old_binding,
        "staging": staged,
        "initialized": initialized,
        "offline_original_upload_count": uploaded_originals,
        "cli": cli,
        "fixed_launcher_sha256_before": fixed_before,
        "fixed_launcher_sha256_after": fixed_after,
        "runtime_started": False,
        "workflow_started": False,
        "inference_started": False,
        "deployment_changed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--keynote-archive", type=Path, required=True)
    parser.add_argument("--frozen-code", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.snapshot, args.keynote_archive, args.frozen_code, args.bundle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "out": str(args.out)}))


if __name__ == "__main__":
    main()
