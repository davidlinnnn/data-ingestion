# Q04 E model artifact path resolution

Status: **read-only evidence; no workload executed**.

The original `READONLY-PREFLIGHT-RECONCILIATION.json` is retained unchanged. It
correctly records that looking for every profile artifact below
`/experiment/PROTOTYPE-wipe-me/hf` finds 14 of 17 paths and 49 total files. The
three reported missing paths use the logical `rapidocr/` namespace; they are
installed by the pinned `rapidocr` distribution under its package `models`
directory, rather than copied into the Hugging Face cache.

On the existing coordinator using the same pinned image, read-only inspection
found:

- 14 profile-referenced artifacts under the Hugging Face cache;
- `PP-OCRv6_det_small.onnx`, SHA-256
  `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f`;
- `PP-OCRv6_rec_small.onnx`, SHA-256
  `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884`;
- `ch_ppocr_mobile_v2.0_cls_mobile.onnx`, SHA-256
  `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c`.

The three observed digests equal the frozen profile. The 49 cache files include
cache metadata, locks, blobs and additional Docling layout files; their total
count does not identify the output-affecting dependency set. The corrected gate
therefore resolves each of the 17 profile-referenced artifacts to its runtime
location, requires readability and exact SHA-256, and treats unrelated cache
files as informational. It does not change the pinned image, artifact digests,
profile, or historical result.
