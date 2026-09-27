# CZ: bounded OCR thread contrast

The diagnostic-only supported intra_op_num_threads=4 override reached all three
ONNX sessions in the actual-image local test and produced16 engine-ready threads
(versus CY58). In normal32-on load, exactly4 OCR threads had30 allocator-stall
entries, versus CY18threads/230entries. Three stalling threads were created during
engine initialization; the fourth was the OCR main thread. Exact NStgid/start-time
mapping is retained. All calls occurred during inference; trace loss/unknowns=0.

| Observed quantity | CY default | CZ intra-op4 |
| --- | ---: | ---: |
| Engine-ready process threads |58|16|
| OCR threads entering stall |18|4|
| OCR allocator entries |230|30|
| Enclosing VM pgscan_direct delta |38353|1921|
| Enclosing VM full-total PSI delta(us) |39026|7695|
| Maximum sampled VM full avg10 |0.18|0.00|
| Inference seconds |1.396|0.566|
| Object full-total PSI delta(us) |0|0|

Both used the same inputs,producer bytes,models,grouped capture,normal topology,
THP policy,limits and guards. Complete first-component OCR reports match after
removing only their existing timing field; crop PNG bytes are identical. However,
starting VM available memory was3,687,501,824(CY) versus3,900,907,520(CZ), and worker
memory2,015,436,800 versus1,786,089,472. This is a single sequential contrast, not
an identical allocator-state experiment. It supports bounding oversubscribed OCR
pools; it does not prove threads are the sole cause or guarantee zero stalls.
Thirty allocator entries and7695us VM PSI remain despite displayed avg10=0.

CZ deliberately stopped after first OCR output using the non-retryable
cz_diagnostic_first_component_complete code. Activity attempt1 only; business
failed,processing_complete=false,28pages and0registered components. No guard breach
was observed; controller records expected Pod workload failure,no retry. A planned
failure is not ingestion success, and first-component evidence is not full-window
acceptance. No second component/later fixture,replay or request20 recycle ran.

Independent cleanup PASS:32off/no owned Pods,object512Mi Ready/HTTP200,all memory.low
manager/kernel values restored,worker/observers/tracers absent,PVC Bound and prefix
retained. The source-level four-thread change is separately checked by the actual
production-path red/green regression in `../../ocr-thread-probe/production-regression/`.
Full producer requalification and mixed-window verification remain before any#44
completion claim. No memory/PSI threshold was relaxed and #51 history is unchanged.
