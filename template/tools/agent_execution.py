"""Deterministic role-based execution policy for agent work (issue #24, policy layer).

This module is the *policy* half of role-based agent execution. It answers one
question deterministically:

    role -> configured policy -> execution profile -> decision

It never launches a model, never schedules a retry, and never persists state.
Orchestration (goal decomposition, retries, review/fix loops, scheduling) is a
separate concern and is deliberately out of scope here.

Separated concepts:

* skill   - what engineering operation is being performed (for example
            ``implement-change``); owned by ``.agents/skills``.
* role    - why a piece of execution needs a quality/cost class; the canonical
            roles are ``planner``, ``implementer``, ``reviewer``, ``fixer``.
* profile - reusable execution policy (harness, optional opaque model,
            reasoning effort, cost class, capabilities).
* harness - the execution environment (``codex`` today; ``local`` later).
* model   - an opaque, harness-specific identifier. This module never
            interprets vendor marketing names and contains no price tables.

The canonical configuration is ``.agents/execution.yaml``. Reading YAML stays in
``agent.py`` so this module has no runtime dependency beyond the standard library
and keeps working in generated projects without PyYAML.

Everything here is pure: same policy + same inputs -> identical decision, with no
model-generated judgment anywhere.
"""

from __future__ import annotations

# The execution policy arrives as untyped YAML, the same dynamic boundary that
# template/tools/agent.py already handles. These reportUnknown* rules are relaxed
# only for that boundary; every public value below is still explicitly typed and
# deterministically validated.
# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnnecessaryIsInstance=false
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

EXECUTION_SCHEMA_VERSION = 1

# The canonical role set. T-035 intentionally keeps this small; adding a role is
# a deliberate architecture decision, not a configuration detail.
CANONICAL_ROLES: tuple[str, ...] = ("planner", "implementer", "reviewer", "fixer")

REASONING_EFFORTS: tuple[str, ...] = ("low", "medium", "high")
COST_CLASSES: tuple[str, ...] = ("cheap", "efficient", "high")
ESCALATION_TRIGGERS: tuple[str, ...] = (
    "implementation_failure",
    "architecture_failure",
    "external_blocker",
)
COST_KINDS: tuple[str, ...] = ("actual", "estimated", "unknown")
BUDGET_SCOPES: tuple[str, ...] = ("task", "session", "campaign")
POLICY_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "schema_version",
    "roles",
    "profiles",
    "policy",
    "escalation",
    "budgets",
)
ROLE_ENTRY_KEYS: tuple[str, ...] = ("profile",)
PROFILE_KEYS: tuple[str, ...] = (
    "harness",
    "model",
    "reasoning_effort",
    "cost_class",
    "capabilities",
)
POLICY_SECTION_KEYS: tuple[str, ...] = (
    "max_implementation_attempts",
    "max_review_cycles",
)
BUDGET_ENTRY_KEYS: tuple[str, ...] = ("max_cost_usd",)
ESCALATION_RULE_KEYS: dict[str, tuple[str, ...]] = {
    "implementation_failure": ("after_attempts", "profile"),
    "architecture_failure": ("role",),
    "external_blocker": ("action",),
}

REVIEW_RESULTS: tuple[str, ...] = ("clean", "changes_requested")
FINDING_SEVERITIES: tuple[str, ...] = ("blocking", "non_blocking")
FINDING_CATEGORIES: tuple[str, ...] = ("implementation", "architecture", "external")

# Decision statuses and actions. ``status`` says whether the caller may proceed;
# ``action`` names who acts next (the harness or a human).
STATUS_READY = "ready"
STATUS_BLOCKED = "blocked"
ACTION_EXECUTE = "execute"
ACTION_HUMAN = "human"


class ExecutionPolicyError(Exception):
    """A request or policy that cannot produce a valid deterministic decision."""


def _optional_str(raw: Any, label: str) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ExecutionPolicyError(f"{label} must be a non-empty string or null.")
    return raw


@dataclass(frozen=True)
class UsageRecord:
    """Structured usage reported for one execution attempt.

    Values the harness cannot report stay ``None``/``unknown``. Nothing is
    invented: a missing cost is never treated as zero and no price is derived.
    """

    role: str | None = None
    profile: str | None = None
    task: str | None = None
    attempt: int = 1
    result: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    cost_kind: str = "unknown"
    elapsed_seconds: float | None = None
    scope: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the usage as a plain mapping for records and JSON output."""
        return {
            "role": self.role,
            "profile": self.profile,
            "task": self.task,
            "attempt": self.attempt,
            "result": self.result,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "cost_kind": self.cost_kind,
            "elapsed_seconds": self.elapsed_seconds,
            "scope": self.scope,
        }


def usage_from_mapping(value: Mapping[str, Any] | None) -> UsageRecord | None:
    """Normalize and validate a harness usage mapping into a :class:`UsageRecord`.

    Missing values stay unknown; they are never fabricated as zero. Reported
    numeric values must be within their public domains, and cost kind/value pairs
    must agree so malformed accounting cannot alter a budget decision.
    """
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ExecutionPolicyError("usage must be a mapping.")

    def optional_int(key: str) -> int | None:
        raw = value.get(key)
        if raw is None:
            return None
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ExecutionPolicyError(f"usage.{key} must be an integer or null.")
        if raw < 0:
            raise ExecutionPolicyError(f"usage.{key} must be non-negative.")
        return raw

    def optional_number(key: str) -> float | None:
        raw = value.get(key)
        if raw is None:
            return None
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not isfinite(float(raw)):
            raise ExecutionPolicyError(f"usage.{key} must be a finite number or null.")
        if raw < 0:
            raise ExecutionPolicyError(f"usage.{key} must be non-negative.")
        return float(raw)

    cost_kind = value.get("cost_kind", "unknown")
    if cost_kind not in COST_KINDS:
        raise ExecutionPolicyError(f"usage.cost_kind must be one of: {', '.join(COST_KINDS)}.")
    attempt = value.get("attempt", 1)
    if isinstance(attempt, bool) or not isinstance(attempt, int):
        raise ExecutionPolicyError("usage.attempt must be an integer.")
    if attempt < 1:
        raise ExecutionPolicyError("usage.attempt must be a positive integer.")
    scope = value.get("scope")
    if scope is not None and scope not in BUDGET_SCOPES:
        raise ExecutionPolicyError(f"usage.scope must be one of: {', '.join(BUDGET_SCOPES)}.")
    cost_usd = optional_number("cost_usd")
    if cost_kind == "unknown" and cost_usd is not None:
        raise ExecutionPolicyError("usage.cost_usd must be null when usage.cost_kind is unknown.")
    if cost_kind in {"actual", "estimated"} and cost_usd is None:
        raise ExecutionPolicyError(
            f"usage.cost_usd is required when usage.cost_kind is {cost_kind}."
        )
    return UsageRecord(
        role=_optional_str(value.get("role"), "usage.role"),
        profile=_optional_str(value.get("profile"), "usage.profile"),
        task=_optional_str(value.get("task"), "usage.task"),
        attempt=attempt,
        result=_optional_str(value.get("result"), "usage.result"),
        input_tokens=optional_int("input_tokens"),
        output_tokens=optional_int("output_tokens"),
        cost_usd=cost_usd,
        cost_kind=str(cost_kind),
        elapsed_seconds=optional_number("elapsed_seconds"),
        scope=None if scope is None else str(scope),
    )


def _validated_usage(
    usage: Mapping[str, Any] | UsageRecord | None,
) -> UsageRecord | None:
    """Validate both public usage input forms through one normalization path."""
    if isinstance(usage, UsageRecord):
        return usage_from_mapping(usage.as_dict())
    return usage_from_mapping(usage)


@dataclass(frozen=True)
class BudgetDecision:
    """Deterministic budget evaluation for one logical scope."""

    status: str
    scope: str | None
    limit_usd: float | None
    cost_usd: float | None
    cost_kind: str
    reason: str | None

    @property
    def blocks(self) -> bool:
        """Whether this budget decision must prevent another invocation."""
        return self.status in {"exhausted", "unknown"}

    def as_dict(self) -> dict[str, Any]:
        """Return the budget decision as a plain mapping."""
        return {
            "status": self.status,
            "scope": self.scope,
            "limit_usd": self.limit_usd,
            "cost_usd": self.cost_usd,
            "cost_kind": self.cost_kind,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExecutionDecision:
    """The deterministic result of resolving one role to one execution profile."""

    status: str
    action: str
    role: str
    profile: str
    harness: str
    model: str | None
    reasoning_effort: str
    capabilities: tuple[str, ...]
    attempt: int
    review_cycle: int
    reason: str
    escalated: bool
    escalation_reason: str | None
    trigger: str | None
    budget: BudgetDecision

    def as_dict(self) -> dict[str, Any]:
        """Return the decision as a plain, JSON-serializable mapping."""
        return {
            "status": self.status,
            "action": self.action,
            "role": self.role,
            "profile": self.profile,
            "harness": self.harness,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "capabilities": list(self.capabilities),
            "attempt": self.attempt,
            "review_cycle": self.review_cycle,
            "reason": self.reason,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
            "trigger": self.trigger,
            "budget": self.budget.as_dict(),
        }


@dataclass(frozen=True)
class ReviewNextAction:
    """The deterministic next action implied by a structured review result."""

    action: str
    role: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        """Return the next action as a plain mapping."""
        return {"action": self.action, "role": self.role, "reason": self.reason}


@dataclass(frozen=True)
class InvocationRecord:
    """Structured runtime record a future orchestrator (#25) can consume.

    This is an in-memory contract only. It is never persisted, so it is not a
    session store, usage database, or event log.
    """

    role: str
    profile: str
    harness: str
    model: str | None
    reasoning_effort: str
    task: str | None
    attempt: int
    reason: str
    result: str | None
    escalation: bool
    budget: BudgetDecision
    usage: UsageRecord | None

    def as_dict(self) -> dict[str, Any]:
        """Return the invocation record as a plain, JSON-serializable mapping."""
        return {
            "role": self.role,
            "profile": self.profile,
            "harness": self.harness,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "task": self.task,
            "attempt": self.attempt,
            "reason": self.reason,
            "result": self.result,
            "escalation": self.escalation,
            "budget": self.budget.as_dict(),
            "usage": None if self.usage is None else self.usage.as_dict(),
        }


def _positive_number(raw: Any) -> bool:
    return (
        not isinstance(raw, bool)
        and isinstance(raw, (int, float))
        and isfinite(float(raw))
        and float(raw) > 0
    )


def _unknown_keys(value: Mapping[str, Any], allowed: tuple[str, ...], label: str) -> list[str]:
    unknown = sorted(str(key) for key in value if key not in allowed)
    if not unknown:
        return []
    return [f"{label} has unknown key(s): {', '.join(unknown)}."]


def validate_policy(policy: Any) -> list[str]:
    """Validate an execution policy, returning deterministic error strings.

    Unknown roles or profiles always fail clearly. The checks deliberately stay
    small: enum sets, required keys, reference integrity, and value types.
    """
    errors: list[str] = []
    if not isinstance(policy, Mapping):
        return [".agents/execution.yaml must be a YAML mapping."]
    errors.extend(_unknown_keys(policy, POLICY_TOP_LEVEL_KEYS, ".agents/execution.yaml"))
    if policy.get("schema_version") != EXECUTION_SCHEMA_VERSION:
        errors.append(f".agents/execution.yaml schema_version must be {EXECUTION_SCHEMA_VERSION}.")
    profiles = policy.get("profiles")
    profile_map: Mapping[str, Any] = profiles if isinstance(profiles, Mapping) else {}
    if not isinstance(profiles, Mapping) or not profiles:
        errors.append(".agents/execution.yaml profiles must be a non-empty mapping.")
    for name, profile in profile_map.items():
        errors.extend(_validate_profile(str(name), profile))
    roles = policy.get("roles")
    if not isinstance(roles, Mapping):
        errors.append(".agents/execution.yaml roles must be a mapping.")
        roles = {}
    missing = [role for role in CANONICAL_ROLES if role not in roles]
    if missing:
        errors.append(
            "Missing canonical role(s): "
            f"{', '.join(missing)}. Required roles: {', '.join(CANONICAL_ROLES)}."
        )
    unknown_roles = [role for role in roles if role not in CANONICAL_ROLES]
    if unknown_roles:
        errors.append(
            "Unknown role(s): "
            f"{', '.join(sorted(unknown_roles))}. Only the canonical roles "
            f"{', '.join(CANONICAL_ROLES)} are allowed."
        )
    for role in CANONICAL_ROLES:
        entry = roles.get(role)
        if entry is None:
            continue
        if not isinstance(entry, Mapping):
            errors.append(f".agents/execution.yaml roles.{role} must be a mapping.")
            continue
        errors.extend(_unknown_keys(entry, ROLE_ENTRY_KEYS, f".agents/execution.yaml roles.{role}"))
        profile_name = entry.get("profile")
        if not isinstance(profile_name, str) or not profile_name.strip():
            errors.append(
                f".agents/execution.yaml roles.{role}.profile must be a non-empty string."
            )
        elif profile_name not in profile_map:
            errors.append(
                f".agents/execution.yaml roles.{role} references missing profile '{profile_name}'."
            )
    errors.extend(_validate_policy_section(policy.get("policy")))
    errors.extend(_validate_escalation(policy.get("escalation"), roles, profile_map))
    errors.extend(_validate_budgets(policy.get("budgets")))
    return errors


def _validate_profile(name: str, profile: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(profile, Mapping):
        return [f".agents/execution.yaml profiles.{name} must be a mapping."]
    errors.extend(_unknown_keys(profile, PROFILE_KEYS, f".agents/execution.yaml profiles.{name}"))
    harness = profile.get("harness")
    if not isinstance(harness, str) or not harness.strip():
        errors.append(f".agents/execution.yaml profiles.{name}.harness must be a non-empty string.")
    model = profile.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        errors.append(
            f".agents/execution.yaml profiles.{name}.model must be null or a non-empty "
            "opaque string."
        )
    if profile.get("reasoning_effort") not in REASONING_EFFORTS:
        errors.append(
            f".agents/execution.yaml profiles.{name}.reasoning_effort must be one of: "
            f"{', '.join(REASONING_EFFORTS)}."
        )
    if profile.get("cost_class") not in COST_CLASSES:
        errors.append(
            f".agents/execution.yaml profiles.{name}.cost_class must be one of: "
            f"{', '.join(COST_CLASSES)}."
        )
    capabilities = profile.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        errors.append(
            f".agents/execution.yaml profiles.{name}.capabilities must be a non-empty list."
        )
    else:
        for capability in capabilities:
            if not isinstance(capability, str) or not capability.strip():
                errors.append(
                    f".agents/execution.yaml profiles.{name}.capabilities entries must be "
                    "non-empty strings."
                )
    return errors


def _validate_policy_section(policy_section: Any) -> list[str]:
    errors: list[str] = []
    if policy_section is None:
        return errors
    if not isinstance(policy_section, Mapping):
        return [".agents/execution.yaml policy must be a mapping."]
    errors.extend(
        _unknown_keys(policy_section, POLICY_SECTION_KEYS, ".agents/execution.yaml policy")
    )
    for key in POLICY_SECTION_KEYS:
        value = policy_section.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            errors.append(f".agents/execution.yaml policy.{key} must be a positive integer.")
    return errors


def _validate_escalation(
    escalation: Any, roles: Mapping[str, Any], profiles: Mapping[str, Any]
) -> list[str]:
    errors: list[str] = []
    if escalation is None:
        return errors
    if not isinstance(escalation, Mapping):
        return [".agents/execution.yaml escalation must be a mapping."]
    for trigger, rule in escalation.items():
        if trigger not in ESCALATION_TRIGGERS:
            errors.append(
                f".agents/execution.yaml escalation trigger '{trigger}' is unknown. "
                f"Use one of: {', '.join(ESCALATION_TRIGGERS)}."
            )
            continue
        if not isinstance(rule, Mapping):
            errors.append(f".agents/execution.yaml escalation.{trigger} must be a mapping.")
            continue
        allowed = ESCALATION_RULE_KEYS[trigger]
        label = f".agents/execution.yaml escalation.{trigger}"
        errors.extend(_unknown_keys(rule, allowed, label))
        missing = [key for key in allowed if key not in rule]
        if missing:
            errors.append(f"{label} is missing required key(s): {', '.join(missing)}.")
        if trigger == "implementation_failure":
            target_profile = rule.get("profile")
            if target_profile not in profiles:
                errors.append(f"{label}.profile references missing profile '{target_profile}'.")
            after_attempts = rule.get("after_attempts")
            if (
                isinstance(after_attempts, bool)
                or not isinstance(after_attempts, int)
                or after_attempts < 1
            ):
                errors.append(f"{label}.after_attempts must be a positive integer.")
        elif trigger == "architecture_failure":
            target_role = rule.get("role")
            if target_role not in roles:
                errors.append(f"{label}.role references missing role '{target_role}'.")
        else:
            if rule.get("action") != ACTION_HUMAN:
                errors.append(f"{label}.action must be {ACTION_HUMAN}.")
    return errors


def _validate_budgets(budgets: Any) -> list[str]:
    errors: list[str] = []
    if budgets is None:
        return errors
    if not isinstance(budgets, Mapping):
        return [".agents/execution.yaml budgets must be a mapping."]
    unknown = [scope for scope in budgets if scope not in BUDGET_SCOPES]
    if unknown:
        errors.append(
            f".agents/execution.yaml budgets has unknown scope(s): "
            f"{', '.join(sorted(unknown))}. Use one of: {', '.join(BUDGET_SCOPES)}."
        )
    for scope, entry in budgets.items():
        if scope not in BUDGET_SCOPES:
            continue
        if not isinstance(entry, Mapping):
            errors.append(f".agents/execution.yaml budgets.{scope} must be a mapping.")
            continue
        label = f".agents/execution.yaml budgets.{scope}"
        errors.extend(_unknown_keys(entry, BUDGET_ENTRY_KEYS, label))
        if "max_cost_usd" not in entry:
            errors.append(f"{label} is missing required key: max_cost_usd.")
            continue
        limit = entry.get("max_cost_usd")
        if limit is not None and not _positive_number(limit):
            errors.append(f"{label}.max_cost_usd must be null or a positive number.")
    return errors


def policy_role_profile(policy: Mapping[str, Any], role: str) -> str:
    """Return the configured primary profile for ``role``, failing when unknown."""
    roles = policy.get("roles")
    if not isinstance(roles, Mapping) or role not in roles:
        raise ExecutionPolicyError(
            f"Unknown role '{role}'. Canonical roles: {', '.join(CANONICAL_ROLES)}."
        )
    entry = roles[role]
    if not isinstance(entry, Mapping):
        raise ExecutionPolicyError(f"roles.{role} must be a mapping.")
    profile_name = entry.get("profile")
    profiles = policy.get("profiles")
    if (
        not isinstance(profile_name, str)
        or not isinstance(profiles, Mapping)
        or profile_name not in profiles
    ):
        raise ExecutionPolicyError(f"roles.{role} references missing profile '{profile_name}'.")
    return profile_name


def _profile(policy: Mapping[str, Any], profile_name: str) -> Mapping[str, Any]:
    profiles = policy.get("profiles")
    if not isinstance(profiles, Mapping) or profile_name not in profiles:
        raise ExecutionPolicyError(f"Unknown profile '{profile_name}'.")
    profile = profiles[profile_name]
    if not isinstance(profile, Mapping):
        raise ExecutionPolicyError(f"profiles.{profile_name} must be a mapping.")
    return profile


def _ok_budget() -> BudgetDecision:
    return BudgetDecision("ok", None, None, None, "unknown", None)


def resolve_execution(
    policy: Mapping[str, Any],
    role: str,
    *,
    attempt: int = 1,
    review_cycle: int = 0,
    trigger: str | None = None,
    usage: Mapping[str, Any] | UsageRecord | None = None,
) -> ExecutionDecision:
    """Resolve ``role`` to a deterministic :class:`ExecutionDecision`.

    The primary profile always comes from configuration. The only ways the
    profile can change are an explicit escalation trigger or a configured limit;
    an agent cannot silently promote itself to a stronger, costlier profile.
    """
    errors = validate_policy(policy)
    if errors:
        raise ExecutionPolicyError("; ".join(errors))
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ExecutionPolicyError("attempt must be a positive integer.")
    if isinstance(review_cycle, bool) or not isinstance(review_cycle, int) or review_cycle < 0:
        raise ExecutionPolicyError("review_cycle must be a non-negative integer.")
    if trigger is not None and trigger not in ESCALATION_TRIGGERS:
        raise ExecutionPolicyError(
            f"Unknown trigger '{trigger}'. Use one of: {', '.join(ESCALATION_TRIGGERS)}."
        )
    record = _validated_usage(usage)
    primary_profile = policy_role_profile(policy, role)
    policy_section = policy.get("policy")
    policy_section = policy_section if isinstance(policy_section, Mapping) else {}
    escalation = policy.get("escalation")
    escalation = escalation if isinstance(escalation, Mapping) else {}

    # Deterministic limits first: an exhausted limit refuses another attempt and
    # returns a human decision rather than scheduling anything.
    if role == "implementer":
        limit = policy_section.get("max_implementation_attempts")
        if isinstance(limit, int) and attempt > limit:
            return _blocked_decision(
                policy,
                role=role,
                profile_name=primary_profile,
                attempt=attempt,
                review_cycle=review_cycle,
                trigger=trigger,
                reason="implementation attempt limit exhausted",
                usage=usage,
            )
    if role == "reviewer":
        limit = policy_section.get("max_review_cycles")
        if isinstance(limit, int) and review_cycle > limit:
            return _blocked_decision(
                policy,
                role=role,
                profile_name=primary_profile,
                attempt=attempt,
                review_cycle=review_cycle,
                trigger=trigger,
                reason="review cycle limit exhausted",
                usage=usage,
            )

    if trigger == "external_blocker":
        return _blocked_decision(
            policy,
            role=role,
            profile_name=primary_profile,
            attempt=attempt,
            review_cycle=review_cycle,
            trigger=trigger,
            reason="external blocker requires a human decision",
            usage=usage,
        )

    effective_role = role
    effective_profile = primary_profile
    escalated = False
    escalation_reason: str | None = None

    rule = escalation.get(trigger) if trigger is not None else None
    if trigger is not None and isinstance(rule, Mapping):
        rule_role = rule.get("role")
        rule_profile = rule.get("profile")
        threshold = rule.get("after_attempts")
        applies = True
        if trigger == "implementation_failure" and isinstance(threshold, int):
            applies = attempt >= threshold
        if applies:
            if isinstance(rule_role, str) and rule_role in (policy.get("roles") or {}):
                effective_role = rule_role
            if isinstance(rule_profile, str):
                effective_profile = rule_profile
            else:
                effective_profile = policy_role_profile(policy, effective_role)
            escalated = True
            escalation_reason = _escalation_reason(trigger, threshold, effective_role)
        else:
            escalation_reason = (
                f"implementation failure below escalation threshold ({threshold}); "
                f"retry configured profile {primary_profile}"
            )

    profile = _profile(policy, effective_profile)
    budget = _ok_budget()
    if record is not None:
        budget = evaluate_budget(policy, record)

    status = STATUS_READY
    action = ACTION_EXECUTE
    reason = escalation_reason or f"{effective_role} uses configured profile {effective_profile}"
    if budget.blocks:
        status = STATUS_BLOCKED
        action = ACTION_HUMAN
        reason = budget.reason or "budget prevents another invocation"

    return ExecutionDecision(
        status=status,
        action=action,
        role=effective_role,
        profile=effective_profile,
        harness=str(profile.get("harness", "")),
        model=profile.get("model"),
        reasoning_effort=str(profile.get("reasoning_effort", "")),
        capabilities=tuple(str(item) for item in (profile.get("capabilities") or [])),
        attempt=attempt,
        review_cycle=review_cycle,
        reason=reason,
        escalated=escalated,
        escalation_reason=escalation_reason,
        trigger=trigger,
        budget=budget,
    )


def _escalation_reason(trigger: str, threshold: Any, effective_role: str) -> str:
    if trigger == "implementation_failure" and isinstance(threshold, int):
        return f"implementation failures >= {threshold}"
    if trigger == "architecture_failure":
        return f"architecture review finding requires {effective_role}"
    return f"{trigger} escalated to {effective_role}"


def _blocked_decision(
    policy: Mapping[str, Any],
    *,
    role: str,
    profile_name: str,
    attempt: int,
    review_cycle: int,
    trigger: str | None,
    reason: str,
    usage: Mapping[str, Any] | UsageRecord | None,
) -> ExecutionDecision:
    profile = _profile(policy, profile_name)
    budget = _ok_budget()
    record = _validated_usage(usage)
    if record is not None:
        budget = evaluate_budget(policy, record)
    return ExecutionDecision(
        status=STATUS_BLOCKED,
        action=ACTION_HUMAN,
        role=role,
        profile=profile_name,
        harness=str(profile.get("harness", "")),
        model=profile.get("model"),
        reasoning_effort=str(profile.get("reasoning_effort", "")),
        capabilities=tuple(str(item) for item in (profile.get("capabilities") or [])),
        attempt=attempt,
        review_cycle=review_cycle,
        reason=reason,
        escalated=False,
        escalation_reason=None,
        trigger=trigger,
        budget=budget,
    )


def evaluate_budget(policy: Mapping[str, Any], usage: UsageRecord | None) -> BudgetDecision:
    """Evaluate a configured cost ceiling against reported usage.

    A configured ceiling with *unknown* accumulated cost is never treated as safe:
    the conservative decision is to block and ask a human, because continuing
    could silently overspend. No price is ever derived from tokens.
    """
    budgets = policy.get("budgets")
    budgets = budgets if isinstance(budgets, Mapping) else {}
    scope = usage.scope if usage is not None else None
    cost = usage.cost_usd if usage is not None else None
    cost_kind = usage.cost_kind if usage is not None else "unknown"
    limit: float | None = None
    if scope is not None and isinstance(budgets.get(scope), Mapping):
        raw_limit = budgets[scope].get("max_cost_usd")  # type: ignore[index]
        if raw_limit is not None:
            limit = float(raw_limit)
    if scope is None:
        configured_limits = [
            float(entry["max_cost_usd"])
            for entry in budgets.values()
            if isinstance(entry, Mapping) and entry.get("max_cost_usd") is not None
        ]
        if configured_limits:
            return BudgetDecision(
                "unknown",
                None,
                None,
                cost,
                cost_kind,
                "a cost budget is configured but usage.scope is missing",
            )
    if limit is None:
        return BudgetDecision("ok", scope, None, cost, cost_kind, None)
    if cost_kind == "unknown" or cost is None:
        return BudgetDecision(
            "unknown",
            scope,
            limit,
            None,
            "unknown",
            f"{scope} cost budget is configured but accumulated cost is unknown",
        )
    if cost >= limit:
        return BudgetDecision(
            "exhausted", scope, limit, cost, cost_kind, f"{scope} cost budget exhausted"
        )
    return BudgetDecision("ok", scope, limit, cost, cost_kind, None)


def validate_review_result(result: Any) -> list[str]:
    """Validate a structured review result, returning deterministic errors."""
    errors: list[str] = []
    if not isinstance(result, Mapping):
        return ["review result must be a mapping."]
    outcome = result.get("result")
    if outcome not in REVIEW_RESULTS:
        errors.append(f"review result 'result' must be one of: {', '.join(REVIEW_RESULTS)}.")
        outcome = None
    findings = result.get("findings")
    if not isinstance(findings, list):
        errors.append("review result 'findings' must be a list.")
        return errors
    if outcome == "clean" and findings:
        errors.append("review result 'clean' must have no findings.")
    if outcome == "changes_requested" and not findings:
        errors.append("review result 'changes_requested' must include at least one finding.")
    for index, finding in enumerate(findings):
        prefix = f"review result findings[{index}]"
        if not isinstance(finding, Mapping):
            errors.append(f"{prefix} must be a mapping.")
            continue
        if finding.get("severity") not in FINDING_SEVERITIES:
            errors.append(f"{prefix}.severity must be one of: {', '.join(FINDING_SEVERITIES)}.")
        if finding.get("category") not in FINDING_CATEGORIES:
            errors.append(f"{prefix}.category must be one of: {', '.join(FINDING_CATEGORIES)}.")
        for key in ["location", "problem", "expected"]:
            value = finding.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.{key} must be a non-empty string.")
    return errors


def review_next_action(result: Any) -> ReviewNextAction:
    """Map a structured review result to a deterministic next action.

    This is a pure helper: it names the role a future orchestrator (#25) would
    invoke but never invokes anything itself. Review is a distinct role and can
    never mark implementation as reviewed; a code-writing follow-up always routes
    to ``fixer`` (implementation findings) or ``planner`` (architecture findings),
    and an external blocker routes to a human.
    """
    errors = validate_review_result(result)
    if errors:
        raise ExecutionPolicyError("; ".join(errors))
    findings = list(result.get("findings") or [])
    blocking = [finding for finding in findings if finding.get("severity") == "blocking"]
    if not blocking:
        return ReviewNextAction("complete", None, "no blocking findings")
    categories = {str(finding.get("category")) for finding in blocking}
    if "external" in categories:
        return ReviewNextAction("human", None, "external blocker requires a human decision")
    if "architecture" in categories:
        return ReviewNextAction(
            "plan", "planner", "architecture finding requires planner re-evaluation"
        )
    return ReviewNextAction("fix", "fixer", "implementation finding requires the fixer role")


def build_invocation_record(
    decision: ExecutionDecision,
    *,
    task: str | None = None,
    result: str | None = None,
    usage: Mapping[str, Any] | UsageRecord | None = None,
) -> InvocationRecord:
    """Build the structured runtime invocation record a consumer can persist later.

    T-035 stops at producing the record. It never writes it to a file, database,
    or event log; that is future orchestration work.
    """
    record = _validated_usage(usage)
    return InvocationRecord(
        role=decision.role,
        profile=decision.profile,
        harness=decision.harness,
        model=decision.model,
        reasoning_effort=decision.reasoning_effort,
        task=task,
        attempt=decision.attempt,
        reason=decision.reason,
        result=result,
        escalation=decision.escalated,
        budget=decision.budget,
        usage=record,
    )
