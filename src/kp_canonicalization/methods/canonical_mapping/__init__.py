"""canonical-mapping: the Processing Result of a paper PDF mapped to its Canonical content,
the validation of that content, and the completeness rule a result must pass first
(docs/design/knowledge-platform-canonical-content-spec.md; #81, #57 B2, B7, B9).

A method without inventory items, like docling-parse: the profile lists it so that its version
and module digest are the Processing Profile's (spec §8), and finalize runs it.

    incomplete(failed, unjudged) -> ProcessingFailure | None   the completeness rule
    content_key(document_uid, request_id) -> str               the content object's key
    build(result, document, store) -> dict                     the content (spec §3, §4)
    validate(content, result, document, store) -> None         spec §6; raises ProcessingFailure
"""

import re
from collections import Counter
from pathlib import PurePosixPath
from typing import Any, Literal

from docling_core.types.doc.document import DoclingDocument
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from kp_canonicalization.ports.object_store import ObjectNotFound, ObjectStore
from kp_canonicalization.stages import ProcessingFailure, sha256

ID = "canonical-mapping"
VERSION = 1
SCHEMA = "canonical-content/v1"
REFERENCE = re.compile(r"[0-9a-f]{64}(/[A-Za-z0-9_-][A-Za-z0-9._-]*)+")  # spec §4
MEDIA_TYPES = {".png": "image/png", ".json": "application/json"}
NATIVE = ("texts", "tables", "pictures", "key_value_items", "form_items")  # every native node
OMITTED = {"furniture": "FURNITURE"}
KEPT = ("item_id", "method_ref", "scope", "origin", "target_refs", "content", "status", "signals")
REVISION = ("document_uid", "source_revision_id", "request_id", "adopted_version",
            "adoption_sequence")  # fmt: skip  # content layer -> the §3.4 rule that leaves it out


def incomplete(
    failed: list[tuple[str, str]], unjudged: list[tuple[str, str]]
) -> ProcessingFailure | None:
    """The failure of a Document with a missing result (#57 B7, B9), given (item_id, reason) of
    each failed enrichment and of each check without a judgement; None when there is none."""
    missing = failed or unjudged
    if not missing:
        return None
    # Only an unanswered result is never registered; a rerun reuses any other and fails again.
    transient = all(reason == "SERVICE_UNAVAILABLE" for _, reason in failed + unjudged)
    return ProcessingFailure(
        "platform",
        "platform" if transient else "method",
        "ENRICHMENT_INCOMPLETE" if failed else "QUALITY_CHECK_INCOMPLETE",
        "An Enrichment item has no result" if failed else "A Quality Check has no judgement",
        retryable=transient,
        metadata={
            "failed": str(len(failed)),
            "not_run": str(len(unjudged)),
            "item_id": missing[0][0],
        },
    )


def revision_id(request_id: str) -> str:
    """crv_ and the request id's 32 hex digits (#57 B3)."""
    return f"crv_{request_id.removeprefix('req_')}"


def content_key(document_uid: str, request_id: str) -> str:
    return f"documents/{document_uid}/revisions/{revision_id(request_id)}.json"


def _invalid(check: str, detail: str) -> ProcessingFailure:
    """Spec §6: the inputs are registered and reused, so a rerun fails the same way."""
    return ProcessingFailure(
        "platform",
        "method",
        "CANONICAL_INVALID",
        f"Canonical content failed its {check} check",
        metadata={"check": check, "detail": detail},
    )


def _mismatch(ref: str) -> ProcessingFailure:
    """Spec §6: a repaired store passes on a rerun."""
    return ProcessingFailure(
        "platform",
        "integrity",
        "ARTIFACT_MISMATCH",
        "An artifact of the Canonical content is missing or differs from its manifest entry",
        retryable=True,
        metadata={"check": "ARTIFACT", "detail": ref},
    )


def _resolve(document: dict[str, Any], ref: str) -> dict[str, Any]:
    _, collection, *index = ref.split("/")  # "#/body" or "#/texts/3"
    return document[collection][int(index[0])] if index else document[collection]


def _collection(ref: str) -> str:
    return ref.split("/")[1]


def _native_text(node: dict[str, Any]) -> tuple[str, bool]:
    """docling's text, or its orig when text is empty; and whether orig had to stand in (#84)."""
    if node["text"]:
        return node["text"], False
    return node.get("orig") or "", bool(node.get("orig"))


def _locators(node: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"page": p["page_no"], "bbox": {**p["bbox"], "unit": "pt"}} for p in node["prov"]]


async def build(result: dict[str, Any], document: dict[str, Any], store: ObjectStore) -> dict:
    """The content of `result` (a Processing Result whose enrichments carry their whole content)
    over its assembly's docling `document`, spec §3 and §4. Reads the size of each artifact;
    a missing one raises ProcessingFailure ARTIFACT_MISMATCH."""
    request, native = result["request"], result["native"]
    prefix = f"documents/{request['document_uid']}/items/"
    artifacts: dict[str, dict[str, Any]] = {}

    async def artifact(key: str, kind: str, declared: str | None = None) -> str:
        ref = key.removeprefix(prefix)  # a key outside the prefix stays whole: REFERENCE_FORM
        if ref not in artifacts:
            if declared:
                size, digest = await store.head(key), declared
            else:
                try:
                    data = await store.get(key)
                except ObjectNotFound:
                    raise _mismatch(ref) from None
                size, digest = len(data), sha256(data)
            if size is None:
                raise _mismatch(ref)
            media = MEDIA_TYPES.get(PurePosixPath(ref).suffix, "application/octet-stream")
            artifacts[ref] = {"ref": ref, "kind": kind, "media_type": media,
                              "sha256": digest, "size": size}  # fmt: skip
        return ref

    targeting: dict[str, Any] = {}  # "<target> <method id>" -> its enrichment's content
    for e in result["enrichments"]:
        for target in e["target_refs"]:
            targeting[f"{target} {e['method_ref']['id']}"] = e["content"]
    pictures = {p["picture_id"]: p for p in native["picture_images"]}
    docling: list[DoclingDocument] = []  # parsed once, only for a document with tables

    def table_markdown(ref: str) -> str:
        if not docling:
            docling.append(DoclingDocument.model_validate(document))
        table = docling[0].tables[int(ref.rsplit("/", 1)[1])]
        # Its captions and footnotes are blocks of their own; exported here they would repeat.
        bare = table.model_copy(update={"captions": [], "footnotes": []})
        spans = any(c.row_span > 1 or c.col_span > 1 for c in table.data.table_cells)
        return bare.export_to_html(docling[0]) if spans else bare.export_to_markdown(docling[0])

    def text_markdown(ref: str, node: dict[str, Any], text: str) -> str:
        match node["label"]:
            case "title":
                return f"# {text}"
            case "section_header":
                return f"{'#' * min(node.get('level', 1) + 1, 6)} {text}"
            case "list_item":
                return f"- {text}"
            case "formula":
                return f"$$\n{targeting.get(f'{ref} formula', text)}\n$$"
            case "code":
                return f"```\n{targeting.get(f'{ref} code', text)}\n```"
        return text

    blocks: list[dict[str, Any]] = []

    def body(node: dict[str, Any]) -> bool:
        return node.get("content_layer", "body") == "body"

    async def visit(ref: str) -> None:
        node = _resolve(document, ref)
        if not body(node):
            return  # listed in omitted
        collection = _collection(ref)
        later = [child["$ref"] for child in node.get("children", [])]
        if collection == "groups":  # a container (a list, an inline group), not delivered
            for child in later:
                await visit(child)
            return
        block: dict[str, Any] = {"ref": ref, "kind": node["label"], "locators": _locators(node)}
        if collection == "texts":
            text, uncertain = _native_text(node)
            block |= {"text": text, "role_uncertain": uncertain,
                      "markdown": text_markdown(ref, node, text)}  # fmt: skip
        elif collection == "tables":
            block["markdown"] = table_markdown(ref)
        elif collection == "pictures":
            picture = pictures.get(ref)
            image = None
            if picture:
                image = await artifact(picture["ref"], "picture_image", picture["sha256"])
            # Text docling placed inside the picture is native text of the picture, not body.
            attached = {c["$ref"] for c in node.get("captions", []) + node.get("footnotes", [])}
            inside: list[dict[str, Any]] = []
            later = []

            def collect(child: str) -> None:
                found = _resolve(document, child)
                own = _collection(child) in ("tables", "pictures")
                if child in attached or own or not body(found):
                    later.append(child)
                    return
                if _collection(child) == "texts":
                    text, uncertain = _native_text(found)
                    inside.append({"ref": child, "text": text, "role_uncertain": uncertain,
                                   "locators": _locators(found)})  # fmt: skip
                for grandchild in found.get("children", []):
                    collect(grandchild["$ref"])

            for child in node.get("children", []):
                collect(child["$ref"])
            block |= {"image": image, "native_text": inside,
                      "markdown": f"![]({image})" if image else ""}  # fmt: skip
        else:
            block["markdown"] = ""
        blocks.append(block)
        for child in later:
            await visit(child)

    for child in document["body"]["children"]:
        await visit(child["$ref"])

    pages = []
    for image in native["page_images"]:
        size = document["pages"][str(image["page"])]["size"]
        ref = await artifact(image["ref"], "page_image", image["sha256"])
        pages.append({"page": image["page"], "width": size["width"], "height": size["height"],
                      "image": ref})  # fmt: skip
    enrichments = []
    for e in result["enrichments"]:
        enrichments.append(
            {key: e[key] for key in KEPT}
            | {
                "status_reason": e["status_reason"] or "",
                "evidence_refs": [await artifact(key, "evidence") for key in e["evidence_refs"]],
            }
        )
    profile = result["profile"]
    return {
        "schema": SCHEMA,
        "revision": {"canonical_revision_id": revision_id(request["request_id"])}
        | {key: request[key] for key in REVISION},
        "source_files": [
            {key: f[key] for key in ("role", "sha256", "size", "media_type")}
            for f in request["files"]
        ],
        "processing": {
            "profile": profile["id"],
            "status_rule": profile["status_rule"],
            "methods": profile["methods"],
            "runtime_identity": profile["runtime_identity"],
        },
        "pages": pages,
        "blocks": blocks,
        "enrichments": enrichments,
        "limitations": result["limitations"],
        "omitted": [
            {"ref": node["self_ref"], "reason": OMITTED[layer]}
            for collection in NATIVE
            for node in document.get(collection, [])
            if (layer := node.get("content_layer", "body")) in OMITTED
        ],
        "artifacts": sorted(artifacts.values(), key=lambda a: a["ref"]),
    }


# --- the schema (spec §3) -----------------------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Box(_Model):
    l: float  # noqa: E741  docling's names
    t: float
    r: float
    b: float
    coord_origin: Literal["BOTTOMLEFT", "TOPLEFT"]
    unit: Literal["pt"]


class _Locator(_Model):
    page: StrictInt = Field(ge=1)
    bbox: _Box


class _NativeText(_Model):
    ref: StrictStr
    text: StrictStr
    role_uncertain: StrictBool
    locators: list[_Locator]


_BY_COLLECTION = {"texts": {"text", "role_uncertain"}, "pictures": {"image", "native_text"}}


class _Block(_Model):
    ref: StrictStr
    kind: StrictStr
    locators: list[_Locator]
    markdown: StrictStr
    text: StrictStr | None = None
    role_uncertain: StrictBool | None = None
    image: StrictStr | None = None
    native_text: list[_NativeText] | None = None

    @model_validator(mode="after")
    def _fields_of_its_collection(self) -> "_Block":
        wanted = _BY_COLLECTION.get(_collection(self.ref), set())
        given = self.model_fields_set & {"text", "role_uncertain", "image", "native_text"}
        if given != wanted or any(getattr(self, name) is None for name in wanted):
            raise ValueError(f"{self.ref}: fields {sorted(given)}, expected {sorted(wanted)}")
        return self


class _Page(_Model):
    page: StrictInt = Field(ge=1)
    width: float
    height: float
    image: StrictStr


class _MethodRef(_Model):
    id: StrictStr
    version: StrictInt
    digest: StrictStr


class _Enrichment(_Model):
    item_id: StrictStr
    method_ref: _MethodRef
    scope: Literal["item", "document"]
    origin: Literal["reconstruction", "interpretation"]
    target_refs: list[StrictStr] = Field(min_length=1)
    content: Any
    evidence_refs: list[StrictStr]
    status: Literal["unverified", "disputed"]  # no verified in v1; no failed when accepted
    status_reason: StrictStr
    signals: dict[str, Any]


class _Revision(_Model):
    canonical_revision_id: StrictStr
    document_uid: StrictStr
    source_revision_id: StrictStr
    request_id: StrictStr
    adopted_version: StrictStr
    adoption_sequence: StrictInt


class _SourceFile(_Model):
    role: StrictStr
    sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    size: StrictInt = Field(ge=0)
    media_type: StrictStr


class _Method(_Model):
    id: StrictStr
    version: StrictInt
    components: list[StrictStr]
    module_digest: StrictStr


class _Runtime(_Model):
    python: StrictStr
    docling_slim: StrictStr
    build_id: StrictStr


class _Processing(_Model):
    profile: StrictStr
    status_rule: StrictStr
    methods: list[_Method]
    runtime_identity: _Runtime


class _Limitation(_Model):
    code: StrictStr
    scope: Literal["profile", "document"]
    detail: StrictStr


class _Omitted(_Model):
    ref: StrictStr
    reason: Literal["FURNITURE"]


class _Artifact(_Model):
    ref: StrictStr
    kind: Literal["page_image", "picture_image", "evidence"]
    media_type: StrictStr
    sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    size: StrictInt = Field(ge=0)


class _Content(_Model):
    schema_: Literal["canonical-content/v1"] = Field(alias="schema")
    revision: _Revision
    source_files: list[_SourceFile]
    processing: _Processing
    pages: list[_Page]
    blocks: list[_Block]
    enrichments: list[_Enrichment]
    limitations: list[_Limitation]
    omitted: list[_Omitted]
    artifacts: list[_Artifact]


# --- validation (spec §6) -----------------------------------------------------------------


async def validate(
    content: dict[str, Any], result: dict[str, Any], document: dict[str, Any], store: ObjectStore
) -> None:
    """Spec §6, in its order. Reads the content, the docling document and the stored objects,
    never the mapper's intermediate values. Raises ProcessingFailure CANONICAL_INVALID, or
    ARTIFACT_MISMATCH for the ARTIFACT check."""
    try:
        _Content.model_validate(content)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.errors()[0]["loc"])
        raise _invalid("SCHEMA", location) from None

    blocks, enrichments = content["blocks"], content["enrichments"]
    used = [page["image"] for page in content["pages"]]
    used += [block["image"] for block in blocks if "image" in block]
    used += [ref for e in enrichments for ref in e["evidence_refs"]]
    listed = [entry["ref"] for entry in content["artifacts"]]
    for ref in used + listed:
        if not REFERENCE.fullmatch(ref):
            raise _invalid("REFERENCE_FORM", ref)
    if set(used) != set(listed) or len(set(listed)) != len(listed):
        raise _invalid("REFERENCE_UNLISTED", ", ".join(sorted(set(used) ^ set(listed))))

    refs = [block["ref"] for block in blocks]
    if len(set(refs)) != len(refs):
        raise _invalid("REFERENCE_UNRESOLVED", "a block ref repeats")
    targets = {target for e in enrichments for target in e["target_refs"]}
    # A code or formula docling placed inside a picture stays the picture's native text.
    inner = {i["ref"] for block in blocks for i in block.get("native_text", [])}
    if unknown := targets - set(refs) - inner - {"#"}:
        raise _invalid("REFERENCE_UNRESOLVED", min(unknown))
    sections = set()
    for e in enrichments:
        if e["method_ref"]["id"] == "document-summary" and isinstance(e["content"], dict):
            sections |= {s["section_id"] for s in e["content"]["sections"]}
            sections |= {x["section_id"] for o in e["content"]["overview"] for x in o["evidence"]}
    if unknown := sections - set(refs) - {"#/body"}:
        raise _invalid("REFERENCE_UNRESOLVED", min(unknown))
    if untargeted := {r for r in refs if _collection(r) in ("tables", "pictures")} - targets:
        raise _invalid("REFERENCE_UNRESOLVED", min(untargeted))

    delivered = {block["ref"]: block for block in blocks}
    delivered |= {inner["ref"]: inner for block in blocks for inner in block.get("native_text", [])}
    count = Counter(refs + [i["ref"] for b in blocks for i in b.get("native_text", [])])
    if twice := [ref for ref, n in count.items() if n > 1]:
        raise _invalid("COVERAGE", min(twice))
    nodes = {n["self_ref"]: n for c in NATIVE for n in document.get(c, [])}
    omitted = {o["ref"]: o["reason"] for o in content["omitted"]}
    for ref, node in nodes.items():
        if (ref in delivered) == (ref in omitted):
            raise _invalid("COVERAGE", ref)
        if ref in omitted and OMITTED.get(node.get("content_layer", "body")) != omitted[ref]:
            raise _invalid("COVERAGE", ref)
        if ref in delivered and _collection(ref) == "texts":
            if delivered[ref]["text"] != _native_text(node)[0]:
                raise _invalid("COVERAGE", ref)
    if extra := (set(delivered) | set(omitted)) - set(nodes):
        raise _invalid("COVERAGE", min(extra))

    native = result["native"]
    declared = {i["ref"]: i["sha256"] for i in native["page_images"] + native["picture_images"]}
    prefix = f"documents/{content['revision']['document_uid']}/items/"
    for entry in content["artifacts"]:
        key = prefix + entry["ref"]
        try:
            data = await store.get(key)
        except ObjectNotFound:
            raise _mismatch(entry["ref"]) from None
        if (sha256(data), len(data)) != (entry["sha256"], entry["size"]) or declared.get(
            key, entry["sha256"]
        ) != entry["sha256"]:
            raise _mismatch(entry["ref"])
