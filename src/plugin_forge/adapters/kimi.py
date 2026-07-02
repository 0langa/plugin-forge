"""Kimi Code plugin manifest.

Layout:
    kimi.plugin.json    (root — inline `interface`, `sessionStart`,
                         `skillInstructions`, inline `mcpServers`, inline `hooks`)

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


def render_kimi(spec: ForgeSpec) -> dict[str, Any]:
    payload = base_header(spec)
    active = spec.surfaces_for_provider(Provider.KIMI)
    if active.skills:
        payload["skills"] = "./skills/"
    if active.commands:
        payload["commands"] = "./commands/"
    if active.agents:
        payload["agents"] = "./agents/"

    iface = _interface(spec)
    if iface:
        payload["interface"] = iface

    meta = spec.metadata if isinstance(spec.metadata, dict) else {}
    session_start = meta.get("session_start_skill")
    if session_start:
        payload["sessionStart"] = {"skill": session_start}
    skill_instructions = meta.get("skill_instructions")
    if skill_instructions:
        payload["skillInstructions"] = skill_instructions

    servers = render_mcp_servers(spec, Provider.KIMI)
    if servers:
        payload["mcpServers"] = servers

    hook_entries = render_hook_entries(spec, Provider.KIMI)
    if hook_entries:
        payload["hooks"] = hook_entries

    payload.update(spec.provider_extras.for_provider(Provider.KIMI))
    return payload


def _interface(spec: ForgeSpec) -> dict[str, Any]:
    meta = spec.metadata.get("interface", {}) if isinstance(spec.metadata, dict) else {}
    if not spec.description and not meta:
        return {}
    iface: dict[str, Any] = {
        "displayName": meta.get("display_name", _title(spec.name)),
        "shortDescription": meta.get("short_description", spec.description or spec.name),
        "longDescription": meta.get("long_description", spec.description or spec.name),
        "developerName": meta.get("developer_name", spec.metadata.get("author", "0langa")),
    }
    if "website_url" in meta or "homepage" in spec.metadata:
        iface["websiteURL"] = meta.get("website_url", spec.metadata.get("homepage"))
    if "brand_color" in meta:
        iface["brandColor"] = meta["brand_color"]
    return iface


def _title(name: str) -> str:
    return " ".join(part.capitalize() for part in name.replace("_", "-").split("-"))


def write_kimi(spec: ForgeSpec, out_root: Path) -> Path:
    path = out_root / "kimi.plugin.json"
    write_json(path, render_kimi(spec))
    return path
