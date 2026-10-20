"""Independent saved-image/response/boundary checks; never imports an API client."""

import base64
from copy import deepcopy
from difflib import SequenceMatcher
from hashlib import sha256
import importlib.util
import json
from math import ceil, floor
from pathlib import Path
import re
import sys

from PIL import Image, ImageChops

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parents[1]
OLD = ROOT / "docs/research/pdf-core-g2-inline-2026-10-15"
PREVIOUS = ROOT / "docs/research/pdf-core-g2-inline-api-2026-10-15"
FROZEN_INPUT_SHA = "9cbaf2d1e31dc8fca9820c75f5c7b14d3a08f4bf8909698e39f3f6466856e22b"
spec = importlib.util.spec_from_file_location("prior_independent_api_review", PREVIOUS / "review/check.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    (WORK / "review" / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def resolve(doc, ref):
    collection, index = ref[2:].split("/")
    return doc[collection][int(index)]


def top_left(prov, doc):
    box = prov["bbox"]
    height = doc["pages"][str(prov["page_no"])]["size"]["height"]
    return [box[k] for k in ("l","t","r","b")] if box["coord_origin"] == "TOPLEFT" else [box["l"],height-box["t"],box["r"],height-box["b"]]


def union(boxes):
    return [min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]


def crop_errors(row, doc):
    errors = []
    if len(row["consumed_item_refs"]) != len(set(row["consumed_item_refs"])):
        errors.append("duplicate consumed source item")
    if row["working_replacement_refs"] != row["consumed_item_refs"] or set(row["consumed_item_refs"]) & set(row["context_only_refs"]):
        errors.append("replacement/context ownership mismatch")
    if row["id"].startswith("controls-pictures-"):
        parent = resolve(doc,row["consumed_item_refs"][0])
        children = [c.get("$ref",c.get("cref")) for c in parent["children"]]
        if row["member_item_refs"] != children or row["source_fragments"][0]["source_refs"] != row["consumed_item_refs"]+children:
            errors.append("incomplete picture/child accounting")
    for fragment in row["source_fragments"]:
        page = fragment["physical_page_1based"]
        if "provider_provenance" in fragment:
            expected = top_left(fragment["provider_provenance"],doc)
            ref = fragment["source_refs"][0]
            if page != fragment["provider_provenance"]["page_no"] or fragment["provider_provenance"] not in resolve(doc,ref)["prov"]:
                errors.append("foreign source fragment")
        else:
            boxes = [top_left(p,doc) for ref in fragment["source_refs"] for p in resolve(doc,ref)["prov"] if p["page_no"] == page]
            if not boxes:
                errors.append("wrong physical page")
                continue
            expected = union(boxes)
        if expected != fragment["bbox_top_left_points"]:
            errors.append("source-derived envelope mismatch")
        scale,pad = row["render_scale"],row["padding_points"]
        raster = Image.open(ROOT / fragment["full_page_raster_ref"]["path"])
        box = [max(0,floor((expected[0]-pad)*scale)),max(0,floor((expected[1]-pad)*scale)),min(raster.width,ceil((expected[2]+pad)*scale)),min(raster.height,ceil((expected[3]+pad)*scale))]
        if box != fragment["crop_pixel_box"]:
            errors.append("crop padding/rounding mismatch")
        x,y,w,h = fragment["canvas_xywh"]
        matrix = [[1/scale,0,box[0]/scale],[0,1/scale,(box[1]-y)/scale],[0,0,1]]
        if matrix != fragment["canvas_pixels_to_source_top_left_points_3x3"] or page not in row["physical_pages_1based"]:
            errors.append("source mapping/page mismatch")
    return errors


def inputs_review(manifest):
    records = []
    assert digest(WORK / "inputs/input-manifest.json") == FROZEN_INPUT_SHA
    for old_manifest in manifest["prior_payload_manifests"]:
        assert digest(ROOT / old_manifest["path"]) == old_manifest["sha256"]
        payloads = read(ROOT / old_manifest["path"])["files"]
        assert len(payloads) == old_manifest["payload_count"]
        assert all(digest(ROOT / f["path"]) == f["sha256"] for f in payloads)
    for row in manifest["inputs"]:
        assert digest(ROOT / row["source"]["path"]) == row["source"]["sha256"]
        assert digest(ROOT / row["baseline_document_ref"]["path"]) == row["baseline_document_ref"]["sha256"]
        doc = read(ROOT / row["baseline_document_ref"]["path"])
        errors = crop_errors(row,doc)
        assert not errors,(row["id"],errors)
        assert not set(row["consumed_item_refs"]) & set(row["context_only_refs"])
        for item in row["source_accounting"]:
            assert resolve(doc,item["item_ref"])["prov"] == item["prov"]
        canvas = Image.open(ROOT / row["image_path"]).convert("RGB")
        assert digest(ROOT / row["image_path"]) == row["image_sha256"]
        assert list(canvas.size) == row["image_pixels_wh"]
        rebuilt = Image.new("RGB",canvas.size,"white")
        prior_stop = 0
        fragments = []
        for fragment in row["source_fragments"]:
            full = fragment["full_page_raster_ref"]
            assert digest(ROOT / full["path"]) == full["sha256"]
            cropped = Image.open(ROOT / full["path"]).convert("RGB").crop(fragment["crop_pixel_box"])
            saved = Image.open(ROOT / fragment["image_ref"]["path"]).convert("RGB")
            assert digest(ROOT / fragment["image_ref"]["path"]) == fragment["image_ref"]["sha256"]
            assert ImageChops.difference(cropped,saved).getbbox() is None
            x,y,w,h = fragment["canvas_xywh"]
            assert saved.size == (w,h) and (y == 0 if prior_stop == 0 else y-prior_stop == row["stitch_gap_pixels"])
            rebuilt.paste(saved,(x,y)); prior_stop = y+h
            fragments.append({"physical_page":fragment["physical_page_1based"],"crop_pixels":fragment["crop_pixel_box"],"pixels_exact":True})
        assert ImageChops.difference(canvas,rebuilt).getbbox() is None
        records.append({"id":row["id"],"source_envelopes_padding_rounding_pixels_and_mapping_pass":True,"fragments":fragments})
    flow = next(r for r in manifest["inputs"] if r["id"] == "seal-prose-continuation")
    a,b = [f["crop_pixel_box"] for f in flow["source_fragments"]]
    return {"inputs":len(records),"records":records,"prior_846_payloads_preserved":True,
        "visual_QA":"All six source regions complete for the declared context. Formula delimiters, code seven lines, body continuation and equation context visible; parallel algorithm/caption excluded from body input.",
        "seal_continuation_source_padding_overlap_pixels":[max(0,min(a[2],b[2])-max(a[0],b[0])),max(0,min(a[3],b[3])-max(a[1],b[1]))],
        "overlap_limit":"Five-pixel source-y fringe repeats only top glyph edges; no complete duplicated line. Not pixel-disjoint crops."}


def run_review(row,observations):
    folder = WORK / "api" / row["id"]
    if not (folder / "output.json").exists():
        return {"id":row["id"],"status":"pending"},None
    request,response,output = [read(folder/name) for name in ("request-description.json","response.json","output.json")]
    body = deepcopy(request["body_without_inline_image"])
    body["messages"][1]["content"][1]["image_url"]["url"] = "data:image/png;base64,"+base64.b64encode((ROOT/row["image_path"]).read_bytes()).decode()
    observation = observations[row["id"]]
    choice = response["choices"][0]
    checks = {"exact_request_body":sha256(json.dumps(body,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()==request["http_body_sha256"],
        "exact_png":digest(folder/"input.png")==row["image_sha256"]==request["input_sha256"],
        "same_system_prompt":body["messages"][0]["content"]==helper.method_system_prompt(),
        "same_model_settings":body["model"]=="gpt-6-luna" and body["store"] is False and body["reasoning_effort"]=="low" and "temperature" not in body and body["max_completion_tokens"]==4096,
        "strict_schema":body["response_format"]["json_schema"]["strict"] is True,
        "high_detail":body["messages"][1]["content"][1]["image_url"]["detail"]=="high",
        "frozen_runner":request["runner_sha256"]==digest(WORK/"api/run.py"),
        "one_attempt_stop":observation["attempts"]==1 and observation["http_status"]==200 and choice["finish_reason"]=="stop" and not choice["message"].get("refusal"),
        "response_hash":digest(folder/"response.json")==observation["response_sha256"],
        "raw_json_equals_output":json.loads(choice["message"]["content"])==output}
    assert all(checks.values()),(row["id"],checks)
    errors = helper.schema_errors(output,row["image_pixels_wh"])
    assert not errors,(row["id"],errors)
    return {"id":row["id"],"status":"completed","checks":checks,"returned_model":response.get("model"),"usage":response.get("usage"),"round_trip_seconds":observation["client_round_trip_seconds"],"block_kinds":[b["kind"] for b in output["blocks"]],"uncertainties":output["uncertainties"]},output


def normalized_math(text):
    text = helper.prior.equivalent_surface(text)
    return re.sub(r"\s+","",text)


def model_identity_preserved(text):
    """Bounded evaluator source predicate; not a producer acceptance algorithm."""
    return "LM_θ'" in normalized_math(text) and "L_M_θ'" not in normalized_math(text)


def target_model_identity(output):
    return model_identity_preserved(" ".join(helper.block_text(b) for b in output["blocks"] if b["kind"]=="paragraph"))


def semantic_review(outputs):
    result = {}
    if "controls-pictures-0" in outputs:
        math = helper.output_text(outputs["controls-pictures-0"])
        compact = re.sub(r"\s+","",math)
        result["C01_matrix"] = {"raw":math,"values_shape_sign_order": "1&-2\\\\3&4" in compact,
            "complete_square_brackets":"\\begin{bmatrix}" in compact or ("\\left[" in compact and "\\right]" in compact)}
    if "controls-pictures-1" in outputs:
        math = helper.output_text(outputs["controls-pictures-1"])
        result["C01_fraction"] = {"raw":math,"complete_fraction":bool(re.search(r"\\frac\s*\{\s*1\s*\}\s*\{\s*x\s*\+\s*1\s*\}",math)) and r"\int" not in math}
    if "controls-pictures-2" in outputs:
        math = helper.output_text(outputs["controls-pictures-2"])
        result["C01_piecewise"] = {"raw":math,"two_cases_and_boundary":r"\begin{cases}" in math and math.count("\\\\")==1 and bool(re.search(r"x\s*\^\s*(?:\{\s*)?2",math)) and bool(re.search(r"x\s*(?:\\geq?|>=|≥)\s*0",math)) and bool(re.search(r"x\s*<\s*0",math))}
    if "controls-code-context" in outputs:
        output = outputs["controls-code-context"]
        case = next(c for c in read(ROOT/"docs/fixtures/pdf-core-g1-2026-10-14/cases.json")["cases"] if c["id"]=="G1-C02")
        result["C02_code"] = {"seven_lines_exact":helper.prior.source_code_exact(helper.output_text(output),case["details"]["oracle"]["code_lines"]),"block_kinds":[b["kind"] for b in output["blocks"]],"language":[b["code_language"] for b in output["blocks"]]}
    if "seal-paragraph-formula-context" in outputs:
        output = outputs["seal-paragraph-formula-context"]
        paragraphs = [b for b in output["blocks"] if b["kind"]=="paragraph"]
        text = " ".join(helper.block_text(b) for b in paragraphs)
        result["seal32"] = {"paragraph_count":len(paragraphs),"paragraph_raw":text,"model_identity_and_theta_prime_subscript_preserved":model_identity_preserved(text),
            "prime_preserved": "θ'" in normalized_math(text),
            "stray_prose_closing_brace":any("}" in (s["text"] or "") for b in paragraphs for s in b["segments"] if s["kind"]=="text"),
            "context_formula_count":sum(b["kind"]=="formula" for b in output["blocks"]),"context_formula_is_not_target_replacement":True}
    if "seal-prose-continuation" in outputs:
        output = outputs["seal-prose-continuation"]
        text = helper.output_text(output)
        doc = read(OLD/"inputs/baselines/seal/document.json")
        fragment = doc["texts"][34]["prov"][0]
        source_text = doc["texts"][34]["text"][slice(*fragment["charspan"])]+" "+doc["texts"][45]["text"]
        def words(value):
            return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",helper.prior.equivalent_surface(value).replace("’","'"))
        a,b = words(source_text),words(text)
        differences = [{"change":op,"source":a[i:j],"observed":b[k:l]} for op,i,j,k,l in SequenceMatcher(None,a,b).get_opcodes() if op!="equal"]
        result["seal34"] = {"block_count":len(output["blocks"]),"block_kinds":[b["kind"] for b in output["blocks"]],"raw":text,
            "continuation_once":text.count("are sampled from")==1 and "rewards are computed using" in text and "the current model." in text,
            "no_algorithm_caption_in_body":"Algorithm 1" not in text and "Reinforcement Learning Loop" not in text,
            "no_next_paragraph_absorbed":"We experimented with various on-policy" not in text,
            "source_model_parameters_phrase_preserved":"model parameters" in text,
            "observed_parameters_word_count":len(re.findall(r"\bparameters\b",text)),"source_parameters_word_count":2,
            "complete_source_prose_pass":a==b,"prose_word_differences":differences,
            "reference_basis":"Unchanged native34 first provenance character span plus native45, independently checked visually; no new frozen denominator.",
            "source_prose_failure":"Missing parameters before the first theta; re-sult and mis-aligned also retain line-wrap hyphens.",
            "old_current_subscripts":[s["text"] for b in output["blocks"] for s in b["segments"] if s["kind"]=="math" and ("old" in (s["text"] or "") or "current" in (s["text"] or ""))]}
    return result


def parsed_review(manifest,outputs):
    records = []
    for row in manifest["inputs"]:
        folder = WORK/"parsed"/row["id"]
        mapped,original = read(folder/"render-map.json"),read(folder/"original-blocks.json")
        markdown = (folder/"document.md").read_text()
        assert original==outputs[row["id"]] and mapped["input_metadata"]==row
        assert digest(ROOT/mapped["api_output_ref"]["path"])==mapped["api_output_ref"]["sha256"]
        assert digest(folder/"document.md")==mapped["markdown_sha256"]
        blocks = []
        for raw,rendered in zip(original["blocks"],mapped["blocks"],strict=True):
            pieces = []
            assert raw["bbox"]==rendered["model_bbox_image_pixels"]
            for segment,span in zip(raw["segments"],rendered["segments"],strict=True):
                markup = helper.expected_markup(segment,raw["kind"])
                assert span["raw_text"]==segment["text"] and span["kind"]==segment["kind"]
                assert markup==span["rendered_markup"]==markdown[slice(*span["markdown_charspan"])]
                pieces.append(markup)
            body = "".join(pieces)
            if raw["kind"]=="code":
                fence = "`"*max(3,max((len(x) for x in re.findall(r"`+",body)),default=0)+1)
                body = fence+(raw["code_language"] or "")+"\n"+body+("" if body.endswith("\n") else "\n")+fence
            elif raw["kind"]=="formula":body="$$\n"+body+"\n$$"
            else:body=("## " if raw["kind"]=="heading" else "- " if raw["kind"]=="list_item" else "")+body
            assert markdown[slice(*rendered["markdown_charspan"])]==body
            blocks.append(body)
        assert "\n\n".join(blocks)==markdown
        records.append({"id":row["id"],"original_and_entire_rendered_content_preserved":True,"segments_checked":sum(len(b["segments"]) for b in original["blocks"])})
    return {"documents_checked":len(records),"records":records,"model_content_repaired":False}


def native_boundary_errors(raw,proposal):
    errors = []
    grouped = {}
    for chunk in proposal["source_charspan_accounting"]:
        grouped.setdefault(chunk["item_ref"],[]).append(chunk)
    if set(grouped)!=set(proposal["consumed_item_refs"]):errors.append("missing consumed native item")
    for ref,chunks in grouped.items():
        text,cursor=resolve(raw,ref)["text"],0
        for chunk in sorted(chunks,key=lambda c:c["charspan"]):
            a,b=chunk["charspan"]
            if a!=cursor or text[a:b]!=chunk["exact_native_text"]:errors.append("native character coverage loss/duplication")
            cursor=b
        if cursor!=len(text):errors.append("native source suffix lost")
    first=resolve(raw,proposal["consumed_item_refs"][0]);tail=resolve(raw,proposal["consumed_item_refs"][1])
    a,b=first["prov"]
    body=first["text"][:b["charspan"][0]]+tail["text"]
    title=first["text"][slice(*b["charspan"])]
    if proposal["native_blocks"][0]["text"]!=body or proposal["native_blocks"][1]["text"]!=title:errors.append("native body/title string changed")
    expected=helper.expected_markup({"kind":"text","text":body},"paragraph")+"\n\n"+helper.expected_markup({"kind":"text","text":title},"paragraph")
    if proposal["markdown"]!=expected:errors.append("native output differs from exact source strings")
    return errors


def working_errors(raw,baseline,working,delta):
    errors,replacements,seen=[],[],set()
    picture_refs=[r.get("$ref",r.get("cref")) for r in raw["body"]["children"] if r.get("$ref",r.get("cref","")).startswith("#/pictures/")]
    picture_offsets=[m.start() for m in re.finditer(re.escape("<!-- image -->"),baseline)]
    if picture_refs and len(picture_refs)!=len(picture_offsets):return ["picture placeholder accounting mismatch"]
    pictures=dict(zip(picture_refs,picture_offsets))
    for proposal in delta["proposals"]:
        if proposal["status"]=="not_applied":continue
        for i,ref in enumerate(proposal["consumed_item_refs"]):
            if ref in seen:errors.append("duplicate consumed ref")
            seen.add(ref)
            if ref.startswith("#/pictures/"):
                original,start="<!-- image -->",pictures[ref]
            else:
                original=helper.prior.original_markdown({"provider_item":resolve(raw,ref)})
                if baseline.count(original)!=1:return errors+["missing/duplicate original native block"]
                start=baseline.index(original)
            replacements.append((start,original,proposal["markdown"] if i==0 else "",ref,proposal["id"]))
    if set(delta["working_serialization_spans"])!=seen:errors.append("serialized scope mismatch")
    rebuilt,cursor,outside="",0,[]
    for start,original,substitute,ref,identifier in sorted(replacements):
        if start<cursor:errors.append("overlapping source replacements")
        literal=baseline[cursor:start];left=len(rebuilt);rebuilt+=literal
        outside.append({"working_charspan":[left,len(rebuilt)],"sha256":sha256(literal.encode()).hexdigest()})
        left=len(rebuilt);rebuilt+=substitute
        expected={"proposal_id":identifier,"charspan":[left,len(rebuilt)],"suppressed_serialized_duplicate":not substitute}
        if delta["working_serialization_spans"].get(ref)!=expected:errors.append("wrong replacement range/order/suppression")
        cursor=start+len(original)
    literal=baseline[cursor:];left=len(rebuilt);rebuilt+=literal
    outside.append({"working_charspan":[left,len(rebuilt)],"sha256":sha256(literal.encode()).hexdigest()})
    if rebuilt!=working:errors.append("working content differs outside or inside declared substitutions")
    if outside!=delta["unchanged_outside_literal_spans"]:errors.append("outside literal/order accounting mismatch")
    return errors


def working_review(manifest,outputs):
    records=[]
    for source in ("controls","seal"):
        folder=WORK/"reinsertion"/source
        delta=read(folder/"working-delta.json")
        ref=delta["provider_document_ref"]
        assert digest(ROOT/ref["path"])==ref["sha256"]
        raw=read(ROOT/ref["path"])
        baseline,working=(folder/"baseline.md").read_text(),(folder/"working.md").read_text()
        assert baseline==(PREVIOUS/"reinsertion"/source/"baseline.md").read_text()
        errors=working_errors(raw,baseline,working,delta)
        assert not errors,(source,errors)
        for p in delta["proposals"]:
            if p["method"]=="new_API_response":assert p["all_model_blocks"]==outputs[p["id"]]
            if "original_input_metadata" in p:
                row=next(r for r in manifest["inputs"] if r["id"]==p["original_input_metadata"]["id"])
                assert p["original_input_metadata"]==row and p["consumed_item_refs"]==row["consumed_item_refs"]
            if p["status"]!="not_applied":
                offset=delta["working_serialization_spans"][p["consumed_item_refs"][0]]["charspan"][0]
                for segment in p["main_markdown_segment_offsets"]:
                    a,b=segment["markdown_charspan"]
                    assert segment["main_markdown_charspan"]==[offset+a,offset+b]
                    assert p["markdown"][a:b]==segment["rendered_markup"]==working[slice(*segment["main_markdown_charspan"])]
                    if "exact_native_text" in segment:
                        assert helper.expected_markup({"kind":"text","text":segment["exact_native_text"]},"paragraph")==segment["rendered_markup"]
        if source=="seal":
            native=next(p for p in delta["proposals"] if p["method"]=="native_boundary_fallback")
            assert not native_boundary_errors(raw,native)
            assert native["AI_transcription_used"] is False and native["math_completion_claim"] is False
            assert native["native_blocks"][1]["inferred_role_lineage"]==native["original_input_metadata"]["retained_spatial_fragment_reuse"]
            assert all(p["status"]=="not_applied" for p in delta["proposals"] if p["method"]=="new_API_response")
            assert working.count(native["native_blocks"][1]["text"])==1 and working.count(raw["texts"][45]["text"])==1
        else:
            reuse=next(p for p in delta["proposals"] if p["method"]=="prior_API_role_reuse")
            evidence=reuse["frozen_reuse_evidence"]
            assert digest(ROOT/evidence["path"])==evidence["sha256"]
            assert reuse["all_model_blocks"]==read(ROOT/evidence["path"])
            assert helper.block_text(reuse["all_model_blocks"]["blocks"][0])==raw["texts"][14]["text"]
        records.append({"source":source,"errors":errors,"serialized_refs":list(delta["working_serialization_spans"]),"entire_working_MD_reconstructed":True,"outside_order_and_literals_preserved":True})
    return {"records":records,"new_model_substitutions":4,"rejected_SEAL_model_proposals":2,"native_only_boundary_substitutions":1,"frozen_inline_role_reuse":1,
        "native34_all_characters_and_title_and_continuation_once":True,"native34_F13_completion_claim":False,
        "native32_and_context33_and_algorithm_items35_to44_unchanged":True,"raw_provider_graph_and_all_assets_unchanged":True,
        "scope":"Working Markdown overlay plus explicit provenance records, not a rewritten Docling document or general semantic approval."}


def integration_selfchecks(manifest):
    spec=importlib.util.spec_from_file_location("boundary_guard_under_review",WORK/"reinsertion/apply.py")
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    controls={}
    def rejected(name,function):
        try:function()
        except (ValueError,KeyError,IndexError):controls[name]=True
        else:controls[name]=False
    row32=next(r for r in manifest["inputs"] if r["context_only_refs"])
    seal=read(ROOT/row32["baseline_document_ref"]["path"])
    native32=seal["texts"][32]["text"]
    good=deepcopy(read(WORK/"api"/row32["id"]/"output.json")["blocks"][0])
    bad_segment=next(s for s in good["segments"] if (s["text"] or "").startswith("L_{"))
    bad_segment["text"]=r"\mathrm{LM}_{\theta'}"
    guard.conservation(native32,good)
    bad=deepcopy(good);next(s for s in bad["segments"] if (s["text"] or "").startswith(r"\mathrm{LM}"))["text"]=r"L_{M_{\theta'}}"
    rejected("producer_balanced_wrong_identifier",lambda:guard.conservation(native32,bad))
    cells=read(ROOT/manifest["native_cells_ref"]["path"])
    actual=guard.model_proposal(seal,row32,cells)
    controls["producer_context_cannot_mask_wrong_target"]=actual["status"]=="not_applied" and "LM" in actual["reason"]
    row=next(r for r in manifest["inputs"] if r["id"]=="controls-code-context")
    raw=read(ROOT/row["baseline_document_ref"]["path"])
    code=read(WORK/"api"/row["id"]/"output.json")["blocks"][0]
    guard.code_guard(raw,row,code,cells)
    source=helper.block_text(code)
    for name,text in (("producer_code_operator",source.replace("<=","<")),("producer_code_indent",source.replace('        emit("ok")','    emit("ok")')),("producer_duplicated_comment",source.splitlines()[0]+"\n"+source)):
        block={**code,"segments":[{"kind":"code","text":text}]}
        rejected(name,lambda block=block:guard.code_guard(raw,row,block,cells))
    plans=read(WORK/"reinsertion/plan.json")["rows"]
    plan32=next(p for p in plans if p["id"]==row32["id"])
    rejected("producer_context_ref_consumed",lambda:guard.scope_guard(seal,plan32,plan32["consumed_item_refs"]+row32["context_only_refs"]))
    badraw=deepcopy(seal);badraw["texts"][0]["parent"]={"$ref":"#/texts/999"}
    rejected("producer_outside_graph_mutation",lambda:guard.scope_guard(badraw,plan32,plan32["consumed_item_refs"]))
    delta=read(WORK/"reinsertion/seal/working-delta.json")
    native=next(p for p in delta["proposals"] if p["method"]=="native_boundary_fallback")
    for name in ("native_character_drop","native_continuation_duplicate","native_title_loss"):
        bad=deepcopy(native)
        if name=="native_character_drop":bad["source_charspan_accounting"][0]["charspan"][1]-=1
        if name=="native_continuation_duplicate":bad["source_charspan_accounting"].append(deepcopy(bad["source_charspan_accounting"][2]))
        if name=="native_title_loss":bad["native_blocks"][1]["text"]="truncated"
        controls[name]=bool(native_boundary_errors(seal,bad))
    folder=WORK/"reinsertion/seal";baseline=(folder/"baseline.md").read_text();working=(folder/"working.md").read_text()
    controls["outside_markdown_drop"]=bool(working_errors(seal,baseline,working[1:],delta))
    folder=WORK/"reinsertion/controls";d=read(folder/"working-delta.json");baseline=(folder/"baseline.md").read_text();working=(folder/"working.md").read_text()
    controls["duplicate_code_in_working"]=bool(working_errors(raw,baseline,working+source,d))
    # This explicitly records a limit: occurrence coverage is not mathematical equivalence.
    no_prime=deepcopy(good);next(s for s in no_prime["segments"] if (s["text"] or "").startswith(r"\mathrm{LM}"))["text"]=r"\mathrm{LM}_{\theta}"
    guard.conservation(native32,no_prime)
    assert not model_identity_preserved(helper.block_text(no_prime))
    assert all(controls.values()),controls
    return {"all_rejected":True,"controls":controls,"producer_guard_sha256":digest(WORK/"reinsertion/apply.py"),
        "explicit_limit":"Correct LM with missing prime still passes the producer Latin-occurrence guard; reviewer semantic predicate rejects it. Guard is not general math equivalence or semantic approval."}


def selfchecks(manifest):
    row = manifest["inputs"][0]
    doc = read(ROOT/row["baseline_document_ref"]["path"])
    assert not crop_errors(row,doc)
    controls = {}
    for name in ("clipped_parent_right","wrong_crop_rounding","wrong_inverse_map","wrong_physical_page"):
        bad = deepcopy(row); f = bad["source_fragments"][0]
        if name=="clipped_parent_right":f["bbox_top_left_points"][2]-=20
        if name=="wrong_crop_rounding":f["crop_pixel_box"][0]+=1
        if name=="wrong_inverse_map":f["canvas_pixels_to_source_top_left_points_3x3"][0][2]+=1
        if name=="wrong_physical_page":f["physical_page_1based"]=2
        controls[name]=bool(crop_errors(bad,doc))
    assert model_identity_preserved(r"\mathrm{LM}_{\theta'}")
    controls["balanced_but_wrong_model_identity"]=not model_identity_preserved(r"L_{M_{\theta'}}")
    controls["lost_theta_prime"]=not model_identity_preserved(r"\mathrm{LM}_{\theta}")
    bad = deepcopy(row);bad["member_item_refs"]=[]
    controls["missing_formula_child_accounting"]=bool(crop_errors(bad,doc))
    bad = deepcopy(row);bad["context_only_refs"]=bad["consumed_item_refs"][:]
    controls["consuming_context_only_ref"]=bool(crop_errors(bad,doc))
    masked = {"blocks":[{"kind":"paragraph","segments":[{"kind":"math","text":r"L_{M_{\theta'}}"}]},{"kind":"formula","segments":[{"kind":"math","text":r"\mathrm{LM}_{\theta'}"}]}]}
    controls["correct_context_cannot_mask_wrong_target_identity"]=not target_model_identity(masked)
    assert all(controls.values()),controls
    return {"all_rejected":True,"controls":controls,"scope":"Reviewer in-memory controls, not a producer semantic guarantee."}


def main():
    manifest = read(WORK/"inputs/input-manifest.json")
    input_result = inputs_review(manifest)
    observations = {r["name"]:r for r in read(WORK/"api/observations.json")} if (WORK/"api/observations.json").exists() else {}
    runs,outputs = [],{}
    for row in manifest["inputs"]:
        run,output = run_review(row,observations); runs.append(run)
        if output is not None:outputs[row["id"]]=output
    result = {"format":"g2-inline-boundary-independent-review-v1","input_manifest_sha256":digest(WORK/"inputs/input-manifest.json"),"checker_sha256":digest(__file__),
        "inputs":input_result,"completed_runs":len(outputs),"expected_runs":6,"runs":runs,"semantics":semantic_review(outputs),"selfchecks":selfchecks(manifest)}
    if len(outputs)==6 and (WORK/"reinsertion/summary.json").exists():
        result.update(parsed=parsed_review(manifest,outputs),working=working_review(manifest,outputs),integration_selfchecks=integration_selfchecks(manifest))
        result["selfchecks"]["controls"].update(result["integration_selfchecks"]["controls"])
    result["negative_control_count"]=len(result["selfchecks"]["controls"])
    save("output-review.json",result)
    print(json.dumps({"inputs":6,"completed":len(outputs),"negative_controls":len(result["selfchecks"]["controls"]),"input_pixels_and_geometry":"passed"}))


if __name__=="__main__":
    main()
