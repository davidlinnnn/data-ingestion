"""Regression observer: assert real component OCR sessions honor the 4-thread bound."""
from pathlib import Path
exec(compile(Path('/source/tests/pdf_processing/t09a_bounds/ocr-thread-probe/ct2/sitecustomize.py').read_text(), 'ct2-observer', 'exec'))
if _directory and 'PDF_PROCESS_LIFECYCLE_FD' in os.environ:
    previous_profile = _profile
    def _profile(frame, event, arg):
        previous_profile(frame, event, arg)
        instance = frame.f_locals.get('self')
        if event == 'return' and frame.f_code.co_name == '__init__' and instance is not None and type(instance).__name__ == 'RapidOCR' and type(instance).__module__.startswith('rapidocr'):
            values = [model.session.session.get_session_options().intra_op_num_threads
                      for model in (instance.text_det, instance.text_cls, instance.text_rec)]
            (Path(_directory).parent/'thread-budget-check.json').write_text(json.dumps({'intra_op_threads':values}))
            assert values == [4,4,4], f'component OCR thread budget not applied: {values}'
    sys.setprofile(_profile)
