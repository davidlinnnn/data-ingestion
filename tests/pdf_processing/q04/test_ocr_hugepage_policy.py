"""Verify OCR-only policy reaches the real fresh child before imports."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pdf_processing.execution import Execution
import pdf_processing.lifecycle_child as lifecycle


class OCRHugepagePolicyTest(unittest.IsolatedAsyncioTestCase):
    async def test_policy_is_ocr_only_with_and_without_lifecycle_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); package = root / 'pdf_processing'; package.mkdir()
            (package / '__init__.py').touch()
            shutil.copyfile(lifecycle.__file__, package / 'lifecycle_child.py')
            body = "import os,json,sys\nfrom pathlib import Path\nvalue=os.environ.get('NUMPY_MADVISE_HUGEPAGE')\nrequest=json.load(sys.stdin)\nPath(request['out'],'env.json').write_text(json.dumps(value))\n"
            for module in ('ocr', 'evidence'):
                (package / (module + '.py')).write_text(body)
            for wrapped in (False, True):
                for module in ('ocr', 'evidence'):
                    with self.subTest(wrapped=wrapped, module=module):
                        out = root / f'{wrapped}-{module}'; out.mkdir()
                        with patch.dict(os.environ, {'PYTHONPATH':str(root), 'NUMPY_MADVISE_HUGEPAGE':'1'}):
                            if wrapped: os.environ['PDF_PROCESS_LIFECYCLE_LOCK'] = str(root/'lock')
                            else: os.environ.pop('PDF_PROCESS_LIFECYCLE_LOCK', None)
                            execution = Execution(None, None, root, child_timeout=5)
                            await execution.child('pdf_processing.' + module, {'out':str(out)}, out)
                            self.assertEqual(json.loads((out/'env.json').read_text()), '0' if module == 'ocr' else '1')
                            self.assertEqual(os.environ['NUMPY_MADVISE_HUGEPAGE'], '1')
                            self.assertFalse(execution.fresh_children)


if __name__ == '__main__': unittest.main()
