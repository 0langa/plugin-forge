"""UserPromptSubmit hook.

Inject curated plugin-state context so the model reasons with fresh drift +
marketplace + version data without the user having to remind it. Silent unless
the current repo is a plugin repo with something worth surfacing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plugin_forge.hooks._safe import cwd_from_payload_or_env, guard


def _run() -> None:
    from plugin_forge import status

    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except Exception:
        payload = {}
    cwd = cwd_from_payload_or_env(payload)
    if cwd is None:
        return
    st = status.probe(cwd)
    if not st.is_plugin_repo or not st.has_forge_yaml:
        return

    lines: list[str] = []
    header = f"plugin-forge context: {st.name} v{st.version}"
    installed = "+".join(st.installed_providers) if st.installed_providers else "none"
    lines.append(f"{header}; declared providers: {'+'.join(st.providers)}; installed: {installed}")

    if st.drift:
        drift_summary = "; ".join(
            f"{d['provider']}: {d['kind']}" for d in st.drift
        )
        lines.append(f"drift: {drift_summary}")

    if st.marketplace_synced is False:
        for note in st.marketplace_notes:
            lines.append(f"marketplace: {note}")

    if st.git_dirty:
        lines.append("git working tree dirty")

    if not lines:
        return

    print("<plugin-forge>")
    for line in lines:
        print(line)
    print("</plugin-forge>")


if __name__ == "__main__":
    sys.exit(guard(_run))
