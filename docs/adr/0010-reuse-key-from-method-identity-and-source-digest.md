# Derive the processing reuse key from method identity and source digest, and freeze released Processing Profiles

A registered processing item (a parsed page group, a picture's OCR text, a
picture interpretation, a formula, a document summary) is reused by any later
request for the same Document when its reuse key matches. The key is
`sha256(document_uid | method_id@version | components | module_digest | input_digests)`:
the Document, the Enrichment Method's declared identity (its version string and
the `components` it declares, such as `layout-heron@<revision>`,
`docling-slim@<version>` or `<provider>/<model>` for an external model), a digest
of the source text of that method's own package computed once at worker start,
and the digests of the item's actual inputs. Nothing else enters the key: no
hashing of model weights, no installed-dependency versions, no configuration
values. Anything that changes a method's output lives inside that method's
package (prompts, schemas, output-affecting constants), so the package digest
covers it; timeouts, concurrency and retry limits live in the profile's
`runtime` section and never affect reuse. This refines the
[workflow v2 record](../design/knowledge-platform-processing-workflow-v2.md)
§5, which fixes the key's shape, by fixing what "module and model digest" means
in code.

Released Processing Profile files (`profiles/<profile>@<n>.yaml`, shipped in the
worker image) are immutable: a change to a method, a component or the method set
is a new file and a new profile version, which an owner adopts and the platform
refreshes. Two checks keep the human-maintained version strings honest: CI
refuses a change under a method's package without a change to that method's
`VERSION`, and refuses a modification to a released profile file; a worker
refuses to start when the profile lists a method version its package does not
declare, and a workflow fails with an integrity error when `adopted_version`
differs from the worker's profile. Even if every check were bypassed, the
package digest keeps stale items from being reused; only their labels would be
wrong.

While a profile file says `released: false` it is a draft: #80 builds paper-pdf@1
over several tickets, and version labels on results from a draft carry no
promise. The CI checks bind only profile files whose base-branch version says
`released: true`, and the methods those files list. Setting it is the release
act, in its own commit and before any later profile version is built on it;
from then on the immutability check forbids any change to the file, including
setting it back.
The package digest keeps reuse correct for drafts too.

The trade-off, confirmed on 2026-10-30 after several simplification rounds in the
#80 grilling: hashing weights, lock files or installed versions would catch a
silently swapped model or a library upgrade without a version bump, but a lock
file hash invalidates every method when an unrelated package moves, weight
hashing is impossible for the external vision-language and summary services and
slow for local ones, and each of these adds a mechanism that must stay in step
with the key. Declared identity strings plus the source digest give the same
protection for every change made through the repository, which is the only path
the design allows (a method change is a new version by definition). Three
consequences are accepted and recorded in the implementation spec: a
comment-only edit to a method package is a new method version; reuse treats
non-deterministic services as "the first successful answer wins"; and a
provider replacing a model behind an unchanged name is detected only by
recording the response's model and fingerprint fields and raising a manual
version bump. The approach matches how Azure Machine Learning (code snapshot
hash), Prefect (task source hash) and Dagster (explicit `code_version`)
decide reuse; see the research summary kept with the #80 decision log.
