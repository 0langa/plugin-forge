"""Cross-provider inventory of installed plugins on this machine.

Walks `~/.claude/plugins/`, `~/.codex/plugins/`, and Kimi's managed plugin
root, reads each plugin's manifest, checks manifest-owned or legacy global MCP
and hook wiring, and flags orphans and cross-provider gaps.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from plugin_forge.paths import has_kimi_code_home_override, kimi_code_home
from plugin_forge.spec import Provider

PROVIDER_ROOTS = {
    Provider.CLAUDE: Path.home() / ".claude" / "plugins",
    Provider.CODEX: Path.home() / ".codex" / "plugins",
    Provider.KIMI: Path.home() / ".kimi-code" / "plugins" / "managed",
}

PROVIDER_SETTINGS = {
    Provider.CLAUDE: Path.home() / ".claude" / "settings.json",
    Provider.CODEX: Path.home() / ".codex" / "config.toml",
    Provider.KIMI: Path.home() / ".kimi-code" / "settings.json",
}

MANIFEST_NAMES = {
    Provider.CLAUDE: (".claude-plugin", "plugin.json"),
    Provider.CODEX: (".codex-plugin", "plugin.json"),
    Provider.KIMI: ("kimi.plugin.json",),
}


@dataclass
class InstalledPlugin:
    provider: Provider
    name: str
    version: str
    path: Path
    is_link: bool
    mcp_registered: bool
    hooks_registered: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class AuditReport:
    installed: list[InstalledPlugin] = field(default_factory=list)
    orphans: list[Path] = field(default_factory=list)
    missing_across: dict[str, set[Provider]] = field(default_factory=dict)


def run() -> AuditReport:
    report = AuditReport()
    seen: dict[str, dict[Provider, InstalledPlugin]] = {}

    for provider, configured_root in PROVIDER_ROOTS.items():
        root = _provider_root(provider, configured_root)
        if not root.is_dir():
            continue
        settings_path = _provider_settings(provider)
        settings = (
            tomllib.loads(settings_path.read_text(encoding="utf-8-sig"))
            if settings_path.suffix == ".toml" and settings_path.exists()
            else _load_json(settings_path)
        )
        entries = list(root.iterdir())
        cache = root / "cache"
        if provider in (Provider.CLAUDE, Provider.CODEX) and cache.is_dir():
            entries.extend(
                version
                for marketplace in cache.iterdir() if marketplace.is_dir()
                for plugin in marketplace.iterdir() if plugin.is_dir()
                for version in plugin.iterdir() if version.is_dir()
            )
        for entry in sorted(entries):
            if not entry.is_dir():
                continue
            manifest = _find_manifest(entry, provider)
            if manifest is None:
                if entry.parent == root and (
                    entry.name.startswith(".") or entry.name in {"cache", "data", "marketplaces"}
                ):
                    continue
                report.orphans.append(entry)
                continue
            data = _load_json(manifest)
            name = data.get("name") or entry.name
            version = str(data.get("version", "?"))
            is_link = (entry / ".forge-link").exists()
            mcp_ok = _mcp_registered(name, settings, data)
            hooks_ok = _hooks_registered(entry, settings, data, provider)
            plugin = InstalledPlugin(
                provider=provider,
                name=name,
                version=version,
                path=entry,
                is_link=is_link,
                mcp_registered=mcp_ok,
                hooks_registered=hooks_ok,
            )
            if cache in entry.parents:
                plugin.notes.append("versioned marketplace cache copy; active version not inferred")
            if data and not name:
                plugin.notes.append("manifest missing 'name'")
            report.installed.append(plugin)
            seen.setdefault(name, {})[provider] = plugin

    all_providers = set(PROVIDER_ROOTS.keys())
    for name, per_provider in seen.items():
        missing = all_providers - set(per_provider.keys())
        if missing:
            report.missing_across[name] = missing
    return report


def _provider_root(provider: Provider, configured_root: Path) -> Path:
    if provider is Provider.KIMI and has_kimi_code_home_override():
        return kimi_code_home() / "plugins" / "managed"
    return configured_root


def _provider_settings(provider: Provider) -> Path:
    if provider is Provider.KIMI and has_kimi_code_home_override():
        return kimi_code_home() / "settings.json"
    return PROVIDER_SETTINGS[provider]


def _find_manifest(plugin_dir: Path, provider: Provider) -> Path | None:
    parts = MANIFEST_NAMES[provider]
    candidate = plugin_dir.joinpath(*parts)
    return candidate if candidate.exists() else None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cast(dict[str, Any], data)
    except Exception:
        return {}


def _mcp_registered(name: str, settings: dict[str, Any], manifest: dict[str, Any]) -> bool:
    if "mcpServers" in manifest:
        return True
    servers = settings.get("mcpServers", settings.get("mcp_servers"))
    return isinstance(servers, dict) and name in servers


def _hooks_registered(
    plugin_dir: Path, settings: dict[str, Any], manifest: dict[str, Any], provider: Provider
) -> bool:
    if "hooks" in manifest:
        return True
    if provider is Provider.CLAUDE and (plugin_dir / "hooks" / "hooks.json").is_file():
        return True
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    plugin_str = str(plugin_dir)
    return any(plugin_str in json.dumps(v) for v in hooks.values())
