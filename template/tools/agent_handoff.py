"""Deterministic, runtime-only agent handoff for one managed task.

One managed task keeps one branch, one worktree, one claim, and one pull
request; a conversation does not survive. This module owns the *handoff model* -
the structured :class:`AgentHandoff` value, its machine-readable mapping, and its
concise human rendering.

Derivation deliberately stays in ``agent.py``, which already owns the canonical
task, Git, worktree, claim, branch-aware changed-file, and check-routing APIs.
This module therefore never re-implements a second change detector, a second
context router, or a second task loader; it only shapes and renders what the
canonical seams already resolved.

The handoff is derived, runtime-only, deterministic, bounded, and
machine-readable. It is never persisted, so it is not session state, not a
transcript, not a reasoning summary, and not a second task record:

* No timestamps. Every field comes from task, Git, or claim state, so two
  handoffs of the same repository state are byte-identical.
* No file contents. Changed files stay ``(source, path)`` entries whose source
  is the existing branch/staged/worktree/untracked classification.
* No logs and no command history. Verification is represented by the checks that
  *should* run next, resolved by the existing context routing.
* A hard byte budget with deterministic compaction, so even a very large branch
  still produces a small handoff.
* Rendering is separate from derivation: :func:`render_text` and
  :func:`render_json` only format a value that was derived elsewhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

HANDOFF_SCHEMA_VERSION = 1

# Normal handoff payload target, in bytes. Human and JSON output both stay under
# this, and a handoff that exceeds it fails loudly instead of silently growing.
HANDOFF_BYTE_BUDGET = 8192

# Deterministic compaction limits. They keep the handoff bounded on a huge
# branch without embedding diffs, so a large template-authoring task still
# produces a small payload. The listed change count is capped because a handoff
# is a resume aid, not a diff: the true total is still reported.
HANDOFF_MAX_CHANGED_FILES = 40
HANDOFF_MAX_COMMITS = 5
HANDOFF_MAX_REMAINING_CRITERIA = 20


class HandoffError(Exception):
    """A handoff that cannot be represented within its deterministic contract."""


@dataclass(frozen=True)
class HandoffDependency:
    """One declared task dependency and whether it currently blocks work."""

    task_id: str
    status: str
    blocking: bool


@dataclass(frozen=True)
class HandoffWorktree:
    """Git and ownership identity of the worktree that owns the task."""

    branch: str | None
    head_sha: str | None
    path: str
    control_checkout: bool
    registered: bool
    exists: bool
    claimed: bool
    claim_task_id: str | None
    dirty: bool
    merged: bool
    unique_commits: int
    ownership_consistent: bool
    errors: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class HandoffChangedFile:
    """One changed path with the canonical change source that reported it."""

    source: str
    path: str


@dataclass(frozen=True)
class HandoffCommit:
    """One recent commit on the task branch. Subject only, never the diff."""

    sha: str
    subject: str


@dataclass(frozen=True)
class AgentHandoff:
    """The durable, reconstructible state of one managed task.

    Every field is derived from repository state by the caller. Fields that would
    be nondeterministic (timestamps, process ids, conversation content) are
    intentionally absent.
    """

    task_id: str
    title: str
    status: str
    effective_status: str
    milestone: str
    priority: int
    approval_level: str
    approval_status: str
    blocked: bool
    blocked_reason: str | None
    unblock_action: str | None
    dependencies: tuple[HandoffDependency, ...]
    worktree: HandoffWorktree
    changed_files: tuple[HandoffChangedFile, ...]
    changed_files_omitted: int
    deleted_files: tuple[str, ...]
    recent_commits: tuple[HandoffCommit, ...]
    remaining_acceptance_criteria: tuple[str, ...]
    remaining_criteria_omitted: int
    next_action: str
    recommended_checks: tuple[str, ...]
    resume_from_worktree: str
    resume_commands: tuple[str, ...]
    stop_conditions: tuple[str, ...]

    def body(self) -> dict[str, Any]:
        """Return the deterministic payload without the metrics block.

        The metrics block is attached afterwards by :meth:`to_payload`, so
        ``metrics.handoff_bytes`` can measure this body exactly instead of
        depending on its own size.
        """
        return {
            "schema_version": HANDOFF_SCHEMA_VERSION,
            "task": {
                "id": self.task_id,
                "title": self.title,
                "status": self.status,
                "effective_status": self.effective_status,
                "milestone": self.milestone,
                "priority": self.priority,
                "approval_level": self.approval_level,
                "approval_status": self.approval_status,
                "blocked": self.blocked,
                "blocked_reason": self.blocked_reason,
                "unblock_action": self.unblock_action,
                "dependencies": [
                    {
                        "id": dependency.task_id,
                        "status": dependency.status,
                        "blocking": dependency.blocking,
                    }
                    for dependency in self.dependencies
                ],
            },
            "worktree": {
                "branch": self.worktree.branch,
                "head_sha": self.worktree.head_sha,
                "path": self.worktree.path,
                "control_checkout": self.worktree.control_checkout,
                "registered": self.worktree.registered,
                "exists": self.worktree.exists,
                "claimed": self.worktree.claimed,
                "claim_task_id": self.worktree.claim_task_id,
                "dirty": self.worktree.dirty,
                "merged": self.worktree.merged,
                "unique_commits": self.worktree.unique_commits,
                "ownership_consistent": self.worktree.ownership_consistent,
                "errors": list(self.worktree.errors),
                "notes": list(self.worktree.notes),
            },
            "changes": {
                "count": len(self.changed_files) + self.changed_files_omitted,
                "listed": len(self.changed_files),
                "omitted": self.changed_files_omitted,
                "files": [
                    {"source": item.source, "path": item.path} for item in self.changed_files
                ],
                "deleted": list(self.deleted_files),
            },
            "recent_commits": [
                {"sha": commit.sha, "subject": commit.subject} for commit in self.recent_commits
            ],
            "remaining_acceptance_criteria": list(self.remaining_acceptance_criteria),
            "remaining_criteria_omitted": self.remaining_criteria_omitted,
            "next_action": self.next_action,
            "recommended_checks": list(self.recommended_checks),
            "resume": {
                "from_worktree": self.resume_from_worktree,
                "commands": list(self.resume_commands),
            },
            "stop_conditions": list(self.stop_conditions),
        }

    def to_payload(self) -> dict[str, Any]:
        """Return the machine-readable payload including deterministic metrics."""
        payload = self.body()
        payload["metrics"] = {
            "changed_files_count": len(self.changed_files) + self.changed_files_omitted,
            "recommended_checks_count": len(self.recommended_checks),
            # Byte size of the payload without this metrics block, so the value
            # never depends on its own digit count.
            "handoff_bytes": payload_bytes(payload),
        }
        return payload


def canonical_json(data: Any) -> str:
    """Return the compact canonical JSON encoding used for size accounting."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_bytes(payload: dict[str, Any]) -> int:
    """Return the deterministic byte size of one payload."""
    return len(canonical_json(payload).encode("utf-8"))


def rendered_bytes(handoff: AgentHandoff) -> int:
    """Return the byte size of the machine-readable handoff output."""
    return len(render_json(handoff).encode("utf-8"))


def enforce_budget(handoff: AgentHandoff) -> int:
    """Return the handoff size, failing loudly above the deterministic budget."""
    size = rendered_bytes(handoff)
    if size > HANDOFF_BYTE_BUDGET:
        raise HandoffError(
            f"Handoff payload is {size} bytes, above the {HANDOFF_BYTE_BUDGET}-byte "
            "budget. Reduce the branch scope or the handoff compaction limits."
        )
    return size


def render_json(handoff: AgentHandoff) -> str:
    """Render the machine-readable handoff used by ``FORMAT=json``."""
    return json.dumps(handoff.to_payload(), indent=2, sort_keys=True, ensure_ascii=False)


def render_text(handoff: AgentHandoff) -> str:
    """Render the concise human handoff.

    The human view stays short on purpose: it is a resume aid, not a report. The
    machine-readable output remains the canonical interface.
    """
    metrics = handoff.to_payload()["metrics"]
    worktree = handoff.worktree
    lines = [
        f"Task {handoff.task_id}: {handoff.title}",
        f"Status: {handoff.status} (effective {handoff.effective_status})"
        + (" [blocked]" if handoff.blocked else ""),
        f"Milestone: {handoff.milestone} | Approval: {handoff.approval_level} "
        f"{handoff.approval_status}",
    ]
    if handoff.dependencies:
        lines.append(
            "Dependencies: "
            + ", ".join(
                f"{dependency.task_id}={dependency.status}"
                + (" (blocking)" if dependency.blocking else "")
                for dependency in handoff.dependencies
            )
        )
    lines.append(f"Branch: {worktree.branch or '(none)'} @ {worktree.head_sha or '(unknown)'}")
    lines.append(
        f"Worktree: {worktree.path} | claim: {'yes' if worktree.claimed else 'none'} | "
        f"{'dirty' if worktree.dirty else 'clean'}"
    )
    for error in worktree.errors:
        lines.append(f"ERROR: {error}")
    for note in worktree.notes:
        lines.append(f"Note: {note}")
    if handoff.changed_files:
        lines.append(f"Changed files: {metrics['changed_files_count']}")
        for item in handoff.changed_files:
            lines.append(f"- ({item.source}) {item.path}")
        if handoff.changed_files_omitted:
            lines.append(f"- (+{handoff.changed_files_omitted} more, compacted)")
    else:
        lines.append("Changed files: 0")
    if handoff.recent_commits:
        lines.append("Recent commits:")
        for commit in handoff.recent_commits:
            lines.append(f"- {commit.sha[:12]} {commit.subject}")
    if handoff.remaining_acceptance_criteria:
        lines.append("Remaining acceptance criteria:")
        for criterion in handoff.remaining_acceptance_criteria:
            lines.append(f"- [ ] {criterion}")
        if handoff.remaining_criteria_omitted:
            lines.append(f"- (+{handoff.remaining_criteria_omitted} more)")
    lines.append(f"Next action: {handoff.next_action}")
    lines.append("Recommended checks:")
    for command in handoff.recommended_checks:
        lines.append(f"- {command}")
    lines.append(f"Resume: {handoff.resume_from_worktree}")
    for command in handoff.resume_commands:
        lines.append(f"  {command}")
    lines.append(
        f"Handoff bytes: {metrics['handoff_bytes']} (<= {HANDOFF_BYTE_BUDGET}) | "
        f"changed files: {metrics['changed_files_count']} | "
        f"checks: {metrics['recommended_checks_count']}"
    )
    return "\n".join(lines)
