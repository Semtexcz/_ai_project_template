---
id: T-033

title: Add focused resume context and compact task context

status: review

priority: 1

milestone: M-08

depends_on: [T-032]

approval_level: A1

approval_status: pending

approved_by:

approved_at:

blocked_reason: null

unblock_action: null
---

# T-033: Add Focused Resume Context and Compact Task Context

## Goal

Separate a task's complete branch change set from the current session's working
set, so a fresh resume session eagerly loads only an explicit, ephemeral focus
while the whole branch stays authoritative, observable, and discoverable.

## Context

A large `_ai_project_template` task can change 30-50 files, but a single fresh
session needs only a handful. `MODE=resume` currently treats every non-deleted
changed file as an eager context candidate, which conflates branch scope with the
session working set. T-032 made the task durable across fresh processes (task,
branch, worktree, claim, and PR persist; the conversation does not), so
continuation must extend to an explicit working-set selector without persisting
any focus state.

## Scope

- Extend `resolve_context(task_id, skill, mode, focus)` with an optional
  structured `focus` input plus a thin CLI/Make boundary (`FOCUS="path ..."`)
  accepting repository-relative exact files only.
- Apply focus to `MODE=resume` only: `MODE=new` and focused-less resume behavior
  stay unchanged, and focus in another mode is rejected clearly.
- Validate every focus path against the canonical exclusion/sensitive policies,
  repository containment, symlink escapes, directories, and missing files.
- When focus is supplied, eagerly load only the focused files (changed or not)
  and keep every non-focused changed file visible as metadata with an
  `outside focus` omission reason.
- Keep the complete branch change set, search roots, diff safety,
  governance/ownership, and recommended checks derived from the whole branch.
- Add deterministic file/byte observability (branch changed count, focused
  requested/loaded counts, eager file count, total bytes).
- Prove the behavior with a realistic 30+ changed-file fixture and focused
  coverage, and audit compact task context instead of adding a second task source.

## Out of Scope

- Issue #29 validation-level or CI redesign.
- Semantic/LLM focus selection, automatic focus guessing, persisted session state,
  or a second compact task file.
- Changing handoff behavior or adding focus state to the derived handoff.

## Acceptance Criteria

- [x] `resolve_context` accepts optional `focus`; `make agent-context TASK=<id>
      MODE=resume FOCUS="..."` works.
- [x] Focus is ephemeral and never persisted; repeated calls with the same
      repository state and focus produce byte-equivalent output.
- [x] Branch scope and session working set are separate machine-readable
      concepts, and `changed_files` stays complete.
- [x] Focus in a non-resume mode is rejected clearly; focused-less resume stays
      backward compatible.
- [x] Focus paths reject traversal/absolute/outside-root/symlink-escape/
      sensitive/excluded/missing/directory inputs.
- [x] Non-changed files can be explicitly focused; unfocused files remain
      discoverable through search roots with an `outside focus` reason.
- [x] Recommended checks and diff safety derive from the complete branch, not the
      focused subset.
- [x] Focused files still obey the deterministic budget and fail loudly when they
      cannot fit.
- [x] Governance/ownership/task/worktree invariants hold with focus.
- [x] A 30+ changed-file fixture resumes with a small 3-8-file eager working set,
      and context amplification is measurable in files/bytes.
- [x] Compact task context is audited; any reduction avoids a second source of
      truth.
- [x] T-032 handoff behavior and tests remain green, and generated small tasks
      need no `FOCUS`.
- [x] Focused tests and the current canonical pre-review gate pass; the task ends
      in `review` / `pending`.

## Verification

- Focused: `uv run pytest tests/test_agent_focused_resume.py
  tests/test_agent_efficiency.py tests/test_agent_context_routing.py
  tests/test_agent_handoff.py` (72 passed).
- Focused: `make test-workflow`, `make test-lifecycle`, `make test-static`,
  `make test-mirror`, `make test-copier-update` (all green after the generated
  project `make check` ruff/pyright alignment).
- Full gate: `make check` via `make agent-pre-review TASK=T-033`.

## Documentation Impact

- `docs/template-development.md`, `template/docs/workflow.md.jinja`,
  `template/AGENTS.md.jinja`, and `template/README.md.jinja` document the optional
  focused resume and `branch scope != session working set`.
- `.agents/context-map.yaml` and `template/.agents/context-map.yaml` route the new
  tooling and tests.

## Completion Notes

Focus is a small extension of the existing resolver, not a new subsystem.
`resolve_context(task_id, skill, mode, focus)` gained an optional `focus` list;
`make agent-context ... FOCUS="<path> ..."` passes it through `--focus` (a single
`nargs="+"` argument placed last). A new `validate_focus_paths()` reuses
`project_relative_path`, the canonical `exclude`/`SENSITIVE_PATTERNS` policies,
and the existing symlink-escape check, and rejects traversal, absolute paths,
`..`, `~`, directories, missing files, and sensitive/excluded files. A
`FOCUS_OMISSION_REASON` constant keeps the `outside focus` omission reason
distinct from `file budget`, `byte budget`, and `excluded`.

`collect_context_candidates()` gained a `focus` parameter: when focus is supplied,
focused files (changed or not) become protected `focused` eager candidates while
every non-focused changed file is recorded as `outside focus` metadata; the
complete changed-file set, change-pattern routing, and search roots are unchanged,
so `recommended_checks()` still derives from the whole branch. `select_budgeted()`
reports focused overflow with the same loud failure as task/skill/bootstrap
context (the message now names `focused`). `FORMAT=json` adds `focus_enabled`,
`focused_files`, `focused_loaded_files`, and a deterministic `metrics` object
(`branch_changed_files_count`, `focused_requested_files_count`,
`focused_loaded_files_count`, `eager_files_count`, `total_bytes`); no token
estimation was introduced and no focus state is written anywhere.

Compact task context was audited rather than reimplemented: the canonical task
record is already the single authoritative source, is loaded once as protected
context, and every durable implementation field resume needs (goal, scope, out of
scope, unchecked acceptance criteria, verification) lives there. A derived runtime
task brief would either duplicate mutable acceptance criteria or drop the record
that readiness/completion rules read, so no second representation was added; the
large-fixture test records the resulting eager size as evidence instead.

Evidence: `tests/test_agent_focused_resume.py` (25 tests) proves exact and
non-changed focus loading, every invalid-path rejection, non-resume rejection,
complete branch visibility with a 32-file fixture, the `outside focus` reason,
search-root continuity, check parity between full and focused resume, governance
enforcement, byte-identical determinism, no-focus backward compatibility, a small
single-session task that never needs `FOCUS`, the structured Python API, and that
the T-032 handoff payload carries no focus state. On the representative large
fixture the branch reports 32+ changed files while the focused resume stays
within the design guardrails: at most 8 eager files and under 40 kB of eager
context - a measurable amplification reduction.
Also green: `tests/test_agent_efficiency.py`, `tests/test_agent_context_routing.py`,
`tests/test_agent_handoff.py` (72 together), `make test-workflow`,
`make test-lifecycle`, `make test-static`, `make test-mirror`,
`make test-copier-update`, `make validate-project`, and `make validate-agent-layer`.

