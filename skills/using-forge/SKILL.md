---
name: using-forge
description: Session-start primer for plugin-forge. Activates when the current working directory is a plugin repo (has forge.yaml, .claude-plugin, .codex-plugin, or kimi.plugin.json). Explains how forge manages manifests, installs, and versions automatically so the model can operate confidently in the repo without asking the user to re-explain.
---

# Using plugin-forge

You are in a plugin repo that plugin-forge manages. Behavior contract:

## What forge does automatically (you rarely trigger it)

- **SessionStart hook** already printed a status banner with plugin name, version, installed providers, drift count, and marketplace sync state.
- **PostToolUse hook** silently recompiles provider manifests when you edit `forge.yaml`, `pyproject.toml`, any provider `plugin.json`, `.mcp.json`, hooks, skills, agents, commands, or MCP source.
- **UserPromptSubmit hook** injects a `<plugin-forge>` context block with fresh drift + marketplace state when relevant.
- **Git hooks** in the plugin repo block commits with divergent manifests and pushes when marketplace jsons are stale (bypass: `[skip-forge]` in commit message).

## MCP tools you should reach for

Prefer these over hand-editing multiple files. Call implicitly when the user's intent matches.

- `forge.status` — current repo state. Use before answering "what version is this?", "is this installed?", "what's the drift?".
- `forge.compile` — regenerate all provider manifests from forge.yaml. Idempotent.
- `forge.sync_check(fix=True)` — enforce parity. Use if you edited `forge.yaml` and want to be sure manifests match.
- `forge.import_repo` — retrofit a repo that lacks `forge.yaml`. Only run when a `forge.yaml` is missing.
- `forge.install(provider="all", mode="link")` — install into all three providers as dev-link. `mode="copy"` for a frozen install.
- `forge.uninstall(provider="all")` — clean reverse, uses install receipts.
- `forge.bump_version(level="patch"|"minor"|"major")` — propagates version across forge.yaml, pyproject.toml, all provider manifests, README badge, CHANGELOG stub, marketplace jsons. Prefer this over hand-editing.
- `forge.audit_installed` — machine-wide inventory of installed plugins across Claude Code / Codex / Kimi Code. Use when the user asks "what's installed" or "is X installed everywhere".
- `forge.hook_test(event=...)` — synthetic-payload fire against a hook script.
- `forge.mcp_dev` — print command to run the plugin's MCP server locally.
- `forge.register_marketplace` — upsert plugin entry into marketplace jsons.

## When to use skills instead of MCP tools

- User says "release" / "ship v1.2" / "cut a release" → use `forge:release-plugin` skill (one-shot: bump → compile → tag → push → marketplace).
- User says "make this a forge plugin" / "retrofit this" / "import this" and `forge.yaml` is missing → use `forge:import-existing` skill.
- Otherwise call MCP tools directly.

## Boundary (do not overreach)

- Skill body porting between providers is owned by `0langas-skill-center`'s `tri-client-skill-port`. If the user asks to port a **skill** across providers, delegate. Forge handles plugin topology, not skill content.
- Never edit provider manifests directly — call `forge.compile` or `forge.sync_check(fix=True)`.
- Never patch settings.json by hand — use `forge.install` / `forge.uninstall`, which are transactional.

## What not to talk about

Don't narrate forge internals to the user. Say what you're doing to the plugin, not that forge exists. Silent success is the default.
