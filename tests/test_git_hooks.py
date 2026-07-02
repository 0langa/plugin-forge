from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from plugin_forge import git_hooks, sync
from plugin_forge.adapters import render_all
from plugin_forge.spec import ForgeSpec


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)


def test_install_hooks_copies_files(tmp_path: Path) -> None:
    _init_git(tmp_path)
    installed = git_hooks.install_hooks(tmp_path)
    assert (tmp_path / ".git" / "hooks" / "pre-commit").exists()
    assert (tmp_path / ".git" / "hooks" / "pre-push").exists()
    assert len(installed) == 2


def test_install_hooks_reinstall_idempotent(tmp_path: Path) -> None:
    _init_git(tmp_path)
    git_hooks.install_hooks(tmp_path)
    first = (tmp_path / ".git" / "hooks" / "pre-commit").read_text()
    git_hooks.install_hooks(tmp_path)
    second = (tmp_path / ".git" / "hooks" / "pre-commit").read_text()
    assert first == second


def test_install_hooks_chains_existing(tmp_path: Path) -> None:
    _init_git(tmp_path)
    existing = tmp_path / ".git" / "hooks" / "pre-commit"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("#!/bin/sh\necho legacy\n", encoding="utf-8")
    git_hooks.install_hooks(tmp_path)
    content = existing.read_text()
    assert "plugin_forge.git_hooks" in content
    assert "legacy" in content


def test_pre_commit_passes_when_no_forge_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert git_hooks.pre_commit() == 0


def test_pre_commit_passes_when_clean(sample_spec: ForgeSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    render_all(sample_spec, tmp_path)
    assert sync.check(sample_spec, tmp_path).is_clean
    monkeypatch.chdir(tmp_path)
    assert git_hooks.pre_commit() == 0


def test_pre_commit_blocks_on_drift(sample_spec: ForgeSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    monkeypatch.chdir(tmp_path)
    assert git_hooks.pre_commit() == 1
    err = capsys.readouterr().err
    assert "BLOCK" in err
