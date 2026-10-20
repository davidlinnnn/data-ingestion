"""Read-only raw Docling JSON mapper. No Docling/model dependency, no inference."""
import collections
import hashlib
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
R3 = ROOT.parent.parent / 'pdf-core-w2-native-coverage-round3-2026-10-20'


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def visible(text):
    # Preserve undecoded glyph evidence rather than silently delete control characters.
    return ''.join(f'\\u{ord(c):04x}' if ord(c) < 32 and c not in '\n\t' else c for c in text.replace('\r\n', '\n'))


def ref_of(ref):
    if isinstance(ref, str):
        return ref
    return ref.get('$ref', ref.get('cref'))


def table_layout(cells, rows, cols):
    occupied={}; issues=[]
    for cell in cells:
        r,c=cell.get('start_row_offset_idx',0),cell.get('start_col_offset_idx',0)
        rs,cs=cell.get('row_span',1),cell.get('col_span',1)
        if min(r,c)<0 or min(rs,cs)<1:
            issues.append({'ref':cell['source_ref'],'type':'invalid_span_or_offset'})
            continue
        for y in range(r,r+rs):
            for x in range(c,c+cs):
                if (y,x)in occupied:
                    issues.append({'ref':cell['source_ref'],'other':occupied[y,x],'position':[y,x],'type':'overlapping_native_cells'})
                occupied[y,x]=cell['source_ref']
    nr=max(rows,max((r for r,c in occupied),default=-1)+1)
    nc=max(cols,max((c for r,c in occupied),default=-1)+1)
    return {'render':'atomic_cell_list' if issues else 'spanned_grid_with_empty_placeholders','issues':issues,'rows':nr,'cols':nc,'unrepresented_grid_positions':nr*nc-len(occupied)}


def map_document(doc):
    index = {doc[k]['self_ref']: doc[k] for k in ('body', 'furniture')}
    for key in ('texts', 'groups', 'pictures', 'tables', 'key_value_items', 'form_items'):
        for item in doc.get(key, []):
            assert item['self_ref'] not in index
            index[item['self_ref']] = item
    seen, aliases, missing = set(), [], []
    units, events = [], []

    def visit(ref, ancestors=(), section='body', picture=None):
        ref = ref_of(ref)
        if ref in seen:
            aliases.append({'ref': ref, 'via': list(ancestors)})
            return None
        if ref not in index:
            missing.append(ref)
            return None
        seen.add(ref)
        item = index[ref]
        role = item.get('label', 'root')
        if item.get('content_layer') == 'furniture' or role in ('page_header', 'page_footer'):
            section = 'furniture'
        node = {k: item[k] for k in ('self_ref', 'parent', 'label', 'content_layer', 'prov', 'level', 'marker', 'enumerated', 'name', 'text', 'orig') if k in item}
        node.update(section=section, ancestors=list(ancestors), children=[])
        if ref.startswith('#/pictures/'):
            picture = ref
            node.update(kind='picture', native_text_channel='picture_native_uncertain', image_supplement={'channel': 'C_image_supplement', 'status': 'NOT_EXECUTED', 'reason': 'No image/OCR/VLM inference in this prototype.'})
        elif ref.startswith('#/tables/'):
            node['kind'] = 'table'
            node['cells'] = []
            for i, cell in enumerate(item.get('data', {}).get('table_cells', [])):
                mapped = dict(cell, source_ref=f'{ref}/data/table_cells/{i}')
                node['cells'].append(mapped)
                units.append({'ref': mapped['source_ref'], 'channel': 'picture_native_uncertain' if picture else section, 'text': cell.get('text', ''), 'source': 'table_cell'})
            node['num_rows'] = item.get('data', {}).get('num_rows', 0)
            node['num_cols'] = item.get('data', {}).get('num_cols', 0)
            node['layout_check'] = table_layout(node['cells'],node['num_rows'],node['num_cols'])
            node['span_policy'] = 'one_native_cell_once; row_span/col_span retained; no grid expansion'
            events.append({'type': 'table_single_cell_mapping', 'ref': ref, 'cells': len(node['cells']), 'merged_cells': sum(c.get('row_span',1)>1 or c.get('col_span',1)>1 for c in node['cells'])})
        elif ref.startswith('#/texts/'):
            text, orig = item.get('text', ''), item.get('orig', '')
            fallback = not text.strip() and bool(orig.strip())
            node.update(kind='text', delivered_text=orig if fallback else text, text_source='orig' if fallback else 'text', role_uncertain=fallback, channel='picture_native_uncertain' if picture else section)
            if fallback:
                events.append({'type': 'empty_text_orig_fallback', 'ref': ref, 'pages': [p['page_no'] for p in item.get('prov', [])], 'original_label': role, 'control_chars': sorted({ord(c) for c in orig if ord(c)<32 and c not in '\r\n\t'})})
            if picture:
                node['picture_ref'] = picture
            units.append({'ref': ref, 'channel': node['channel'], 'text': node['delivered_text'], 'source': node['text_source']})
        else:
            node['kind'] = 'group'
        # Children carry native order. Caption/footnote aliases are visited once only.
        for child in [*item.get('children', []), *item.get('captions', []), *item.get('footnotes', [])]:
            mapped = visit(child, (*ancestors, ref), section, picture)
            if mapped is not None:
                node['children'].append(mapped)
        return node

    body = visit('#/body')
    furniture = visit('#/furniture', section='furniture')
    unlinked = []
    for ref in index:
        if ref not in seen:
            mapped = visit(ref, section='unlinked_uncertain')
            if mapped is not None:
                unlinked.append(mapped)
    assert not missing, missing
    counts = collections.Counter(u['ref'] for u in units)
    assert all(v == 1 for v in counts.values()), counts
    expected = {x['self_ref'] for x in doc.get('texts', [])}
    expected |= {f"{t['self_ref']}/data/table_cells/{i}" for t in doc.get('tables', []) for i, _ in enumerate(t.get('data', {}).get('table_cells', []))}
    assert set(counts) == expected, sorted(expected-set(counts))
    value_counts = collections.Counter(u['text'] for u in units if u['text'].strip())
    source_repeated_values = [{'text_sha256': hashlib.sha256(k.encode()).hexdigest(), 'units': v, 'refs': [u['ref'] for u in units if u['text'] == k]} for k,v in value_counts.items() if v > 1]
    result = {'schema': 'w2-raw-native-mapper-v1', 'name': doc.get('name'), 'body': body, 'furniture': furniture, 'unlinked': unlinked, 'events': events, 'units': units}
    result['selfcheck'] = {'source_text_items': len(doc.get('texts', [])), 'source_table_cells': len(expected)-len(doc.get('texts', [])), 'delivered_units': len(units), 'new_duplicate_item_refs': 0, 'new_duplicate_cell_refs': 0, 'all_source_units_delivered_once': True, 'missing_refs': missing, 'revisited_aliases_suppressed': aliases, 'unlinked_roots': len(unlinked), 'source_repeated_values_retained': source_repeated_values, 'ordering': 'native children order; no reorder or sentence/formula correctness claim', 'native_parent_links_preserved': True}
    return result


def render_node(node, include_furniture=False):
    if node['section'] == 'furniture' and not include_furniture:
        return ''
    ref = html.escape(node['self_ref'], quote=True)
    role = html.escape(node.get('label', 'root'), quote=True)
    attrs = f'data-source-ref="{ref}" data-role="{role}" data-section="{node["section"]}"'
    children = ''.join(render_node(c, include_furniture) for c in node['children'])
    if node['kind'] == 'text':
        value = node['delivered_text']
        marker = node.get('marker', '')
        if node.get('label') == 'list_item' and marker and not value.lstrip().startswith(marker):
            value = marker + ' ' + value
        value = html.escape(visible(value))
        attrs += f' data-text-source="{node["text_source"]}" data-channel="{node["channel"]}"'
        if node.get('label') == 'list_item':
            attrs += f' data-marker="{html.escape(marker, quote=True)}" data-enumerated="{str(node.get("enumerated",False)).lower()}"'
        if node.get('role_uncertain'):
            return f'<aside {attrs} class="role-uncertain"><b>ROLE_UNCERTAIN: raw orig fallback; formula/role unverified</b><pre>{value}</pre>{children}</aside>\n'
        tag = 'pre' if node.get('label') == 'code' else 'p'
        if node.get('label') == 'section_header':
            tag = f'h{max(1,min(6,node.get("level",1)))}'
        return f'<{tag} {attrs}>{value}</{tag}>\n{children}'
    if node['kind'] == 'picture':
        return f'<section {attrs} class="picture-native"><h6>Picture native text (uncertain; separate from body and C image supplement)</h6><div data-channel="picture_native_uncertain">{children}</div><aside data-channel="C_image_supplement">NOT_EXECUTED — image supplement unavailable; native strings do not describe all visual content.</aside></section>\n'
    if node['kind'] == 'table':
        # Never invent a column relation when native cells already overlap.
        layout=node['layout_check']
        if layout['issues']:
            values=[]
            for cell in node['cells']:
                position=f'row={cell.get("start_row_offset_idx",0)}, col={cell.get("start_col_offset_idx",0)}, rowspan={cell.get("row_span",1)}, colspan={cell.get("col_span",1)}'
                values.append(f'<div data-source-ref="{html.escape(cell["source_ref"])}"><small>{position}</small><pre>{html.escape(visible(cell.get("text","")))}</pre></div>')
            return f'<section {attrs}><b>TABLE_LAYOUT_UNCERTAIN: overlapping/invalid native cells; one cell once, source coordinates retained.</b>'+''.join(values)+children+'</section>\n'
        starts={(c.get('start_row_offset_idx',0),c.get('start_col_offset_idx',0)):c for c in node['cells']}
        covered={(r,c)for cell in node['cells'] for r in range(cell.get('start_row_offset_idx',0),cell.get('start_row_offset_idx',0)+cell.get('row_span',1))for c in range(cell.get('start_col_offset_idx',0),cell.get('start_col_offset_idx',0)+cell.get('col_span',1))}
        table = []
        for row in range(layout['rows']):
            rendered = []
            for col in range(layout['cols']):
                cell=starts.get((row,col))
                if cell is None:
                    if (row,col)not in covered:
                        rendered.append('<td aria-hidden="true" data-empty-grid-position="true"></td>')
                    continue
                tag = 'th' if cell.get('column_header') or cell.get('row_header') else 'td'
                value = html.escape(visible(cell.get('text', '')))
                rendered.append(f'<{tag} data-source-ref="{html.escape(cell["source_ref"])}" data-row="{row}" data-col="{cell.get("start_col_offset_idx",0)}" rowspan="{max(1,cell.get("row_span",1))}" colspan="{max(1,cell.get("col_span",1))}">{value}</{tag}>')
            table.append('<tr>'+''.join(rendered)+'</tr>')
        return f'<section {attrs}><table>'+''.join(table)+'</table>'+children+'</section>\n'
    return f'<section {attrs}>{children}</section>\n'


def render(mapped):
    # Raw HTML blocks are intentional CommonMark content: spans/uncertainty are expressible.
    body = render_node(mapped['body'])
    def furniture_roots(node):
        if node['section'] == 'furniture':
            return [node]
        return [found for child in node['children'] for found in furniture_roots(child)]
    furniture = ''.join(render_node(n, True) for tree in [mapped['body'], mapped['furniture'], *mapped['unlinked']] for n in furniture_roots(tree))
    unlinked = ''.join(render_node(n) for n in mapped['unlinked'])
    content = '<main>'+body+'</main><hr><section class="furniture"><h2>Furniture (separate channel)</h2>'+furniture+'</section>'
    if unlinked:
        content += '<section class="unlinked"><h2>Unlinked native items (uncertain)</h2>'+unlinked+'</section>'
    return '<!doctype html><meta charset="utf-8"><title>Native mapper prototype</title><style>body{font-family:sans-serif;max-width:1000px;margin:auto}pre{white-space:pre-wrap}td,th{border:1px solid #aaa;padding:.4em}table{border-collapse:collapse}.picture-native,.role-uncertain,.furniture,.unlinked{border:2px solid #aaa;padding:1em;margin:1em 0}.picture-native{background:#eef6ff}.role-uncertain{background:#fff3db}</style>'+content, content


def selfcheck():
    def text(i, parent, value, **extra):
        return dict(self_ref=f'#/texts/{i}', parent={'$ref':parent}, children=[], label='text', text=value,orig=value, **extra)
    doc = {'name':'synthetic','body':{'self_ref':'#/body','children':[{'$ref':'#/texts/0'},{'$ref':'#/pictures/0'},{'$ref':'#/tables/0'}]},'furniture':{'self_ref':'#/furniture','children':[]},'texts':[text(0,'#/body',''),text(1,'#/pictures/0','payload'),text(2,'#/pictures/0','caption')], 'pictures':[{'self_ref':'#/pictures/0','label':'picture','children':[{'$ref':'#/texts/1'},{'$ref':'#/texts/2'}],'captions':[{'$ref':'#/texts/2'}]}], 'tables':[{'self_ref':'#/tables/0','label':'table','children':[],'data':{'num_rows':1,'num_cols':2,'table_cells':[{'text':'unique merged content','row_span':1,'col_span':2,'start_row_offset_idx':0,'start_col_offset_idx':0}]}}]}
    doc['texts'][0].update(orig='no\x02negation',label='formula')
    out = map_document(doc)
    h,md=render(out)
    assert out['body']['children'][0]['role_uncertain']
    assert h.count('unique merged content') == 1 and 'colspan="2"' in h
    assert h.count('>payload<') == 1 and h.count('>caption<') == 1
    assert '\\u0002' in h and '\x02' not in h
    assert out['selfcheck']['new_duplicate_item_refs'] == 0
    alias_doc=json.loads(json.dumps(doc).replace('"$ref":', '"cref":'))
    assert render(map_document(alias_doc)) == (h, md)
    assert 'data-section="furniture"' not in h.split('<main>')[1].split('</main>')[0]
    overlap=json.loads(json.dumps(doc))
    overlap['tables'][0]['data']['table_cells'].append(dict(overlap['tables'][0]['data']['table_cells'][0],text='overlap second value'))
    mapped=map_document(overlap);rendered,_=render(mapped)
    assert 'TABLE_LAYOUT_UNCERTAIN' in rendered and rendered.count('overlap second value')==1
    assert rendered.count('unique merged content')==1
    footer=text(3,'#/body','99',content_layer='furniture')
    footer['label']='page_footer'
    overlap['texts'].append(footer);overlap['body']['children'].append({'$ref':'#/texts/3'})
    rendered,_=render(map_document(overlap))
    assert 'data-section="furniture"' not in rendered.split('<main>')[1].split('</main>')[0]
    assert rendered.count('data-source-ref="#/texts/3"')==1
    return {'synthetic_fallback_controlchar_picture_caption_alias_merged_span': 'PASS', 'canonical_dollar_ref_and_modeldump_cref_equivalence':'PASS','overlapping_native_cells_do_not_create_false_spanned_grid':'PASS','furniture_under_source_body_routed_separately_once':'PASS'}


def main():
    checks=selfcheck()
    inputs=json.loads((R3/'baseline-inputs.json').read_text())
    summaries=[]
    for job_id, source in inputs.items():
        path=pathlib.Path(source)/'document.json'
        raw=path.read_bytes()
        mapped=map_document(json.loads(raw))
        mapped['input']={'job_id':job_id,'path':str(path),'sha256':hashlib.sha256(raw).hexdigest()}
        dest=ROOT/'outputs'/job_id
        dest.mkdir(parents=True,exist_ok=True)
        save(dest/'mapped.json',mapped)
        h,md=render(mapped)
        (dest/'document.html').write_text(h)
        (dest/'document.md').write_text(md)
        refs=re.findall(r'data-source-ref="([^"]+)"', h)
        rendered=collections.Counter(html.unescape(r) for r in refs)
        assert all(n==1 for n in rendered.values()), {r:n for r,n in rendered.items() if n>1}
        assert all(rendered[u['ref']]==1 for u in mapped['units'])
        summary={'id':job_id,'input':mapped['input'],'counts':dict(collections.Counter(e['type'] for e in mapped['events'])),'fallbacks':sum(e['type']=='empty_text_orig_fallback' for e in mapped['events']),'picture_native_units':sum(u['channel']=='picture_native_uncertain' for u in mapped['units']),'picture_native_characters':sum(len(u['text']) for u in mapped['units'] if u['channel']=='picture_native_uncertain'),'merged_cells':sum(e.get('merged_cells',0) for e in mapped['events']),'selfcheck':mapped['selfcheck'],'render_source_ref_multiplicity': 'exactly once for every native text/cell'}
        save(dest/'counts.json',summary)
        summaries.append(summary)
    save(ROOT/'counts.json',{'documents':len(summaries),'fallback_items':sum(x['fallbacks'] for x in summaries),'picture_native_units':sum(x['picture_native_units'] for x in summaries),'merged_cells':sum(x['merged_cells'] for x in summaries),'new_duplicate_item_refs':0,'new_duplicate_cell_refs':0,'jobs':summaries})
    save(ROOT/'selfcheck.json',dict(checks,documents=len(summaries),source_hashes_verified_unchanged=all(hashlib.sha256(pathlib.Path(s['input']['path']).read_bytes()).hexdigest()==s['input']['sha256'] for s in summaries),all_source_native_text_cells_once=True,render_refs_once=True))
    print(json.dumps({'documents':len(summaries),'fallbacks':sum(x['fallbacks'] for x in summaries),'picture_native_units':sum(x['picture_native_units'] for x in summaries),'merged_cells':sum(x['merged_cells'] for x in summaries)}))


if __name__ == '__main__':
    main()
