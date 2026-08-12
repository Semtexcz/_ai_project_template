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
    assert set(config["governance"]["choices"].values()) == {"lightweight", "managed"}
    assert config["governance"]["default"] == "lightweight"
    assert set(config["workflow_mode"]["choices"].values()) == {"local", "branch", "pr"}
    assert config["workflow_mode"]["default"] == "local"


def test_generated_project_has_single_state_source_and_dashboard_tools() -> None:
    required = [
        "template/project/state.yaml.jinja",
        "template/tools/project.py",
        "template/README.md.jinja",
        "template/project/index.md.jinja",
        "template/project/board.md.jinja",
        "template/AGENTS.md.jinja",
        "template/.agents/context-map.yaml",
        "template/.agents/skills/conventional-commit/SKILL.md",
        "template/.agents/skills/conventional-commit/agents/openai.yaml",
        "template/.agents/skills/conventional-commit/agents/model.yaml",
        "template/.agents/skills/conventional-commit/scripts/validate_commit_message.py",
        "template/.codex/skills/conventional-commit/SKILL.md",
        "template/.codex/config.toml",
        "docs/template-architecture.md",
        "docs/profile-matrix.md",
        "docs/template-development.md",
        "docs/diagrams/template-flow.d2",
        "docs/diagrams/generated-project-workflow.d2",
        "docs/diagrams/runtime-profiles.d2",
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
    assert "`make check` is the fast maintainer subset" in readme
    assert "`make release-check` runs the full" in readme


def test_documentation_validation_targets_are_declared() -> None:
    makefile = (ROOT / "Makefile").read_text()
    generated_makefile = (ROOT / "template" / "Makefile.jinja").read_text()
    project_tool = (ROOT / "template" / "tools" / "project.py").read_text()

    assert "validate-template-docs:" in makefile
    assert "validate-docs:" in generated_makefile
    assert "validate-docs" in project_tool
    assert "validate_docs" in project_tool


def test_generated_frontend_commands_bootstrap_pnpm_with_corepack() -> None:
    generated_makefile = (ROOT / "template" / "Makefile.jinja").read_text()
    api_client = (ROOT / "template" / "tools" / "api_client.py").read_text()
    fullstack = (ROOT / "template" / "tools" / "fullstack.py").read_text()
    template_gitignore = (ROOT / "template" / ".gitignore.jinja").read_text()

    assert "COREPACK_HOME ?= $(abspath .corepack)" in generated_makefile
    assert "PNPM ?= corepack pnpm" in generated_makefile
    assert "FRONTEND_PNPM =" in generated_makefile
    assert ".corepack/" in template_gitignore

    generated_entrypoints = "\n".join([generated_makefile, api_client, fullstack])
    assert "pnpm --dir" not in generated_entrypoints
    assert '"pnpm"' not in generated_entrypoints
    assert '"corepack pnpm"' in generated_entrypoints


def test_agent_workflow_strictness_is_configurable() -> None:
    root_agents = (ROOT / "AGENTS.md").read_text()
    generated_agents = (ROOT / "template" / "AGENTS.md.jinja").read_text()
    root_required_instruction_parts = [
        "non-`main` branch",
        "commit the agent's own changes",
        "push the branch",
        "`origin`",
        "ready GitHub pull request",
        "Do not push directly to",
    ]
    for part in root_required_instruction_parts:
        assert part in root_agents
    for part in [
        "Workflow mode is `local`",
        "Workflow mode is `branch`",
        "Workflow mode is `pr`",
        "workflow_mode",
    ]:
        assert part in generated_agents

    root_ci = (ROOT / ".github" / "workflows" / "template-ci.yml").read_text()
    generated_ci = (ROOT / "template" / ".github" / "workflows" / "ci.yml.jinja").read_text()
    for content in [root_ci, generated_ci]:
        assert "require-pr-for-main:" in content
        assert "pull-requests: read" in content
        assert "/commits/${SHA}/pulls" in content
        assert "github.event_name == 'push' && github.ref == 'refs/heads/main'" in content
        assert "Pushes to main must come from a GitHub pull request" in content

    assert "${{ github.token }}" in root_ci
    assert "${{ '{{' }} github.token {{ '}}' }}" in generated_ci
    assert "{% if workflow_mode == \"pr\" %}" in generated_ci


def copy_project(
    tmp_path: Path,
    *,
    project_type: str = "script",
    runtime_level: str = "local",
    governance: str = "lightweight",
    workflow_mode: str = "local",
) -> Path:
    generated = tmp_path / f"{project_type}-{runtime_level}-{governance}-{workflow_mode}"
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--skip-tasks",
            "--data",
            f"project_name={generated.name}",
            "--data",
            f"project_type={project_type}",
            "--data",
            f"runtime_level={runtime_level}",
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
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return generated


def test_lightweight_generation_omits_managed_governance_machinery(tmp_path: Path) -> None:
    generated = copy_project(tmp_path)

    assert (generated / "project" / "brief.md").exists()
    assert (generated / "docs" / "decisions" / "index.md").exists()
    managed_only = [
        ".agents",
        ".codex",
        "tools/agent.py",
        "tools/project.py",
        "project/state.yaml",
        "project/tasks",
        "project/board.md",
        "project/index.md",
        "project/roadmap.md",
        "docs/lifecycle.md",
    ]
    for relative in managed_only:
        assert not (generated / relative).exists(), relative

    makefile = (generated / "Makefile").read_text()
    assert "sync-project-docs:" not in makefile
    assert "task-start:" not in makefile
    assert "validate-project:" not in makefile
    assert "check: validate-docs format-check lint typecheck test" in makefile


def test_managed_generation_preserves_task_lifecycle(tmp_path: Path) -> None:
    generated = copy_project(tmp_path, governance="managed", workflow_mode="pr")

    assert (generated / "project" / "state.yaml").exists()
    assert (generated / "project" / "tasks" / "T-001-initialize-project.md").exists()
    assert (generated / ".agents" / "context-map.yaml").exists()
    makefile = (generated / "Makefile").read_text()
    for target in [
        "sync-project-docs:",
        "validate-project:",
        "agent-context:",
        "task-start:",
        "task-approve:",
    ]:
        assert target in makefile
    assert "check: validate-docs validate-project validate-agent-skills format-check lint typecheck test" in makefile


def test_workflow_modes_render_expected_agent_policy(tmp_path: Path) -> None:
    local = copy_project(tmp_path, workflow_mode="local")
    branch = copy_project(tmp_path, workflow_mode="branch")
    pr = copy_project(tmp_path, governance="managed", workflow_mode="pr")

    assert "Workflow mode is `local`" in (local / "AGENTS.md").read_text()
    assert "Workflow mode is `branch`" in (branch / "AGENTS.md").read_text()
    assert "Workflow mode is `pr`" in (pr / "AGENTS.md").read_text()
    assert "ready pull request" in (pr / "AGENTS.md").read_text()


def test_generated_make_check_is_non_mutating_for_clean_lightweight_project(tmp_path: Path) -> None:
    generated = copy_project(tmp_path)
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
    }
    subprocess.run(["make", "setup"], cwd=generated, env=env, check=True)
    subprocess.run(["git", "init", "-q"], cwd=generated, env=env, check=True)
    subprocess.run(["git", "config", "user.email", "check@example.invalid"], cwd=generated, env=env, check=True)
    subprocess.run(["git", "config", "user.name", "Check Purity"], cwd=generated, env=env, check=True)
    subprocess.run(["git", "add", "-A"], cwd=generated, env=env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=generated, env=env, check=True)
    before = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=generated,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout

    subprocess.run(["make", "check"], cwd=generated, env=env, check=True)
    after = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=generated,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout

    assert before == ""
    assert after == ""


def test_conventional_commit_skill_uses_cheap_model_and_validator() -> None:
    root_skill = ROOT / ".agents" / "skills" / "conventional-commit" / "SKILL.md"
    root_openai = ROOT / ".agents" / "skills" / "conventional-commit" / "agents" / "openai.yaml"
    root_model = ROOT / ".agents" / "skills" / "conventional-commit" / "agents" / "model.yaml"
    root_validator = (
        ROOT / ".agents" / "skills" / "conventional-commit" / "scripts" / "validate_commit_message.py"
    )

    assert "$conventional-commit" in root_openai.read_text(encoding="utf-8")
    assert 'model: "gpt-5-mini"' in root_model.read_text(encoding="utf-8")
    assert "validate_commit_message.py" in root_skill.read_text(encoding="utf-8")

    valid = subprocess.run(
        [sys.executable, str(root_validator), "--message", "feat(agent): add deterministic validator"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert valid.returncode == 0

    invalid = subprocess.run(
        [sys.executable, str(root_validator), "--message", "Bad message"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert invalid.returncode != 0


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
