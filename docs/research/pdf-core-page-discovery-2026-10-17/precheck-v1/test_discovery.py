from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import discovery as d


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patch = patch.object(d, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        Image.new("RGB", (200, 400), "white").save(self.root/"page.png")
        (self.root/"source.pdf").write_bytes(b"source-control-not-real-pdf")
        (self.root/"baseline.json").write_text("{}")
        self.job = dict(id="synthetic-p2", physical_page=2, pixels_wh=[200, 400],
            size_points=[100, 200], image="page.png", image_sha256=d.file_hash(self.root/"page.png"),
            source="source.pdf", source_sha256=d.file_hash(self.root/"source.pdf"),
            baseline="baseline.json", baseline_sha256=d.file_hash(self.root/"baseline.json"),
            native_scopes=[dict(scope_id="native:0", bbox_top_left_points=[0, 0, 10, 20])])
        self.response = dict(complete=True, issues=[], regions=[dict(kind="math", container="body", bbox=[500,500,900,900])])

    def test_new_region_without_native_owner_keeps_page_binding(self):
        out = d.bind_response(self.job, self.response)
        candidate = out["candidates"][0]
        self.assertEqual(candidate["native_intersections"], [])
        self.assertEqual(candidate["crop_pixels"], [100,200,180,360])
        self.assertEqual(candidate["bbox_top_left_points"], [50,100,90,180])
        self.assertEqual(candidate["physical_page"], 2)
        self.assertFalse(out["source_coverage_verified"])
        self.assertEqual(out["preserved_native_scopes"], self.job["native_scopes"])
        self.assertEqual(out["raw_response"], self.response)
        self.assertEqual(json.loads(json.dumps(out)), out)

    def test_overlap_does_not_consume_native(self):
        self.response["regions"][0]["bbox"] = [0,0,1000,1000]
        out = d.bind_response(self.job, self.response)
        self.assertEqual(out["candidates"][0]["native_intersections"], ["native:0"])
        self.assertEqual(out["candidates"][0]["consumes_native_refs"], [])
        self.assertFalse(out["canonical_writeback"])

    def test_table_picture_caption_and_unknown_are_not_forced_to_body(self):
        for container, hint in (("table","B"),("picture","A+C"),("caption","parent+A"),("unknown","unresolved")):
            with self.subTest(container=container):
                self.response["regions"][0]["container"] = container
                out = d.bind_response(self.job, self.response)
                self.assertEqual(out["candidates"][0]["responsibility_hint"], hint)
                self.assertFalse(out["candidates"][0]["delivered"])

    def test_invalid_boxes_refused(self):
        for box in ([0,0,0,1], [-1,0,1,1], [0,0,1001,1000], [0,0,1], [False,0,1,1], [0,0,float("nan"),1]):
            with self.subTest(box=box), self.assertRaises(ValueError):
                d.window(box, [200,400])

    def test_outward_rounding_and_page_edge(self):
        self.assertEqual(d.window([1,1,999,999], [1191,1684]), [1,1,1190,1683])
        self.assertEqual(d.window([0,0,1000,1000], [1191,1684]), [0,0,1191,1684])

    def test_native_origin_conversion(self):
        self.assertEqual(d.native_box(dict(bbox=dict(l=10,t=190,r=30,b=180,coord_origin="BOTTOMLEFT")), [100,200]), [10,10,30,20])

    def test_duplicates_unknown_fields_and_overflow_refused(self):
        bad = []
        other = deepcopy(self.response); other["regions"] *= 2; bad.append(other)
        other = deepcopy(self.response); other["transcript"] = "answer"; bad.append(other)
        other = deepcopy(self.response); other["regions"][0]["text"] = "answer"; bad.append(other)
        other = deepcopy(self.response); other["regions"] *= 129; bad.append(other)
        other = deepcopy(self.response); other["regions"][0]["kind"] = []; bad.append(other)
        for response in bad:
            with self.subTest(response_type=list(response)), self.assertRaises(ValueError):
                d.bind_response(self.job, response)

    def test_abstention_is_preserved(self):
        self.response.update(complete=False, issues=["ambiguous_boundary"])
        self.assertFalse(d.bind_response(self.job,self.response)["model_claimed_complete"])
        self.response["complete"] = True
        with self.assertRaises(ValueError):
            d.bind_response(self.job,self.response)

    def test_empty_result_does_not_prove_no_targets(self):
        self.response["regions"] = []
        self.assertFalse(d.bind_response(self.job,self.response)["source_coverage_verified"])

    def test_changed_input_or_page_image_refused(self):
        for name in ("source.pdf","baseline.json","page.png"):
            with self.subTest(name=name):
                path = self.root/name
                original = path.read_bytes()
                path.write_bytes(original+b"changed")
                with self.assertRaises(ValueError):
                    d.bind_response(self.job,self.response)
                path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
