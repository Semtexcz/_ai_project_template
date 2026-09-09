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
- Skill-local `agents/` metadata may pin model profiles and validator scripts.
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

## Context Map

`.agents/context-map.yaml` is the canonical context routing definition. It
separates:

- `bootstrap.files`: Tier 0 repository rules that are always loaded (normally
  only `AGENTS.md`).
- `task.files`: the selected managed task record.
- `managed.files`: governance state files that exist in managed projects.
- `project_type.<profile>.files`: explicit narrow files for the project shape.
- `search_roots`: directories that are searchable only; they are never
  recursively loaded into context.
- `change_patterns`: routing from changed paths to narrowly relevant files and
  search roots.
- `checks`: focused validation recommendations per changed-path pattern.
- `budget`: deterministic `max_files` and `max_bytes`.

`make agent-context TASK=<id> SKILL=<skill>` routes the selected skill's
`reads:` metadata into context; missing skills fail clearly and missing read
files degrade safely. Directory reads become search roots.

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
run the full `make check` gate once before review
review the diff
update docs or record no documentation impact
capture learning only when repeated experience justifies a guardrail
```

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
