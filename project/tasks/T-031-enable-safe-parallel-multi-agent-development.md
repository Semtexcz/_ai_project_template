---
id: T-031

title: Enable safe parallel multi-agent development in generated projects

status: review

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

# T-031: Enable Safe Parallel Multi-Agent Development in Generated Projects

## Goal

Let several agents work concurrently on different independent tasks in generated
managed projects without corrupting each other's work, by giving every active
task one Git-isolated worktree, one deterministic branch, and one race-safe local
task claim. Parallelism comes from Git isolation, never from multiple agents
mutating the same checkout.

Core invariant: one task -> one claim -> one branch -> one worktree -> one agent
-> one PR.

## Context

The governed lifecycle currently encodes a single-agent assumption:
`project/state.yaml` carries `work.active_task`, `transition_blocker()` rejects a
second `in-progress` task, and `validate_active_task()` enforces at most one
`in-progress` task whose id equals `work.active_task`. Every transition also
rewrites `state.yaml` plus the persisted dashboard blocks.

That model is incompatible with concurrent agents: parallel branches would each
have to rewrite the same global ownership field to announce "I am working on
T-101", producing exactly the merge conflicts this task removes, and a second
independent task could not legally be active at all.

T-027 established the human PR merge as the PR-mode completion boundary, T-029
separated persisted deterministic state from Git-relative runtime state, T-028
narrowed agent context and focused validation, and T-030 split `project.py` into
cohesive `project_tool` modules. This task builds the execution/isolation
substrate on top of that base.

## Scope

- Audit and classify current state as project-global, task-local, worktree-local,
  or derived/runtime; document the findings.
- Remove unnecessary global mutable task-ownership state instead of turning
  `active_task` into a list.
- Add a focused `project_tool/worktrees.py` owning deterministic branch naming,
  worktree discovery/creation, worktree/task association, dirty detection, safe
  removal, merged/unmerged branch checks, and task-scoped claims. Keep `git.py`
  read-only provenance and keep worktree mechanics separate from lifecycle policy.
- Make the claim mechanism local, observable, explicitly releasable, and
  race-safe using Git/filesystem primitives rather than a new database, and
  without lifecycle-only commits or ownership-only task-file edits.
- Allow multiple independent `in-progress` tasks while rejecting a second active
  task in one worktree, a second claim on one task, and premature dependent work.
- Reuse the canonical `effective_status()` / `dependencies_done()` dependency
  rules and expose deterministic runnable-task discovery for a future scheduler.
- Make `agent-status`, `agent-context`, `agent-pre-task`, and `agent-pre-review`
  worktree-aware and fail loudly on branch/claim/task-argument mismatches.
- Show concurrent agents in `make project-status` without committing ephemeral
  worktree paths or claims.
- Provide managed-only Make targets for worktree creation, inspection, safe
  removal, and explicit stale-claim release.
- Preserve the simple single-agent path, A1 human merge boundary, A2 pre-start
  approval, CI, review status, PR/task association, and Copier update safety.
- Update concise workflow/template documentation and focused tests.

## Out of Scope

- Long-term campaign planning, automatic planner -> implementer -> reviewer
  loops, model routing, Telegram/mobile control, or autonomous multi-task
  scheduling.
- Distributed/remote claim coordination across machines; v1 is one local Git
  repository with several worktrees and agent processes.
- GitHub API integration, new dependencies, or a second lifecycle status system.
- Broad golden-path test restructuring.

## Acceptance Criteria

- [x] Two independent tasks can be worked concurrently, each on a distinct branch
      and worktree, with isolated uncommitted changes.
- [x] Same-task double claiming is prevented atomically, and one worktree owns at
      most one task.
- [x] Multiple independent tasks may be `in-progress` without rewriting a shared
      global ownership field.
- [x] Dependency rules and all approval/PR governance semantics stay canonical
      and enforced; dependent work cannot start early.
- [x] Branch- and worktree-scoped context and diff remain isolated from other
      worktrees, and `git.py` stays read-only provenance.
- [x] Each task can independently reach review/PR; merging one task leaves another
      worktree valid and usable.
- [x] Cleanup refuses dirty worktrees and unique unmerged commits by default, with
      an explicit destructive override, and stale claims can be inspected and
      explicitly released.
- [x] Single-agent usage through the main checkout remains simple and unchanged.
- [x] Generated managed projects render for local/branch/pr, lightweight projects
      gain no multi-agent machinery, and Copier update remains safe.
- [x] Focused tests, `make check`, and `make release-check` pass; final-head GitHub
      Actions are green.
- [x] Task remains `review` / `pending`; the agent does not merge the PR.

## Verification

- Focused: new worktree/claim seam tests for local claim, race safety, cleanup,
  and worktree-aware context.
- Focused: `make validate-project` and `make test-lifecycle` for lifecycle and
  persisted/runtime behavior.
- Focused: `make test-agent` and context-routing tests for worktree-aware agent
  context.
- Focused: `make test-workflow` and `make test-copier-update` for generated
  project and update behavior.
- Focused: `make test-static` for rendering and scaffold contracts.
- Full gate: `make check`, then `make release-check` once before review.
- Manual: run the two-agent golden path in a rendered managed project and verify
  isolated branches, worktrees, diffs, and cleanup behavior.

## Documentation Impact

- Managed workflow documentation gains a concise section covering single-agent
  mode, parallel worktree mode, claim semantics, cleanup, stale-claim recovery,
  and dependency behavior.
- `.agents/context-map.yaml` gains focused routing for the new module and tests.
- `CHANGELOG.md` records the new capability.

## Completion Notes

Single-agent assumptions found and removed: `project/state.yaml` carried
`work.active_task`, `transition_blocker()` rejected a second `in-progress` task,
`validate_active_task()` enforced at most one active task plus a duplicated
`work.blocked` flag, every transition rewrote `state.yaml` and three committed
dashboards, and the agent tool resolved an omitted task from that global field.

Final model: ownership is derived from Git, never from a shared field. `claims.py`
resolves the owned task from the current branch plus a local claim stored in the
repository's Git directory (`O_CREAT|O_EXCL`, so two racing agents cannot both
win), and `worktrees.py` owns branch naming (`task/T-###-<slug>`), worktree
creation/removal outside the tracked tree, and dirty/merged predicates. A claim
survives process death and must be released explicitly; `agent-worktree-remove`
refuses dirty worktrees and unique unmerged commits unless `FORCE=1` is passed.

Persisted versus local state: `state.yaml`, `README.md`, `project/index.md`, and
`project/board.md` now hold project-global facts only, so a task transition
rewrites just the task record and parallel branches cannot conflict in shared
Markdown; live task status, the board, available tasks, and worktree claims are
rendered by `make project-status`. Dependency checks, A1 human-merge completion,
A2 pre-start approval, review gates, and PR/task association are unchanged.

Module ownership after T-030 is preserved: `model`, `storage`, `git` (read-only),
`worktrees`, `claims`, `lifecycle`, `rendering`, `docs`, `validation`,
`mutations`, `commands`, CLI; every module stays under the 500-line guardrail and
imports remain one-directional with no cycles.

Evidence: focused seam tests (`tests/test_project_tool_worktrees.py`, including a
two-process claim race), module-seam/lifecycle/static suites, and a rendered
managed `workflow_mode: pr` two-agent golden path that proves distinct branches
and worktrees, isolated uncommitted changes and branch-scoped context, both tasks
`in-progress` at once, per-task review and `pr-validate`, a merge of T-002 leaving
T-003's worktree valid, a conflict-free `git merge main` into the surviving
worktree, refusal of dirty/unmerged cleanup, and explicit `FORCE=1` override.
