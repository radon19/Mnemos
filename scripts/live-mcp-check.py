#!/usr/bin/env python3
"""Live check for the MCP server against NEAR testnet.

Reads the account file for the agent key, runs the read-only MCP commands and
prints their output. Nothing secret is printed: the outputs contain account
ids, prices and balances only.

Usage:
    uv run --project apps/broker python scripts/live-mcp-check.py
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = ROOT / "apps" / "mcp" / "dist" / "cli.js"


def main() -> int:
    accounts = json.loads((ROOT / ".secrets" / "accounts.json").read_text())
    agent = accounts["agent"]
    owner = accounts["owner"]
    contract = accounts["contract"]

    environment = {
        **os.environ,
        "MNEMOS_CONTRACT_ID": contract["account_id"],
        "MNEMOS_AGENT_ACCOUNT": agent["account_id"],
        "MNEMOS_AGENT_KEY": agent["secret_key"],
        "MNEMOS_BROKER_URL": os.environ.get("MNEMOS_BROKER_URL", "http://localhost:8000"),
        "MNEMOS_BROKER_RECIPIENT": os.environ.get(
            "MNEMOS_BROKER_RECIPIENT", "localhost:8000"
        ),
        "NEAR_RPC_URL": os.environ.get(
            "NEAR_RPC_URL", "https://test.rpc.fastnear.com"
        ),
        "MNEMOS_NETWORK_ID": "testnet",
    }

    node = shutil.which("node")
    if node is None:
        raise SystemExit("node is not on the PATH")

    commands = [
        ["credit"],
        ["grants", "--owner", owner["account_id"]],
    ]
    failed = False
    for command in commands:
        print(f"$ mnemos-agent {' '.join(command)}")
        result = subprocess.run(
            [node, str(CLI), *command],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode != 0:
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
