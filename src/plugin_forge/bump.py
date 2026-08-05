"""Version bump propagation across every place the version can live.

Handles: `forge.yaml`, `pyproject.toml`, Python runtime `__version__` values,
provider and legacy manifests, README badge lines, and marketplace manifests.
Idempotent — running `bump` twice at the same target version is a no-op.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from plugin_forge.spec import ForgeSpec

SEMVER = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<rest>[-+][^ ]*)?$")


def _parse(v: str) -> tuple[int, int, int, str]:
    m = SEMVER.match(v.strip())
    if not m:
        raise ValueError(f"not a semver: {v!r}")
    return int(m["major"]), int(m["minor"]), int(m["patch"]), m["rest"] or ""


def bump_version(current: str, level: str) -> str:
    major, minor, patch, rest = _parse(current)
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"unknown bump level: {level!r} (want major|minor|patch)")


@dataclass
class BumpResult:
    old: str
    new: str
    files_changed: list[str]


def apply_bump(
    spec_path: Path, level: str | None = None, *, explicit: str | None = None
) -> BumpResult:
    """Bump the version across all known files.

    If `explicit` is given, use it (raw semver). Otherwise use `level`.
    """
    spec = ForgeSpec.load(spec_path)
    old = spec.version
    if explicit:
        new = explicit
        _parse(new)
    elif level:
        new = bump_version(old, level)
    else:
        raise ValueError("bump requires either level or explicit")

    if old == new:
        return BumpResult(old=old, new=new, files_changed=[])

    repo = spec_path.parent
    changed: list[str] = []

    spec.version = new
    spec.dump(spec_path)
    changed.append(str(spec_path))

    pyproject = repo / "pyproject.toml"
    if pyproject.exists() and _rewrite_pyproject_version(pyproject, new):
        changed.append(str(pyproject))

    for path in _runtime_version_files(repo):
        if _rewrite_runtime_version(path, new):
            changed.append(str(path))

    for rel in (
        Path(".claude-plugin/plugin.json"),
        Path(".codex-plugin/plugin.json"),
        Path("kimi.plugin.json"),
        Path("plugin.json"),
    ):
        p = repo / rel
        if p.exists() and _rewrite_json_version(p, new):
            changed.append(str(p))

    readme = repo / "README.md"
    if readme.exists() and _rewrite_readme_badge(readme, old, new):
        changed.append(str(readme))

    changelog = repo / "CHANGELOG.md"
    if changelog.exists():
        _prepend_changelog_stub(changelog, new)
        changed.append(str(changelog))

    for mkt in (spec.marketplace.claude_manifest, spec.marketplace.kimi_manifest):
        if not mkt:
            continue
        mkt_path = _resolve_marketplace(repo, mkt)
        if mkt_path.exists() and _rewrite_marketplace_version(mkt_path, spec.name, new):
            changed.append(str(mkt_path))

    return BumpResult(old=old, new=new, files_changed=changed)


def _rewrite_pyproject_version(path: Path, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    replaced, n = re.subn(
        r'^(version\s*=\s*)"[^"]+"',
        rf'\1"{new}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n == 0:
        return False
    path.write_text(replaced, encoding="utf-8")
    return True


def _rewrite_json_version(path: Path, new: str) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") == new:
        return False
    data["version"] = new
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def _runtime_version_files(repo: Path) -> list[Path]:
    candidates = [repo / "src", repo]
    return [
        path
        for root in candidates
        if root.exists()
        for path in root.glob("*/__init__.py")
    ]


def _rewrite_runtime_version(path: Path, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    replaced, count = re.subn(
        r'^(\s*__version__\s*=\s*)"[^"]+"',
        rf'\1"{new}"',
        text,
        flags=re.MULTILINE,
    )
    if count == 0:
        return False
    path.write_text(replaced, encoding="utf-8")
    return True


def _rewrite_readme_badge(path: Path, old: str, new: str) -> bool:
    text = path.read_text(encoding="utf-8")
    updated = text.replace(f"version-{old}", f"version-{new}").replace(
        f"v{old}", f"v{new}"
    )
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def _prepend_changelog_stub(path: Path, new: str) -> None:
    from datetime import date

    text = path.read_text(encoding="utf-8")
    if f"[{new}]" in text:
        return
    stub = f"## [{new}] - {date.today().isoformat()}\n\n- Pending release notes.\n\n"
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("## "):
            lines.insert(i, stub)
            path.write_text("".join(lines), encoding="utf-8")
            return
    path.write_text(text.rstrip() + "\n\n" + stub, encoding="utf-8")


def _rewrite_marketplace_version(path: Path, plugin_name: str, new: str) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    def walk(obj: object) -> None:
        nonlocal changed
        if isinstance(obj, dict):
            if obj.get("name") == plugin_name and "version" in obj and obj["version"] != new:
                obj["version"] = new
                changed = True
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    if changed:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def _resolve_marketplace(repo: Path, target: str) -> Path:
    p = Path(target).expanduser()
    if not p.is_absolute():
        p = (repo / p).resolve()
    return p
