"""Run the unchanged T01 fresh-scan assertion in the pinned Linux coordinator."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('restoration','/tmp/t05-test/tests/test_restoration.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
root=Path('/tmp/t05-source')
root.mkdir(exist_ok=True)
(root/'src').symlink_to('/app',target_is_directory=True)
module.ROOT=root
module.FIXED=Path('/experiment')
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
raise SystemExit(0 if result.wasSuccessful() else 1)
