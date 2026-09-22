---
id: T-030

title: Refactor project.py into cohesive project-governance modules

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

# T-030: Refactor project.py into Cohesive Project-Governance Modules

## Goal

Reduce the context cost and change amplification of project-governance work by
replacing the 1837-line `template/tools/project.py` monolith with a small
package of cohesive modules behind an unchanged public CLI.

## Context

`template/tools/project.py` currently owns root discovery, the task model,
status/workflow constants, a simple YAML codec, task/state loading, Git merge
provenance, lifecycle transitions, approvals, transactional mutations, project
and task validation, documentation validation, deterministic persisted
rendering, runtime merge-aware rendering, drift detection, synchronization, PR
validation, and CLI parsing at once. Any localized governance change therefore
forces an agent to read and reason about the whole file, which is the
amplification issue #19 targets - especially before issue #18 adds multi-agent
support on top of the same lifecycle rules.

T-029 (PR #21) split persisted deterministic state from runtime Git-relative
state inside the same file. This task must move that code without redesigning
its ownership model.

## Scope

- Audit responsibilities, dependencies, external callers (`template/tools/agent.py`,
  `tools/template_release.py`, tests, Makefiles), and existing behavioral
  coverage before choosing module boundaries.
- Extract cohesive modules under `template/tools/project_tool/` for the model,
  persistence/parsing, Git provenance, lifecycle policy, rendering, project/task
  validation, documentation validation, and the explicit mutation boundary.
- Reduce `template/tools/project.py` to CLI parsing, dispatch, minimal
  bootstrap, top-level error handling, and compatibility exports required by
  existing importlib callers.
- Keep `python tools/project.py ...` working in rendered projects and keep every
  existing Make target and command argument compatible.
- Add focused context routing for the new package paths and document the
  resulting ownership map in `docs/template-development.md`.
- Update `.agents/context-map.yaml` checks so Git completion, rendering, docs
  validation, and lifecycle-rule changes each map to a small neighborhood.
- Verify Copier rendering/update safety for the new generated files.

## Out of Scope

- Issue #18 multi-agent support, #12 general Python architecture, #11
  documentation redesign, #16 Agent Efficiency v2.
- T-019 (Pydantic + Typer), a new task schema, a new persistence format,
  new dependencies, GitHub API integration, distributed locking.
- Lifecycle, approval, or completion-semantics redesign; broad golden-path test
  restructuring.

## Acceptance Criteria

- [x] `project.py` is a thin CLI/composition layer (147 lines) that still works
      when executed as `python tools/project.py ...`.
- [x] `task_merge_completed()` semantics, `effective_status()`, PR-mode
      merge-derived completion, A2 pre-start approval, local/branch persisted
      completion, deterministic persisted dashboards, and live merge-aware
      `make project-status` are unchanged.
- [x] No circular imports, no generic utility dumping ground, no new monolithic
      replacement module, and one canonical implementation per behavior.
- [x] Extracted modules use precise typing without copying the monolith's
      file-wide Pyright/Ruff suppressions.
- [x] All commands, arguments, output messages, and exit semantics remain
      compatible, and existing importlib consumers of `project.py` keep working.
- [x] Context routing reflects the new module ownership, and
      `docs/template-development.md` documents the ownership map.
- [x] Focused tests pass, `make check` passes, `make release-check` passes, and
      generated local/branch/pr projects work through their Make targets.
- [x] Task remains `review` / `pending`; the agent does not merge the PR.

## Verification

- Focused: `uv run pytest tests/test_agent_context_routing.py` for new routing.
- Focused: `make validate-project` and `make test-lifecycle` for lifecycle,
  approval, merge-provenance, and persisted/runtime behavior.
- Focused: `make test-static` for generated scaffold, copier config, Makefile,
  and T-029 rendering contracts.
- Focused: `make test-workflow` and `make test-copier-update` for generated
  project and update behavior.
- Full gate: `make check`, then `make release-check` once before review.
- Manual: run `python tools/project.py status|validate|sync` inside rendered
  local, branch, and pr projects.

## Documentation Impact

- `docs/template-development.md` gains a compact ownership map for the new
  modules.
- `.agents/context-map.yaml` gains focused routing and checks for
  `template/tools/project_tool/**`.
- `CHANGELOG.md` records the structural refactor.

## Completion Notes

`template/tools/project.py` went from 1837 lines to a 147-line CLI over
`template/tools/project_tool/` (`model` 134, `storage` 265, `git` 83,
`lifecycle` 226, `rendering` 390, `docs` 289, `validation` 408, `mutations` 166,
`commands` 216). Imports stay one-directional with no cycles, no generic utility
module, and no new monolith; `project.py` keeps only the compatibility exports
that `tools/agent.py` and `tools/template_release.py` load by path.

Behavioral evidence: 92 focused tests passed (lifecycle, static, workflow,
agent efficiency, mirror, routing, new module seams), `make agent-pre-review`
ran the canonical `make check` gate green, ruff and pyright strict are clean
without the monolith's file-wide suppressions, and rendered lightweight/local,
managed/branch, and managed/pr projects passed `python tools/project.py
status|validate|sync` plus their Make targets, transition guards, and Definition
of Done enforcement. T-029 ownership is untouched: merge provenance,
effective-status derivation, deterministic persisted blocks, and the live
merge-aware status view behave exactly as before.
