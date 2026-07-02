from __future__ import annotations

from pathlib import Path

import pytest

from plugin_forge.spec import ForgeSpec, Provider


def test_load_dump_roundtrip(sample_spec: ForgeSpec, tmp_path: Path) -> None:
    p = tmp_path / "forge.yaml"
    sample_spec.dump(p)
    reloaded = ForgeSpec.load(p)
    assert reloaded == sample_spec


def test_duplicate_providers_rejected() -> None:
    with pytest.raises(ValueError):
        ForgeSpec(
            name="x",
            version="0.1.0",
            providers=[Provider.CLAUDE, Provider.CLAUDE],
        )


def test_surface_targets_undeclared_provider_rejected() -> None:
    with pytest.raises(ValueError):
        ForgeSpec.model_validate(
            {
                "name": "x",
                "version": "0.1.0",
                "providers": ["claude"],
                "surfaces": {
                    "skills": [{"name": "s", "path": "s.md", "providers": ["kimi"]}]
                },
            }
        )


def test_surfaces_for_provider_filters(sample_spec: ForgeSpec) -> None:
    active = sample_spec.surfaces_for_provider(Provider.CLAUDE)
    assert len(active.skills) == 1
