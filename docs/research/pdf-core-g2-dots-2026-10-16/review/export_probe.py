"""Synthetic native-parser/export regressions; no inference or output repair."""
import json
from pathlib import Path
from importlib.metadata import version
from html.parser import HTMLParser
import marko
from docling.utils.dots_utils import parse_dots_json
from docling_core.types.doc import Size

HERE = Path(__file__).parent
CASES = {
    "inline_math_code": r"For $x_i^2$ use `items[i] <= limit`; retain $\theta'$.",
    "bare_literal_underscores": "Keep __init__ and _TEMP_ literally; ordinary under_score_name.",
    "escaped_literal_underscores": r"Keep \_\_init\_\_ and \_TEMP\_ literally; ordinary under_score_name.",
    "bare_literal_unknown_tag": "Keep <widget> and <sample> literally.",
    "entity_literal_unknown_tag": "Keep &lt;widget&gt; and &lt;sample&gt; literally.",
    "inline_code_unknown_tag": "Use `<widget>` and `a <= b` literally.",
    "inline_code_known_html": "Use `<b>bold</b>` literally; preserve `x_i`.",
    "entity_inline_code_known_html": "Use `&lt;b&gt;bold&lt;/b&gt;` literally; preserve `x_i`.",
    "escaped_known_html": r"Keep \<b\>bold\</b\> literally.",
    "html_with_math": r"<b>Important</b>: keep $x_i^2$ and `a <= b`.",
    "latex_less_than_sequence": r"Preserve $p(y_{<s})$ in this sentence.",
}
class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def visible(s):
    p=Visible();p.feed(s);return ''.join(p.parts).strip()

results=[]
for name, text in CASES.items():
    raw=json.dumps([{"category":"Text","bbox":[10,10,500,50],"text":text}])
    doc=parse_dots_json(raw,original_page_size=Size(width=560,height=840),page_no=1,model_image_size=Size(width=560,height=840))
    exports={"default":doc.export_to_markdown(),"no_underscores":doc.export_to_markdown(escape_underscores=False),"native":doc.export_to_markdown(escape_underscores=False,escape_html=False)}
    results.append({"name":name,"input":text,"native_items":[{"label":x.label.value,"text":x.text,"orig":x.orig} for x in doc.texts],"exports":exports,"commonmark_html":{k:marko.convert(v) for k,v in exports.items()},"commonmark_visible":{k:visible(marko.convert(v)) for k,v in exports.items()}})
lookup={x['name']:x for x in results}
assert lookup['inline_math_code']['exports']['native'].strip()==CASES['inline_math_code']
assert '__init__' in lookup['bare_literal_underscores']['commonmark_visible']['default']
assert '__init__' not in lookup['bare_literal_underscores']['commonmark_visible']['native']
assert '<widget>' in lookup['bare_literal_unknown_tag']['commonmark_visible']['default']
assert '<widget>' not in lookup['bare_literal_unknown_tag']['commonmark_visible']['native']
assert '<widget>' in lookup['entity_literal_unknown_tag']['commonmark_visible']['native']
assert '<widget>' in lookup['inline_code_unknown_tag']['commonmark_visible']['native']
record={"model_calls":0,"custom_output_repairs":0,"scope":"synthetic parser and Markdown renderer only; no formula rendering or source recognition", "packages":{x:version(x) for x in ['docling-slim','docling-core','marko']},"results":results}
(HERE/'export-results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(record,ensure_ascii=False,indent=2))
