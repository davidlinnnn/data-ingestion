"""Source-preserving, relocatable packaging; no provider execution."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil

from PIL import Image
from docling_core.types.doc import DoclingDocument, ImageRef, ImageRefMode
import method as m


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def export(doc, settings):
    return m.GroupMarkdownSerializer(doc=doc,reconstructed_captions=set(settings["typed_caption_refs"])).serialize(
        image_mode=ImageRefMode.REFERENCED,allowed_meta_names=set(),include_annotations=False).text


def save(destination, production, baseline_path, result, C_scope=None, C_payloads=None):
    destination=Path(destination);destination.mkdir(parents=True)
    doc=DoclingDocument.model_validate(result["document"])
    raw=read(baseline_path)
    views={v["asset"]:v for v in result["binding"]["group"]["views"]}
    images=[] if C_scope is None else C_scope["images"]
    if C_scope:
        for v in C_scope["views"]:
            if v["asset"] in views and views[v["asset"]]["sha256"]!=v["sha256"]:
                raise ValueError("same asset path, different source pixels")
            views[v["asset"]]=v
    for asset,view in views.items():
        path=destination/asset;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(Path(production)/asset,path)
        if sha(path)!=view["sha256"]:raise ValueError("changed context asset")
    for record in images:
        asset=record["asset"];path=destination/asset;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(Path(production)/asset,path)
        if sha(path)!=record["crop_sha256"]:raise ValueError("changed original crop")
        picture=m.old.resolve(doc,record["owner_ref"])
        source=m.old.resolve(DoclingDocument.model_validate(raw),record["owner_ref"])
        if picture.prov!=source.prov:raise ValueError("picture source mapping changed")
        with Image.open(path) as image:
            reference=ImageRef.from_pil(image,dpi=144)
        reference.uri=Path(asset)
        picture.image=reference
    shutil.copyfile(baseline_path,destination/"source.json")
    write(destination/"document.json",doc.export_to_dict())
    markdown=export(doc,result["serialization"])
    (destination/"document.md").write_text(markdown)
    source_records=[r["source"] for r in read(Path(production)/"inventory.json")["ranges"]
        if (m.ROOT/r["baseline"]).resolve()==Path(baseline_path).resolve()]
    if not source_records or len({r["sha256"] for r in source_records})!=1:
        raise ValueError("ambiguous source PDF identity")
    metadata={"source_file_sha256":sha(baseline_path),"source_revision":m.digest(raw),
        "source_pdf":source_records[0],
        "binding":result["binding"],"serialization":result["serialization"],
        "images":deepcopy(images),"views":list(views.values()),"model_calls":0,
        "source_quality_verified":False,"raw_response":result["raw_response"]}
    write(destination/"binding.json",metadata)
    if C_scope:
        write(destination/"supplement.json",m.supplement(raw,C_scope,C_payloads))
    write(destination/"integrity.json",{str(p.relative_to(destination)):sha(p)
        for p in destination.rglob("*") if p.is_file()})
    return markdown


def verify(directory, expected_revision):
    root=Path(directory).resolve()
    for name,expected in read(root/"integrity.json").items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or sha(path)!=expected:
            raise ValueError("missing/changed/foreign bundle dependency")
    metadata=read(root/"binding.json");raw=read(root/"source.json")
    if (metadata["source_revision"]!=expected_revision or m.digest(raw)!=expected_revision
            or sha(root/"source.json")!=metadata["source_file_sha256"]):
        raise ValueError("foreign source revision")
    doc=DoclingDocument.load_from_json(root/"document.json")
    if export(doc,metadata["serialization"]).encode()!=(root/"document.md").read_bytes():
        raise ValueError("reloaded Markdown differs")
    for record in metadata["images"]:
        picture=m.old.resolve(doc,record["owner_ref"])
        if str(picture.image.uri)!=record["asset"]:raise ValueError("image reference changed")
        path=(root/record["asset"]).resolve()
        if not path.is_relative_to(root):raise ValueError("image path escaped bundle")
        runtime=picture.image.model_copy(update={"uri":path})
        if runtime.pil_image.size!=(picture.image.size.width,picture.image.size.height):
            raise ValueError("runtime image decode changed")
    if (root/"supplement.json").exists():
        supplement=read(root/"supplement.json")
        if supplement["document_revision"]!=expected_revision:raise ValueError("foreign supplement")
        if {r["image"]["image_key"] for r in supplement["images"]}!={r["image_key"] for r in metadata["images"]}:
            raise ValueError("supplement image identity mismatch")
    return {"json_reload":True,"markdown_byte_reproduction":True,
        "runtime_images_decoded":len(metadata["images"]),"source_revision":expected_revision,
        "model_calls":0,"source_quality_verified":False}
