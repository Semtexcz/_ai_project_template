"""Focused tests for the role-based execution policy (#24, policy layer).

These tests prove the deterministic execution-policy primitive: canonical roles,
role/profile separation, opaque models, harness independence, deterministic
escalation and limits, budget evaluation (including honest unknown cost),
structured review results, reviewer independence, the conventional-commit
migration, generated-project policy, and canonical/mirror propagation.

They deliberately do not test orchestration: T-035 implements policy only and
never launches a model.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
EXECUTION_TOOL = ROOT / "template" / "tools" / "agent_execution.py"
AGENT_TOOL = ROOT / "template" / "tools" / "agent.py"
MIRROR_TOOL = ROOT / "tools" / "agent_layer.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations via sys.modules
    spec.loader.exec_module(module)
    return module


EXECUTION = load_module("t035_execution", EXECUTION_TOOL)


def run(
    command: list[str],
    cwd: Path,
    *,
    expect_success: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(f"Command failed: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"Command unexpectedly passed: {' '.join(command)}")
    return result


def default_policy() -> dict:
    data = yaml.safe_load((ROOT / ".agents" / "execution.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def local_harness_policy() -> dict:
    """A fixture policy using a non-Codex harness and an opaque local model."""
    return {
        "schema_version": 1,
        "roles": {
            role: {"profile": "local-efficient"}
            for role in ("planner", "implementer", "reviewer", "fixer")
        },
        "profiles": {
            "local-efficient": {
                "harness": "local",
                "model": "my-local-model",
                "reasoning_effort": "medium",
                "cost_class": "efficient",
                "capabilities": ["implementation"],
            }
        },
    }


def budgeted_policy(limit: float | None) -> dict:
    policy = default_policy()
    policy["budgets"] = {
        "task": {"max_cost_usd": limit},
        "session": {"max_cost_usd": None},
        "campaign": {"max_cost_usd": None},
    }
    return policy


def finding(severity: str, category: str) -> dict:
    return {
        "severity": severity,
        "category": category,
        "location": "src/foo.py:42",
        "problem": "problem",
        "expected": "expected",
    }


def copy_project(
    tmp_path_factory: pytest.TempPathFactory,
    name: str,
    *,
    governance: str,
    workflow_mode: str = "pr",
) -> Path:
    generated = tmp_path_factory.mktemp(name) / name
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(generated.parent / "uv-cache"),
    }
    run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--skip-tasks",
            "--data",
            f"project_name=Execution {name}",
            "--data",
            "project_type=script",
            "--data",
            "runtime_level=local",
            "--data",
            f"governance={governance}",
            "--data",
            f"workflow_mode={workflow_mode}",
            "--data",
            "include_reference_feature=false",
            "--trust",
            "--vcs-ref=HEAD",
            str(ROOT),
            str(generated),
        ],
        ROOT,
        env=env,
    )
    return generated


@pytest.fixture(scope="module")
def lightweight_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return copy_project(tmp_path_factory, "lightweight", governance="lightweight", workflow_mode="local")


@pytest.fixture(scope="module")
def managed_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return copy_project(tmp_path_factory, "managed", governance="managed")


def test_canonical_roles_exist_in_default_policy() -> None:
    policy = default_policy()
    assert set(policy["roles"]) == {"planner", "implementer", "reviewer", "fixer"}
    assert EXECUTION.validate_policy(policy) == []
    for role in ("planner", "implementer", "reviewer", "fixer"):
        assert policy["roles"][role]["profile"] in policy["profiles"]


def test_policy_validation_fails_closed_for_unknown_keys_and_unsupported_escalation_fields() -> None:
    cases = [
        ({"surprise": True}, ".agents/execution.yaml has unknown key(s): surprise."),
        ({"policy": {"max_implementation_attempt": 3}}, "policy has unknown key(s): max_implementation_attempt."),
        ({"budgets": {"task": {"max_cost_us": 1}}}, "budgets.task has unknown key(s): max_cost_us."),
        ({"roles": {"implementer": {"foo": "bar"}}}, "roles.implementer has unknown key(s): foo."),
        ({"profiles": {"coding-efficient": {"surprise": True}}}, "profiles.coding-efficient has unknown key(s): surprise."),
        ({"escalation": {"implementation_failure": {"after_attempt": 2}}}, "escalation.implementation_failure has unknown key(s): after_attempt."),
        ({"escalation": {"implementation_failure": {"action": "human"}}}, "escalation.implementation_failure has unknown key(s): action."),
        ({"escalation": {"external_blocker": {"profile": "reasoning-high"}}}, "escalation.external_blocker has unknown key(s): profile."),
    ]
    for change, expected in cases:
        policy = default_policy()
        for section, value in change.items():
            policy[section] = value
        errors = EXECUTION.validate_policy(policy)
        assert any(expected in error for error in errors), errors
        with pytest.raises(EXECUTION.ExecutionPolicyError, match="unknown key"):
            EXECUTION.resolve_execution(policy, "implementer")


def test_canonical_trigger_specific_escalation_rules_validate_and_resolve() -> None:
    policy = default_policy()
    assert EXECUTION.validate_policy(policy) == []
    assert EXECUTION.resolve_execution(
        policy, "implementer", attempt=2, trigger="implementation_failure"
    ).profile == "reasoning-high"
    assert EXECUTION.resolve_execution(policy, "reviewer", trigger="architecture_failure").role == "planner"
    external = EXECUTION.resolve_execution(policy, "implementer", trigger="external_blocker")
    assert (external.status, external.action) == ("blocked", "human")


def test_resolver_rejects_invalid_runtime_numeric_inputs() -> None:
    policy = default_policy()
    for kwargs, expected in [
        ({"attempt": 0}, "attempt must be a positive integer"),
        ({"attempt": -1}, "attempt must be a positive integer"),
        ({"review_cycle": -1}, "review_cycle must be a non-negative integer"),
        ({"usage": {"input_tokens": -1}}, "usage.input_tokens must be non-negative"),
        ({"usage": {"output_tokens": -1}}, "usage.output_tokens must be non-negative"),
        ({"usage": {"cost_usd": -1, "cost_kind": "actual"}}, "usage.cost_usd must be non-negative"),
        ({"usage": {"elapsed_seconds": -1}}, "usage.elapsed_seconds must be non-negative"),
        ({"usage": {"attempt": 0}}, "usage.attempt must be a positive integer"),
    ]:
        with pytest.raises(EXECUTION.ExecutionPolicyError, match=expected):
            EXECUTION.resolve_execution(policy, "implementer", **kwargs)


def test_usage_cost_kind_consistency_is_fail_closed() -> None:
    for usage, expected in [
        ({"cost_kind": "unknown", "cost_usd": 1.23}, "must be null when usage.cost_kind is unknown"),
        ({"cost_kind": "actual"}, "is required when usage.cost_kind is actual"),
        ({"cost_kind": "estimated"}, "is required when usage.cost_kind is estimated"),
    ]:
        with pytest.raises(EXECUTION.ExecutionPolicyError, match=expected):
            EXECUTION.usage_from_mapping(usage)


def test_missing_usage_scope_cannot_bypass_a_configured_budget() -> None:
    policy = budgeted_policy(1.0)
    decision = EXECUTION.resolve_execution(
        policy, "implementer", usage={"cost_usd": 100, "cost_kind": "actual"}
    )
    assert (decision.status, decision.action, decision.budget.status) == ("blocked", "human", "unknown")
    assert "scope is missing" in (decision.budget.reason or "")

    open_policy = budgeted_policy(None)
    no_budget = EXECUTION.resolve_execution(
        open_policy, "implementer", usage={"cost_usd": 100, "cost_kind": "actual"}
    )
    assert (no_budget.status, no_budget.budget.status) == ("ready", "ok")


def test_role_profile_separation_changes_resolution_without_skill_logic() -> None:
    policy = default_policy()
    before = EXECUTION.resolve_execution(policy, "implementer")
    assert before.profile == "coding-efficient"

    edited = json.loads(json.dumps(policy))
    edited["roles"]["implementer"]["profile"] = "reasoning-high"
    after = EXECUTION.resolve_execution(edited, "implementer")
    # Only the policy edit changed the outcome; no skill logic was touched.
    assert after.profile == "reasoning-high"
    assert after.harness == "codex"
    assert after.reasoning_effort == "high"


def test_opaque_model_identifiers_resolve_without_vendor_branching() -> None:
    policy = default_policy()
    policy = json.loads(json.dumps(policy))
    policy["profiles"]["coding-efficient"]["model"] = "vendor-agnostic/opaque-xyz:7b"
    decision = EXECUTION.resolve_execution(policy, "implementer")
    assert decision.model == "vendor-agnostic/opaque-xyz:7b"
    assert EXECUTION.validate_policy(policy) == []
    # The canonical resolver never inspects the model string.
    source = EXECUTION_TOOL.read_text(encoding="utf-8")
    for banned in ["gpt-", "claude", "openai", "provider ==", "startswith("]:
        assert banned not in source


def test_harness_independence_local_profile_needs_no_role_change() -> None:
    policy = local_harness_policy()
    assert EXECUTION.validate_policy(policy) == []
    decision = EXECUTION.resolve_execution(policy, "implementer")
    assert decision.harness == "local"
    assert decision.model == "my-local-model"
    # Roles are unchanged from the canonical set even on a different harness.
    assert set(policy["roles"]) == set(EXECUTION.CANONICAL_ROLES)


def test_no_silent_promotion_uses_configured_primary_profile() -> None:
    policy = default_policy()
    assert EXECUTION.resolve_execution(policy, "implementer").profile == "coding-efficient"
    # Attempt 2 alone never promotes; escalation requires an explicit trigger.
    second = EXECUTION.resolve_execution(policy, "implementer", attempt=2)
    assert second.profile == "coding-efficient"
    assert second.escalated is False
    assert EXECUTION.resolve_execution(policy, "planner").profile == "reasoning-high"


def test_deterministic_escalation_from_implementation_failures() -> None:
    policy = default_policy()
    below = EXECUTION.resolve_execution(
        policy, "implementer", attempt=1, trigger="implementation_failure"
    )
    assert below.profile == "coding-efficient"
    assert below.escalated is False

    reached = EXECUTION.resolve_execution(
        policy, "implementer", attempt=2, trigger="implementation_failure"
    )
    assert reached.profile == "reasoning-high"
    assert reached.escalated is True
    assert reached.escalation_reason == "implementation failures >= 2"
    assert reached.as_dict()["profile"] == "reasoning-high"


def test_architecture_finding_escalates_to_planner() -> None:
    policy = default_policy()
    decision = EXECUTION.resolve_execution(policy, "reviewer", trigger="architecture_failure")
    assert decision.role == "planner"
    assert decision.profile == "reasoning-high"


def test_external_blocker_requires_human_not_another_retry() -> None:
    policy = default_policy()
    decision = EXECUTION.resolve_execution(policy, "implementer", trigger="external_blocker")
    assert decision.status == "blocked"
    assert decision.action == "human"
    assert "human" in decision.reason


def test_attempt_and_review_limits_block_deterministically() -> None:
    policy = default_policy()
    assert EXECUTION.resolve_execution(policy, "implementer", attempt=3).status == "ready"
    over = EXECUTION.resolve_execution(policy, "implementer", attempt=4)
    assert over.status == "blocked"
    assert over.action == "human"
    assert "attempt limit" in over.reason

    reviewer = EXECUTION.resolve_execution(policy, "reviewer", review_cycle=4)
    assert reviewer.status == "blocked"
    assert "review cycle limit" in reviewer.reason


def test_budget_under_limit_remains_ready() -> None:
    policy = budgeted_policy(1.0)
    decision = EXECUTION.resolve_execution(
        policy, "implementer", usage={"scope": "task", "cost_usd": 0.42, "cost_kind": "actual"}
    )
    assert decision.status == "ready"
    assert decision.budget.status == "ok"
    assert decision.budget.limit_usd == 1.0


def test_budget_exhausted_blocks_the_next_invocation() -> None:
    policy = budgeted_policy(1.0)
    decision = EXECUTION.resolve_execution(
        policy, "implementer", usage={"scope": "task", "cost_usd": 1.5, "cost_kind": "actual"}
    )
    assert decision.status == "blocked"
    assert decision.action == "human"
    assert decision.budget.status == "exhausted"


def test_unknown_usage_is_not_invented_as_zero() -> None:
    record = EXECUTION.usage_from_mapping({"scope": "task"})
    assert record is not None
    assert record.cost_usd is None
    assert record.cost_kind == "unknown"
    assert record.input_tokens is None
    assert record.output_tokens is None

    # A configured ceiling with unknown cost is never treated as safe.
    policy = budgeted_policy(1.0)
    decision = EXECUTION.resolve_execution(policy, "implementer", usage={"scope": "task"})
    assert decision.status == "blocked"
    assert decision.action == "human"
    assert decision.budget.status == "unknown"
    assert decision.budget.cost_usd is None

    # Without a ceiling, unknown cost simply stays unknown (no fabricated price).
    open_policy = budgeted_policy(None)
    open_decision = EXECUTION.resolve_execution(open_policy, "implementer", usage={"scope": "task"})
    assert open_decision.status == "ready"
    assert open_decision.budget.status == "ok"
    assert open_decision.budget.cost_usd is None


def test_public_evaluate_budget_is_a_safe_standalone_seam() -> None:
    """The public seam validates policy and usage without any prior call."""
    policy = budgeted_policy(1.0)

    under = EXECUTION.evaluate_budget(
        policy, {"scope": "task", "cost_usd": 0.4, "cost_kind": "actual"}
    )
    assert (under.status, under.limit_usd) == ("ok", 1.0)

    exhausted = EXECUTION.evaluate_budget(
        policy, {"scope": "task", "cost_usd": 1.0, "cost_kind": "actual"}
    )
    assert exhausted.status == "exhausted"

    # A malformed mapping never reaches budget arithmetic.
    with pytest.raises(EXECUTION.ExecutionPolicyError, match="cost_usd must be non-negative"):
        EXECUTION.evaluate_budget(
            policy, {"scope": "task", "cost_usd": -1, "cost_kind": "actual"}
        )

    # A dataclass cannot bypass normalization: constructing UsageRecord is not
    # validation.
    with pytest.raises(EXECUTION.ExecutionPolicyError, match="cost_usd must be non-negative"):
        EXECUTION.evaluate_budget(
            policy, EXECUTION.UsageRecord(scope="task", cost_usd=-1, cost_kind="actual")
        )

    # Malformed budget policy fails closed before any budget arithmetic.
    for broken_budgets in ({"task": {"max_cost_usd": -1}}, {"task": {"max_cost_us": 1}}):
        broken = default_policy()
        broken["budgets"] = broken_budgets
        with pytest.raises(EXECUTION.ExecutionPolicyError):
            EXECUTION.evaluate_budget(
                broken, {"scope": "task", "cost_usd": 0.4, "cost_kind": "actual"}
            )

    # A configured ceiling is never reported safe without proven cost/scope.
    for usage in (
        {"cost_usd": 0.4, "cost_kind": "actual"},  # missing scope
        {"scope": "task"},  # unknown cost
        None,  # no usage at all
    ):
        decision = EXECUTION.evaluate_budget(policy, usage)
        assert decision.status == "unknown"
        assert decision.blocks is True

    # Without a configured ceiling, absent usage stays valid.
    open_decision = EXECUTION.evaluate_budget(budgeted_policy(None), None)
    assert (open_decision.status, open_decision.blocks) == ("ok", False)

    # A claimed actual/estimated cost with no value is an error, never a guess.
    for kind in ("actual", "estimated"):
        with pytest.raises(EXECUTION.ExecutionPolicyError, match="is required"):
            EXECUTION.evaluate_budget(policy, {"scope": "task", "cost_kind": kind})

    # The public seam and resolve_execution share one deterministic decision.
    shared_usage = {"scope": "task", "cost_usd": 0.4, "cost_kind": "actual"}
    assert EXECUTION.evaluate_budget(policy, shared_usage) == EXECUTION.resolve_execution(
        policy, "implementer", usage=shared_usage
    ).budget


def test_structured_review_results_validate_and_reject_malformed() -> None:
    assert EXECUTION.validate_review_result({"result": "clean", "findings": []}) == []
    for category, expected_action, expected_role in [
        ("implementation", "fix", "fixer"),
        ("architecture", "plan", "planner"),
        ("external", "human", None),
    ]:
        result = {"result": "changes_requested", "findings": [finding("blocking", category)]}
        assert EXECUTION.validate_review_result(result) == []
        action = EXECUTION.review_next_action(result)
        assert action.action == expected_action
        assert action.role == expected_role

    non_blocking = {
        "result": "changes_requested",
        "findings": [finding("non_blocking", "implementation")],
    }
    assert EXECUTION.review_next_action(non_blocking).action == "complete"

    assert EXECUTION.validate_review_result({"result": "clean", "findings": [finding("blocking", "implementation")]})
    assert EXECUTION.validate_review_result(
        {"result": "changes_requested", "findings": []}
    )
    assert EXECUTION.validate_review_result(
        {"result": "maybe", "findings": [{"severity": "blocking"}]}
    )
    with pytest.raises(EXECUTION.ExecutionPolicyError):
        EXECUTION.review_next_action({"result": "nonsense", "findings": []})


def test_reviewer_role_is_independent_and_non_mutating() -> None:
    policy = default_policy()
    reviewer_caps = policy["profiles"][policy["roles"]["reviewer"]["profile"]]["capabilities"]
    assert "implementation" not in reviewer_caps
    assert "repair" not in reviewer_caps

    # A review result never routes back to a code-writing reviewer/implementer.
    for category in ("implementation", "architecture", "external"):
        action = EXECUTION.review_next_action(
            {"result": "changes_requested", "findings": [finding("blocking", category)]}
        )
        assert action.role not in {"reviewer", "implementer"}

    schema = yaml.safe_load(
        (ROOT / ".agents" / "schemas" / "review-result.schema.yaml").read_text(encoding="utf-8")
    )
    assert schema["required"] == ["result", "findings"]
    assert schema["findings"]["item_required_keys"] == [
        "severity",
        "category",
        "location",
        "problem",
        "expected",
    ]
    # The contract has no field for writing code, so review cannot mutate.
    assert not any(
        token in json.dumps(schema).lower() for token in ("write", "patch", "apply", "files")
    )


def test_conventional_commit_requests_utility_cheap_profile() -> None:
    model = ROOT / ".agents" / "skills" / "conventional-commit" / "agents" / "model.yaml"
    model_text = model.read_text(encoding="utf-8")
    assert 'profile: "utility-cheap"' in model_text
    assert "gpt-" not in model_text

    policy = default_policy()
    assert policy["profiles"]["utility-cheap"]["cost_class"] == "cheap"

    # No canonical vendor cheap-model allowlist may remain.
    assert "CHEAP_MODELS" not in AGENT_TOOL.read_text(encoding="utf-8")

    run(
        [sys.executable, "template/tools/agent.py", "validate-skills"],
        ROOT,
    )


def test_structured_invocation_record_is_available_to_consumers() -> None:
    policy = budgeted_policy(1.0)
    usage = {"scope": "task", "cost_usd": 0.42, "cost_kind": "actual", "input_tokens": 12000}
    decision = EXECUTION.resolve_execution(policy, "implementer", attempt=2, usage=usage)
    record = EXECUTION.build_invocation_record(
        decision, task="T-101", result="failed", usage=usage
    ).as_dict()
    for key in [
        "role",
        "profile",
        "harness",
        "model",
        "reasoning_effort",
        "task",
        "attempt",
        "reason",
        "result",
        "escalation",
        "budget",
        "usage",
    ]:
        assert key in record
    assert record["task"] == "T-101"
    assert record["result"] == "failed"
    assert record["usage"]["input_tokens"] == 12000
    json.dumps(record)  # the record is plain, JSON-serializable data


def test_agent_route_cli_resolves_policy_without_invoking_a_model() -> None:
    planner = run(
        [sys.executable, "template/tools/agent.py", "route", "--role", "planner", "--format", "json"],
        ROOT,
    )
    data = json.loads(planner.stdout)
    assert data["status"] == "ready"
    assert data["role"] == "planner"
    assert data["profile"] == "reasoning-high"
    assert data["harness"] == "codex"
    assert data["model"] is None
    assert data["reasoning_effort"] == "high"
    assert data["escalated"] is False

    escalated = run(
        [
            sys.executable,
            "template/tools/agent.py",
            "route",
            "--role",
            "implementer",
            "--attempt",
            "2",
            "--trigger",
            "implementation_failure",
            "--format",
            "json",
        ],
        ROOT,
    )
    payload = json.loads(escalated.stdout)
    assert payload["profile"] == "reasoning-high"
    assert payload["escalated"] is True

    unknown = run(
        [sys.executable, "template/tools/agent.py", "route", "--role", "nope"],
        ROOT,
        expect_success=False,
    )
    assert "Unknown role" in unknown.stdout

    for option, value, expected in [
        ("--attempt", "0", "attempt must be a positive integer"),
        ("--review-cycle", "-1", "review_cycle must be a non-negative integer"),
    ]:
        invalid = run(
            [sys.executable, "template/tools/agent.py", "route", "--role", "implementer", option, value],
            ROOT,
            expect_success=False,
        )
        assert expected in invalid.stdout


def test_generated_projects_expose_the_execution_policy(
    lightweight_project: Path, managed_project: Path
) -> None:
    for project, managed in [(lightweight_project, False), (managed_project, True)]:
        assert (project / ".agents" / "execution.yaml").exists()
        assert (project / ".agents" / "schemas" / "execution-policy.schema.yaml").exists()
        assert (project / ".agents" / "schemas" / "review-result.schema.yaml").exists()
        assert (project / "tools" / "agent_execution.py").exists()
        makefile = (project / "Makefile").read_text(encoding="utf-8")
        assert "validate-agent-skills:" in makefile
        # Lightweight projects keep no orchestration surface; managed ones do.
        assert ("agent-route:" in makefile) is managed
        env = {**os.environ, "UV_CACHE_DIR": str(project.parent / "uv-cache")}
        run(["make", "validate-agent-skills"], project, env=env)

    # A managed project can resolve policy for humans and future orchestration.
    result = run(
        [sys.executable, "tools/agent.py", "route", "--role", "implementer", "--format", "json"],
        managed_project,
    )
    data = json.loads(result.stdout)
    assert data["role"] == "implementer"
    assert data["profile"] == "coding-efficient"
    assert data["status"] == "ready"


def test_execution_policy_mirrors_propagate_deterministically() -> None:
    pairs = [
        (".agents/execution.yaml", "template/.agents/execution.yaml"),
        (
            ".agents/schemas/execution-policy.schema.yaml",
            "template/.agents/schemas/execution-policy.schema.yaml",
        ),
        (
            ".agents/schemas/review-result.schema.yaml",
            "template/.agents/schemas/review-result.schema.yaml",
        ),
        (
            ".agents/skills/conventional-commit/agents/model.yaml",
            "template/.agents/skills/conventional-commit/agents/model.yaml",
        ),
        (
            ".codex/skills/conventional-commit/SKILL.md",
            "template/.codex/skills/conventional-commit/SKILL.md",
        ),
    ]
    for canonical, mirror in pairs:
        assert (ROOT / canonical).read_bytes() == (ROOT / mirror).read_bytes(), mirror
    run([sys.executable, str(MIRROR_TOOL), "check"], ROOT)
