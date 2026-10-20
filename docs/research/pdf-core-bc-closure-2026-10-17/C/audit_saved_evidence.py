"""Read saved image evidence; never run providers or attach it to new owners."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
G2 = Path("docs/research/pdf-core-g2-images-2026-10-14")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


manifest = json.loads((G2 / "inputs/input-manifest.json").read_text())
observations = json.loads((G2 / "api/observations.json").read_text())
by_case = {x["case"]: x for x in observations}
api = []
for inp in manifest["inputs"]:
    case = inp["input_id"]
    directory = G2 / "api" / case.lower()
    request_path = directory / "request-description.json"
    request = json.loads(request_path.read_text())
    response_path = directory / "response.json"
    response = json.loads(response_path.read_text())
    obs = by_case[case]
    assert sha(inp["path"]) == inp["sha256"] == request["input_sha256"]
    assert sha(directory / "input.png") == inp["sha256"]
    assert sha(response_path) == obs["response_sha256"]
    assert response["model"] == obs["returned_model"] == "gpt-6-luna"
    assert response["choices"][0]["finish_reason"] == "stop"
    assert response["usage"] == obs["usage"]
    body = request["body_without_inline_image"]
    api.append({"case": case, "source_id": inp["source_id"],
                "physical_page_1based": inp["physical_page_1based"],
                "input_sha256": inp["sha256"], "pixels": inp["pixels"],
                "request_description": str(request_path), "response": str(response_path),
                "parsed_output": str(directory / "output.json"),
                "model": response["model"], "reasoning_effort": body["reasoning_effort"],
                "image_detail": body["messages"][1]["content"][1]["image_url"]["detail"],
                "cap": body["max_completion_tokens"], "usage": obs["usage"],
                "api_rtt_seconds": obs["client_round_trip_seconds"],
                "retained_quality": "selected_real_source_meaning_pass" if case in {"G1-S05", "G1-S07"} else "controlled_chart_only_pass",
                "quality_evidence": str(G2 / "review/output-review.json"),
                "reusable_as": "exact_saved_input_component_evidence_and_offline_round_trip",
                "not_reusable_as": "new_native_crop_accuracy_same_revision_end_to_end_or_company_model"})
ocr_path = Path("docs/research/pdf-core-g2-round2-2026-10-14/ocr/runs/picture-scale3/ocr.json")
ocr = json.loads(ocr_path.read_text())
ocr_img = ocr_path.parent / "figure.png"
assert sha(ocr_img) == ocr["crop_sha256"]
assert len(ocr["texts"]) == len(ocr["scores"]) == len(ocr["boxes"]) == 53
mock_dir = Path("docs/research/pdf-core-stage1-followup-2026-10-17/C")
mock_results = json.loads((mock_dir / "results.json").read_text())
classifier = json.loads((G2 / "classifier/method.json").read_text())
historical = {}
for manifest_path in [Path("docs/research/pdf-core-stage1-2026-10-17/C/evidence-hashes.json"),
                      mock_dir / "evidence-hashes.json"]:
    expected = json.loads(manifest_path.read_text())
    for path, digest in expected.items():
        assert sha(path) == digest, path
        historical[path] = digest
result = {
    "status": "saved_identity_and_scope_audit_pass", "new_inference": 0,
    "api": api,
    "api_total": {"calls_historical": len(api),
                  "input_tokens_historical": sum(x["usage"]["prompt_tokens"] for x in api),
                  "completion_tokens_historical": sum(x["usage"]["completion_tokens"] for x in api),
                  "serial_rtt_seconds_historical": sum(x["api_rtt_seconds"] for x in api)},
    "ocr": {"path": str(ocr_path), "input_image": str(ocr_img),
            "input_sha256": ocr["crop_sha256"], "pixels": ocr["pixel_dimensions"],
            "texts": 53, "producer": ocr["producer"],
            "content_scope": "saved_output_and_some_selected_source_checks_not_whole_screenshot_quality_pass",
            "new_native_crop_reuse": False},
    "classifier": {"method": str(G2 / "classifier/method.json"),
                   "revision": classifier["revision"], "device": classifier["devices"],
                   "dtype": classifier["dtypes"], "runtime": classifier["versions"],
                   "scope": "six image sources/twelve crops; broad family positive, not same 2.132 profile or mandatory-work exemption"},
    "mock_native": {"results": str(mock_dir / "results.json"),
                    "summary": str(mock_dir / "summary.md"),
                    "status": "one_native_owner_same_crop_mock_mechanical_only",
                    "full_C_readiness": "partial", "new_model_evidence": False},
    "historical_hashes_verified": historical,
    "new_native_or_same_revision_API_results": 0,
    "same_crop_requirement": "No provider answer is attached to an owner/crop/revision different from its registered input."
}
(ROOT / "saved-evidence-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": result["status"], "saved_api": len(api), "saved_ocr_texts": 53,
                  "historical_files_verified": len(historical), "new_model_calls": 0}))
