"""Evaluator-only unchanged historical payload replay; no model calls or producer writes."""
import sys
sys.dont_write_bytecode = True
import collections
import datetime
import hashlib
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE.parent / 'A'))
import producer as p

comparison = json.loads((HERE / 'producer-coverage-comparison.json').read_text())
old = json.loads((p.REPO / 'docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json').read_text())
inventory = json.loads((HERE.parent / 'A/inventory.json').read_text())
by_id = {u['old_unit_id']: u for u in comparison['legacy41']}
source_rows = {s['source']: s for s in inventory['sources']}
protected_ids = [u['source'] + '/' + u['job_id'] for u in old['protected_original_positives']]
join_ids = [u['unit_id'] for u in old['units'] if len(u['physical_pages_1based']) > 1]
units = [u for u in old['units'] if u['unit_id'] in set(protected_ids + join_ids)]
outcomes = []
for u in units:
    match = by_id[u['unit_id']]
    assert len(match['common_eligible_owner_refs']) == 1
    reference = match['common_eligible_owner_refs'][0]
    source = source_rows[u['source']]
    raw = json.loads((p.REPO / source['document_path']).read_text())
    historical_folder = p.REPO / 'docs/research/pdf-core-g2-context-api-2026-10-15/api' / u['source'] / u['job_id']
    payload_path = historical_folder / 'output.json'
    image_path = historical_folder / 'input.png'
    request_path = historical_folder / 'request-description.json'
    payload_bytes = payload_path.read_bytes()
    payload = json.loads(payload_bytes)
    scope = p.bind_scope(raw, [reference])
    inputs = p.legacy.bind_input(scope, image_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
                                image_pixels_wh=list(Image.open(image_path).size),
                                request_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest(),
                                manifest_row_sha256=p.digest(u))
    data = {'targets': [{'target_ref': reference, 'content': payload}]}
    response = p.legacy.bind_response(inputs, data, response_sha256=hashlib.sha256(payload_bytes).hexdigest())
    before = p.digest(raw)
    result = p.apply(raw, scope, inputs, response)
    expected_markdown, expected_offsets = p.legacy.parser.render(payload)
    assert result['proposals'][0]['markdown'] == expected_markdown
    assert result['proposals'][0]['segment_offsets'] == expected_offsets
    assert result['working'].count(expected_markdown) == 1
    assert p.digest(raw) == before
    assert payload_path.read_bytes() == payload_bytes
    folder = HERE / 'saved-payload-replay' / u['source'] / u['job_id']
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'working.md').write_text(result['working'])
    (folder / 'association.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    math = [s['text'] for b in payload['blocks'] for s in b['segments'] if s['kind'] == 'math']
    text = ''.join(s['text'] for b in payload['blocks'] for s in b['segments'])
    checks = {'unchanged_payload': True, 'saved_render_literal_once': True, 'outside_literals_unchanged': True,
              'native_document_unchanged': True,
              'single_logical_paragraph': len(payload['blocks']) == 1 and payload['blocks'][0]['kind'] == 'paragraph'
                                          and '\n\n' not in expected_markdown.strip()}
    # Source meaning checks are separate from successful unchanged-payload transport.
    if u['unit_id'] == 'wikiskill/ordinary_paragraph--texts-363':
        checks['original_six_math_occurrences'] = len(math) == 6
        checks['opening_and_ending_present'] = text.startswith('We determine top-performing methods') and text.endswith('a top-tier statistical tie (and bolded accordingly).')
    elif u['unit_id'] == 'seal/ordinary_paragraph--texts-30':
        checks['original_eleven_math_occurrences'] = len(math) == 11
        checks['source_meaning_scored'] = False
        checks['historical_internal_paragraph_split_retained'] = '\n\n' in expected_markdown.strip()
    elif u['unit_id'] == 'wikiskill/ordinary_paragraph--texts-362':
        checks['opening_source_sentence_present'] = 'Statistical significance testing' in text and 'We perform paired bootstrap significance tests' in text
    elif u['unit_id'] == 'dgm/ordinary_paragraph--texts-648':
        checks['plain_text_or_code_token_strings_preserved'] = all(t in text for t in ['edit', 'edit_type', 'edit_actions', 'str_replace', '23.3%', '40.5%'])
    outcomes.append({'old_unit_id': u['unit_id'], 'current_target_ref': reference,
                     'protected_positive': u['unit_id'] in protected_ids, 'crosspage_join': u['unit_id'] in join_ids,
                     'original_physical_pages': u['physical_pages_1based'],
                     'current_source_pages': sorted({f['physical_page_1based'] for e in scope['entries'] for f in e['fragments']}),
                     'payload_path': str(payload_path), 'payload_sha256': hashlib.sha256(payload_bytes).hexdigest(),
                     'checks': checks, 'saved_math_segment_count': len(math),
                     'new_model_quality': 'not assessed', 'source_semantic_acceptance': False,
                     'limit': 'Historical payload retained unchanged in evaluator-only wrapper with current S0 ownership. Successful transport does not correct a historically bad answer or establish source completeness.'})

summary = {'format': 'evaluator-saved-payload-replay-v1',
           'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'producer_inventory_sha256': comparison['producer_inventory_sha256'],
           'outcomes': outcomes, 'protected_positives_transport_pass': sum(o['protected_positive'] for o in outcomes),
           'crosspage_joins_transport_pass': sum(o['crosspage_join'] for o in outcomes),
           'unique_saved_payloads_replayed': len(outcomes), 'inference_calls': 0,
           'source_semantic_gate_pass': False,
           'limit': 'All artifacts evaluator-only; no oracle-derived jobs or corrected strings sent to producer. Saved response quality remains independent of representation transport.'}
(HERE / 'saved-payload-replay.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print({k: v for k, v in summary.items() if k not in ['outcomes']})
for o in outcomes:
    print(o['old_unit_id'], o['checks'])
