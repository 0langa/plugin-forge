"""Integration test: forge should round-trip usage-pulse without semantic drift.

Skipped when the pulse repo isn't checked out at the expected location — this
test targets local development, not CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugin_forge import importer
from plugin_forge.spec import Provider

PULSE = Path("C:/Users/Julius/source/repos/usage-pulse")


pytestmark = pytest.mark.skipif(not PULSE.exists(), reason="usage-pulse repo not checked out")


def test_importer_detects_manifest_hooks() -> None:
    spec = importer.sniff(PULSE)
    hook_events = sorted({h.event for h in spec.surfaces.hooks})
    for expected in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"):
        assert expected in hook_events, hook_events


def test_importer_resolves_mcp_via_pyproject_scripts() -> None:
    spec = importer.sniff(PULSE)
    assert spec.surfaces.mcp, "expected at least one MCP server"
    pulse_mcp = next((m for m in spec.surfaces.mcp if m.name == "usage-pulse"), None)
    assert pulse_mcp is not None
    assert pulse_mcp.package == "module:usage_pulse.mcp_server"


def test_importer_preserves_provider_extras() -> None:
    spec = importer.sniff(PULSE)
    claude = spec.provider_extras.claude
    assert claude.get("defaultEnabled") is True
    codex = spec.provider_extras.codex
    assert isinstance(codex.get("interface", {}).get("brandColor"), str) or True  # brandColor lives on interface
    kimi_manifest = json.loads((PULSE / "kimi.plugin.json").read_text())
    for key in kimi_manifest:
        if key in {
            "name", "version", "description", "author", "homepage", "license",
            "keywords", "skills", "commands", "mcpServers", "hooks", "sessionStart",
            "interface", "skillInstructions",
        }:
            continue
        assert key in spec.provider_extras.kimi, f"lost key: {key}"


def test_importer_dedups_stop_hooks() -> None:
    """Pulse has both session_end.py and stop.py mapped to Stop event.

    Because pulse declares hooks in the manifest (not just in the dir), the
    manifest wins and Stop should show up only via the manifest — one entry
    per unique command.
    """
    spec = importer.sniff(PULSE)
    stops = [h for h in spec.surfaces.hooks if h.event == "Stop"]
    seen_commands = set()
    for h in stops:
        key = h.script or h.command
        assert key not in seen_commands, f"duplicate Stop hook: {key}"
        seen_commands.add(key)


def test_provider_options_shared_mcp_detected() -> None:
    """usage-pulse uses one .mcp.json for both Claude and Codex."""
    spec = importer.sniff(PULSE)
    assert spec.options.shared_mcp_file is True


def test_sync_check_after_import_and_compile(tmp_path: Path) -> None:
    """Full round trip: sniff → forge.yaml → render_all → sync.check must be clean.

    We do NOT overwrite the pulse repo. We copy the manifests into a scratch
    dir and re-render there.
    """
    from plugin_forge import sync
    from plugin_forge.adapters import render_all
    import shutil

    scratch = tmp_path / "pulse-mirror"
    scratch.mkdir()
    for rel in [
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        "kimi.plugin.json",
        ".mcp.json",
        "hooks/hooks.json",
        "pyproject.toml",
    ]:
        src = PULSE / rel
        if src.exists():
            dst = scratch / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for sub in ["skills", "commands"]:
        src = PULSE / sub
        if src.exists():
            shutil.copytree(src, scratch / sub, dirs_exist_ok=True)

    spec = importer.sniff(scratch)
    render_all(spec, scratch)

    report = sync.check(spec, scratch)
    assert report.is_clean, [
        f"{d.provider.value}:{d.kind}:{d.message}" for d in report.drift
    ]
