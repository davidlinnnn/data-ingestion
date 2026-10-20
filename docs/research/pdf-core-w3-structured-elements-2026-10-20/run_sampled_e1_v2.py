"""Authorized source-stratified inference scope; model/options remain E1 unchanged."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent


def main():
    import run_e1 as run
    seal = json.loads((ROOT / "selection-freeze-v2.json").read_text())
    for name, digest in seal["files"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    run.__file__ = str(Path(__file__).resolve())
    original_save = run.save

    def save(path, obj):
        if path.name == "option-diff.json":
            obj = dict(obj, sample_gate="Frozen source-unit/reference scope only; official E1 options unchanged", selection_freeze_sha256=hashlib.sha256((ROOT / "selection-freeze-v2.json").read_bytes()).hexdigest())
        original_save(path, obj)

    run.save = save
    if sys.argv[1:2] == ["--run"]:
        run.parent(sys.argv[2])
        return
    assert sys.argv[1:2] == ["--child"]
    name, jobid = sys.argv[2:4]
    plan = json.loads((ROOT / "plans" / f"{name}.json").read_text())
    allowed = plan["selected_items_by_job"][jobid]
    from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
    original = CodeFormulaVlmModel.is_processable
    seen = set()

    def selected(self, doc, element):
        item = element
        eligible = original(self, doc, item)
        if not eligible or item.self_ref not in allowed:
            return False
        expected = allowed[item.self_ref]
        assert str(item.label) == expected["label"], item.self_ref
        assert hashlib.sha256(item.orig.encode()).hexdigest() == expected["orig_sha256"], item.self_ref
        seen.add(item.self_ref)
        run.save(ROOT / "runs" / name / "jobs" / jobid / "sample-selection-observed.json",
                 dict(policy="registered source unit scope only; no model/numeric changes", selected_refs=sorted(seen), expected_refs=sorted(allowed)))
        return True

    CodeFormulaVlmModel.is_processable = selected
    run.child(name, jobid)


if __name__ == "__main__":
    main()
