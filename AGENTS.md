# AGENTS.md

## Required Start

Run or read the agent-oriented project status before changing files:

```bash
make agent-status
```

Respect exactly one owned task per worktree. Then load only the context recommended
by the Tier 1 context command:

```bash
make agent-status
make agent-context TASK=<id>
make agent-context TASK=<id> SKILL=<skill>
make agent-context TASK=<id> SKILL=<skill> MODE=resume
```

`make agent-status` derives the task this checkout owns from its branch and local
claim, so a parallel worktree does not need to be told its own task. Use the
default context mode for a new task and `MODE=resume` when resuming or fixing an
existing PR on this branch. Do not manually re-read architecture/workflow
documents that the context bundle already resolves deterministically.

## Project Workflow

- Before editing files, agents must be on a non-`main` branch. If the current
  branch is `main`, create a dedicated branch for the task first.
- Use `make task-ready`, `make task-start`, `make task-review`,
  `make task-complete`, and `make task-block` for state changes.
- Do not bypass the task lifecycle by silently editing task status.
- Do not autonomously run `make task-approve`; approval commands are only for a
  human.
- Run `make agent-pre-review TASK=<id>` before moving a task to review.
- In GitHub-backed managed projects (`workflow_mode: pr`), moving A1/A2 work to
  review and opening its pull request is the agent boundary. The human GitHub
  merge is the normal A1 approval/completion boundary: after the merge there is
  no required `task-approve`, `task-complete`, sync, cleanup branch, or
  lifecycle-only pull request. Never manufacture or record human approval
  yourself; never merge your own governed PR.
- In `local`/`branch` managed projects, `make task-approve` (humans only)
  followed by `make task-complete` remains the explicit offline fallback.
- Prefer focused checks while implementing: run the commands `make agent-context`
  recommends for the changed surface. `make agent-pre-review TASK=<id>` is the
  single canonical local gate per review cycle and runs `make check` exactly
  once; do not run `make check` immediately before it, and do not run
  `make release-check` during normal implementation.
- The implementation session ends once the task is in review and its pull request
  is pushed. CI remains required, exhaustive, and asynchronous: do not wait for
  or poll GitHub Actions. If CI fails, start a fresh session, run
  `make agent-handoff TASK=<id>` and a focused resume on the same
  task/branch/worktree/claim/PR, fix the failure, run the focused checks, run
  `make agent-pre-review TASK=<id>` once for that repair cycle, push the same
  pull request, and stop.
- For parallel work, give each independent task its own worktree instead of
  sharing one checkout: `make agent-worktree TASK=<id>` claims the task, creates
  `task/T-###-<slug>` outside the project tree, and prints the worktree path.
  Inspect with `make agent-worktrees`, recover a stale claim with
  `make agent-claim-release TASK=<id>`, and clean up with
  `make agent-worktree-remove TASK=<id>` (which refuses dirty or unmerged work
  unless `FORCE=1` is passed explicitly).
- Task status is task-local: only task records change on a transition. Committed
  dashboards carry project-global rows only, and live task status, the board, and
  local worktree claims are rendered by `make project-status`.
- The canonical agent layer lives in `.agents/` and `.codex/`; `template/.agents/`
  and `template/.codex/` are deterministic mirrors (except the intentional
  `.agents/README.md` and `.agents/context-map.yaml` divergences). After editing
  canonical agent-layer files, run `make sync-agent-layer`; `make
  validate-agent-layer` (part of `make check` and `make release-check`) proves
  the mirrors never drift.
- Keep task files as concise durable records. Execution detail belongs in
  commit history, PR descriptions, and review discussion, not task files.
- After project or task changes, run `make sync-project-docs` when generated
  dashboards need refresh. Those committed blocks intentionally carry only state
  that the canonical task records already decide.
- Read live, merge-derived task status, board, and next action with
  `make project-status`. Never create a commit that only reconciles an
  already-merged task.
- Finish by running `make validate-project`.
- For every agent-made change, commit the agent's own changes, push the branch
  to `origin`, and open a ready GitHub pull request. Do not push directly to
  `main`.
- Template releases use two maintainer-only commands that never bypass the
  branch/PR workflow: `make template-release-prepare BUMP=<major|minor|patch>`
  creates the reviewable version commit on a non-`main` release branch, and
  `make template-release-tag` creates the annotated release tag only after the
  release PR is merged to `main` and local `main` matches `origin/main`.
- Every template change is a release. As part of the same change, choose the
  SemVer bump (`major` for breaking template or update contracts, `minor` for
  new template capability, `patch` for fixes, tooling, or documentation that
  preserve behavior) and add an English entry under a dated
  `## vX.Y.Z - YYYY-MM-DD` section in `CHANGELOG.md` for exactly that version.
  `CHANGELOG.md` must never contain an `Unreleased` section.
  `make template-release-prepare` refuses to prepare a release whose newest
  `CHANGELOG.md` section is not the version being prepared, and
  `make validate-template-docs` (part of `make check`) rejects `Unreleased`
  sections, malformed release headings, non-descending releases, an empty newest
  section, and a changelog version that is neither the current `template.version`
  nor exactly one SemVer bump ahead. That permissive window is intentional: it
  lets release preparation run before the version commit exists.
  `make validate-template-release-ready` (executed by Template CI after
  `make release-check`) requires the newest `CHANGELOG.md` release to equal
  `template.version` exactly. Template CI then runs
  `make validate-template-release-boundary`, which proves `HEAD` itself
  introduces that version relative to `HEAD^1`. The version transition must be
  the final release-PR commit so rebase history remains taggable.

Canonical agent procedures are in `.agents/`. Codex-specific adapter notes are
in `.codex/`. Project-specific context is in `project/` and `docs/`.

## Project State Reconciliation

Before declaring template work ready, reconcile durable planning/status
documentation with the actual repository state whenever a change can affect
template capabilities, architecture decisions, roadmap or milestone progress,
previously planned work, or next-task selection. Identify the planning and
status artifacts that actually exist here (`project/state.yaml`,
`project/board.md`, `project/index.md`, `project/roadmap.md`,
`project/tasks/`) and compare them against the post-change repository state.

- Mark work complete only when it was actually delivered; do not mechanically
  advance the previous backlog order.
- Re-evaluate the next meaningful task from current template capabilities,
  milestone goals, unresolved evidence gaps, accepted architecture decisions,
  and existing examples or tests. Prefer the smallest evidence-producing next
  slice.
- Search planning/status artifacts for stale wording such as "next task",
  "planned", "deferred", "not yet implemented", "open decision",
  "prerequisite", "upcoming", or "blocked".
- If no planning/status artifact needs a change, state that reconciliation was
  checked and no update was required.

Because this repository uses managed governance, end agent reports with a short
`Project State Check` stating what became complete, the next meaningful step,
and why it follows from the current repository state.

The task lifecycle, approval controls, and `project/state.yaml` remain
authoritative for managed task state. Committed dashboards carry only the
deterministic subset of that state - project-global rows - while task status,
the board, available tasks, and local worktree claims are rendered at read time
by `make project-status`. Reconciliation complements them by checking whether
higher-level planning stays accurate; it never edits managed task state or
generated boards directly.

## Boundaries

Do not add production runtime, databases, queues, brokers, Redis, or external
infrastructure unless a later approved task explicitly scopes that work.
