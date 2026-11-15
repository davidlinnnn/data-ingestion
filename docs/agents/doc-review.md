# Review of a Contract document

Implementers build from a Contract document (kinds: [`docs/design/README.md`](../design/README.md)),
so a sentence that no ruling and no code supports turns into wrong code. Before the pull
request that adds a Contract document, or changes what one promises, the author has it
reviewed by a reviewer with fresh context (a subagent) and gives every finding a
disposition: fixed, declined with the reason, or taken to the user because it needs a
ruling. The pull request's Evidence states the number of findings and how they were answered.

## Dispatch

Render the document's diagrams first with `scripts/render-mermaid <path>` and look at each
PNG: the reviewer checks what a diagram says, not how it is laid out.

Give the reviewer the brief below and these facts. Keep your own conclusions out, so its
read is independent of yours.

- The document's path, and whether to read all of it or a diff
  (`git diff origin/dev...HEAD -- <path>`).
- Its readers, and what each one has to be able to do from it.
- Its sources of truth: the design records and ADRs it relies on, the specification sections
  it cites, the code it describes, the tickets that build it.
- The language of the report.

## Brief

You review one document. Your work is read-only: read files and run read-only commands.
Web lookups may check a vendor fact; keep personal names, email addresses and
company-internal names out of every query.

1. Read the whole document, then its sources of truth.
2. **Rulings.** List the terms the document turns on: each name, status code, limit and rule
   it states. Search every ruling for each term, including documents outside the list you
   were given:

   ```sh
   grep -n -i -E '^(\| *|- \*\*|#+ +)[A-Z]{1,2}[0-9.]+[a-z]?[ :|*].*<term>' docs/design/*.md
   grep -n -i '<term>' docs/adr/*.md CONTEXT.md
   ```

   Done when every hit has a verdict: consistent, or in conflict with both lines quoted.
3. **Code.** Find the code line behind every statement about what the system does today.
   Done when each statement is supported (file and line), contradicted, or has no source. A
   sensible rule that nothing supports is a finding: the document is a contract.
4. **Consistency.** Diagrams agree with the tables and prose beside them, examples with the
   field tables, and one thing keeps one name.
5. **Readers.** For each reader, name the first question they would still have to ask.
6. **Failure and exposure.** For each flow: a dependency is down, a call repeats, state is
   stale. Report any path that exposes or loses data.
7. **Public repository.** Report company-internal product names, personal names and internal
   field or host names.

The user has settled the rulings. Report a conflict with one as a finding. If you think a
ruling itself is wrong, say so once, in a separate section, with evidence.

## Report

A verdict in two or three sentences: is the document fit to be the contract, and what matters
most to fix. Then the findings, most severe first. Each one gives the severity, the section
and line, the quoted text, the evidence (source file and line) and the smallest fix, and says
whether it was verified against a source or is a judgement. End with what you did not check.

| Severity | Meaning |
|---|---|
| blocker | wrong or unsafe as a contract |
| major | a reader would be misled or stuck |
| minor | clarity |
