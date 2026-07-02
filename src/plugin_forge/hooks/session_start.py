"""SessionStart hook.

If cwd is inside a plugin repo, print a compact status banner. Auto-fix
drifted manifests silently and note the fix in the banner. Never prompts.
"""

from __future__ import annotations

import sys

from plugin_forge.hooks._safe import cwd_from_env, emit_banner, guard
from plugin_forge.spec import ForgeSpec


def _run() -> None:
    from plugin_forge import status, sync

    cwd = cwd_from_env()
    st = status.probe(cwd)
    if not st.is_plugin_repo:
        return

    if st.has_forge_yaml and st.drift:
        try:
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
