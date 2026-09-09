# Template Authoring Cost Audit

Task: T-028 (GitHub issue #17).
Scope: why one logical template change currently requires too many files,
mirrored edits, context reads, and test runs - and what changed to reduce it.
Method: repository Git history and existing routing/validation tooling; no
synthetic metrics where real evidence exists.

## Highest-Cost Causes (ranked)

### 1. Agent-layer content is mirrored by hand (highest measured cost)

The template dogfoods its own agent layer: `.agents/` and `.codex/` are
canonical at the root and are duplicated under `template/.agents/` and
`template/.codex/` for generated projects. Every agent-layer change was
previously applied manually to both trees, and no test or tool enforced parity.

Repository evidence (files changed per merged PR):

| PR / work | Total files | `.agents` + `template/.agents` | `.codex` + `template/.codex` | Mirror edits share |
|---|---|---|---|---|
| #15 / issue #9 lifecycle | 38 | 14 | 2 | 16 files = 42% |
| #14 / Agent Efficiency v1 | 46 | 20 | 8 | 28 files = 61% |
| #5 skill architecture refactor | 72 | 34 | 23 | 57 files = 79% |

Current-state measurement: `.agents/` and `template/.agents/` are byte-identical
for every file except `README.md` and `context-map.yaml`; `.codex/` and
`template/.codex/` are fully byte-identical. Those two `.agents/` files are
intentional divergences (root describes the template repository, the template
copies describe generated projects), so the mirrored set is exact and
deterministic.

Classification: canonical source = root `.agents/`/`.codex/`; derived mirrored
output = `template/.agents/`/`template/.codex/` (except the two intentional
divergences).

Change made: `tools/agent_layer.py` (`check`/`sync`), `make sync-agent-layer`,
`make validate-agent-layer` wired into `make check` and `make release-check`,
plus focused drift/idempotence/protection tests.

### 2. Context routing treated every template change as one big neighborhood

Before this task the root `.agents/context-map.yaml` routed every change under
`template/**` (and `tests/**`, `tools/**`) to the same coarse treatment:
eager file `docs/template-development.md`, search roots `template/` + `tests/`,
and a recommended check of the full fast gate `make check`.

Concrete gaps:

- A change to `template/frontend/...` recommended `make check` (the whole fast
  gate), not the frontend/fullstack profile tests that prove the surface.
- A change to `template/tools/agent.py` recommended `make check`, which does not
  even execute `tests/test_agent_efficiency.py` (the test file that proves the
  agent tool); the real focused proof lived in release-check only.
- A change to `tests/test_agent_efficiency.py` recommended `make check`, again
  skipping the changed file itself.
- `.agents/**` changes recommended skill validation only; there was no
  mirror-drift guardrail, so a hand-edited template mirror passed.

Change made: the root map now has narrow per-surface neighborhoods and focused
check recommendations (see `change_patterns`/`checks` sections), profile search
roots are minimal, and unmatched paths keep the deterministic `make check`
fallback so no change silently escapes validation.

### 3. Governance/lifecycle changes touch duplicated authoritative prose

A PR #15-like decision is inherently wide, but part of the surface was
duplicated authority rather than real spread:

- `.agents/`/`.codex/` + mirrors (cause 1, fixed).
- Root `AGENTS.md` and `template/AGENTS.md.jinja` intentionally differ
  (root is maintainer guidance with template-release rules; the jinja renders
  generated-project guidance with lightweight/managed branches). Overlapping
  policy prose is duplicated manually.
- `docs/template-architecture.md` / `docs/template-development.md` (root docs)
  and `template/docs/workflow.md.jinja` (generated docs) are intentionally
  different audiences; the docs validator already guards drift between them.

Classification: `AGENTS.md` vs `template/AGENTS.md.jinja` and root docs vs
generated docs are intentionally different representations with partially
overlapping policy, not accidental duplicated files. Deduplicating them would
require rendering the jinja for this repository and merging maintainer-only
prose; left as a documented follow-up (#16/#11 territory), not done here.

### 4. Golden-path test setup duplication is real but low-change-cost

Every per-profile golden-path test re-declares a `run_command` helper and the
Copier render preamble (~40-50 duplicated lines across 8 modules). However,
these files are scenario-specific, change rarely per logical concept, and a
mechanical extraction would touch ~8 test files at once (itself amplification).
The frequently changed lifecycle/agent tests already centralize helpers.
Decision: no reorganization; if future evidence shows golden-path churn,
extract a shared `tests/` helper module as a separate small change.

Found during validation: the release-fixture suites
(`tests/test_copier_update_golden_path.py` and
`tests/test_template_release_workflow.py`) stubbed the copied-template
`release-check` recipe with an exact prerequisite-string match, which silently
stopped matching after the gate gained `validate-agent-layer` and caused nested
release-check recursion. Both fixtures now stub the recipe with a regex that is
independent of the prerequisite list, so the canonical gate can evolve without
editing the fixtures.

## Before/After Evidence

Mirror editing:

- Before: one skill edit = 2 manual file edits (skill + mirror); adapter
  changes also needed the `.codex` copy (2 more).
- After: one canonical edit + `make sync-agent-layer`; `make
  validate-agent-layer` proves parity byte-for-byte and is part of the
  canonical gates. Idempotence is tested.

Routing recommendations (resolver output for a single changed path):

| Changed path | Before (recommended check) | After (recommended check) |
|---|---|---|
| `template/frontend/pages/index.vue.jinja` | `make check` | `make test-frontend` |
| `template/backend/pyproject.toml.jinja` | `make check` | `make test-backend` |
| `template/tools/agent.py` | `make check` | `make validate-agent-skills`, `make test-agent` |
| `template/tools/project.py` | `make check` | `make validate-project`, `make test-lifecycle` |
| `.agents/skills/.../SKILL.md` | `make validate-agent-skills` | `make validate-agent-skills`, `make validate-agent-layer` |
| `tests/test_agent_efficiency.py` | `make check` | `uv run pytest tests/test_agent_efficiency.py` |

PR #15 regression scenario, after:

- `template/.agents/managed/skills/complete-task/SKILL.md` governance wording
  would be edited once at `.agents/managed/skills/complete-task/SKILL.md`,
  propagated by `make sync-agent-layer`, and proven by
  `make validate-agent-skills` + `make validate-agent-layer` +
  `make test-agent` instead of two hand edits and an over-broad gate.
- The root context map is the single routing authority: adding a future surface
  is one edit in `.agents/context-map.yaml`, and focused routing is proven by
  `tests/test_agent_context_routing.py`.

## Remaining Known Sources of Change Amplification

- `AGENTS.md` vs `template/AGENTS.md.jinja` and root docs vs generated docs
  share overlapping policy prose by hand (intentional representations; see
  cause 3). A governance change still requires touching several intentional
  representations plus their tests - fewer edits and context reads than before,
  but not zero.
- Context-budget evidence remains a manual measurement step; automation of
  before/after byte reports is possible follow-up.
- Golden-path preamble duplication (cause 4) stays documented, not reorganized.

## Follow-ups (explicitly not in this PR)

- Unified governance-prose rendering for root vs generated `AGENTS.md` /
  workflow docs (coordinate with #11/#16).
- Optional shared golden-path test helper module if profile churn increases.
- Optional generated-project context-map routing improvements beyond the root
  map this task narrowed.

