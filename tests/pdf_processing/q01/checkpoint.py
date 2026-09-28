"""Source-pinned regression, with private documents written only to a fresh directory."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from assemble import assemble
from replay import load


def source_content(document):
    # Keep even pre-existing invalid ranges visible; never normalize source text.
    return Counter((item['label'], prov['page_no'], json.dumps(prov['bbox'], sort_keys=True),
                    prov['charspan'][1]-prov['charspan'][0],
                    item['text'][slice(*prov['charspan'])])
                   for item in document['texts'] for prov in item['prov'])


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=False)
    before, old = assemble(False)
    after, new = assemble(True)
    refs = {str(e.cid): e.ref.cref for e in load()}
    def edges(mapping):
        return {(refs[k], refs[str(v)]) for k, values in mapping.items() for v in values}
    removed, added = edges(old)-edges(new), edges(new)-edges(old)
    assert removed == {('#/3/0', '#/4/14'), ('#/4/2', '#/5/10'),
                       ('#/5/0', '#/6/14'), ('#/8/4', '#/9/11')}
    assert added == {('#/5/0', '#/6/6')}
    assert source_content(before) == source_content(after)
    # Tables/images retain their payloads; reference renumbering is expected.
    def payload(value, document):
        if isinstance(value, dict):
            if 'cref' in value:
                _, collection, index = value['cref'].split('/')
                target = document[collection][int(index)]
                return {k: target[k] for k in ('label', 'text', 'prov') if k in target}
            return {k: payload(v, document) for k, v in value.items()
                    if k not in ('self_ref', '$ref', 'parent', 'children')}
        if isinstance(value, list):
            return [payload(v, document) for v in value]
        return value
    for key in ('tables', 'pictures', 'pages'):
        assert payload(before[key], before) == payload(after[key], after), key
    hashes = {}
    for name, document in [('baseline', before), ('corrected', after)]:
        raw = json.dumps(document, indent=2).encode()
        (out/(name+'.json')).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    summary = {'scope': 'checkpoint assembly only; no runtime acceptance',
               'removed': sorted(removed), 'added': sorted(added),
               'text_type_source_regions_equal': True, 'table_picture_page_payloads_equal': True,
               'full_graph_qualified': False, 'private_directory': str(out), 'sha256': hashes}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
