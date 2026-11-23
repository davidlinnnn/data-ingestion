# Declare Processing Profile adoption in the deployment repository and roll a method back by withdrawing its version

Which Processing Profile version new requests run under stays a record in the
platform database, the adoption record. It is no longer written by a person
running a command: the adopted version, its refresh scope and the withdrawn
versions are declared in the deployment repository's values and applied by a
scheduled job after a gate (the new build is current on every task queue and a
test workflow completed). The company's production clusters allow nobody to run
a command inside a pod except for investigation or emergency support, so every
operation in this design has a declared, scheduled form (user, 2026-11-22). A
declaration carries an integer the author raises and is applied only when it is
above the highest one applied. Every adoption declares its refresh scope
(`none`, `all`, or the versions whose revisions to redo), with no default. The
refresh is one scan over Documents with no global wait: a Document is redone
under the version adopted now when the version that made its revision is in the
latest adoption's scope.

A method rollback in the pilot is a reprocessing, not a pointer move. The older
version is adopted again and the faulty one is declared withdrawn. A withdrawn
version is never adopted again; a result made under it that arrives after the
withdrawal forms no Canonical Acceptance; and the scan redoes every Document
whose current revision it made, ahead of ordinary refreshes and whatever a
later adoption's scope says. A Document whose redo fails keeps serving the
revision it had, counted and alerted (user, 2026-11-22, confirmed again the
same day on the corrected premise that removing it would need no new event). A
content rollback is the Source's: it submits the old content again as a new
Source Revision. Confirmed in
[#57](https://github.com/davidlinnnn/data-ingestion/issues/57) (rulings B6 and
B8); built by #261 and #98.

The trade-offs: until the scan has redone them, Documents keep serving content
made by the withdrawn version, and at production volume that is days of
reprocessing; moving the current revision back to the previous accepted
revision of the same Source Revision without reprocessing (canonical
consumption D3) is therefore owed before production (#270). Withdrawing takes
no lock on Documents, so a result accepted an instant before the withdrawal
stays until the scan redoes it. Rejected: Temporal's current and ramping
versions as the switch, which would put the decision outside the acceptance
transaction that compares adoption sequences; encoding breaking and
non-breaking changes in the version name, since a consumer-facing
incompatibility is the Canonical content schema version; and removing a
Document from serving when its redo fails, because a withdrawal is declared for
a version, not for a Document, and the pilot's way to take one Document out is
its Source's deletion.
