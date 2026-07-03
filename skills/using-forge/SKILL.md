---
name: using-forge
description: Use this skill when maintaining a Forge-managed plugin, when checking manifest drift, when compiling provider files, when installing a dev copy, when validating hooks/MCP, or when auditing Claude/Codex/Kimi install state. Use proactively in Forge repos; automatically trigger on forge.yaml.
---

# Using Plugin Forge

## Purpose

Use Plugin Forge as the normal maintenance layer for Claude Code, Codex, and
Kimi Code plugin repos. It owns plugin topology, generated manifests, install
state, parity checks, and safe hook/MCP packaging.

Prefer Forge whenever a task affects more than one provider surface.
Examples include adding a skill, adding an MCP server, installing a dev copy,
checking provider drift, or validating provider-specific hooks.

## Inputs

You receive a user request and the current repository. Treat this skill as active
when the repo contains one of these files:

```text
forge.yaml
.claude-plugin/plugin.json
.codex-plugin/plugin.json
kimi.plugin.json
hooks/hooks.json
.mcp.json
```

If `forge.yaml` exists, it is the source of truth. If it does not exist but
provider manifests exist, use the `import-existing` skill instead.

## Tool Selection

Use Forge MCP tools before hand-editing generated provider files.

```text
Question about repo state       -> forge.status
Regenerate provider manifests   -> forge.compile
Check or fix manifest drift      -> forge.sync_check(fix=true)
Install into providers          -> forge.install(provider="all", mode="link")
Remove provider install         -> forge.uninstall(provider="all")
Machine-wide install inventory  -> forge.audit_installed
Synthetic hook validation       -> forge.hook_test(event="...")
Local MCP runner command        -> forge.mcp_dev
```

Use `release-plugin` for version bump, tag, push, or marketplace release work.
Use `import-existing` only when a plugin repo lacks `forge.yaml`.

## Operating Rules

Read `forge.yaml` before editing provider manifests. Provider manifests are
generated output unless the repo has not been imported yet.

After changing `forge.yaml`, run:

```powershell
forge compile
forge sync-check
```

After changing hook, skill, command, MCP, or manifest logic, run the repo's
tests and at least one synthetic hook or MCP smoke test when available.

When installing locally for development, use link mode:

```powershell
forge install --provider all --mode link
```

Use copy mode only for frozen install tests or release-like validation.

## Output Format

For user-facing status, keep output compact:

```text
Forge status: <plugin> v<version>, providers: Claude/Codex/Kimi, drift: none, installed: all.
```

For repair work:

```text
Fixed provider drift in <files>. Verified with forge sync-check and pytest.
```

For blocked work:

```text
Blocked: <specific provider/config reason>. No provider config was changed.
```

## Safety

Do not patch Claude `installed_plugins.json` directly. Claude plugin install
goes through a marketplace or skills-directory plugin discovery.

Do not add Kimi hook blocks directly to `config.toml` for plugin hooks. Kimi
plugin hooks live in `kimi.plugin.json`; install state lives in
`~/.kimi-code/plugins/installed.json`.

Do not add global Codex MCP blocks for a plugin whose `.codex-plugin/plugin.json`
already points to bundled MCP configuration. Enable the plugin instead.

Do not create RECALL memories from this repo unless the user explicitly asks.

## Examples

User: "Is this plugin installed everywhere?"

Action:

```text
forge.status
forge.audit_installed
```

Response: installed providers, missing providers, and drift state.

User: "I added a hook, make sure all providers are updated."

Action:

```text
forge.compile
forge.sync_check(fix=true)
pytest
```

Response: files changed and verification result.

User: "Make this plugin safe for Kimi too."

Action: check official Kimi docs, inspect `kimi.plugin.json`, verify MCP/hook
paths stay inside plugin root, run `kimi doctor` after install.

## Decision Matrix

| Request | First action | Follow-up |
| --- | --- | --- |
| "What changed?" | `forge.status` | `git diff` only if status needs detail |
| "Manifests drifted" | `forge.sync_check(fix=true)` | rerun tests |
| "Install this locally" | `forge.install(provider="all", mode="link")` | provider reload |
| "Hook seems broken" | `forge.hook_test(event="...")` | inspect error log |
| "MCP missing" | `forge.mcp_dev` | run server command directly |
| "Release it" | switch to `release-plugin` | do not continue here |

## Verification Checklist

For provider file changes:

```powershell
forge compile
forge sync-check
pytest
```

For hook changes:

```powershell
forge hook-test --event SessionStart
forge hook-test --event PostToolUse
```

For MCP changes:

```powershell
forge mcp-dev
```

Run the printed MCP command once before reporting success.

## Troubleshooting

If manifests drift after compile, inspect the generated file and the corresponding
adapter before editing the manifest by hand.

If install breaks a provider, restore from the Forge backup or uninstall receipt
before attempting a second install.

If a provider docs shape is unclear, stop provider-specific edits and check the
official docs before guessing.

If a target plugin has its own installer, compare its behavior against Forge and
remove duplicate global config mutation only after tests prove equivalence.

## Related

- `release-plugin`: release automation for Forge-managed plugin repos.
- `import-existing`: one-time retrofit for hand-made plugin repos.
