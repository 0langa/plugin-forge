"""Shared helpers for provider manifest adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plugin_forge.spec import ForgeSpec, McpSurface, Provider


def base_header(spec: ForgeSpec) -> dict[str, Any]:
    """Fields common to every provider manifest."""
    header: dict[str, Any] = {
        "name": spec.name,
        "version": spec.version,
    }
    if spec.description:
        header["description"] = spec.description
    header["author"] = {"name": spec.metadata.get("author", "0langa")}
    if "homepage" in spec.metadata:
        header["homepage"] = spec.metadata["homepage"]
    if "repository" in spec.metadata:
        header["repository"] = spec.metadata["repository"]
    header["license"] = spec.metadata.get("license", "MIT")
    if "keywords" in spec.metadata:
        header["keywords"] = spec.metadata["keywords"]
    return header


def render_mcp_entry(m: McpSurface) -> dict[str, Any]:
    """Render an McpSurface into the `mcpServers` entry shape used across providers."""
    if m.package.startswith("python:"):
        module_path = m.package.removeprefix("python:")
        entry: dict[str, Any] = {
            "command": "uv",
            "args": ["run", "python", module_path, *m.args],
            "cwd": "./",
        }
    elif m.package.startswith("module:"):
        module = m.package.removeprefix("module:")
        entry = {
            "command": "uv",
            "args": ["run", "python", "-m", module, *m.args],
            "cwd": "./",
        }
    elif m.package.startswith("node:"):
        script = m.package.removeprefix("node:")
        entry = {"command": "node", "args": [script, *m.args], "cwd": "./"}
    else:
        entry = {"command": m.package, "args": list(m.args), "cwd": "./"}
    if m.env:
        entry["env"] = {k: f"${{{k}}}" for k in m.env}
    return entry


def render_mcp_servers(spec: ForgeSpec, provider: Provider) -> dict[str, Any]:
    active = spec.surfaces_for_provider(provider).mcp
    return {m.name: render_mcp_entry(m) for m in active}


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def render_hook_command(script: str, provider: Provider) -> str:
    """Render a script-path hook into the inline shell command shape hosts expect.

    Uses `py -3` on Windows-friendly path; each provider passes a plugin-root
    env var that lets the hook resolve its own source at runtime.
    """
    root_expr = {
        Provider.CLAUDE: "os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('PLUGIN_ROOT')",
        Provider.CODEX: "os.environ.get('PLUGIN_ROOT') or os.environ.get('CLAUDE_PLUGIN_ROOT')",
        Provider.KIMI: "os.environ.get('KIMI_PLUGIN_ROOT')",
    }[provider]
    script_norm = script.replace("\\", "/")
    return (
        "py -3 -c \"import os,runpy,sys; "
        f"root={root_expr} or os.getcwd(); "
        "sys.path.insert(0, os.path.join(root,'src')); "
        f"runpy.run_path(os.path.join(root, {script_norm!r}), run_name='__main__')\""
    )


def render_hook_entries(spec: ForgeSpec, provider: Provider) -> list[dict[str, Any]]:
    """Render every hook active on `provider` into the standard entry shape:

        {"event": ..., "command": ..., "matcher"?, "timeout"?}
    """
    active = spec.surfaces_for_provider(provider).hooks
    entries: list[dict[str, Any]] = []
    for h in active:
        entry: dict[str, Any] = {"event": h.event}
        if h.command:
            entry["command"] = h.command
        else:
            entry["command"] = render_hook_command(h.script or "", provider)
        if h.matcher:
            entry["matcher"] = h.matcher
        if h.timeout_seconds:
            entry["timeout"] = h.timeout_seconds
        entries.append(entry)
    return entries


def render_hooks_config(spec: ForgeSpec, provider: Provider) -> dict[str, Any]:
    """Render Claude/Codex plugin hook sidecar shape.

    Kimi uses flat inline hook entries. Claude and Codex use the nested
    lifecycle config shape under a top-level `hooks` object.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in render_hook_entries(spec, provider):
        event = str(entry["event"])
        command_hook: dict[str, Any] = {
            "type": "command",
            "command": entry["command"],
        }
        if "timeout" in entry:
            command_hook["timeout"] = entry["timeout"]
        matcher_entry: dict[str, Any] = {"hooks": [command_hook]}
        if "matcher" in entry:
            matcher_entry["matcher"] = entry["matcher"]
        grouped.setdefault(event, []).append(matcher_entry)
    return {"hooks": grouped} if grouped else {}
