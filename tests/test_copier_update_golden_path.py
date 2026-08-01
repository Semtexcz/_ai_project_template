from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import yaml


ROOT = Path(__file__).resolve().parents[1]


def run_command(
    command: list[str],
    cwd: Path,
    env: Mapping[str, str],
    *,
    timeout: int = 300,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(command_failure(command, result))
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"Command unexpectedly passed: {' '.join(command)}")
    return result


def command_failure(command: list[str], result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        [
            f"Command failed: {' '.join(command)}",
            f"Exit code: {result.returncode}",
            "--- stdout ---",
            result.stdout,
            "--- stderr ---",
            result.stderr,
        ]
    )


def env_for(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "UV_LINK_MODE": "copy",
        "PNPM_HOME": str(tmp_path / "pnpm-home"),
        "PNPM_STORE_DIR": str(tmp_path / "pnpm-store"),
    }


def copy_workspace_to_template_repo(target: Path) -> None:
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
        ),
    )


def init_git_repo(path: Path, env: Mapping[str, str]) -> None:
    run_command(["git", "init", "-q"], path, env)
    run_command(["git", "config", "user.email", "copier-test@example.invalid"], path, env)
    run_command(["git", "config", "user.name", "Copier Update Test"], path, env)


def commit_all(path: Path, env: Mapping[str, str], message: str) -> str:
    run_command(["git", "add", "-A"], path, env)
    run_command(["git", "commit", "-q", "-m", message], path, env)
    return run_command(["git", "rev-parse", "HEAD"], path, env).stdout.strip()


def read_answers(project: Path) -> dict[str, Any]:
    data = yaml.safe_load((project / ".copier-answers.yml").read_text())
    if not isinstance(data, dict):
        raise AssertionError(".copier-answers.yml did not contain a mapping")
    return cast(dict[str, Any], data)


def copy_fullstack_project(template_repo: Path, project: Path, env: Mapping[str, str], ref: str) -> None:
    run_command(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--data",
            "project_name=Update Golden Path",
            "--data",
            "project_type=fullstack",
            "--data",
            "runtime_level=local",
            "--data",
            "include_reference_feature=false",
            "--trust",
            f"--vcs-ref={ref}",
            str(template_repo),
            str(project),
        ],
        ROOT,
        env,
        timeout=300,
    )


def customize_project(project: Path, env: Mapping[str, str]) -> dict[str, str]:
    brief = "# Brief\n\nCUSTOM-BRIEF-KEEP: project brief survives template update.\n"
    roadmap = "# Roadmap\n\nCUSTOM-ROADMAP-KEEP: project roadmap survives template update.\n"
    task = "\n".join(
        [
            "---",
            "id: T-900",
            "title: Custom Project Task",
            "status: backlog",
            "priority: 900",
            "milestone: M-01",
            "approval: A1",
            "---",
            "",
            "# T-900: Custom Project Task",
            "",
            "CUSTOM-TASK-KEEP: project task survives template update.",
            "",
        ]
    )
    code = "\n".join(
        [
            "from __future__ import annotations",
            "",
            "from dataclasses import dataclass",
            "",
            "",
            "@dataclass(frozen=True)",
            "class ProjectOwnedValue:",
            "    name: str = \"CUSTOM-CODE-KEEP\"",
            "",
        ]
    )

    (project / "project" / "brief.md").write_text(brief)
    (project / "project" / "roadmap.md").write_text(roadmap)
    (project / "project" / "tasks" / "T-900-custom-project-task.md").write_text(task)
    custom_code = project / "backend" / "src" / "app" / "modules" / "custom_feature" / "domain" / "model.py"
    custom_code.parent.mkdir(parents=True)
    custom_code.write_text(code)
    (custom_code.parent / "__init__.py").write_text("")
    (custom_code.parent.parent / "__init__.py").write_text("")
    (custom_code.parent.parent.parent / "__init__.py").write_text("")

    readme = project / "README.md"
    readme.write_text(
        readme.read_text()
        + "\n## Project Notes\n\nCUSTOM-README-KEEP: project-owned README section survives.\n"
    )
    makefile = project / "Makefile"
    makefile.write_text(makefile.read_text() + "\nPROJECT_LOCAL_NOTE := CUSTOM-MAKEFILE-KEEP\n")

    commit_all(project, env, "customize generated project")
    return {
        "brief": brief,
        "roadmap": roadmap,
        "task": task,
        "code": "CUSTOM-CODE-KEEP",
        "readme": "CUSTOM-README-KEEP",
        "makefile": "CUSTOM-MAKEFILE-KEEP",
    }


def create_template_v2(template_repo: Path, env: Mapping[str, str]) -> str:
    project_tool = template_repo / "template" / "tools" / "project.py"
    project_tool.write_text(
        project_tool.read_text().replace(
            "STATE_PATH = ROOT / \"project\" / \"state.yaml\"\n",
            "STATE_PATH = ROOT / \"project\" / \"state.yaml\"\n"
            "TEMPLATE_TOOLING_REVISION = \"v1.1.0-test\"\n",
        )
    )
    (template_repo / "template" / "tools" / "template_update_marker.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "TEMPLATE_UPDATE_MARKER = \"v1.1.0-test-new-file\"",
                "",
            ]
        )
    )
    readme_template = template_repo / "template" / "README.md.jinja"
    readme_template.write_text(
        readme_template.read_text().replace(
            "## Quick Start\n\n```bash\nmake setup\nmake check\nmake build\n```",
            "## Quick Start\n\nTemplate update marker: v1.1.0.\n\n```bash\nmake setup\nmake check\nmake build\n```",
        )
    )
    commit = commit_all(template_repo, env, "template v1.1.0")
    run_command(["git", "tag", "v1.1.0"], template_repo, env)
    return commit


def update_project(project: Path, env: Mapping[str, str], ref: str, *, expect_success: bool) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            sys.executable,
            "-m",
            "copier",
            "update",
            "--defaults",
            "--trust",
            f"--vcs-ref={ref}",
        ],
        project,
        env,
        timeout=300,
        expect_success=expect_success,
    )


def update_project_allow_result(project: Path, env: Mapping[str, str], ref: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "copier",
            "update",
            "--defaults",
            "--trust",
            f"--vcs-ref={ref}",
        ],
        cwd=project,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=300,
    )


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return cast(int, sock.getsockname()[1])


def get_text(base_url: str, path: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=2) as response:
        return response.status, response.headers.get("content-type", ""), response.read().decode()


def stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            return process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            return process.communicate(timeout=10)
    return process.communicate(timeout=1)


def assert_fullstack_runtime(project: Path, env: Mapping[str, str]) -> None:
    backend_port = free_port()
    frontend_port = free_port()
    runtime_env = {
        **env,
        "BACKEND_HOST": "127.0.0.1",
        "BACKEND_PORT": str(backend_port),
        "FRONTEND_HOST": "127.0.0.1",
        "FRONTEND_PORT": str(frontend_port),
        "NUXT_PUBLIC_API_BASE_URL": f"http://127.0.0.1:{backend_port}",
    }
    process = subprocess.Popen(
        ["make", "run"],
        cwd=project,
        env=runtime_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    deadline = time.monotonic() + 45
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate(timeout=1)
                raise AssertionError(f"runtime exited early\n{stdout}\n{stderr}")
            try:
                status, _, body = get_text(backend_url, "/api/system/info")
                front_status, front_type, _ = get_text(frontend_url, "/")
                if status == 200 and "Update Golden Path" in body and front_status == 200 and "text/html" in front_type:
                    run_command(["make", "e2e"], project, {**env, "E2E_BASE_URL": frontend_url}, timeout=180)
                    return
            except (ConnectionError, TimeoutError, urllib.error.URLError):
                time.sleep(0.25)
        stdout, stderr = stop_process(process)
        raise AssertionError(f"runtime did not become ready\n{stdout}\n{stderr}")
    finally:
        stop_process(process)


def assert_updated_project(project: Path, template_repo: Path, kept: dict[str, str]) -> None:
    assert (project / "project" / "brief.md").read_text() == kept["brief"]
    assert (project / "project" / "roadmap.md").read_text() == kept["roadmap"]
    assert (project / "project" / "tasks" / "T-900-custom-project-task.md").read_text() == kept["task"]
    assert kept["code"] in (
        project / "backend" / "src" / "app" / "modules" / "custom_feature" / "domain" / "model.py"
    ).read_text()

    assert "TEMPLATE_TOOLING_REVISION = \"v1.1.0-test\"" in (project / "tools" / "project.py").read_text()
    assert "v1.1.0-test-new-file" in (project / "tools" / "template_update_marker.py").read_text()
    assert (project / ".template-version").read_text().strip() == "v1.1.0"

    readme = (project / "README.md").read_text()
    assert "Template update marker: v1.1.0." in readme
    assert kept["readme"] in readme
    assert kept["makefile"] in (project / "Makefile").read_text()

    answers = read_answers(project)
    assert answers["_src_path"] == str(template_repo)
    assert answers["_commit"] == "v1.1.0"
    assert answers["project_name"] == "Update Golden Path"
    assert "template_version" not in answers


def test_copier_update_golden_path(tmp_path: Path) -> None:
    env = env_for(tmp_path)
    template_repo = tmp_path / "template-repo"
    project = tmp_path / "generated-project"

    copy_workspace_to_template_repo(template_repo)
    init_git_repo(template_repo, env)
    v1_commit = commit_all(template_repo, env, "template v1.0.0")
    run_command(["git", "tag", "v1.0.0"], template_repo, env)

    copy_fullstack_project(template_repo, project, env, "v1.0.0")
    assert read_answers(project)["_src_path"] == str(template_repo)
    assert read_answers(project)["_commit"] == "v1.0.0"
    assert (project / ".template-version").read_text().strip() == "v1.0.0"
    init_git_repo(project, env)
    commit_all(project, env, "generated from template v1.0.0")
    kept = customize_project(project, env)

    v2_commit = create_template_v2(template_repo, env)
    assert v1_commit != v2_commit

    update_project(project, env, "v1.1.0", expect_success=True)
    assert_updated_project(project, template_repo, kept)

    run_command(["make", "setup"], project, env, timeout=360)
    run_command(["make", "api-check"], project, env, timeout=180)
    run_command(["make", "check"], project, env, timeout=360)
    run_command(["make", "build"], project, env, timeout=360)
    assert_fullstack_runtime(project, env)


def test_copier_update_reports_merge_conflict_without_silent_loss(tmp_path: Path) -> None:
    env = env_for(tmp_path)
    template_repo = tmp_path / "template-repo"
    project = tmp_path / "generated-project"

    copy_workspace_to_template_repo(template_repo)
    init_git_repo(template_repo, env)
    commit_all(template_repo, env, "template v1.0.0")
    run_command(["git", "tag", "v1.0.0"], template_repo, env)
    copy_fullstack_project(template_repo, project, env, "v1.0.0")
    init_git_repo(project, env)
    commit_all(project, env, "generated from template v1.0.0")

    readme = project / "README.md"
    readme.write_text(
        readme.read_text().replace(
            "Update Golden Path is a newly generated project. Replace this paragraph after\n"
            "the project brief is approved so it states the product, user, and value in one\n"
            "or two sentences.",
            "CONFLICT-PROJECT-VERSION: keep this project-specific README opening.",
        )
    )
    commit_all(project, env, "conflicting project README edit")

    readme_template = template_repo / "template" / "README.md.jinja"
    readme_template.write_text(
        readme_template.read_text().replace(
            "{{ project_name }} is a newly generated project. Replace this paragraph after\n"
            "the project brief is approved so it states the product, user, and value in one\n"
            "or two sentences.",
            "CONFLICT-TEMPLATE-VERSION: template changed this README opening.",
        )
    )
    commit_all(template_repo, env, "conflicting template README edit")
    run_command(["git", "tag", "v1.1.0"], template_repo, env)

    result = update_project_allow_result(project, env, "v1.1.0")
    output = result.stdout + result.stderr
    updated_readme = readme.read_text()
    assert "CONFLICT-PROJECT-VERSION" in updated_readme
    assert (
        "<<<<<<<" in updated_readme
        or "CONFLICT-TEMPLATE-VERSION" in updated_readme
        or "conflict" in output.lower()
        or list(project.rglob("*.rej"))
    )


def test_copier_update_invalid_tag_fails_without_metadata_success(tmp_path: Path) -> None:
    env = env_for(tmp_path)
    template_repo = tmp_path / "template-repo"
    project = tmp_path / "generated-project"

    copy_workspace_to_template_repo(template_repo)
    init_git_repo(template_repo, env)
    commit_all(template_repo, env, "template v1.0.0")
    run_command(["git", "tag", "v1.0.0"], template_repo, env)
    copy_fullstack_project(template_repo, project, env, "v1.0.0")
    init_git_repo(project, env)
    commit_all(project, env, "generated from template v1.0.0")
    kept = customize_project(project, env)

    result = update_project(project, env, "v9.9.9", expect_success=False)
    output = result.stdout + result.stderr
    assert "v9.9.9" in output or "tag" in output.lower() or "ref" in output.lower()
    assert (project / "project" / "brief.md").read_text() == kept["brief"]
    assert (project / "project" / "roadmap.md").read_text() == kept["roadmap"]
    assert read_answers(project)["_commit"] == "v1.0.0"
    assert (project / ".template-version").read_text().strip() == "v1.0.0"
