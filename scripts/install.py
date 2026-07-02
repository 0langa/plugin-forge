#!/usr/bin/env python
"""Install plugin-forge itself into every provider.

Bootstraps forge: uses forge's own installer to install forge into
~/.claude/plugins/plugin-forge, ~/.codex/plugins/plugin-forge, and
~/.kimi-code/plugins/plugin-forge, and to register its MCP + hooks in each
provider's settings.json.

Run from the forge repo root:
    python scripts/install.py --mode link
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plugin_forge import installer  # noqa: E402
from plugin_forge.adapters import render_all  # noqa: E402
from plugin_forge.installer import Mode  # noqa: E402
from plugin_forge.spec import ForgeSpec, Provider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="all", choices=["all", "claude", "codex", "kimi"])
    parser.add_argument("--mode", default="link", choices=["link", "copy"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    forge_yaml = repo / "forge.yaml"
    spec = ForgeSpec.load(forge_yaml)

    render_all(spec, repo)

    providers = list(spec.providers) if args.provider == "all" else [Provider(args.provider)]
    for prov in providers:
        report = installer.install(spec, repo, prov, mode=Mode(args.mode), dry_run=args.dry_run)
        print(
            f"[{prov.value}] target={report.target} mode={report.mode.value} "
            f"settings_patched={report.settings_patched}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
