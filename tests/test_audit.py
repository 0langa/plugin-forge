from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugin_forge import audit
from plugin_forge.spec import Provider


@pytest.fixture(autouse=True)
def redirect_provider_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for provider in Provider:
        root = tmp_path / provider.value / "plugins"
        root.mkdir(parents=True)
        settings = tmp_path / provider.value / "settings.json"
        settings.write_text("{}", encoding="utf-8")
        monkeypatch.setitem(audit.PROVIDER_ROOTS, provider, root)
        monkeypatch.setitem(audit.PROVIDER_SETTINGS, provider, settings)


def _plant(provider: Provider, name: str, version: str, is_link: bool = False) -> Path:
    root = audit.PROVIDER_ROOTS[provider]
    plugin_dir = root / name
    plugin_dir.mkdir(parents=True)
    manifest_parts = audit.MANIFEST_NAMES[provider]
    manifest = plugin_dir.joinpath(*manifest_parts)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({"name": name, "version": version}), encoding="utf-8"
    )
    if is_link:
        (plugin_dir / ".forge-link").write_text(
            json.dumps({"source": "/tmp/x"}), encoding="utf-8"
        )
    return plugin_dir


def test_reports_installed_plugin() -> None:
    _plant(Provider.CLAUDE, "demo", "0.1.0")
    report = audit.run()
    names = [p.name for p in report.installed]
    assert "demo" in names


def test_detects_link_marker() -> None:
    _plant(Provider.KIMI, "linked", "0.1.0", is_link=True)
    report = audit.run()
    inst = next(p for p in report.installed if p.name == "linked")
    assert inst.is_link is True


def test_orphan_plugin_dir_flagged() -> None:
    orphan = audit.PROVIDER_ROOTS[Provider.CODEX] / "no-manifest"
    orphan.mkdir()
    report = audit.run()
    assert orphan in report.orphans


def test_missing_across_providers() -> None:
    _plant(Provider.CLAUDE, "only-claude", "0.1.0")
    report = audit.run()
    assert "only-claude" in report.missing_across
    missing = report.missing_across["only-claude"]
    assert Provider.CODEX in missing
    assert Provider.KIMI in missing


def test_mcp_registration_detected() -> None:
    _plant(Provider.CLAUDE, "demo", "0.1.0")
    settings = audit.PROVIDER_SETTINGS[Provider.CLAUDE]
    settings.write_text(
        json.dumps({"mcpServers": {"demo": {"command": "x"}}}), encoding="utf-8"
    )
    report = audit.run()
    inst = next(p for p in report.installed if p.name == "demo")
    assert inst.mcp_registered is True


def test_kimi_audit_honors_kimi_code_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kimi_home = tmp_path / "kimi-home"
    managed = kimi_home / "plugins" / "managed" / "demo"
    manifest = managed / "kimi.plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"name": "demo", "version": "0.1.0"}), encoding="utf-8")
    monkeypatch.setenv("KIMI_CODE_HOME", str(kimi_home))

    report = audit.run()

    plugin = next(p for p in report.installed if p.provider is Provider.KIMI and p.name == "demo")
    assert plugin.path == managed


def test_marketplace_caches_are_discovered_without_orphaning_provider_storage() -> None:
    for provider in (Provider.CLAUDE, Provider.CODEX):
        root = audit.PROVIDER_ROOTS[provider]
        for name in ("data", "marketplaces", ".plugin-appserver"):
            (root / name).mkdir()
        for version in ("0.9.0", "1.0.0"):
            plugin = root / "cache" / "market" / "demo" / version
            manifest = plugin.joinpath(*audit.MANIFEST_NAMES[provider])
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"name": "demo", "version": version}), encoding="utf-8")
    _plant(Provider.KIMI, "demo", "1.0.0")
    report = audit.run()
    assert len([p for p in report.installed if p.name == "demo"]) == 5
    assert "demo" not in report.missing_across
    assert report.orphans == []
    assert all(p.notes for p in report.installed if p.provider is not Provider.KIMI)


def test_codex_toml_and_claude_autodiscovered_hooks_are_recognized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex = _plant(Provider.CODEX, "demo", "1.0.0")
    settings = tmp_path / "config.toml"
    settings.write_text('[mcp_servers.demo]\ncommand = "example"\n', encoding="utf-8")
    monkeypatch.setitem(audit.PROVIDER_SETTINGS, Provider.CODEX, settings)
    claude = _plant(Provider.CLAUDE, "demo", "1.0.0")
    (claude / "hooks").mkdir()
    (claude / "hooks" / "hooks.json").write_text('{"hooks": {}}', encoding="utf-8")
    # A dual-provider package's Claude hooks do not register Codex hooks.
    (codex / ".claude-plugin").mkdir()
    (codex / ".claude-plugin" / "plugin.json").write_text('{"name": "demo"}', encoding="utf-8")
    (codex / "hooks").mkdir()
    (codex / "hooks" / "hooks.json").write_text('{"hooks": {}}', encoding="utf-8")
    report = audit.run()
    assert next(p for p in report.installed if p.provider is Provider.CODEX).mcp_registered
    assert not next(p for p in report.installed if p.provider is Provider.CODEX).hooks_registered
    assert next(p for p in report.installed if p.provider is Provider.CLAUDE).hooks_registered
