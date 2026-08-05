from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml

from plugin_forge import __version__


def test_runtime_version_matches_project_forge_spec_and_manifests() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    forge_spec = yaml.safe_load((root / "forge.yaml").read_text(encoding="utf-8"))
    manifests = [
        root / ".claude-plugin" / "plugin.json",
        root / ".codex-plugin" / "plugin.json",
        root / "kimi.plugin.json",
    ]

    expected = project["project"]["version"]
    assert __version__ == expected
    assert forge_spec["version"] == expected
    assert all(json.loads(path.read_text(encoding="utf-8"))["version"] == expected for path in manifests)
