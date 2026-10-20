"""Independent evaluator fixtures and actual T03 graph-preservation controls."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

from docling_core.types.doc import DoclingDocument, RefItem, TableData
from markdown_it import MarkdownIt
from scoring import digest, score, score_math
from table_seam import discover, replace_data

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
B = ROOT / "docs/research/pdf-core-eval-interfaces-2026-10-18/B"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads(path.read_text())


protocol = load("offline_protocol", B / "protocol.py")
old = load("offline_delivery_reader", ROOT / "docs/research/pdf-core-fixed-seven-source-2026-10-18/evaluate.py")


def source_fixture():
    """Evaluator-only oracle-generated MOCK. Never enters a producer/request."""
    worksheet = read(B / "evaluator/G1-T04.json")
    rows, columns = {}, []
    for point in worksheet["points"]:
        e = point["expected"]
        if e["column_key"] not in columns:
            columns.append(e["column_key"])
        rows.setdefault(e["row_id"], []).append(point)
    panel = dict(panel_label="", title="", dimension_names=list(worksheet["points"][0]["expected_row_context"]),
                 columns=[dict(key=str(i), path=[dict(id=f"h{i}", text=c)]) for i,c in enumerate(columns)],
                 rows=[], groups=[])
    for row_id, points in rows.items():
        panel["rows"].append(dict(key=row_id, dimensions=points[0]["expected_row_context"], group=None,
            cells=[dict(id=p["expected"]["id"], column=str(columns.index(p["expected"]["column_key"])),
                        text=p["expected"]["raw_value"]) for p in points]))
    data, _ = protocol.method.normalized_panel(panel)
    job = next(j for j in read(B / "candidate.json")["jobs"] if j["name"]=="paper09-p17-table0")
    document = DoclingDocument.model_validate_json(Path(job["baseline"]).read_text())
    ref = job["target_key"].split(":", 1)[1]
    RefItem(cref=ref).resolve(document).data = TableData.model_validate(data)
    document = DoclingDocument.model_validate_json(document.model_dump_json())
    table = RefItem(cref=ref).resolve(document)
    grid = [[c.text.strip() for c in row] for row in table.data.grid]
    markdown = table.export_to_markdown(doc=document)
    rendered = old.Tables(MarkdownIt("default").enable("table").render(markdown)).tables
    assert rendered == [grid], "actual Core and rendered fixture must agree"
    cells, matches = [], {}
    for ri, row in enumerate(panel["rows"], 1):
        for ci, cell in enumerate(row["cells"]):
            observed = dict(locator=f"{ri}:{ci}", text=grid[ri][len(panel["dimension_names"])+ci],
                semantics=dict(row_dimensions=row["dimensions"], header=panel["columns"][ci]["path"],
                               panel=panel["title"], group=row["group"]))
            cells.append(observed)
            matches[cell["id"]] = dict(locator=observed["locator"], component=0, passed=True,
                observed_sha256=digest(observed), evidence="CONTROL: source-generated fixture, not model output")
    review = dict(matches=matches, decisions={k:dict(passed=True,evidence="CONTROL source fixture")
        for k in worksheet["manual_structure_review"] if k!="notes"})
    return worksheet, cells, review


class ScoringControls(unittest.TestCase):
    def setUp(self):
        self.w, self.cells, self.review = source_fixture()

    def test_complete_legal_T04_and_equivalent_dimension_names(self):
        for cell in self.cells:
            cell["semantics"]["row_dimensions"] = {k.upper():v for k,v in cell["semantics"]["row_dimensions"].items()}
        for match in self.review["matches"].values():
            cell=next(c for c in self.cells if c["locator"]==match["locator"])
            match["observed_sha256"] = digest(cell)
        result = score(self.w,self.cells,self.review)
        self.assertTrue(result["passed"])
        self.assertEqual((result["numeric_correct"],result["comparisons_passed"]),(300,5))

    def test_one_permitted_minor_does_not_require_zero_error(self):
        critical={c["expected"][k] for c in self.w["comparisons"] for k in ("left","right")}
        point=next(p for p in self.w["points"] if p["expected"]["id"] not in critical)
        match=self.review["matches"][point["expected"]["id"]]
        cell=next(c for c in self.cells if c["locator"]==match["locator"])
        cell["text"]="999"
        match["observed_sha256"]=digest(cell)
        self.assertTrue(score(self.w,self.cells,self.review)["passed"])

    def test_minor_missing_cell_counted_once(self):
        critical={c["expected"][k] for c in self.w["comparisons"] for k in ("left","right")}
        pid=next(p["expected"]["id"] for p in self.w["points"] if p["expected"]["id"] not in critical)
        match=self.review["matches"][pid]
        self.cells=[c for c in self.cells if c["locator"]!=match["locator"]]
        match.update(locator=None,absent=True)
        result=score(self.w,self.cells,self.review)
        self.assertTrue(result["passed"]);self.assertEqual(result["error_count"],1)

    def test_wrong_header_group_or_condition_invalidates_review_snapshot(self):
        for key in ("header","group","panel"):
            cells=deepcopy(self.cells);cells[0]["semantics"][key]="wrong source association"
            self.assertFalse(score(self.w,cells,self.review)["passed"])

    def test_pending_or_negative_required_source_review_cannot_pass(self):
        for value in (None,dict(passed=False,evidence="source header incorrect")):
            review=deepcopy(self.review);review["decisions"]["header_condition_binding"]=value
            self.assertFalse(score(self.w,self.cells,review)["passed"])

    def test_whole_missing_row_cannot_hide_under_numeric_tolerance(self):
        review=deepcopy(self.review)
        review["decisions"]["row_dimension_binding"]=dict(passed=False,evidence="a required row missing")
        self.assertFalse(score(self.w,self.cells,review)["passed"])

    def test_extra_panel_counted_and_never_expands_denominator(self):
        cells=self.cells+[dict(locator="foreign-panel",text=" ".join(["999"]*16),semantics={})]
        result=score(self.w,cells,self.review)
        self.assertFalse(result["passed"]);self.assertEqual(result["numeric_denominator"],300)
        self.assertEqual(result["extra_numeric"],16)

    def test_duplicate_source_consumption_rejected(self):
        keys=list(self.review["matches"])
        self.review["matches"][keys[1]]=deepcopy(self.review["matches"][keys[0]])
        with self.assertRaises(ValueError):score(self.w,self.cells,self.review)

    def test_critical_relation_reversal_fails(self):
        pid=self.w["comparisons"][0]["expected"]["left"]
        match=self.review["matches"][pid]
        cell=next(c for c in self.cells if c["locator"]==match["locator"])
        cell["text"]="-999";match["observed_sha256"]=digest(cell)
        self.assertFalse(score(self.w,self.cells,self.review)["passed"])

    def test_math_correct_wrong_and_pending_are_explicit_reviews(self):
        corrected=["1/(c-1)"]
        yes=[dict(passed=True,evidence="CONTROL reviewed source denominator subtraction",observed_sha256=digest(corrected[0]))]
        self.assertTrue(score_math(corrected,yes)["passed"])
        self.assertFalse(score_math(["1/c_{-1}"],yes)["passed"])
        self.assertFalse(score_math(corrected,[dict(passed=None,evidence="")])["passed"])

    def test_pair_role_inversion_invalidates_observed_binding(self):
        self.cells[0]["semantics"]["roles"]=["accepted","proposed"]
        self.assertFalse(score(self.w,self.cells,self.review)["passed"])

    def test_missing_dash_typography_allowed_but_zero_is_not_missing(self):
        point=deepcopy(self.w["points"][0])
        point["expected"].update(id="missing-control",value_kind="missing",raw_value="-")
        self.w["points"].append(point)
        cell=dict(locator="missing-control",text="—",semantics={"role":"source missing run"})
        self.cells.append(cell)
        match=dict(passed=True,evidence="CONTROL: reviewed missing-run source role",locator=cell["locator"],
                   component=0,observed_sha256=digest(cell))
        self.review["matches"]["missing-control"]=match
        self.assertTrue(score(self.w,self.cells,self.review)["passed"])
        cell["text"]="0";match["observed_sha256"]=digest(cell)
        self.assertFalse(score(self.w,self.cells,self.review)["passed"])


def native_document():
    seam=read(B / "T03-native-seam.json")
    return DoclingDocument.model_validate_json((ROOT/seam["current_S0_inspection"]["document"]).read_text())


class ContinuationControls(unittest.TestCase):
    def setUp(self):
        self.doc=native_document()
        self.relation=discover(self.doc)[0]
        panel=dict(panel_label="",title="",dimension_names=["Task","Dom.","Mode"],groups=[],
            columns=[dict(key=str(i),path=[dict(id=str(i),text=v)]) for i,v in enumerate(["No skill","Curated skill","Evolved"])],
            rows=[dict(key="mock",dimensions={"Task":"MOCK transport only","Dom.":"MOCK","Mode":"MOCK"},group=None,
                       cells=[dict(id=str(i),column=str(i),text="0") for i in range(3)])])
        data,_=protocol.method.normalized_panel(panel)
        self.replacements={f["table_ref"]:data for f in self.relation["fragments"]}

    def test_real_native_group_and_mock_data_preserve_entire_other_graph(self):
        self.assertEqual([f["page"] for f in self.relation["fragments"]],[27,28,29])
        before=digest(self.doc.model_dump(mode="json"))
        out,sidecar=replace_data(self.doc,self.relation,self.replacements)
        self.assertEqual(before,digest(self.doc.model_dump(mode="json")))
        self.assertEqual(sidecar["condition_caption_refs"],[self.doc.tables[2].captions[0].cref])
        loaded=DoclingDocument.model_validate_json(out.model_dump_json())
        self.assertEqual(digest(loaded.model_dump(mode="json")),sidecar["output_revision"])
        for i in (0,1):
            self.assertEqual(self.doc.tables[i].model_dump(),loaded.tables[i].model_dump())
            self.assertEqual(self.doc.tables[i].export_to_markdown(doc=self.doc),loaded.tables[i].export_to_markdown(doc=loaded))
        self.assertIn("Table 13 (continued)",loaded.export_to_markdown())

    def test_missing_fragment_and_stale_revision_rejected(self):
        missing=dict(self.replacements);missing.pop(next(iter(missing)))
        with self.assertRaises(ValueError):replace_data(self.doc,self.relation,missing)
        stale=deepcopy(self.relation);stale["source_revision"]="stale"
        with self.assertRaises(ValueError):replace_data(self.doc,stale,self.replacements)

    def test_ambiguous_initial_caption_abstains(self):
        ref=self.doc.tables[3].captions[0]
        ref.resolve(self.doc).text="Table 13: duplicate initial"
        self.assertEqual(discover(self.doc),[])

    def test_missing_continuation_caption_abstains(self):
        self.doc.tables[4].captions=[]
        self.assertEqual(discover(self.doc),[])

    def test_page_gap_and_header_conflict_abstain(self):
        self.doc.tables[3].prov[0].page_no=30
        self.assertEqual(discover(self.doc),[])
        self.doc=native_document()
        next(c for c in self.doc.tables[3].data.table_cells if c.column_header).text="conflicting header"
        self.assertEqual(discover(self.doc),[])


class SourceBoundaryControls(unittest.TestCase):
    def test_actual_cross_parent_scope_is_rejected_without_graph_repair(self):
        owner=ROOT/"docs/research/pdf-core-owner-context-2026-10-17"
        stored=read(owner/"results.json")
        job=next(j for j in stored["routes"]["native_plus_discovery"]
                 if j["binding"]=="unresolved" and len(j["target_owner_refs"])>4)
        inventory=read(ROOT/"docs/research/pdf-core-stage1-followup-2026-10-17/A/inventory.json")
        source=next(s for s in inventory["sources"] if s["source"]==job["source"])
        raw=read(ROOT/source["document_path"])
        method=load("boundary_A",ROOT/"docs/research/pdf-core-stage1-followup-2026-10-17/A/method.py")
        with self.assertRaisesRegex(ValueError,"one native parent"):
            method.scope(raw,job["target_owner_refs"])

    def test_native_crop_cannot_silently_be_fullpage_context(self):
        c=ROOT/"docs/research/pdf-core-eval-interfaces-2026-10-18/C"
        producer=load("boundary_C",c/"producer.py")
        row=next(p for p in read(c/"producer-inventory.json")["pictures"] if p["range_id"]=="SRC11-cached-seal")
        job=deepcopy(next(j for j in read(c/"requests.json")["jobs"] if j["binding"]["image_key"]==row["image_key"]))
        self.assertIsInstance(producer.materialize(job),bytes)
        job["input"]=str(ROOT/"docs/research/pdf-core-page-discovery-2026-10-17/pages/seal-p2.png")
        with self.assertRaisesRegex(ValueError,"actual image bytes changed"):
            producer.materialize(job)


if __name__=="__main__":unittest.main()
