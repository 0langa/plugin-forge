"""Provider manifest adapters.

Each adapter renders a `ForgeSpec` into the shape a specific provider expects.
Shapes verified against production plugins in `0langas-plugin-marketplace`
(agent-handoff, RECALL) as of 2026-07.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plugin_forge.spec import ForgeSpec, Provider

from .claude import render_claude
from .codex import render_codex
from .kimi import render_kimi

__all__ = ["render_all", "render_for_provider", "render_claude", "render_codex", "render_kimi"]


def render_for_provider(spec: ForgeSpec, provider: Provider) -> dict[str, Any]:
    if provider is Provider.CLAUDE:
        return render_claude(spec)
    if provider is Provider.CODEX:
        return render_codex(spec)
    if provider is Provider.KIMI:
        return render_kimi(spec)
    raise ValueError(f"unknown provider: {provider}")


def render_all(spec: ForgeSpec, out_root: Path) -> dict[Provider, Path]:
    """Write manifests for every declared provider under `out_root`.

    Returns the map of provider → written file path.
    """
    from .claude import write_claude
    from .codex import write_codex
    from .kimi import write_kimi

    out_root.mkdir(parents=True, exist_ok=True)
    result: dict[Provider, Path] = {}
    if Provider.CLAUDE in spec.providers:
        result[Provider.CLAUDE] = write_claude(spec, out_root)
    if Provider.CODEX in spec.providers:
        result[Provider.CODEX] = write_codex(spec, out_root)
    if Provider.KIMI in spec.providers:
        result[Provider.KIMI] = write_kimi(spec, out_root)
    return result
