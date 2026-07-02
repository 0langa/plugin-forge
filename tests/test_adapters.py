from __future__ import annotations

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


def test_kimi_inlines_mcp(sample_spec: ForgeSpec) -> None:
    out = render_for_provider(sample_spec, Provider.KIMI)
    assert isinstance(out["mcpServers"], dict)
    assert "demo" in out["mcpServers"]
    assert out["mcpServers"]["demo"]["command"] == "uv"


def test_render_all_writes_files(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    written = render_all(sample_spec, tmp_path)
    assert (tmp_path / ".claude-plugin" / "plugin.json").exists()
    assert (tmp_path / ".codex-plugin" / "plugin.json").exists()
    assert (tmp_path / "kimi.plugin.json").exists()
    assert (tmp_path / ".mcp.json").exists()
    assert (tmp_path / ".codex-mcp.json").exists()
    assert Provider.CLAUDE in written
