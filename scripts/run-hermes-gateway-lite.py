#!/usr/bin/env python3
"""Low-memory Hermes gateway entrypoint for the Northflank Telegram service.

Hermes v2026.9.11 performs MCP discovery before platform adapters. On a small
single-instance container, stale/heavy MCP startup can prevent Telegram from
ever reaching polling. This wrapper preserves upstream gateway.run unchanged
and replaces only that boot discovery step when explicitly enabled.
"""
from __future__ import annotations

import os
import sys

from gateway import run as gateway_run


async def _skip_gateway_mcp_discovery(_config: object) -> None:
    print(
        "[gateway-lite] skipping boot-time MCP discovery; persisted MCP config is unchanged",
        flush=True,
    )


if os.getenv("HERMES_SKIP_GATEWAY_MCP_DISCOVERY", "0").strip().lower() in {
    "1", "true", "yes", "on"
}:
    gateway_run._discover_gateway_mcp_tools = _skip_gateway_mcp_discovery

# Preserve gateway.run's argparse contract.
gateway_run.main()
