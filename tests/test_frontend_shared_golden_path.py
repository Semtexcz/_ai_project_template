from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import cast


ROOT = Path(__file__).resolve().parents[1]


def run_command(
    command: list[str],
    cwd: Path,
    env: Mapping[str, str],
    *,
    timeout: int = 240,
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


def stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            return process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            return process.communicate(timeout=10)
    return process.communicate(timeout=1)


def read_root_html(base_url: str, process: subprocess.Popen[str]) -> str:
    deadline = time.monotonic() + 30
    last_error: BaseException | None = None

    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(
                "\n".join(
                    [
                        f"Frontend exited before readiness with code {process.returncode}",
                        "--- stdout ---",
                        stdout,
                        "--- stderr ---",
                        stderr,
                    ]
                )
            )

        try:
            with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
                body = response.read().decode("utf-8")
                if response.status != 200:
                    raise AssertionError(f"/ returned {response.status}")
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    raise AssertionError(f"/ returned {content_type}")
                return body
        except (AssertionError, ConnectionError, TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(0.25)

    stdout, stderr = stop_process(process)
    raise AssertionError(
        "\n".join(
            [
                f"Frontend did not become ready: {last_error!r}",
                "--- stdout ---",
                stdout,
                "--- stderr ---",
                stderr,
            ]
        )
    )


def assert_frontend_runtime(generated: Path, env: Mapping[str, str]) -> None:
    port = free_port()
    process = subprocess.Popen(
        ["make", "run"],
        cwd=generated,
        env={**env, "HOST": "127.0.0.1", "PORT": str(port)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )

    try:
        body = read_root_html(f"http://127.0.0.1:{port}", process)
        assert "Example Frontend" in body
        assert "<h1" in body
        assert "project/brief.md" in body

        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/missing", timeout=2)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        else:
            raise AssertionError("/missing did not return 404")
    except Exception:
        stdout, stderr = stop_process(process)
        raise AssertionError(
            "\n".join(
                [
                    "Frontend smoke test failed",
                    "--- stdout ---",
                    stdout,
                    "--- stderr ---",
                    stderr,
                ]
            )
        )
    else:
        stop_process(process)


def test_frontend_shared_golden_path(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "PNPM_HOME": str(tmp_path / "pnpm-home"),
        "PNPM_STORE_DIR": str(tmp_path / "pnpm-store"),
        "PNPM_INSTALL_FLAGS": "--frozen-lockfile",
    }

    run_command(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--data",
            "project_name=Example Frontend",
            "--data",
            "project_type=frontend",
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

    run_command(["make", "setup"], cwd=generated, env=env, timeout=480)
    run_command(["make", "check"], cwd=generated, env=env)
    run_command(["make", "build"], cwd=generated, env=env)

    server_entry = generated / "frontend" / ".output" / "server" / "index.mjs"
    assert server_entry.is_file()

    assert_frontend_runtime(generated, env)
