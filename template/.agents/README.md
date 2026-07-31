# Agent Layer

`.agents/` is the canonical, tool-neutral agent layer. It describes agent
judgment, context routing, and hook behavior, while deterministic state changes
remain in `tools/project.py` and `tools/agent.py`.

## Responsibilities

- Canonical skills live in `.agents/skills/*/SKILL.md`.
- Skills describe judgment and stop conditions. They do not rewrite task state.
- Project state, task transitions, approvals, and dashboard sync are controlled
  by `tools/project.py`.
- Agent orientation, context resolution, skill validation, and hooks are
  controlled by `tools/agent.py`.
- Tool-specific adapters such as `.codex/` only point back to these canonical
  skills.

## Context Map

`.agents/context-map.yaml` defines the minimum files to load. The resolver always
includes `AGENTS.md`, `project/state.yaml`, `project/index.md`, and the selected
task, then adds profile and changed-file context. Excludes block secrets,
dependency directories, caches, and build artifacts. Paths cannot traverse
outside the project root and symlinks outside the root are rejected.

## Hooks

- `make agent-pre-task TASK=<id>` verifies readiness before implementation.
- `make agent-pre-review TASK=<id>` checks diff safety, skills, project checks,
  and review readiness.
- `make agent-post-task TASK=<id>` verifies a completed task and synchronized
  project state.

Hooks may call project CLI functions, but they must not approve A1/A2 work or
silently change task status.
