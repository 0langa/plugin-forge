"""Retrofit an existing plugin repo into a `forge.yaml`.

Strategy: sniff conventional manifest paths, merge into a single ForgeSpec,
best-effort. Never mutates the source repo — only writes `forge.yaml` at the
repo root (or a path the caller chooses).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from plugin_forge.spec import (
    AgentSurface,
    CommandSurface,
    ForgeSpec,
    HookSurface,
    InstallTargets,
    Marketplace,
    McpSurface,
    Provider,
    SkillSurface,
    Surfaces,
)


def sniff(repo: Path) -> ForgeSpec:
    """Inspect a repo and return a ForgeSpec best-guess."""
    repo = repo.resolve()
    if not repo.is_dir():
        raise ValueError(f"{repo} is not a directory")

    claude_json = _read_json(repo / ".claude-plugin" / "plugin.json")
    codex_json = _read_json(repo / ".codex-plugin" / "plugin.json")
    kimi_json = _read_json(repo / "kimi.plugin.json")

    providers = []
    if claude_json is not None:
        providers.append(Provider.CLAUDE)
    if codex_json is not None:
        providers.append(Provider.CODEX)
    if kimi_json is not None:
        providers.append(Provider.KIMI)
    if not providers:
        providers = [Provider.CLAUDE]

    canonical = kimi_json or claude_json or codex_json or {}
    name = canonical.get("name") or repo.name
    version = _detect_version(repo, canonical)
    description = canonical.get("description")

    skills = _list_dir_surfaces(repo, "skills", _skill_from_dir)
    commands = _list_dir_surfaces(repo, "commands", _command_from_file)
    agents = _list_dir_surfaces(repo, "agents", _agent_from_file)
    hooks = _detect_hooks(repo, claude_json, codex_json, kimi_json)
    mcp = _detect_mcp(repo, claude_json, codex_json, kimi_json)

    metadata: dict[str, Any] = {}
    for src in (kimi_json, codex_json, claude_json):
        if not src:
            continue
        for k in ("author", "homepage", "repository", "license", "keywords"):
            if k in src and k not in metadata:
                metadata[k] = src[k]
        iface = src.get("interface")
        if iface and "interface" not in metadata:
            metadata["interface"] = _snakeify_interface(iface)
        session_start = src.get("sessionStart")
        if session_start and "session_start_skill" not in metadata:
            metadata["session_start_skill"] = session_start.get("skill")
        instructions = src.get("skillInstructions")
        if instructions and "skill_instructions" not in metadata:
            metadata["skill_instructions"] = instructions
    if "author" in metadata and isinstance(metadata["author"], dict):
        metadata["author"] = metadata["author"].get("name", "0langa")

    return ForgeSpec(
        name=name,
        version=version,
        description=description,
        providers=providers,
        surfaces=Surfaces(skills=skills, commands=commands, agents=agents, hooks=hooks, mcp=mcp),
        install=_guess_install(name),
        settings_patches={},
        marketplace=_guess_marketplace(repo, name),
        metadata=metadata,
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _detect_version(repo: Path, canonical: dict[str, Any]) -> str:
    if canonical.get("version"):
        return str(canonical["version"])
    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if m:
            return m.group(1)
    return "0.1.0"


def _list_dir_surfaces(repo: Path, subdir: str, factory: Any) -> list:
    base = repo / subdir
    if not base.is_dir():
        return []
    out: list = []
    for child in sorted(base.iterdir()):
        surface = factory(child)
        if surface is not None:
            out.append(surface)
    return out


def _skill_from_dir(path: Path) -> SkillSurface | None:
    if not path.is_dir():
        return None
    skill_md = path / "SKILL.md"
    if not skill_md.exists():
        return None
    return SkillSurface(name=path.name, path=str(skill_md.relative_to(path.parents[1])).replace("\\", "/"))


def _command_from_file(path: Path) -> CommandSurface | None:
    if not path.is_file() or path.suffix != ".md":
        return None
    return CommandSurface(
        name=path.stem, path=str(path.relative_to(path.parents[1])).replace("\\", "/")
    )


def _agent_from_file(path: Path) -> AgentSurface | None:
    if not path.is_file() or path.suffix != ".md":
        return None
    return AgentSurface(
        name=path.stem, path=str(path.relative_to(path.parents[1])).replace("\\", "/")
    )


def _detect_hooks(
    repo: Path,
    claude_json: dict[str, Any] | None,
    codex_json: dict[str, Any] | None,
    kimi_json: dict[str, Any] | None,
) -> list[HookSurface]:
    result: list[HookSurface] = []
    hooks_dir = repo / "hooks"
    if hooks_dir.is_dir():
        for f in sorted(hooks_dir.iterdir()):
            if not f.is_file() or f.suffix not in (".py", ".sh", ".ps1"):
                continue
            event = _event_from_filename(f.stem)
            result.append(
                HookSurface(
                    event=event, script=str(f.relative_to(repo)).replace("\\", "/")
                )
            )
    return result


def _event_from_filename(stem: str) -> str:
    mapping = {
        "session_start": "SessionStart",
        "sessionstart": "SessionStart",
        "pre_tool_use": "PreToolUse",
        "post_tool_use": "PostToolUse",
        "user_prompt_submit": "UserPromptSubmit",
        "session_end": "Stop",
        "stop": "Stop",
        "pre_compact": "PreCompact",
    }
    return mapping.get(stem.lower(), stem)


def _detect_mcp(
    repo: Path,
    claude_json: dict[str, Any] | None,
    codex_json: dict[str, Any] | None,
    kimi_json: dict[str, Any] | None,
) -> list[McpSurface]:
    servers: dict[str, dict[str, Any]] = {}
    for src in (kimi_json, claude_json, codex_json):
        if not src:
            continue
        raw = src.get("mcpServers")
        if isinstance(raw, dict):
            for name, cfg in raw.items():
                servers.setdefault(name, cfg)
        elif isinstance(raw, str):
            candidate = repo / raw.lstrip("./")
            data = _read_json(candidate)
            if isinstance(data, dict) and isinstance(data.get("mcpServers"), dict):
                for name, cfg in data["mcpServers"].items():
                    servers.setdefault(name, cfg)
    result: list[McpSurface] = []
    for name, cfg in servers.items():
        package = _guess_package(cfg)
        env = list(cfg.get("env", {}).keys()) if isinstance(cfg.get("env"), dict) else []
        result.append(McpSurface(name=name, transport="stdio", package=package, env=env))
    return result


def _guess_package(cfg: dict[str, Any]) -> str:
    args = cfg.get("args", [])
    if isinstance(args, list) and "-m" in args:
        idx = args.index("-m")
        if idx + 1 < len(args):
            return f"module:{args[idx + 1]}"
    if isinstance(args, list) and any(a.endswith(".py") for a in args if isinstance(a, str)):
        for a in args:
            if isinstance(a, str) and a.endswith(".py"):
                return f"python:{a}"
    return cfg.get("command", "python")


def _snakeify_interface(iface: dict[str, Any]) -> dict[str, Any]:
    key_map = {
        "displayName": "display_name",
        "shortDescription": "short_description",
        "longDescription": "long_description",
        "developerName": "developer_name",
        "websiteURL": "website_url",
        "privacyPolicyURL": "privacy_policy_url",
        "termsOfServiceURL": "terms_of_service_url",
        "defaultPrompt": "default_prompt",
    }
    return {key_map.get(k, k): v for k, v in iface.items()}


def _guess_install(name: str) -> InstallTargets:
    return InstallTargets(
        claude=f"~/.claude/plugins/{name}/",
        codex=f"~/.codex/plugins/{name}/",
        kimi=f"~/.kimi-code/plugins/{name}/",
    )


def _guess_marketplace(repo: Path, name: str) -> Marketplace:
    candidate = repo.parent.parent / "0langas-plugin-marketplace"
    if (candidate / "plugins.json").exists():
        return Marketplace(
            claude_manifest=str((candidate / "plugins.json").resolve()),
            kimi_manifest=str((candidate / "kimi-marketplace.json").resolve()),
        )
    return Marketplace()
