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


def mcp_root(provider: Provider) -> str:
    """Root prefix an MCP launcher must use to locate its own plugin directory.

    Claude Code spawns plugin MCP servers with the *session* working directory,
    not the plugin directory, so relative paths resolve against the user's repo
    and the launcher fails. `${CLAUDE_PLUGIN_ROOT}` is expanded by the host and
    is the only portable anchor. Codex and Kimi resolve relative paths against
    the plugin root already, so they keep `.`.
    """
    return "${CLAUDE_PLUGIN_ROOT}" if provider is Provider.CLAUDE else "."


def render_mcp_entry(m: McpSurface, provider: Provider) -> dict[str, Any]:
    """Render an McpSurface into the `mcpServers` entry shape used across providers."""
    root = mcp_root(provider)
    cwd = root if provider is Provider.CLAUDE else "./"

    def under_root(rel: str) -> str:
        # Codex/Kimi keep the bare relative path they already resolve correctly.
        return f"{root}/{rel}" if provider is Provider.CLAUDE else rel

    if m.package.startswith("python:"):
        module_path = m.package.removeprefix("python:")
        entry: dict[str, Any] = {
            "command": "uv",
            "args": ["run", "python", under_root(module_path), *m.args],
            "cwd": cwd,
        }
    elif m.package.startswith("module:"):
        module = m.package.removeprefix("module:")
        entry = {
            "command": "uv",
            "args": ["run", "--project", root, "python", "-m", module, *m.args],
            "cwd": cwd,
        }
    elif m.package.startswith("node:"):
        script = m.package.removeprefix("node:")
        entry = {"command": "node", "args": [under_root(script), *m.args], "cwd": cwd}
    else:
        entry = {"command": m.package, "args": list(m.args), "cwd": cwd}
    if m.env:
        entry["env"] = {k: f"${{{k}}}" for k in m.env}
    return entry


def render_mcp_servers(spec: ForgeSpec, provider: Provider) -> dict[str, Any]:
    active = spec.surfaces_for_provider(provider).mcp
    return {m.name: render_mcp_entry(m, provider) for m in active}


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _render_args(args: list[str]) -> str:
    return "" if not args else " " + " ".join(json.dumps(arg) for arg in args)


def render_hook_command(
    script: str, provider: Provider, args: list[str] | None = None
) -> str:
    """Render a script-path hook into the inline shell command shape hosts expect.

    Claude receives a portable shell command. Kimi keeps its inline Python
    launcher because its manifest has no separate Windows-command field.
    """
    script_norm = script.replace("\\", "/")
    hook_args = list(args or [])
    if provider is Provider.CLAUDE:
        return (
            'root="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-$PWD}}"; '
            f'uv run --project "$root" python "$root/{script_norm}"'
            f"{_render_args(hook_args)}"
        )
    root_expr = {
        Provider.KIMI: "os.environ.get('KIMI_PLUGIN_ROOT')",
    }[provider]
    argv = ["plugin-hook", *hook_args]
    return (
        "py -3 -c \"import os,runpy,sys; "
        f"root={root_expr} or os.getcwd(); "
        f"sys.argv={argv!r}; "
        "sys.path.insert(0, os.path.join(root,'src')); "
        f"runpy.run_path(os.path.join(root, {script_norm!r}), run_name='__main__')\""
    )


def render_hook_command_windows(script: str, provider: Provider, args: list[str]) -> str:
    script_norm = script.replace("/", "\\")
    primary = "CLAUDE_PLUGIN_ROOT" if provider is Provider.CLAUDE else "PLUGIN_ROOT"
    secondary = "PLUGIN_ROOT" if provider is Provider.CLAUDE else "CLAUDE_PLUGIN_ROOT"
    return (
        f"$root = if ($env:{primary}) {{ $env:{primary} }} "
        f"elseif ($env:{secondary}) {{ $env:{secondary} }} "
        "else { (Get-Location).Path }; "
        f"uv run --project $root python (Join-Path $root '{script_norm}')"
        f"{_render_args(args)}"
    )


def render_codex_hook_commands(script: str, args: list[str]) -> dict[str, str]:
    script_norm = script.replace("\\", "/")
    return {
        "command": (
            'root="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$PWD}}"; '
            f'uv run --project "$root" python "$root/{script_norm}"{_render_args(args)}'
        ),
        "commandWindows": render_hook_command_windows(script, Provider.CODEX, args),
    }


def render_hook_entries(spec: ForgeSpec, provider: Provider) -> list[dict[str, Any]]:
    """Render every hook active on `provider` into the standard entry shape:

        {"event": ..., "command": ..., "matcher"?, "timeout"?}
    """
    active = spec.surfaces_for_provider(provider).hooks
    entries: list[dict[str, Any]] = []
    for h in active:
        hook_args = h.args.get(provider, [])
        entry: dict[str, Any] = {"event": h.event}
        if h.command:
            entry["command"] = h.command
        elif provider is Provider.CODEX:
            entry.update(render_codex_hook_commands(h.script or "", hook_args))
        else:
            entry["command"] = render_hook_command(h.script or "", provider, hook_args)
            if provider is Provider.CLAUDE:
                entry["commandWindows"] = render_hook_command_windows(
                    h.script or "", provider, hook_args
                )
        matcher = h.matchers.get(provider, h.matcher)
        if matcher:
            entry["matcher"] = matcher
        if h.status_message and provider is not Provider.KIMI:
            entry["statusMessage"] = h.status_message
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
        if "commandWindows" in entry:
            command_hook["commandWindows"] = entry["commandWindows"]
        if "statusMessage" in entry:
            command_hook["statusMessage"] = entry["statusMessage"]
        if "timeout" in entry:
            command_hook["timeout"] = entry["timeout"]
        matcher_entry: dict[str, Any] = {"hooks": [command_hook]}
        if "matcher" in entry:
            matcher_entry["matcher"] = entry["matcher"]
        grouped.setdefault(event, []).append(matcher_entry)
    return {"hooks": grouped} if grouped else {}
