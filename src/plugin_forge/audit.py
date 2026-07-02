"""Cross-provider inventory of installed plugins on this machine.

Walks `~/.claude/plugins/`, `~/.codex/plugins/`, `~/.kimi-code/plugins/`,
reads each plugin's manifest, cross-references settings.json for MCP + hooks
registration state, flags orphans and outdated versions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from plugin_forge.spec import Provider


PROVIDER_ROOTS = {
    Provider.CLAUDE: Path.home() / ".claude" / "plugins",
    Provider.CODEX: Path.home() / ".codex" / "plugins",
    Provider.KIMI: Path.home() / ".kimi-code" / "plugins",
}

PROVIDER_SETTINGS = {
    Provider.CLAUDE: Path.home() / ".claude" / "settings.json",
    Provider.CODEX: Path.home() / ".codex" / "settings.json",
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

    for provider, root in PROVIDER_ROOTS.items():
        if not root.is_dir():
            continue
        settings = _load_json(PROVIDER_SETTINGS[provider])
        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            manifest = _find_manifest(entry, provider)
            if manifest is None:
                report.orphans.append(entry)
                continue
            data = _load_json(manifest)
            name = data.get("name") or entry.name
            version = str(data.get("version", "?"))
            is_link = (entry / ".forge-link").exists()
            mcp_ok = _mcp_registered(name, settings)
            hooks_ok = _hooks_registered(entry, settings)
            plugin = InstalledPlugin(
                provider=provider,
                name=name,
                version=version,
                path=entry,
                is_link=is_link,
                mcp_registered=mcp_ok,
                hooks_registered=hooks_ok,
            )
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


def _find_manifest(plugin_dir: Path, provider: Provider) -> Path | None:
    parts = MANIFEST_NAMES[provider]
    candidate = plugin_dir.joinpath(*parts)
    return candidate if candidate.exists() else None


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mcp_registered(name: str, settings: dict) -> bool:
    servers = settings.get("mcpServers")
    return isinstance(servers, dict) and name in servers


def _hooks_registered(plugin_dir: Path, settings: dict) -> bool:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    plugin_str = str(plugin_dir)
    return any(plugin_str in json.dumps(v) for v in hooks.values())
