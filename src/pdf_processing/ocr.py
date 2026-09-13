"""Fresh-process OCR for an explicitly selected Docling picture component."""
import base64
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import sys
import time


def execute(request):
    import pypdfium2 as pdfium
    from PIL import Image
    from rapidocr import RapidOCR
    from rapidocr.utils.output import RapidOCROutput
    import rapidocr

    assert rapidocr.__file__ is not None
    parsed, source, out = (Path(request[k]) for k in ('parsed', 'pdf', 'out'))
    out.mkdir(parents=True, exist_ok=True)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    try:
        doc = json.loads(parsed.read_text())
        item = next(p for p in doc['pictures'] if p['self_ref'] == request['component'])
        if len(item['prov']) != 1:
            raise ValueError('This extraction seam requires single-page picture provenance')
        prov = item['prov'][0]
        with pdfium.PdfDocument(source) as pdf:
            page = pdf[prov['page_no'] - 1]
            try:
                b = prov['bbox']
                w, h = page.get_size()
                scale = request.get('scale', 3)
                if w*h*scale*scale > request.get('max_render_pixels', 20_000_000):
                    raise ValueError('component_render_pixel_limit')
                if page.get_rotation() != 0 or tuple(page.get_bbox()) != (0, 0, w, h):
                    raise ValueError('unsupported_rotated_or_cropped_page')
                if b['coord_origin'] == 'BOTTOMLEFT':
                    box = (b['l'], h-b['t'], b['r'], h-b['b'])
                elif b['coord_origin'] == 'TOPLEFT':
                    box = (b['l'], b['t'], b['r'], b['b'])
                else:
                    raise ValueError('unsupported_coordinate_origin')
                assert 0 <= box[0] < box[2] <= w and 0 <= box[1] < box[3] <= h
                def pixels(value):
                    return Image.open(io.BytesIO(base64.b64decode(value['image']['uri'].split(',')[1])))
                page_pixels = pixels(doc['pages'][str(prov['page_no'])])
                original_crop = pixels(item)
                assert page_pixels.size == (round(w), round(h))
                # PDFium accepts fractional scale; its unannotated default infers int.
                rendered = page.render(scale=1.5)  # pyright: ignore[reportArgumentType]
                assert rendered.to_pil().resize(page_pixels.size).convert('RGB').tobytes() == page_pixels.convert('RGB').tobytes()
                rendered.close()
                assert page_pixels.crop(box).tobytes() == original_crop.tobytes()
                crop = page.render(scale=scale).to_pil().crop(tuple(x*scale for x in box))
            finally:
                page.close()
    except (ValueError, AssertionError, KeyError, StopIteration, IndexError):
        (out/'failure.json').write_text(json.dumps({'category': 'integrity', 'code': 'invalid_component_crop'}))
        raise
    crop.save(out/'figure.png')
    t = time.perf_counter()
    result = RapidOCR()(crop)
    if not isinstance(result, RapidOCROutput):
        raise TypeError("Expected complete OCR output")
    report = {
        'component': item['self_ref'], 'parsed_result_sha256': sha(parsed),
        'source_sha256': sha(source), 'provenance': prov, 'render_scale': scale,
        'pixel_dimensions': crop.size, 'crop_sha256': sha(out/'figure.png'),
        'cached_component_pixels_match_coordinates': True,
        'producer': {'engine': 'RapidOCR', 'version': importlib.metadata.version('rapidocr'),
                     'backend': 'onnxruntime ' + importlib.metadata.version('onnxruntime'),
                     'model_sha256': {p.name: sha(p) for p in (Path(rapidocr.__file__).parent/'models').glob('*.onnx')}},
        'seconds_including_engine_load': time.perf_counter()-t,
        'texts': list(result.txts) if result.txts is not None else [],
        'scores': [float(x) for x in result.scores] if result.scores is not None else [],
        'boxes': result.boxes.tolist() if result.boxes is not None else [],
    }
    (out/'ocr.json').write_text(json.dumps(report, indent=2))

if __name__ == '__main__':
    execute(json.load(sys.stdin))
