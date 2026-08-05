from __future__ import annotations

import json
from pathlib import Path

from plugin_forge.adapters import render_all, render_for_provider
from plugin_forge.spec import ForgeSpec, Provider


def test_claude_manifest_shape(sample_spec: ForgeSpec) -> None:
    out = render_for_provider(sample_spec, Provider.CLAUDE)
    assert out["name"] == "demo"
    assert out["version"] == "0.3.1"
    assert out["skills"] == "./skills"
    assert out["mcpServers"] == "./.mcp.json"
    assert out["license"] == "MIT"


def test_codex_includes_interface(sample_spec: ForgeSpec) -> None:
    out = render_for_provider(sample_spec, Provider.CODEX)
    assert "interface" in out
    assert out["interface"]["displayName"] == "Demo"
    assert out["mcpServers"] == "./.codex-mcp.json"


def test_codex_interface_supports_visuals_and_prompt_list(sample_spec: ForgeSpec) -> None:
    sample_spec.metadata["interface"] = {
        "default_prompt": "Use Demo.",
        "brand_color": "#123456",
        "composer_icon": "./assets/icon.png",
        "logo": "./assets/logo.png",
        "screenshots": ["./assets/screenshot-1.png"],
    }
    out = render_for_provider(sample_spec, Provider.CODEX)
    assert out["interface"]["defaultPrompt"] == ["Use Demo."]
    assert out["interface"]["brandColor"] == "#123456"
    assert out["interface"]["composerIcon"] == "./assets/icon.png"
    assert out["interface"]["logo"] == "./assets/logo.png"
    assert out["interface"]["screenshots"] == ["./assets/screenshot-1.png"]


def test_kimi_inlines_mcp(sample_spec: ForgeSpec) -> None:
    out = render_for_provider(sample_spec, Provider.KIMI)
    assert isinstance(out["mcpServers"], dict)
    assert "demo" in out["mcpServers"]
    assert out["mcpServers"]["demo"]["command"] == "cmd.exe"
    assert out["mcpServers"]["demo"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\kimi-uv-mcp.cmd",
        "-m",
        "demo.mcp_server",
    ]
    assert "--with-editable" not in out["mcpServers"]["demo"]["args"]


def test_claude_mcp_is_anchored_to_plugin_root(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    """Claude Code spawns plugin MCP servers with the session cwd, not the plugin
    dir, so a relative `--project .` resolves into the user's repo and the server
    dies with ModuleNotFoundError. Every path must go through ${CLAUDE_PLUGIN_ROOT}."""
    render_all(sample_spec, tmp_path)
    entry = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["demo"]
    assert entry["cwd"] == "${CLAUDE_PLUGIN_ROOT}"
    assert entry["args"][:3] == ["run", "--project", "${CLAUDE_PLUGIN_ROOT}"]
    assert "." not in entry["args"]


def test_codex_mcp_keeps_relative_paths(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    """Codex resolves relative paths against the plugin root already; keep its
    output unchanged so the Claude fix cannot regress Codex."""
    render_all(sample_spec, tmp_path)
    entry = json.loads((tmp_path / ".codex-mcp.json").read_text(encoding="utf-8"))["mcpServers"]["demo"]
    assert entry["cwd"] == "./"
    assert entry["args"][:3] == ["run", "--project", "."]
    assert "${CLAUDE_PLUGIN_ROOT}" not in json.dumps(entry)


def test_render_all_writes_files(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    written = render_all(sample_spec, tmp_path)
    assert (tmp_path / ".claude-plugin" / "plugin.json").exists()
    assert (tmp_path / ".codex-plugin" / "plugin.json").exists()
    assert (tmp_path / "kimi.plugin.json").exists()
    assert (tmp_path / ".mcp.json").exists()
    assert (tmp_path / ".codex-mcp.json").exists()
    launcher = tmp_path / "scripts" / "kimi-uv-mcp.cmd"
    assert launcher.exists()
    content = launcher.read_text(encoding="utf-8")
    assert "%USERPROFILE%\\.local\\bin\\uv.exe" in content
    assert '"%UV_EXE%" run --project "%~dp0.." python %*' in content
    assert Provider.CLAUDE in written
