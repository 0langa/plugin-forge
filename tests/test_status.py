from __future__ import annotations

from pathlib import Path

import pytest

from plugin_forge import audit, status
from plugin_forge.adapters import render_all
from plugin_forge.spec import ForgeSpec, Provider


@pytest.fixture(autouse=True)
def redirect_provider_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for provider in Provider:
        root = tmp_path / provider.value / "plugins"
        root.mkdir(parents=True)
        settings = tmp_path / provider.value / "settings.json"
        settings.write_text("{}", encoding="utf-8")
        monkeypatch.setitem(audit.PROVIDER_ROOTS, provider, root)
        monkeypatch.setitem(audit.PROVIDER_SETTINGS, provider, settings)


def test_probe_reports_non_plugin_repo(tmp_path: Path) -> None:
    st = status.probe(tmp_path)
    assert st.is_plugin_repo is False
    assert st.banner() == ""


def test_probe_reports_plugin_with_drift(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    st = status.probe(tmp_path)
    assert st.is_plugin_repo is True
    assert st.has_forge_yaml is True
    assert st.name == sample_spec.name
    assert st.drift, "expected drift because manifests are not compiled yet"


def test_probe_clean_after_compile(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    render_all(sample_spec, tmp_path)
    st = status.probe(tmp_path)
    assert st.drift == []
    assert "drift" not in st.banner().lower()
    assert sample_spec.name in st.banner()


def test_probe_detects_provider_manifest_only(tmp_path: Path) -> None:
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "plugin.json").write_text(
        '{"name": "x", "version": "0"}', encoding="utf-8"
    )
    st = status.probe(tmp_path)
    assert st.is_plugin_repo is True
    assert st.has_forge_yaml is False
    assert any("import" in note.lower() for note in st.notes)
