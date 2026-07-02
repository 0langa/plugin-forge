from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from plugin_forge.adapters import render_all
from plugin_forge.hooks import _safe, post_tool_use, session_start, user_prompt_submit
from plugin_forge.spec import ForgeSpec


@pytest.fixture(autouse=True)
def isolate_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_safe, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(_safe, "ERROR_LOG", tmp_path / "logs" / "errors.log")


def test_session_start_silent_when_not_plugin_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    buf = io.StringIO()
    with redirect_stdout(buf):
        session_start._run()
    assert buf.getvalue() == ""


def test_session_start_prints_banner_when_plugin_repo(
    sample_spec: ForgeSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    render_all(sample_spec, tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    buf = io.StringIO()
    with redirect_stdout(buf):
        session_start._run()
    assert sample_spec.name in buf.getvalue()


def test_user_prompt_submit_injects_context_block(
    sample_spec: ForgeSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    render_all(sample_spec, tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    buf = io.StringIO()
    with redirect_stdout(buf):
        user_prompt_submit._run()
    out = buf.getvalue()
    assert "<plugin-forge>" in out
    assert "</plugin-forge>" in out
    assert sample_spec.name in out


def test_post_tool_use_ignores_unrelated_edits(
    sample_spec: ForgeSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    render_all(sample_spec, tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = json.dumps(
        {"tool_name": "Edit", "tool_input": {"file_path": "README.md"}}
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    buf = io.StringIO()
    with redirect_stdout(buf):
        post_tool_use._run()
    assert buf.getvalue() == ""


def test_post_tool_use_recompiles_on_manifest_edit(
    sample_spec: ForgeSpec, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample_spec.dump(tmp_path / "forge.yaml")
    render_all(sample_spec, tmp_path)

    kimi_path = tmp_path / "kimi.plugin.json"
    payload_data = json.loads(kimi_path.read_text())
    payload_data["version"] = "9.9.9"
    kimi_path.write_text(json.dumps(payload_data, indent=2), encoding="utf-8")

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    stdin_payload = json.dumps(
        {"tool_name": "Edit", "tool_input": {"file_path": str(kimi_path)}}
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_payload))
    buf = io.StringIO()
    with redirect_stdout(buf):
        post_tool_use._run()
    assert "recompiled" in buf.getvalue()
    restored = json.loads(kimi_path.read_text())
    assert restored["version"] == sample_spec.version
