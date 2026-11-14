# Identify a Resource by its Source's own key

Within a tenant, a Resource is identified by the Source that registered it and
the key that Source gives it: for a knowledge-management Source, the key of a
space it already keeps in the company authorization service (GAM). The Source
registers the key with the platform by a call it may repeat, declares Documents
against that key, and a read decision asks GAM about the Source's existing
object. The 2026-10-26 design (#85 Q13, G12) had the platform generate an opaque
id and register it in GAM as a new object. The Source would then keep a mapping
from its key to the platform's id and write every reader relation a second time
on the new object, and a member removed from a space would keep reading until
the copy caught up. The first knowledge-management Source already maintains its
user-to-space relations in GAM under its own keys and will not adopt a platform
id.

Decided by the user on 2026-11-14, after
[#113](https://github.com/davidlinnnn/data-ingestion/issues/113); recorded in
the [authorization design](../design/knowledge-platform-authorization.md).

## Consequences

- Reader relations exist once, in GAM, written by the Source. The platform
  writes none for such a Source, so no copy has to catch up with a revocation:
  it reaches the platform's decisions within GAM's own staleness bound, which
  [#86](https://github.com/davidlinnnn/data-ingestion/issues/86) verifies (G5
  of the authorization design).
- GAM holds no relation for a Source, so `place` and `manage` are decided from
  the platform's own Resource record, the Source that registered the key.
  Admission then asks GAM nothing.
- A key is unique only within its Source. Wherever a Resource is named without a
  Source credential, the identifier carries the Source as well.
- The platform does not learn of a space from GAM. A key it has no record of is
  refused at declaration, so registration stays an explicit call, repeatable so
  that the Source keeps no record of what it has registered.
- Each Source's configuration names its GAM object type and the permission that
  means read.
