"""Focused tests for the canonical agent-layer mirror tool.

The template repository dogfoods its own agent layer: canonical skills,
schemas, and Codex adapters live under ``.agents/`` and ``.codex/`` and are
mirrored into ``template/.agents/`` and ``template/.codex/`` by
``tools/agent_layer.py``. These tests prove the propagation is deterministic,
idempotent, and that the intentional divergences (``.agents/README.md`` and
``.agents/context-map.yaml`` vs their ``template/.agents/`` counterparts) are
never overwritten.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "agent_layer.py"


def run_tool(root: Path, command: str = "check") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TOOL), command, "--root", str(root)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def make_layout(root: Path) -> None:
    """Create a minimal canonical root + template mirror fixture."""
    canonical_agents = root / ".agents"
    (canonical_agents / "skills" / "demo").mkdir(parents=True)
    (canonical_agents / "README.md").write_text("root agent README", encoding="utf-8")
    (canonical_agents / "context-map.yaml").write_text("root context map", encoding="utf-8")
    (canonical_agents / "skills" / "demo" / "SKILL.md").write_text(
        "canonical skill v1", encoding="utf-8"
    )
    canonical_codex = root / ".codex"
    canonical_codex.mkdir()
    (canonical_codex / "config.toml").write_text("codex config", encoding="utf-8")

    mirrored_agents = root / "template" / ".agents"
    (mirrored_agents / "skills" / "demo").mkdir(parents=True)
    # Intentional divergences: template representations differ on purpose.
    (mirrored_agents / "README.md").write_text("generated agent README", encoding="utf-8")
    (mirrored_agents / "context-map.yaml").write_text(
        "generated context map", encoding="utf-8"
    )
    (mirrored_agents / "skills" / "demo" / "SKILL.md").write_text(
        "canonical skill v1", encoding="utf-8"
    )
    mirrored_codex = root / "template" / ".codex"
    mirrored_codex.mkdir(parents=True)
    (mirrored_codex / "config.toml").write_text("codex config", encoding="utf-8")


def test_real_repository_mirrors_are_in_sync() -> None:
    result = run_tool(ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "in sync" in result.stdout


def test_check_passes_and_sync_preserves_intentional_divergences(tmp_path: Path) -> None:
    make_layout(tmp_path)
    assert run_tool(tmp_path).returncode == 0
    sync = run_tool(tmp_path, "sync")
    assert sync.returncode == 0, sync.stdout + sync.stderr
    # The intentional template divergences must survive a sync untouched.
    assert (tmp_path / "template" / ".agents" / "README.md").read_text() == (
        "generated agent README"
    )
    assert (tmp_path / "template" / ".agents" / "context-map.yaml").read_text() == (
        "generated context map"
    )
    # Mirrored files must match their canonical counterparts.
    assert (tmp_path / "template" / ".agents" / "skills" / "demo" / "SKILL.md").read_text() == (
        "canonical skill v1"
    )
    assert (tmp_path / "template" / ".codex" / "config.toml").read_text() == "codex config"


def test_check_detects_mirror_drift_and_sync_propagates_idempotently(tmp_path: Path) -> None:
    make_layout(tmp_path)
    # Drift: edit the mirror by hand instead of the canonical file.
    mirror = tmp_path / "template" / ".agents" / "skills" / "demo" / "SKILL.md"
    mirror.write_text("hand-edited mirror", encoding="utf-8")
    drifted = run_tool(tmp_path)
    assert drifted.returncode != 0
    assert "SKILL.md" in drifted.stdout

    # Sync restores the canonical content; a second sync changes nothing.
    assert run_tool(tmp_path, "sync").returncode == 0
    assert mirror.read_text(encoding="utf-8") == "canonical skill v1"
    snapshot = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    assert run_tool(tmp_path, "sync").returncode == 0
    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    assert after == snapshot


def test_sync_propagates_canonical_edits_to_the_mirror(tmp_path: Path) -> None:
    make_layout(tmp_path)
    canonical = tmp_path / ".agents" / "skills" / "demo" / "SKILL.md"
    canonical.write_text("canonical skill v2", encoding="utf-8")
    # check fails before propagation, passes after.
    assert run_tool(tmp_path).returncode != 0
    assert run_tool(tmp_path, "sync").returncode == 0
    assert run_tool(tmp_path).returncode == 0
    assert (tmp_path / "template" / ".agents" / "skills" / "demo" / "SKILL.md").read_text() == (
        "canonical skill v2"
    )


def test_sync_removes_stale_mirrored_files_but_keeps_template_specific_files(
    tmp_path: Path,
) -> None:
    make_layout(tmp_path)
    stale = tmp_path / "template" / ".codex" / "stale.toml"
    stale.write_text("no canonical counterpart", encoding="utf-8")
    # check flags the stale file; sync removes it while preserving divergences.
    assert run_tool(tmp_path).returncode != 0
    assert run_tool(tmp_path, "sync").returncode == 0
    assert not stale.exists()
    assert (tmp_path / "template" / ".agents" / "README.md").exists()
    assert run_tool(tmp_path).returncode == 0
