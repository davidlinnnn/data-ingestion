"""Research control for documented public serializer injection; no model or paper."""
import hashlib
import html
import json
from pathlib import Path

from docling_core.transforms.serializer.markdown import MarkdownDocSerializer, MarkdownTableSerializer
from docling_core.types.doc import DocItemLabel, DoclingDocument, RichTableCell, TableCell, TableData
from markdown_it import MarkdownIt

HERE=Path(__file__).resolve().parent


class EscapedTableSerializer(MarkdownTableSerializer):
    """Escape display copies only; source strings and typed structure stay intact."""

    def serialize(self, *, item, doc_serializer, **kwargs):
        display=item.model_copy(deep=True)
        for cell in display.data.table_cells:
            if not isinstance(cell,RichTableCell):
                cell.text=html.escape(cell.text,quote=False)
        result=super().serialize(item=display,doc_serializer=doc_serializer,**kwargs)
        for span in result.spans:
            if span.item.self_ref==item.self_ref:
                span.item=item
        return result


def cell(text,row,col,*,width=1,header=False,section=False):
    return TableCell(text=text,start_row_offset_idx=row,end_row_offset_idx=row+1,
        start_col_offset_idx=col,end_col_offset_idx=col+width,col_span=width,
        column_header=header,row_section=section)


def rendered_cells(md):
    parser=MarkdownIt('commonmark',{'html':True}).enable('table')
    # Parse the reference renderer's tokens so literal text is distinguished from HTML tags.
    groups=[];current=None
    for token in parser.parse(md):
        if token.type in ('th_open','td_open'): current=[]
        elif token.type=='inline' and current is not None:
            current.extend(t.content for t in token.children or [] if t.type in ('text','code_inline'))
        elif token.type in ('th_close','td_close'):
            groups.append(''.join(current));current=None
    return groups,parser.render(md)


def main():
    doc=DoclingDocument(name='public table serializer research control')
    doc.add_text(label=DocItemLabel.TEXT,text='Before the table')
    table=doc.add_table(data=TableData(num_rows=5,num_cols=2,table_cells=[
        cell('Category',0,0,header=True),cell('Value',0,1,header=True),
        cell('By device',1,0,width=2,section=True),cell('Desktop',2,0),cell('001.20',2,1),
        cell('By token',3,0,width=2,section=True),cell('<s>',4,0),cell('&lt;s&gt; & x < 7 | y',4,1)]))
    caption=doc.add_text(label=DocItemLabel.CAPTION,text='Synthetic source caption',parent=table)
    table.captions.append(caption.get_ref())
    doc.add_text(label=DocItemLabel.TEXT,text='After the table')
    source=doc.model_dump_json();baseline=doc.export_to_markdown()
    result=MarkdownDocSerializer(doc=doc,table_serializer=EscapedTableSerializer()).serialize()
    actual=result.text
    assert doc.model_dump_json()==source
    for item in result.get_unique_doc_items():
        assert item.model_dump_json()==item.get_ref().resolve(doc).model_dump_json()
    assert actual.count('Synthetic source caption')==1
    assert actual.index('Before the table')<actual.index('Synthetic source caption')<actual.index('After the table')
    assert '| Category' in actual and 'Category - By device' not in actual
    cells,rendered=rendered_cells(actual)
    assert '<s>' in cells and '&lt;s&gt; & x < 7 | y' in cells and '001.20' in cells
    _,native_rendered=rendered_cells(baseline)
    assert '<td><s></td>' in native_rendered
    assert doc.tables[0].data.table_cells[2].row_section and not doc.tables[0].data.table_cells[2].column_header
    for name,text in [('input.json',doc.model_dump_json(indent=2)),('stock.md',baseline),('extended.md',actual),('extended-rendered.html',rendered)]:
        (HERE/name).write_text(text+'\n')
    report={'status':'small public-API control passes; not full gate or model qualification',
        'direct_typed_row_group_kept_out_of_global_header':True,'rendered_literal_and_entity_text_preserved':True,
        'pipe_and_numeric_precision_preserved':True,'caption_once_and_body_order_preserved':True,
        'canonical_JSON_byte_identical_before_after':True,'model_calls':0,'API_requests':0,'source_paper_reads':0,
        'serializer_source_metadata_matches_original_items':True,
        'SDK_edits':0,'public_extension_maintained_by_project':True,'rich_cells_or_full_document_regressions_tested':False,
        'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
