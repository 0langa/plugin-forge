from __future__ import annotations

import json
from pathlib import Path

from plugin_forge.adapters import render_all
from plugin_forge.spec import (
    ForgeSpec,
    HookSurface,
    InstallTargets,
    McpSurface,
    Provider,
    SkillSurface,
    Surfaces,
)


def _spec_with_hooks() -> ForgeSpec:
    return ForgeSpec(
        name="hooky",
        version="0.1.0",
        description="hook plugin",
        providers=[Provider.CLAUDE, Provider.CODEX, Provider.KIMI],
        surfaces=Surfaces(
            skills=[SkillSurface(name="s", path="skills/s/SKILL.md")],
            hooks=[
                HookSurface(event="SessionStart", script="hooks/session_start.py"),
                HookSurface(
                    event="PreToolUse",
                    script="hooks/pre_tool_use.py",
                    matcher=".*",
                    timeout_seconds=10,
                ),
                HookSurface(event="Stop", command="raw shell noop"),
            ],
            mcp=[McpSurface(name="hooky", package="module:hooky.mcp_server")],
        ),
        install=InstallTargets(
            claude="~/.claude/plugins/hooky/",
            codex="~/.codex/plugins/hooky/",
            kimi="~/.kimi-code/plugins/hooky/",
        ),
    )


def test_kimi_inlines_hooks(tmp_path: Path) -> None:
    spec = _spec_with_hooks()
    render_all(spec, tmp_path)
    kimi = json.loads((tmp_path / "kimi.plugin.json").read_text())
    assert isinstance(kimi["hooks"], list)
    events = [h["event"] for h in kimi["hooks"]]
    assert events == ["SessionStart", "PreToolUse", "Stop"]
    session_start_cmd = kimi["hooks"][0]["command"]
    assert "session_start.py" in session_start_cmd
    assert "KIMI_PLUGIN_ROOT" in session_start_cmd
    pre_tool = kimi["hooks"][1]
    assert pre_tool["matcher"] == ".*"
    assert pre_tool["timeout"] == 10
    raw = kimi["hooks"][2]
    assert raw["command"] == "raw shell noop"


def test_claude_hooks_sidecar(tmp_path: Path) -> None:
    spec = _spec_with_hooks()
    render_all(spec, tmp_path)
    plugin = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["hooks"] == "./hooks/hooks.json"
    sidecar = json.loads((tmp_path / "hooks" / "hooks.json").read_text())
    assert len(sidecar["hooks"]) == 3
    assert "CLAUDE_PLUGIN_ROOT" in sidecar["hooks"][0]["command"]


def test_codex_hooks_sidecar_reuses_claude_file(tmp_path: Path) -> None:
    spec = _spec_with_hooks()
    render_all(spec, tmp_path)
    plugin = json.loads((tmp_path / ".codex-plugin" / "plugin.json").read_text())
    assert plugin["hooks"] == "./hooks/hooks.json"
    sidecar_text = (tmp_path / "hooks" / "hooks.json").read_text()
    assert "CLAUDE_PLUGIN_ROOT" in sidecar_text
    assert "CODEX_PLUGIN_ROOT" not in sidecar_text


def test_shared_mcp_option(tmp_path: Path) -> None:
    spec = _spec_with_hooks()
    spec.options.shared_mcp_file = True
    render_all(spec, tmp_path)
    claude = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text())
    codex = json.loads((tmp_path / ".codex-plugin" / "plugin.json").read_text())
    assert claude["mcpServers"] == "./.mcp.json"
    assert codex["mcpServers"] == "./.mcp.json"
    assert (tmp_path / ".mcp.json").exists()
    assert not (tmp_path / ".codex-mcp.json").exists()


def test_provider_extras_roundtrip(tmp_path: Path) -> None:
    spec = _spec_with_hooks()
    spec.provider_extras.claude = {"defaultEnabled": True}
    spec.provider_extras.codex = {"brandColor": "#256D5A"}
    spec.provider_extras.kimi = {"customField": [1, 2, 3]}
    render_all(spec, tmp_path)
    claude = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text())
    codex = json.loads((tmp_path / ".codex-plugin" / "plugin.json").read_text())
    kimi = json.loads((tmp_path / "kimi.plugin.json").read_text())
    assert claude["defaultEnabled"] is True
    assert codex["brandColor"] == "#256D5A"
    assert kimi["customField"] == [1, 2, 3]
