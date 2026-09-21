"""Focused tests for deterministic, narrow context-map routing in the template
repository itself (root ``.agents/context-map.yaml``).

These tests exercise the real resolver against the real root configuration:
a changed path must route to the expected narrow neighborhood and its focused
checks, never silently widening to the full ``make check`` gate when a focused
route exists. Intentionally different root/template files are part of the
``tools/agent_layer.py`` mirror contract and are covered by
``tests/test_agent_layer_mirror.py``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENT_TOOL = ROOT / "template" / "tools" / "agent.py"


def load_agent_tool():
    spec = importlib.util.spec_from_file_location("agent_context_tool", AGENT_TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations via sys.modules
    spec.loader.exec_module(module)
    return module


def root_config() -> dict:
    config = yaml.safe_load((ROOT / ".agents" / "context-map.yaml").read_text(encoding="utf-8"))
    assert isinstance(config, dict)
    return config


def test_frontend_scaffold_routes_to_frontend_checks_not_the_full_gate() -> None:
    agent = load_agent_tool()
    checks = agent.recommended_checks(root_config(), ["template/frontend/pages/index.vue.jinja"])
    assert checks == ["make test-frontend"]


def test_backend_scaffold_routes_to_backend_checks() -> None:
    agent = load_agent_tool()
    checks = agent.recommended_checks(
        root_config(), ["template/backend/pyproject.toml.jinja"]
    )
    assert checks == ["make test-backend"]


def test_python_src_skeleton_routes_to_python_profile_checks() -> None:
    agent = load_agent_tool()
    checks = agent.recommended_checks(root_config(), ["template/src/example/__init__.py.jinja"])
    assert checks == ["make test-python-profiles"]


def test_canonical_agent_tool_change_routes_to_agent_neighborhood() -> None:
    agent = load_agent_tool()
    checks = agent.recommended_checks(root_config(), ["template/tools/agent.py"])
    assert checks == ["make validate-agent-skills", "make test-agent"]


def test_lifecycle_tool_change_routes_to_lifecycle_neighborhood() -> None:
    agent = load_agent_tool()
    checks = agent.recommended_checks(root_config(), ["template/tools/project.py"])
    assert checks == ["make validate-project", "make test-lifecycle"]


def test_canonical_agent_layer_change_routes_to_drift_and_skills_validation() -> None:
    agent = load_agent_tool()
    checks = agent.recommended_checks(
        root_config(), [".agents/skills/implement-change/SKILL.md"]
    )
    assert checks == ["make validate-agent-skills", "make validate-agent-layer"]


def test_template_mirror_change_routes_to_drift_validation_first() -> None:
    agent = load_agent_tool()
    checks = agent.recommended_checks(
        root_config(), ["template/.agents/skills/implement-change/SKILL.md"]
    )
    assert checks == ["make validate-agent-layer", "make validate-agent-skills"]


def test_exact_test_file_change_runs_exactly_that_file() -> None:
    agent = load_agent_tool()
    checks = agent.recommended_checks(root_config(), ["tests/test_agent_efficiency.py"])
    assert checks == ["uv run pytest tests/test_agent_efficiency.py"]


def test_checks_are_deterministic_for_the_same_change_set() -> None:
    agent = load_agent_tool()
    config = root_config()
    changes = ["template/frontend/pages/index.vue.jinja"]
    assert agent.recommended_checks(config, changes) == agent.recommended_checks(
        config, changes
    )


def test_unmatched_template_path_falls_back_to_the_canonical_gate() -> None:
    agent = load_agent_tool()
    # A root jinja scaffold file without a dedicated route keeps the
    # deterministic default so no change silently escapes validation.
    checks = agent.recommended_checks(
        root_config(), ["template/{{ _copier_conf.answers_file }}.jinja"]
    )
    assert checks == ["make check"]
