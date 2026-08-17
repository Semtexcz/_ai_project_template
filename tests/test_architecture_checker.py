from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "template" / "tools" / "architecture.py"


def write_module(path: Path, loc: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join("value = 1" for _ in range(loc)) + "\n", encoding="utf-8")


def write_config(
    root: Path,
    *,
    exclude: list[str] | None = None,
    exceptions: str = "",
) -> None:
    exclude_lines = "\n".join(f"      - {pattern}" for pattern in (exclude or []))
    text = "\n".join(
        [
            "module_design:",
            "  principle: single-responsibility",
            "",
            "  python:",
            "    target_loc: 200",
            "    soft_limit_loc: 300",
            "    hard_limit_loc: 500",
            "",
            "    exclude:",
            exclude_lines or "      []",
            "",
            "    exceptions:",
            exceptions or "      []",
            "",
        ]
    )
    (root / "quality.yaml").write_text(text, encoding="utf-8")


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_module_below_soft_limit_passes(tmp_path: Path) -> None:
    write_config(tmp_path)
    write_module(tmp_path / "src" / "feature.py", 300)

    result = run_checker(tmp_path)

    assert result.returncode == 0
    assert "OK" in result.stdout
    assert "src/feature.py" in result.stdout


def test_module_between_soft_and_hard_limit_warns_but_passes(tmp_path: Path) -> None:
    write_config(tmp_path)
    write_module(tmp_path / "src" / "feature.py", 301)

    result = run_checker(tmp_path)

    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "Architecture check: 1 modules, 1 warnings, 0 errors." in result.stdout


def test_module_above_hard_limit_fails(tmp_path: Path) -> None:
    write_config(tmp_path)
    write_module(tmp_path / "src" / "feature.py", 501)

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "Hard limit exceeded" in result.stderr


def test_configured_exclusion_is_ignored(tmp_path: Path) -> None:
    write_config(tmp_path, exclude=["src/generated/**"])
    write_module(tmp_path / "src" / "generated" / "client.py", 700)

    result = run_checker(tmp_path)

    assert result.returncode == 0
    assert "client.py" not in result.stdout
    assert "Architecture check: 0 modules, 0 warnings, 0 errors." in result.stdout


def test_documented_exception_permits_otherwise_failing_module(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        exceptions="\n".join(
            [
                "      - path: src/feature.py",
                "        reason: generated compatibility module",
            ]
        ),
    )
    write_module(tmp_path / "src" / "feature.py", 501)

    result = run_checker(tmp_path)

    assert result.returncode == 0
    assert "WARNING" in result.stdout
    assert "src/feature.py exempt" in result.stdout


def test_unjustified_exception_configuration_fails_validation(tmp_path: Path) -> None:
    write_config(
        tmp_path,
        exceptions="\n".join(
            [
                "      - path: src/feature.py",
                "        reason: ''",
            ]
        ),
    )
    write_module(tmp_path / "src" / "feature.py", 501)

    result = run_checker(tmp_path)

    assert result.returncode == 2
    assert "must include a non-empty reason" in result.stderr
