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
