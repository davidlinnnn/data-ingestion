"""Diagnostic-only extension of the preserved AS observer."""
from pathlib import Path
exec(compile((Path(__file__).resolve().parents[2] / "q04/pod-topology-v44/sitecustomize.py").read_text(), "as-observer", "exec"))
if _directory and "PDF_PROCESS_LIFECYCLE_FD" in os.environ:
    _prior_lines = _ocr_lines
    def _ocr_lines(frame, event, arg):
        if event == "line":
            line = __import__("linecache").getline(frame.f_code.co_filename, frame.f_lineno).strip()
            if line == "assert rapidocr.__file__ is not None":
                _mark("imports_ready")
            elif line.startswith("item = next(p for p in doc["):
                _mark("document_ready")
        _prior_lines(frame, event, arg)
        return _ocr_lines
