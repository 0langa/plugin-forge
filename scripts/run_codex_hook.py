from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

HOOKS = {
    "session_start": "session_start.py",
    "post_tool_use": "post_tool_use.py",
    "user_prompt_submit": "user_prompt_submit.py",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Plugin Forge Codex hook.")
    parser.add_argument("hook", choices=sorted(HOOKS))
    args = parser.parse_args()

    plugin_root = Path(__file__).resolve().parents[1]
    src = plugin_root / "src"
    sys.path.insert(0, str(src))
    runpy.run_path(str(src / "plugin_forge" / "hooks" / HOOKS[args.hook]), run_name="__main__")


if __name__ == "__main__":
    main()
