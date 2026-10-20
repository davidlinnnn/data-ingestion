"""Last-candidate paired request and official-assembly verification; offline only."""
import ast
import base64
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import patch
import warnings

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "pdf-core-g2-official-method-2026-10-15"
spec = importlib.util.spec_from_file_location("frozen_official_api_verification", PARENT / "api-verification.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
REPO, MODEL, ENDPOINT = base.REPO, base.MODEL, base.ENDPOINT

# Filled before candidate3 completes; only immutable candidate2 execution evidence.
PARENT_SNAPSHOT = {'docs/research/pdf-core-g2-official-method-2026-10-15/api/controls-p1/input.png': 'dad381be5aa2fa4eb1b3faa675bed9ceea32282c58ac3bd25c72175d6f8e88d6', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/controls-p1/raw-doctags.txt': 'bc8cedbefde2dcc289f0b7ef00bf55e408d86ac9ed7e3f7e0e8a8a0c9e7c2a1f', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/controls-p1/request.json': '7c1cf8683847c02c322f0143cb70cea0de96c5829452d775a80ad6806f5d8102', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/controls-p1/response.json': 'bd59222ffb580d18b38c0a0504497e8c2815b4080a7ab8e6e25bf9a62697c7b0', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/dgm-p51/input.png': '714802d083f951e716dca46e4bd5161b79f481685cbb29de92eccdda6edb607c', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/dgm-p51/raw-doctags.txt': '1d59c4322bc6e0316ef64e2eb4bb48ff25841b8207462dc8e99be8412f591a49', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/dgm-p51/request.json': '1f357db3ccd75a0f2fa8835bbb6e1f71e02bcbc5d302f4ea1ecb7a839ec162da', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/dgm-p51/response.json': '47f44e9ac38e47342edd7a40f7817799e9c353685b7161329560d79d2ffdb3f4', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p2/input.png': '93b96e692729180de47072a1d0b15cf8a1a100af9faf797198365e022d698655', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p2/raw-doctags.txt': '18dc8c2432c97dc61b8f02bf7a10ab2cf564d06b2e9bab165044d77a538aa66b', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p2/request.json': '33ebd55089e7f42d1cf692cb682a6128a5c439f546131401ca2ab32223668c26', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p2/response.json': '81ceef0d0ad430d1188fb1b8845c6682552d6915381caf5474a91f2d9886ac2b', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p3/input.png': '13fc6fee95b99fa2a0642b9c716d27bc18ef1f0252a9e8d1b0191fdebd2a1efe', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p3/raw-doctags.txt': '0c2348c8f03d7e5f12757e141bd275fb795c34f9c1814ce080c1ef93d908bfdb', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p3/request.json': 'cd643e02a0a467bed491aa8f10baabcb330cbde2a1cc3907ca8c5af66fa44900', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p3/response.json': '99b1206b0f3af732720fbff646401c05509be7377a0a2ae4c5e938a26c7525a9', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p4/input.png': '649cf41e9e1b232eeb11dbcfaeca239e83dfa1d48324fd3bdd2499863df5961e', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p4/raw-doctags.txt': 'c3eda27055d33f923fa041d9647edbfff8112fb1933b0a9820c7ebb77bb3c00a', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p4/request.json': 'd3c90df633f3551ef1946d5a419ee383e27785d0e4536836ac638f5fe0df7046', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/seal-p4/response.json': 'eddfbb26e297d690909e817610ae5307d62fbe8b8cccfc5e1d4d2fba2e147b89', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p20/input.png': '61f420b1ef8f3aef868dfbbc9aa4cc0f0bbcd9c00bac9ed8f0768cd42ee1f125', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p20/raw-doctags.txt': '5eaa1e851dfcb9de89018f35a260ac1b75c401663f7275530a26bf9b1efed4ab', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p20/request.json': 'd5187ee141322cc8e8293559916a77c7246a92e44f33510aaa7f528e08e4d985', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p20/response.json': '8b36adc665d5cf04dedbb28e638dac1ecbe1e60b9416a98082d0eafbec2dc08b', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p21/input.png': 'b5a997699199d83f2cfdacb47e2272c23dd974eca978581e06858db143262633', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p21/raw-doctags.txt': '1fee14b11e8094943bcddfb2c9642b022cb5dcc531f99f84cbca76752402d89e', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p21/request.json': 'd150556001238e3f41eddb8ece6debbf61ed82af27e2f7027d8cde72ff9757ef', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p21/response.json': '3828062d9d29c85936ce764a868548308a30349e8ac4dbb66213a91890c91052', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p22/input.png': '9f05cfa8d3d390e1a79fc35c89a05931a9a6e6d796ac001678a9748584bf971c', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p22/raw-doctags.txt': 'c42f082bc2e370919f4873af906a0e95aa1309ce47e58278a52f6002e40f4886', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p22/request.json': '4c77019e5053336c81aee563a903d92fbd562fc163e832b9ce41939af591eefe', 'docs/research/pdf-core-g2-official-method-2026-10-15/api/wikiskill-p22/response.json': 'def690870df44cd1755e24a774cc09b39b3a71162189d30fc0a377c32b714d44', 'docs/research/pdf-core-g2-official-method-2026-10-15/api-verification.json': 'ad8182667207e62ec50a678765e772cf59d0bba5845569a0b1e44d46367c626f', 'docs/research/pdf-core-g2-official-method-2026-10-15/api-verification.py': 'c5a432908fdc71ea574f4c44893419d78148e237c53a02ae7140ed4fa404955c', 'docs/research/pdf-core-g2-official-method-2026-10-15/conversions.json': 'a2ce95ca2c5e91082181d171bbbeac2e6075ad8ad07ef7eff7991b976c6d7382', 'docs/research/pdf-core-g2-official-method-2026-10-15/documents/controls/document.json': 'a98663b411870a0fec6288ab7e1e3d1a98404d3513305492f00010f1efc713a4', 'docs/research/pdf-core-g2-official-method-2026-10-15/documents/controls/document.md': '74eb947117f4d127cd43903ca784566fc3c47c6199266835444e703b07a9e579', 'docs/research/pdf-core-g2-official-method-2026-10-15/documents/dgm/document.json': '9cddb29a25248f0f46636df481df7ce100833e467e0b2b772798c3fab78038e7', 'docs/research/pdf-core-g2-official-method-2026-10-15/documents/dgm/document.md': '4c0026df9cbf2e90df7ccbf2f793bd9ad873378f3491b96d0dc84fc40b79cf0b', 'docs/research/pdf-core-g2-official-method-2026-10-15/documents/seal/document.json': '04a4be78fa31b672bef9ecf2ed2948ddbbd5fd247a6b44ec1a3e7bac95c16b87', 'docs/research/pdf-core-g2-official-method-2026-10-15/documents/seal/document.md': 'ac6ee2f2fa82577b9d693790f4d669476710b33716894283840046324aaba37e', 'docs/research/pdf-core-g2-official-method-2026-10-15/documents/wikiskill/document.json': 'a02eb0cd80ca411d2c07b382d25023a51e547d0fa87dcb974bc95f2b6b2a232f', 'docs/research/pdf-core-g2-official-method-2026-10-15/documents/wikiskill/document.md': '468a3f9fdc01479dd5c76c7edc1390c0695f0c8dd2944184d49005ac9b99f370', 'docs/research/pdf-core-g2-official-method-2026-10-15/execution.json': '5e4d5bd721006dcf934b1faf110c031d57496be01fae3b817018204760b69475', 'docs/research/pdf-core-g2-official-method-2026-10-15/observations.json': 'efcaf048c1332d7610b38392797f0cbe4a787d212537ba0f090e4974fc5e4ce0', 'docs/research/pdf-core-g2-official-method-2026-10-15/registration.json': 'd2488590b6607b517e62aae4fda5f1eb096534dd3be1bdc69a9de073a9e2d3ac', 'docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json': '22ee81e79db28cf07d14ddd1f53269aada08d8b6480633ef67046a3e955777f2', 'docs/research/pdf-core-g2-official-method-2026-10-15/run.py': 'bff221274abb8b9abd8bbff46b56165bae170a9e1c710d739d8db3cfbee0f33a'}


def verify_pair(old_request, new_request, old_image, new_image):
    old = old_request["body_without_inline_image"]
    new = new_request["body_without_inline_image"]
    assert old["reasoning_effort"] == "low" and new["reasoning_effort"] == "medium"
    expected = deepcopy(old)
    expected["reasoning_effort"] = "medium"
    assert new == expected
    assert old_image == new_image
    assert old_request["input_sha256"] == new_request["input_sha256"] == hashlib.sha256(new_image).hexdigest()
    assert old_request["source"] == new_request["source"]
    assert old_request["physical_page_1based"] == new_request["physical_page_1based"]
    payload = deepcopy(new)
    image = payload["messages"][0]["content"][0]["image_url"]
    assert image == {"url": "IMAGE_BYTES_FROM_input.png"}
    image["url"] = "data:image/png;base64," + base64.b64encode(new_image).decode()
    assert hashlib.sha256(base.request_body(payload)).hexdigest() == new_request["http_body_sha256"]
    return payload


def main():
    assert (HERE / "execution.json").is_file(), "Wait for candidate3 execution completion"
    assert len(PARENT_SNAPSHOT) >= 40
    for path, expected in PARENT_SNAPSHOT.items():
        assert base.sha(REPO / path) == expected, "Frozen candidate2 changed: " + path
    registration, execution = base.read(HERE / "registration.json"), base.read(HERE / "execution.json")
    contract = base.read(HERE / "review/contract.json")
    assert registration["configuration_number"] == registration["maximum_configurations"] == 3
    assert base.version("docling") == "2.102.0" and base.version("docling-core") == "2.96.0"
    for path, expected in base.read(PARENT / "preflight/summary.json")["source_files"].items():
        assert base.sha(Path(path)) == expected
    assert registration["post_result_tuning_permitted"] is False
    assert registration["budget_exhausted_after_this_configuration"] is True
    assert registration["single_changed_parameter"] == {"reasoning_effort": {"before": "low", "after": "medium"}}
    assert base.sha(HERE / "run.py") == registration["runner_sha256"]
    assert (HERE / "review/contract.json").read_bytes() == (PARENT / "review/contract.json").read_bytes()
    registered = datetime.fromisoformat(registration["registered_at_utc"]).timestamp()
    assert datetime.fromisoformat(contract["frozen_at_utc"]).timestamp() <= registered
    checked = set()
    base.verify_refs(registration, checked)
    base.verify_refs(contract, checked)
    prior = base.read(PARENT / "prior-inputs.json")
    base.verify_refs(prior, checked)
    prior_payloads = set()
    for reference in prior["prior_manifest_refs"]:
        found = set()
        base.verify_refs(base.read(REPO / reference["path"]), found)
        checked.update(found)
        prior_payloads.update(found)
    module = ast.parse((PARENT / "run.py").read_text())
    prompt = next(ast.literal_eval(n.value) for n in module.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "PROMPT" for t in n.targets))
    assert all(s not in prompt for s in ["ReflACT", "RefIACT", "23.3", "40.5", "#/texts/"])
    observations, conversions = base.read(HERE / "observations.json"), base.read(HERE / "conversions.json")
    rows = contract["scope"]["page_manifest"]
    keys = [(r["source"], r["physical_page_1based"]) for r in rows]
    assert len(keys) == len(set(keys)) == 8
    assert [(r["source"], r["page"]) for r in observations] == keys
    assert execution["all_exchanges_usable"] and execution["attempted_requests"] == 8
    assert execution["automatic_retries"] == 0 and not execution["model_output_repair"]
    assert execution["holdout_reads"] == 0 and execution["credentials_persisted"] is False
    assert len({r["request_id"] for r in observations}) == 8 and all(r["request_id"] for r in observations)
    old_ids = {r["request_id"] for r in base.read(PARENT / "observations.json")}
    assert not old_ids.intersection(r["request_id"] for r in observations)
    totals = {k:0 for k in ["prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cached_tokens"]}
    records, responses, negatives = [], {}, []
    for (source, page), observed in zip(keys, observations):
        folder, old_folder = HERE / "api" / f"{source}-p{page}", PARENT / "api" / f"{source}-p{page}"
        request, old_request = base.read(folder / "request.json"), base.read(old_folder / "request.json")
        image, old_image = (folder / "input.png").read_bytes(), (old_folder / "input.png").read_bytes()
        payload = verify_pair(old_request, request, old_image, image)
        assert payload["model"] == MODEL and payload["temperature"] is None
        assert payload["max_completion_tokens"] == 8192 and payload["store"] is False
        assert payload["messages"][0]["content"][1]["text"] == prompt
        assert not request["authorization_persisted"]
        if not negatives:
            for name in ["model", "prompt", "reasoning", "image"]:
                bad = deepcopy(request)
                altered_image = image
                if name == "model": bad["body_without_inline_image"]["model"] = "other-model"
                elif name == "prompt": bad["body_without_inline_image"]["messages"][0]["content"][1]["text"] += " changed"
                elif name == "reasoning": bad["body_without_inline_image"]["reasoning_effort"] = "high"
                else: altered_image += b"changed"
                try:
                    verify_pair(old_request, bad, old_image, altered_image)
                except AssertionError:
                    negatives.append(name)
                else:
                    raise AssertionError("Invalid paired mutation accepted")
        response = base.read(folder / "response.json")
        choice, usage = response["choices"][0], response["usage"]
        content = choice["message"]["content"]
        assert response["model"] == observed["returned_model"] == MODEL
        assert response["created"] >= registered
        assert observed["http_status"] == 200 and observed["attempts"] == 1
        assert choice["finish_reason"] == observed["finish_reason"] == "stop"
        assert not choice["message"].get("refusal") and not observed["refusal"]
        assert content.strip() and content == (folder / "raw-doctags.txt").read_text()
        assert usage == observed["usage"]
        assert usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"]
        for name in ["prompt_tokens", "completion_tokens", "total_tokens"]: totals[name] += usage[name]
        totals["reasoning_tokens"] += usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
        totals["cached_tokens"] += usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        locations = [int(v) for v in re.findall(r"<loc_(-?\d+)>", content)]
        with base.Image.open(BytesIO(image)) as im: dimensions = list(im.size)
        records.append({"source": source, "physical_page_1based": page,
            "request_body_exact": True, "only_reasoning_changed_vs_candidate2": True,
            "input_png_bytes_identical_to_candidate2": True, "input_png_pixels_wh": dimensions,
            "response_id": response.get("id"), "request_id": observed["request_id"],
            "response_sha256": base.sha(folder / "response.json"), "response_created": response["created"],
            "saved_response_content_matches_saved_doctags": True,
            "observer_redaction_applied": observed["credential_redaction_applied"],
            "persisted_redaction_marker_count": content.count("[REDACTED]"),
            "location_tokens": len(locations), "location_min": min(locations, default=None),
            "location_max": max(locations, default=None),
            "outside_requested_0_500_count": sum(not 0 <= n <= 500 for n in locations),
            "one_doctag_envelope": bool(re.fullmatch(r"\s*<doctag>.*</doctag>\s*", content, flags=re.S)),
            "seconds": observed["seconds"], "usage": usage})
        responses[(source, page)] = response

    active, replays = {"source":None, "pages":[], "index":0}, []
    def no_network(*args, **kwargs): raise AssertionError("No network in verifier")
    def post(url, *, headers=None, json=None, timeout=None, **kwargs):
        assert str(url) == ENDPOINT and timeout == 180 and not kwargs
        source, page = active["source"], active["pages"][active["index"]]
        active["index"] += 1
        request = base.read(HERE / "api" / f"{source}-p{page}" / "request.json")
        assert hashlib.sha256(base.request_body(json)).hexdigest() == request["http_body_sha256"]
        return SimpleNamespace(ok=True, text=__import__("json").dumps(responses[(source,page)]))
    api = base.ApiVlmEngineOptions(url=ENDPOINT, timeout=180, concurrency=1,
        params={"model":MODEL, "temperature":None, "max_completion_tokens":8192,
                "reasoning_effort":"medium", "store":False})
    assert execution["safe_options"]["actual_engine_options"] == api.model_dump(mode="json")
    spec = base.VlmModelSpec(name="gpt-6-luna-official-doctags-candidate2", default_repo_id=MODEL,
        prompt=prompt, response_format=base.ResponseFormat.DOCTAGS, max_new_tokens=8192)
    options = base.VlmPipelineOptions(enable_remote_services=True,
        accelerator_options=base.AcceleratorOptions(device="cpu", num_threads=4),
        images_scale=1.0, generate_page_images=True, generate_picture_images=False,
        vlm_options=base.VlmConvertOptions(engine_options=api, model_spec=spec, scale=2.0,
                                          batch_size=1, force_backend_text=False))
    with ExitStack() as stack:
        for target in ["requests.sessions.Session.send", "socket.create_connection", "socket.socket.connect"]:
            stack.enter_context(patch(target, side_effect=no_network))
        stack.enter_context(patch("requests.post", side_effect=post))
        converter = base.DocumentConverter(format_options={base.InputFormat.PDF: base.PdfFormatOption(
            pipeline_cls=base.VlmPipeline, pipeline_options=options)})
        for conversion in conversions:
            source, pages = conversion["source"], conversion["requested_physical_pages"]
            active.update(source=source, pages=pages, index=0)
            row = next(r for r in rows if r["source"] == source)
            with warnings.catch_warnings(record=True) as warnings_seen:
                warnings.simplefilter("always")
                conv = converter.convert(REPO / row["source_pdf_ref"]["path"],
                    page_range=(min(pages), max(pages)), raises_on_error=False)
                raw = conv.document.export_to_dict()
                markdown = conv.document.export_to_markdown()
            saved = base.read(HERE / "documents" / source / "document.json")
            diff = base.differences(saved, raw)
            redacted = any(r["observer_redaction_applied"] for r in records if r["source"] == source)
            if redacted:
                strings = [d for d in diff if isinstance(d["stored_official"], str)]
                assert strings and all(base.legacy_redact(d["stored_official"]) == d["replayed_persisted_response"] for d in strings)
                for delta in [d for d in diff if d not in strings]:
                    text = next(d for d in strings if delta["path"] == d["path"].removesuffix("/text") + "/prov/0/charspan/1")
                    assert delta["stored_official"] == len(text["stored_official"])
                    assert delta["replayed_persisted_response"] == len(text["replayed_persisted_response"])
            else: assert not diff
            markdown_exact = markdown == (HERE / "documents" / source / "document.md").read_text()
            assert markdown_exact == (not bool(diff))
            assert active["index"] == len(pages) == conversion["actual_requests"]
            assert conversion["source_page_map"] == {str(i+1):p for i,p in enumerate(pages)}
            assert conversion["official_document_pages"] == sorted(int(k) for k in raw["pages"]) == list(range(1,len(pages)+1))
            positions = [p for key in ["texts","pictures","tables"] for item in raw[key] for p in item.get("prov",[])]
            zero, degenerate, outside = 0, 0, 0
            for p in positions:
                b, size = p["bbox"], raw["pages"][str(p["page_no"] )]["size"]
                zero += all(b[k] == 0 for k in ["l","t","r","b"])
                degenerate += b["r"] <= b["l"] or abs(b["t"]-b["b"]) <= 0
                outside += not (0 <= b["l"] <= b["r"] <= size["width"] and 0 <= min(b["t"],b["b"]) <= max(b["t"],b["b"]) <= size["height"])
            replays.append({"source":source, "official_document_replay_exact":not bool(diff),
                "official_markdown_replay_exact":markdown_exact, "source_page_map":conversion["source_page_map"],
                "all_differences_explained_by_observer_redaction":bool(diff),
                "redaction_differences":[{"path":d["path"],
                    "stored_length_or_value":len(d["stored_official"]) if isinstance(d["stored_official"],str) else d["stored_official"],
                    "replayed_length_or_value":len(d["replayed_persisted_response"]) if isinstance(d["replayed_persisted_response"],str) else d["replayed_persisted_response"],
                    "regex_matches":[m.group(0) for m in re.finditer(r"sk-(?:proj-)?[A-Za-z0-9_.*-]{6,}",d["stored_official"])] if isinstance(d["stored_official"],str) else []} for d in diff],
                "zero_bboxes":zero,"degenerate_bboxes":degenerate,"bboxes_outside_official_page":outside,
                "native_warnings":sorted({str(w.message) for w in warnings_seen})})
    for path, expected in PARENT_SNAPSHOT.items(): assert base.sha(REPO / path) == expected
    result = {"passed":True,"scope":"Independent paired-request and official-parser replay verification; not semantic acceptance",
        "configuration_number":3,"configuration_budget_exhausted":True,"requests_verified":8,
        "pairwise_only_reasoning_changed":True,"input_png_bytes_unchanged":True,
        "exact_http_body_reconstruction":True,"parent_execution_payloads_unchanged":len(PARENT_SNAPSHOT),
        "parent_payload_snapshot":PARENT_SNAPSHOT,"frozen_references_verified":len(checked),
        "prior_payload_paths_verified":len(prior_payloads),"one_attempt_each":True,
        "registered_before_responses":True,"no_new_prompt_or_output_repair":True,
        "location_contract_satisfied":all(r["outside_requested_0_500_count"]==0 for r in records),
        "location_tokens_outside_contract":sum(r["outside_requested_0_500_count"] for r in records),
        "raw_response_preserved_pages":sum(not r["observer_redaction_applied"] for r in records),
        "observer_false_positive_redaction_pages":[r["source"]+"-p"+str(r["physical_page_1based"]) for r in records if r["observer_redaction_applied"]],
        "usage":totals,"requests":records,"official_replay":replays,
        "selfcheck":{"passed":True,"rejected_pair_mutations":negatives},
        "network_calls":0,"holdout_pdf_reads":0,"credentials_read":False,"source_page_identity_does_not_prove_geometry":True}
    (HERE/"verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ["passed","requests_verified","pairwise_only_reasoning_changed","parent_execution_payloads_unchanged","location_contract_satisfied","location_tokens_outside_contract","observer_false_positive_redaction_pages","usage"]},indent=2))


if __name__ == "__main__": main()
