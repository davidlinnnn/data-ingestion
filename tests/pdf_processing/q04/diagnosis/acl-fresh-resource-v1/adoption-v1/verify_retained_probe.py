"""Execute the generated retained-request probe against a private S3 snapshot."""

import argparse
import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types

Q04_DIR = Path(__file__).resolve().parents[3]
if str(Q04_DIR) not in sys.path:
    sys.path.insert(0, str(Q04_DIR))

from sentinel.run_acl_option_a_c import (
    build_initialized_state_probe_program,
    build_old_request_binding_program,
    validate_initialized_state,
)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class Body:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload


class MockS3:
    def __init__(self, objects):
        self.objects = objects
        self.list_calls = []
        self.get_calls = []

    def list_objects_v2(self, *, Bucket, Prefix, **kwargs):
        self.list_calls.append({"Bucket": Bucket, "Prefix": Prefix, **kwargs})
        return {
            "Contents": [
                {"Key": key} for key in sorted(self.objects) if key.startswith(Prefix)
            ]
        }

    def get_object(self, *, Bucket, Key):
        self.get_calls.append({"Bucket": Bucket, "Key": Key})
        return {"Body": Body(self.objects[Key])}


def execute_fixture(path):
    snapshot_raw = path.read_bytes()
    snapshot = json.loads(snapshot_raw)
    prefix = snapshot["prefix"]
    accepted_raw = base64.b64decode(snapshot["accepted_b64"])
    config_raw = base64.b64decode(snapshot["config_b64"])
    objects = {
        key: base64.b64decode(value)
        for key, value in snapshot["objects_b64"].items()
    }
    accepted = json.loads(accepted_raw)
    config = json.loads(config_raw)
    mock = MockS3(objects)
    fake_boto3 = types.ModuleType("boto3")

    def client(service, *, endpoint_url):
        if service != "s3" or endpoint_url != "http://objects:9000":
            raise ValueError("unexpected mocked boto3 client request")
        return mock

    fake_boto3.client = client
    previous = sys.modules.get("boto3")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        accepted_path = root / "state/keynote-window-2/fresh-10/accepted.json"
        accepted_path.parent.mkdir(parents=True)
        accepted_path.write_bytes(accepted_raw)
        (root / "state/config.json").write_bytes(config_raw)
        program = build_old_request_binding_program(root=str(root), prefix=prefix)
        output = io.StringIO()
        try:
            sys.modules["boto3"] = fake_boto3
            with redirect_stdout(output):
                exec(compile(program, "<generated-retained-request-probe>", "exec"), {})
        finally:
            if previous is None:
                sys.modules.pop("boto3", None)
            else:
                sys.modules["boto3"] = previous

        state_output = io.StringIO()
        state_program = build_initialized_state_probe_program(root=str(root))
        with redirect_stdout(state_output):
            exec(compile(state_program, "<generated-init-state-probe>", "exec"), {})
        initialized = json.loads(state_output.getvalue())

    binding = json.loads(output.getvalue())
    if mock.list_calls != [
        {"Bucket": "t09a", "Prefix": prefix + "registered/"}
    ]:
        raise ValueError("generated probe registration listing changed")
    fetched_keys = [call["Key"] for call in mock.get_calls]
    if sorted(fetched_keys) != sorted(objects) or len(fetched_keys) != len(objects):
        raise ValueError("generated probe did not fetch each snapshot object exactly once")
    matching = []
    for key, raw in objects.items():
        if not key.startswith(prefix + "registered/"):
            continue
        manifest = json.loads(raw)
        for file in manifest["files"]:
            if file["name"] != "processing-result.json":
                continue
            result_raw = objects[file["key"]]
            if sha256(result_raw) != file["sha256"] or len(result_raw) != file["bytes"]:
                raise ValueError("snapshot object hash or length mismatch")
            result = json.loads(result_raw)
            if result["source"]["request_id"] == accepted["request"]["request_id"]:
                matching.append((key, manifest, file, result))
    if len(matching) != 1:
        raise ValueError("snapshot does not contain one unique retained binding")
    key, manifest, file, result = matching[0]
    expected = {
        "registration_key": key,
        "operation": manifest["operation"],
        "request_id": result["source"]["request_id"],
        "source_key": result["source"]["artifact"]["key"],
        "profile_id": result["provenance"]["profile"]["id"],
        "profile_release": result["provenance"]["profile"]["release"],
        "artifact_sha256": file["sha256"],
        "status": result["status"],
    }
    if binding != expected:
        raise ValueError("generated probe binding differs from independent snapshot check")
    if config["profiles"]["10"] != accepted["profile"]:
        raise ValueError("accepted profile differs from retained config")
    profile_keys = set(config["profiles"])
    reconstructed_bundle = {
        "producer": config["producer"],
        "base_profile": {
            "id": config["profiles"]["09"]["id"],
            "method": config["profiles"]["09"]["method"],
        },
        "fixtures": [
            {"id": key}
            for key in sorted(profile_keys - {"native-evidence", "native-method"})
        ],
    }
    validate_initialized_state(
        initialized,
        reconstructed_bundle,
        remote_root=config["bundle"].removesuffix("/inputs"),
        prefix=config["prefix"],
        source_run_id="schema-audit-must-not-equal-retained-run",
        bundle_sha256=config["bundle_sha256"],
    )
    return {
        "status": "PASS",
        "snapshot_sha256": sha256(snapshot_raw),
        "accepted_sha256": sha256(accepted_raw),
        "config_sha256": sha256(config_raw),
        "object_count": len(objects),
        "registration_list_count": len(mock.list_calls),
        "object_get_count": len(mock.get_calls),
        "matching_binding_count": len(matching),
        "init_schema_status": "PASS",
        "init_config_field_count": len(initialized["config_keys"]),
        "request_id_sha256": sha256(binding["request_id"].encode()),
        "source_key_sha256": sha256(binding["source_key"].encode()),
        "profile_id": binding["profile_id"],
        "profile_release": binding["profile_release"],
        "result_artifact_sha256": binding["artifact_sha256"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = execute_fixture(args.fixture)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.open("x").write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
