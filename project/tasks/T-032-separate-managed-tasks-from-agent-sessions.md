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

- [ ] `make agent-handoff TASK=<id>` and `FORMAT=json` return deterministic
      structured output derived only from canonical repository state.
- [ ] Output covers task identity/lifecycle/approval/dependencies/blocker,
      branch/HEAD/worktree/claim ownership and dirty state, a compact
      branch-aware changed-file summary with change source, a bounded set of
      recent task commits, derivable remaining acceptance criteria, the
      lifecycle next action, reused recommended checks, deterministic resume
      commands, and small metrics.
- [ ] Ownership mismatch fails loudly; changed files never embed contents.
- [ ] Normal handoff output is at most 8 kB and contains no transcript,
      reasoning, full diff, full logs, or command history.
- [ ] The normal one-session `agent-status` -> `agent-context` -> implement ->
      `agent-pre-review` flow stays valid without invoking handoff.
- [ ] Ordinary implementation context no longer eagerly loads unrelated
      planning/dashboard artifacts or routing-only files.
- [ ] Focused tests pass and the canonical pre-review gate passes; the task ends
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

Pending.
