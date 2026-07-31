import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_copier_configuration_has_required_axes() -> None:
    config = yaml.safe_load((ROOT / "copier.yml").read_text())

    assert config["_subdirectory"] == "template"
    assert config["_templates_suffix"] == ".jinja"
    assert set(config["project_type"]["choices"].values()) == {
        "script",
        "library",
        "backend",
        "frontend",
        "fullstack",
    }
    assert set(config["runtime_level"]["choices"].values()) == {
        "local",
        "shared",
        "production",
    }


def test_generated_project_has_single_state_source_and_dashboard_tools() -> None:
    required = [
        "template/project/state.yaml.jinja",
        "template/tools/project.py",
        "template/README.md.jinja",
        "template/project/index.md.jinja",
        "template/project/board.md.jinja",
        "template/AGENTS.md.jinja",
        "template/.agents/context-map.yaml",
        "template/.codex/config.toml",
    ]

    for relative in required:
        assert (ROOT / relative).exists(), relative


def test_reference_fullstack_feature_exists() -> None:
    required = [
        "template/examples/reference-fullstack/backend/src/app/modules/todos/domain/model.py",
        "template/examples/reference-fullstack/backend/src/app/modules/todos/application/use_cases.py",
        "template/examples/reference-fullstack/backend/src/app/modules/todos/infrastructure/repository.py",
        "template/examples/reference-fullstack/backend/src/app/modules/todos/api/routes.py",
        "template/examples/reference-fullstack/frontend/pages/todos.vue",
        "template/examples/reference-fullstack/frontend/features/todos/composables/useTodos.ts",
    ]

    for relative in required:
        assert (ROOT / relative).exists(), relative


def git_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_release_hygiene_rejects_committed_artifacts_and_local_paths() -> None:
    forbidden_parts = [
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".venv/",
        "node_modules/",
        "/dist/",
        "/build/",
        "/.output/",
        "playwright-report/",
        "test-results/",
        "frontend/shared/api/generated/",
    ]
    forbidden_suffixes = (
        ".pyc",
        ".pyo",
        ".egg-info",
        ".log",
        ".DS_Store",
    )
    offenders = []
    for path in git_files():
        normalized = path.replace("\\", "/")
        if normalized.endswith(forbidden_suffixes) or any(part in normalized for part in forbidden_parts):
            offenders.append(path)
    assert offenders == []

    local_path_markers = [
        "/" + "mnt" + "/" + "Data" + "/",
        "/" + "home" + "/" + "semtex" + "/",
        "C:\\Users\\",
    ]
    text_offenders = []
    for path in git_files():
        file_path = ROOT / path
        if not file_path.exists() or file_path.stat().st_size > 500_000:
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(marker in content for marker in local_path_markers):
            text_offenders.append(path)
    assert text_offenders == []


def test_release_hygiene_gitignore_and_gate_are_declared() -> None:
    root_gitignore = (ROOT / ".gitignore").read_text()
    template_gitignore = (ROOT / "template" / ".gitignore.jinja").read_text()
    for ignore in [root_gitignore, template_gitignore]:
        assert "__pycache__/" in ignore
        assert "*.py[cod]" in ignore
        assert ".pytest_cache/" in ignore
        assert "node_modules/" in ignore
        assert ".output/" in ignore
        assert "dist/" in ignore

    makefile = (ROOT / "Makefile").read_text()
    assert "release-check:" in makefile
    release_target = makefile.split("release-check:", 1)[1].split("\n\n", 1)[0]
    assert "uv run pytest" in release_target
    assert "|| true" not in release_target

    readme = (ROOT / "README.md").read_text()
    assert "make check` intentionally runs a narrow maintainer subset" in readme
    assert "`make release-check` runs the complete release-candidate pytest suite" in readme


def test_rendered_projects_do_not_include_cache_artifacts(tmp_path: Path) -> None:
    profiles = [
        ("script", "local"),
        ("library", "shared"),
        ("backend", "shared"),
        ("frontend", "shared"),
        ("fullstack", "local"),
        ("fullstack", "production"),
    ]
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
    }
    for project_type, runtime_level in profiles:
        generated = tmp_path / f"{project_type}-{runtime_level}"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "copier",
                "copy",
                "--defaults",
                "--skip-tasks",
                "--data",
                f"project_name={project_type}-{runtime_level}",
                "--data",
                f"project_type={project_type}",
                "--data",
                f"runtime_level={runtime_level}",
                "--data",
                "include_reference_feature=false",
                "--trust",
                "--vcs-ref=HEAD",
                str(ROOT),
                str(generated),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        offenders = [
            path
            for path in generated.rglob("*")
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}
        ]
        assert offenders == []
