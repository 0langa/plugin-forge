"""Smoke tests for MCP tool functions by importing them directly.

We don't spin up a real MCP client; each tool is a plain Python function
inside a FastMCP decorator. We import the module and call the underlying
callables via the tool registry.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plugin_forge import mcp_server
from plugin_forge.adapters import render_all
from plugin_forge.spec import ForgeSpec


def test_status_tool_reports_plugin_repo(
    sample_spec: ForgeSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    render_all(sample_spec, tmp_path)
    result = mcp_server.status_tool(path=str(tmp_path))
    assert result["is_plugin_repo"] is True
    assert result["name"] == sample_spec.name


def test_status_tool_skips_git_by_default(
    sample_spec: ForgeSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    render_all(sample_spec, tmp_path)

    def fail_if_called(_repo: Path) -> tuple[str | None, bool]:
        raise AssertionError("hosted MCP status must not spawn Git by default")

    monkeypatch.setattr(mcp_server.status, "_git_state", fail_if_called)
    result = mcp_server.status_tool(path=str(tmp_path))

    assert result["git_branch"] is None
    assert result["git_dirty"] is False
    assert "git state omitted" in result["notes"]


def test_compile_tool_writes_manifests(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    result = mcp_server.compile(path=str(tmp_path))
    assert result["name"] == sample_spec.name
    for provider_key in ("claude", "codex", "kimi"):
        assert provider_key in result["written"]


def test_import_repo_tool_produces_spec(
    sample_spec: ForgeSpec, tmp_path: Path
) -> None:
    render_all(sample_spec, tmp_path)
    result = mcp_server.import_repo(path=str(tmp_path), write=False)
    assert result["wrote"] is None
    assert result["spec"]["name"] == sample_spec.name


def test_sync_check_tool_reports_drift(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    result = mcp_server.sync_check(path=str(tmp_path), fix=False)
    assert result["clean"] is False
    assert result["drift"]


def test_sync_check_fix_resolves_drift(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    result = mcp_server.sync_check(path=str(tmp_path), fix=True)
    assert result["clean"] is True


def test_bump_version_tool_propagates(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    render_all(sample_spec, tmp_path)
    result = mcp_server.bump_version(path=str(tmp_path), level="patch")
    assert result["new"] != result["old"]


def test_bump_version_rejects_bad_level(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    with pytest.raises(ValueError):
        mcp_server.bump_version(path=str(tmp_path), level="huge")
