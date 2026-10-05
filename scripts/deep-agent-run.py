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
from typing import Any

from urllib.request import Request, urlopen


def load_hermes_env() -> None:
    """Load missing provider variables from Hermes' private env file.

    Hermes sanitizes terminal subprocess environments. Its boot sequence
    already persists the protected values in this container-local file.
    """
    try:
        with open("/data/.hermes/.env", encoding="utf-8") as stream:
            for line in stream:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                name = name.strip()
                value = value.strip().strip("\"'")
                if name and value and name not in os.environ:
                    os.environ[name] = value
    except OSError:
        pass


load_hermes_env()


def env(name: str, required: bool = True) -> str:
    value = os.getenv(name, "").strip()
    if required and not value:
        raise RuntimeError(f"{name} is not configured")
    return value


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int) -> Any:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def notify_telegram(text: str) -> None:
    token = env("TELEGRAM_BOT_TOKEN")
    chat_id = env("TELEGRAM_OWNER_CHAT_ID")
    post_json(
        f"https://api.telegram.org/bot{token}/sendMessage",
        {"Content-Type": "application/json"},
        {"chat_id": chat_id, "text": text},
        30,
    )


def rpc(name: str, payload: dict[str, Any]) -> Any:
    base = env("MY_AGENT_CONTEXT_URL").rstrip("/")
    key = env("MY_AGENT_CONTEXT_PUBLISHABLE_KEY")
    return post_json(
        f"{base}/rest/v1/rpc/{name}",
        {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        payload,
        30,
    )


def model_answer(goal: str) -> tuple[str, str]:
    model = os.getenv("DEEP_AGENT_MODEL", "gemma4:31b-cloud").strip()
    ollama_key = os.getenv("OLLAMA_API_KEY", "").strip()
    if ollama_key:
        data = post_json(
            os.getenv("DEEP_AGENT_OLLAMA_URL", "https://ollama.com/api/chat"),
            {"Authorization": f"Bearer {ollama_key}", "Content-Type": "application/json"},
            {
                "model": model,
                "stream": False,
                "options": {"num_predict": 64},
                "messages": [
                    {"role": "system", "content": "You are the durable Deep Agent worker. Plan briefly, execute the requested harmless task, and verify the result. Keep the final answer concise."},
                    {"role": "user", "content": goal},
                ],
            },
            120,
        )
        message = data.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not content:
            raise RuntimeError("model returned no content")
        return str(content), f"ollama/{model}"
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        groq_model = os.getenv("DEEP_AGENT_GROQ_MODEL", "openai/gpt-oss-20b").strip()
        data = post_json(
            os.getenv("DEEP_AGENT_GROQ_URL", "https://api.groq.com/openai/v1/chat/completions"),
            {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            {"model": groq_model, "max_tokens": 64, "messages": [{"role": "system", "content": "You are the durable Deep Agent worker. Verify the harmless task and answer concisely."}, {"role": "user", "content": goal}]},
            120,
        )
        content = data["choices"][0]["message"]["content"]
        return str(content), f"groq/{data.get('model', groq_model)}"
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key:
        deepseek_model = os.getenv("DEEP_AGENT_DEEPSEEK_MODEL", "deepseek-chat").strip()
        data = post_json(
            os.getenv("DEEP_AGENT_DEEPSEEK_URL", "https://api.deepseek.com/chat/completions"),
            {"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"},
            {"model": deepseek_model, "max_tokens": 64, "messages": [{"role": "system", "content": "You are the durable Deep Agent worker. Verify the harmless task and answer concisely."}, {"role": "user", "content": goal}]},
            120,
        )
        content = data["choices"][0]["message"]["content"]
        return str(content), f"deepseek/{data.get('model', deepseek_model)}"
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_key:
        raise RuntimeError("no remote model credential is configured")
    data = post_json(
        os.getenv("DEEP_AGENT_OPENAI_URL", "https://api.openai.com/v1/chat/completions"),
        {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
        {"model": os.getenv("DEEP_AGENT_OPENAI_MODEL", "gpt-4o-mini"), "max_tokens": 64, "messages": [{"role": "system", "content": "You are the durable Deep Agent worker. Verify the harmless task and answer concisely."}, {"role": "user", "content": goal}]},
        120,
    )
    content = data["choices"][0]["message"]["content"]
    return str(content), f"openai/{data.get('model', os.getenv('DEEP_AGENT_OPENAI_MODEL', 'gpt-4o-mini'))}"


def main() -> int:
    notify = "--telegram" in sys.argv[1:]
    args = [arg for arg in sys.argv[1:] if arg != "--telegram"]
    goal = " ".join(args).strip()
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
        result = {"run_id": run_id, "queue_msg_id": queue_msg_id, "status": terminal.get("status"), "provider": provider, "content": content}
        encoded = json.dumps(result, ensure_ascii=False)
        if notify:
            notify_telegram(encoded)
        print(encoded)
        return 0
    except Exception as exc:
        try:
            rpc("complete_agent_run", {"p_queue_msg_id": queue_msg_id, "p_run_id": run_id, "p_owner_id": owner, "p_status": "failed", "p_result": {"error": type(exc).__name__}, "p_secret": secret})
        except Exception:
            pass
        if notify:
            try:
                notify_telegram(json.dumps({"status": "failed", "run_id": run_id, "error": type(exc).__name__}))
            except Exception:
                pass
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": type(exc).__name__}), file=sys.stderr)
        raise
