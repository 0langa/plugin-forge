from __future__ import annotations

from pathlib import Path

from plugin_forge import importer
from plugin_forge.adapters import render_all


def test_import_roundtrip_from_rendered(sample_spec, tmp_path: Path) -> None:
    render_all(sample_spec, tmp_path)
    (tmp_path / "skills" / "do-thing").mkdir(parents=True, exist_ok=True)
    (tmp_path / "skills" / "do-thing" / "SKILL.md").write_text(
        "---\nname: do-thing\n---\nbody", encoding="utf-8"
    )
    reimported = importer.sniff(tmp_path)
    assert reimported.name == sample_spec.name
    assert reimported.version == sample_spec.version
    assert set(p.value for p in reimported.providers) == set(
        p.value for p in sample_spec.providers
    )
    assert reimported.surfaces.skills
    assert any(m.name == "demo" for m in reimported.surfaces.mcp)
