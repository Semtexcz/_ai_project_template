# AGENTS.md

## Required Start

Run or read the agent-oriented project status before changing files:

```bash
make agent-status
```

Respect exactly one active task. Then load only the context recommended by:

```bash
make agent-context TASK=<id>
```

## Project Workflow

- Before editing files, agents must be on a non-`main` branch. If the current
  branch is `main`, create a dedicated branch for the task first.
- Use `make task-ready`, `make task-start`, `make task-review`,
  `make task-complete`, and `make task-block` for state changes.
- Do not bypass the task lifecycle by silently editing task status.
- Do not autonomously run `make task-approve`; approval commands are only for a
  human.
- Run `make agent-pre-review TASK=<id>` before moving a task to review.
- After project or task changes, run `make sync-project-docs` when generated
  dashboards need refresh.
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

The task lifecycle, approval controls, `project/state.yaml`, and generated
dashboards remain authoritative for managed task status. Reconciliation
complements them by checking whether higher-level planning stays accurate; it
never edits managed task state or generated boards directly.

## Boundaries

Do not add production runtime, databases, queues, brokers, Redis, or external
infrastructure unless a later approved task explicitly scopes that work.
