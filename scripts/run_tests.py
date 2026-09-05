#!/usr/bin/env python3
"""
LEDGER Test Suite Runner
========================
Runs tests for answer-validator-api and orchestrator-api in isolated environments
to prevent module namespace collisions.
"""

import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SUITES = [
    {
        "name": "Answer Validator API Tests",
        "cwd": REPO_ROOT / "answer-validator-api",
        "cmd": [sys.executable, "-m", "pytest", "tests/test_validator.py", "-v"],
    },
    {
        "name": "Orchestrator API Unit Tests",
        "cwd": REPO_ROOT / "orchestrator-api",
        "cmd": [sys.executable, "-m", "pytest", "tests/test_orchestrator.py", "-v"],
    },
    {
        "name": "Orchestrator End-to-End Integration Tests",
        "cwd": REPO_ROOT / "orchestrator-api",
        "cmd": [sys.executable, "-m", "pytest", "tests/test_e2e_integration.py", "-v"],
    },
]


def main():
    print("=" * 60)
    print("          LEDGER TEST SUITE EXECUTION")
    print("=" * 60)

    total_failed = 0

    for suite in SUITES:
        print(f"\n>> Running {suite['name']}...")
        print("-" * 60)
        res = subprocess.run(suite["cmd"], cwd=str(suite["cwd"]))
        if res.returncode != 0:
            total_failed += 1

    print("\n" + "=" * 60)
    if total_failed == 0:
        print(" [SUCCESS] ALL TEST SUITES PASSED SUCCESSFULLY")
    else:
        print(f" [FAILURE] {total_failed} TEST SUITE(S) FAILED")
    print("=" * 60)

    sys.exit(total_failed)


if __name__ == "__main__":
    main()
