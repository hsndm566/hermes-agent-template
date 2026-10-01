from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


def _module():
    path = Path(__file__).parent / "scripts" / "configure-connectors.py"
    spec = importlib.util.spec_from_file_location("configure_connectors", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configure_is_scoped_and_secret_free(tmp_path, monkeypatch):
    module = _module()
    config = tmp_path / "config.yaml"
    config.write_text("mcp_servers:\n  custom:\n    url: https://example.invalid\n", encoding="utf-8")
    monkeypatch.setattr(module, "CONFIG", config)
    monkeypatch.setenv("MCP_GITHUB_API_KEY", "test-github-secret")
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "test-supabase-secret")
    monkeypatch.setenv("SUPABASE_PROJECT_REF", "ufyvelnxexjvlibhweau")
    monkeypatch.setenv("GOOGLE_WORKSPACE_MCP_ENABLED", "1")
    monkeypatch.delenv("HEROKU_API_KEY", raising=False)

    configured = module.configure()
    result = yaml.safe_load(config.read_text(encoding="utf-8"))
    text = config.read_text(encoding="utf-8")

    assert {"github", "supabase", "clerk", "gmail", "google-drive"}.issubset(configured)
    assert result["mcp_servers"]["supabase"]["url"].endswith(
        "project_ref=ufyvelnxexjvlibhweau&features=docs%2Caccount%2Cdatabase%2Cdebugging%2Cdevelopment%2Cfunctions%2Cbranching"
    )
    assert result["mcp_servers"]["github"]["headers"]["Authorization"] == "Bearer ${MCP_GITHUB_API_KEY}"
    assert "test-github-secret" not in text
    assert "test-supabase-secret" not in text
    assert result["mcp_servers"]["custom"]["url"] == "https://example.invalid"


def test_uncredentialed_servers_are_removed(tmp_path, monkeypatch):
    module = _module()
    config = tmp_path / "config.yaml"
    config.write_text(
        "mcp_servers:\n  github: {enabled: true}\n  supabase: {enabled: true}\n  heroku: {enabled: true}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "CONFIG", config)
    for key in (
        "MCP_GITHUB_API_KEY",
        "SUPABASE_ACCESS_TOKEN",
        "SUPABASE_PROJECT_REF",
        "HEROKU_API_KEY",
        "GOOGLE_WORKSPACE_MCP_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)

    module.configure()
    servers = yaml.safe_load(config.read_text(encoding="utf-8"))["mcp_servers"]
    assert "github" not in servers
    assert "supabase" not in servers
    assert "heroku" not in servers
    assert servers["clerk"]["url"] == "https://mcp.clerk.com/mcp"
