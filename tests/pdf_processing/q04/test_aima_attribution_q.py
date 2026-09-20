"""Q keeps unknown PSS unknown and records both process enumerations."""

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from sentinel import aima_attribution_telemetry_q as telemetry


class ProcessTransitionEvidenceTest(unittest.TestCase):
    def test_changed_membership_persists_exact_before_and_after_identities(self):
        before = {
            100: {"pid": 100, "ppid": 1, "start_ticks": 1000, "state": "S"},
            101: {"pid": 101, "ppid": 100, "start_ticks": 1001, "state": "S"},
        }
        after = {
            **before,
            102: {"pid": 102, "ppid": 101, "start_ticks": 1002, "state": "R"},
        }

        def read_text(path):
            return {
                "memory.current": "1000\n",
                "memory.events": "oom_kill 0\n",
                "memory.stat": (
                    "anon 1\nfile 1\nshmem 0\nfile_mapped 0\n"
                    "inactive_file 0\nslab 1\nkernel 1\n"
                ),
                "memory.pressure": "some total=0\nfull total=0\n",
            }[path.name]

        def process(_proc, identity, _text, _bytes, owned):
            return {
                **identity,
                "ownership": "owned" if owned else "shared_cgroup_other",
                "status": "complete",
                "command_class": "worker",
                "pss_bytes": 10,
            }

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            telemetry, "cgroup_identity", return_value={"proc_cgroup": "0::/"}
        ), mock.patch.object(
            telemetry,
            "_scan_identities",
            side_effect=[(before, []), (after, [])],
        ), mock.patch.object(telemetry, "_read_process", side_effect=process):
            row = telemetry.strict_attribution_sample(
                root_pid=100,
                expected_cgroup={"proc_cgroup": "0::/"},
                proc_root=Path(tmp) / "proc",
                cgroup_root=Path(tmp) / "cgroup",
                read_text=read_text,
                read_bytes=lambda _path: b"",
            )

        coverage = row["process_coverage"]
        self.assertFalse(row["attribution_complete"])
        self.assertIsNone(row["owned_pss_total_bytes"])
        self.assertEqual(
            coverage["identities_before"],
            [
                {"pid": 100, "ppid": 1, "start_ticks": 1000},
                {"pid": 101, "ppid": 100, "start_ticks": 1001},
            ],
        )
        self.assertEqual(
            coverage["identities_after"],
            coverage["identities_before"]
            + [{"pid": 102, "ppid": 101, "start_ticks": 1002}],
        )


if __name__ == "__main__":
    unittest.main()
