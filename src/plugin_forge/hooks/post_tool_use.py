"""PostToolUse hook.

If the last tool touched a manifest / hook / MCP source / skill body inside a
plugin repo, silently recompile provider manifests. Stay quiet unless a fix
was applied.

Payload arrives on stdin as JSON. Fields used (best-effort — schema differs
per host):
    tool_name  — the tool that just ran
    tool_input — usually contains a `file_path`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plugin_forge.hooks._safe import cwd_from_payload_or_env, emit_banner, guard

WATCHED_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
TRIGGER_SUFFIXES = (
    "forge.yaml",
    "pyproject.toml",
    "kimi.plugin.json",
    "plugin.json",
    ".mcp.json",
    ".codex-mcp.json",
    "SKILL.md",
)
TRIGGER_DIRS = ("hooks/", "skills/", "commands/", "agents/", "manifests/")


def _run() -> None:
    from plugin_forge import status, sync
    from plugin_forge.spec import ForgeSpec

    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except Exception:
        payload = {}

    tool = payload.get("tool_name") or ""
    if tool and tool not in WATCHED_TOOLS:
        return

    file_path = _extract_path(payload)
    if not _is_trigger_path(file_path):
        return

    cwd = cwd_from_payload_or_env(payload)
    if cwd is None:
        return
    st = status.probe(cwd)
    if not st.is_plugin_repo or not st.has_forge_yaml:
        return

    try:
        spec = ForgeSpec.load(st.repo / "forge.yaml")
    except Exception as exc:
        emit_banner(f"forge.yaml invalid, skipping auto-compile: {exc}")
        return

    report = sync.check(spec, st.repo)
    if report.is_clean:
        return

    fixed = sync.fix(spec, st.repo)
    if fixed.fixed:
        emit_banner(f"recompiled {len(fixed.fixed)} manifest(s) after edit")


def _extract_path(payload: dict[str, Any]) -> str:
    ti = payload.get("tool_input") or {}
    if isinstance(ti, dict):
        return str(ti.get("file_path") or ti.get("path") or "")
    return ""


def _is_trigger_path(p: str) -> bool:
    if not p:
        return False
    lower = p.replace("\\", "/").lower()
    if any(lower.endswith(s.lower()) for s in TRIGGER_SUFFIXES):
        return True
    return any(f"/{d.lower()}" in lower for d in TRIGGER_DIRS)


if __name__ == "__main__":
    sys.exit(guard(_run))
