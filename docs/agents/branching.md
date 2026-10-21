# Branches and worktrees

This repo is **public**: every push publishes.

## Where work starts

- `dev` is the integration branch. Start every task from `origin/dev`, and merge it back into `dev` by pull request.
- `dev` is the GitHub default branch. `main` is a frozen older snapshot, kept because published links point at `blob/main/…`; nothing merges into it.
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

## Parallel agent sessions

Several agent sessions often run at once on this repo. Sessions that share one working tree overwrite each other's uncommitted files and share one git index.

- Start each session that edits files inside its own task worktree (`cd ~/work/data-ingestion-<task>`), so its working directory, loaded instructions and `git status` all describe that task.
- One editing session per worktree. A session never edits files in another session's worktree.
- Use the main checkout only for reading, coordination and tracker work.
- Commit to the task branch locally as soon as a change is coherent; uncommitted files are the easiest work to lose. Push only when ready to publish.
- Update the task branch from `origin/dev` before committing a change to shared files such as `CONTEXT.md`, and keep those changes small.

## Committing and pushing

- Commit a curated set. Large outputs, model weights and third-party documents (papers, page images) stay out of git; record their hashes in a manifest file instead.
- Run `scripts/check-docs` before every push: secrets in the branch's commits, local paths and emails in added lines, and links and anchors in changed Markdown. The `docs-checks` workflow runs the same script on every pull request.

## Merging

- Squash-merge into `dev` by default.
- Use a merge commit when another open branch is built on top of this one. Squashing would make that branch conflict with `dev`.

## Keeping and deleting branches

- Archive a branch once its PR merges or its work ends as a primary source (research, prototype): push an annotated tag with the branch's exact name on its tip, then delete the branch. GitHub `blob/<name>/…` and `tree/<name>/…` links resolve to the tag, so links and commits stay valid.

  ```sh
  git tag -a <branch> origin/<branch> -m "Archived branch <branch>"
  git push origin refs/tags/<branch>
  git push origin --delete refs/heads/<branch>
  ```

- Delete a merged branch that nothing links to without a tag.
- Archive a branch that was never pushed with `git bundle`, and verify the bundle before deleting it.
- Retire a task worktree after its PR merges. First archive its uncommitted and untracked files, check that the archive restores, then remove the worktree.
