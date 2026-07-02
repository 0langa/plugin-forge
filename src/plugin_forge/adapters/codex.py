"""Codex plugin manifest.

Layout:
    .codex-plugin/plugin.json     (rich — includes `interface` block)
    .codex-mcp.json               (mcpServers block, sibling of .codex-plugin)

Shape verified against `0langas-plugin-marketplace/plugins/agent-handoff` (2026-07).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plugin_forge.spec import ForgeSpec, Provider

from ._common import base_header, render_mcp_servers, write_json


def render_codex(spec: ForgeSpec) -> dict[str, Any]:
    payload = base_header(spec)
    active = spec.surfaces_for_provider(Provider.CODEX)
    if active.skills:
        payload["skills"] = "./skills/"
    if active.commands:
        payload["commands"] = "./commands/"
    if active.agents:
        payload["agents"] = "./agents/"

    iface = _interface(spec)
    if iface:
        payload["interface"] = iface

    if active.mcp:
        payload["mcpServers"] = "./.codex-mcp.json"
    return payload


def render_codex_mcp(spec: ForgeSpec) -> dict[str, Any]:
    servers = render_mcp_servers(spec, Provider.CODEX)
    return {"mcpServers": servers} if servers else {}


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
    if "category" in meta:
        iface["category"] = meta["category"]
    if "capabilities" in meta:
        iface["capabilities"] = meta["capabilities"]
    if "website_url" in meta or "homepage" in spec.metadata:
        iface["websiteURL"] = meta.get("website_url", spec.metadata.get("homepage"))
    if "privacy_policy_url" in meta:
        iface["privacyPolicyURL"] = meta["privacy_policy_url"]
    if "terms_of_service_url" in meta:
        iface["termsOfServiceURL"] = meta["terms_of_service_url"]
    if "default_prompt" in meta:
        iface["defaultPrompt"] = meta["default_prompt"]
    return iface


def _title(name: str) -> str:
    return " ".join(part.capitalize() for part in name.replace("_", "-").split("-"))


def write_codex(spec: ForgeSpec, out_root: Path) -> Path:
    plugin_path = out_root / ".codex-plugin" / "plugin.json"
    write_json(plugin_path, render_codex(spec))
    mcp = render_codex_mcp(spec)
    if mcp:
        write_json(out_root / ".codex-mcp.json", mcp)
    return plugin_path
