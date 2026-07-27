"""SessionStart hook.

If cwd is inside a plugin repo, print a compact status banner. Auto-fix
drifted manifests silently and note the fix in the banner. Never prompts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plugin_forge.hooks._safe import cwd_from_payload_or_env, emit_banner, guard


def _run() -> None:
    from plugin_forge import status, sync

    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except Exception:
        payload = {}
    cwd = cwd_from_payload_or_env(payload)
    if cwd is None:
        return
    st = status.probe(cwd)
    if not st.is_plugin_repo:
        return

    if st.has_forge_yaml and st.drift:
        try:
            from plugin_forge.spec import ForgeSpec

            spec = ForgeSpec.load(st.repo / "forge.yaml")
            report = sync.fix(spec, st.repo)
            if report.fixed:
                st.drift = []
                st.notes.append(f"auto-fixed {len(report.fixed)} manifest(s)")
        except Exception:
            pass

    banner = st.banner()
    if banner:
        emit_banner(banner)
    for note in st.notes:
        emit_banner(note)


if __name__ == "__main__":
    sys.exit(guard(_run))
