from __future__ import annotations

import argparse
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_API_PORT = 18083
DEFAULT_FRONTEND_PORT = 9527


def local_demo_environment() -> dict[str, str]:
    username = os.environ.get("LOCAL_DEMO_USERNAME", "demo").strip() or "demo"
    password = os.environ.get("LOCAL_DEMO_PASSWORD", "").strip()
    if not password:
        password = f"LocalDemo-{secrets.token_urlsafe(12)}"
    return {
        "APP_ENV": "staging",
        "ENVIRONMENT": "staging",
        "DEMO_LOGIN_ENABLED": "true",
        "DEMO_LOGIN_USERNAME": username,
        "DEMO_LOGIN_PASSWORD": password,
        "DEMO_CAPTCHA_CODE": "1111",
        "DEMO_CAPTCHA_KEY": "DEMO-CAPTCHA",
        "DATABASE_URL": "",
        "MIGRATION_ORGANIZATION_ENABLED": "false",
        "MIGRATION_LIVE_ENABLED": "false",
        "MIGRATION_ORDER_ENABLED": "false",
        "MIGRATION_FINANCE_ENABLED": "false",
        "MIGRATION_SYSTEM_ENABLED": "false",
    }


def run_local_stack(
    project_root: Path,
    *,
    frontend_port: int = DEFAULT_FRONTEND_PORT,
    api_port: int = DEFAULT_API_PORT,
) -> None:
    root = project_root.resolve()
    frontend_root = root / "frontend"
    if not (frontend_root / "package.json").is_file():
        raise FileNotFoundError(
            f"frontend/package.json does not exist; restore the frontend first: {frontend_root}"
        )
    if not (frontend_root / "node_modules").is_dir():
        raise FileNotFoundError(
            f"frontend/node_modules is missing; run 'pnpm install' in {frontend_root}"
        )
    if frontend_port == api_port:
        raise ValueError("frontend and API ports must be different")
    _ensure_port_available(DEFAULT_HOST, api_port)
    _ensure_port_available(DEFAULT_HOST, frontend_port)

    environment = os.environ.copy()
    environment.update(local_demo_environment())

    api_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            DEFAULT_HOST,
            "--port",
            str(api_port),
        ],
        cwd=root,
        env=environment,
    )

    frontend_process = None
    try:
        _wait_for_api(api_process, api_port)
        frontend_process = _start_frontend(
            frontend_root,
            api_port=api_port,
            frontend_port=frontend_port,
        )
        _wait_for_frontend(frontend_process, frontend_port)
        print(f"前端地址: http://{DEFAULT_HOST}:{frontend_port}/", flush=True)
        print(f"API 文档: http://{DEFAULT_HOST}:{api_port}/docs", flush=True)
        print(f"演示账号: {environment['DEMO_LOGIN_USERNAME']}", flush=True)
        print(f"演示密码: {environment['DEMO_LOGIN_PASSWORD']}", flush=True)
        print("演示验证码: 1111", flush=True)
        print("按 Ctrl+C 停止本地联调环境", flush=True)

        # 保持前台运行，直到任一子进程退出或被 Ctrl+C 中断
        while True:
            if api_process.poll() is not None:
                raise RuntimeError(
                    f"local API exited unexpectedly: {api_process.returncode}"
                )
            if frontend_process.poll() is not None:
                raise RuntimeError(
                    f"frontend dev server exited unexpectedly: {frontend_process.returncode}"
                )
            time.sleep(0.5)
    finally:
        _stop_process(frontend_process)
        _stop_process(api_process)


def _start_frontend(
    frontend_root: Path,
    *,
    api_port: int,
    frontend_port: int,
) -> subprocess.Popen:
    """启动 vite dev server（pnpm dev），代理指向本地后端 API。"""
    if shutil.which("pnpm") is None:
        raise FileNotFoundError(
            "pnpm is not installed; install it first (https://pnpm.io/installation)"
        )

    environment = os.environ.copy()
    # vite 的 loadEnv 会优先使用进程环境变量，覆盖 .env.test 中的后端地址
    environment["VITE_SERVICE_BASE_URL"] = f"http://{DEFAULT_HOST}:{api_port}"

    command = f"pnpm dev --host {DEFAULT_HOST} --port {frontend_port} --open=false"
    return subprocess.Popen(
        command,
        cwd=frontend_root,
        env=environment,
        shell=True,
    )


def _ensure_port_available(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError as error:
            raise RuntimeError(f"port is already in use: {host}:{port}") from error


def _wait_for_api(process: subprocess.Popen, port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    health_url = f"http://{DEFAULT_HOST}:{port}/internal/health/live"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"local API exited during startup: {process.returncode}")
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.1)
    raise TimeoutError(f"local API did not become healthy: {health_url}")


def _wait_for_frontend(
    process: subprocess.Popen,
    port: int,
    timeout: float = 60.0,
) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://{DEFAULT_HOST}:{port}/"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"frontend dev server exited during startup: {process.returncode}"
            )
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.2)
    raise TimeoutError(f"frontend dev server did not become ready: {url}")


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start the local frontend (vite) and Python API"
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT)
    args = parser.parse_args(argv)

    try:
        run_local_stack(
            args.project_root,
            frontend_port=args.frontend_port,
            api_port=args.api_port,
        )
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

