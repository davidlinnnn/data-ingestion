"""Assert official fixed-version serializer behavior with a synthetic native table."""
import importlib.metadata
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument, TableCell, TableData

ROOT = Path(__file__).resolve().parent
TEXT = 'Only buy black work shoes below $50.00, size 10.'


def main():
    doc = DoclingDocument(name='Synthetic colspan delivery check')
    cells = [
        TableCell(text='Header A', row_span=1, col_span=1, start_row_offset_idx=0,
                  end_row_offset_idx=1, start_col_offset_idx=0, end_col_offset_idx=1, column_header=True),
        TableCell(text='Header B', row_span=1, col_span=1, start_row_offset_idx=0,
                  end_row_offset_idx=1, start_col_offset_idx=1, end_col_offset_idx=2, column_header=True),
        TableCell(text=TEXT, row_span=1, col_span=2, start_row_offset_idx=1,
                  end_row_offset_idx=2, start_col_offset_idx=0, end_col_offset_idx=2),
    ]
    table = doc.add_table(data=TableData(table_cells=cells, num_rows=2, num_cols=2))
    markdown = doc.export_to_markdown()
    html = doc.export_to_html()
    native_count = sum(c.text.count(TEXT) for c in table.data.table_cells)
    result = {'docling_core_version': importlib.metadata.version('docling-core'),
        'new_model_inferences': 0, 'native_input_cells': len(cells),
        'native_sentence_occurrences': native_count, 'grid_sentence_occurrences':
        sum(c.text.count(TEXT) for row in table.data.grid for c in row),
        'markdown_sentence_occurrences': markdown.count(TEXT),
        'html_sentence_occurrences': html.count(TEXT), 'html_colspan2': 'colspan="2"' in html,
        'routing': '#81 delivery/serialization; synthetic native extraction input is already correct.'}
    assert native_count == 1
    assert result['grid_sentence_occurrences'] == 2
    assert result['markdown_sentence_occurrences'] == 2
    assert result['html_sentence_occurrences'] == 1
    assert result['html_colspan2']
    (ROOT / 'synthetic-colspan-native.json').write_text(doc.model_dump_json(indent=2))
    (ROOT / 'synthetic-colspan.md').write_text(markdown)
    (ROOT / 'synthetic-colspan.html').write_text(html)
    (ROOT / 'synthetic-colspan-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
