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


def run_command(
    command: list[str],
    cwd: Path,
    env: Mapping[str, str],
    *,
    timeout: int = 300,
    expect_success: bool = True,
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
    if expect_success and result.returncode != 0:
        raise AssertionError(command_failure(command, result))
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"Command unexpectedly passed: {' '.join(command)}")
    return result


def command_failure(command: list[str], result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        [
            f"Command failed: {' '.join(command)}",
            f"Exit code: {result.returncode}",
            "--- stdout ---",
            result.stdout,
            "--- stderr ---",
            result.stderr,
        ]
    )


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return cast(int, sock.getsockname()[1])


def get_text(base_url: str, path: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=2) as response:
        return response.status, response.headers.get("content-type", ""), response.read().decode()


def get_json(base_url: str, path: str) -> dict[str, Any]:
    status, _, body = get_text(base_url, path)
    if status != 200:
        raise AssertionError(f"{path} returned {status}")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise AssertionError(f"{path} did not return a JSON object")
    return cast(dict[str, Any], payload)


def stop_process(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            return process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            return process.communicate(timeout=10)
    return process.communicate(timeout=1)


def wait_for_json(base_url: str, path: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 40
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(
                "\n".join(
                    [
                        f"Fullstack runtime exited early with {process.returncode}",
                        "--- stdout ---",
                        stdout,
                        "--- stderr ---",
                        stderr,
                    ]
                )
            )
        try:
            get_json(base_url, path)
            return
        except (ConnectionError, TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(0.25)
    stdout, stderr = stop_process(process)
    raise AssertionError(
        "\n".join(
            [
                f"Runtime did not become ready: {last_error!r}",
                "--- stdout ---",
                stdout,
                "--- stderr ---",
                stderr,
            ]
        )
    )


def wait_for_frontend(base_url: str, process: subprocess.Popen[str]) -> str:
    deadline = time.monotonic() + 40
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(
                "\n".join(
                    [
                        f"Fullstack runtime exited early with {process.returncode}",
                        "--- stdout ---",
                        stdout,
                        "--- stderr ---",
                        stderr,
                    ]
                )
            )
        try:
            status, content_type, body = get_text(base_url, "/")
            if status == 200 and "text/html" in content_type:
                return body
        except (ConnectionError, TimeoutError, urllib.error.URLError) as exc:
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


def start_fullstack(
    generated: Path,
    env: Mapping[str, str],
    *,
    api_base_url: str | None = None,
) -> tuple[subprocess.Popen[str], int, int]:
    backend_port = free_port()
    frontend_port = free_port()
    process_env = {
        **env,
        "BACKEND_HOST": "127.0.0.1",
        "BACKEND_PORT": str(backend_port),
        "FRONTEND_HOST": "127.0.0.1",
        "FRONTEND_PORT": str(frontend_port),
        "NUXT_PUBLIC_API_BASE_URL": api_base_url or f"http://127.0.0.1:{backend_port}",
    }
    process = subprocess.Popen(
        ["make", "run"],
        cwd=generated,
        env=process_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    return process, backend_port, frontend_port


def assert_built_runtime(generated: Path, env: Mapping[str, str]) -> None:
    process, backend_port, frontend_port = start_fullstack(generated, env)
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    e2e_env = {**env, "E2E_BASE_URL": frontend_url}

    try:
        wait_for_json(backend_url, "/ready", process)
        wait_for_frontend(frontend_url, process)
        assert get_json(backend_url, "/health") == {"status": "ok"}
        assert get_json(backend_url, "/ready") == {"status": "ready"}
        assert get_json(backend_url, "/api/system/info") == {
            "name": "Example Fullstack",
            "version": "0.1.0",
            "environment": "local",
            "next_step": "Open project/brief.md",
        }
        openapi = get_json(backend_url, "/openapi.json")
        assert openapi["paths"]["/api/system/info"]["get"]["operationId"] == "getSystemInfo"

        run_command(["make", "e2e"], generated, e2e_env, timeout=180)
    except Exception:
        stdout, stderr = stop_process(process)
        raise AssertionError(
            "\n".join(
                [
                    "Built fullstack runtime failed",
                    "--- stdout ---",
                    stdout,
                    "--- stderr ---",
                    stderr,
                ]
            )
        )
    else:
        stop_process(process)


def assert_runtime_integration_failure(generated: Path, env: Mapping[str, str]) -> None:
    unused_port = free_port()
    process, _, frontend_port = start_fullstack(
        generated,
        env,
        api_base_url=f"http://127.0.0.1:{unused_port}",
    )
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    e2e_env = {**env, "E2E_BASE_URL": frontend_url}

    try:
        wait_for_frontend(frontend_url, process)
        run_command(["make", "e2e"], generated, e2e_env, timeout=180, expect_success=False)
    finally:
        stop_process(process)


def assert_contract_drift_is_detected(generated: Path, env: Mapping[str, str]) -> None:
    route_path = generated / "backend" / "src" / "app" / "modules" / "system" / "api" / "routes.py"
    original = route_path.read_text()
    try:
        route_path.write_text(
            original.replace(
                "class SystemInfoResponse(BaseModel):\n    name: str\n",
                "class SystemInfoResponse(BaseModel):\n    build: str\n    name: str\n",
            )
        )
        result = run_command(["make", "api-check"], generated, env, expect_success=False)
        assert "Generated OpenAPI client drift detected" in result.stdout
    finally:
        route_path.write_text(original)
        run_command(["make", "api-check"], generated, env)


def test_fullstack_local_golden_path(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "PNPM_HOME": str(tmp_path / "pnpm-home"),
        "PNPM_STORE_DIR": str(tmp_path / "pnpm-store"),
    }

    run_command(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--data",
            "project_name=Example Fullstack",
            "--data",
            "project_type=fullstack",
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

    run_command(["make", "setup"], generated, env, timeout=600)
    run_command(["make", "validate-docs"], generated, env)
    run_command(["make", "api-check"], generated, env)
    assert_contract_drift_is_detected(generated, env)
    run_command(["make", "check"], generated, env, timeout=300)
    run_command(["make", "build"], generated, env, timeout=300)

    assert (generated / "backend" / "dist").is_dir()
    assert (generated / "frontend" / ".output" / "server" / "index.mjs").is_file()

    assert_built_runtime(generated, env)
    assert_runtime_integration_failure(generated, env)
