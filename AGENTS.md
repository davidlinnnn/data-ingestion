## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles use matching label strings: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` at the repo root, plus `docs/adr/`. See `docs/agents/domain.md`.

### Code

Before writing or reviewing code, read `CODING_STANDARDS.md`.

Implementing a ticket follows the `implement` flow: `tdd` at the spec's seams, `codebase-design` on every new interface, two-axis `code-review` before the pull request. `/mattpocock-skills:implement` loads only when the user types it.

`scripts/check` mirrors CI's lint and type checks; `scripts/check --all` adds the S3 stand-in and the whole test suite. Enable it as the pre-commit hook once per clone: `git config core.hooksPath scripts/git-hooks`.

### Branches and worktrees

Public repo. Before creating a branch or worktree, committing, pushing, merging or deleting a branch, read `docs/agents/branching.md`.

### Wayfinder map

The Knowledge Platform design map is issue #52. Before creating or editing the map or one of its tickets, apply the `wayfinder` skill's rules: each ticket asks one question sized to one session, the map is an index of one-line gists with links, and tickets are referred to by name. Map mechanics: `docs/agents/issue-tracker.md`; the map's long-form notes: `docs/design/knowledge-platform-map-notes.md`.
