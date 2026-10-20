"""Inspect failed PDFs without bitmap decoding, rendering, OCR or conversion."""
import collections
import json
from pathlib import Path
import re

import pypdfium2 as pdfium
import pypdfium2.raw as raw

ROOT = Path(__file__).resolve().parents[1]


def inspect(job):
    doc = pdfium.PdfDocument(job['pdf'])
    rows = []
    try:
        for pn in range(1, len(doc) + 1):
            page = doc[pn - 1]
            tp = page.get_textpage()
            text = tp.get_text_range()
            width, height = page.get_size()
            images = []
            types = collections.Counter()
            for obj in page.get_objects():
                types[obj.type] += 1
                if obj.type == raw.FPDF_PAGEOBJ_IMAGE:
                    try:
                        w, h = obj.get_px_size()
                        images.append({'width': w, 'height': h, 'pixels': w * h})
                    except Exception as exc:
                        images.append({'metadata_error': str(exc)})
            rows.append({'page': pn, 'width_points': width, 'height_points': height,
                         'render_pixels_scale2': width * height * 4,
                         'scale2_rgba_mib': width * height * 4 * 4 / 2**20,
                         'text_characters': len(text), 'pdfium_raw_chars': tp.count_chars(),
                         'page_object_counts': dict(types), 'images': images,
                         'image_pixels_total': sum(i.get('pixels', 0) for i in images),
                         'table_caption_candidates': re.findall(r'(?im)^\s*Table\s+\d+[^\r\n]{0,150}', text),
                         'figure_caption_candidates': re.findall(r'(?im)^\s*Figure\s+\d+[^\r\n]{0,150}', text)})
            tp.close()
            page.close()
    finally:
        doc.close()
    chosen = []
    for key in ('image_pixels_total', 'render_pixels_scale2'):
        for row in sorted(rows, key=lambda p: p[key], reverse=True)[:2]:
            if row['page'] not in chosen:
                chosen.append(row['page'])
    for row in sorted(rows, key=lambda p: (len(p['table_caption_candidates']), sum(p['page_object_counts'].values())), reverse=True):
        if row['page'] not in chosen:
            chosen.append(row['page'])
        if len(chosen) >= 5:
            break
    return {'job': job['id'], 'pdf_sha256': job['pdf_sha256'], 'pages': rows,
            'representative_pages_max5': chosen[:5],
            'stage': 'UNKNOWN',
            'limits': 'Image dimensions obtained with FPDFImageObj_GetImagePixelSize only; no image decoding or rasterization. Table/figure caption strings are candidates, not structural table detection. Document-level RSS stop has no page/stage observation.'}


def main():
    jobs = json.loads((ROOT / 'jobs.json').read_text())['jobs']
    failed = ('P-03-2603.25158v5', 'P-06-2606.14239v2', 'P-10-2509.25140v2',
              'P-16-2505.22954v1', 'P-18-2511.16043v1', 'P-20-2505.03335v1')
    selected = [j for j in jobs if j['id'] in failed]
    output = {'method': 'metadata-only independent PDFium inspection', 'documents': [inspect(j) for j in selected]}
    samples = json.loads((ROOT / 'execution.json').read_text())['samples']
    for document in output['documents']:
        document['metadata_inspected_pages'] = document.pop('representative_pages_max5')
        found = [s for s in samples if s.get('job') == document['job']]
        document['rss_samples'] = {'first_bytes': found[0]['rss'], 'last_bytes': found[-1]['rss'],
                                  'peak_bytes': max(s['rss'] for s in found), 'samples': len(found),
                                  'limit': 'Worker process-tree samples include retained earlier-document state; not isolated per-document allocation.'}
    candidates = sorted(((p['image_pixels_total'], d['job'], p['page'])
                         for d in output['documents'] for p in d['pages']), reverse=True)
    output['representative_pages_for_rss_stop_type_max5'] = [
        {'job': job, 'page': page, 'image_pixels_total': pixels} for pixels, job, page in candidates[:5]]
    (ROOT / 'diagnostics/resource-pdfs.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    for doc in output['documents']:
        print(json.dumps({'job': doc['job'], 'pages': len(doc['pages']),
                          'metadata_inspected_pages': doc['metadata_inspected_pages'],
                          'max_image_pixels': max(p['image_pixels_total'] for p in doc['pages']),
                          'max_page_size': max((p['width_points'], p['height_points']) for p in doc['pages'])}))


if __name__ == '__main__':
    main()
