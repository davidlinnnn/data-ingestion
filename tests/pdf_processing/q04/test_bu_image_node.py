"""Projected preflight must accept only the relocated worker's node."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pod_preflight_bu as preflight


class ImageNodeTest(unittest.TestCase):
    def test_relocated_image_identity(self):
        engine = preflight.base.base
        self.assertEqual(engine.EXPECTED_NODE, "internal-a2a-vs6-local-worker")
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "pod-identity.json"
            path.write_text(json.dumps({
                "node": "internal-a2a-vs6-local-worker",
                "image_id": engine.EXPECTED_IMAGE,
                "image_id_representation": "repository-platform-manifest",
                "restart_count": 0,
                "pod_name": "pod", "pod_uid": "uid", "container_id": "container",
            }))
            with mock.patch.object(engine, "EXPECTED_NODE", "internal-a2a-vs6-local-worker2"):
                with self.assertRaisesRegex(ValueError, "accepted Pod image identity changed"):
                    engine.verify_image_identity(path)
            self.assertEqual(engine.verify_image_identity(path)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
