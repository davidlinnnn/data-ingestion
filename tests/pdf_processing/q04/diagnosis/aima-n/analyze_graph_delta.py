"""Inactive AIMA image-supplement review; never promotes runtime acceptance."""
import argparse
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import sys

import pypdfium2
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from consumer import canonical, graph_projection

REFERENCE_SHA = "7fb90a662e77789c0827a02e17d364718ea76f79e96718ff750a2883e227e92c"
SOURCE_SHA = "b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compare(document, reference, source):
    """Check every added image against fixed source pixels, all other fields exactly."""
    if sha(source.read_bytes()) != SOURCE_SHA:
        raise ValueError("fixed AIMA source changed")
    projected = graph_projection(document)
    expected = graph_projection(reference)
    normalized = copy.deepcopy(projected)
    if len(projected['pictures']) != 9 or set(projected['pages']) != {str(i) for i in range(1, 13)}:
        raise ValueError("AIMA image inventory changed")
    for key in normalized['pages']:
        if 'image' in expected['pages'][key]:
            raise ValueError("reference already contains page image")
        normalized['pages'][key].pop('image', None)
    for new, old in zip(normalized['pictures'], expected['pictures']):
        if 'image' in old:
            raise ValueError("reference already contains picture image")
        new.pop('image', None)
    if normalized != expected:
        raise ValueError("non-image graph delta")
    records = []

    def image_check(value, pixels, path):
        if set(value) != {'mimetype', 'dpi', 'size', 'uri'} or value['mimetype'] != 'image/png' or value['dpi'] != 72:
            raise ValueError("image metadata changed: " + path)
        if value['size'] != dict(zip(('width', 'height'), pixels.size)):
            raise ValueError("image dimensions changed: " + path)
        prefix = 'data:image/png;base64,'
        if not value['uri'].startswith(prefix):
            raise ValueError("image encoding changed: " + path)
        raw = base64.b64decode(value['uri'][len(prefix):], validate=True)
        with Image.open(io.BytesIO(raw)) as actual:
            actual.load()
            if actual.format != 'PNG' or actual.mode != pixels.mode or actual.size != pixels.size or actual.tobytes() != pixels.tobytes():
                raise ValueError("image pixels changed: " + path)
        records.append({'path': path, 'encoded_sha256': sha(raw), 'pixel_sha256': sha(pixels.tobytes()), 'dimensions': list(pixels.size), 'source_pixels_equal': True})

    pages = {}
    with pypdfium2.PdfDocument(source) as pdf:
        for key, page in projected['pages'].items():
            # Match the documented backend's 1.5x render then native-size resize.
            source_page = pdf[int(key)-1]
            bitmap = source_page.render(scale=1.5)
            try:
                pixels = bitmap.to_pil().copy().resize(tuple(round(x) for x in source_page.get_size()))
            finally:
                bitmap.close()
                source_page.close()
            image_check(page['image'], pixels, '/pages/'+key+'/image')
            pages[int(key)] = pixels
    for index, picture in enumerate(projected['pictures']):
        prov, = picture['prov']
        box = prov['bbox']
        height = projected['pages'][str(prov['page_no'])]['size']['height']
        if box['coord_origin'] != 'BOTTOMLEFT':
            raise ValueError("fixed picture coordinate origin changed")
        crop = pages[prov['page_no']].crop((box['l'], height-box['t'], box['r'], height-box['b']))
        image_check(picture['image'], crop, f'/pictures/{index}/image')
    return {'status': 'SOURCE_IMAGE_SUPPLEMENT_VERIFIED_NOT_ACCEPTED',
            'non_image_graph_equal': True, 'image_count': len(records), 'images': records,
            'original_graph_sha256': sha(canonical(expected).encode()),
            'actual_graph_sha256': sha(canonical(projected).encode()),
            'runtime_acceptance': False, 'requires_explicit_adoption': True}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('document', 'reference', 'source', 'out'):
        cli.add_argument('--'+name, type=Path, required=True)
    args = cli.parse_args()
    raw = args.reference.read_bytes()
    if sha(raw) != REFERENCE_SHA:
        raise ValueError('fixed Q01 reference changed')
    report = compare(json.loads(args.document.read_text()), json.loads(raw), args.source)
    with args.out.open('x') as stream:
        stream.write(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
