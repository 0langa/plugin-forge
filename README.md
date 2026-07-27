# plugin-forge

**Multi-provider AI-coding plugin lifecycle automation.**

MCP server + hooks that keep plugins for **Claude Code**, **Codex**, and **Kimi Code** automatically coherent while you edit source. One canonical `forge.yaml` per plugin drives version bumps, manifest generation, cross-provider installs, marketplace registration, and parity enforcement. Zero-touch during normal work.

---

## Why

Every non-trivial multi-provider plugin has:

- 3+ manifest files (Claude `.claude-plugin/plugin.json`, Codex `.codex-plugin/plugin.json`, Kimi `kimi.plugin.json`)
- Per-provider install directories (`~/.claude/plugins/`, `~/.codex/plugins/`, `~/.kimi-code/plugins/`)
- Provider plugin manifests (MCP registrations, hook wiring, timeouts)
- Version strings scattered across `pyproject.toml`, three manifests, README badges, and two marketplace JSONs
- Hook + MCP + agent + command + skill surfaces that must stay identical across providers

Manually keeping this coherent = repeated 5-file hand-edits, silent drift, broken installs. Plugin-forge collapses all of it behind one spec + automation.

---

## Design principles

- **Automation-first.** Hooks + MCP tools do the work. Slash commands are escape hatches, not primary UX.
- **Single source of truth.** `forge.yaml` per plugin. Adapters emit provider-specific manifests deterministically.
- **Manifest-owned installs.** Provider discovery files own MCP and hook wiring; global settings patches are a legacy escape hatch, not the default path.
- **Fail-open hooks.** Nothing in forge is allowed to break the host session — every hook wraps its body in a safety net.
- **Clean provider boundary.** Skill body porting is owned by `0langas-skill-center` (tri-client-skill-port). Forge owns topology, install, MCP, hooks, versioning, marketplace.
- **Round-trip fidelity.** `forge.import` → `forge.compile` should never lose information. Unknown manifest keys go into `provider_extras` and re-emit verbatim.

---

## What it does

### MCP tools (model calls these implicitly when in a plugin repo)

| Tool | Purpose |
| --- | --- |
| `forge.init_project` | Bootstrap a new plugin repo with `forge.yaml` and standard source dirs |
| `forge.status` | Compact plugin-repo report: surfaces, install state, drift, marketplace sync, git |
| `forge.compile` | Regenerate every provider manifest from `forge.yaml` |
| `forge.import_repo` | Retrofit an existing plugin repo into a `forge.yaml` (best-effort sniff) |
| `forge.sync_check` | Detect (and optionally fix) drift between spec and provider manifests |
| `forge.install` | Install into one or all providers (link mode for dev, copy mode for frozen) |
| `forge.uninstall` | Reverse install; legacy settings patches are rolled back exactly via receipts |
| `forge.bump_version` | Propagate version across forge.yaml, pyproject, all manifests, README badge, CHANGELOG, marketplace jsons |
| `forge.audit_installed` | Cross-provider inventory of every plugin installed on this machine |
| `forge.hook_test` | Fire a hook script with a synthetic payload; return exit + stdout/stderr |
| `forge.mcp_dev` | Print the command that would run the plugin's MCP server locally |
| `forge.register_marketplace` | Upsert plugin entry into `plugins.json` + `kimi-marketplace.json` |

### Hooks (installed into host provider)

- **SessionStart** — if cwd is inside a plugin repo, surface status banner and silently auto-fix manifest drift
- **PostToolUse (Edit/Write)** — if the edited path is a manifest/hook/skill/mcp source, recompile provider manifests immediately
- **UserPromptSubmit** — inject a curated `<plugin-forge>` context block with fresh drift/marketplace state
- Every hook fail-open; errors go to `~/.plugin-forge/errors.log`, host session never breaks

### Git hooks (installed into target plugin repos)

- **pre-commit** — block commit if provider manifests diverge from `forge.yaml`
- **pre-push** — block push if marketplace jsons stale vs plugin version
- **Bypass**: `[skip-forge]` in commit message, or `--no-verify`

### Skills (thin, single-call, only where actually needed)

- `forge:using-forge` — session-start primer, activates only in plugin repos
- `forge:release-plugin` — one-shot autonomous release (bump → compile → commit → tag → push → GitHub release → marketplace update)
- `forge:import-existing` — one-shot retrofit of an existing plugin

### Slash commands

- `/forge` — status dashboard (rare use; hook banner covers 95%)

---

## Canonical spec: `forge.yaml`

Full example, based on the real `usage-pulse` shape:

```yaml
name: usage-pulse
version: 0.1.0
description: Local passive usage telemetry for Claude Code, Codex, and Kimi Code sessions.
providers: [claude, codex, kimi]

surfaces:
  skills:
    - name: using-pulse
      path: skills/using-pulse/SKILL.md
    - name: usage-report
      path: skills/usage-report/SKILL.md
  commands:
    - name: pulse
      path: commands/pulse.md
  hooks:
    - event: SessionStart
      script: hooks/session_start.py
      timeout_seconds: 10
    - event: UserPromptSubmit
      script: hooks/user_prompt_submit.py
      timeout_seconds: 10
    - event: PreToolUse
      script: hooks/pre_tool_use.py
      matcher: .*
      timeout_seconds: 10
    - event: PostToolUse
      script: hooks/post_tool_use.py
      matcher: .*
      timeout_seconds: 10
    - event: PreCompact
      script: hooks/pre_compact.py
      timeout_seconds: 10
    - event: Stop
      script: hooks/stop.py
      timeout_seconds: 10
  mcp:
    - name: usage-pulse
      transport: stdio
      package: module:usage_pulse.mcp_server

install:
  claude: ~/.claude/plugins/usage-pulse/
  codex:  ~/.codex/plugins/usage-pulse/
  kimi:   ~/.kimi-code/plugins/managed/usage-pulse/

marketplace:
  claude_manifest: ../0langas-plugin-marketplace/plugins.json
  kimi_manifest:   ../0langas-plugin-marketplace/kimi-marketplace.json

options:
  shared_mcp_file: true    # Claude + Codex both point at one .mcp.json

metadata:
  author: 0langa
  license: MIT
  homepage: https://github.com/0langa/usage-pulse
  keywords: [usage, telemetry, local, mcp, hooks]
  interface:
    display_name: Usage Pulse
    short_description: Local session usage telemetry
    long_description: Passively records local per-session usage counters and exposes summaries through MCP.
    developer_name: 0langa
    category: Productivity
    capabilities: [Read, Local, Automation]
    brand_color: '#256D5A'
  session_start_skill: pulse:using-pulse

provider_extras:
  claude:
    defaultEnabled: true
  # kimi-only or codex-only fields also live here; forge merges them verbatim
```

Emitted files after `forge compile`:

```
.claude-plugin/plugin.json    # thin, points at ./skills, ./commands, ./.mcp.json
.codex-plugin/plugin.json     # rich, includes interface block, same references
kimi.plugin.json              # inline mcpServers + inline hooks + sessionStart block
.mcp.json                     # Claude MCP file
.codex-mcp.json               # Codex MCP file, unless options.shared_mcp_file is true
hooks/hooks.json              # default hook wiring for Claude
hooks/codex-hooks.json        # hook wiring for Codex
```

Emitted hook commands use the official runtime root variables: `CLAUDE_PLUGIN_ROOT` for Claude, `PLUGIN_ROOT` for Codex, and `KIMI_PLUGIN_ROOT` for Kimi. Compatibility fallbacks are only used where provider docs expose them.

---

## Quick start

### New plugin

```bash
mkdir my-plugin && cd my-plugin
forge init --name my-plugin --providers all
# Add your source: hooks/, skills/, mcp/, commands/, etc.
# Edit forge.yaml for real surfaces and metadata
forge compile        # emit all provider manifests
forge sync           # verify emitted manifests match forge.yaml
forge install        # link into ~/.claude, ~/.codex, ~/.kimi-code
```

### Retrofit an existing plugin

```bash
cd path/to/existing-plugin
forge import         # sniff manifests → write forge.yaml
forge install-git-hooks   # add pre-commit + pre-push guards
forge sync           # verify parity
forge install        # link into provider plugin directories when ready
```

### Cut a release

```bash
forge bump patch     # or minor / major
forge sync --fix     # regenerate manifests if needed
git add -A && git commit -m "release: v..."
git tag v...
git push --tags
# Or ask the model to run the `release-plugin` skill for autonomous execution.
```

### Machine-wide audit

```bash
forge audit
# Lists every plugin installed under ~/.claude, ~/.codex, ~/.kimi-code
# with version + MCP + hooks registration state, orphans, and cross-provider gaps.
```

---

## Install forge itself

```bash
git clone https://github.com/0langa/plugin-forge C:/Users/ExampleUser/source/repos/0langa-plugin-forge
cd plugin-forge
uv venv
uv pip install -e ".[dev]"
python scripts/install.py --mode link --provider all
```

After that, every provider discovers the `plugin-forge` MCP server and SessionStart / PostToolUse / UserPromptSubmit hooks from the installed plugin manifests. No global MCP or hook settings are written by the forge self-install path.

---

## Boundary with skill-center

Skill-center (`0langas-skill-center`) owns single-skill operations: body porting between providers, trigger evaluation, skill curation.

Forge owns plugin-level operations: manifests, installs, MCP wiring, hooks, versioning, marketplace, cross-provider parity. When forge needs a skill body ported, it delegates to skill-center's `tri-client-skill-port`.

---

## Status

Alpha. See [CHANGELOG.md](CHANGELOG.md).

- 94 unit + integration tests passing
- Round-trip verified against real `usage-pulse` plugin
- Live install verification: pending on your machine

## License

MIT
