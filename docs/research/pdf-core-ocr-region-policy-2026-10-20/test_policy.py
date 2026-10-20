"""Real factory discovery and geometry controls; no model weights loaded."""
from types import SimpleNamespace
import unittest

from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.pipeline_options import OcrMode
from docling.models.factories import get_ocr_factory
from docling_core.types.doc import BoundingBox, Size

from region_policy import SeparateOptions, SeparateRapidOcr


class CropPolicyControls(unittest.TestCase):
    def regions(self, boxes, context=False, cells=None):
        model = SeparateRapidOcr(enabled=False, artifacts_path=None,
            options=SeparateOptions(mode=OcrMode.LAYOUT_REGIONS, preserve_context=context),
            accelerator_options=AcceleratorOptions(device="cpu"))
        page = SimpleNamespace(size=Size(width=100, height=100),
            _backend=SimpleNamespace(get_text_cells=lambda: [] if cells is None else cells),
            predictions=SimpleNamespace(layout=SimpleNamespace(clusters=[
                SimpleNamespace(bbox=BoundingBox(l=l,t=t,r=r,b=b,coord_origin="TOPLEFT"))
                for l,t,r,b in boxes])))
        return model.get_ocr_rects(page)

    def test_real_plugin_discovery_and_disabled_initialization(self):
        factory = get_ocr_factory(allow_external_plugins=True)
        self.assertIs(factory.classes[SeparateOptions], SeparateRapidOcr)
        model = factory.create_instance(options=SeparateOptions(), enabled=False,
            artifacts_path=None, accelerator_options=AcceleratorOptions(device="cpu"))
        self.assertIsInstance(model, SeparateRapidOcr)

    def test_padding_does_not_reconnect_separated_crops(self):
        values = self.regions([(10,10,40,30),(50,10,80,30)], context=True)
        self.assertEqual(len(values), 2)
        self.assertGreater(values[0].r, values[1].l)

    def test_actual_overlap_grouped_without_duplicate_crops(self):
        self.assertEqual(len(self.regions([(10,10,40,30),(30,10,50,30)])), 1)

    def test_context_clipped_to_page_and_original_coverage_retained(self):
        values = self.regions([(0,0,5,5),(95,95,100,100)], context=True)
        self.assertEqual([(v.l,v.t,v.r,v.b) for v in values], [(0,0,15,15),(85,85,100,100)])

    def test_empty_layout(self):
        self.assertEqual(self.regions([]), [])

    def test_native_text_rejected(self):
        with self.assertRaisesRegex(AssertionError, "raster"):
            self.regions([(1,1,10,10)], cells=[object()])


if __name__ == "__main__":
    unittest.main()
