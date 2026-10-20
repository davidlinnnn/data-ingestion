"""Stage evidence gallery: native drawing APIs and saved crops, zero model calls."""
import hashlib
import json
from pathlib import Path
import random
import shutil
from types import SimpleNamespace

import numpy as np
import cv2
from PIL import Image
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import Cluster, InputFormat, Page
from docling.datamodel.document import ConversionResult, InputDocument
from docling.datamodel.settings import DocumentLimits, settings
from docling.models.base_ocr_model import BaseOcrModel
from docling.models.stages.page_preprocessing.page_preprocessing_model import PagePreprocessingModel, PagePreprocessingOptions
from docling.utils.visualization import draw_clusters, draw_clusters_and_cells_side_by_side
from docling_core.types.doc import BoundingBox, Size
from docling_core.types.doc.page import TextCell
from rapidocr.utils.vis_res import VisRes

HERE = Path(__file__).resolve().parent
TRACE = HERE.parent / "pdf-core-ocr-boundary-trace-2026-10-19"
ABLATION = HERE.parent / "pdf-core-ocr-crop-ablation-2026-10-19"
INTERNAL = ABLATION / "A/trace"
READER = INTERNAL / "reader-001"
SOURCE = HERE.parent / "pdf-core-native-round-2026-10-17/inputs/scan-p1.png"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    out = HERE / "output/stages"
    out.mkdir(exist_ok=True)
    assets = out / "assets"
    assets.mkdir(exist_ok=True)
    inputs = {}

    def read(path):
        inputs[str(path.resolve())] = sha(path)
        return json.loads(path.read_text())

    def image(path, label):
        inputs[str(path.resolve())] = sha(path)
        target = assets / (sha(path)+".png")
        if not target.exists():
            shutil.copyfile(path, target)
        with Image.open(target) as im:
            im.verify()
        return {"src": "assets/"+target.name, "alt": label, "label": label}

    def native(name, painter):
        target = out / name
        canvas = background.copy()
        painter(canvas)
        canvas.save(target)
        return {"src": name, "alt": name}

    background = Image.open(SOURCE).convert("RGB")
    assert background.size == (1224, 1584)
    raw = read(TRACE / "live/trace/layout-clusters-001.json")
    before = read(TRACE / "live/trace/layout-before-postprocess-001.json")[0]
    post = read(TRACE / "live/trace/layout-after-postprocess-001.json")[0]
    dedup = read(TRACE / "live/trace/ocr-dedup-001.json")
    engine = read(TRACE / "live/trace/ocr-engine-001.json")
    premerge = read(TRACE / "live/trace/ocr-cells-before-merge-001.json")
    merged = read(TRACE / "live/trace/ocr-cells-after-merge-001.json")
    saved = read(TRACE / "live/result.json")
    det = read(READER / "detector-crops.json")
    preprocessing = read(READER / "preprocess.json")
    cls = read(READER / "classify.json")
    rec = read(READER / "recognize.json")
    final = read(READER / "result.json")
    profile = read(TRACE / "registration.json")["effective_options"]
    reader_config = read(ABLATION / "A/reader-config.json")
    classifier_threshold = reader_config["Cls"]["cls_thresh"]
    assert all(read(ABLATION / "A/reproduction.json").values())
    assert final["boxes"] == engine["boxes"] and final["txts"] == engine["texts"] and final["scores"] == engine["scores"]
    assert raw["clusters"] == before["clusters"] and len(raw["clusters"]) == 22
    assert premerge == merged and len(merged) == len(det["boxes"]) == 114
    assert len(post["clusters"]) == len(saved["assembled"]["elements"]) == 13
    assert cls["after"] == rec["inputs"] and len(cls["labels"]) == 114
    assert preprocessing["input"]["pixel_sha256"] == engine["input_pixel_sha256"]
    assert dedup["dilation_size"] == 20 and classifier_threshold == .9
    assert profile["do_table_structure"] and not any(profile[key] for key in
        ("do_formula_enrichment", "do_code_enrichment", "do_picture_description", "do_picture_classification", "do_chart_extraction"))

    # Re-enter only the native PDF preprocessing/debug stage; no model initialization.
    source_pdf = Path(saved["input"]["file"])
    inputs[str(source_pdf)] = sha(source_pdf)
    in_doc = InputDocument(source_pdf, format=InputFormat.PDF, backend=PyPdfiumDocumentBackend,
        limits=DocumentLimits(page_range=(1, 1)))
    conv = ConversionResult(input=in_doc)
    page = Page(page_no=1)
    page._backend = in_doc._backend.load_page(0)
    page.size = page._backend.get_size()
    previous_path, previous_cells = settings.debug.debug_output_path, settings.debug.visualize_cells
    try:
        settings.debug.debug_output_path = str(out)
        settings.debug.visualize_cells = True
        page = list(PagePreprocessingModel(options=PagePreprocessingOptions(images_scale=2,
            capture_reading_order_separators=True))(conv, [page]))[0]
        assert not page.cells and not page.parsed_page.char_cells and not page.parsed_page.word_cells
        pdf_counts = {"native_textline_cells": len(page.cells), "char_cells": len(page.parsed_page.char_cells),
            "word_cells": len(page.parsed_page.word_cells), "bitmap_regions": sum(1 for _ in page._backend.get_bitmap_rects())}
    finally:
        settings.debug.debug_output_path, settings.debug.visualize_cells = previous_path, previous_cells
        page._backend.unload()
        in_doc._backend.unload()
    pdf_image = {"src": "debug_scan-pages-3-5/cells_page_00001.png", "alt": "Docling 原生 PDF cell debug；綠框是整頁 bitmap"}
    assert (out / pdf_image["src"]).exists()

    raw_clusters = [Cluster.model_validate(v) for v in raw["clusters"]]
    post_clusters = [Cluster.model_validate(v) for v in post["clusters"]]
    raw_image = native("heron-raw.png", lambda im: draw_clusters(im, raw_clusters, 2., 2.))
    post_image = native("layout-postprocessed.png", lambda im: draw_clusters(im, post_clusters, 2., 2.))
    size = Size.model_validate(raw["page_size"])
    rects = [BoundingBox.model_validate(v) for v in dedup["rects"]]
    previous_path = settings.debug.debug_output_path
    try:
        for name, cells in (("ocr-regions", []), ("ocr-cells", premerge)):
            settings.debug.debug_output_path = str(out / name)
            BaseOcrModel.draw_ocr_rects_and_cells(None, SimpleNamespace(input=SimpleNamespace(file=SOURCE)),
                SimpleNamespace(image=background, size=size, cells=[TextCell.model_validate(v) for v in cells], page_no=1), rects)
        settings.debug.debug_output_path = str(out)
        for name, clusters in (("raw", raw_clusters), ("postprocessed", post_clusters)):
            draw_clusters_and_cells_side_by_side(SOURCE,
                SimpleNamespace(image=background, size=size, page_no=1), clusters, mode_prefix=name)
    finally:
        settings.debug.debug_output_path = previous_path
    region_image = {"src": "ocr-regions/debug_scan-p1/ocr_page_00001.png", "alt": "Docling 原生 OCR 輸入區域，尚無辨識文字"}
    cell_image = {"src": "ocr-cells/debug_scan-p1/ocr_page_00001.png", "alt": "Docling 原生 OCR 文字行框；黃色裁圖／洋紅文字 cells"}

    det_path = INTERNAL / det["input"]["npy"]
    inputs[str(det_path.resolve())] = sha(det_path)
    pixels = np.load(det_path, allow_pickle=False)
    assert pixels.shape == (1984, 1440, 3)
    assert hashlib.sha256(pixels.tobytes()).hexdigest() == det["input"]["pixel_sha256"]
    # draw_dt_boxes bypasses the font-loading __call__; no font/model download.
    state = random.getstate()
    try:
        random.seed(0)
        vis = VisRes().draw_dt_boxes(pixels.copy(), np.array(det["boxes"]), scores=[float("nan")]*114)
    finally:
        random.setstate(state)
    Image.fromarray(vis).save(out / "rapidocr-detector.png")
    # Native renderer always adds a score; use index-only labels when none was retained.
    indexed = pixels.copy()
    for index, box in enumerate(det["boxes"]):
        points = np.asarray(box, dtype=np.int32)
        cv2.polylines(indexed, [points], True, (0, 100, 230), 2)
        cv2.putText(indexed, str(index), tuple(points[0]), cv2.FONT_HERSHEY_SIMPLEX,
            .6, (0, 100, 230), 2)
    Image.fromarray(indexed).save(out / "rapidocr-detector-indexed.png")
    detector_image = {"src": "rapidocr-detector-indexed.png", "alt": "保存的 detector quad 座標；檢視器只繪行號，不顯示未保存的分數"}

    def crop_image(info, label):
        return image(INTERNAL / info["preview"], label)

    branches = []
    for index in range(114):
        branches.append({"label": f"行 index={index}｜方向 {cls['labels'][index][0]}°",
            "text": f"方向分類分數：{cls['labels'][index][1]}",
            "images": [crop_image(cls["before"][index], "方向分類前：實際偵測裁圖"),
                       crop_image(cls["after"][index], "方向分類後：實際送辨識器")],
            "details": {"index_0based": index, "classifier_threshold": classifier_threshold,
                "before_equals_after": cls["before"][index]["pixel_sha256"] == cls["after"][index]["pixel_sha256"]}})
    rotation_before = np.load(INTERNAL / cls["before"][39]["npy"], allow_pickle=False)
    rotation_after = np.load(INTERNAL / cls["after"][39]["npy"], allow_pickle=False)
    assert np.array_equal(np.rot90(rotation_before, 2), rotation_after)

    native_source = "原 S0 邊界追蹤：pdf-core-ocr-boundary-trace-2026-10-19/live/trace"
    replay_source = "同源精確重播 A：pdf-core-ocr-crop-ablation-2026-10-19/A/trace/reader-001（與原 S0 boxes／texts／scores／cells 相同）"
    stages = [
        {"id": "pdf", "title": "PDFium 原生內容", "status": "影像頁；原生文字為 0", "kind": "Docling 原生 debug 視覺化",
         "source": "同一固定 PDF 的原生 preprocessing 重播；沒有模型推論", "image": pdf_image,
         "summary": "這頁是一張整頁 bitmap。PDF parser 沒有可直接取用的文字，因此後面必須 OCR。",
         "text": json.dumps(pdf_counts, ensure_ascii=False, indent=2),
         "notes": ["綠框是 bitmap；原生文字應為紅框，此頁沒有。這不是 OCR 行框。", "本圖是原生 debug 的 scale 1；其餘頁面疊圖使用你指定的 scan-p1.png。"]},
        {"id": "heron", "title": "Heron 原始候選框", "status": "22 框；未跨欄", "kind": "Docling 原生繪圖函式",
         "source": native_source+"/layout-clusters-001.json", "image": raw_image,
         "summary": "原始候選分居左右欄；含重複類型提案，並不是 22 個已確認段落。這時還沒有 OCR 字串。",
         "items": [{"label": f"cluster {c['id']}｜{c['label']}", "details": c} for c in raw["clusters"]],
         "links": [{"label": "官方雙面板 debug 圖", "href": "debug_scan-p1/raw_layout_page_00001.png"}],
         "notes": ["框旁信心來自保存的真實 cluster.confidence。候選已經過模型 threshold／後處理，不是 raw logits。", "官方雙面板按類型分組，不是文件左欄／右欄。"]},
        {"id": "ocr-regions", "title": "OCR 區域合併", "status": "第一個跨欄輸入區域", "kind": "Docling 原生 OCR debug＋實際裁圖",
         "source": native_source+"/ocr-dedup-001.json、ocr-engine-001.png", "image": region_image,
         "images": [image(TRACE / "live/trace/ocr-engine-001.png", "真正送入 RapidOCR 的 1608×2211 大裁圖")],
         "summary": "22 個 Heron 候選經大小 20 的膨脹核及連通區合併，變成 1 個跨欄框。這裡還沒有辨識文字。",
         "text": json.dumps({"dilation_kernel": 20, "candidates": 22, "regions": dedup["rects"], "scale": 3}, ensure_ascii=False, indent=2),
         "notes": ["黃色是 OCR 工作區域；不是 Heron 直接預測出的大段落。膨脹核 20 不是左右各加 20。"]},
        {"id": "ocr-preprocess", "title": "RapidOCR 影像預處理", "status": "大圖縮放後送 detector", "kind": "保存的實際影像",
         "source": replay_source+"/preprocess.json", "summary": "原 reader 圖是 1608×2211；內部預處理後是 1440×1984。後續 detector 框屬於後者座標。",
         "images": [crop_image(preprocessing["input"], "reader 輸入：1608×2211"), crop_image(preprocessing["output"], "detector 前預處理：1440×1984")],
         "text": json.dumps(preprocessing["operations"], indent=2), "notes": ["顯示保存像素，沒有為檢視頁另行裁切或放大推論。"]},
        {"id": "detector", "title": "文字行偵測與裁圖", "status": "首次形成 3 個跨欄文字行", "kind": "保存的 detector 框＋自訂行號標籤＋實際裁圖",
         "source": replay_source+"/detector-crops.json", "image": detector_image,
         "summary": "114 個後處理文字行框中，indices 3、4、15 已跨欄；此時尚未進文字辨識。選項目可看真正裁出的那一行。",
         "items": [{"label": f"detector 行 index={i}"+("｜跨欄" if i in (3,4,15) else ""),
                    "image": crop_image(c, f"detector 實際裁圖 index={i}"), "details": {"quad": det["boxes"][i], "shape": c["shape"]}}
                   for i,c in enumerate(det["crops"])],
         "links": [{"label": "原生 renderer 舊圖（含檢視器加入的 nan 佔位值）", "href": "rapidocr-detector.png"}],
         "notes": ["行號為零起算；分數未保存，所以不畫分數。舊圖的 nan 是本檢視器傳入原生 renderer 的佔位值，不是 detector 輸出異常或低信心。", "主圖使用保存的原生 quad 座標，只自訂框線與行號顯示；沒有修正偵測結果。框疊在真實 1440×1984 detector 圖上；未捕捉 raw probability map。"]},
        {"id": "orientation", "title": "文字方向分類", "status": "index39 誤轉 180°", "kind": "保存的實際前／後裁圖",
         "source": replay_source+"/classify.json", "summary": "原本完整、正向的 Background 定義首行，以 0.9755 信心被判成 180°，超過 0.9 門檻而翻轉。主圖先顯示這一行。",
         "images": [crop_image(cls["before"][39], "index39：正向原裁圖"), crop_image(cls["after"][39], "index39：實際翻轉後送辨識器")],
         "items": branches, "notes": ["這是 OCR 文字方向分類器，不是圖片內容分類器。兩圖像素已確認為精確 180° 旋轉。", "方向結果取自 S0 等值 A 重播；不是分離裁圖 B 的 0.9540。"]},
        {"id": "recognizer", "title": "文字辨識", "status": "混行／倒置圖被辨識成文字", "kind": "保存的實際辨識輸入與文字",
         "source": replay_source+"/recognize.json", "image": cell_image,
         "summary": "辨識器收到的部分圖已混入兩欄，另有倒置首行。這裡第一次產生實際字串；index39 是 Bs  a    ler。",
         "items": [{"label": f"recognizer 行 index={i}"+("｜跨欄" if i in (3,4,15) else "｜誤轉首行" if i==39 else ""),
                    "text": text, "image": crop_image(rec["inputs"][i], f"實際辨識輸入 index={i}"),
                    "details": {"recognition_score": rec["scores"][i]}}
                   for i,text in enumerate(rec["texts"])],
         "notes": ["主圖為原生 OCR cells 的頁面位置；逐項裁圖才是 recognizer 真正收到的像素。", "字串未修字、未重新排序；不是原文件原生文字層。"]},
        {"id": "merge", "title": "座標回映與 PDF／OCR 合併", "status": "114 cells 逐值不變", "kind": "Docling 原生 OCR debug＋保存文字",
         "source": native_source+"/ocr-cells-before-merge-001.json、ocr-cells-after-merge-001.json", "image": cell_image,
         "summary": "文字行已回映 PDF 頁面座標；此頁沒有原生文字衝突，合併前後 114 個 cells 完全相同，沒有在這一步引入混句。",
         "items": [{"label": f"cell index={c['index']}", "text": c["text"], "details": {"confidence": c["confidence"], "rect": c["rect"]}} for c in merged],
         "notes": ["這是原始 S0 單一 reader 的 merge 結果；不要套用分離圖 B 的 index 重編行為。"]},
        {"id": "layout-postprocess", "title": "Layout 後處理與分群", "status": "22 候選 → 13 clusters", "kind": "Docling 原生繪圖函式",
         "source": native_source+"/layout-after-postprocess-001.json", "image": post_image,
         "summary": "OCR 行被指派到區塊；cluster3 收入 11 行、cluster2 收入 17 行，包含跨欄 cells，因此這裡出現跨欄段落群。",
         "items": [{"label": f"cluster {c['id']}｜{c['label']}｜{len(c['cells'])} cells",
                    "text": "\n".join(v["text"] for v in c["cells"]), "details": {"bbox": c["bbox"], "confidence": c["confidence"]}} for c in post["clusters"]],
         "links": [{"label": "官方雙面板 postprocessed debug", "href": "debug_scan-p1/postprocessed_layout_page_00001.png"}],
         "notes": ["右側列出保存的 cluster.cells 原順序，尚未做 PageAssemble 合行。這些框不能再稱為 Heron 原始框。"]},
        {"id": "table-enrichment", "title": "表格與選配增強", "status": "本頁無表；此 S0 增強停用", "kind": "保存設定與適用範圍",
         "source": "原 S0 effective-options.json 與 result.pages[0].predictions.tablestructure", "summary": "TableFormer 雖在 profile 啟用，但此頁無表而走原生早退。Formula／code／圖片描述等在這份 S0 基線沒有啟用，無可顯示的新模型結果。",
         "text": json.dumps({"table_structure": saved["pages"][0]["predictions"]["tablestructure"],
            **{key: profile[key] for key in ("do_table_structure", "do_formula_enrichment", "do_code_enrichment",
                "do_picture_description", "do_picture_classification", "do_chart_extraction")},
            "heading_hierarchy_enabled": profile["heading_hierarchy_options"]["enabled"]}, ensure_ascii=False, indent=2),
         "notes": ["不畫假的空表格推論或公式熱圖；這不代表需求已驗收或被取消。"]},
        {"id": "assembly", "title": "PageAssemble 段落合行", "status": "for- 接上 or LLMs → foror", "kind": "保存的原生組裝前／後文字",
         "source": native_source+"/assembly-lines-002.json；result.assembled.elements", "image": post_image,
         "summary": "原生合行沿已錯的行順序，將右欄尾端 for- 與左欄 or LLMs 接成 foror。這一步擴大已有錯誤，並非唯一根因。",
         "text": "原生 sanitize_text 的保存輸入與輸出：\n"+json.dumps(read(TRACE / "live/trace/assembly-lines-002.json"), ensure_ascii=False, indent=2),
         "items": [{"label": f"assembled cluster {e['id']}｜{e['label']}", "text": e.get("text", ""), "details": {"page_no": e["page_no"]}} for e in saved["assembled"]["elements"]],
         "notes": ["主圖沿用本階段所用的 postprocessed 區塊，沒有假加閱讀箭頭；清單是組裝儲存順序，尚非最後閱讀順序。"]},
        {"id": "reading-order", "title": "最終結構與閱讀順序", "status": "沿已有混段建立順序", "kind": "Docling 原生 Layout／ReadingOrderVisualizer",
         "source": "原 S0 document.json（既有 final visualization）", "image": {"src": "../reading-order.png", "alt": "最終 DoclingDocument 區塊及紅色讀序箭頭"},
         "summary": "紅箭頭是保存文件的推定閱讀順序。此時上方兩個段落已各含左右欄文字，箭頭無法把字串還原成原句。",
         "items": [{"label": f"{t['self_ref']}｜{t['label']}｜{t['content_layer']}", "text": t["text"], "details": {"provenance": t["prov"]}} for t in saved["document"]["texts"]],
         "notes": ["這是原 S0，不是分離圖 B；B 另外證實『段落分開後仍有 ReadingOrder 錯序』，不可混成同一次輸出。", "框由 DocItem.prov 轉換 BOTTOMLEFT 座標畫出，不是原始 Heron 偵測框。"]},
        {"id": "export", "title": "Markdown／HTML 交付", "status": "原樣呈現錯誤；不再辨識", "kind": "Docling 原生輸出＋自訂檢視容器",
         "source": "原 S0 live/document.md 與既有原生 split-page HTML", "summary": "這一步只序列化既有結構；混句與 foror 都已在上游形成。右側是保存的 Markdown 原文。",
         "text": (TRACE / "live/document.md").read_text(),
         "links": [{"label": "Docling 原生左右對照 HTML", "href": "../source-and-parsed.html"}, {"label": "最終區塊框 PNG", "href": "../final-layout.png"}],
         "notes": ["此檢視頁本身不是 Docling 官方全流程 viewer；每張圖與每段文字都標明實際來源。"]}
    ]
    inputs[str((TRACE / "live/document.md").resolve())] = sha(TRACE / "live/document.md")
    data = {"title": "scan-p1｜逐階段解析證據", "subtitle": "S0 StandardPdfPipeline：PDFium → Heron → RapidOCR → 分群／組裝 → 閱讀順序 → 交付",
        "notices": ["主線使用原 S0 trace；RapidOCR 內部用同源、結果完全相同的 A 組重播補足，並非同一次執行。",
                    "多數框線由原生工具產生；detector 主圖只自訂行號顯示，沿用原座標。逐階段容器為自訂檢視。沒有重新跑模型，也沒有修正原文。"], "stages": stages}
    assert len(stages) == len({s["id"] for s in stages}) == 13
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")
    shutil.copyfile(HERE / "stage-view.html", out / "index.html")
    inputs[str(SOURCE.resolve())] = sha(SOURCE)
    inputs[str((HERE / "stage-view.html").resolve())] = sha(HERE / "stage-view.html")
    assert all(sha(path) == digest for path,digest in inputs.items())
    manifest = {"new_model_inferences": 0, "downloads": 0, "stage_count": len(stages), "source_hashes": inputs,
        "source_notes": data["notices"], "generator": str(Path(__file__).resolve()), "generator_sha256": sha(Path(__file__)),
        "outputs": {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "manifest.json"}}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"stages":len(stages), "native_model_calls":0, "output":str(out), "image_assets":len(list(assets.iterdir()))}))


if __name__ == "__main__":
    build()
