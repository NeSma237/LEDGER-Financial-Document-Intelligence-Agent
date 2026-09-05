#!/usr/bin/env python3
"""
LEDGER Unified Microservice Runner
==================================
Starts and manages all available microservices for the LEDGER system with
appropriate environment configurations and graceful shutdown.
"""

import os
import sys
import time
import signal
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# Define services with their working directories, entry commands, ports, and environment
SERVICES = [
    {
        "name": "answer-validator-api",
        "cwd": REPO_ROOT / "answer-validator-api",
        "cmd": [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005"],
        "port": 8005,
        "health_path": "/health",
        "env": {},
        "required": True,
    },
    {
        "name": "document_processor",
        "cwd": REPO_ROOT / "document_processor",
        "cmd": [sys.executable, "-m", "uvicorn", "doc_processor_api:app", "--host", "0.0.0.0", "--port", "8001"],
        "port": 8001,
        "health_path": "/docs",
        "env": {},
        "required": False,
    },
    {
        "name": "retrieval-api",
        "cwd": REPO_ROOT / "retrieval-api",
        "cmd": [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"],
        "port": 8002,
        "health_path": "/health",
        "env": {},
        "required": False,
    },
    {
        "name": "agent-service",
        "cwd": REPO_ROOT / "agent-service",
        "cmd": [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"],
        "port": 8003,
        "health_path": "/health",
        "env": {
            "VALIDATOR_URL": "http://localhost:8005",
            "RETRIEVAL_URL": "http://localhost:8002",
        },
        "required": False,
    },
    {
        "name": "orchestrator-api",
        "cwd": REPO_ROOT / "orchestrator-api",
        "cmd": [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        "port": 8000,
        "health_path": "/health",
        "env": {
            "AGENT_SERVICE_URL": "http://localhost:8003",
            "VALIDATOR_SERVICE_URL": "http://localhost:8005",
            "DOC_PROCESSOR_URL": "http://localhost:8001",
            "RETRIEVAL_SERVICE_URL": "http://localhost:8002",
        },
        "required": True,
    },
    {
        "name": "eval-service",
        "cwd": REPO_ROOT / "eval-service",
        "cmd": [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"],
        "port": 8004,
        "health_path": "/health",
        "env": {},
        "required": False,
        "check_file": "app/main.py",
    },
    {
        "name": "ui-service",
        "cwd": REPO_ROOT / "ui-service",
        "cmd": [sys.executable, "app/main.py"],
        "port": 7860,
        "health_path": "/",
        "env": {},
        "required": False,
        "check_file": "app/main.py",
    },
]


def is_service_ready(host: str, port: int, path: str) -> bool:
    url = f"http://{host}:{port}{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HealthCheck"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status in (200, 404)
    except Exception:
        return False


def main():
    print("=" * 65)
    print("      LEDGER MICROSERVICE ORCHESTRATION RUNNER")
    print("=" * 65)

    running_processes = []

    def shutdown(signum=None, frame=None):
        print("\n\nStopping all LEDGER microservices...")
        for name, proc in reversed(running_processes):
            print(f"  Stopping {name} (PID {proc.pid})...")
            try:
                proc.terminate()
            except Exception:
                pass
        for name, proc in running_processes:
            try:
                proc.wait(timeout=3)
            except Exception:
                proc.kill()
        print("All services stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    for svc in SERVICES:
        name = svc["name"]
        cwd = svc["cwd"]
        port = svc["port"]
        check_file = svc.get("check_file")

        # Verify cwd exists
        if not cwd.exists():
            if svc["required"]:
                print(f"[ERROR] Required service directory missing: {cwd}")
                shutdown()
            else:
                print(f"[SKIP] {name}: Directory '{cwd.name}' does not exist.")
                continue

        # Check if entry file exists for optional services
        if check_file and not (cwd / check_file).exists():
            print(f"[SKIP] {name}: Entry point '{check_file}' not found (service pending teammate implementation).")
            continue

        # Prepare environment
        env = os.environ.copy()
        env.update(svc.get("env", {}))

        print(f"[START] Starting {name:22} on port {port}...")
        try:
            proc = subprocess.Popen(
                svc["cmd"],
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            running_processes.append((name, proc))
        except Exception as e:
            if svc["required"]:
                print(f"[ERROR] Failed to start required service {name}: {e}")
                shutdown()
            else:
                print(f"[WARN] Failed to start optional service {name}: {e}")

    # Wait for services to respond
    print("\nWaiting for services to become healthy...")
    time.sleep(2)

    for name, svc in [(s["name"], s) for s in SERVICES if any(p[0] == s["name"] for p in running_processes)]:
        ready = False
        for _ in range(15):
            if is_service_ready("127.0.0.1", svc["port"], svc["health_path"]):
                ready = True
                break
            time.sleep(1)

        if ready:
            print(f"  [OK] {name:22} is healthy at http://localhost:{svc['port']}")
        else:
            print(f"  [WAIT] {name:22} started (port {svc['port']}), waiting for complete initialization...")

    print("\n" + "=" * 65)
    print(" All active LEDGER services are running.")
    print(" Press Ctrl+C to terminate all services.")
    print("=" * 65)

    try:
        while True:
            time.sleep(1)
            # Monitor any crashed processes
            for name, proc in running_processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"[NOTICE] Service '{name}' exited with code {ret}")
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
