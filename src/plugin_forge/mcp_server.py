"""plugin-forge MCP server.

stdio transport. Exposes forge subsystems as tools the model calls implicitly
when working inside a plugin repo. All operations are idempotent where
possible; destructive ops require an explicit `confirm=True`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from plugin_forge import audit, bump, importer, installer, status, sync
from plugin_forge.adapters import render_all
from plugin_forge.installer import Mode
from plugin_forge.spec import ForgeSpec, Provider


mcp = FastMCP("plugin-forge")


def _cwd(path: str | None) -> Path:
    return Path(path).resolve() if path else Path(os.getcwd()).resolve()


def _load(path: str | None) -> tuple[ForgeSpec, Path]:
    repo = _cwd(path)
    forge_yaml = repo / "forge.yaml"
    if not forge_yaml.exists():
        raise FileNotFoundError(f"no forge.yaml at {forge_yaml}")
    return ForgeSpec.load(forge_yaml), repo


@mcp.tool()
def status_tool(path: str | None = None) -> dict[str, Any]:
    """Return combined plugin-repo status: manifests, drift, installs, marketplace, git."""
    return status.probe(_cwd(path)).to_dict()


@mcp.tool()
def compile(path: str | None = None) -> dict[str, Any]:
    """Regenerate every provider manifest from forge.yaml. Idempotent."""
    spec, repo = _load(path)
    written = render_all(spec, repo)
    return {
        "name": spec.name,
        "version": spec.version,
        "written": {p.value: str(f) for p, f in written.items()},
    }


@mcp.tool()
def import_repo(path: str | None = None, write: bool = True) -> dict[str, Any]:
    """Sniff repo layout and emit forge.yaml. Returns the resulting spec."""
    repo = _cwd(path)
    spec = importer.sniff(repo)
    forge_yaml = repo / "forge.yaml"
    if write:
        spec.dump(forge_yaml)
    return {
        "wrote": str(forge_yaml) if write else None,
        "spec": spec.model_dump(mode="json", exclude_none=True),
    }


@mcp.tool()
def sync_check(path: str | None = None, fix: bool = False) -> dict[str, Any]:
    """Report drift between forge.yaml and provider manifests. If `fix`, regenerate."""
    spec, repo = _load(path)
    report = sync.fix(spec, repo) if fix else sync.check(spec, repo)
    return {
        "clean": report.is_clean,
        "drift": [
            {"provider": d.provider.value, "kind": d.kind, "message": d.message}
            for d in report.drift
        ],
        "fixed": report.fixed,
    }


@mcp.tool()
def install(
    path: str | None = None,
    provider: str = "all",
    mode: str = "link",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Install into provider(s). `provider`: all|claude|codex|kimi. `mode`: link|copy."""
    spec, repo = _load(path)
    targets = _providers(spec, provider)
    reports = []
    for prov in targets:
        r = installer.install(spec, repo, prov, mode=Mode(mode), dry_run=dry_run)
        reports.append(
            {
                "provider": r.provider.value,
                "target": str(r.target),
                "mode": r.mode.value,
                "manifest": str(r.manifest),
                "settings_target": str(r.settings_target) if r.settings_target else None,
                "settings_patched": r.settings_patched,
            }
        )
    return {"installs": reports, "dry_run": dry_run}


@mcp.tool()
def uninstall(path: str | None = None, provider: str = "all") -> dict[str, Any]:
    """Reverse install. `provider`: all|claude|codex|kimi."""
    spec, repo = _load(path)
    results = []
    for prov in _providers(spec, provider):
        ok = installer.uninstall(spec, prov)
        results.append({"provider": prov.value, "removed": ok})
    return {"results": results}


@mcp.tool()
def bump_version(
    path: str | None = None, level: str = "patch", explicit: str | None = None
) -> dict[str, Any]:
    """Bump version across every file: forge.yaml, pyproject, provider manifests, marketplace."""
    _, repo = _load(path)
    result = bump.apply_bump(repo / "forge.yaml", level=level, explicit=explicit)
    return {"old": result.old, "new": result.new, "files_changed": result.files_changed}


@mcp.tool()
def audit_installed() -> dict[str, Any]:
    """Inventory every installed plugin across all three providers on this machine."""
    report = audit.run()
    return {
        "installed": [
            {
                "provider": p.provider.value,
                "name": p.name,
                "version": p.version,
                "path": str(p.path),
                "is_link": p.is_link,
                "mcp_registered": p.mcp_registered,
                "hooks_registered": p.hooks_registered,
                "notes": p.notes,
            }
            for p in report.installed
        ],
        "orphans": [str(o) for o in report.orphans],
        "missing_across": {
            name: sorted(p.value for p in providers)
            for name, providers in report.missing_across.items()
        },
    }


@mcp.tool()
def hook_test(path: str | None = None, event: str = "SessionStart") -> dict[str, Any]:
    """Fire the hook script for `event` with a synthetic payload. Returns exit + stdout/stderr."""
    import subprocess

    spec, repo = _load(path)
    matches = [h for h in spec.surfaces.hooks if h.event == event]
    if not matches:
        return {"error": f"no hook registered for event {event}"}
    hook = matches[0]
    script = repo / hook.script
    payload = json.dumps({"event": event, "cwd": str(repo), "synthetic": True})
    completed = subprocess.run(
        ["python", str(script)], input=payload, capture_output=True, text=True, timeout=30
    )
    return {
        "event": event,
        "script": str(script),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


@mcp.tool()
def mcp_dev(path: str | None = None, name: str | None = None) -> dict[str, Any]:
    """Print the command that would run the plugin's MCP server locally.

    Does not spawn (host controls process lifecycle). Returns command + env for
    manual launch or copy into an editor.
    """
    spec, repo = _load(path)
    servers = spec.surfaces.mcp
    if name:
        servers = [s for s in servers if s.name == name]
    if not servers:
        return {"error": "no matching MCP server"}
    from plugin_forge.adapters._common import render_mcp_entry

    return {
        "servers": [
            {
                "name": s.name,
                "cwd": str(repo),
                "entry": render_mcp_entry(s),
            }
            for s in servers
        ]
    }


@mcp.tool()
def register_marketplace(
    path: str | None = None,
    marketplace_repo: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Add or update this plugin's entry in the marketplace JSON files."""
    spec, repo = _load(path)
    mkt_root = Path(marketplace_repo).expanduser().resolve() if marketplace_repo else None
    if mkt_root is None:
        candidate = repo.parent / "0langas-plugin-marketplace"
        if candidate.exists():
            mkt_root = candidate
    if mkt_root is None:
        return {"error": "marketplace repo not found; pass marketplace_repo=<path>"}

    changed: list[str] = []
    notes: list[str] = []
    for name in ("plugins.json", "kimi-marketplace.json"):
        path_j = mkt_root / name
        if not path_j.exists():
            continue
        data = json.loads(path_j.read_text(encoding="utf-8"))
        updated, note = _upsert_marketplace_entry(data, spec, name)
        if note:
            notes.append(f"{path_j.name}: {note}")
        if updated and not dry_run:
            path_j.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if updated:
            changed.append(str(path_j))
    return {"changed": changed, "notes": notes, "dry_run": dry_run}


def _upsert_marketplace_entry(
    data: dict[str, Any], spec: ForgeSpec, filename: str
) -> tuple[bool, str | None]:
    """Update an existing marketplace entry for `spec`; never auto-create.

    Real marketplace schemas differ:
        - `plugins.json` (Claude-style): entries keyed by `name`, with
          `pluginRoot`, `installPaths`, `installCommands`, `providers`.
        - `kimi-marketplace.json`: entries keyed by `id`, with `source`.

    Forge only updates `version` (and optional `description`) on existing
    entries. Adding a brand-new entry needs manual review — auto-appending a
    bare stub would produce a broken marketplace.
    """
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        return False, "no plugins list found"

    is_kimi = "kimi" in filename.lower()
    key = "id" if is_kimi else "name"

    for entry in plugins:
        if not isinstance(entry, dict):
            continue
        if entry.get(key) != spec.name:
            continue
        changed = False
        if not is_kimi and "version" in entry and entry["version"] != spec.version:
            entry["version"] = spec.version
            changed = True
        if not is_kimi and spec.description and entry.get("description") != spec.description:
            entry["description"] = spec.description
            changed = True
        if changed:
            return True, None
        return False, "already up to date"

    return False, (
        f"plugin '{spec.name}' not present — add a full entry manually first "
        f"(forge only updates existing entries to avoid breaking marketplace schema)"
    )


def _providers(spec: ForgeSpec, provider: str) -> list[Provider]:
    if provider == "all":
        return list(spec.providers)
    try:
        p = Provider(provider)
    except ValueError as exc:
        raise ValueError(f"unknown provider: {provider}") from exc
    if p not in spec.providers:
        raise ValueError(f"provider {provider} not declared in forge.yaml")
    return [p]


def run() -> None:
    mcp.run()


if __name__ == "__main__":
    run()
