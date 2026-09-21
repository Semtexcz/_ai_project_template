"""Project governance CLI for managed projects.

Invocation is unchanged: ``python tools/project.py <command>``. This module is
the composition boundary only - the parser, dispatch, top-level error handling,
and the compatibility exports that existing importlib consumers rely on.
Governance behavior and its ownership map live in the ``project_tool`` package
(see ``project_tool/__init__.py``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Both supported loading modes need ``project_tool`` importable from this
# folder: direct script execution (``python tools/project.py``) and
# file-location loading by the generated agent tool. Make the tools directory
# explicit and idempotent instead of relying on the current working directory.
_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from project_tool.commands import (  # noqa: E402
    approve,
    controlled_transition,
    pr_validate,
    status,
    validate,
    validate_docs_command,
)
from project_tool.docs import validate_docs  # noqa: E402
from project_tool.git import github_merge_completes, task_merge_completed  # noqa: E402
from project_tool.lifecycle import (  # noqa: E402
    definition_of_done,
    definition_of_ready,
    dependencies_done,
    effective_status,
)
from project_tool.model import ProjectError, find_active, nonempty, task_by_id  # noqa: E402
from project_tool.mutations import sync  # noqa: E402
from project_tool.rendering import recommended_next_action  # noqa: E402
from project_tool.storage import (  # noqa: E402
    load_tasks,
    parse_simple_yaml,
    read_state,
    write_state,
)
from project_tool.validation import validate_all, validate_candidate  # noqa: E402

# Compatibility surface for importlib consumers that load this file by path:
# ``tools/agent.py`` and the maintainer release tool. Each name is the canonical
# implementation from its owning module, never a second implementation.
__all__ = [
    "approve",
    "controlled_transition",
    "definition_of_done",
    "definition_of_ready",
    "dependencies_done",
    "effective_status",
    "find_active",
    "github_merge_completes",
    "load_tasks",
    "nonempty",
    "parse_simple_yaml",
    "pr_validate",
    "read_state",
    "recommended_next_action",
    "status",
    "sync",
    "task_by_id",
    "task_merge_completed",
    "validate",
    "validate_all",
    "validate_candidate",
    "validate_docs",
    "validate_docs_command",
    "write_state",
]

TRANSITION_COMMANDS = ["ready", "start", "review", "complete", "unblock", "cancel"]


def build_parser() -> argparse.ArgumentParser:
    """Build the public command-line parser."""
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("sync")
    sub.add_parser("validate")
    sub.add_parser("validate-docs")
    sub.add_parser("pr-validate")
    for name in TRANSITION_COMMANDS:
        command = sub.add_parser(name)
        command.add_argument("task")
    block = sub.add_parser("block")
    block.add_argument("task")
    block.add_argument("--reason", required=True)
    block.add_argument("--unblock", required=True)
    approve_cmd = sub.add_parser("approve")
    approve_cmd.add_argument("task")
    approve_cmd.add_argument("--approved-by", required=True)
    return parser


def dispatch(args: argparse.Namespace) -> None:
    """Run the command selected by the parser."""
    if args.command == "status":
        status()
    elif args.command == "sync":
        sync()
    elif args.command == "validate":
        validate()
    elif args.command == "validate-docs":
        validate_docs_command()
    elif args.command == "pr-validate":
        pr_validate()
    elif args.command == "ready":
        controlled_transition(args.task, "ready")
    elif args.command == "start":
        controlled_transition(args.task, "in-progress")
    elif args.command == "review":
        controlled_transition(args.task, "review")
    elif args.command == "complete":
        controlled_transition(args.task, "done")
    elif args.command == "unblock":
        controlled_transition(args.task, "ready")
    elif args.command == "cancel":
        controlled_transition(args.task, "cancelled")
    elif args.command == "block":
        controlled_transition(args.task, "blocked", reason=args.reason, unblock=args.unblock)
    elif args.command == "approve":
        approve(args.task, args.approved_by)


def main() -> None:
    """Run the CLI with governance errors reported as deterministic errors."""
    args = build_parser().parse_args()
    try:
        dispatch(args)
    except ProjectError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
