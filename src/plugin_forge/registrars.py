"""Per-provider registrar strategies.

Each provider discovers plugins through a distinct mechanism. Forge cannot
install a plugin by only patching `settings.json` (that only wires MCP +
hooks, not discovery). What follows was verified against the official docs
and Julius's live environment on 2026-07-03:

Claude Code
    Documented install path is a marketplace. Forge maintains a "forge-local"
    marketplace file (`.claude-plugin/marketplace.json` per official schema at
    https://code.claude.com/docs/en/plugin-marketplaces) that lists every
    forge-managed plugin with a `source` pointing at the source repo. Forge
    does not touch `installed_plugins.json` (internal cache). Actual install
    is done by `claude plugin install <name>@forge-local` — either the user
    runs it once or forge invokes the CLI as a subprocess.

Codex
    Documented model: `~/.codex/config.toml` with `[marketplaces.<name>]`
    (`source_type = "local"`, `source = "<path>"`) plus a `[plugins."<name>@<marketplace>"]`
    section with `enabled = true`. Forge writes both. Verified against the
    live `[marketplaces.0langas-personal]` block on Julius's box.

Kimi Code
    Documented model: `~/.kimi-code/plugins/installed.json` v1 with entries
    `{id, root, source, enabled, ...}`; `source: "local-path"` is the
    documented "install-from-a-directory" flow. Forge's registrar writes the
    same shape used by every other 0langas plugin already installed via that
    flow on Julius's box.

Registrars are non-transactional today: they take a `.forge-backup.<ts>`
snapshot before modifying, but do not chain into the settings.json patcher's
receipt system. Removal uses "delete by exact key match", relying on the id
being unique.
"""

from __future__ import annotations

import json
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

try:
    import tomllib  # 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

import tomli_w

from plugin_forge.spec import ForgeSpec, Provider

DEFAULT_MARKETPLACE = "forge-local"


@dataclass
class RegistrarReport:
    provider: Provider
    registry: Path
    installed: bool
    already_present: bool
    backup: Path | None


class Registrar(ABC):
    provider: Provider

    @property
    @abstractmethod
    def registry_path(self) -> Path: ...

    @abstractmethod
    def register(
        self, spec: ForgeSpec, install_dir: Path, source_dir: Path | None = None
    ) -> RegistrarReport: ...

    @abstractmethod
    def unregister(self, name: str) -> bool: ...

    def _backup(self, path: Path) -> Path | None:
        if not path.exists():
            return None
        ts = int(time.time())
        backup = path.with_suffix(path.suffix + f".forge-backup.{ts}")
        shutil.copy2(path, backup)
        return backup


class ClaudeRegistrar(Registrar):
    provider = Provider.CLAUDE

    @property
    def registry_path(self) -> Path:
        return (
            Path.home()
            / ".plugin-forge"
            / "marketplaces"
            / "claude"
            / DEFAULT_MARKETPLACE
            / ".claude-plugin"
            / "marketplace.json"
        )

    def register(
        self, spec: ForgeSpec, install_dir: Path, source_dir: Path | None = None
    ) -> RegistrarReport:
        registry = self.registry_path
        registry.parent.mkdir(parents=True, exist_ok=True)
        data = _load_json(registry) or {
            "name": DEFAULT_MARKETPLACE,
            "owner": {"name": "0langa"},
            "plugins": [],
        }
        data["name"] = DEFAULT_MARKETPLACE
        data.setdefault("owner", {"name": "0langa"})
        plugins = data.setdefault("plugins", [])
        if not isinstance(plugins, list):
            plugins = []
            data["plugins"] = plugins
        entry: dict[str, Any] = {
            "name": spec.name,
            "source": str(source_dir or install_dir),
            "description": spec.description or spec.name,
            "version": spec.version,
        }
        author = spec.metadata.get("author") if isinstance(spec.metadata, dict) else None
        if author:
            entry["author"] = {"name": str(author)}
        already = any(isinstance(p, dict) and p.get("name") == spec.name for p in plugins)
        backup = self._backup(registry)
        plugins[:] = [
            p for p in plugins if not (isinstance(p, dict) and p.get("name") == spec.name)
        ]
        plugins.append(entry)
        registry.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return RegistrarReport(
            provider=self.provider,
            registry=registry,
            installed=True,
            already_present=already,
            backup=backup,
        )

    def unregister(self, name: str) -> bool:
        registry = self.registry_path
        if not registry.exists():
            return False
        data = _load_json(registry) or {}
        plugins = data.get("plugins")
        if not isinstance(plugins, list):
            return False
        keep = [p for p in plugins if not (isinstance(p, dict) and p.get("name") == name)]
        if len(keep) == len(plugins):
            return False
        self._backup(registry)
        data["plugins"] = keep
        registry.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True


class CodexRegistrar(Registrar):
    provider = Provider.CODEX

    @property
    def registry_path(self) -> Path:
        return Path.home() / ".codex" / "config.toml"

    def register(
        self, spec: ForgeSpec, install_dir: Path, source_dir: Path | None = None
    ) -> RegistrarReport:
        registry = self.registry_path
        registry.parent.mkdir(parents=True, exist_ok=True)
        data = _load_toml(registry)

        marketplaces = data.setdefault("marketplaces", {})
        marketplaces.setdefault(
            DEFAULT_MARKETPLACE,
            {
                "last_updated": _iso_now(),
                "source_type": "local",
                "source": str(install_dir.parent),
            },
        )

        plugins = data.setdefault("plugins", {})
        key = f"{spec.name}@{DEFAULT_MARKETPLACE}"
        already = key in plugins
        backup = self._backup(registry)
        plugins[key] = {"enabled": True, "version": spec.version, "install_path": str(install_dir)}

        registry.write_text(tomli_w.dumps(data), encoding="utf-8")
        return RegistrarReport(
            provider=self.provider,
            registry=registry,
            installed=True,
            already_present=already,
            backup=backup,
        )

    def unregister(self, name: str) -> bool:
        registry = self.registry_path
        if not registry.exists():
            return False
        data = _load_toml(registry)
        plugins = data.get("plugins")
        if not isinstance(plugins, dict):
            return False
        keys_to_delete = [k for k in plugins if k.split("@", 1)[0] == name]
        if not keys_to_delete:
            return False
        self._backup(registry)
        for k in keys_to_delete:
            plugins.pop(k, None)
        registry.write_text(tomli_w.dumps(data), encoding="utf-8")
        return True


class KimiRegistrar(Registrar):
    provider = Provider.KIMI

    @property
    def registry_path(self) -> Path:
        return Path.home() / ".kimi-code" / "plugins" / "installed.json"

    def register(
        self, spec: ForgeSpec, install_dir: Path, source_dir: Path | None = None
    ) -> RegistrarReport:
        registry = self.registry_path
        registry.parent.mkdir(parents=True, exist_ok=True)
        data = _load_json(registry) or {"version": 1, "plugins": []}
        plugins = data.setdefault("plugins", [])

        entry = {
            "id": spec.name,
            "root": str(install_dir),
            "source": "local-path",
            "enabled": True,
            "installedAt": _iso_now(),
            "updatedAt": _iso_now(),
            "originalSource": str(source_dir or install_dir),
        }
        already = any(isinstance(p, dict) and p.get("id") == spec.name for p in plugins)
        backup = self._backup(registry)
        for i, existing in enumerate(plugins):
            if isinstance(existing, dict) and existing.get("id") == spec.name:
                entry["installedAt"] = existing.get("installedAt", entry["installedAt"])
                plugins[i] = entry
                break
        else:
            plugins.append(entry)

        registry.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return RegistrarReport(
            provider=self.provider,
            registry=registry,
            installed=True,
            already_present=already,
            backup=backup,
        )

    def unregister(self, name: str) -> bool:
        registry = self.registry_path
        if not registry.exists():
            return False
        data = _load_json(registry) or {}
        plugins = data.get("plugins")
        if not isinstance(plugins, list):
            return False
        keep = [p for p in plugins if not (isinstance(p, dict) and p.get("id") == name)]
        if len(keep) == len(plugins):
            return False
        self._backup(registry)
        data["plugins"] = keep
        registry.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True


REGISTRARS: dict[Provider, Registrar] = {
    Provider.CLAUDE: ClaudeRegistrar(),
    Provider.CODEX: CodexRegistrar(),
    Provider.KIMI: KimiRegistrar(),
}


def registrar_for(provider: Provider) -> Registrar:
    return REGISTRARS[provider]


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cast(dict[str, Any], data)
    except Exception:
        return None


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _iso_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
