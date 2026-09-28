"""Reproduce reviewed representation metadata from retained independent sources.

Never imported by production. Does not discover relationships or authorize new
source differences. Full source text remains private; only symbol excerpts persist.
"""
import difflib
import hashlib
import json
from pathlib import Path
from fixtures import document, SOURCE
from oracle.score import CASES, inside
from oracle.source_segments import segments
from oracle.role_oracle import source_order

ROOT = Path(__file__).resolve().parent

def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()

def freeze():
    transcripts = json.loads(Path('/private/tmp/t09a-code-oracle.json').read_text())
    captions = json.loads(Path('/private/tmp/aima-quality-candidate/caption-source.json').read_text())
    parts = segments(document())
    transcript_hashes = json.loads((ROOT.parent/'t09a/evidence/code-source-oracle.json').read_text())
    caption_hashes = json.loads((ROOT.parent/'q02/oracle/caption-oracle.json').read_text())
    reviews = []
    for page, _, _, box, caption_box in CASES:
        streams = {}
        for name, region, source in (
            ('header_body', box, next(t['source_native_text'] for t in transcripts if t['processed_page'] == page)),
            ('caption', caption_box, next(t['source_native_text'] for t in captions if t['page'] == page))):
            selected = source_order([s for s in parts if s['page'] == page and inside(s['box'], region) and s['text'] != '\u0338'])
            extracted = ''.join(''.join(s['text'].split()) for s in selected)
            native = ''.join(source.split())
            if name == 'header_body':
                assert sha(source) == next(t['source_text_sha256'] for t in transcript_hashes if t['processed_page'] == page)
            else:
                assert sha(native) == next(t['whitespace_compacted_sha256'] for t in caption_hashes if t['page'] == page)
            differences = []
            for tag, i, j, k, l in difflib.SequenceMatcher(None, native, extracted, autojunk=False).get_opcodes():
                if tag == 'equal': continue
                pair = (native[i:j], extracted[k:l])
                kind = {('−', '-'): 'minus_hyphen', ('\x07', ''): 'combining_control', ('\x02', ''): 'caption_control'}[pair]
                differences.append({'kind': kind, 'source_range': [i, j], 'extracted_range': [k, l],
                    'source': pair[0], 'extracted': pair[1], 'disposition': 'retain_uninterpreted'})
            streams[name] = {'source_compacted_sha256': sha(native), 'extracted_compacted_sha256': sha(extracted),
                             'differences': differences}
        reviews.append({'id': f'q03-source-review-{page}', 'selection': f'page-{page}', 'page': page,
            'source_sha256': SOURCE, 'reviewer': 'Q03 agent source-image review 2026-09-16',
            'reason': 'Bounded structural delivery with exact extraction and readable source; representation and mathematical equivalence remain unconfirmed.',
            'streams': streams,
            'isolated_symbols': [{'text': '\u0338', 'disposition': 'retain_uninterpreted'}] if page in (9, 10) else []})
    return {'version': 'source-reviewed-representation-v1', 'reviews': reviews}

if __name__ == '__main__':
    (ROOT/'reviewed-representation.json').write_text(json.dumps(freeze(), indent=2, ensure_ascii=True)+'\n')
