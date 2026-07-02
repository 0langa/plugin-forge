"""Install / uninstall a plugin into provider directories.

Two install modes:

    link — the provider dir contains a `.forge-link` file pointing back at the
           source repo. Used for local dev; edits to the repo are picked up
           immediately without recopy.
    copy — the provider dir is a full copy of the repo (excluding VCS and
           build artefacts). Used for user-style installs.

Both modes:
    - Write provider manifests via adapters.
    - Apply settings_patches transactionally against the provider settings.json.
    - Record an install receipt for exact reversal.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from plugin_forge import patcher
from plugin_forge.adapters import render_all
from plugin_forge.registrars import registrar_for
from plugin_forge.spec import ForgeSpec, Provider


class Mode(str, Enum):
    LINK = "link"
    COPY = "copy"


PROVIDER_SETTINGS = {
    Provider.CLAUDE: Path.home() / ".claude" / "settings.json",
    Provider.CODEX: Path.home() / ".codex" / "settings.json",
    Provider.KIMI: Path.home() / ".kimi-code" / "settings.json",
}


@dataclass
class InstallReport:
    provider: Provider
    target: Path
    mode: Mode
    manifest: Path
    settings_target: Path | None
    settings_patched: bool
    registry_path: Path | None = None
    registry_updated: bool = False
    warnings: list[str] = field(default_factory=list)


IGNORE_PATTERNS = {".git", ".venv", ".venv-*", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build", "*.egg-info"}


def install(
    spec: ForgeSpec,
    repo: Path,
    provider: Provider,
    *,
    mode: Mode = Mode.LINK,
    dry_run: bool = False,
) -> InstallReport:
    target = _resolve_target(spec, provider)
    if not target:
        raise ValueError(f"install target for {provider.value} not defined in forge.yaml")
    target = target.expanduser().resolve()

    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        if mode is Mode.LINK:
            _link_install(repo, target)
        else:
            _copy_install(repo, target)

    manifest_paths = render_all(spec, target if not dry_run else Path("/tmp/forge-dryrun"))
    manifest = manifest_paths.get(provider) or target

    settings_target = PROVIDER_SETTINGS.get(provider)
    settings_patched = False
    if spec.settings_patches and settings_target is not None:
        patch = _resolve_settings_patch(spec, provider, target)
        if not dry_run:
            patcher.apply(spec.name, settings_target, patch)
        settings_patched = True

    warnings = _collision_warnings(repo)

    registry_path: Path | None = None
    registry_updated = False
    if not dry_run:
        reg = registrar_for(provider)
        report = reg.register(spec, target)
        registry_path = report.registry
        registry_updated = report.installed

    return InstallReport(
        provider=provider,
        target=target,
        mode=mode,
        manifest=manifest,
        settings_target=settings_target,
        settings_patched=settings_patched,
        registry_path=registry_path,
        registry_updated=registry_updated,
        warnings=warnings,
    )


def _collision_warnings(repo: Path) -> list[str]:
    """Detect competing install machinery in the target plugin repo.

    Emits warnings — never blocks — so the user can decide whether to keep or
    remove the plugin's own installer.
    """
    warnings: list[str] = []
    candidate = repo / "scripts" / "install.py"
    if candidate.exists() and candidate.stat().st_size > 500:
        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return warnings
        if "plugin_forge" not in content:
            warnings.append(
                f"plugin ships its own installer at {candidate.relative_to(repo).as_posix()}; "
                "forge install runs alongside it — consider deleting the plugin's own installer "
                "once forge install is verified equivalent"
            )
    return warnings


def uninstall(spec: ForgeSpec, provider: Provider, *, remove_files: bool = True) -> bool:
    target = _resolve_target(spec, provider)
    if not target:
        return False
    target = target.expanduser().resolve()

    settings_target = PROVIDER_SETTINGS.get(provider)
    if settings_target and settings_target.exists():
        patcher.unapply(spec.name, settings_target)

    registrar_for(provider).unregister(spec.name)

    if remove_files and target.exists():
        link_marker = target / ".forge-link"
        if link_marker.exists():
            link_marker.unlink()
            if not any(target.iterdir()):
                target.rmdir()
        else:
            shutil.rmtree(target, ignore_errors=True)

    return True


def _resolve_target(spec: ForgeSpec, provider: Provider) -> Path | None:
    raw = spec.install.for_provider(provider)
    return Path(raw) if raw else None


def _link_install(repo: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    marker = target / ".forge-link"
    marker.write_text(
        json.dumps({"source": str(repo.resolve())}, indent=2) + "\n",
        encoding="utf-8",
    )


def _copy_install(repo: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(
        repo, target, ignore=shutil.ignore_patterns(*IGNORE_PATTERNS), dirs_exist_ok=True
    )


def _resolve_settings_patch(spec: ForgeSpec, provider: Provider, target: Path) -> dict:
    """Return the patch with `{{target}}` placeholders resolved to the install path."""
    raw = json.dumps(spec.settings_patches)
    raw = raw.replace("{{target}}", str(target).replace("\\", "\\\\"))
    raw = raw.replace("{{provider}}", provider.value)
    return json.loads(raw)
