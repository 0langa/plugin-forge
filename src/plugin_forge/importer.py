"""Retrofit an existing plugin repo into a `forge.yaml`.

Strategy: sniff conventional manifest paths, merge into a single ForgeSpec,
best-effort. Never mutates the source repo — only writes `forge.yaml` at the
repo root (or a path the caller chooses).

Fidelity notes:
    - MCP package detection cross-references `[project.scripts]` in pyproject
      so `usage-pulse-mcp` (a console script) resolves back to the module it
      calls into (`module:usage_pulse.mcp_server`).
    - Hooks declared in provider manifests take precedence over hooks/ dir
      files; if both are present, manifest wins and the dir file is skipped.
    - Unknown top-level manifest keys are captured in
      `spec.provider_extras.<provider>` so a round-trip preserves them.
    - Skill/command/agent surfaces are collected from the file tree; provider
      subsetting via `surface.providers` is not inferred (impossible from
      files alone).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

try:
    import tomllib  # 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

from plugin_forge.spec import (
    AgentSurface,
    CommandSurface,
    ForgeSpec,
    HookSurface,
    InstallTargets,
    Marketplace,
    McpSurface,
    Options,
    Provider,
    ProviderExtras,
    SkillSurface,
    Surfaces,
)

KNOWN_MANIFEST_KEYS = {
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "skills",
    "commands",
    "agents",
    "mcpServers",
    "hooks",
    "interface",
    "sessionStart",
    "skillInstructions",
}


def sniff(repo: Path) -> ForgeSpec:
    """Inspect a repo and return a ForgeSpec best-guess."""
    repo = repo.resolve()
    if not repo.is_dir():
        raise ValueError(f"{repo} is not a directory")

    manifests = _load_provider_manifests(repo)
    providers = [p for p, m in manifests.items() if m is not None]
    if not providers:
        providers = [Provider.CLAUDE]

    canonical = _pick_canonical(manifests)
    name = canonical.get("name") or repo.name
    version = _detect_version(repo, canonical)
    description = canonical.get("description")

    pyproject_scripts = _pyproject_scripts(repo)

    skills = _list_dir_surfaces(repo, "skills", _skill_from_dir)
    commands = _list_dir_surfaces(repo, "commands", _command_from_file)
    agents = _list_dir_surfaces(repo, "agents", _agent_from_file)
    hooks = _detect_hooks(repo, manifests)
    mcp = _detect_mcp(repo, manifests, pyproject_scripts)

    metadata = _collect_metadata(manifests)
    provider_extras = _collect_provider_extras(manifests)
    options = _detect_options(manifests)

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
        provider_extras=provider_extras,
        options=options,
    )


def _load_provider_manifests(repo: Path) -> dict[Provider, dict[str, Any] | None]:
    return {
        Provider.CLAUDE: _read_json(repo / ".claude-plugin" / "plugin.json"),
        Provider.CODEX: _read_json(repo / ".codex-plugin" / "plugin.json"),
        Provider.KIMI: _read_json(repo / "kimi.plugin.json"),
    }


def _pick_canonical(manifests: dict[Provider, dict[str, Any] | None]) -> dict[str, Any]:
    for provider in (Provider.KIMI, Provider.CLAUDE, Provider.CODEX):
        m = manifests.get(provider)
        if m:
            return m
    return {}


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cast(dict[str, Any], data)
    except Exception:
        return None


def _pyproject_scripts(repo: Path) -> dict[str, str]:
    """Return `[project.scripts]` mapping script name → `module:function`."""
    pyproject = repo / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:
        return {}
    scripts = data.get("project", {}).get("scripts", {})
    return {k: v for k, v in scripts.items() if isinstance(v, str)}


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


def _list_dir_surfaces(repo: Path, subdir: str, factory: Any) -> list[Any]:
    base = repo / subdir
    if not base.is_dir():
        return []
    out: list[Any] = []
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
    rel = skill_md.relative_to(path.parents[1]).as_posix()
    return SkillSurface(name=path.name, path=rel)


def _command_from_file(path: Path) -> CommandSurface | None:
    if not path.is_file() or path.suffix != ".md":
        return None
    return CommandSurface(name=path.stem, path=path.relative_to(path.parents[1]).as_posix())


def _agent_from_file(path: Path) -> AgentSurface | None:
    if not path.is_file() or path.suffix != ".md":
        return None
    return AgentSurface(name=path.stem, path=path.relative_to(path.parents[1]).as_posix())


def _detect_hooks(
    repo: Path, manifests: dict[Provider, dict[str, Any] | None]
) -> list[HookSurface]:
    """Prefer manifest-declared hooks; fall back to hooks/ dir sniff.

    Dedup by (event, script_or_command_hash). Same event with different
    scripts is preserved as separate entries; identical duplicates are merged.
    """
    from_manifest = _hooks_from_manifests(repo, manifests)
    if from_manifest:
        return from_manifest

    hooks_dir = repo / "hooks"
    if not hooks_dir.is_dir():
        return []

    seen: set[tuple[str, str]] = set()
    result: list[HookSurface] = []
    for f in sorted(hooks_dir.iterdir()):
        if not f.is_file() or f.suffix not in (".py", ".sh", ".ps1"):
            continue
        event = _event_from_filename(f.stem)
        rel = f.relative_to(repo).as_posix()
        key = (event, rel)
        if key in seen:
            continue
        seen.add(key)
        result.append(HookSurface(event=event, script=rel))
    return result


def _hooks_from_manifests(
    repo: Path, manifests: dict[Provider, dict[str, Any] | None]
) -> list[HookSurface]:
    """Extract hooks from any provider's manifest (inline or `hooks.json` sidecar).

    Returns the union across providers, deduped by (event, command).
    """
    seen: set[tuple[str, str]] = set()
    result: list[HookSurface] = []
    for manifest in manifests.values():
        if not manifest:
            continue
        raw = manifest.get("hooks")
        entries = _resolve_hook_entries(repo, raw)
        for entry in entries:
            event = str(entry.get("event") or "")
            command = str(entry.get("command") or "")
            if not event or not command:
                continue
            key = (event, command)
            if key in seen:
                continue
            seen.add(key)
            script = _extract_script_from_command(command)
            hook = HookSurface(
                event=event,
                script=script,
                command=None if script else command,
                matcher=entry.get("matcher"),
                timeout_seconds=entry.get("timeout"),
            )
            result.append(hook)
    return result


def _resolve_hook_entries(repo: Path, raw: Any) -> list[dict[str, Any]]:
    """Normalize a manifest `hooks` value into a list of entry dicts."""
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]
    if isinstance(raw, str):
        candidate = repo / raw.lstrip("./")
        data = _read_json(candidate)
        if isinstance(data, dict) and isinstance(data.get("hooks"), list):
            return [e for e in data["hooks"] if isinstance(e, dict)]
    if isinstance(raw, dict) and isinstance(raw.get("hooks"), list):
        return [e for e in raw["hooks"] if isinstance(e, dict)]
    return []


_SCRIPT_IN_CMD = re.compile(r"['\"]([^'\"]+\.py)['\"]")


def _extract_script_from_command(command: str) -> str | None:
    """Best-effort extraction of a `.py` script path from an inline command.

    If we can spot one, we treat the hook as script-based (letting forge
    regenerate the command shape on emit). Otherwise the raw command is kept
    verbatim.
    """
    matches = _SCRIPT_IN_CMD.findall(command)
    for m in matches:
        norm = str(m).replace("\\", "/")
        if norm.startswith("hooks/") or "/hooks/" in norm:
            return norm
    return None


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
    manifests: dict[Provider, dict[str, Any] | None],
    pyproject_scripts: dict[str, str],
) -> list[McpSurface]:
    servers: dict[str, dict[str, Any]] = {}
    for provider in (Provider.KIMI, Provider.CLAUDE, Provider.CODEX):
        m = manifests.get(provider)
        if not m:
            continue
        raw = m.get("mcpServers")
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
        package = _guess_package(cfg, pyproject_scripts)
        env_raw = cfg.get("env")
        env = list(env_raw.keys()) if isinstance(env_raw, dict) else []
        result.append(McpSurface(name=name, transport="stdio", package=package, env=env))
    return result


def _guess_package(cfg: dict[str, Any], pyproject_scripts: dict[str, str]) -> str:
    """Resolve MCP invocation into forge's canonical `package:` form.

    Priority:
        1. `-m <module>` in args → `module:<module>`.
        2. `<script>.py` in args → `python:<script>`.
        3. Bare script alias (e.g. `usage-pulse-mcp`) matched against
           `[project.scripts]` → `module:<module>` (target of the entry point).
        4. Fallback to the command name.
    """
    args = cfg.get("args", []) if isinstance(cfg.get("args"), list) else []
    args_str = [a for a in args if isinstance(a, str)]

    if "-m" in args_str:
        idx = args_str.index("-m")
        if idx + 1 < len(args_str):
            return f"module:{args_str[idx + 1]}"

    for a in args_str:
        if a.endswith(".py"):
            return f"python:{a}"

    for alias, target in pyproject_scripts.items():
        if alias in args_str:
            module = target.split(":", 1)[0]
            return f"module:{module}"

    return str(cfg.get("command", "python"))


def _collect_metadata(manifests: dict[Provider, dict[str, Any] | None]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for provider in (Provider.KIMI, Provider.CODEX, Provider.CLAUDE):
        src = manifests.get(provider)
        if not src:
            continue
        for k in ("author", "homepage", "repository", "license", "keywords"):
            if k in src and k not in metadata:
                metadata[k] = src[k]
        iface = src.get("interface")
        if isinstance(iface, dict) and "interface" not in metadata:
            metadata["interface"] = _snakeify_interface(iface)
        session_start = src.get("sessionStart")
        if isinstance(session_start, dict) and "session_start_skill" not in metadata:
            metadata["session_start_skill"] = session_start.get("skill")
        instructions = src.get("skillInstructions")
        if instructions and "skill_instructions" not in metadata:
            metadata["skill_instructions"] = instructions
    author = metadata.get("author")
    if isinstance(author, dict):
        metadata["author"] = author.get("name", "0langa")
    return metadata


def _collect_provider_extras(
    manifests: dict[Provider, dict[str, Any] | None]
) -> ProviderExtras:
    extras = ProviderExtras()
    for provider in (Provider.CLAUDE, Provider.CODEX, Provider.KIMI):
        src = manifests.get(provider)
        if not src:
            continue
        bucket: dict[str, Any] = {}
        for key, value in src.items():
            if key in KNOWN_MANIFEST_KEYS:
                continue
            bucket[key] = value
        if bucket:
            setattr(extras, provider.value, bucket)
    return extras


def _detect_options(manifests: dict[Provider, dict[str, Any] | None]) -> Options:
    """Infer forge options from manifest shape."""
    claude = manifests.get(Provider.CLAUDE) or {}
    codex = manifests.get(Provider.CODEX) or {}
    shared = (
        claude.get("mcpServers") == "./.mcp.json"
        and codex.get("mcpServers") == "./.mcp.json"
    )
    return Options(shared_mcp_file=shared)


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
        "brandColor": "brand_color",
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
