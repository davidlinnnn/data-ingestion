"""The release evidence cannot silently drift from the tested image/source bytes."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]


class Evidence(unittest.TestCase):
    def test_sealed_artifacts_and_packaged_source_match(self):
        directory=Path(__file__).parent/'evidence'
        index=json.loads((directory/'INDEX.json').read_text())
        for name,digest in index['sealed_artifacts'].items():
            self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),digest)
        release=json.loads((directory/'RELEASE.json').read_text())
        for name,digest in release['image_source_hashes'].items():
            path=ROOT/'src'/name if name.startswith('pdf_processing/') else ROOT/'deploy/pdf-processing'/name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest,name)


if __name__=='__main__':unittest.main()
