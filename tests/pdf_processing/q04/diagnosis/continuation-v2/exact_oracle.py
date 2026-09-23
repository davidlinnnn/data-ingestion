"""Fixture-local exact graph gate; no split normalization at runtime."""

import hashlib
import json

from consumer import canonical, graph_projection


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check(fixture, document, source_bytes, reference_bytes, method, manifest):
    if manifest.get('status') not in ('REVIEWED_EXACT_V2', 'REVIEWED_EXACT_V3') or fixture not in ('native', '06'):
        raise ValueError('unreviewed exact oracle')
    expected = manifest['fixtures'][fixture]
    if (digest(source_bytes) != expected['source_pdf_sha256']
            or digest(reference_bytes) != expected['historical_reference_sha256']
            or method.get('continuation') != manifest['continuation']):
        raise ValueError('exact oracle input or method changed')
    graph_sha = digest(canonical(graph_projection(document)).encode())
    if graph_sha != expected['exact_graph_sha256']:
        raise ValueError('unreviewed exact graph delta')
    return graph_sha
