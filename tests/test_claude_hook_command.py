"""Claude Code runs a plugin hook's `command` and nothing else.

`commandWindows` is a Codex field. Claude Code runs `command` through `sh -c`
on macOS and Linux and through Git Bash on Windows, so these tests run the
rendered strings through that same shell. On Windows `python3` is often only
the Microsoft Store stub, which prints "Python was not found" and exits 49.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from plugin_forge.adapters._common import render_hook_entries
from plugin_forge.spec import ForgeSpec, HookSurface, InstallTargets, Provider, Surfaces

ROOT = Path(__file__).resolve().parents[1]
STORE_STUB = "#!/bin/sh\necho 'Python was not found' >&2\nexit 49\n"


def claude_shell() -> list[str] | None:
    """The shell Claude Code hands a hook's `command` to on this platform."""
    if os.name != "nt":
        sh = shutil.which("sh")
        return [sh, "-c"] if sh else None
    git = shutil.which("git")
    if git is None:
        return None
    for parent in Path(git).resolve().parents:
        candidate = parent / "bin" / "bash.exe"
        if candidate.is_file():
            return [str(candidate), "-c"]
    return None


def write_script(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def store_stubs(folder: Path) -> Path:
    for name in ("python3", "python"):
        write_script(folder / name, STORE_STUB)
    return folder


def hook_spec() -> ForgeSpec:
    return ForgeSpec(
        name="hooky",
        version="0.1.0",
        providers=[Provider.CLAUDE, Provider.CODEX],
        surfaces=Surfaces(
            hooks=[
                HookSurface(
                    event="PreToolUse",
                    script="hooks/pre_tool_use.py",
                    args={Provider.CLAUDE: ["PreToolUse", "--provider", "claude"]},
                )
            ]
        ),
        install=InstallTargets(claude="~/.claude/plugins/hooky/", codex="~/.codex/plugins/hooky/"),
    )


def claude_commands(hooks_json: Path) -> dict[str, dict[str, object]]:
    hooks = json.loads(hooks_json.read_text(encoding="utf-8"))["hooks"]
    return {event: groups[0]["hooks"][0] for event, groups in hooks.items()}


def test_claude_hooks_carry_no_command_windows() -> None:
    # Claude would ignore it; only Codex keeps a PowerShell variant.
    (claude_entry,) = render_hook_entries(hook_spec(), Provider.CLAUDE)
    assert "commandWindows" not in claude_entry
    (codex_entry,) = render_hook_entries(hook_spec(), Provider.CODEX)
    assert "commandWindows" in codex_entry
    for event, hook in claude_commands(ROOT / "hooks" / "hooks.json").items():
        assert "commandWindows" not in hook, event


def test_claude_hook_finds_uv_in_its_default_location(tmp_path: Path) -> None:
    # A host started before uv joined PATH, or a GUI host with a short PATH,
    # does not see uv; the standalone installer puts it in ~/.local/bin.
    shell = claude_shell()
    if shell is None:
        pytest.skip("no POSIX shell (Git Bash on Windows) to run the hook command")
    (claude_entry,) = render_hook_entries(hook_spec(), Provider.CLAUDE)
    home = tmp_path / "home"
    record = tmp_path / "uv-args.txt"
    write_script(home / ".local" / "bin" / "uv", '#!/bin/sh\nprintf "%s\\n" "$@" > "$UV_ARGS_OUT"\n')
    plugin_root = str(tmp_path / "plugin")
    env = {key: value for key, value in os.environ.items() if key.upper() not in {"PATH", "HOME"}}
    env.update(
        PATH=str(store_stubs(tmp_path / "stub")),
        HOME=str(home),
        CLAUDE_PLUGIN_ROOT=plugin_root,
        UV_ARGS_OUT=str(record),
    )
    completed = subprocess.run(
        [*shell, str(claude_entry["command"])], env=env, capture_output=True, text=True, timeout=60
    )
    assert completed.returncode == 0, completed.stderr
    assert record.read_text(encoding="utf-8").splitlines() == [
        "run",
        "--project",
        plugin_root,
        "python",
        f"{plugin_root}/hooks/pre_tool_use.py",
        "PreToolUse",
        "--provider",
        "claude",
    ]


def test_repository_claude_hooks_run_without_python3(tmp_path: Path) -> None:
    shell = claude_shell()
    if shell is None:
        pytest.skip("no POSIX shell (Git Bash on Windows) to run the hook command")
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH")
    cache = subprocess.run([uv, "cache", "dir"], capture_output=True, text=True, timeout=60).stdout.strip()
    home = tmp_path / "home"
    home.mkdir()
    env = {key: value for key, value in os.environ.items() if key.upper() not in {"HOME", "USERPROFILE"}}
    env.pop("PLUGIN_ROOT", None)
    env.update(
        PATH=str(store_stubs(tmp_path / "stub")) + os.pathsep + os.environ.get("PATH", ""),
        HOME=str(home),
        USERPROFILE=str(home),
        UV_CACHE_DIR=cache,
        CLAUDE_PLUGIN_ROOT=str(ROOT),
        CLAUDE_PROJECT_DIR=str(ROOT),
    )
    for event, hook in claude_commands(ROOT / "hooks" / "hooks.json").items():
        completed = subprocess.run(
            [*shell, str(hook["command"])],
            input=json.dumps({"hook_event_name": event, "cwd": str(ROOT), "prompt": "hi"}),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert completed.returncode == 0, f"{event}: {completed.stderr}"
        if event == "UserPromptSubmit":
            # This repository is a forge plugin, so the prompt hook reports on it.
            assert "<plugin-forge>" in completed.stdout, completed.stdout
