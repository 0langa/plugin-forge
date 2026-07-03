from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from plugin_forge import mcp_server
from plugin_forge.spec import (
    ForgeSpec,
    InstallTargets,
    Marketplace,
    Provider,
    Surfaces,
)


def _spec(name: str, version: str, description: str = "demo") -> ForgeSpec:
    return ForgeSpec(
        name=name,
        version=version,
        description=description,
        providers=[Provider.CLAUDE],
        install=InstallTargets(claude="~/.claude/plugins/x/"),
        surfaces=Surfaces(),
        marketplace=Marketplace(),
    )


def _make_repo(tmp_path: Path, name: str, version: str) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _spec(name, version).dump(repo / "forge.yaml")
    return repo


def _write_marketplaces(mkt: Path, existing_plugins: list[dict[str, Any]]) -> None:
    mkt.mkdir(parents=True, exist_ok=True)
    (mkt / "plugins.json").write_text(
        json.dumps({"plugins": existing_plugins}, indent=2), encoding="utf-8"
    )
    kimi = [
        {"id": p["name"], "displayName": p.get("displayName", p["name"]), "source": "./x"}
        for p in existing_plugins
    ]
    (mkt / "kimi-marketplace.json").write_text(
        json.dumps({"version": "2", "plugins": kimi}, indent=2), encoding="utf-8"
    )


def test_updates_existing_entry_version(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "demo", "1.2.3")
    mkt = tmp_path / "mkt"
    _write_marketplaces(
        mkt,
        [{"name": "demo", "version": "1.0.0", "description": "old"}],
    )
    result = mcp_server.register_marketplace(path=str(repo), marketplace_repo=str(mkt))
    assert result["changed"], result
    updated = json.loads((mkt / "plugins.json").read_text())
    assert updated["plugins"][0]["version"] == "1.2.3"


def test_refuses_to_add_missing_entry(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "new-plugin", "0.1.0")
    mkt = tmp_path / "mkt"
    _write_marketplaces(mkt, [{"name": "other", "version": "1.0.0"}])
    result = mcp_server.register_marketplace(path=str(repo), marketplace_repo=str(mkt))
    assert result["changed"] == []
    assert any("not present" in n for n in result["notes"])
    unchanged = json.loads((mkt / "plugins.json").read_text())
    assert len(unchanged["plugins"]) == 1


def test_kimi_marketplace_uses_id_key(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "demo", "1.2.3")
    mkt = tmp_path / "mkt"
    _write_marketplaces(mkt, [{"name": "demo", "version": "1.0.0"}])
    result = mcp_server.register_marketplace(path=str(repo), marketplace_repo=str(mkt))
    assert result["dry_run"] is False
    kimi = json.loads((mkt / "kimi-marketplace.json").read_text())
    entry = next((p for p in kimi["plugins"] if p.get("id") == "demo"), None)
    assert entry is not None
    assert entry.get("source") == "./x"


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "demo", "1.2.3")
    mkt = tmp_path / "mkt"
    _write_marketplaces(mkt, [{"name": "demo", "version": "1.0.0"}])
    original = (mkt / "plugins.json").read_text()
    result = mcp_server.register_marketplace(
        path=str(repo), marketplace_repo=str(mkt), dry_run=True
    )
    assert result["dry_run"] is True
    assert (mkt / "plugins.json").read_text() == original


def test_no_op_when_already_current(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "demo", "1.2.3")
    mkt = tmp_path / "mkt"
    _write_marketplaces(mkt, [{"name": "demo", "version": "1.2.3", "description": "demo"}])
    result = mcp_server.register_marketplace(path=str(repo), marketplace_repo=str(mkt))
    assert result["changed"] == []
    assert any("up to date" in n for n in result["notes"])


REAL_MKT = Path("C:/Users/Julius/source/repos/0langas-plugin-marketplace")


@pytest.mark.skipif(not REAL_MKT.exists(), reason="real marketplace repo missing")
def test_real_marketplace_shape_recognized(tmp_path: Path) -> None:
    """Sanity-check: run against the real 0langas-plugin-marketplace jsons in dry-run."""
    repo = _make_repo(tmp_path, "recall", "1.1.1")
    result = mcp_server.register_marketplace(
        path=str(repo), marketplace_repo=str(REAL_MKT), dry_run=True
    )
    assert isinstance(result["changed"], list)
    combined_notes = " ".join(result["notes"])
    assert "not present" not in combined_notes, combined_notes
