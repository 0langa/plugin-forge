"""Canonical `forge.yaml` schema.

Single source of truth for a plugin's topology across Claude Code, Codex, and
Kimi Code. Adapter modules translate a `ForgeSpec` into provider-specific
manifests. All other subsystems (install, sync, bump, release) operate on
`ForgeSpec` instances rather than raw dicts.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Provider(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"
    KIMI = "kimi"


class SurfaceKind(StrEnum):
    SKILL = "skill"
    COMMAND = "command"
    AGENT = "agent"
    HOOK = "hook"
    MCP = "mcp"


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SkillSurface(_Base):
    name: str
    path: str
    providers: list[Provider] | None = None


class CommandSurface(_Base):
    name: str
    path: str
    providers: list[Provider] | None = None


class AgentSurface(_Base):
    name: str
    path: str
    providers: list[Provider] | None = None


class HookSurface(_Base):
    """Hook surface.

    Either `script` (path to a Python file relative to the repo root — forge
    renders it into the provider's expected command shape) or `command` (a
    raw shell command; passed through verbatim) must be given.
    """

    event: str
    script: str | None = None
    command: str | None = None
    providers: list[Provider] | None = None
    matcher: str | None = None
    matchers: dict[Provider, str] = Field(default_factory=dict)
    args: dict[Provider, list[str]] = Field(default_factory=dict)
    status_message: str | None = None
    timeout_seconds: int | None = None

    @model_validator(mode="after")
    def _script_or_command(self) -> HookSurface:
        if not self.script and not self.command:
            raise ValueError("hook must define either script or command")
        return self


class McpSurface(_Base):
    name: str
    transport: str = "stdio"
    package: str
    env: list[str] = Field(default_factory=list)
    args: list[str] = Field(default_factory=list)
    providers: list[Provider] | None = None


class Surfaces(_Base):
    skills: list[SkillSurface] = Field(default_factory=list)
    commands: list[CommandSurface] = Field(default_factory=list)
    agents: list[AgentSurface] = Field(default_factory=list)
    hooks: list[HookSurface] = Field(default_factory=list)
    mcp: list[McpSurface] = Field(default_factory=list)


class InstallTargets(_Base):
    claude: str | None = None
    codex: str | None = None
    kimi: str | None = None

    def for_provider(self, provider: Provider) -> str | None:
        return cast(str | None, getattr(self, provider.value))


class Marketplace(_Base):
    claude_manifest: str | None = None
    kimi_manifest: str | None = None


class ProviderExtras(_Base):
    """Passthrough bucket for provider-specific manifest keys forge does not
    model explicitly (e.g. `defaultEnabled`, `brandColor`, `capabilities`).

    Keys here are merged into the emitted provider manifest verbatim.
    Preserves round-trip fidelity for hand-tuned manifests.
    """

    claude: dict[str, Any] = Field(default_factory=dict)
    codex: dict[str, Any] = Field(default_factory=dict)
    kimi: dict[str, Any] = Field(default_factory=dict)

    def for_provider(self, provider: Provider) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, provider.value))


class Options(_Base):
    shared_mcp_file: bool = False
    """If true, Claude and Codex share a single `.mcp.json` file at the repo
    root. If false (default), each provider gets its own file."""


class ForgeSpec(_Base):
    """Root schema."""

    name: str
    version: str
    description: str | None = None
    providers: list[Provider]
    surfaces: Surfaces = Field(default_factory=Surfaces)
    install: InstallTargets = Field(default_factory=InstallTargets)
    settings_patches: dict[str, Any] = Field(default_factory=dict)
    marketplace: Marketplace = Field(default_factory=Marketplace)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provider_extras: ProviderExtras = Field(default_factory=ProviderExtras)
    options: Options = Field(default_factory=Options)

    @field_validator("providers")
    @classmethod
    def _providers_unique(cls, v: list[Provider]) -> list[Provider]:
        if not v:
            raise ValueError("providers must list at least one provider")
        if len(set(v)) != len(v):
            raise ValueError("providers list contains duplicates")
        return v

    @model_validator(mode="after")
    def _cross_check(self) -> ForgeSpec:
        declared: set[Provider] = set(self.providers)
        surface_groups: list[tuple[list[Any], str]] = [
            (self.surfaces.skills, "skill"),
            (self.surfaces.commands, "command"),
            (self.surfaces.agents, "agent"),
            (self.surfaces.hooks, "hook"),
            (self.surfaces.mcp, "mcp"),
        ]
        for surface_list, kind in surface_groups:
            for surface in surface_list:
                sub = getattr(surface, "providers", None)
                if sub is None:
                    continue
                unknown: set[Provider] = set(sub) - declared
                if unknown:
                    raise ValueError(
                        f"{kind} surface targets undeclared providers: "
                        f"{sorted(p.value for p in unknown)}"
                    )
        return self

    @classmethod
    def load(cls, path: str | Path) -> ForgeSpec:
        p = Path(path)
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"{p} did not parse to a mapping")
        return cls.model_validate(data)

    def dump(self, path: str | Path) -> None:
        p = Path(path)
        data = self.model_dump(mode="json", exclude_none=True)
        with p.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)

    def has_surface(self, kind: SurfaceKind) -> bool:
        return {
            SurfaceKind.SKILL: bool(self.surfaces.skills),
            SurfaceKind.COMMAND: bool(self.surfaces.commands),
            SurfaceKind.AGENT: bool(self.surfaces.agents),
            SurfaceKind.HOOK: bool(self.surfaces.hooks),
            SurfaceKind.MCP: bool(self.surfaces.mcp),
        }[kind]

    def surfaces_for_provider(self, provider: Provider) -> Surfaces:
        """Return only surfaces enabled for the given provider."""

        def _keep(sub: list[Provider] | None) -> bool:
            return sub is None or provider in sub

        return Surfaces(
            skills=[s for s in self.surfaces.skills if _keep(s.providers)],
            commands=[c for c in self.surfaces.commands if _keep(c.providers)],
            agents=[a for a in self.surfaces.agents if _keep(a.providers)],
            hooks=[h for h in self.surfaces.hooks if _keep(h.providers)],
            mcp=[m for m in self.surfaces.mcp if _keep(m.providers)],
        )
