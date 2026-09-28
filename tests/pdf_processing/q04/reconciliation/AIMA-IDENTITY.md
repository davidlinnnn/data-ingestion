# AIMA Q03 to Q04 identity reconciliation

The executable comparison is
[`evidence/aima-identity.json`](evidence/aima-identity.json). It compares the
accepted Q03 trial-A fresh record with fixture `08` in the retained Q04
Option-A config and bundle. No registration, request ID or object-store key was
copied.

| Identity | Result | Consequence |
| --- | --- | --- |
| Fixture and original source bytes/pages | equal | The Q03 source review remains a valid bounded source reference. |
| 20-file producer | equal | Q03 exercises the same production file inventory. |
| Parse/continuation method | equal | Q03 remains direct historical evidence for the corrected AIMA method. |
| Base profile fields | equal | `native-v1`, version and group size agree. |
| Relationship coverage/representation policy | equal | The four reviewed AIMA regions and unresolved-symbol disposition remain reusable as policy evidence. |
| Full profile/release | **different** | Q03 has six review entries and Q04 fixture `08` has one; original-object key/version and release also differ. |
| Source artifact namespace/version | **different by design** | A Q04 fresh request must capture its own version under a new Q04 prefix. |
| Oracle identity | **different overall** | Exact hashes show the shared AIMA transcript, representation and five Q02 oracle files agree; Q04 additionally binds its continuation oracle and full reference graph. |
| Test harness identity | **different** | Exact file manifests show the shared Q02 oracle files agree while the Q03 runtime/tests and Q04 consumer/audit harness are distinct. |

Q03 therefore remains useful evidence for source bytes, method behavior, the four
algorithm structures, localized representation dispositions, reuse mechanics and
the required-relationship interruption path. It does not satisfy Q04
fresh/restored/exact replay, and it cannot create a Q04 `fresh-index.json` entry.
Those four gates remain unproven until a distinct Q04 run uses the Q04 profile,
namespace and consumer/oracle harness. The run may be scheduled after higher-value
fixtures; this conclusion does not request a blind AIMA matrix rerun.

The reuse conclusion is conditional on the computed fixture, producer, method,
policy and shared-oracle equalities. A drift in any of those inputs removes all
items from the report's `reusable` list. The report generator accepts the Q03
record and hash manifest plus Q04 config and bundle paths so the comparison can
be repeated without modifying historical evidence:

```sh
PYTHONPATH=tests/pdf_processing/q04 python \
  tests/pdf_processing/q04/reconciliation/reconcile_aima_identity.py \
  --q03 /private/tmp/q03-results-20260916-a/fresh/accepted.json \
  --q03-manifest tests/pdf_processing/q03/evidence/manifest.json \
  --q04-config /private/tmp/q04-acl-option-a-window-c-review/state/config.json \
  --bundle /private/tmp/q04-inputs-option-a-v7/inputs.json \
  --out /private/tmp/aima-identity.json
```
