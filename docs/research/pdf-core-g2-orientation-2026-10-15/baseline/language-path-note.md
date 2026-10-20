# Language and effective model identity

The seven probes use the cached **Chinese PP-OCRv6 small recognizer**, with its
18,708-entry embedded ONNX dictionary. The four English scan pages request
Docling `lang=["en"]`; this is a requested language setting, not evidence that
an English recognizer ran. Mixed pages request `lang=["chinese"]`. Every probe
pins the same explicit detector, classifier and recognizer paths. See each
`producer.json` for constructor parameters, resolved configuration, dictionary
hash and live ONNX CPU sessions; `method.json` retains complete options and
package/model hashes.

The installed Docling 2.102.0 primary source
[`rapid_ocr_model.py`](../../../prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling/models/stages/ocr/rapid_ocr_model.py)
resolves any language list containing `en` or `english` to `english` (lines
83–92). This means `["en", "zh-tw"]` is not a bilingual model selection.
However, in its constructor the selected model-set paths are only applied when
`artifacts_path` is non-null (lines 175–217). With that argument null and no
explicit model paths, the constructor passes null paths to RapidOCR (lines
219–260); it does not pass the resolved language as RapidOCR `Rec.lang_type`.

RapidOCR 3.9.2 loads its bundled defaults before applying constructor parameters
([official `main.py`](https://github.com/RapidAI/RapidOCR/blob/v3.9.2/python/rapidocr/main.py#L48-L65)).
Its defaults select Chinese PP-OCRv6 small detection/recognition and enable
classification ([official `config.yaml`](https://github.com/RapidAI/RapidOCR/blob/v3.9.2/python/rapidocr/config.yaml)).
The recognizer obtains its dictionary from ONNX metadata when available
([official recognizer source](https://github.com/RapidAI/RapidOCR/blob/v3.9.2/python/rapidocr/ch_ppocr_rec/main.py#L52-L62)).
Thus historical runs with null artifact/model paths cannot be described as
using an English recognizer solely from their Docling language option. Their
original output payloads are unchanged.

`use_cls=None` passes through the stock Docling call, leaving RapidOCR's
`Global.use_cls=true` effective. The cached classifier has only `0`/`180` labels;
this is not a four-direction page-orientation classifier. Actual model identity
and classifier outputs, rather than language labels or conversion success,
govern interpretation of these probes.

No English recognizer was cached or downloaded for this task. These are bounded
diagnostic probes of the existing model set, not broad language qualification.
