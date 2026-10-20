# Holdout custody — 2026-10-15

Six public scientific-paper PDF work groups are acquired and frozen by exact version, byte size, and full SHA-256. Total: 3113292 bytes. This is a custody freeze for a future evaluation; no holdout PDF has been rendered, extracted, previewed, annotated, or passed to Docling or any other model.

| Work group and exact version | Official metadata | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| arxiv:1312.5602v1 | [Playing Atari with Deep Reinforcement Learning](https://arxiv.org/abs/1312.5602) | 483443 | `8db04120cace173151c77e0faa6f3eaa4207009da66b9417597dc70bfee56d9c` |
| arxiv:1603.02754v3 | [XGBoost: A Scalable Tree Boosting System](https://arxiv.org/abs/1603.02754) | 944793 | `52bc282c922a239134ee4d6f4367c58bf920a9bdd53acbb3b2aa3342e2bb7214` |
| arxiv:0908.3871v1 | [Critical parameters for the one-dimensional systems with long-range correlated disorder](https://arxiv.org/abs/0908.3871) | 317307 | `73656ff82dcccc9c768423f4ce428dc250ac7bac44b373cb2cb4f8dddae1b551` |
| arxiv:1202.5147v2 | [Tensor functors between categories of quasi-coherent sheaves](https://arxiv.org/abs/1202.5147) | 269409 | `1c934e778fdce47fdca105981bb40b400c0a7888533f2166d2f21302d5647f23` |
| arxiv:1402.1120v2 | [Performance analysis of electronic structure codes on HPC systems: A case study of SIESTA](https://arxiv.org/abs/1402.1120) | 597387 | `d7bc9f1d7baf15412880e1e1e91a2e7aef85a29cc7678c6c4df07d03fe7f55a7` |
| arxiv:1206.5533v2 | [Practical recommendations for gradient-based training of deep architectures](https://arxiv.org/abs/1206.5533) | 500953 | `13b45892fd59e675fb1b9611b4926357f7eee3893d2cc763ceddb4b2e2a5a46a` |

The exact requested and resolved PDF URLs, observed UTC times, HTTP metadata, and redirect chains are in `holdout-custody.json`. All six resolved without a redirect. Files live in `docs/fixtures/pdf-core-g2-holdout-2026-10-15/`; the local `*.pdf` ignore rule follows existing fixture conventions. The initial sandboxed download failed DNS resolution, then an approved public network read acquired all six. Only magic-prefix, size, and SHA-256 checks touched the PDF bytes.

Selection used metadata and an ordered queue, with conservative rejection at the work-family level. Before any fetch, `rtk proxy rg --hidden --no-ignore -l -i -F` checked each unversioned ID and official title alias across repository text/metadata, including ignored and hidden experiment output and installed-package records. PDF/image/archive bytes and the two newly created freeze directories were excluded. A separate `rg --files` inventory checked work-ID filenames. All six selected groups had zero text and filename matches. The queue, exact scope, limitations, correction of the tentative TensorFlow/XGBoost and Atari/NMT identities, and all exclusions are recorded in JSON. Source metadata determined versions; PDF content and extraction quality never determined selection.

| Rejected work family | Reason |
| --- | --- |
| arxiv:1706.03762 | Existing exact work-ID/title references; conservative family exclusion. |
| arxiv:1810.04805 | Existing exact work-ID/title references; conservative family exclusion. |
| arxiv:1605.08695 | Corrected official metadata identifies TensorFlow v2, not XGBoost v3; actual title has existing references. |
| arxiv:1412.6980 | Existing exact work-ID/title references; conservative family exclusion. |
| arxiv:1502.03167 | Existing installed-source reference; conservative family exclusion. |
| rfc:8439 | Existing installed SBOM reference. Intended RFC Editor info page also unexpectedly embedded full text; excluded in all cases. |
| rfc:9000 | Zero repository references, but intended RFC Editor info page is a full-text route. Only title/line count returned; ambiguous source-page exposure conservatively excluded. |
| gnu:make-manual | Existing installed-source/SBOM title or manual-family references; GNU landing-page fetch also failed. |
| rfc:8949 | Zero repository references, but intended Datatracker metadata route embedded full text and returned a body/contents snippet; conservatively excluded. |
| rfc:8785 | Zero repository references, but intended Datatracker metadata route embedded full text. Only title/line count returned; ambiguous source-page exposure conservatively excluded. |

The intended RFC metadata routes unexpectedly embedded source full text: RFC 8439 and RFC 8949 returned source body snippets; RFC 9000 and RFC 8785 returned only title/line-count information but their routes were still ambiguous. All were excluded conservatively. None of those RFC PDFs was acquired. No selected scientific-paper full text or PDF content was read.

“Experiment-unseen” means no prior identity/title/filename match within the recorded repository screen. It does not establish absence from model pretraining, undisclosed external experiments, differently named binary copies, or semantic independence. The coordinator must still compare these identities/hashes with the frozen exposure registry.

Feature coverage remains **unknown** until a separate source-only annotation pass. Six scientific papers do not establish code/formula/context coverage or support claims for official manuals, SOPs, or Traditional Chinese. This custody manifest contains no ground-truth page/span labels and authorizes no evaluation run.
