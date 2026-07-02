from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from plugin_forge.hooks import _safe


def test_guard_catches_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_safe, "LOG_DIR", tmp_path)
    monkeypatch.setattr(_safe, "ERROR_LOG", tmp_path / "errors.log")

    def _boom() -> None:
        raise RuntimeError("nope")

    exit_code = _safe.guard(_boom)
    assert exit_code == 0
    assert (tmp_path / "errors.log").exists()
    assert "RuntimeError" in (tmp_path / "errors.log").read_text()


def test_guard_returns_zero_on_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_safe, "LOG_DIR", tmp_path)
    exit_code = _safe.guard(lambda: None)
    assert exit_code == 0


def test_guard_propagates_system_exit_code() -> None:
    def _sysexit() -> None:
        raise SystemExit(3)

    assert _safe.guard(_sysexit) == 3


def test_emit_banner_writes_stdout() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        _safe.emit_banner("hello")
    assert "[forge] hello" in buf.getvalue()


def test_emit_banner_noop_on_empty() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        _safe.emit_banner("")
    assert buf.getvalue() == ""


def test_cwd_from_env_reads_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert _safe.cwd_from_env() == tmp_path.resolve()
