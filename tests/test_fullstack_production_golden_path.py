from __future__ import annotations

import os
import socket
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast


ROOT = Path(__file__).resolve().parents[1]


def run_command(
    command: list[str],
    cwd: Path,
    env: Mapping[str, str],
    *,
    timeout: int = 600,
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


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return cast(int, sock.getsockname()[1])


def assert_production_runtime_files(generated: Path) -> None:
    compose = (generated / "compose.yaml").read_text()
    backend_dockerfile = (generated / "backend" / "Dockerfile").read_text()
    frontend_dockerfile = (generated / "frontend" / "Dockerfile").read_text()

    forbidden = ("fastapi dev", "uvicorn --reload", "pnpm dev", "nuxt dev", "volumes:")
    for value in forbidden:
        assert value not in compose
    assert "target: runtime" in compose
    assert "healthcheck:" in compose
    assert "depends_on:" in compose

    assert " AS builder" in backend_dockerfile
    assert " AS runtime" in backend_dockerfile
    assert "USER app" in backend_dockerfile
    assert "fastapi run" not in backend_dockerfile
    assert "uv run" not in backend_dockerfile

    assert " AS dependencies" in frontend_dockerfile
    assert " AS build" in frontend_dockerfile
    assert " AS runtime" in frontend_dockerfile
    assert "USER app" in frontend_dockerfile
    assert "nuxt dev" not in frontend_dockerfile
    assert "pnpm dev" not in frontend_dockerfile


def test_fullstack_production_golden_path(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    backend_port = free_port()
    frontend_port = free_port()
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "PNPM_HOME": str(tmp_path / "pnpm-home"),
        "PNPM_STORE_DIR": str(tmp_path / "pnpm-store"),
        "COMPOSE_PROJECT_NAME": f"golden-prod-{tmp_path.name}",
        "PROD_BACKEND_PORT": str(backend_port),
        "PROD_FRONTEND_PORT": str(frontend_port),
        "NUXT_PUBLIC_API_BASE_URL": f"http://127.0.0.1:{backend_port}",
    }

    run_command(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--data",
            "project_name=Example Production",
            "--data",
            "project_type=fullstack",
            "--data",
            "runtime_level=production",
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

    try:
        run_command(["make", "setup"], generated, env, timeout=600)
        run_command(["make", "api-check"], generated, env)
        run_command(["make", "check"], generated, env, timeout=600)
        run_command(["make", "build"], generated, env, timeout=600)

        assert (generated / "backend" / "dist").is_dir()
        assert (generated / "frontend" / ".output" / "server" / "index.mjs").is_file()
        assert_production_runtime_files(generated)

        run_command(["make", "image-build"], generated, env, timeout=900)
        run_command(["make", "prod-up"], generated, env, timeout=300)
        run_command(["make", "prod-smoke"], generated, env, timeout=180)
        run_command(["make", "e2e-production"], generated, env, timeout=180)
    finally:
        if generated.exists():
            subprocess.run(
                ["make", "prod-down"],
                cwd=generated,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=180,
            )
