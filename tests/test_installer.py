from __future__ import annotations

from pathlib import Path

import pytest

from plugin_forge import installer, patcher
from plugin_forge.installer import Mode
from plugin_forge.spec import ForgeSpec, InstallTargets, Provider


@pytest.fixture(autouse=True)
def isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(patcher, "RECEIPTS_DIR", tmp_path / "receipts")
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    monkeypatch.setitem(installer.PROVIDER_SETTINGS, Provider.CLAUDE, settings_dir / "claude.json")
    monkeypatch.setitem(installer.PROVIDER_SETTINGS, Provider.CODEX, settings_dir / "codex.json")
    monkeypatch.setitem(installer.PROVIDER_SETTINGS, Provider.KIMI, settings_dir / "kimi.json")


def test_link_install_creates_marker(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "code.py").write_text("x = 1\n", encoding="utf-8")

    target = tmp_path / "installs" / "claude"
    sample_spec.install = InstallTargets(claude=str(target))
    sample_spec.providers = [Provider.CLAUDE]
    sample_spec.settings_patches = {"mcpServers": {"demo": {"command": "x", "cwd": "{{target}}"}}}

    report = installer.install(sample_spec, repo, Provider.CLAUDE, mode=Mode.LINK)
    assert target.exists()
    assert target.is_symlink() or (target / ".forge-link").exists() or (target / "src" / "code.py").exists()
    assert report.settings_patched


def test_link_install_noops_when_target_resolves_to_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src.txt").write_text("ok\n", encoding="utf-8")

    installer._link_install(repo, repo)  # noqa: SLF001

    assert (repo / "src.txt").read_text(encoding="utf-8") == "ok\n"
    assert not (repo / ".forge-link").exists()


def test_uninstall_reverts_settings(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    target = tmp_path / "installs" / "claude"
    sample_spec.install = InstallTargets(claude=str(target))
    sample_spec.providers = [Provider.CLAUDE]
    sample_spec.settings_patches = {"mcpServers": {"demo": {"command": "x"}}}

    installer.install(sample_spec, repo, Provider.CLAUDE, mode=Mode.LINK)
    installer.uninstall(sample_spec, Provider.CLAUDE)
    settings = installer.PROVIDER_SETTINGS[Provider.CLAUDE]
    import json
    data = json.loads(settings.read_text()) if settings.exists() else {}
    assert "mcpServers" not in data
    assert not (target / ".forge-link").exists()


def test_kimi_install_honors_kimi_code_home(
    sample_spec: ForgeSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "source"
    repo.mkdir()
    (repo / "skill.md").write_text("body\n", encoding="utf-8")
    kimi_home = tmp_path / "kimi-home"
    monkeypatch.setenv("KIMI_CODE_HOME", str(kimi_home))
    sample_spec.providers = [Provider.KIMI]
    sample_spec.install = InstallTargets(kimi="~/.kimi-code/plugins/managed/demo/")

    report = installer.install(sample_spec, repo, Provider.KIMI, mode=Mode.COPY)

    expected_target = kimi_home / "plugins" / "managed" / "demo"
    assert report.target == expected_target
    assert report.registry_path == kimi_home / "plugins" / "installed.json"
    assert report.registry_path.exists()
