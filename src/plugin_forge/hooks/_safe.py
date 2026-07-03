"""Shared hook safety net.

Every hook wraps its body in `guard()`. On any exception, the traceback is
appended to `~/.plugin-forge/errors.log` and the hook exits 0. Host sessions
must never break because of forge.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

LOG_DIR = Path.home() / ".plugin-forge"
ERROR_LOG = LOG_DIR / "errors.log"

T = TypeVar("T")


def guard(fn: Callable[[], T]) -> int:
    try:
        fn()
        return 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except BaseException:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with ERROR_LOG.open("a", encoding="utf-8") as f:
                f.write(f"\n=== {time.strftime('%Y-%m-%dT%H:%M:%S')} {sys.argv[0]} ===\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        return 0


def cwd_from_env() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()


def cwd_from_payload_or_env(payload: dict[str, Any] | None = None) -> Path | None:
    payload = payload or {}
    for key in ("cwd", "project_dir", "projectDir", "workspace", "workspace_dir"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return Path(value).resolve()

    env_value = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_value:
        return Path(env_value).resolve()

    cwd = Path(os.getcwd()).resolve()
    plugin_roots = {
        os.environ.get("KIMI_PLUGIN_ROOT"),
        os.environ.get("PLUGIN_ROOT"),
        os.environ.get("CLAUDE_PLUGIN_ROOT"),
    }
    for root in plugin_roots:
        if root and cwd == Path(root).resolve():
            return None
    return cwd


def emit_banner(text: str) -> None:
    if not text:
        return
    print(f"[forge] {text}")
