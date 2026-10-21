# Branches and worktrees

This repo is **public**: every push publishes.

## Where work starts

- `dev` is the integration branch. Start every task from `origin/dev`, and merge it back into `dev` by pull request.
- `main` is the GitHub default branch, but it is an older snapshot that lags `dev`. Read the current design and evidence from `dev`.
- The main checkout (`~/work/data-ingestion`) stays clean on `dev` as the home base. Do task work in a task worktree.

## One task, one branch, one worktree

```sh
git fetch origin
git worktree add --no-track -b <branch> ~/work/data-ingestion-<task> origin/dev
```

Branch names carry the ticket number:

| Prefix | For |
|---|---|
| `design/<issue>-<slug>` | design decisions (wayfinder grilling tickets) and their docs |
| `research/<issue>-<slug>` | research findings and evidence |
| `prototype/<issue>-<slug>` | throwaway prototype code that answers one design question |
| `impl/<issue>-<slug>` | implementation |

Leave out `<issue>-` only when the work has no ticket.

## Committing and pushing

- Commit a curated set. Large outputs, model weights and third-party documents (papers, page images) stay out of git; record their hashes in a manifest file instead.
- Run `scripts/check-docs` before every push: secrets in the branch's commits, local paths and emails in added lines, and links and anchors in changed Markdown. The `docs-checks` workflow runs the same script on every pull request.

## Merging

- Squash-merge into `dev` by default.
- Use a merge commit when another open branch is built on top of this one. Squashing would make that branch conflict with `dev`.

## Keeping and deleting branches

- A branch stays while an issue, PR or doc links to its name or to commits only it contains. A research or prototype branch linked from its ticket stays as a primary source, even after a curated summary merges into `dev`.
- Delete other branches once they are merged.
- Before deleting a branch with commits `dev` lacks, archive it with `git bundle` and verify the bundle.
- Retire a task worktree after its PR merges. First archive its uncommitted and untracked files, check that the archive restores, then remove the worktree.
