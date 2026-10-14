from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

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
    for folder in ("install", "source"):
        _plugin_tree(tmp_path / folder)
    return tmp_path


def _plugin_tree(root: Path) -> Path:
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text('{"name": "demo"}\n', encoding="utf-8")
    (root / "skills" / "s").mkdir(parents=True, exist_ok=True)
    (root / "skills" / "s" / "SKILL.md").write_text(f"from {root.name}\n", encoding="utf-8")
    return root


def test_claude_registrar_creates_entry(isolated_home: Path) -> None:
    r = ClaudeRegistrar()
    report = r.register(
        _spec("demo", "1.0.0"), isolated_home / "install", isolated_home / "source"
    )
    assert report.installed is True
    data = json.loads(r.registry_path.read_text())
    assert data["name"] == "forge-local"
    entry = next(p for p in data["plugins"] if p["name"] == "demo")
    assert entry["version"] == "1.0.0"
    # Claude Code accepts a string source only as a "./" path inside the marketplace root.
    assert entry["source"] == "./plugins/demo"
    copy = r.marketplace_root / "plugins" / "demo"
    assert (copy / "skills" / "s" / "SKILL.md").read_text(encoding="utf-8") == "from source\n"
    assert r.registry_path.parent.parent == r.marketplace_root


def test_claude_registrar_refreshes_its_copy(isolated_home: Path) -> None:
    r = ClaudeRegistrar()
    source = isolated_home / "source"
    (source / "old.txt").write_text("old\n", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")
    r.register(_spec(), isolated_home / "install", source)
    copy = r.marketplace_root / "plugins" / "demo"
    assert (copy / "old.txt").exists()
    assert not (copy / ".git").exists()
    # A hook's `uv run` builds .venv in the copy; a refresh must keep it.
    (copy / ".venv").mkdir()
    (copy / ".venv" / "marker").write_text("venv\n", encoding="utf-8")

    (source / "old.txt").unlink()
    (source / "new.txt").write_text("new\n", encoding="utf-8")
    r.register(_spec(), isolated_home / "install", source)

    assert not (copy / "old.txt").exists()
    assert (copy / "new.txt").read_text(encoding="utf-8") == "new\n"
    assert (copy / ".venv" / "marker").exists()


def test_claude_registrar_rejects_names_claude_cannot_install(isolated_home: Path) -> None:
    r = ClaudeRegistrar()
    for name in ("../escape", "has space", "-dash-first", "a..b"):
        with pytest.raises(ValueError):
            r.register(_spec(name), isolated_home / "install", isolated_home / "source")
    assert not r.registry_path.exists()
    assert not (isolated_home / "escape").exists()


def test_claude_registrar_needs_an_existing_source(isolated_home: Path) -> None:
    r = ClaudeRegistrar()
    with pytest.raises(FileNotFoundError):
        r.register(_spec(), isolated_home / "missing")
    assert not r.registry_path.exists()


def test_claude_registrar_preserves_other_plugins(isolated_home: Path) -> None:
    r = ClaudeRegistrar()
    r.registry_path.parent.mkdir(parents=True, exist_ok=True)
    r.registry_path.write_text(
        json.dumps(
            {
                "name": "forge-local",
                "owner": {"name": "0langa"},
                "plugins": [{"name": "recall", "source": "x", "version": "1.0.0"}],
            }
        ),
        encoding="utf-8",
    )
    r.register(_spec(), isolated_home / "install")
    data = json.loads(r.registry_path.read_text())
    assert any(p["name"] == "recall" for p in data["plugins"])


def test_claude_registrar_unregister(isolated_home: Path) -> None:
    r = ClaudeRegistrar()
    r.register(_spec(), isolated_home / "install")
    assert (r.marketplace_root / "plugins" / "demo").is_dir()
    assert r.unregister("demo") is True
    data = json.loads(r.registry_path.read_text())
    assert not any(p.get("name") == "demo" for p in data.get("plugins", []))
    assert not (r.marketplace_root / "plugins" / "demo").exists()
    assert (isolated_home / "install" / ".claude-plugin" / "plugin.json").exists()


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
    r.register(_spec(), isolated_home / "install", isolated_home / "source")
    data = json.loads(r.registry_path.read_text())
    ids = [p["id"] for p in data["plugins"]]
    assert "demo" in ids
    demo = next(p for p in data["plugins"] if p["id"] == "demo")
    assert demo["root"] == str(isolated_home / "install")
    assert demo["originalSource"] == str(isolated_home / "source")


def test_kimi_registrar_updates_existing_id(isolated_home: Path) -> None:
    r = KimiRegistrar()
    r.register(_spec("demo", "1.0.0"), isolated_home / "install-old")
    r.register(_spec("demo", "1.1.0"), isolated_home / "install-new")
    data = json.loads(r.registry_path.read_text())
    demos = [p for p in data["plugins"] if p["id"] == "demo"]
    assert len(demos) == 1
    assert str(isolated_home / "install-new") in demos[0]["root"]


def test_kimi_registrar_preserves_enabled_state(isolated_home: Path) -> None:
    r = KimiRegistrar()
    r.register(_spec(), isolated_home / "install-old")
    registry = json.loads(r.registry_path.read_text())
    registry["plugins"][0]["enabled"] = False
    r.registry_path.write_text(json.dumps(registry), encoding="utf-8")

    r.register(_spec(), isolated_home / "install-new")

    updated = json.loads(r.registry_path.read_text())
    demo = next(p for p in updated["plugins"] if p["id"] == "demo")
    assert demo["enabled"] is False


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
