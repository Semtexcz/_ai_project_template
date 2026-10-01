---
id: T-034

title: Separate implementation validation from CI and prove the multi-session workflow

status: in-progress

priority: 1

milestone: M-08

depends_on: [T-033]

approval_level: A1

approval_status: pending

approved_by:

approved_at:

blocked_reason: null

unblock_action: null
---

# T-034: Separate Implementation Validation from CI and Prove the Multi-Session Workflow

## Goal

Make template-authoring validation cost explicit by separating three boundaries -
focused implementation checks, one canonical local pre-review gate, and
exhaustive asynchronous CI - and prove the resulting multi-session workflow
(T-032 handoff + T-033 focused resume + T-034 boundaries) with a deterministic
golden path that never depends on GitHub.

## Context

`_ai_project_template` has unusually expensive validation surfaces (focused
routing tests, static/template validation, project-state validation, Copier
update tests, profiles, render matrix, golden paths, `release-check`). A long
implementation session that repeatedly runs `make check`/`release-check` and
polls CI wastes time, compute, and agent context. `make agent-context` already
routes changed files to `recommended_checks`, `make agent-pre-review` already
owns the single local gate, and GitHub Actions already run exhaustively after a
push. T-031 gave each task an isolated worktree/claim, T-032 a deterministic
bounded handoff across fresh processes, and T-033 a focused resume working set.
This task names the boundaries, prevents duplicated local full-gate execution,
and proves the multi-session loop end to end.

## Scope

- Document and enforce three validation boundaries: focused implementation
  checks (existing `recommended_checks`), one local pre-review gate
  (`make agent-pre-review` -> `make check` once), and exhaustive asynchronous
  CI/release validation.
- Keep `recommended_checks()` as the canonical focused-check source; add no
  second router or check map.
- Guarantee `agent-pre-review` continues to run diff safety and `make check`
  exactly once, and never invokes `release-check`.
- Audit and remove duplicated local full-gate execution (manual `make check`
  immediately before `agent-pre-review`) where it does not change test intent.
- Add a deterministic multi-session golden path covering implementation,
  handoff, fresh focused resume, PR boundary, a simulated exhaustive-only CI
  failure after local pre-review passes, and a fresh CI-repair session that
  preserves task, branch, worktree, claim, and the same PR.
- Update template-authoring/root agent documentation and generic shared skills;
  keep generated-project guidance light and keep `release-check` in real
  template release tooling.

## Out of Scope

- Removing or weakening required CI coverage; CI-internal deduplication beyond
  trivially safe cases.
- CI polling/`gh run watch`/scheduler/daemon/CI state, autonomous CI repair, or
  any orchestration for issues #23/#24/#25.
- Changing generated-project default validation structure or forcing template
  ceremony on lightweight projects.

## Acceptance Criteria

- [x] Template authoring clearly distinguishes focused implementation checks,
      local pre-review, and exhaustive CI (`docs/template-development.md`
      "Validation Boundaries", root `AGENTS.md`, `.agents/README.md`).
- [x] `recommended_checks()` stays canonical; routine implementation does not
      automatically execute `release-check`.
- [x] `agent-pre-review` runs `make check` exactly once, never `release-check`,
      and keeps its diff-safety guard (enforced by
      `test_pre_review_runs_one_canonical_gate`).
- [x] A representative implementation cycle does not manually run `make check`
      immediately before `agent-pre-review` (duplicate removed from the one-task
      golden path and enforced by
      `test_golden_paths_do_not_duplicate_the_local_full_gate`).
- [x] A deterministic golden path proves multi-session identity (task/branch/
      worktree/claim) and a small focused resume over 30+ branch changes.
- [x] The PR structural boundary stays valid with A1 `review` / `pending` and the
      human merge as completion.
- [x] A simulated exhaustive CI proxy can fail after local pre-review passes, and
      a fresh repair session fixes it and returns to review via existing
      lifecycle, reusing the same PR.
- [x] No transcript/log persistence or CI state is introduced; repair derives
      context from repository state plus explicit CI failure evidence.
- [x] Generated-project compatibility: template `release-check` and multi-session
      ceremony do not leak into the ordinary small-task flow.
- [x] T-032/T-033 suites stay green; focused tests pass and the canonical
      pre-review gate passes once; the task ends `review` / `pending`.

## Verification

- Focused: new multi-session golden path and pre-review invariant tests, plus
  `tests/test_agent_handoff.py` and `tests/test_agent_focused_resume.py` for the
  T-032/T-033 regressions.
- Full gate: `make check`, invoked through `make agent-pre-review TASK=T-034`.

## Documentation Impact

- Root `docs/template-development.md` and root agent guidance state the three
  boundaries, the implementation-session stop boundary, that CI is required but
  asynchronous, and that sessions must not poll CI.
- Shared/generic skill wording stays generic so generated projects inherit no
  template release ceremony.

## Completion Notes

Validation is now policy plus tests, not new orchestration. The three boundaries
are named in `docs/template-development.md` ("Validation Boundaries"), root
`AGENTS.md`, `.agents/README.md`, the `implement-change`/`verify-change`/
`review-change` skills, and the generated `template/docs/workflow.md.jinja` /
`template/AGENTS.md.jinja` guidance (kept generic and light). `recommended_checks`
stayed the only focused-check source: no second router, YAML check map, or
machine-readable validation block was added. The `agent.py` pre-review body is
unchanged (diff safety, then `run_command("make check")` once) and contains no
`release-check`; `context-map.yaml` documents that exhaustive validation belongs
to CI and release preparation.

The duplicated local gate was removed from
`tests/test_agent_one_task_workflow_golden_path.py`, and
`test_golden_paths_do_not_duplicate_the_local_full_gate` now fails if any golden
path invokes `make check` before `agent-pre-review`. No CI polling, scheduler,
CI status store, transcript, or session record was added; CI remains required and
asynchronous, and `release-check` stays in real template release tooling.

Evidence (all green): `tests/test_agent_multi_session_workflow_golden_path.py`
(1) proves Phases A-D - implementation with focused checks only and a bounded
handoff, a fresh process recovering the same task/branch/worktree/claim and a
small focused resume over 32 branch changes, the `pr-validate` boundary at A1
`review`/`pending`, a simulated exhaustive-only CI failure after local pre-review
passes, and a fresh repair session that returns review -> in-progress -> review,
repairs with focused checks, pushes the same PR, and turns the CI proxy green
with exactly one pre-review per cycle.
`tests/test_agent_efficiency.py` (48 with routing/mirror) covers the strengthened
pre-review invariant and the new de-duplication guard;
`tests/test_agent_handoff.py` + `tests/test_agent_focused_resume.py` (36),
`tests/test_template_static.py` (20),
`tests/test_project_state_validation_golden_path.py` (17), and
`tests/test_agent_one_task_workflow_golden_path.py` (4) remain green; the
canonical `make check` gate runs once through
`make agent-pre-review TASK=T-034`.
