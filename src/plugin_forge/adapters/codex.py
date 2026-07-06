"""Codex plugin manifest.

Layout:
    .codex-plugin/plugin.json     (rich — includes `interface` block)
    .codex-mcp.json               (mcpServers block; or shared .mcp.json when
                                   spec.options.shared_mcp_file is true)
    hooks/codex-hooks.json        (Codex hook file, sibling of .codex-plugin)

Shape verified against `0langas-plugin-marketplace/plugins/agent-handoff` and
`usage-pulse` (2026-07).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plugin_forge.spec import ForgeSpec, Provider

from ._common import (
    base_header,
    render_hooks_config,
    render_mcp_servers,
    write_json,
)


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
        payload["mcpServers"] = "./.mcp.json" if spec.options.shared_mcp_file else "./.codex-mcp.json"
    if active.hooks:
        payload["hooks"] = "./hooks/codex-hooks.json"
    payload.update(spec.provider_extras.for_provider(Provider.CODEX))
    return payload


def render_codex_mcp(spec: ForgeSpec) -> dict[str, Any]:
    servers = render_mcp_servers(spec, Provider.CODEX)
    return {"mcpServers": servers} if servers else {}


def render_codex_hooks(spec: ForgeSpec) -> dict[str, Any]:
    return render_hooks_config(spec, Provider.CODEX)


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
        iface["defaultPrompt"] = _default_prompt(meta["default_prompt"])
    if "brand_color" in meta:
        iface["brandColor"] = meta["brand_color"]
    if "composer_icon" in meta:
        iface["composerIcon"] = meta["composer_icon"]
    if "logo" in meta:
        iface["logo"] = meta["logo"]
    if "screenshots" in meta:
        iface["screenshots"] = meta["screenshots"]
    return iface


def _title(name: str) -> str:
    return " ".join(part.capitalize() for part in name.replace("_", "-").split("-"))


def _default_prompt(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def write_codex(spec: ForgeSpec, out_root: Path) -> Path:
    plugin_path = out_root / ".codex-plugin" / "plugin.json"
    write_json(plugin_path, render_codex(spec))

    mcp = render_codex_mcp(spec)
    if mcp:
        if spec.options.shared_mcp_file:
            shared = out_root / ".mcp.json"
            if not shared.exists():
                write_json(shared, mcp)
        else:
            write_json(out_root / ".codex-mcp.json", mcp)

    hooks = render_codex_hooks(spec)
    if hooks:
        write_json(out_root / "hooks" / "codex-hooks.json", hooks)

    return plugin_path
