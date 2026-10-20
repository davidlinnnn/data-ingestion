"""Run the additional registered HTML header controls without inference."""
import hashlib
import json
import os
from pathlib import Path
import socket

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
HERE = Path(__file__).resolve().parent


def blocked(*args, **kwargs):
    raise AssertionError("Network forbidden")


socket.socket.connect = blocked
socket.create_connection = blocked
from docling.utils.dots_utils import parse_dots_json
from docling_core.types.doc import Size

registration = json.loads((HERE / "header-control-registration.json").read_text())
out = HERE / "header-controls"
out.mkdir(exist_ok=False)
results = []
for case in registration["cases"]:
    dest = out / case["name"]
    dest.mkdir()
    raw = json.dumps([dict(category="Table", bbox=[20, 20, 540, 300], text=case["html"])])
    (dest / "raw.txt").write_text(raw)
    doc = parse_dots_json(raw, original_page_size=Size(width=560, height=840), page_no=3)
    doc.save_as_json(dest / "prediction.json")
    actual = [dict(text=c.text, row=c.start_row_offset_idx, col=c.start_col_offset_idx,
                   row_span=c.row_span, col_span=c.col_span, column_header=c.column_header)
              for c in doc.tables[0].data.table_cells]
    assert actual == registration["expected_cells"]
    markdown = {}
    for setting in registration["settings"]:
        text = doc.export_to_markdown(**setting["options"])
        (dest / (setting["name"] + ".md")).write_text(text)
        markdown[setting["name"]] = 'rowspan="2"' in text and 'colspan="2"' in text
    results.append(dict(name=case["name"], exact_cells_and_header_roles_pass=True,
                        markdown_spans_preserved=markdown))
initial = json.loads((HERE / "run/merged-table/prediction.json").read_text())
initial_headers = {c["text"]: c["column_header"] for c in initial["tables"][0]["data"]["table_cells"]}
assert not initial_headers["Train"] and not initial_headers["Test"]
(out / "results.json").write_text(json.dumps(dict(
    registration_sha256=hashlib.sha256((HERE / "header-control-registration.json").read_bytes()).hexdigest(),
    initial_control_second_header_row_roles_preserved=False, controls=results,
    note="The initial synthetic raw was not repaired; explicit-thead/scope are distinct registered source representations."), indent=2) + "\n")
print("Exact table positions/spans/header roles pass with explicit thead or scope; initial bare second-row th roles are absent; Markdown still flattens spans.")
