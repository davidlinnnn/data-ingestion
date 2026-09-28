"""Real child process stopped at observable stage boundaries for external Pod kill."""
import os
from pathlib import Path
import runpy
import signal
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FAULT = os.environ.get('PDF_FAULT', '')

def stop(point):
    Path(os.environ['PDF_FAULT_MARKER']).write_text(point)
    print('PROTOTYPE_STOP_AT_' + point, flush=True)
    os.kill(os.getpid(), signal.SIGSTOP)

if sys.argv[1] == 'ocr':
    from rapidocr import RapidOCR
    original = RapidOCR.__call__
    def call(self, *args, **kwargs):
        if FAULT == 'ocr':
            stop('ocr_before_inference_after_engine_init')
        return original(self, *args, **kwargs)
    RapidOCR.__call__ = call
    sys.argv = [str(ROOT/'k8s/ocr_component.py'), *sys.argv[2:]]
    runpy.run_path(str(ROOT/'k8s/ocr_component.py'), run_name='__main__')
else:
    import experiment
    original_event = experiment.event
    def event(stage, pages, elapsed, **extra):
        original_event(stage, pages, elapsed, **extra)
        if FAULT == 'parse' and stage == 'checkpoint_commit' and 7 in pages:
            stop('parse_after_page_7_before_group_registration')
    experiment.event = event
    if FAULT == 'assembly':
        from docling.models.stages.reading_order.readingorder_model import ReadingOrderModel
        original = ReadingOrderModel.__call__
        def reading(self, *args, **kwargs):
            stop('assembly_at_reading_order_entry')
            return original(self, *args, **kwargs)
        ReadingOrderModel.__call__ = reading
    sys.argv = [str(ROOT/'experiment.py'), *sys.argv[1:]]
    experiment.main()
