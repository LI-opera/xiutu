"""Standalone real HTTP SDK client. Credentials never accepted on command line."""

import argparse
import asyncio
import json
from pathlib import Path

from app.domain.policies import DomainError
from app.infrastructure.mcp_client import ClientConfig, ManualMCPClient
from app.mcp_server.config import TOOLS, read_config


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--tool", choices=TOOLS, required=True)
    p.add_argument("--arguments", required=True, help="JSON file with model tool arguments only")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    try:
        cfg = read_config(a.config, ClientConfig)
        args = json.loads(Path(a.arguments).read_text(encoding="utf8"))
        answer = asyncio.run(ManualMCPClient(cfg).exchange(a.tool, args))
        with Path(a.output).open("x", encoding="utf8") as f:
            json.dump(
                dict(
                    protocol="2025-11-25", transport="streamable-http", tool=a.tool, answer=answer
                ),
                f,
                ensure_ascii=False,
                indent=2,
            )
        print("MCP call completed; result saved to requested output")
        return 0
    except DomainError as exc:
        print("MCP call failed: " + exc.code)
        return 1
    except Exception:
        print("MCP configuration or exchange failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
