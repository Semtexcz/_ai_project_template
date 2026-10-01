---
id: T-032

title: Separate managed tasks from agent sessions and add deterministic handoff

status: in-progress

priority: 1

milestone: M-08

depends_on: []

approval_level: A1

approval_status: pending

approved_by: null

approved_at: null

blocked_reason: null

unblock_action: null
---

# T-032: Separate Managed Tasks from Agent Sessions and Add Deterministic Handoff

## Goal

Let one large template-authoring task continue across fresh agent processes by
rendering a compact, deterministic, runtime-only handoff from authoritative task,
Git, worktree, claim, change-summary, and context-routing state. The task,
branch, worktree, claim, and PR persist; the conversation does not.

## Context

One managed task already keeps one branch, worktree, claim, and PR, but a large
`_ai_project_template` task can outlive a single useful agent conversation.
T-026 through T-031 provide bounded context, branch-aware changes, modular
governance, merge-derived PR completion, and local worktree claims; continuation
needs to derive their durable state without storing session records or
transcripts. Repository state stays authoritative and conversation history stays
disposable.

## Scope

- Add a structured `AgentHandoff` representation plus concise human and
  machine-readable (JSON) command output in the existing agent tooling.
- Reuse canonical task, effective-status, dependency, ownership, worktree,
  branch-aware changed-file, lifecycle next-action, and recommended-check APIs;
  fail loudly on task/worktree ownership mismatch.
- Keep handoff derived, runtime-only, deterministic, bounded (<= 8 kB for
  representative normal state), and free of diffs, transcripts, reasoning, logs,
  command history, and copied documentation.
- Reduce safely redundant implementation-session bootstrap context and stop
  eagerly loading unrelated planning/dashboard artifacts for ordinary
  already-selected implementation work where the routing machinery already
  resolves what is needed.
- Cover determinism, fresh-process continuation, dirty state, change sources,
  ownership mismatch, payload bound, routing consistency, single-session
  compatibility, and rendered managed-project behavior with focused tests.
- Document optional handoff/resume use for maintainers and generated managed
  projects without making it mandatory ceremony.

## Out of Scope

- Issue #28 focused working-set or `FOCUS` behavior; issue #29 validation-level
  or CI redesign.
- Session identifiers, persistence, databases, transcripts, reasoning storage,
  orchestration, schedulers, or telemetry frameworks.
- Making handoff mandatory, adding managed-session machinery to lightweight
  projects, or adding a second compact task record.

## Acceptance Criteria

- [x] `make agent-handoff TASK=<id>` and `FORMAT=json` return deterministic
      structured output derived only from canonical repository state.
- [x] Output covers task identity/lifecycle/approval/dependencies/blocker,
      branch/HEAD/worktree/claim ownership and dirty state, a compact
      branch-aware changed-file summary with change source, a bounded set of
      recent task commits, derivable remaining acceptance criteria, the
      lifecycle next action, reused recommended checks, deterministic resume
      commands, and small metrics.
- [x] Ownership mismatch fails loudly; changed files never embed contents.
- [x] Normal handoff output is at most 8 kB and contains no transcript,
      reasoning, full diff, full logs, or command history.
- [x] The normal one-session `agent-status` -> `agent-context` -> implement ->
      `agent-pre-review` flow stays valid without invoking handoff.
- [x] Ordinary implementation context no longer eagerly loads unrelated
      planning/dashboard artifacts or routing-only files.
- [x] Focused tests pass and the canonical pre-review gate passes; the task ends
      `review` / `pending` with exactly one PR and no agent merge.

## Verification

- Focused: new handoff tests including cross-subprocess determinism and resume.
- Focused: `make validate-project`, `make test-agent`, `make test-lifecycle`,
  `make test-static`, `make test-workflow`, `make test-copier-update`.
- Full gate: `make agent-pre-review TASK=T-032` once before review, then
  `make validate-project`.
- Manual: render a managed project, run handoff in a worktree, and confirm the
  normal single-session path still works unchanged.

## Documentation Impact

- Maintainer documentation explains the large-task multi-session continuation
  loop and that the task persists while the session does not.
- Generated managed project documentation describes handoff as optional
  resume/recovery tooling.
- `CHANGELOG.md`/`UPGRADING.md` update only if generated projects have a
  meaningful migration or upgrade implication.

## Completion Notes

`template/tools/agent_handoff.py` owns the handoff model: the frozen
`AgentHandoff` value, its deterministic JSON payload (schema version 1), the
concise human rendering, the canonical JSON size accounting, and a loud byte
budget. Derivation lives in `template/tools/agent.py` and reuses existing seams
only - `get_task`, `resolve_owner`, `worktree_states`, `effective_status`,
`acceptance_checkboxes`, `changed_file_entries`, `recommended_checks`,
`recommended_next_action` - so no second task loader, change detector, or
check router exists. `make agent-handoff TASK=<id>` (and `FORMAT=json`) is
managed-only; `tools/agent_handoff.py` is excluded from lightweight generation
and `implement-change` never references the target, so lightweight projects keep
validating their skills unchanged.

The handoff is derived and runtime-only: no session id, session record, claim of
persistence, timestamp, or second task file. Ownership mismatch fails loudly
(get_task + an explicit owned-task comparison), dirty state is reported, changed
files stay `(source, path)` entries capped at 40 with the true total reported,
and the payload fails loudly above 8 kB. Metrics are
`changed_files_count`, `recommended_checks_count`, and `handoff_bytes`.
`CONTEXT_STOP_CONDITIONS` is now a shared constant so handoff and context cannot
drift.

Context reduction: `implement-change` no longer eagerly reads
`.agents/context-map.yaml` or the `Makefile` (tooling resolves routing), and
`managed.files` keeps only `project/state.yaml`; the planning/reassessment skills
still read the dashboards through their own `reads:`.

Evidence: `tests/test_agent_handoff.py` (10 passed) proves cross-process
determinism, fresh-process reconstruction of task/branch/worktree/claim, the
8 kB bound with a 120-file change set and deterministic compaction, absence of
transcript/reasoning/diff/log/command-history, loud ownership mismatch and
unowned-checkout refusal, dirty/clean determinism, branch+staged+unstaged+
untracked change sources without contents, check/stop-condition/next-action
consistency with `agent-context`, the unchanged single-session loop, and the
rendered managed `make agent-handoff` target. Also green:
`tests/test_agent_efficiency.py` (29), `tests/test_agent_context_routing.py`
(13), `tests/test_agent_layer_mirror.py` (5),
`tests/test_project_tool_modules.py` + `tests/test_project_tool_worktrees.py`
(21), `tests/test_agent_one_task_workflow_golden_path.py` (4, including a full
generated `make check` with ruff and Pyright strict over `tools/`),
`tests/test_parallel_agent_worktrees_golden_path.py` (3),
`tests/test_script_local_golden_path.py` (1),
`tests/test_copier_update_golden_path.py` (3), `make test-static` (20),
`make test-lifecycle` (17), `make validate-project`,
`make validate-agent-skills`, `make validate-template-docs`,
`make validate-agent-layer`. One focused expectation moved with the narrowed
baseline: the context budget test now uses `max_files: 3`, and the
implement-change skill test now asserts the routing config and Makefile are
*not* eagerly loaded.
