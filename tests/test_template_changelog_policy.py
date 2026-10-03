from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_docs_tool() -> Any:
    spec = importlib.util.spec_from_file_location(
        "template_docs_tool",
        ROOT / "tools" / "template_docs.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load template documentation tool module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules["template_docs_tool"] = module
    spec.loader.exec_module(module)
    return module


def valid_changelog_text(newest: str = "v1.2.1") -> str:
    return (
        "# Changelog\n\n"
        f"## {newest} - 2026-10-04\n\n"
        "- Added the newest change.\n\n"
        "## v1.2.0 - 2026-10-03\n\n"
        "- Added the previous change.\n\n"
        "## v0.1.0 - 2026-07-31\n\n"
        "- Initial release.\n"
    )


def test_changelog_accepts_current_version() -> None:
    docs = load_docs_tool()
    errors = docs.validate_changelog_text(valid_changelog_text("v1.2.1"), "v1.2.1")
    assert errors == []


def test_changelog_accepts_one_pending_bump() -> None:
    docs = load_docs_tool()
    for newest in ["v1.2.1", "v1.3.0", "v2.0.0"]:
        errors = docs.validate_changelog_text(valid_changelog_text(newest), "v1.2.0")
        assert errors == [], errors


def test_changelog_rejects_unreleased_section() -> None:
    docs = load_docs_tool()
    text = "# Changelog\n\n## Unreleased\n\n- Work in progress.\n\n" + valid_changelog_text()
    errors = docs.validate_changelog_text(text, "v1.2.1")
    assert any("Unreleased" in error for error in errors)


def test_changelog_rejects_malformed_release_heading() -> None:
    docs = load_docs_tool()
    text = "# Changelog\n\n## v1.2.1\n\n- Missing the date.\n"
    errors = docs.validate_changelog_text(text, "v1.2.1")
    assert any("released version heading" in error for error in errors)


def test_changelog_requires_the_changelog_heading() -> None:
    docs = load_docs_tool()
    text = valid_changelog_text().replace("# Changelog", "# Notes", 1)
    errors = docs.validate_changelog_text(text, "v1.2.1")
    assert any("must start with" in error for error in errors)


def test_changelog_rejects_non_descending_releases() -> None:
    docs = load_docs_tool()
    text = (
        "# Changelog\n\n"
        "## v1.1.0 - 2026-10-04\n\n"
        "- Older.\n\n"
        "## v1.2.0 - 2026-10-03\n\n"
        "- Newer.\n"
    )
    errors = docs.validate_changelog_text(text, "v1.1.0")
    assert any("descending order" in error for error in errors)


def test_changelog_rejects_empty_newest_section() -> None:
    docs = load_docs_tool()
    text = (
        "# Changelog\n\n"
        "## v1.2.1 - 2026-10-04\n\n"
        "## v1.2.0 - 2026-10-03\n\n"
        "- Older entry.\n"
    )
    errors = docs.validate_changelog_text(text, "v1.2.1")
    assert any("at least one entry" in error for error in errors)


def test_changelog_rejects_out_of_range_newest_version() -> None:
    docs = load_docs_tool()
    errors = docs.validate_changelog_text(valid_changelog_text("v9.9.9"), "v1.2.0")
    assert any("must match the current template version" in error for error in errors)


def test_changelog_requires_a_release_section() -> None:
    docs = load_docs_tool()
    errors = docs.validate_changelog_text("# Changelog\n\nNothing here.\n", "v1.2.0")
    assert any("at least one" in error for error in errors)


def test_repository_changelog_satisfies_the_policy() -> None:
    docs = load_docs_tool()
    assert docs.validate_changelog() == []


def test_root_agents_requires_a_release_per_change() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Every template change is a release" in agents
    assert "`CHANGELOG.md` must never contain an `Unreleased` section." in agents
    assert "make template-release-prepare" in agents
    assert "make validate-template-docs" in agents


def test_template_development_documents_the_version_changelog_policy() -> None:
    development = (ROOT / "docs" / "template-development.md").read_text(encoding="utf-8")
    assert "## Version And Changelog Policy" in development
    assert "no `Unreleased`" in development


# --- Strict release-ready boundary -------------------------------------------
#
# Ordinary validation may accept one pending SemVer bump so release preparation
# can run before the version commit exists. The strict release-ready gate is the
# final PR/CI contract: the newest changelog release must equal template.version
# exactly, so a change cannot ship a newer changelog version, skip
# `make template-release-prepare`, and still pass.


def release_ready_changelog_text(newest: str = "v1.2.0") -> str:
    """A structurally valid changelog whose newest release is exactly ``newest``."""
    return (
        "# Changelog\n\n"
        f"## {newest} - 2026-10-03\n\n"
        "- Added the newest change.\n\n"
        "## v0.1.0 - 2026-07-31\n\n"
        "- Initial release.\n"
    )


def test_release_ready_accepts_exact_version_match() -> None:
    docs = load_docs_tool()
    assert docs.validate_release_ready_text(release_ready_changelog_text("v1.2.0"), "v1.2.0") == []


@pytest.mark.parametrize("newest", ["v1.2.1", "v1.3.0", "v2.0.0"])
def test_release_ready_rejects_a_pending_bump(newest: str) -> None:
    docs = load_docs_tool()
    errors = docs.validate_release_ready_text(release_ready_changelog_text(newest), "v1.2.0")
    assert any("must exactly match" in error for error in errors), errors


def test_release_ready_rejects_an_unreleased_section() -> None:
    docs = load_docs_tool()
    text = "# Changelog\n\n## Unreleased\n\n- Work in progress.\n\n" + release_ready_changelog_text()
    errors = docs.validate_release_ready_text(text, "v1.2.0")
    assert any("Unreleased" in error for error in errors)


def test_release_ready_requires_a_typeable_template_version() -> None:
    docs = load_docs_tool()
    errors = docs.validate_release_ready_text(release_ready_changelog_text(), None)
    assert any("must define template.version" in error for error in errors)


def test_release_ready_shares_the_structural_validation() -> None:
    docs = load_docs_tool()
    malformed = "# Changelog\n\n## v1.2.0\n\n- Missing the date.\n"
    assert any(
        "released version heading" in error
        for error in docs.validate_release_ready_text(malformed, "v1.2.0")
    )

    non_descending = (
        "# Changelog\n\n"
        "## v1.1.0 - 2026-10-04\n\n"
        "- Older.\n\n"
        "## v1.2.0 - 2026-10-03\n\n"
        "- Newer.\n"
    )
    assert any(
        "descending order" in error
        for error in docs.validate_release_ready_text(non_descending, "v1.2.0")
    )

    empty_newest = (
        "# Changelog\n\n"
        "## v1.2.0 - 2026-10-03\n\n"
        "## v0.1.0 - 2026-07-31\n\n"
        "- Older entry.\n"
    )
    assert any(
        "at least one entry" in error
        for error in docs.validate_release_ready_text(empty_newest, "v1.2.0")
    )


def test_repository_changelog_is_release_ready() -> None:
    docs = load_docs_tool()
    assert docs.validate_release_ready() == []
