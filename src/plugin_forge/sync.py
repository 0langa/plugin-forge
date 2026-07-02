"""Parity check across providers.

Compares what's declared in `forge.yaml` against what would be emitted for each
provider, and against what's actually on disk. Reports drift; can auto-fix by
regenerating manifests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from plugin_forge.adapters import render_for_provider
from plugin_forge.spec import ForgeSpec, Provider


@dataclass
class DriftItem:
    provider: Provider
    kind: str
    message: str


@dataclass
class SyncReport:
    drift: list[DriftItem] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.drift


def check(spec: ForgeSpec, repo: Path) -> SyncReport:
    report = SyncReport()

    provider_files = {
        Provider.CLAUDE: repo / ".claude-plugin" / "plugin.json",
        Provider.CODEX: repo / ".codex-plugin" / "plugin.json",
        Provider.KIMI: repo / "kimi.plugin.json",
    }

    for provider, path in provider_files.items():
        declared = provider in spec.providers
        exists = path.exists()

        if declared and not exists:
            report.drift.append(
                DriftItem(provider=provider, kind="missing_manifest", message=str(path))
            )
            continue
        if not declared and exists:
            report.drift.append(
                DriftItem(
                    provider=provider,
                    kind="orphan_manifest",
                    message=f"{path} exists but provider not declared",
                )
            )
            continue
        if not declared:
            continue

        current = _load_json(path)
        expected = render_for_provider(spec, provider)
        if current != expected:
            report.drift.append(
                DriftItem(
                    provider=provider,
                    kind="manifest_drift",
                    message=_diff_summary(current, expected),
                )
            )
    return report


def fix(spec: ForgeSpec, repo: Path) -> SyncReport:
    from plugin_forge.adapters import render_all

    report = check(spec, repo)
    if report.is_clean:
        return report
    written = render_all(spec, repo)
    for provider, path in written.items():
        report.fixed.append(f"{provider.value}: {path}")
    report.drift = []
    return report


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _diff_summary(current: dict, expected: dict) -> str:
    cur_keys = set(current.keys())
    exp_keys = set(expected.keys())
    missing = sorted(exp_keys - cur_keys)
    extra = sorted(cur_keys - exp_keys)
    changed = sorted(k for k in cur_keys & exp_keys if current[k] != expected[k])
    parts = []
    if missing:
        parts.append(f"missing={missing}")
    if extra:
        parts.append(f"extra={extra}")
    if changed:
        parts.append(f"changed={changed}")
    return "; ".join(parts) or "differs"
