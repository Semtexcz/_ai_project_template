from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "\n".join(
                [
                    f"Command failed: {' '.join(command)}",
                    f"Exit code: {result.returncode}",
                    "--- stdout ---",
                    result.stdout,
                    "--- stderr ---",
                    result.stderr,
                ]
            )
        )
    return result


def test_script_local_golden_path(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
    }

    run_command(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--data",
            "project_name=Script Local Golden Path",
            "--data",
            "project_type=script",
            "--data",
            "runtime_level=local",
            "--data",
            "include_reference_feature=false",
            "--trust",
            "--vcs-ref=HEAD",
            str(ROOT),
            str(generated),
        ],
        cwd=ROOT,
        env=env,
    )

    run_command(["make", "setup"], cwd=generated, env=env)
    run_command(["make", "check"], cwd=generated, env=env)
    run_command(["make", "build"], cwd=generated, env=env)

    dist = generated / "dist"
    assert any(path.suffix == ".whl" for path in dist.iterdir())
    assert any(path.name.endswith(".tar.gz") for path in dist.iterdir())
