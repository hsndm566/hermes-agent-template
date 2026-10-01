#!/usr/bin/env python3
"""Read or write the owner-scoped My Agent context bridge.

The bridge uses Supabase's secret-gated RPCs.  It never prints credentials and
returns only the small set of records matching the requested query.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _call(function: str, payload: dict[str, str]) -> object:
    base = os.getenv("MY_AGENT_CONTEXT_URL", "").strip().rstrip("/")
    key = os.getenv("MY_AGENT_CONTEXT_PUBLISHABLE_KEY", "").strip()
    secret = os.getenv("MY_AGENT_CONTEXT_SECRET", "").strip()
    if not base or not key or not secret:
        raise RuntimeError("My Agent context bridge is not configured")
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/rest/v1/rpc/{function}",
        data=body,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(512).decode("utf-8", errors="replace")
        raise RuntimeError(f"context bridge HTTP {exc.code}: {detail[:240]}") from exc


def read(query: str) -> int:
    owner_id = os.getenv("MY_AGENT_CONTEXT_OWNER_ID", "").strip()
    if not owner_id:
        raise RuntimeError("MY_AGENT_CONTEXT_OWNER_ID is not configured")
    result = _call(
        "read_agent_context",
        {
            "p_owner_id": owner_id,
            "p_query": query,
            "p_secret": os.environ["MY_AGENT_CONTEXT_SECRET"],
        },
    )
    print(json.dumps({"source": "my-agent", "records": result}, ensure_ascii=False))
    return 0


def write(scope: str, key: str, content: str, source: str) -> int:
    owner_id = os.getenv("MY_AGENT_CONTEXT_OWNER_ID", "").strip()
    if not owner_id:
        raise RuntimeError("MY_AGENT_CONTEXT_OWNER_ID is not configured")
    result = _call(
        "write_agent_context",
        {
            "p_owner_id": owner_id,
            "p_scope": scope,
            "p_record_key": key,
            "p_content": content,
            "p_source": source,
            "p_secret": os.environ["MY_AGENT_CONTEXT_SECRET"],
        },
    )
    print(json.dumps({"source": "my-agent", "saved": result}, ensure_ascii=False))
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "write":
        if len(sys.argv) != 6:
            raise SystemExit("usage: my-agent-context.py write <scope> <key> <content> <source>")
        return write(*sys.argv[2:])
    query = " ".join(sys.argv[1:]).strip()
    return read(query)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"context bridge unavailable: {exc}", file=sys.stderr)
        raise SystemExit(1)
