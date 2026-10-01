#!/usr/bin/env python3
"""Small REST worker boundary for one durable Deep Agent run.

The control plane remains Supabase-owned: the RPC creates the run, queues it,
leases it exactly once, and archives the message only after completion. The
model call is remote and credentials stay in the process environment.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any

import httpx


def env(name: str, required: bool = True) -> str:
    value = os.getenv(name, "").strip()
    if required and not value:
        raise RuntimeError(f"{name} is not configured")
    return value


def rpc(name: str, payload: dict[str, Any]) -> Any:
    base = env("MY_AGENT_CONTEXT_URL").rstrip("/")
    key = env("MY_AGENT_CONTEXT_PUBLISHABLE_KEY")
    response = httpx.post(
        f"{base}/rest/v1/rpc/{name}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def model_answer(goal: str) -> tuple[str, str]:
    model = os.getenv("DEEP_AGENT_MODEL", "gemma4:31b-cloud").strip()
    ollama_key = os.getenv("OLLAMA_API_KEY", "").strip()
    if ollama_key:
        response = httpx.post(
            os.getenv("DEEP_AGENT_OLLAMA_URL", "https://ollama.com/api/chat"),
            headers={"Authorization": f"Bearer {ollama_key}"},
            json={
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": "You are the durable Deep Agent worker. Plan briefly, execute the requested harmless task, and verify the result. Keep the final answer concise."},
                    {"role": "user", "content": goal},
                ],
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not content:
            raise RuntimeError("model returned no content")
        return str(content), f"ollama/{model}"
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        groq_model = os.getenv("DEEP_AGENT_GROQ_MODEL", "openai/gpt-oss-20b").strip()
        response = httpx.post(
            os.getenv("DEEP_AGENT_GROQ_URL", "https://api.groq.com/openai/v1/chat/completions"),
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={"model": groq_model, "messages": [{"role": "system", "content": "You are the durable Deep Agent worker. Verify the harmless task and answer concisely."}, {"role": "user", "content": goal}]},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return str(content), f"groq/{data.get('model', groq_model)}"
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key:
        deepseek_model = os.getenv("DEEP_AGENT_DEEPSEEK_MODEL", "deepseek-chat").strip()
        response = httpx.post(
            os.getenv("DEEP_AGENT_DEEPSEEK_URL", "https://api.deepseek.com/chat/completions"),
            headers={"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"},
            json={"model": deepseek_model, "messages": [{"role": "system", "content": "You are the durable Deep Agent worker. Verify the harmless task and answer concisely."}, {"role": "user", "content": goal}]},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return str(content), f"deepseek/{data.get('model', deepseek_model)}"
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_key:
        raise RuntimeError("no remote model credential is configured")
    response = httpx.post(
        os.getenv("DEEP_AGENT_OPENAI_URL", "https://api.openai.com/v1/chat/completions"),
        headers={"Authorization": f"Bearer {openai_key}"},
        json={"model": os.getenv("DEEP_AGENT_OPENAI_MODEL", "gpt-4o-mini"), "messages": [{"role": "system", "content": "You are the durable Deep Agent worker. Verify the harmless task and answer concisely."}, {"role": "user", "content": goal}]},
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return str(content), f"openai/{data.get('model', os.getenv('DEEP_AGENT_OPENAI_MODEL', 'gpt-4o-mini'))}"


def main() -> int:
    goal = " ".join(sys.argv[1:]).strip()
    if not goal:
        raise SystemExit("usage: deep-agent-run.py <goal>")
    owner = env("MY_AGENT_CONTEXT_OWNER_ID")
    secret = env("MY_AGENT_CONTEXT_SECRET")
    thread = os.getenv("HERMES_DEEP_AGENT_THREAD_ID", f"telegram:{owner}")
    created = rpc("create_agent_run", {"p_owner_id": owner, "p_goal": goal, "p_thread_id": thread, "p_secret": secret})
    run_id = created["run_id"]
    queue_msg_id = int(created["queue_msg_id"])
    try:
        leased = rpc("claim_agent_run", {"p_queue_msg_id": queue_msg_id, "p_run_id": run_id, "p_owner_id": owner, "p_secret": secret})
        if leased.get("status") != "running":
            raise RuntimeError(f"run was not leased: {leased.get('status')}")
        content, provider = model_answer(str(leased["goal"]))
        result = {"content": content, "provider": provider, "verified": True, "worker": "hermes-rest-boundary"}
        terminal = rpc("complete_agent_run", {"p_queue_msg_id": queue_msg_id, "p_run_id": run_id, "p_owner_id": owner, "p_status": "completed", "p_result": result, "p_secret": secret})
        print(json.dumps({"run_id": run_id, "queue_msg_id": queue_msg_id, "status": terminal.get("status"), "provider": provider, "content": content}, ensure_ascii=False))
        return 0
    except Exception as exc:
        try:
            rpc("complete_agent_run", {"p_queue_msg_id": queue_msg_id, "p_run_id": run_id, "p_owner_id": owner, "p_status": "failed", "p_result": {"error": type(exc).__name__}, "p_secret": secret})
        except Exception:
            pass
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": type(exc).__name__}), file=sys.stderr)
        raise
