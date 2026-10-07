#!/usr/bin/env python3
"""Low-memory Hermes gateway entrypoint for the Northflank Telegram service.

The persisted MCP configuration remains untouched. When the low-memory guard is
enabled, every in-process call to discover_mcp_tools() becomes a no-op. This
covers both gateway boot discovery and the cron scheduler's independent MCP
initialization after platform adapters connect.
"""
from __future__ import annotations

import os
from pathlib import Path

from gateway import run as gateway_run


def _skip_mcp_discovery(*_args, **_kwargs):
    print(
        "[gateway-lite] MCP discovery bypass active for low-memory Telegram runtime",
        flush=True,
    )
    return []


async def _skip_gateway_mcp_discovery(_config: object) -> None:
    _skip_mcp_discovery()


if os.getenv("HERMES_SKIP_GATEWAY_MCP_DISCOVERY", "0").strip().lower() in {
    "1", "true", "yes", "on"
}:
    # Patch the shared module function so later imports inside cron.scheduler
    # receive the no-op too, not only gateway.run's startup wrapper.
    import tools.mcp_tool_discovery as mcp_discovery

    mcp_discovery.discover_mcp_tools = _skip_mcp_discovery
    gateway_run._discover_gateway_mcp_tools = _skip_gateway_mcp_discovery
    try:
        Path("/tmp/hermes-mcp-bypass-active").write_text("1\n", encoding="utf-8")
    except OSError:
        pass

gateway_run.main()
