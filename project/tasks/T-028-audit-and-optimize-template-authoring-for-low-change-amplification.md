---
id: T-028

title: Audit and optimize template authoring for low change amplification

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

# T-028: Audit and Optimize Template Authoring for Low Change Amplification

## Goal

Make development of `_ai_project_template` itself substantially cheaper for
coding agents by reducing template-authoring change amplification: one logical
template change should have one canonical ownership location, deterministic
propagation where needed, and a small focused test neighborhood.

## Context

Template-authoring cost is the problem, not generated-project runtime
performance. One logical template change currently spreads across too many
files and mirrored representations, requiring too much repository context,
too many tests to understand and run, and therefore slow agent iteration.
PR #15 / issue #9 (large change surface for one lifecycle decision), Agent
Efficiency v1 (T-026), the release workflow (T-023), project lifecycle changes,
and representative template/profile changes provide repository evidence for an
audit of the highest-cost authoring patterns.

## Scope

- Run an evidence-based audit of representative recent changes (governance
  simplification, agent efficiency, release workflow, project lifecycle,
  template/profile changes) using real Git history and repository tooling.
  Record concise ranked durable findings under the existing audit structure.
- Classify duplicated or mirrored authoring surfaces (for example
  `.agents/` vs `template/.agents/`, `AGENTS.md` vs `template/AGENTS.md.jinja`)
  as canonical source, deterministic derived/mirrored output, intentionally
  different representation, or accidental duplicated authority; reduce the
  highest-value accidental duplicated authority with one canonical source plus
  a small deterministic, inspectable, CI-validated propagation mechanism.
- Narrow `.agents/context-map.yaml` routing so localized template changes do
  not force `template/`, `tests/`, and `docs/` to be treated as one large
  conceptual neighborhood; keep `search_roots` as discovery roots.
- Improve focused validation recommendations so the implementation loop runs
  the smallest affected checks, pre-review runs the canonical fast repository
  gate, and GitHub CI / release candidates keep the broader and full gates.
- Simplify golden-path test infrastructure only where duplication materially
  increases change cost; preserve explicit scenario intent.
- Introduce one small machine-readable concept -> canonical source -> derived
  outputs -> relevant tests/docs impact map only by extending the existing
  context-map architecture, not another metadata system.
- Document the resulting ownership and focused-validation knowledge concisely.

## Out of Scope

- Issues #10 (Cline adapter), #11 (documentation architecture), #12 (Python
  engineering), #13 (frontend engineering), #16 (Agent Efficiency v2), and
  #18 (multi-agent worktrees); they remain separate.
- A repository-wide rewrite, broad CI/performance redesign, or general
  templating abstraction.
- Weakening full release validation or correctness.

## Acceptance Criteria

- [x] The audit identifies concrete high-cost authoring patterns from
      repository evidence, ranked by impact.
- [x] Canonical versus derived/mirrored ownership is clearer and at least the
      highest-value accidental duplicated authority is reduced where safe.
- [x] Common template changes have narrower context routing and deterministic
      focused-check recommendations; full validation is preserved.
- [x] Test infrastructure is simplified where evidence justified it; focused
      tests cover drift prevention, idempotent propagation, narrow routing,
      deterministic check selection, and protection of intentionally different
      files.
- [x] Before/after authoring-efficiency evidence is documented, including a
      concrete PR #15-like regression scenario.
- [x] No unrelated architecture redesign was introduced; all required checks
      are green; task remains `review` / `pending` awaiting the human PR merge.

## Verification

- Focused mirror tests: `tests/test_agent_layer_mirror.py` (5 passed) proves
  parity, idempotent propagation, drift detection, stale-file removal, and
  protection of the intentional `.agents/` vs `template/.agents/` divergences.
- Focused routing tests: `tests/test_agent_context_routing.py` (10 passed)
  proves each template surface routes to its narrow checks, exact test-file
  changes run exactly that file, and the deterministic `make check` fallback
  survives for unmatched paths.
- `tests/test_agent_efficiency.py` (29 passed) and
  `tests/test_agent_one_task_workflow_golden_path.py` (4 passed) confirm the
  agent context/routing behavior did not regress (one routing expectation was
  updated because `.agents/**` changes now also recommend
  `make validate-agent-layer`).
- `make validate-template-docs`, `make validate-project`,
  `make validate-agent-skills`, and `make validate-agent-layer` pass.
- `make agent-pre-review TASK=T-028` (diff-safety + canonical `make check`)
  passes.
- `make release-check` (full pytest) result and the latest complete GitHub
  Actions run for the final head are recorded in the pull request once green.
- The PR description includes the ranked audit, before/after authoring
  evidence, the PR #15-like regression scenario, remaining amplification
  sources, and focused/full validation results.

## Documentation Impact

Concise durable audit findings and authoring-knowledge updates under the
existing audit/documentation structure; no new long general-purpose manual.

## Completion Notes

Pending.

## Notes

One concept -> one canonical ownership location -> deterministic propagation
where needed -> small focused test neighborhood. Keep the implementation
proportional: rank opportunities, implement only the highest-value
improvements, and leave lower-value ideas as documented follow-ups.
