from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[import-not-found]

from plugin_forge.registrars import (
    ClaudeRegistrar,
    CodexRegistrar,
    KimiRegistrar,
    Registrar,
)
from plugin_forge.spec import ForgeSpec, InstallTargets, Provider, Surfaces


def _spec(name: str = "demo", version: str = "0.1.0") -> ForgeSpec:
    return ForgeSpec(
        name=name,
        version=version,
        providers=[Provider.CLAUDE, Provider.CODEX, Provider.KIMI],
        install=InstallTargets(
            claude=f"~/.claude/plugins/{name}/",
            codex=f"~/.codex/plugins/{name}/",
            kimi=f"~/.kimi-code/plugins/{name}/",
        ),
        surfaces=Surfaces(),
    )


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def test_claude_registrar_creates_entry(isolated_home: Path) -> None:
    r = ClaudeRegistrar()
    report = r.register(_spec("demo", "1.0.0"), isolated_home / "install")
    assert report.installed is True
    data = json.loads(r.registry_path.read_text())
    assert "demo@forge-local" in data["plugins"]
    entry = data["plugins"]["demo@forge-local"][0]
    assert entry["version"] == "1.0.0"


def test_claude_registrar_preserves_other_plugins(isolated_home: Path) -> None:
    r = ClaudeRegistrar()
    r.registry_path.parent.mkdir(parents=True, exist_ok=True)
    r.registry_path.write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "recall@0langas-plugins": [
                        {"scope": "user", "installPath": "x", "version": "1.0.0"}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    r.register(_spec(), isolated_home / "install")
    data = json.loads(r.registry_path.read_text())
    assert "recall@0langas-plugins" in data["plugins"]


def test_claude_registrar_unregister(isolated_home: Path) -> None:
    r = ClaudeRegistrar()
    r.register(_spec(), isolated_home / "install")
    assert r.unregister("demo") is True
    data = json.loads(r.registry_path.read_text())
    assert not any(k.startswith("demo@") for k in data.get("plugins", {}))


def test_codex_registrar_writes_toml(isolated_home: Path) -> None:
    r = CodexRegistrar()
    r.register(_spec(), isolated_home / "install")
    data = tomllib.loads(r.registry_path.read_text(encoding="utf-8"))
    assert "demo@forge-local" in data.get("plugins", {})
    assert "forge-local" in data.get("marketplaces", {})


def test_codex_registrar_preserves_existing_config(isolated_home: Path) -> None:
    r = CodexRegistrar()
    r.registry_path.parent.mkdir(parents=True, exist_ok=True)
    r.registry_path.write_text(
        'model = "gpt-5.5"\n\n[marketplaces.openai-bundled]\nsource = "x"\n',
        encoding="utf-8",
    )
    r.register(_spec(), isolated_home / "install")
    data = tomllib.loads(r.registry_path.read_text(encoding="utf-8"))
    assert data["model"] == "gpt-5.5"
    assert "openai-bundled" in data["marketplaces"]


def test_kimi_registrar_appends_entry(isolated_home: Path) -> None:
    r = KimiRegistrar()
    r.register(_spec(), isolated_home / "install")
    data = json.loads(r.registry_path.read_text())
    ids = [p["id"] for p in data["plugins"]]
    assert "demo" in ids


def test_kimi_registrar_updates_existing_id(isolated_home: Path) -> None:
    r = KimiRegistrar()
    r.register(_spec("demo", "1.0.0"), isolated_home / "install-old")
    r.register(_spec("demo", "1.1.0"), isolated_home / "install-new")
    data = json.loads(r.registry_path.read_text())
    demos = [p for p in data["plugins"] if p["id"] == "demo"]
    assert len(demos) == 1
    assert str(isolated_home / "install-new") in demos[0]["root"]


def test_kimi_registrar_unregister(isolated_home: Path) -> None:
    r = KimiRegistrar()
    r.register(_spec(), isolated_home / "install")
    assert r.unregister("demo") is True
    data = json.loads(r.registry_path.read_text())
    assert not any(p.get("id") == "demo" for p in data["plugins"])


@pytest.mark.parametrize("cls", [ClaudeRegistrar, CodexRegistrar, KimiRegistrar])
def test_backup_created(cls: type[Registrar], isolated_home: Path) -> None:
    r = cls()
    r.registry_path.parent.mkdir(parents=True, exist_ok=True)
    r.registry_path.write_text("{}" if not isinstance(r, CodexRegistrar) else "", encoding="utf-8")
    report = r.register(_spec(), isolated_home / "install")
    assert report.backup is not None
    assert report.backup.exists()
