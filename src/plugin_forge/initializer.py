"""New-plugin bootstrap helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from plugin_forge.spec import ForgeSpec, InstallTargets, Provider


@dataclass(frozen=True)
class InitResult:
    repo: Path
    forge_yaml: Path
    created_dirs: list[Path]
    spec: ForgeSpec


def create(
    repo: Path,
    name: str,
    providers: list[Provider],
    *,
    description: str | None = None,
    force: bool = False,
) -> InitResult:
    repo = repo.resolve()
    repo.mkdir(parents=True, exist_ok=True)
    forge_yaml = repo / "forge.yaml"
    if forge_yaml.exists() and not force:
        raise FileExistsError(f"forge.yaml already exists at {forge_yaml}")

    spec = ForgeSpec(
        name=name,
        version="0.1.0",
        description=description,
        providers=providers,
        install=InstallTargets(
            claude=f"~/.claude/plugins/{name}/" if Provider.CLAUDE in providers else None,
            codex=f"~/.codex/plugins/{name}/" if Provider.CODEX in providers else None,
            kimi=f"~/.kimi-code/plugins/managed/{name}/" if Provider.KIMI in providers else None,
        ),
        metadata={
            "author": "0langa",
            "license": "MIT",
            "interface": {
                "display_name": _title(name),
                "short_description": description or f"{_title(name)} plugin.",
            },
        },
    )
    spec.dump(forge_yaml)

    created_dirs: list[Path] = []
    for rel in ("skills", "commands", "hooks", "assets", "src"):
        path = repo / rel
        path.mkdir(exist_ok=True)
        created_dirs.append(path)

    return InitResult(repo=repo, forge_yaml=forge_yaml, created_dirs=created_dirs, spec=spec)


def parse_providers(value: str) -> list[Provider]:
    raw = [part.strip() for part in value.split(",") if part.strip()]
    if raw == ["all"]:
        return [Provider.CLAUDE, Provider.CODEX, Provider.KIMI]
    providers = [Provider(part) for part in raw]
    if len(set(providers)) != len(providers):
        raise ValueError("providers list contains duplicates")
    return providers


def _title(name: str) -> str:
    return " ".join(part.capitalize() for part in name.replace("_", "-").split("-"))
