# Next bounded step: isolate component OCR allocation pressure

CS proves the approved object-PSI rule works, but VM full avg10=0.18 stops first
Wiki06 during component_ocr. The worker container had173 allocator-stall entries
across18threads in the largest pressure interval. Host TGID mapping to the
container child and library pool is missing. Do not start another full matrix.

1. Recover the exact Wiki06 selected component/crop/request from retained CS
   artifacts/prefix. Keep existing OCR NumPy policy and model/version/crop bytes.
2. Make a minimal owned component probe that represents the warm-parser overlap,
   records host/container PID mapping and actual native thread count, and uses
   existing VM/OOM/memory/deadline guards. Preserve trigger samples and cleanup.
3. Test the candidate that explicitly bounding the active ONNX thread pool reduces
   parallel allocation/reclaim; inspect actual installed API before choosing the
   parameter. A contrasting run must use a separate identity and reviewed change,
   not automatic retry. Compare full OCR output/crop evidence and timing.
4. If pool ownership or the allocation mechanism is not reproduced, keep it unknown
   and do not change production based only on simultaneous timing. Only a supported
   fix justifies another full mixed-window diagnostic.

No VM PSI threshold change,new hardware,permanent memory policy,or ticket closing
is authorized/implied by the CS result. Existing normal diagnostic work remains
authorized; no additional repeated permission is needed for the scoped investigation.
