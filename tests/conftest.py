from __future__ import annotations

from pathlib import Path

import pytest

from plugin_forge.spec import (
    ForgeSpec,
    HookSurface,
    InstallTargets,
    Marketplace,
    McpSurface,
    Provider,
    SkillSurface,
    Surfaces,
)


@pytest.fixture
def sample_spec() -> ForgeSpec:
    return ForgeSpec(
        name="demo",
        version="0.3.1",
        description="demo plugin",
        providers=[Provider.CLAUDE, Provider.CODEX, Provider.KIMI],
        surfaces=Surfaces(
            skills=[SkillSurface(name="do-thing", path="skills/do-thing/SKILL.md")],
            hooks=[HookSurface(event="SessionStart", script="hooks/session_start.py")],
            mcp=[McpSurface(name="demo", package="module:demo.mcp_server", env=["DEMO_HOME"])],
        ),
        install=InstallTargets(
            claude="~/.claude/plugins/demo/",
            codex="~/.codex/plugins/demo/",
            kimi="~/.kimi-code/plugins/demo/",
        ),
        marketplace=Marketplace(),
        metadata={"author": "0langa", "license": "MIT", "homepage": "https://example.com"},
    )


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    (tmp_path / "skills" / "do-thing").mkdir(parents=True)
    (tmp_path / "skills" / "do-thing" / "SKILL.md").write_text("---\nname: do-thing\n---\nbody", encoding="utf-8")
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "session_start.py").write_text("print('ok')\n", encoding="utf-8")
    return tmp_path
