from __future__ import annotations

from pathlib import Path

from plugin_forge import importer
from plugin_forge.adapters import render_all
from plugin_forge.spec import ForgeSpec


def test_import_roundtrip_from_rendered(sample_spec: ForgeSpec, tmp_path: Path) -> None:
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


def test_importer_preserves_codex_visual_interface_fields(tmp_path: Path) -> None:
    plugin_dir = tmp_path / ".codex-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        """
{
  "name": "visual-demo",
  "version": "0.1.0",
  "description": "visual plugin",
  "interface": {
    "displayName": "Visual Demo",
    "defaultPrompt": ["Audit visuals."],
    "composerIcon": "./assets/icon.png",
    "logo": "./assets/logo.png",
    "screenshots": ["./assets/screenshot-1.png"]
  }
}
""".strip(),
        encoding="utf-8",
    )

    spec = importer.sniff(tmp_path)

    interface = spec.metadata["interface"]
    assert interface["display_name"] == "Visual Demo"
    assert interface["default_prompt"] == ["Audit visuals."]
    assert interface["composer_icon"] == "./assets/icon.png"
    assert interface["logo"] == "./assets/logo.png"
    assert interface["screenshots"] == ["./assets/screenshot-1.png"]
