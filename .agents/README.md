# Agent Layer

`.agents/` is the canonical, tool-neutral agent layer. Skills represent reusable
agent capabilities. Governance controls project-management process. These are
separate concerns.

## Responsibilities

- Core engineering skills live in `.agents/skills/*/SKILL.md` and are available
  in lightweight and managed projects.
- Managed lifecycle skills live in `.agents/managed/skills/*/SKILL.md` and are
  generated only when `governance=managed`.
- Capability skills live in `.agents/capabilities/skills/*/SKILL.md` and are
  generated only for profiles with the matching specialized workflow.
- Skill-local `agents/` metadata requests an execution profile and a
  deterministic validator script; the profile's harness/model/reasoning settings
  live in `.agents/execution.yaml`.
- Skills describe judgment, inputs, reads, outputs, approval boundaries, and
  stop conditions. They do not rewrite task state.
- In managed projects, project state, task transitions, approvals, and dashboard
  sync are controlled by `tools/project.py`.
- Skill validation is controlled by `tools/agent.py`. Managed context commands
  and hooks are available only in managed projects.
- Tool-specific adapters such as `.codex/` only point back to these canonical
  skills.

## Skill Groups

Core skills:

- `orient-project`: build concise project orientation from durable context.
- `implement-change`: implement the smallest coherent requested change.
- `verify-change`: route changes to existing validation commands.
- `review-change`: review the actual diff before declaring readiness.
- `update-documentation`: decide and apply durable documentation updates.
- `create-adr`: create ADRs only for durable architectural decisions.
- `conventional-commit`: draft and validate one commit message when requested.
- `capture-learning`: convert repeated failures into executable guardrails,
  durable documentation, or agent instructions in that order.

Managed skills:

- `assess-project-state`
- `choose-next-task`
- `prepare-task`
- `complete-task`
- `reassess-project`

Capability skills:

- `change-api-contract` for full-stack OpenAPI/client workflows.
- `verify-production-artifact` for production runtime artifact checks.

## Execution Policy

`.agents/execution.yaml` is the one visible source of truth for role-based
execution policy. It separates four different things:

```text
skill   = what engineering operation runs        (implement-change, review-change, ...)
role    = why execution needs a quality/cost class (planner, implementer, reviewer, fixer)
profile = reusable execution policy              (harness, model, reasoning_effort, cost_class)
harness = where execution runs                   (codex today; local/other later)
model   = an opaque, harness-specific identifier (null = the harness default)
```

- Roles resolve deterministically to profiles; the canonical roles are exactly
  `planner`, `implementer`, `reviewer`, `fixer`.
- A `model: null` profile inherits the configured harness model, so no
  time-sensitive vendor model name is pinned in canonical policy. The resolver
  never interprets vendor model names and contains no price table.
- `make agent-route ROLE=<role> [FORMAT=json]` prints the deterministic decision
  (status, role, profile, harness, model, reasoning effort, capabilities,
  escalation, budget). It resolves policy only: it never launches a model.
- Policy validation is fail-closed: unknown keys are rejected rather than ignored,
  and escalation fields are trigger-specific (`implementation_failure` uses
  `after_attempts` + `profile`, `architecture_failure` uses `role`, and
  `external_blocker` uses `action: human`). Retry/review counters and reported
  usage values enforce their non-negative/positive domains before resolution.
- Budget configuration uses the logical scopes `task`, `session`, and `campaign`.
  The canonical layer only evaluates a configured ceiling against harness-reported
  usage; it never stores accounting and never derives a price. Contradictory cost
  records are rejected, and missing usage scope with a configured ceiling blocks
  rather than silently bypassing budget protection.
- Reviewer is a distinct role: it inspects and returns findings and never marks
  implementation reviewed. Structured review results use
  `.agents/schemas/review-result.schema.yaml`; implementation findings route to
  `fixer`, architecture findings to `planner`, and external blockers to a human.
- Orchestration (goal decomposition, retries, review/fix loops, scheduling) is a
  separate concern and is not part of the execution policy.

## Context Map

`.agents/context-map.yaml` is the canonical context routing definition. It
separates:

- `bootstrap.files`: Tier 0 repository rules that are always loaded (normally
  only `AGENTS.md`).
- `task.files`: the selected managed task record.
- `managed.files`: the managed governance baseline for an already selected task
  (`project/state.yaml`). Planning and dashboard artifacts (`project/index.md`,
  `project/board.md`, `project/roadmap.md`) are not eager: the task-selection,
  planning, and reassessment skills load them through their own `reads:`.
- `project_type.<profile>.files`: explicit narrow files for the project shape
  (here the `template` profile has no eager files).
- `search_roots`: directories that are searchable only; they are never
  recursively loaded into context.
- `change_patterns`: routing from changed paths to narrowly relevant files and
  search roots (for example `.agents/**` changes load `.agents/README.md`).
- `checks`: focused validation recommendations per changed-path pattern.
- `budget`: deterministic `max_files` and `max_bytes`.

`make agent-context TASK=<id> SKILL=<skill>` routes the selected skill's
`reads:` metadata into context; missing skills fail clearly and missing read
files degrade safely. Directory reads become search roots. Skill reads stay
narrow so context routing does not reintroduce whole-documentation preloading.

Task, selected-skill, and bootstrap files are protected from budget truncation.
Context output reports included files with categories, omitted files with
reasons, available search roots, changed files considered, and the total byte
cost. Use the default context mode for new tasks and `MODE=resume` when
resuming or fixing an existing PR.

Excludes block secrets, dependency directories, caches, and build artifacts.
Paths cannot traverse outside the project root and symlinks outside the root
are rejected.

The recommended loop is conceptual, not mandatory orchestration:

```text
orient when context is unclear
implement the scoped change
verify with focused deterministic checks
run `make agent-pre-review TASK=<id>` once to move to review
review the diff
update docs or record no documentation impact
capture learning only when repeated experience justifies a guardrail
```

`make agent-pre-review` owns the single local `make check` gate: do not run
`make check` immediately before it. Exhaustive validation (`make release-check`,
the render matrix, generated-project golden paths, and the Copier update path)
is CI's job. It is required but asynchronous: after the task is in review and the
branch is pushed, the implementation session ends, and it does not wait for or
poll CI. A CI failure starts a fresh session that resumes from the handoff.

## Canonical Agent-Layer Mirror

`.agents/` and `.codex/` are canonical at the repository root. Their mirrored
copies under `template/.agents/` and `template/.codex/` are deterministic
derived output so generated projects start from identical skills, schemas, and
adapters. Edit the canonical root files once, then propagate:

```bash
make sync-agent-layer
```

`make validate-agent-layer` (included in `make check` and `make release-check`)
verifies the mirrors byte-for-byte, so canonical and derived assets cannot
drift silently and propagation is idempotent. Two files are intentional
divergences and are never mirrored: `.agents/README.md` and
`.agents/context-map.yaml` describe this template repository, while their
`template/.agents/` counterparts describe generated projects (profile routing,
lightweight vs managed governance, template-local guidance).

## Handoff

One managed task keeps one branch, worktree, local claim, and pull request, but a
large template-authoring task can outlive one useful agent conversation. The
handoff makes the durable state reconstructible without any conversation history:

```text
task persists
session does not
```

```bash
make agent-handoff TASK=<id>              # concise human view
make agent-handoff TASK=<id> FORMAT=json  # machine-readable
```

The handoff is derived, runtime-only, deterministic, bounded (at most 8 kB), and
machine-readable. It reports task identity and lifecycle, branch/HEAD/worktree/
claim ownership and dirty state, a compact branch-aware changed-file summary, a
bounded set of recent task commits, the remaining acceptance criteria, the
lifecycle next action, the checks resolved by the same context routing,
deterministic resume commands, and small metrics (`changed_files_count`,
`recommended_checks_count`, `handoff_bytes`).

It contains no transcript, no reasoning, no diff, no test log, and no command
history, and it is never persisted: there is no session id, no session record,
and no second task file. Requesting a handoff from the wrong task or worktree
fails loudly. The normal one-session loop (`agent-status`, `agent-context`,
implement, `agent-pre-review`) never needs it.

## Hooks

Hooks are managed-governance guardrails. They are generated only when
`governance=managed`.

- `make agent-pre-task TASK=<id>` verifies readiness before implementation.
- `make agent-pre-review TASK=<id>` checks diff safety and lifecycle readiness,
  then runs the canonical `make check` full gate exactly once without re-running
  validators that gate already contains.
- `make agent-post-task TASK=<id>` verifies a completed task and synchronized
  project state.

Hooks may call project CLI functions, but they must not approve A1/A2 work or
silently change task status. In `workflow_mode: pr`, A1/A2 approval and
completion follow from the human GitHub merge of the pull request; hooks never
record that decision.

## Template Releases

Template releases use a two-phase, PR-only flow. They are maintainer actions in
the template repository root (`tools/template_release.py`), never in generated
projects, and they are never a backdoor for committing to `main`.

Every template change is a release: it bumps
`project/state.yaml.template.version` and adds an English entry under a dated
`## vX.Y.Z - YYYY-MM-DD` section in `CHANGELOG.md`. There is no `Unreleased`
section. `make validate-template-docs` (part of `make check`) rejects an
`Unreleased` section, malformed or non-descending release headings, an empty
newest release section, and a changelog version that is neither the current
`template.version` nor exactly one SemVer bump ahead.

Phase 1 (`make template-release-prepare BUMP=<major|minor|patch>`) prepares an
ordinary, reviewable version commit on a non-`main` release branch. It requires
a matching `CHANGELOG.md` release section, runs the release gate, updates
`project/state.yaml.template.version`, commits `chore(release): vX.Y.Z`, creates
no tag, pushes nothing, and refuses to run on `main`. The commit reaches `main`
only through the normal push -> pull request -> CI -> human approval -> merge
workflow.

Phase 2 (`make template-release-tag`) runs on clean, up-to-date `main` after
the release PR is merged. It fetches `origin main` (remote-tracking ref only),
verifies local `main` equals `origin/main`, verifies the current main tip
introduced the `template.version` transition from its first parent, refuses
existing local or remote tags, and creates an annotated tag at that release
boundary. The boundary may be a merge commit, squash commit, or the release
commit itself under fast-forward/rebase history. It never creates commits, never
rewrites history, and never force-pushes. Tagging is post-merge release metadata
and grants no exception to PR-only `main` governance.

Publication pushes only the intended tag (`git push origin vX.Y.Z`);
`--follow-tags` is not recommended because it can publish unrelated annotated
tags. Until publication the tag is not visible to Copier or GitHub. When
proposing a release, infer the semantic version bump from the merged change
set: `major` for breaking template or update contracts, `minor` for new
template capability, and `patch` for fixes, documentation, or tooling changes
that preserve behavior. Without a bump the command defaults to `patch`.
