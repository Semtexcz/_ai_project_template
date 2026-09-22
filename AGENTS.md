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
- Prefer focused checks while implementing; `make agent-pre-review` runs the
  canonical `make check` full gate once at final pre-review.
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
