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
