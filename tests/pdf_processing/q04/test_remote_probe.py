"""Tests for configurable restored-state paths in the read-only probe."""

import json
from pathlib import Path
import tempfile
import unittest

from preflight.remote_probe import configured_producer_roots, retained_profile_inventory


class RemoteProbe(unittest.TestCase):
    def test_restored_bundle_can_supply_the_retained_profile(self):
        method = {"python": "3.12.13", "packages": {}, "model_artifacts": {}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inputs.json"
            path.write_text(
                json.dumps(
                    {
                        "base_profile": {
                            "method": method,
                            "group_pages": 5,
                            "release": "q01-release",
                        }
                    }
                )
            )

            result = retained_profile_inventory(
                {"profile_path": str(path)}, method
            )

        self.assertTrue(result["method_matches"])
        self.assertEqual(result["group_pages"], 5)
        self.assertEqual(result["release"], "q01-release")

    def test_explicit_producer_roots_replace_the_pre_restart_default(self):
        roots = configured_producer_roots(
            {"producer_roots": ["/app/pdf_processing", "/restored/q04/producer"]}
        )

        self.assertEqual(
            roots, ["/app/pdf_processing", "/restored/q04/producer"]
        )


if __name__ == "__main__":
    unittest.main()
