"""Frozen source mapping for independent oracle; no runtime imports."""
import hashlib
import json

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def segments(doc):
    result = []
    for item in doc['texts']:
        for prov in item.get('prov', []):
            start, end = prov['charspan']
            valid = 0 <= start <= end <= len(item['text'])
            b = prov['bbox']
            h = doc['pages'][str(prov['page_no'])]['size']['height']
            box = [b['l'], h-b['t'], b['r'], h-b['b']] if b['coord_origin'] == 'BOTTOMLEFT' else [b[k] for k in ('l','t','r','b')]
            result.append({'ref': item['self_ref'], 'page': prov['page_no'], 'range': [start, end],
                           'box': box, 'text': item['text'][start:end] if valid else '', 'actual_type': item['label'], 'valid_range': valid})
    return result

