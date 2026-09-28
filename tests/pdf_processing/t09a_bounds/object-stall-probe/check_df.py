"""Necessary offline checks for the bounded DF many-small-key contract."""
import json
from unittest.mock import patch

import normal_topology_df as run


assert run.RUN_ID == "object-small-key-df"
assert run.SOURCE == "t09a/bounds-20260928-dd/"
assert run.PREFIX == "t09a/object-probe-20260928-df/"
assert run.SELECTED == 256 and run.SELECTED_BYTES == 2737516 and run.BATCH == 16
row = {"key": run.PREFIX + "attempts/id/file.json", "bytes": 10,
    "source_get_seconds": .01, "put_seconds": .02, "dest_get_seconds": .01}
reply = {"selected": run.SELECTED, "selected_bytes": run.SELECTED_BYTES,
    "start": 0, "rows": [row] * run.BATCH}
with patch.object(run.co, "object_request", return_value=json.dumps(reply)):
    run.co.record["batches"] = []
    assert run.replay_batch(0) == reply
    assert run.co.record["batches"] == [reply]
bad = dict(reply, selected_bytes=1)
with patch.object(run.co, "object_request", return_value=json.dumps(bad)):
    try:
        run.replay_batch(0)
    except ValueError as error:
        assert str(error) == "small-key replay response changed"
    else:
        raise AssertionError("invalid small-key replay accepted")
print("PASS: immutable DD source; fresh DF prefix;256-object/32MiB bound; response validation")
