"""Explicit filesystem mutation boundary for governance control files.

Everything here writes files, and every multi-file mutation is atomic: candidate
content is validated first, written through temporary files, then validated
again after the swap, with a full rollback when anything fails. Derivation,
policy, and rendering stay in the modules below this one.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from project_tool.model import ROOT, ProjectError, relative
from project_tool.rendering import (
    persisted_board_block,
    persisted_status_block,
    print_errors,
    project_index_block,
)
from project_tool.storage import (
    INDEX_END,
    INDEX_START,
    KANBAN_END,
    KANBAN_START,
    STATE_END,
    STATE_START,
    dump_task_text,
    load_tasks_with_overrides,
    normalize_task_data,
    read_state,
    replace_block_text,
    split_frontmatter,
    task_path,
    write_if_changed,
)
from project_tool.validation import validate_all, validate_candidate


def assert_no_tmp_files(paths: list[Path]) -> None:
    """Fail loudly when a transactional mutation leaves temporary files."""
    leftovers: list[Path] = []
    for path in paths:
        leftovers.extend(path.parent.glob(path.name + ".tmp-*"))
    if leftovers:
        raise ProjectError(
            "Temporary mutation files remain: "
            + ", ".join(relative(path) for path in sorted(leftovers))
        )


def commit_files_atomically(files: dict[Path, str]) -> None:
    """Write several files as one transaction with rollback on failure."""
    paths = list(files)
    snapshots = {path: path.read_bytes() if path.exists() else None for path in paths}
    tmp_paths: list[Path] = []
    try:
        for path, content in files.items():
            tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
            tmp.write_text(content, encoding="utf-8")
            tmp_paths.append(tmp)
        if os.environ.get("PROJECT_TOOL_FAIL_WRITE") == "1":
            raise ProjectError("Injected write failure.")
        for tmp, path in zip(tmp_paths, paths, strict=True):
            tmp.replace(path)
        if os.environ.get("PROJECT_TOOL_FAIL_FINAL_VALIDATE") == "1":
            raise ProjectError("Injected final validation failure.")
        errors = validate_all(check_drift=True)
        if errors:
            raise ProjectError("\n".join(errors))
    except Exception:
        for path, content in snapshots.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        for tmp in tmp_paths:
            tmp.unlink(missing_ok=True)
        assert_no_tmp_files(paths)
        raise
    assert_no_tmp_files(paths)


def rendered_dashboard_texts(state: dict[str, Any]) -> dict[Path, str]:
    """Committed Markdown blocks: project-global content only.

    These blocks are functions of ``project/state.yaml`` alone, so a task
    transition never rewrites a shared committed file.
    """
    if os.environ.get("PROJECT_TOOL_FAIL_RENDER") == "1":
        raise ProjectError("Injected dashboard rendering failure.")
    replacements = {
        ROOT / "README.md": (STATE_START, STATE_END, persisted_status_block(state)),
        ROOT / "project" / "index.md": (
            INDEX_START,
            INDEX_END,
            project_index_block(state),
        ),
        ROOT / "project" / "board.md": (
            KANBAN_START,
            KANBAN_END,
            persisted_board_block(state),
        ),
    }
    rendered: dict[Path, str] = {}
    for path, (start, end, content) in replacements.items():
        rendered[path] = replace_block_text(
            path.read_text(encoding="utf-8"), start, end, content, path
        )
    return rendered


def sync() -> None:
    """Refresh committed Markdown with project-global content only.

    Committed blocks hold no task status in any workflow mode, so a task
    transition - and a merge-derived completion - never requires a
    synchronization commit.
    """
    state = read_state()
    errors = validate_all(check_drift=False)
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    for path, updated in rendered_dashboard_texts(state).items():
        write_if_changed(path, updated)
    print("Project docs synchronized.")


def transactional_task_mutation(
    task_id: str,
    task_updates: dict[str, Any],
) -> None:
    """Apply task updates atomically.

    Only the task record changes. Project-global state and the committed
    dashboards depend on task state in no way, so a transition never rewrites a
    shared file and cannot conflict with a parallel branch.
    """
    path = task_path(task_id)
    data, body = split_frontmatter(path)
    data.update(task_updates)
    task_text = dump_task_text(data, body)
    task_overrides = {path: task_text}
    candidate_tasks = load_tasks_with_overrides(task_overrides)
    if os.environ.get("PROJECT_TOOL_FAIL_VALIDATION") == "1":
        candidate_tasks = [
            task
            if task.id != task_id
            else normalize_task_data(
                {**data, "status": "__invalid_candidate_status__"},
                path,
                body,
            )
            for task in candidate_tasks
        ]
    state = read_state()
    errors = validate_candidate(state, candidate_tasks)
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    try:
        commit_files_atomically({path: task_text})
    except ProjectError as exc:
        print_errors([str(exc)])
        raise SystemExit(1) from exc
