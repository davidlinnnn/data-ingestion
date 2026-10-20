"""Read-only replay plus isolated negative mutations; never regenerates saved evidence."""
from pathlib import Path
import shutil
import json
import tempfile
import unittest

import controls as c


class NativeBundleTests(unittest.TestCase):
    def test_saved_bundles_and_boundary_controls_read_only(self):
        before = {str(p): c.sha(p) for p in c.HERE.rglob('*') if p.is_file()}
        result = c.controls(c.HERE/'bundle-original')
        self.assertTrue(result['positive_native_bundle']['pass'])
        self.assertEqual(len(result['negative_controls_rejected']), 17)
        self.assertTrue(c.verify_bundle(c.HERE/'bundle-relocated')['pass'])
        self.assertTrue(all(c.sha(c.ROOT/name)==expected for name,expected in c.read(c.HERE/'evidence-hashes.json').items()))
        self.assertEqual(before, {str(p): c.sha(p) for p in c.HERE.rglob('*') if p.is_file()})

    def test_missing_crop_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)/'bundle'
            shutil.copytree(c.HERE/'bundle-relocated',target)
            record=c.read(target/'supplement.json')['images'][0]
            (target/record['image_path']).unlink()
            with self.assertRaisesRegex(ValueError,'inventory mismatch'):
                c.verify_bundle(target)

    def test_changed_raw_response_rejected_before_reload(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'bundle'
            shutil.copytree(c.HERE/'bundle-relocated',target)
            (target/'provider/mock-response.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                c.verify_bundle(target)

    def test_changed_crop_rejected_even_when_hashes_and_identity_updated(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'bundle'
            shutil.copytree(c.HERE/'bundle-relocated',target)
            supplement=c.read(target/'supplement.json')
            record=supplement['images'][0]
            image_path=target/record['image_path']
            with c.Image.open(image_path) as source:
                image=source.copy()
            pixel=image.getpixel((0,0))
            image.putpixel((0,0),(pixel[0]^255,pixel[1],pixel[2]))
            image.save(image_path)
            record['crop_sha256']=c.sha(image_path)
            record['image_key']=c.digest([supplement['document_revision'],record['owner_ref'],record['crop_sha256']])
            raw=c.read(target/'provider/mock-response.json')
            raw['input']={k:record[k] for k in ['owner_ref','image_key','crop_sha256']}
            (target/'supplement.json').write_text(json.dumps(supplement))
            (target/'provider/mock-response.json').write_text(json.dumps(raw))
            manifest=c.read(target/'bundle.json')
            manifest['files']={name:c.sha(target/name) for name in manifest['files']}
            (target/'bundle.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'crop pixels differ'):
                c.verify_bundle(target)

    def test_native_child_text_change_rejected(self):
        directory=c.HERE/'bundle-original'
        doc=c.DoclingDocument.load_from_json(directory/'document.json')
        doc.pictures[0].children[0].resolve(doc).text='native source changed'
        with self.assertRaisesRegex(ValueError,'native graph'):
            c.validate(doc,c.read(directory/'supplement.json'),c.read(directory/'baseline.json'),
                       c.read(directory/'provider/mock-response.json'))

    def test_native_child_order_change_rejected(self):
        directory=c.HERE/'bundle-original'
        doc=c.DoclingDocument.load_from_json(directory/'document.json')
        children=doc.pictures[0].children
        children[0],children[1]=children[1],children[0]
        with self.assertRaisesRegex(ValueError,'native graph'):
            c.validate(doc,c.read(directory/'supplement.json'),c.read(directory/'baseline.json'),
                       c.read(directory/'provider/mock-response.json'))

    def test_rotation_axes_and_anisotropic_mapping(self):
        point=[13.25,72.5]
        self.assertEqual(c.rotate(point,317,199,90),[126.5,13.25])
        self.assertEqual(c.rotate(point,317,199,180),[303.75,126.5])
        self.assertEqual(c.rotate(point,317,199,270),[72.5,303.75])
        mapping={'crop_size_px':[317,199],'page_pixel_window':[41,73,358,272],'page_scale_xy':[2.3,1.7]}
        self.assertEqual(c.to_page([0,0],mapping),[41/2.3,73/1.7])
        self.assertNotEqual(c.rotate(c.rotate(point,317,199,90),199,317,90),point)


if __name__=='__main__':
    unittest.main()
