"""Necessary offline checks for the bounded DE object operation contract."""
import json
from unittest.mock import patch

import normal_topology_de as run


assert run.RUN_ID == "object-rw-de"
assert run.PREFIX == "t09a/object-probe-20260928-de/"
assert run.REQUESTS * run.REQUEST_BYTES == 32 * 1024 * 1024
reply = {"kind": "put", "key": run.PREFIX + "object-00.bin",
    "bytes": run.REQUEST_BYTES, "started_at": 1, "finished_at": 2,
    "latency_seconds": .5}
with patch.object(run.co, "object_request", return_value=json.dumps(reply)):
    run.co.record["operations"] = []
    assert run.object_operation("put", reply["key"]) == reply
    assert run.co.record["operations"] == [reply]
bad = dict(reply, bytes=1)
with patch.object(run.co, "object_request", return_value=json.dumps(bad)):
    try:
        run.object_operation("put", reply["key"])
    except ValueError as error:
        assert str(error) == "object operation response changed"
    else:
        raise AssertionError("invalid object response accepted")
print("PASS: fresh prefix;32MiB bound; exact PUT/GET response validation")
