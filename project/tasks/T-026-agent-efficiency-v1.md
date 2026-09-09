---
id: T-026

title: Agent efficiency v1

status: review

priority: 1

milestone: M-08

depends_on: []

approval_level: A1

approval_status: pending

blocked_reason: null

unblock_action: null

approved_by: null

approved_at: null
---

# T-026: Agent Efficiency v1

## Goal

Reduce the time, token/context usage, repeated repository reading, and
redundant validation performed by coding agents generated from this template,
without weakening managed governance or any existing validation coverage.

## Context

The generated agent workflow is correct but expensive. Startup instructions
duplicate context (`AGENTS.md` + manual doc reads + `agent-context`),
`.agents/context-map.yaml` directory entries are recursively expanded into
many files, skill `reads:` metadata is never used for routing, `git status`
loses committed branch changes after a commit, and `agent-pre-review` re-runs
validators that `make check` already covers. The change set must remain
harness-agnostic and must not redesign approvals, CI, or the task architecture.

## Scope

- Make startup use one canonical context-loading path with a three-tier model:
  minimal bootstrap, deterministic task/skill context, and exploration roots.
- Refactor `.agents/context-map.yaml` semantics to separate explicit files from
  search roots so a directory entry never silently becomes recursive eager
  context.
- Add deterministic context budgets (`max_files`, `max_bytes`) with stable
  ordering, truncation, omission reporting, and guaranteed task/skill priority.
- Use the selected skill's declared `reads:` as routing information via
  `make agent-context TASK=<id> SKILL=<name>`.
- Make changed-file detection branch-aware: union of branch diff against base,
  staged changes, unstaged changes, and untracked files, with a safe fallback
  when no remote/base exists.
- Make `recommended_checks()` use the actual changed-file set instead of
  defaulting to broad `make check` after commits.
- Run the canonical full validation gate once at final pre-review; remove
  validator duplication in `agent-pre-review`.
- Add a lightweight resume/review-fix context mode for existing PRs.
- Keep task-file guidance durable and concise (no execution journals) for
  future tasks; do not rewrite historical task files.
- Make context output observable (skill, files included/omitted, bytes,
  budget, category) in a human-scannable or machine-readable form.
- Preserve lightweight vs managed governance, one-active-task invariant,
  PR-only `main`, no self-approval, T-023 release workflow, and T-025
  project-state reconciliation.
- Add focused tests for context routing, budgets, branch-aware diffing,
  recommended checks, pre-review de-duplication, and generated-project
  rendering for representative configurations.
- Update affected documentation and provide measurable before/after context
  evidence for representative scenarios.

## Out of Scope

- Approval lifecycle redesign around GitHub PR review/merge.
- Broad GitHub Actions/CI architecture redesign.
- Removal of managed governance or the managed task lifecycle.
- New orchestration framework, vector databases, embeddings, or RAG.
- Harness-specific optimization or large-scale skill redesign.
- Rewriting historical task files or unrelated release-workflow changes.

## Acceptance Criteria

- [x] Startup no longer loads the same docs twice through the canonical path.
- [x] `make agent-context TASK=<id> SKILL=<name>` uses the skill's `reads:`
  metadata; missing/invalid skills fail clearly or degrade safely.
- [x] Directory context entries no longer recursively inject whole trees;
  explicit files and search roots have separate deterministic semantics.
- [x] Context generation enforces deterministic file and byte budgets and
  reports included/omitted files, approximate cost, and budget.
- [x] Changed-file detection includes committed branch changes plus staged,
  unstaged, and untracked files, with a safe fallback without `origin/main`.
- [x] `recommended_checks()` uses the actual changed-file set and favors
  focused checks during implementation.
- [x] Final pre-review runs the canonical full gate once without redundant
  validator execution through multiple paths.
- [x] A documented resume/review-fix mode exists that avoids full
  re-orientation for existing PR work.
- [x] Future task-writing guidance discourages execution-journal bloat while
  keeping durable task records concise.
- [x] Focused tests cover routing, budgets, diff scenarios, recommended
  checks, and pre-review de-duplication; representative generated projects
  render correctly.
- [x] Documentation is updated and representative context sizes are reported
  as before/after evidence.

## Verification

- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_efficiency.py -q`
  passed: 8 focused routing/budget/diff/pre-review/generated-profile tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_agent_one_task_workflow_golden_path.py -q`
  passed: 4 lifecycle golden-path tests.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_template_static.py tests/test_project_state_validation_golden_path.py -q`
  passed: 24 static/validation tests.
- `make check` passed once as the final canonical pre-review gate.
- `make validate-agent-skills`, `make validate-project`, and
  `make validate-template-docs` passed.
- Measured generated `script + managed` context for a new managed task: 7
  files / 10.6 KB included (previously the old model would have loaded 15
  files / 22.8 KB). Docs-only change: 8 files / 12.1 KB with focused
  `make validate-docs`; existing-PR fix in `MODE=resume`: 10 files / 17.9 KB
  with focused `make test`, `make typecheck`, `make lint`.

## Documentation Impact

Update root and generated agent instructions/context documentation, workflow
and architecture docs, the task template guidance, `UPGRADING.md`, and
`CHANGELOG.md` where materially affected.

## Completion Notes

Agent efficiency v1 is implemented: `.agents/context-map.yaml` is schema v2
with explicit `files`/`search_roots` and a `budget`; `agent-context` accepts
`SKILL=` (routes `reads:`) and `MODE=resume`; context output reports included
and omitted files with categories, roots, changed files, checks, and bytes;
changed-file detection is branch-aware (committed + staged + unstaged +
untracked with a base fallback); recommended checks are change-aware;
`agent-pre-review` runs the canonical `make check` once; startup no longer
duplicates documentation reads; task guidance stays concise; and focused tests
plus generated-profile renders cover the new behavior. Human A1 approval is
required before this task can complete.
