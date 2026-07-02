from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugin_forge import patcher


@pytest.fixture(autouse=True)
def isolate_receipts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(patcher, "RECEIPTS_DIR", tmp_path / "receipts")


def test_apply_creates_backup_and_receipt(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"a": 1}), encoding="utf-8")
    receipt = patcher.apply("demo", target, {"mcpServers": {"demo": {"command": "x"}}})
    assert receipt.backup.exists()
    data = json.loads(target.read_text())
    assert data["mcpServers"]["demo"]["command"] == "x"
    assert data["a"] == 1


def test_unapply_removes_added_keys(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"a": 1}), encoding="utf-8")
    patcher.apply("demo", target, {"mcpServers": {"demo": {"command": "x"}}})
    assert patcher.unapply("demo", target) is True
    data = json.loads(target.read_text())
    assert "mcpServers" not in data
    assert data["a"] == 1


def test_unapply_restores_scalar_override(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text(json.dumps({"model": "old", "other": 5}), encoding="utf-8")
    patcher.apply("demo", target, {"model": "new"})
    patcher.unapply("demo", target)
    data = json.loads(target.read_text())
    assert data["model"] == "old"
    assert data["other"] == 5


def test_apply_on_missing_target_creates_it(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    patcher.apply("demo", target, {"mcpServers": {"demo": {"command": "x"}}})
    assert target.exists()
    patcher.unapply("demo", target)
    data = json.loads(target.read_text())
    assert data == {}
