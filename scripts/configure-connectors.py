#!/usr/bin/env python3
"""Build Hermes' persistent MCP connector configuration from env references.

Secrets are never written to config.yaml. The Hermes runtime resolves the
``${ENV_NAME}`` references when it opens a connector. Connectors that require
credentials are omitted until their credential is present, which keeps a
partial deployment from repeatedly attempting unauthenticated connections.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

import yaml


HOME = Path(os.environ.get("HERMES_HOME", "/data/.hermes"))
CONFIG = HOME / "config.yaml"


def _load() -> dict:
    try:
        value = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        value = {}
    return value if isinstance(value, dict) else {}


def _headers(existing: object, env_name: str) -> dict[str, str]:
    result = dict(existing) if isinstance(existing, dict) else {}
    result["Authorization"] = f"Bearer ${{{env_name}}}"
    return result


def _optional_server(
    servers: dict,
    configured: list[str],
    *,
    name: str,
    url_env: str,
    token_env: str | None = None,
) -> None:
    """Register an owner-supplied MCP endpoint without inventing its URL."""
    url = os.getenv(url_env)
    if not url:
        servers.pop(name, None)
        return
    entry: dict[str, object] = {"url": url, "enabled": True}
    if token_env and os.getenv(token_env):
        entry["headers"] = _headers(None, token_env)
    servers[name] = entry
    configured.append(name)


def configure() -> list[str]:
    data = _load()
    servers = data.setdefault("mcp_servers", {})
    if not isinstance(servers, dict):
        servers = {}
        data["mcp_servers"] = servers

    configured: list[str] = []

    # GitHub's hosted server supports both OAuth and PAT auth. Northflank uses
    # a secret reference; GITHUB_TOKEN is promoted to this name in start.sh.
    github_key = os.getenv("MCP_GITHUB_API_KEY")
    github_oauth = os.getenv("MCP_GITHUB_MCP_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
    if github_key or github_oauth:
        existing = servers.get("github") if isinstance(servers.get("github"), dict) else {}
        entry = {
            **existing,
            "url": "https://api.githubcopilot.com/mcp/",
            "enabled": True,
        }
        if github_key:
            entry["headers"] = _headers(existing.get("headers"), "MCP_GITHUB_API_KEY")
        servers["github"] = entry
        configured.append("github")
    else:
        servers.pop("github", None)

    # Supabase's hosted MCP endpoint is scoped to one project. Do not fall
    # back to an unscoped URL: that would grant access to every project.
    supabase_token = os.getenv("SUPABASE_ACCESS_TOKEN")
    project_ref = os.getenv("SUPABASE_PROJECT_REF")
    supabase_oauth = os.getenv("SUPABASE_MCP_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
    if project_ref and (supabase_token or supabase_oauth):
        features = os.getenv(
            "SUPABASE_MCP_FEATURES",
            "docs,account,database,debugging,development,functions,branching",
        )
        query = urlencode({"project_ref": project_ref, "features": features})
        existing = servers.get("supabase") if isinstance(servers.get("supabase"), dict) else {}
        entry = {
            **existing,
            "url": f"https://mcp.supabase.com/mcp?{query}",
            "enabled": True,
        }
        if supabase_token:
            entry["headers"] = _headers(existing.get("headers"), "SUPABASE_ACCESS_TOKEN")
        servers["supabase"] = entry
        configured.append("supabase")
    else:
        servers.pop("supabase", None)

    # Clerk's official server provides current SDK and MCP implementation
    # guidance and intentionally needs no secret.
    servers["clerk"] = {
        "url": "https://mcp.clerk.com/mcp",
        "enabled": True,
    }
    configured.append("clerk")

    # Google Workspace and other private MCP servers can be supplied by the
    # owner without changing the image. The token remains an env reference.
    workspace_url = os.getenv("GOOGLE_WORKSPACE_MCP_URL")
    if workspace_url:
        entry = {"url": workspace_url, "enabled": True}
        if os.getenv("GOOGLE_WORKSPACE_MCP_TOKEN"):
            entry["headers"] = {"Authorization": "Bearer ${GOOGLE_WORKSPACE_MCP_TOKEN}"}
        servers["google-workspace"] = entry
        configured.append("google-workspace")
    else:
        servers.pop("google-workspace", None)

    # Google's first-party Workspace MCP servers use OAuth. Enabling this flag
    # makes Hermes expose the endpoints in its dashboard so the owner can
    # authorize them once; no Google refresh token is stored in this image.
    if os.getenv("GOOGLE_WORKSPACE_MCP_ENABLED", "0").lower() in {"1", "true", "yes", "on"}:
        google_endpoints = {
            "gmail": "https://gmailmcp.googleapis.com/mcp/v1",
            "google-drive": "https://drivemcp.googleapis.com/mcp/v1",
            "google-calendar": "https://calendar-mcp.googleapis.com/mcp/v1",
            "google-contacts": "https://peoplemcp.googleapis.com/mcp/v1",
        }
        for name, url in google_endpoints.items():
            servers[name] = {"url": url, "enabled": True}
            configured.append(name)
    else:
        for name in ("gmail", "google-drive", "google-calendar", "google-contacts"):
            servers.pop(name, None)

    # Heroku now provides an official OAuth-protected remote MCP endpoint. An
    # API key can be used for non-interactive service deployments; otherwise
    # the owner can enable it and complete OAuth from Hermes' dashboard.
    if os.getenv("HEROKU_API_KEY") or os.getenv("HEROKU_MCP_ENABLED", "0").lower() in {"1", "true", "yes", "on"}:
        entry = {"url": "https://mcp.heroku.com/mcp", "enabled": True}
        if os.getenv("HEROKU_API_KEY"):
            entry["headers"] = {"Authorization": "Bearer ${HEROKU_API_KEY}"}
        servers["heroku"] = entry
        configured.append("heroku")
    else:
        servers.pop("heroku", None)

    # These services expose either a user-specific MCP endpoint or a local /
    # self-hosted server. The URL is deliberately supplied by the owner so a
    # typo or third-party endpoint cannot be silently trusted by the image.
    for name, url_env, token_env in (
        ("notion", "NOTION_MCP_URL", "NOTION_MCP_TOKEN"),
        ("cloudflare", "CLOUDFLARE_MCP_URL", "CLOUDFLARE_API_TOKEN"),
        ("resend", "RESEND_MCP_URL", "RESEND_API_KEY"),
        ("firecrawl", "FIRECRAWL_MCP_URL", "FIRECRAWL_API_KEY"),
        ("playwright", "PLAYWRIGHT_MCP_URL", None),
        ("n8n", "N8N_MCP_URL", "N8N_API_KEY"),
    ):
        _optional_server(servers, configured, name=name, url_env=url_env, token_env=token_env)

    # Official OAuth endpoints can be advertised without a token. The owner
    # still authorizes them from Hermes before private data is available.
    oauth_endpoints = {
        "notion": ("https://mcp.notion.com/mcp", "NOTION_MCP_ENABLED"),
        "cloudflare": ("https://mcp.cloudflare.com/mcp?codemode=false", "CLOUDFLARE_MCP_ENABLED"),
    }
    for name, (url, flag) in oauth_endpoints.items():
        if os.getenv(flag, "0").lower() in {"1", "true", "yes", "on"} and name not in servers:
            servers[name] = {"url": url, "enabled": True}
            configured.append(name)

    # Vercel publishes an official OAuth-protected remote MCP server. It is
    # opt-in because authorization is interactive and account-scoped.
    if os.getenv("VERCEL_MCP_ENABLED", "0").lower() in {"1", "true", "yes", "on"}:
        servers["vercel"] = {"url": "https://mcp.vercel.com", "enabled": True}
        configured.append("vercel")
    else:
        servers.pop("vercel", None)

    # These providers have APIs but no official hosted MCP endpoint. Keep a
    # declarative inventory for the platform-connectors skill; it contains only
    # endpoint names and env variable names, never credentials.
    data["platform_connectors"] = {
        "northflank": {
            "base_url": "https://api.northflank.com/v1",
            "token_env": "NORTHFLANK_API_TOKEN",
        },
        "heroku": {
            "base_url": "https://api.heroku.com",
            "token_env": "HEROKU_API_KEY",
        },
        "clerk_api": {
            "base_url": "https://api.clerk.com/v1",
            "token_env": "CLERK_SECRET_KEY",
        },
        "github": {
            "base_url": "https://api.github.com",
            "token_env": "MCP_GITHUB_API_KEY",
        },
        "supabase": {
            "base_url": "https://mcp.supabase.com/mcp",
            "token_env": "SUPABASE_ACCESS_TOKEN",
            "project_ref_env": "SUPABASE_PROJECT_REF",
        },
        "vercel": {
            "base_url": "https://mcp.vercel.com",
            "auth": "oauth",
        },
        "google_workspace": {
            "auth": "oauth",
            "endpoints": ["gmail", "drive", "calendar", "contacts"],
        },
    }

    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return configured


if __name__ == "__main__":
    print("[connectors] configured=" + ",".join(configure()), flush=True)
