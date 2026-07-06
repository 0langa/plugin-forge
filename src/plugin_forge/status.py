"""Plugin-repo status probe.

Given a directory, decides whether it's a plugin repo, loads its `forge.yaml`
(or offers import), and reports drift + install state + marketplace sync in a
single call. Used by hooks and the /forge command.
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from plugin_forge import audit, sync
from plugin_forge.spec import ForgeSpec


@dataclass
class RepoStatus:
    is_plugin_repo: bool
    repo: Path
    has_forge_yaml: bool
    name: str | None = None
    version: str | None = None
    providers: list[str] = field(default_factory=list)
    drift: list[dict[str, Any]] = field(default_factory=list)
    installed_providers: list[str] = field(default_factory=list)
    installed_versions: dict[str, str] = field(default_factory=dict)
    marketplace_synced: bool | None = None
    marketplace_notes: list[str] = field(default_factory=list)
    git_branch: str | None = None
    git_dirty: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "repo": str(self.repo)}

    def banner(self) -> str:
        if not self.is_plugin_repo:
            return ""
        parts = [f"{self.name or self.repo.name} v{self.version or '?'}"]
        if self.installed_providers:
            parts.append("installed " + "+".join(self.installed_providers))
        missing = set(self.providers) - set(self.installed_providers)
        if missing:
            parts.append("MISSING " + "+".join(sorted(missing)))
        if self.drift:
            parts.append(f"{len(self.drift)} drift")
        if self.marketplace_synced is False:
            parts.append("marketplace STALE")
        if self.git_dirty:
            parts.append("uncommitted")
        return " | ".join(parts)


def probe(cwd: Path) -> RepoStatus:
    repo = _find_repo_root(cwd)
    if repo is None:
        return RepoStatus(is_plugin_repo=False, repo=cwd, has_forge_yaml=False)

    forge_yaml = repo / "forge.yaml"
    has_forge = forge_yaml.exists()

    is_plugin_repo = has_forge or _has_provider_manifest(repo)
    status = RepoStatus(is_plugin_repo=is_plugin_repo, repo=repo, has_forge_yaml=has_forge)
    if not is_plugin_repo:
        return status

    status.git_branch, status.git_dirty = _git_state(repo)

    if not has_forge:
        status.notes.append("no forge.yaml - run forge.import to retrofit")
        return status

    try:
        spec = ForgeSpec.load(forge_yaml)
    except Exception as exc:
        status.notes.append(f"forge.yaml invalid: {exc}")
        return status

    status.name = spec.name
    status.version = spec.version
    status.providers = [p.value for p in spec.providers]

    drift_report = sync.check(spec, repo)
    status.drift = [
        {"provider": d.provider.value, "kind": d.kind, "message": d.message}
        for d in drift_report.drift
    ]

    inventory = audit.run()
    for inst in inventory.installed:
        if inst.name == spec.name:
            status.installed_providers.append(inst.provider.value)
            status.installed_versions[inst.provider.value] = inst.version

    status.marketplace_synced, status.marketplace_notes = _check_marketplace(spec, repo)
    return status


def _find_repo_root(cwd: Path) -> Path | None:
    cwd = cwd.resolve()
    for candidate in [cwd, *cwd.parents]:
        if (
            (candidate / "forge.yaml").exists()
            or _has_provider_manifest(candidate)
        ):
            return candidate
    if (cwd / ".git").exists():
        return cwd
    return None


def _has_provider_manifest(repo: Path) -> bool:
    return (
        (repo / ".claude-plugin" / "plugin.json").exists()
        or (repo / ".codex-plugin" / "plugin.json").exists()
        or (repo / "kimi.plugin.json").exists()
    )


def _git_state(repo: Path) -> tuple[str | None, bool]:
    try:
        branch = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        )
        return branch, dirty
    except Exception:
        return None, False


def _check_marketplace(spec: ForgeSpec, repo: Path) -> tuple[bool | None, list[str]]:
    notes: list[str] = []
    import json

    checked = False
    ok = True
    for mkt in (spec.marketplace.claude_manifest, spec.marketplace.kimi_manifest):
        if not mkt:
            continue
        path = Path(mkt).expanduser()
        if not path.is_absolute():
            path = (repo / path).resolve()
        if not path.exists():
            notes.append(f"{path} not found")
            continue
        checked = True
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            notes.append(f"{path}: {exc}")
            ok = False
            continue
        found_version = _find_plugin_version(data, spec.name)
        if found_version is None:
            notes.append(f"{path.name}: plugin '{spec.name}' not registered")
            ok = False
        elif found_version != spec.version:
            notes.append(f"{path.name}: {found_version} != {spec.version}")
            ok = False
    return (ok if checked else None), notes


def _find_plugin_version(root: object, name: str) -> str | None:
    if isinstance(root, dict):
        if root.get("name") == name and "version" in root:
            return str(root["version"])
        for v in root.values():
            found = _find_plugin_version(v, name)
            if found is not None:
                return found
    elif isinstance(root, list):
        for v in root:
            found = _find_plugin_version(v, name)
            if found is not None:
                return found
    return None
