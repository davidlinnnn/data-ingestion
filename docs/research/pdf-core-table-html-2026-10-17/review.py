"""Review semantic delivery after the fixed synthetic run; never alters its outputs."""
import hashlib
import json
from pathlib import Path

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

HERE=Path(__file__).resolve().parent


def main():
    registration=json.loads((HERE/'registration.json').read_text())
    assert hashlib.sha256((HERE/'probe.py').read_bytes()).hexdigest()==registration['runner_sha256']
    for path,digest in registration['source_hashes'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
    md=(HERE/'escaped_literal/document.md').read_text()
    parser=MarkdownIt('commonmark',{'html':True}).enable('table')
    rendered=parser.render(md);(HERE/'escaped_literal/rendered-commonmark.html').write_text(rendered)
    soup=BeautifulSoup(rendered,'html.parser')
    cells=[c.get_text() for c in soup.select('tbody td')]
    assert cells==['','item[i] < limit & ready']
    with_html_disabled=MarkdownIt('commonmark',{'html':False}).enable('table').render(md)
    (HERE/'escaped_literal/rendered-html-disabled.html').write_text(with_html_disabled)
    assert [c.get_text() for c in BeautifulSoup(with_html_disabled,'html.parser').select('tbody td')]==['<s>','item[i] < limit & ready']
    report={'status':'A gate failed; B intentionally not started','api_requests':0,'new_model_inferences':0,
        'mechanical_checks':{'public_HTML_import':True,'public_PDF_envelope_rebinding':True,'JSON_reload':True,'stock_Markdown_reload':True},
        'material_findings':[
            {'case':'row_groups','finding':'First source row group promoted into global metric headers; second group remains body text under contradictory first-group header',
             'typed_flags':'column_header=True and row_section=False; diagnostic, not a standalone requirement for a specific label',
             'markdown_header':'Category - By Device | Count - By Device'},
            {'case':'escaped_literal','finding':'HTML input escaped correctly and typed cell contains <s>, but stock Markdown emits raw <s>; CommonMark with HTML enabled consumes it as a tag',
             'rendered_cell_texts':cells,'scope':'reference CommonMark renderer; not an observation of Codex UI or every consumer',
             'html_disabled_preserves_literal':True}],
        'minor_findings':[{'case':'blank_missing_precision','finding':'Native HTML unicode cleanup maps em dash to hyphen. Blank, missing marker and zero remain distinct; precision000.00 retained.',
                           'classification':'glyph normalization; not equivalent to losing the missing value and not the independent material stop reason'}],
        'negative_controls':'unescaped literal and zero-span input both return native success; preserved as invalid/normalized inputs, not positive fidelity results',
        'not_executed':['HTML target-envelope implementation/validation beyond importer gate','four-page API run','two additional S0 pages','source oracle evaluation','holdout/Paddle/company serving'],
        'decision':'Stop this stock HTML→TableData→Markdown configuration under the agreed gate. Do not patch SDK, repair content, or add a renderer during this round.'}
    (HERE/'decision.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'rendered_literal_cells':cells,'HTML_disabled_retains_literal':True,'row_group_material_stop':True},ensure_ascii=False))


if __name__=='__main__':main()
