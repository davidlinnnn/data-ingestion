"""Bounded fresh-child PDF inspection; no inference/model imports."""
import json
import math
from pathlib import Path
import sys


def inspect(request):
    import pypdfium2 as pdfium
    try:
        document = pdfium.PdfDocument(request['pdf'])
    except pdfium.PdfiumError as error:
        return {'error': 'password_required' if error.err_code == 4 else 'invalid_pdf'}
    try:
        count = len(document)
        if not 0 < count <= request['max_pages']:
            return {'error': 'page_limit'}
        sizes = []
        for index in range(count):
            page = document[index]
            try:
                width, height = page.get_size()
                # Include the selected parser's scale and enforce each page before render.
                pixels = math.ceil(width * request['render_scale']) * math.ceil(height * request['render_scale'])
                if not all(math.isfinite(v) and v > 0 for v in (width, height)) or pixels > request['max_page_pixels']:
                    return {'error': 'pixel_limit'}
                sizes.append({'page': index+1, 'width': width, 'height': height, 'pixels': pixels})
            finally:
                page.close()
        return {'pages': count, 'page_sizes': sizes}
    except Exception:
        return {'error': 'invalid_pdf'}
    finally:
        document.close()


if __name__ == '__main__':
    request = json.load(sys.stdin)
    Path(request['out']).write_text(json.dumps(inspect(request)))
