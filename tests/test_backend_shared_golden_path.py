from __future__ import annotations

import json
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
from typing import Any, cast


ROOT = Path(__file__).resolve().parents[1]


def run_command(command: list[str], cwd: Path, env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=180,
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


def get_json(base_url: str, path: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=2) as response:
        if response.status != 200:
            raise AssertionError(f"{path} returned {response.status}")
        payload = json.loads(response.read().decode("utf-8"))

    if not isinstance(payload, dict):
        raise AssertionError(f"{path} did not return a JSON object")
    return cast(dict[str, Any], payload)


def wait_until_ready(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    last_error: BaseException | None = None

    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(
                "\n".join(
                    [
                        f"Server exited before readiness with code {process.returncode}",
                        "--- stdout ---",
                        stdout,
                        "--- stderr ---",
                        stderr,
                    ]
                )
            )

        try:
            if get_json(base_url, "/ready") == {"status": "ready"}:
                return
        except (ConnectionError, TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(0.25)

    stdout, stderr = stop_process(process)
    raise AssertionError(
        "\n".join(
            [
                f"Server did not become ready: {last_error!r}",
                "--- stdout ---",
                stdout,
                "--- stderr ---",
                stderr,
            ]
        )
    )


def stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            return process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            return process.communicate(timeout=10)
    return process.communicate(timeout=1)


def assert_backend_contract(base_url: str) -> None:
    assert get_json(base_url, "/health") == {"status": "ok"}
    assert get_json(base_url, "/ready") == {"status": "ready"}

    openapi = get_json(base_url, "/openapi.json")
    assert openapi["info"]["title"] == "Example Backend"
    assert openapi["info"]["version"] == "0.1.0"
    assert "/health" in openapi["paths"]
    assert "/ready" in openapi["paths"]


def assert_server_contract(
    command: list[str],
    cwd: Path,
    env: Mapping[str, str],
    *,
    command_uses_env_port: bool = True,
) -> None:
    port = free_port()
    actual_command = command
    if not command_uses_env_port:
        actual_command = [*command, "--host", "127.0.0.1", "--port", str(port)]

    process_env = {**env, "HOST": "127.0.0.1", "PORT": str(port)}
    process = subprocess.Popen(
        actual_command,
        cwd=cwd,
        env=process_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    base_url = f"http://127.0.0.1:{port}"

    try:
        wait_until_ready(base_url, process)
        assert_backend_contract(base_url)
    except Exception:
        stdout, stderr = stop_process(process)
        raise AssertionError(
            "\n".join(
                [
                    f"Server smoke test failed: {' '.join(actual_command)}",
                    "--- stdout ---",
                    stdout,
                    "--- stderr ---",
                    stderr,
                ]
            )
        )
    else:
        stop_process(process)


def test_backend_shared_golden_path(tmp_path: Path) -> None:
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
            "project_name=Example Backend",
            "--data",
            "project_type=backend",
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

    dist = generated / "backend" / "dist"
    wheels = list(dist.glob("*.whl"))
    sdists = list(dist.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1

    assert_server_contract(["make", "run"], generated, env)

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
    assert_server_contract(
        [
            str(consumer_env / "bin" / "python"),
            "-m",
            "uvicorn",
            "app.main:app",
        ],
        tmp_path,
        env,
        command_uses_env_port=False,
    )
