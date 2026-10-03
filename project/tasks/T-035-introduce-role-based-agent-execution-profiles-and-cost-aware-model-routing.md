---
id: T-035

title: Introduce role-based agent execution profiles and cost-aware model routing

status: review

priority: 1

milestone: M-08

depends_on: [T-034]

approval_level: A1

approval_status: pending

approved_by:

approved_at:

blocked_reason: null

unblock_action: null
---

# T-035: Introduce Role-Based Agent Execution Profiles and Cost-Aware Model Routing

## Goal

Introduce generated-project execution-policy primitives: canonical planner /
implementer / reviewer / fixer roles that resolve deterministically to reusable
execution profiles (harness, opaque model, reasoning effort, cost class,
capabilities), a deterministic escalation and budget evaluator, a structured
usage/invocation contract, and a structured review-result contract. This is the
first layer of issue #24 - policy, not orchestration - so the future closed-loop
orchestrator in #25 can consume stable decisions without T-035 launching any
model process.

## Context

The template already dogfoods a canonical agent layer (`.agents/`), a mirror
mechanism (`tools/agent_layer.py`), an agent CLI (`template/tools/agent.py`),
`make validate-agent-skills`, and lightweight Python/dataclass/YAML patterns.
What is missing is a harness-independent execution policy: today the
`conventional-commit` skill pins a vendor model and the canonical validator
carries a vendor `CHEAP_MODELS` allowlist, conflating skill, role, profile,
harness, and model. T-035 separates those concepts, keeps default model ids
opaque/inherited, and prepares explicit seams for #25.

## Scope

- Add one visible canonical execution policy (`.agents/execution.yaml`) with
  exactly the roles `planner`, `implementer`, `reviewer`, `fixer`; reusable
  profiles; deterministic escalation/limits; and task/session/campaign budget
  configuration.
- Add a small deterministic resolver (`resolve_execution`, `evaluate_budget`,
  `review_next_action`) with no model-generated judgment: same config + inputs
  yields an identical decision.
- Expose the resolver through a thin `make agent-route ROLE=... FORMAT=json`
  surface that resolves policy only and never invokes a model.
- Add schemas under `.agents/schemas/` for the execution policy, the structured
  review result, and (only if a consumer needs it) the invocation record.
- Extend the existing `make validate-agent-skills` boundary to validate the
  policy, review-result, and role/profile references; unknown role/profile must
  fail clearly.
- Migrate `conventional-commit` from pinning a concrete model to requesting the
  `utility-cheap` profile, and remove the vendor cheap-model allowlist.
- Document skill vs role vs profile vs harness vs model and the deferred
  #25/#23/#10 boundaries; propagate canonical files through the existing mirror.

## Out of Scope

- The closed-loop orchestrator of #25 (goal decomposition, scheduler, retry /
  review / fix loops, campaign state, issue/PR creation, model invocation).
- #23 event/notification infrastructure and #10 Cline adapter work.
- Persistent usage/session/event stores, provider price tables, live vendor
  pricing, model benchmarking, or automatic cheapest-model discovery.
- Adding a new runtime dependency; heavyweight code-review ontology.

## Acceptance Criteria

- [x] Exactly the canonical roles `planner`, `implementer`, `reviewer`, `fixer`
      exist and each maps to an existing reusable profile.
- [x] Profiles carry harness, opaque model (`null` or non-empty string),
      reasoning effort, cost class, and capabilities; role resolution is
      deterministic and independent of vendor model names.
- [x] Attempt 1 uses the configured primary profile; no path silently promotes
      to another profile without an explicit escalation rule or input.
- [x] Deterministic escalation (implementation failures -> stronger profile;
      architecture finding -> planner; external blocker -> human) is visible in
      the decision and never auto-invokes a role.
- [x] Task/session/campaign budget configuration is supported; budget evaluation
      blocks unsafe next execution and represents unknown cost honestly without
      inventing zero or a price.
- [x] Attempt/review limits are deterministic and return a blocking/human
      decision instead of an automatic retry.
- [x] Structured review results validate (clean / changes_requested; blocking
      implementation/architecture/external findings) and reviewer output is
      independent and non-mutating.
- [x] Structured invocation/usage records are available to future consumers
      without introducing a usage/session/event database.
- [x] `conventional-commit` requests `utility-cheap` and no canonical
      vendor cheap-model allowlist remains.
- [x] Lightweight generated projects stay simple; generated managed projects
      expose `make agent-route` without automatic model invocation.
- [x] Mirror, generated-profile, and existing T-032/T-033/T-034 suites stay
      green; #25/#23/#10 remain unimplemented.

## Verification

- Focused: `make validate-agent-skills`, resolver/validation unit tests, mirror
  tests, and generated-render tests for the execution policy.
- Full gate: `make check`, invoked once through `make agent-pre-review
  TASK=T-035`.

## Documentation Impact

- Root agent guidance and `docs/template-development.md` explain skill vs role
  vs profile vs harness vs opaque model, customization via profiles, and that
  budgets use harness-reported usage with no vendor price table in the canonical
  layer.
- Generated project guidance notes that the execution policy is available but
  orchestration is not mandatory; lightweight projects keep `edit -> check ->
  done`.

## Completion Notes

`.agents/execution.yaml` is the canonical policy: the four roles map to
`reasoning-high` / `coding-efficient` / `utility-cheap` profiles whose `model`
defaults to `null` (the harness default), so no time-sensitive vendor model name
is pinned. `template/tools/agent_execution.py` is the pure, deterministic
resolver (`resolve_execution`, `evaluate_budget`, `review_next_action`,
`validate_policy`, `validate_review_result`, `build_invocation_record`); it has
no vendor branching and no price table. `template/tools/agent.py` validates the
policy and both schemas inside the existing `make validate-agent-skills`
boundary and exposes `make agent-route ROLE=<role> [FORMAT=json]`, which resolves
policy only and never invokes a model.

Retry/review limits and budget evaluation return `status=blocked` /
`action=human`; a configured cost ceiling with unknown cost blocks rather than
assuming safety; unknown token/cost values stay unknown. Escalation is explicit
(`implementation_failure`, `architecture_failure`, `external_blocker`) so an
agent cannot silently promote itself. Structured review results use
`.agents/schemas/review-result.schema.yaml`; a review never mutates code and
routes implementation findings to `fixer`, architecture findings to `planner`,
and external blockers to a human.

`conventional-commit` now requests the `utility-cheap` profile instead of a
pinned model, and the canonical `CHEAP_MODELS` allowlist is removed. Canonical
files propagate deterministically to `template/.agents/` and `template/.codex/`
via `make sync-agent-layer`; like other tools, `tools/agent_execution.py` is
emitted for every profile, while `make agent-route` stays managed-only. No
orchestrator, scheduler, retry loop, model execution, usage/session/event store,
#23 notification transport, or #10 Cline adapter was added.

Evidence: `tests/test_execution_policy.py` (19) proves the canonical roles,
role/profile separation, opaque models, harness independence, no silent
promotion, deterministic escalation, external-blocker human routing,
attempt/review limits, budget under/over limit, honest unknown usage, structured
review validation, reviewer independence, the conventional-commit migration, the
invocation record, generated lightweight/managed policy, and mirror propagation.
`tests/test_agent_one_task_workflow_golden_path.py` (4), `template/tools`
lint/format/strict-pyright, and the canonical `make check` gate stay green.
