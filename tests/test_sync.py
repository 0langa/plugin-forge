from __future__ import annotations

import json
from pathlib import Path

from plugin_forge import sync
from plugin_forge.adapters import render_all
from plugin_forge.spec import ForgeSpec


def test_clean_after_render(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    render_all(sample_spec, tmp_path)
    report = sync.check(sample_spec, tmp_path)
    assert report.is_clean


def test_detects_missing_manifest(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    report = sync.check(sample_spec, tmp_path)
    assert not report.is_clean
    kinds = {d.kind for d in report.drift}
    assert "missing_manifest" in kinds


def test_detects_drift_after_edit(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    render_all(sample_spec, tmp_path)
    kimi = tmp_path / "kimi.plugin.json"
    data = json.loads(kimi.read_text())
    data["version"] = "9.9.9"
    kimi.write_text(json.dumps(data, indent=2))
    report = sync.check(sample_spec, tmp_path)
    kinds = {d.kind for d in report.drift}
    assert "manifest_drift" in kinds


def test_fix_regenerates(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    report = sync.fix(sample_spec, tmp_path)
    assert report.fixed
    assert sync.check(sample_spec, tmp_path).is_clean
