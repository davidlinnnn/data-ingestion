"""Test-only source role mapping. No dependency on candidate derivation output."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def coverage(entries):
    return Counter((s['ref'], s['page'], n) for s in entries for n in range(*s['range']))


def source_order(parts):
    """Read rows top-to-bottom, grouping sub-point baseline variation, then left-to-right."""
    rows = []
    for part in sorted(parts, key=lambda s: s['box'][1]):
        if not rows or part['box'][1] - rows[-1][0]['box'][1] > 2:
            rows.append([part])
        else:
            rows[-1].append(part)
    return [s for row in rows for s in sorted(row, key=lambda s: s['box'][0])]


def expected_roles(reviewed, transcript):
    """Map a frozen native header line to exact parsed source-span character indices."""
    specification = next(c for c in json.loads((ROOT/'p2/header-oracle.json').read_text())
                         if c['page'] == transcript['processed_page'])
    raw = transcript['source_native_text']
    assert hashlib.sha256(raw.encode()).hexdigest() == specification['source_transcript_sha256']
    header = ''.join(raw.splitlines()[specification['source_header_line']].split())
    assert hashlib.sha256(header.encode()).hexdigest() == specification['header_whitespace_compacted_sha256']
    ordered = source_order(reviewed)
    # Source-reviewed combining marks are separate uncertain fragments, never header/body.
    symbols = [s for s in ordered if s['text'] == '\u0338']
    ordinary = [s for s in ordered if s['text'] != '\u0338']
    remaining = header
    headers = []
    for segment in ordinary:
        if not remaining:
            break
        nonspace = [(i, c) for i, c in enumerate(segment['text']) if not c.isspace()]
        take = min(len(nonspace), len(remaining))
        if ''.join(c for _, c in nonspace[:take]) != remaining[:take]:
            return None  # No mapped exact header; do not infer a replacement.
        remaining = remaining[take:]
        end = len(segment['text']) if remaining else nonspace[take-1][0]+1
        headers.append(dict(segment, range=[segment['range'][0], segment['range'][0]+end]))
    if remaining or not headers:
        return None
    return {'header': coverage(headers), 'body': coverage(ordinary)-coverage(headers),
            'symbols': coverage(symbols)}


def roles_and_order(relation, expected):
    if expected is None:
        return False, False
    members = relation['members']
    roles = [m.get('role') for m in members]
    rank = {'header': 0, 'body': 1, 'caption': 2}
    role_shape = all(r in rank for r in roles) and all(r in roles for r in rank)
    if role_shape:
        role_shape = [rank[r] for r in roles] == sorted(rank[r] for r in roles)
    exact_roles = role_shape and all(coverage([m for m in members if m.get('role') == role]) == expected[role]
                                     for role in ('header', 'body'))
    symbols = relation.get('symbol_uncertainty', [])
    exact_roles = exact_roles and coverage(symbols) == expected['symbols'] and all(
        m.get('role') == 'unplaced_combining_mark' and 'order' in m and m['order'] is None for m in symbols)
    order_ok = all(type(m.get('order')) is int and m['order'] == i for i,m in enumerate(members))
    return exact_roles, order_ok
