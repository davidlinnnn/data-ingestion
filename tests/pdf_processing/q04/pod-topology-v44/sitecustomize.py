"""AS-only OCR phase markers without changing the frozen producer."""

import json
import os
from pathlib import Path
import resource
import sys
import time


_directory = os.environ.get("Q04_OCR_TRACE_DIR")
if _directory and "PDF_PROCESS_LIFECYCLE_FD" in os.environ:
    _path = Path(_directory) / f"ocr-{os.getpid()}.jsonl"
    _writing = False

    def _mark(stage):
        global _writing
        if _writing:
            return
        _writing = True
        try:
            _path.parent.mkdir(parents=True, exist_ok=True)
            usage = resource.getrusage(resource.RUSAGE_SELF)
            row = {"stage": stage, "pid": os.getpid(), "time": time.time(),
                   "monotonic": time.monotonic(), "minor_faults": usage.ru_minflt,
                   "major_faults": usage.ru_majflt}
            for name, key in (("/proc/self/status", "VmRSS"),
                              ("/proc/self/smaps_rollup", "Pss")):
                try:
                    row[key.lower() + "_kb"] = next(
                        int(line.split()[1]) for line in Path(name).read_text().splitlines()
                        if line.startswith(key + ":"))
                except (OSError, StopIteration):
                    row[key.lower() + "_kb"] = None
            with _path.open("a") as stream:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            _writing = False

    def _ocr_lines(frame, event, arg):
        if event == "line":
            source = frame.f_code.co_filename
            line = __import__("linecache").getline(source, frame.f_lineno).strip()
            if line == "t = time.perf_counter()":
                _mark("crop_ready")
        elif event == "return" and (Path(frame.f_locals.get("out", "/")) / "ocr.json").exists():
            _mark("result_written")
        return _ocr_lines

    def _trace(frame, event, arg):
        if event == "call" and frame.f_code.co_name == "execute" \
                and frame.f_code.co_filename.endswith("/pdf_processing/ocr.py"):
            _mark("ocr_enter")
            return _ocr_lines
        return None

    def _profile(frame, event, arg):
        if _writing or event not in ("call", "return"):
            return
        instance = frame.f_locals.get("self")
        if instance is None or instance.__class__.__name__ != "RapidOCR" \
                or not instance.__class__.__module__.startswith("rapidocr"):
            return
        if frame.f_code.co_name == "__init__":
            _mark("engine_start" if event == "call" else "engine_ready")
        elif frame.f_code.co_name == "__call__":
            _mark("inference_start" if event == "call" else "inference_ready")

    sys.settrace(_trace)
    sys.setprofile(_profile)
