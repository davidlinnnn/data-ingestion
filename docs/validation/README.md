# Validation reports

Each folder holds one ticket's measurements: a `README.md` with the verdict, how it ran and how to
rerun it, the scripts, and the evidence (JSON and a hash manifest; papers and raw outputs stay
outside git). The folder is named after the ticket.

## paper-pdf@1 end to end and its release

| Report | What it shows |
|---|---|
| [233](233/README.md) | **Current release evidence.** #199's 21-paper workflow run with #210, #211 and #212 together, compared with #199 paper by paper: `paper-pdf@1` is releasable |
| [199](199/README.md) | The first end-to-end run: 20 corpus papers and W2 on the Temporal workflow, accuracy against #84's gold and tokens per component; found the three defects below. Its [Reuse](199/README.md#reuse) section is how later tickets rerun it |
| [210](210/README.md) | Fix 1: a whole code listing in code items (native text layer fonts); held-out and overfit checks |
| [211](211/README.md) | Fix 2: fixed roles for chart value labels in `picture-interpretation@1` |
| [212](212/README.md) | Fix 3: identifier lines labelled as formulas become text lines; held-out check |

## The PDF workflow's build (#80, spec #129)

Under [80/](80/), one folder per build ticket. "Seam B" runs this repo's code on the real stack;
"accuracy" scores a method against the gold.

| Report | Ticket | What it shows |
|---|---|---|
| [t2-tracer-bullet](80/t2-tracer-bullet/README.md) | #131 | One paper through the real stack |
| [t2-queue-split](80/t2-queue-split/README.md) | #131 | Orchestration and inference queues |
| [t3-accuracy](80/t3-accuracy/README.md) | #132 | Accuracy of the local enrichment methods |
| [t3-seam-b](80/t3-seam-b/README.md) | #132 | The corpus paper with the most pictures, with local enrichment |
| [t4-accuracy](80/t4-accuracy/README.md) | #133 | Accuracy of the VLM methods |
| [t4-seam-b](80/t4-seam-b/README.md) | #133 | VLM enrichment against a real model |
| [t4-receipt-overhead](80/t4-receipt-overhead/README.md) | #133 | V9: receipt overhead |
| [t5-seam-b](80/t5-seam-b/README.md) | #134 | The whole `paper-pdf@1` with the Document Summary |
| [t5b-accuracy](80/t5b-accuracy/README.md) | #155 | How well the summary's verify step catches unsupported sentences |
| [t5b-seam-b](80/t5b-seam-b/README.md) | #155 | The Document Summary in the platform, on Claude Sonnet 5.5 |
| [t5c-seam-b](80/t5c-seam-b/README.md) | #161 | The d3 Quality Check against d3-mini |
| [t6-seam-b](80/t6-seam-b/README.md) | #135 | Reuse across requests and profile versions (V3), a version's life under Worker Versioning (V1, local) |
| [t7-capacity](80/t7-capacity/README.md) | #136 | Capacity and freshness: V2 and V8 |

## Other platform parts

| Report | What it shows |
|---|---|
| [113](113/README.md) | Decision latency of the allow-all authorization provider against `authz_timeout` |
| [57](57/README.md) | Change Feed positions after a point-in-time restore: transaction IDs are handed out again and a stale cursor skips the new events without an error |
| [178](178/README.md) | The Temporal side of Worker Deployments per Processing Profile version |
| [184](184/storage_probe.py) | The storage behaviour the upload design relies on (a probe; results in the file upload design, section 6.7) |
