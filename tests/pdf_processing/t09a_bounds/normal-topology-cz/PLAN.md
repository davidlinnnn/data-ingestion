# CZ: one-variable contrast to CY OCR allocator pressure

CY exactly maps230 allocator entries in18 OCR threads to the inference interval
under normal32-on load; VM avg10 later reaches0.18. CZ keeps identical producer,
input bundle, grouped capture/assembly, Pod limits, THP policy, object protection,
resource guards, deadlines and first-output non-retryable stop. Only the supported
RapidOCR ONNX intra-op parameter is overridden to4 by the explicit diagnostic hook.
No production source patch or bundle/oracle rebinding is claimed.

Fresh CZ run/prefix/PVC,one attempt,no automatic retry. Record runtime override,
actual thread counts,NSpid/start-time matches,full PSI and reclaim counters.
Compare complete first OCR report except its existing timing field and exact PNG
bytes against retained CY. If guards trip,stop and preserve that result. Do not
count deliberate business failure as ingestion success or narrow pass as full
acceptance. Restore32off/object512Mi/all low values; retain history/PVC/prefix.

Before runtime: image-backed hook/non-retryable test,actual API session-config
check,source projection/import/scope check,unchanged guard comparison and review.
A single diagnostic contrast can support a candidate,not permanent qualification.
