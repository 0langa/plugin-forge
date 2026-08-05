from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugin_forge import bump
from plugin_forge.adapters import render_all
from plugin_forge.spec import ForgeSpec


def test_bump_semver() -> None:
    assert bump.bump_version("0.3.1", "patch") == "0.3.2"
    assert bump.bump_version("0.3.1", "minor") == "0.4.0"
    assert bump.bump_version("0.3.1", "major") == "1.0.0"


def test_bump_rejects_non_semver() -> None:
    with pytest.raises(ValueError):
        bump.bump_version("nope", "patch")


def test_apply_bump_updates_all_files(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.3.1"\n', encoding="utf-8"
    )
    runtime = tmp_path / "src" / "demo" / "__init__.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text('__version__ = "0.3.1"\n', encoding="utf-8")
    render_all(sample_spec, tmp_path)
    (tmp_path / "plugin.json").write_text(
        '{"name": "demo", "version": "0.3.1"}\n', encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [0.3.1] - 2026-01-01\n", encoding="utf-8")

    result = bump.apply_bump(tmp_path / "forge.yaml", level="minor")
    assert result.old == "0.3.1"
    assert result.new == "0.4.0"

    pyproject = (tmp_path / "pyproject.toml").read_text()
    assert 'version = "0.4.0"' in pyproject

    claude = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text())
    assert claude["version"] == "0.4.0"
    kimi = json.loads((tmp_path / "kimi.plugin.json").read_text())
    assert kimi["version"] == "0.4.0"
    assert '__version__ = "0.4.0"' in runtime.read_text(encoding="utf-8")
    legacy = json.loads((tmp_path / "plugin.json").read_text())
    assert legacy["version"] == "0.4.0"
    assert "- Pending release notes." in (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")


def test_apply_bump_idempotent(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    r1 = bump.apply_bump(tmp_path / "forge.yaml", explicit="0.3.1")
    assert r1.files_changed == []
