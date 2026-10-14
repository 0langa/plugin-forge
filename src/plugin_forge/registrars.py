"""Per-provider registrar strategies.

Each provider discovers plugins through a distinct mechanism. Forge cannot
install a plugin by only patching `settings.json` (that only wires MCP +
hooks, not discovery). What follows was verified against the official docs
and a live Windows environment on 2026-07-03:

Claude Code
    Documented install path is a marketplace. Forge maintains a "forge-local"
    marketplace directory (`.claude-plugin/marketplace.json` per the official
    schema at https://code.claude.com/docs/en/plugins/marketplace-reference)
    that lists every forge-managed plugin. A string `source` must be a path
    inside the marketplace root that starts with `./`: an absolute path fails
    validation (`must start with "./"`), and a link to a folder outside the
    root installs but fails to load (`Path escapes plugin directory`). So
    forge copies each plugin to `plugins/<name>/` under the root and lists it
    as `./plugins/<name>`; registering again refreshes that copy. Forge does
    not touch `installed_plugins.json` (internal cache). The user adds the
    marketplace once (`claude plugin marketplace add <root>`) and installs
    with `claude plugin install <name>@forge-local`.

Codex
    Documented model: `~/.codex/config.toml` with `[marketplaces.<name>]`
    (`source_type = "local"`, `source = "<path>"`) plus a `[plugins."<name>@<marketplace>"]`
    section with `enabled = true`. Forge writes both. Verified against the
    live `[marketplaces.0langas-personal]` block on a Windows host.

Kimi Code
    `KIMI_CODE_HOME` overrides the default `~/.kimi-code` data root.
    Documented model: `~/.kimi-code/plugins/installed.json` v1 with entries
    `{id, root, source, enabled, ...}`; `source: "local-path"` is the
    documented "install-from-a-directory" flow. Forge's registrar writes the
    same shape used by every other 0langas plugin already installed via that
    flow on a Windows host.

Registrars are non-transactional today: they take a `.forge-backup.<ts>`
snapshot before modifying, but do not chain into the settings.json patcher's
receipt system. Removal uses "delete by exact key match", relying on the id
being unique.
"""

from __future__ import annotations

import json
import re
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

from plugin_forge.paths import kimi_code_home
from plugin_forge.spec import ForgeSpec, Provider

DEFAULT_MARKETPLACE = "forge-local"

# Claude Code's plugin-name rule: letters, digits, ".", "_" and "-", starting
# with a letter or digit, and no "..". It also keeps the copy inside plugins/.
_CLAUDE_PLUGIN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# Left out of the Claude marketplace copy, and kept in it when the copy is
# refreshed (the hook command's `uv run` builds `.venv` inside the copy).
CLAUDE_COPY_IGNORE = (
    ".git",
    ".venv",
    ".venv-*",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "*.egg-info",
    ".forge-link",
)


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
    def marketplace_root(self) -> Path:
        """The directory that holds `.claude-plugin/`; relative sources resolve from it."""
        return Path.home() / ".plugin-forge" / "marketplaces" / "claude" / DEFAULT_MARKETPLACE

    @property
    def registry_path(self) -> Path:
        return self.marketplace_root / ".claude-plugin" / "marketplace.json"

    def plugin_dir(self, name: str) -> Path:
        """Where the marketplace keeps its copy of plugin `name`."""
        if not _CLAUDE_PLUGIN_NAME.fullmatch(name) or ".." in name:
            raise ValueError(
                f"Claude Code cannot install a plugin named {name!r}: use letters, digits, "
                "'.', '_' and '-', starting with a letter or digit"
            )
        return self.marketplace_root / "plugins" / name

    def register(
        self, spec: ForgeSpec, install_dir: Path, source_dir: Path | None = None
    ) -> RegistrarReport:
        registry = self.registry_path
        copy = self.plugin_dir(spec.name)
        _refresh_copy(source_dir or install_dir, copy)
        registry.parent.mkdir(parents=True, exist_ok=True)
        data = _load_json(registry) or {
            "name": DEFAULT_MARKETPLACE,
            "owner": {"name": "0langa"},
            "plugins": [],
        }
        data["name"] = DEFAULT_MARKETPLACE
        data.setdefault("owner", {"name": "0langa"})
        data.setdefault("description", "Plugins registered locally by plugin-forge")
        plugins = data.setdefault("plugins", [])
        if not isinstance(plugins, list):
            plugins = []
            data["plugins"] = plugins
        entry: dict[str, Any] = {
            "name": spec.name,
            "source": "./" + copy.relative_to(self.marketplace_root).as_posix(),
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
        if _CLAUDE_PLUGIN_NAME.fullmatch(name) and ".." not in name:
            copy = self.plugin_dir(name)
            if copy.is_symlink():
                copy.unlink()
            elif copy.is_dir():
                shutil.rmtree(copy)
        return True


def _refresh_copy(source: Path, copy: Path) -> None:
    """Make `copy` hold the current files of `source`.

    Entries matching CLAUDE_COPY_IGNORE are neither copied nor removed, so the
    `.venv` that a hook's `uv run` built inside the copy survives a refresh.
    """
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"plugin source directory not found: {source}")
    if copy.is_symlink():
        copy.unlink()
    target = copy.resolve()
    if target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError(f"the marketplace copy {copy} overlaps the plugin source {source}")
    ignore = shutil.ignore_patterns(*CLAUDE_COPY_IGNORE)
    if copy.is_dir():
        children = list(copy.iterdir())
        kept = ignore(str(copy), [child.name for child in children])
        for child in children:
            if child.name in kept:
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
    shutil.copytree(source, copy, ignore=ignore, dirs_exist_ok=True)


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
        return kimi_code_home() / "plugins" / "installed.json"

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
                if isinstance(existing.get("enabled"), bool):
                    entry["enabled"] = existing["enabled"]
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
