from __future__ import annotations

import os
import subprocess
import sys
import zipfile
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


def test_library_shared_golden_path(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    consumer_env = tmp_path / "consumer-env"
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
            "project_name=Example Library",
            "--data",
            "project_type=library",
            "--data",
            "runtime_level=shared",
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
    wheels = list(dist.glob("*.whl"))
    sdists = list(dist.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1

    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())

    assert "example_library/__init__.py" in names
    assert "example_library/py.typed" in names
    assert "example_library/__main__.py" not in names
    assert not any(name.startswith("tests/") for name in names)
    assert not any(name.startswith("tools/") for name in names)
    assert not any(name.startswith("project/") for name in names)
    assert not any("__pycache__" in name for name in names)

    run_command(["uv", "venv", str(consumer_env)], cwd=generated, env=env)
    run_command(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(consumer_env / "bin" / "python"),
            str(wheels[0]),
        ],
        cwd=generated,
        env=env,
    )
    run_command(
        [
            str(consumer_env / "bin" / "python"),
            "-c",
            "from example_library import package_name; assert package_name() == 'Example Library'",
        ],
        cwd=generated,
        env=env,
    )
