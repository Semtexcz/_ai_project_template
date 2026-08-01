from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any


EXPECTED_SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
}
EXPECTED_CSP_TOKENS = [
    "default-src 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
]
ROOT = Path(__file__).resolve().parents[1]


def env_value(name: str, default: str) -> str:
    return os.environ.get(name, default)


def pnpm_command() -> list[str]:
    return shlex.split(os.environ.get("PNPM", "corepack pnpm"))


def start_process(
    command: Sequence[str],
    env: dict[str, str],
    *,
    cwd: Path | None = None,
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        list(command),
        cwd=cwd,
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


def run_checked(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "\n".join(
                [
                    f"Command failed: {' '.join(command)}",
                    "--- stdout ---",
                    result.stdout,
                    "--- stderr ---",
                    result.stderr,
                ]
            )
        )
    return result


def docker_json(command: Sequence[str]) -> Any:
    output = run_checked(command).stdout
    if not output.strip():
        raise RuntimeError("No Compose services are running")
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return [json.loads(line) for line in output.splitlines() if line.strip()]


def compose_command(*args: str) -> list[str]:
    command = env_value("COMPOSE", "docker compose").split()
    command.extend(args)
    return command


def image_inspect(image: str) -> dict[str, Any]:
    payload = docker_json(["docker", "image", "inspect", image])
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"Image does not exist or cannot be inspected: {image}")
    item = payload[0]
    if not isinstance(item, dict):
        raise RuntimeError(f"Unexpected image inspect payload for {image}")
    return item


def image_config(image: str) -> dict[str, Any]:
    config = image_inspect(image).get("Config")
    if not isinstance(config, dict):
        raise RuntimeError(f"{image} is missing image config")
    return config


def assert_image_contract(
    image: str,
    *,
    expected_port: str,
    forbidden_terms: Sequence[str],
) -> None:
    config = image_config(image)
    user = str(config.get("User") or "")
    if user in {"", "0", "root"}:
        raise RuntimeError(f"{image} must use a non-root runtime user, got {user!r}")
    command = [str(value) for value in config.get("Cmd") or []]
    entrypoint = [str(value) for value in config.get("Entrypoint") or []]
    process = " ".join(entrypoint + command)
    if not process.strip():
        raise RuntimeError(f"{image} must define a command or entrypoint")
    lowered = process.lower()
    for term in forbidden_terms:
        if term in lowered:
            raise RuntimeError(f"{image} runtime process contains forbidden term {term!r}: {process}")
    exposed = config.get("ExposedPorts")
    if not isinstance(exposed, dict) or f"{expected_port}/tcp" not in exposed:
        raise RuntimeError(f"{image} must expose TCP port {expected_port}")
    if not config.get("Env"):
        raise RuntimeError(f"{image} must include basic environment metadata")


def run_image_inspect() -> None:
    backend_image = env_value("BACKEND_IMAGE", "app-backend:production")
    frontend_image = env_value("FRONTEND_IMAGE", "app-frontend:production")
    assert_image_contract(
        backend_image,
        expected_port="8000",
        forbidden_terms=["--reload", "reload", "fastapi dev"],
    )
    assert_image_contract(
        frontend_image,
        expected_port="3000",
        forbidden_terms=["nuxt dev", "pnpm dev", "vite", "hmr"],
    )
    print(f"Image inspection passed: {backend_image}, {frontend_image}")


def run_prod_status() -> None:
    deadline = time.monotonic() + 60
    services: list[Any] = []
    failures: list[str] = []
    while time.monotonic() < deadline:
        payload = docker_json(compose_command("ps", "--format", "json"))
        services = payload if isinstance(payload, list) else [payload]
        if not services:
            raise RuntimeError("No Compose services are running")
        failures = compose_status_failures(services)
        if not failures:
            break
        if any("health is unhealthy" in failure.lower() for failure in failures):
            break
        time.sleep(1)
    for service in services:
        if not isinstance(service, dict):
            raise RuntimeError(f"Unexpected Compose status payload: {service!r}")
        name = service.get("Service") or service.get("Name")
        state = str(service.get("State") or "")
        health = str(service.get("Health") or "")
        image = service.get("Image")
        ports = service.get("Publishers") or service.get("Ports") or []
        print(f"{name}: state={state} health={health or 'none'} image={image} ports={ports}")
    if failures:
        raise RuntimeError("; ".join(failures))


def compose_status_failures(services: Sequence[Any]) -> list[str]:
    failures: list[str] = []
    for service in services:
        if not isinstance(service, dict):
            raise RuntimeError(f"Unexpected Compose status payload: {service!r}")
        name = service.get("Service") or service.get("Name")
        state = str(service.get("State") or "")
        health = str(service.get("Health") or "")
        if state.lower() != "running":
            failures.append(f"{name} is {state}")
        if health and health.lower() != "healthy":
            failures.append(f"{name} health is {health}")
    return failures


def assert_security_headers(headers: Any) -> None:
    lowered = {key.lower(): value for key, value in headers.items()}
    for key, expected in EXPECTED_SECURITY_HEADERS.items():
        actual = lowered.get(key)
        if actual != expected:
            raise RuntimeError(f"Missing or invalid {key}: expected {expected!r}, got {actual!r}")
    csp = lowered.get("content-security-policy", "")
    for token in EXPECTED_CSP_TOKENS:
        if token not in csp:
            raise RuntimeError(f"Content-Security-Policy is missing {token!r}: {csp!r}")


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
        assert_security_headers(response.headers)
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

    corepack_home = Path(os.environ.get("COREPACK_HOME", ROOT / ".corepack"))
    corepack_home.mkdir(parents=True, exist_ok=True)
    base_env = {**os.environ, "COREPACK_HOME": str(corepack_home)}
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
        frontend_command = [
            *pnpm_command(),
            "dev",
            "--host",
            frontend_host,
            "--port",
            frontend_port,
        ]
        frontend_cwd = ROOT / "frontend"
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
        frontend_cwd = None
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    processes = [
        start_process(backend_command, backend_env),
        start_process(frontend_command, frontend_env, cwd=frontend_cwd),
    ]

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
    if len(sys.argv) != 2 or sys.argv[1] not in {"dev", "run", "prod-smoke", "image-inspect", "prod-status"}:
        raise SystemExit("Usage: python tools/fullstack.py <dev|run|prod-smoke|image-inspect|prod-status>")
    if sys.argv[1] == "prod-smoke":
        run_prod_smoke()
        return
    if sys.argv[1] == "image-inspect":
        run_image_inspect()
        return
    if sys.argv[1] == "prod-status":
        run_prod_status()
        return
    run_fullstack(sys.argv[1])


if __name__ == "__main__":
    main()
