from __future__ import annotations

import os
import json
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any


def env_value(name: str, default: str) -> str:
    return os.environ.get(name, default)


def start_process(command: Sequence[str], env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        list(command),
        env=env,
        text=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


def wait_for_url(url: str, process: subprocess.Popen[str], name: str) -> None:
    deadline = time.monotonic() + 30
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{name} exited before readiness with code {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (ConnectionError, TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"{name} did not become ready: {last_error!r}")


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=3) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{url} did not return a JSON object")
    return payload


def wait_for_http(url: str, name: str) -> None:
    deadline = time.monotonic() + 60
    last_error: BaseException | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    return
        except (ConnectionError, TimeoutError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"{name} did not become ready: {last_error!r}")


def run_prod_smoke() -> None:
    backend_url = env_value("PROD_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    frontend_url = env_value("PROD_FRONTEND_URL", "http://127.0.0.1:3000").rstrip("/")

    wait_for_http(f"{backend_url}/ready", "backend readiness")
    wait_for_http(f"{frontend_url}/", "frontend")

    health = get_json(f"{backend_url}/health")
    readiness = get_json(f"{backend_url}/ready")
    system_info = get_json(f"{backend_url}/api/system/info")
    openapi = get_json(f"{backend_url}/openapi.json")

    if health != {"status": "ok"}:
        raise RuntimeError(f"Unexpected health response: {health!r}")
    if readiness != {"status": "ready"}:
        raise RuntimeError(f"Unexpected readiness response: {readiness!r}")
    if system_info.get("environment") != "production":
        raise RuntimeError(f"Production stack returned non-production system info: {system_info!r}")
    if openapi.get("paths", {}).get("/api/system/info", {}).get("get", {}).get("operationId") != "getSystemInfo":
        raise RuntimeError("OpenAPI contract is missing getSystemInfo operation")

    with urllib.request.urlopen(f"{frontend_url}/", timeout=3) as response:
        body = response.read().decode("utf-8")
        content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        raise RuntimeError(f"Frontend returned unexpected content type: {content_type}")
    if "Backend system information is unavailable." in body:
        raise RuntimeError("Frontend rendered the backend error state")


def stop(processes: Sequence[subprocess.Popen[str]]) -> int:
    exit_code = 0
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        if process.returncode not in {0, -signal.SIGTERM}:
            exit_code = process.returncode
    return exit_code


def run_fullstack(mode: str) -> None:
    backend_host = env_value("BACKEND_HOST", env_value("HOST", "127.0.0.1"))
    backend_port = env_value("BACKEND_PORT", "8000")
    frontend_host = env_value("FRONTEND_HOST", env_value("HOST", "127.0.0.1"))
    frontend_port = env_value("FRONTEND_PORT", "3000")
    api_base_url = env_value("NUXT_PUBLIC_API_BASE_URL", f"http://{backend_host}:{backend_port}")

    base_env = os.environ.copy()
    backend_env = {
        **base_env,
        "HOST": backend_host,
        "PORT": backend_port,
        "APP_CORS_ALLOWED_ORIGINS": f'["http://{frontend_host}:{frontend_port}"]',
    }
    frontend_env = {
        **base_env,
        "HOST": frontend_host,
        "PORT": frontend_port,
        "NUXT_PUBLIC_API_BASE_URL": api_base_url,
    }

    if mode == "dev":
        backend_command = [
            "uv",
            "--directory",
            "backend",
            "run",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "src",
            "--host",
            backend_host,
            "--port",
            backend_port,
            "--reload",
        ]
        frontend_command = ["pnpm", "--dir", "frontend", "dev", "--host", frontend_host, "--port", frontend_port]
    elif mode == "run":
        backend_command = [
            "uv",
            "--directory",
            "backend",
            "run",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "src",
            "--host",
            backend_host,
            "--port",
            backend_port,
        ]
        frontend_command = ["node", "frontend/.output/server/index.mjs"]
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    processes = [start_process(backend_command, backend_env), start_process(frontend_command, frontend_env)]

    def handle_shutdown(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    try:
        wait_for_url(f"http://{backend_host}:{backend_port}/ready", processes[0], "backend")
        wait_for_url(f"http://{frontend_host}:{frontend_port}/", processes[1], "frontend")
        while True:
            for process in processes:
                if process.poll() is not None:
                    raise SystemExit(process.returncode)
            time.sleep(0.5)
    except KeyboardInterrupt:
        raise SystemExit(0)
    finally:
        code = stop(processes)
        if code:
            raise SystemExit(code)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"dev", "run", "prod-smoke"}:
        raise SystemExit("Usage: python tools/fullstack.py <dev|run|prod-smoke>")
    if sys.argv[1] == "prod-smoke":
        run_prod_smoke()
        return
    run_fullstack(sys.argv[1])


if __name__ == "__main__":
    main()
