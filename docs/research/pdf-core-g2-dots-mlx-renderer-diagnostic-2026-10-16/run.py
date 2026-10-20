"""Reuse the frozen runner with one official PDF-backend override, two pages only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REG = json.loads((HERE / "registration.json").read_text())
REPO = HERE.parents[2]
source = REPO / REG["parent_run_ref"]["path"]
assert hashlib.sha256(source.read_bytes()).hexdigest() == REG["parent_run_ref"]["sha256"]
spec = importlib.util.spec_from_file_location("frozen_mlx_runner", source)
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)
runner.HERE, runner.OUT, runner.REG = HERE, HERE / "run", REG
runner.__file__ = __file__

if sys.argv[1:] == ["--child"] or sys.argv[1:] == ["--preflight"]:
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.document_converter import PdfFormatOption

    def pdf_option(*args, **kwargs):
        kwargs["backend"] = PyPdfiumDocumentBackend
        return PdfFormatOption(*args, **kwargs)

    assert pdf_option().backend is PyPdfiumDocumentBackend
    assert len(json.loads((HERE / "inputs.json").read_text())["pages"]) == 2
    if sys.argv[1:] == ["--child"]:
        with patch("docling.document_converter.PdfFormatOption", pdf_option):
            runner.child()
    else:
        print("Official backend override and frozen two-page scope verified; no model instances")
else:
    assert not sys.argv[1:]
    runner.main()
