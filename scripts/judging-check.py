#!/usr/bin/env python3
"""Run fresh rubric checks without funding or spending mainnet wallets."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/demo"


def run(script: str, *args: str, json_output: bool = False) -> dict | None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    (OUT / f"judging-{script}.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(
            f"FAIL {script}: exit {result.returncode}; inspect artifacts/demo/judging-{script}.log"
        )
    print(f"PASS {script}", flush=True)
    return json.loads(result.stdout) if json_output else None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    run("laptop.py", "doctor")
    run("agent_api.py", "check")
    model = run("verify-nearai.py", json_output=True)
    nonce = run("verify-attestation-negative.py", json_output=True)
    policy = json.loads((OUT / "agent-api-checks.json").read_text())
    evidence = {
        "checked_at": datetime.now(UTC).isoformat(),
        "source": "Fresh calls to the real NEAR RPC, Agent API and NEAR AI Cloud",
        "testnet_runtime_key": "RPC permission checked by doctor: restricted contract/methods and finite gas allowance",
        "model": model,
        "nonce_negative_test": nonce,
        "agent_api": policy,
        "mainnet_purchase_live_verified": False,
        "mainnet_funding": "Intentionally unfunded at the user's request. No mainnet purchase or refund was executed.",
        "test_boundary": "Payment success, refund, duplicate and concurrency behavior is covered separately by deterministic HTTP/real-Postgres integration tests.",
    }
    (OUT / "judging-evidence.json").write_text(json.dumps(evidence, indent=2))
    (ROOT / "docs/JUDGING_EVIDENCE.json").write_text(json.dumps(evidence, indent=2))
    print("Evidence: docs/JUDGING_EVIDENCE.json")
    print(
        "Mainnet sale/refund and USD-budget rejection are NOT live-verified; wallets remain unfunded."
    )
    print(
        "The real testnet paid answer is exercised separately by make demo and make record-demo."
    )


if __name__ == "__main__":
    main()
