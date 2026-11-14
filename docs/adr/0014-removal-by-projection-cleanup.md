# Remove content through projection cleanup, without a serving-time block

After a Source Deletion, a withdrawal or a rebind, content stops being served
when each projection has applied the Change Feed event to its own store: it has
removed the Document from its index, regenerated or deleted the Wiki pages that
used it, or moved it to its new Resource. A reader does not ask the platform
about a Document at query time. The platform sets a cleanup time limit and
judges, per Document, when no projection holds the content any more
(`enforced`). The earlier design (#31 Q10.5, #55 B5, #85 E2) put a serving-time
block in front of that cleanup: within one minute a query would no longer find,
read or cite the Document, and a Wiki page that used it would be hidden. The
block needs a check that every reader calls on every query, which was #56's to
design and did not exist, and it makes every read depend on one more platform
call. The user accepts a bounded delay instead.

Decided by the user on 2026-11-14 (after a deletion a Wiki page need not be
taken down at once) and on 2026-11-15 (the same rule for the Document's own
content, for withdrawal and for rebind), during the review of the
[authorization guide](../design/knowledge-platform-authorization-guide.md).

## Consequences

- Until cleanup finishes, removed content can still be served: a deleted or
  withdrawn Document to the people who could already read it, and a rebound
  Document to readers of its old Resource who cannot read the new one. The bound
  is the cleanup time limit. Its target is the former `enforced` target, 10
  minutes, unmeasured; #56 sets it and #98 measures it. Regenerating the pages
  of a heavily cited Document may take longer (#55 B5), so the limit is a target
  and not a guarantee until it is measured.
- There is no fast path for an incident. The incident path of #31 Q10.8 relied
  on "unreadable within a minute"; it is now a deletion followed by cleanup
  within the limit. A block check can be added later for that case: readers
  would call it before disclosure, which the reader SDK can absorb.
- `applied` (admission specification §8) keeps its meaning inside admission:
  the deletion is recorded, the status shows `deleted`, the catalog fields are
  cleared and the event is in the Change Feed. It no longer means that agents
  cannot find the content; that is `enforced`.
- A reader filters and checks on the Resource its own store records for a
  Document, kept current by the Change Feed. E2's rule that an index's copy of a
  Resource is never authority for a read decision is withdrawn for v1.
- The commit-time check of #55 B5 stays: from its own records the platform
  refuses a projection's write for a Document that is deleted, withdrawn or
  moved out.
- Narrowing events keep their priority in the Change Feed (#55), which is what
  makes the limit reachable.
- Cross-Source copies (#55 B3) are not designed; their design follows this
  decision.
