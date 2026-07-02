"""Claude Code plugin manifest.

Layout:
    .claude-plugin/plugin.json    (thin — points at ./skills, ./commands, ./.mcp.json, ./hooks/hooks.json)
    .mcp.json                     (mcpServers block, sibling of .claude-plugin)
    hooks/hooks.json              (hook wiring, sibling of .claude-plugin)

If `spec.options.shared_mcp_file` is set, a single `.mcp.json` is written and
also referenced by the Codex adapter. Provider-specific manifest keys not
modelled by forge are read from `spec.provider_extras.claude` and merged into
the output verbatim.

Shape verified against `0langas-plugin-marketplace/plugins/agent-handoff` and
`usage-pulse` (2026-07).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plugin_forge.spec import ForgeSpec, Provider

from ._common import (
    base_header,
    render_hook_entries,
    render_mcp_servers,
    write_json,
)


def render_claude(spec: ForgeSpec) -> dict[str, Any]:
    payload = base_header(spec)
    active = spec.surfaces_for_provider(Provider.CLAUDE)
    if active.skills:
        payload["skills"] = "./skills"
    if active.commands:
        payload["commands"] = "./commands"
    if active.agents:
        payload["agents"] = "./agents"
    if active.mcp:
        payload["mcpServers"] = "./.mcp.json"
    if active.hooks:
        payload["hooks"] = "./hooks/hooks.json"
    payload.update(spec.provider_extras.for_provider(Provider.CLAUDE))
    return payload


def render_claude_mcp(spec: ForgeSpec) -> dict[str, Any]:
    servers = render_mcp_servers(spec, Provider.CLAUDE)
    return {"mcpServers": servers} if servers else {}


def render_claude_hooks(spec: ForgeSpec) -> dict[str, Any]:
    entries = render_hook_entries(spec, Provider.CLAUDE)
    return {"hooks": entries} if entries else {}


def write_claude(spec: ForgeSpec, out_root: Path) -> Path:
    plugin_path = out_root / ".claude-plugin" / "plugin.json"
    write_json(plugin_path, render_claude(spec))

    mcp = render_claude_mcp(spec)
    if mcp:
        write_json(out_root / ".mcp.json", mcp)

    hooks = render_claude_hooks(spec)
    if hooks:
        write_json(out_root / "hooks" / "hooks.json", hooks)

    return plugin_path
