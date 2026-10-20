"""Compare source-extracted official smart_resize with installed Docling helper."""
from pathlib import Path
import importlib.util
import json
from docling.utils.vlm_utils import compute_qwen2vl_image_size
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("review_official_resize", HERE/"official-smart-resize.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rows=[]
for w,h in [(1120,1680),(1200,1600),(1224,1584),(1191,1684),(1200,1800),(200,300),(1800,2400)]:
    mh,mw=module.smart_resize(height=h,width=w,factor=28,min_pixels=3136,max_pixels=11289600)
    native=compute_qwen2vl_image_size(width=w,height=h,scale=1,max_size=None)
    rows.append({"input_pixels":[w,h],"pinned_model_processor_pixels":[mw,mh],"official_pipeline_assumed_pixels":[native.width,native.height],"equal":native.width==mw and native.height==mh})
assert all(x["equal"] for x in rows[:5])
assert all(not x["equal"] for x in rows[5:])
record={"model_calls":0,"method":"official Transformers4.57.6 smart_resize pure function extracted unchanged from source; pinned dots preprocessor constants versus installed Docling helper. No processor/model/PDF rendered.","rows":rows}
(HERE/"geometry-results.json").write_text(json.dumps(record,indent=2)+"\n")
print(json.dumps(record,indent=2))
