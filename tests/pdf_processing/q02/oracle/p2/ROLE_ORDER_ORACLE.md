# Source role/order oracle v3 — P2 correction

Supersedes the role/order sufficiency claim of the 50ad080 oracle; historical
ORACLE.md, evidence.json and private outputs remain immutable historical evidence.
This adds no new source-quality cases or symbol policy. Header boundaries follow
the four source-reviewed function declaration lines in the existing frozen native
transcript; header-oracle.json pins each first line and its full transcript hash.
No expected role or range is read from derive() or its output.

## Independent role membership

For each reviewed algorithm, its first native transcript line is the complete
header: function declaration through its declared return alternatives. The first
return/body instruction is body, including the recursive function in depth-limited.
Map that exact whitespace-compacted source line to the initial source-ordered text
within the frozen algorithm region. Preserve original text indices: the header
ends immediately after its last non-whitespace character. Inter-item whitespace
belongs to the preceding fragment; remaining text, including separating whitespace
inside the final header item, belongs to body. The existing per-page provenance span
bounds this mapping, so an embedded header never consumes preceding-page prose.

Header coverage must equal precisely those mapped character intervals; body
coverage must equal all remaining reviewed algorithm characters, apart from the
previously reviewed separate combining mark. At least one nonempty header, body
and caption member is mandatory. Their roles cannot be missing or unknown.
Source-caption full hashes, exact content/order checks and localized representation
uncertainties continue unchanged. Fragmentation is representation-flexible: both
one item split into role-specific ranges and multiple items for one role are valid.
Actual labels and local item IDs never define roles. Source transcript mismatch
or an unmappable header is failure, never a permissive fallback.

## Order contract

The members list is authoritative. Every member has an integer (not boolean)
order equal to its zero-based list position. Thus orders are unique, contiguous
and monotonic. Header members precede body members, which precede caption members.
Within a role, exact source-content sequence remains required. Splitting a member
is legal when concatenated content, precise role coverage and ordering are unchanged.

The separate symbol_uncertainty list is not an ordered body stream. Its members
retain role unplaced_combining_mark and order null. This does not reconstruct the
mark's mathematical position or grant release acceptance to uncertain symbols.
