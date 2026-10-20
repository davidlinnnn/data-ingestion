# Frozen inputs for the stronger-model comparison

The manifest references 22 existing images: the exact 17 whole-provider-item
paragraph PNGs and the exact five full-page PNGs saved at the CPU VLM engine
boundary. No image was resized, cropped again or regenerated, and no large
baseline document was copied. Every row exposes `id`, `phase`, `image_path`,
`image_sha256`, `image_pixels_wh`, source identity/hash and physical pages, plus
the prior CPU input/method references.

Paragraph rows link all 19 original provenance fragments and their crop/stitch
transforms through JSON pointers into the prior input manifest, SHA-256
`4fd11ccacd2819d0eb44461974315f217dee12e3fc58308b28875b0964e00ccf`.
They preserve full provider item references and replacement spans, including
the SEAL p3-to-p4 join. All 28 ordinary-paragraph gate decisions remain linked,
including the 17 ordinary items that did not trigger the previous character
gate. Selection was not rerun or expanded for this model comparison.

Full-page inputs are WikiSkill p21, DGM p51, SEAL pp3-4 and controls p1. Their
images are the saved official CPU pipeline inputs at nominal scale 2; actual
pixel dimensions, source page dimensions, full-page crop and render-method
references remain explicit. These full-page inputs have a different render
chain and scale from the paragraph crops. Nominal affine mappings do not erase
render rounding/resampling uncertainty or establish glyph-level source boxes.

Eligible source content is limited to the three public fixed-version research
papers and original synthetic controls page 1. Public arXiv URLs are supported
by the existing fixture acquisition manifest; controls provenance comes from
the frozen source registry. No private source, credential or answer payload was
added. Only referenced image bytes and the separately decided output contract
belong in later model requests. Native transcripts, gold expectations, previous
model outputs and independent review material are excluded from producer input
records and prompt content. The preparation does not choose an API/model/output
contract or perform inference.

`prepare.py` verifies the entire prior 646-payload manifest and frozen source
registry, checks all image/source/baseline/method references and counts, and
rejects stale images, duplicate IDs and answer/transcription fields. It creates
no new images or baseline copies. The saved verification passes with all prior
payloads unchanged, zero inference calls and zero API requests.

```sh
rtk python3 -B docs/research/pdf-core-g2-inline-api-2026-10-15/inputs/prepare.py
```

This freezes input parity with the CPU experiment; it does not establish broad
detector recall or model quality.
