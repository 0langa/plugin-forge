from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tracked_files_do_not_expose_private_windows_identity() -> None:
    private_name = "Ju" + "lius"
    forbidden = (
        private_name.casefold(),
        f"c:/users/{private_name}".casefold(),
        f"c:\\users\\{private_name}".casefold(),
    )
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")

    leaks: list[str] = []
    for raw_path in tracked:
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8")
        data = (ROOT / relative).read_bytes()
        if b"\0" in data:
            continue
        text = data.decode("utf-8", errors="replace").casefold()
        if any(value in text for value in forbidden):
            leaks.append(relative)

    assert leaks == []
