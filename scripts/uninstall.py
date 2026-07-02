#!/usr/bin/env python
"""Uninstall plugin-forge from every provider.

Removes files at each provider's install target and reverses the settings.json
patches using the install receipts stored under ~/.plugin-forge/receipts/.

Run from the forge repo root:
    python scripts/uninstall.py --provider all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from plugin_forge import installer  # noqa: E402
from plugin_forge.spec import ForgeSpec, Provider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="all", choices=["all", "claude", "codex", "kimi"])
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    spec = ForgeSpec.load(repo / "forge.yaml")
    providers = list(spec.providers) if args.provider == "all" else [Provider(args.provider)]
    for prov in providers:
        ok = installer.uninstall(spec, prov)
        print(f"[{prov.value}] {'removed' if ok else 'nothing to remove'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
