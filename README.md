# plugin-forge

Multi-provider AI-coding plugin lifecycle automation.

MCP server + hooks keep plugins for **Claude Code**, **Codex**, and **Kimi Code** automatically coherent while you edit source. Version bumps, manifest generation, cross-provider installs, marketplace registration, parity enforcement — all driven by a single canonical `forge.yaml` per plugin. Zero-touch during normal work.

## Why

Every non-trivial multi-provider plugin has:

- 3+ manifest files (Claude `plugin.json`, Codex config, Kimi `kimi.plugin.json`)
- Per-provider install directories (`~/.claude/plugins/`, `~/.codex/plugins/`, kimi variant)
- Settings.json patches (MCP registrations, hook wiring)
- Version strings scattered across `pyproject.toml`, manifests, README badges, marketplace jsons
- Hook + MCP + agent + command + skill surfaces that must stay in sync across providers

Manually keeping this coherent = repeated 5-file hand-edits, silent drift, broken installs. Plugin-forge collapses all of it behind one spec + automation.

## Design principles

- **Automation-first.** Hooks + MCP tools do the work. Slash commands are escape hatches, not primary UX.
- **Single source of truth.** `forge.yaml` per plugin. Adapters emit provider-specific manifests.
- **Transactional installs.** Settings.json patched with backup + rollback + receipt-based uninstall.
- **Fail-open hooks.** Nothing in forge is allowed to break the host session.
- **Clean provider boundary.** Skill body porting belongs to `0langas-skill-center` (tri-client-skill-port). Forge owns topology, install, MCP, hooks, versioning, marketplace.

## What it does (surface)

### MCP tools (model calls these implicitly when in a plugin repo)

- `forge.status` — surfaces, install state, drift, marketplace sync
- `forge.compile` — regen manifests from `forge.yaml`
- `forge.import` — retrofit existing plugin → `forge.yaml`
- `forge.sync` — enforce parity across providers
- `forge.install` / `forge.uninstall` — transactional, per-provider
- `forge.bump` — propagate version across manifests + marketplace jsons
- `forge.release` — bump + tag + push + marketplace PR
- `forge.audit_installed` — cross-provider inventory of installed plugins
- `forge.mcp_dev` — spawn stdio MCP runner for iteration
- `forge.hook_test` — synthetic-payload fire against hook script
- `forge.register_marketplace` — add entry to marketplace jsons

### Hooks (installed into host provider)

- **SessionStart** — if cwd is inside a plugin repo, surface status banner + auto-audit
- **PostToolUse (Edit/Write)** — if edited path is a manifest/hook/skill/mcp source, auto-recompile silently
- **UserPromptSubmit** — inject curated plugin-state context (drift, pending bumps)
- **PreCompact / Stop** — persist plugin state for next session

### Git hooks (installed into target plugin repos)

- **pre-commit** — block commit if provider manifests diverge from `forge.yaml`
- **pre-push** — block push if marketplace jsons stale vs plugin version (bypass with `[skip-forge]`)

### Skills (thin, single-call)

- `forge:using-forge` — session-start primer, activates only in plugin repos
- `forge:release-plugin` — one-shot autonomous release (bump → tag → push → marketplace PR)
- `forge:import-existing` — one-shot retrofit of an existing plugin

### Slash commands

- `/forge` — status dashboard (rare use; hook banner covers 95%)

## Canonical spec: `forge.yaml`

```yaml
name: my-plugin
version: 1.2.0
providers: [claude, codex, kimi]

surfaces:
  skills:
    - name: my-skill
      path: skills/my-skill/SKILL.md
  commands:
    - name: mycmd
      path: commands/mycmd.md
  agents:
    - name: my-agent
      path: agents/my-agent.md
  hooks:
    - event: SessionStart
      script: hooks/session_start.py
  mcp:
    - name: my-plugin
      transport: stdio
      package: python:./src/my_plugin/mcp_server.py
      env: [MY_PLUGIN_HOME]

install:
  claude: ~/.claude/plugins/my-plugin/
  codex:  ~/.codex/plugins/my-plugin/
  kimi:   ~/.kimi-code/plugins/my-plugin/

settings_patches:
  mcpServers:
    my-plugin:
      command: "python"
      args: ["-m", "my_plugin.mcp_server"]

marketplace:
  claude_manifest: "../0langas-plugin-marketplace/plugins.json"
  kimi_manifest:   "../0langas-plugin-marketplace/kimi-marketplace.json"
```

## Install

```bash
cd C:\Users\Julius\source\repos\0langas-plugin-forge
uv venv
uv pip install -e .
python scripts/install.py --provider all
```

## Status

Alpha. See [CHANGELOG.md](CHANGELOG.md).

## License

MIT
