"""Use the frozen strict parser without changing any model text or block role."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = load("context_api_independent_verifier", ROOT / "api/verify.py")
parser = load("context_api_frozen_strict_parser", verify.PARSER)


def main():
    rows, exchanges = verify.verify_all()
    outcomes = []
    for row, exchange in zip(rows, exchanges, strict=True):
        folder = HERE / row["source"] / row["job_id"]
        folder.mkdir(parents=True, exist_ok=False)
        output = verify.read(verify.checked(exchange["output_ref"]))
        record = {"source": row["source"], "job_id": row["job_id"], "input_metadata": row,
                  "exchange": exchange, "model_text_repaired": False, "semantic_quality_assessed": False}
        try:
            parser.validate(output, row["image_pixels_wh"])
            markdown, mapped = parser.render(output)
            for block in mapped:
                for segment in block["segments"]:
                    assert markdown[slice(*segment["markdown_charspan"])] == segment["rendered_markup"]
            unknown = any(s["kind"] == "unknown" or s["text"] is None for b in output["blocks"] for s in b["segments"])
            verify.save(folder / "original-blocks.json", output)
            (folder / "document.md").write_text(markdown)
            assert output == verify.read(verify.checked(exchange["output_ref"]))
            contract = verify.read(verify.checked(row["request_contract_ref"]))
            compatible = [b["kind"] for b in output["blocks"]] == [contract["native_target_role"]]
            record.update(status="parsed", blocks=mapped, uncertainties=output["uncertainties"],
                          unknown_or_null_segments=unknown, exactly_one_declared_role=compatible,
                          eligible_for_structural_application=not unknown and compatible,
                          markdown_ref=verify.ref(folder / "document.md"),
                          original_blocks_ref=verify.ref(folder / "original-blocks.json"))
            verify.save(folder / "render-map.json", record)
        except (ValueError, KeyError, TypeError) as error:
            record.update(status="parse_failed", reason=str(error), eligible_for_structural_application=False)
            verify.save(folder / "failure.json", record)
        outcomes.append({k: record[k] for k in ("source", "job_id", "status", "reason", "eligible_for_structural_application",
                                                "exactly_one_declared_role", "unknown_or_null_segments") if k in record})
    verify.save(HERE / "summary.json", {"format": "g2-context-strict-parse-v1", "parser_ref": verify.ref(verify.PARSER),
        "driver_ref": verify.ref(Path(__file__)), "input_manifest_ref": verify.ref(verify.MANIFEST),
        "api_verification_ref": verify.ref(ROOT / "api/verification.json"), "outcomes": outcomes,
        "output_count": len(outcomes), "model_text_repaired": False, "semantic_quality_assessed": False})
    print("Saved strict parse records for all 36 fixed requests; no semantic repair.")


if __name__ == "__main__":
    main()
