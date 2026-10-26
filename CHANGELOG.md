# Changelog

## 0.2.17 - 2026-10-26

- Replace the plugin icon and logo with the approved Folded Crest artwork and include its SVG source.


## 0.2.16 - 2026-10-26

- Mark the plugin dormant while keeping existing functionality and installation IDs.
- Publish through https://github.com/0langa/plugins; Kimi compatibility is legacy.

All notable changes to plugin-forge.

## [0.2.15] - 2026-10-15

- The forge-local Claude marketplace now lists each plugin as a `./plugins/<name>` path, the only string source Claude Code accepts. `forge install --provider claude` copies the plugin to `~/.plugin-forge/marketplaces/claude/forge-local/plugins/<name>/` and lists that copy. Installing again refreshes the copy and keeps its `.venv`, and uninstalling removes it. Before, each entry held the repo's absolute path, and `claude plugin validate` rejected it.
- Generated Claude hooks now work on Windows on their own. Claude Code ignores `commandWindows`, so Claude hooks get one POSIX `command`, which Claude Code runs through Git Bash on Windows and `sh` elsewhere. It starts the hook through `uv`, never `python3` (on Windows often only the Microsoft Store stub), and falls back to `~/.local/bin/uv` when `uv` is not on PATH. Codex hooks keep their `commandWindows`.
- Upgrade: run `forge install --provider claude` again for each plugin you registered with Claude Code, so its entry moves to the `./plugins/<name>` form. Entries written by 0.2.14 or earlier keep their absolute path until then, and `claude plugin validate` flags them. Then add the marketplace once with `claude plugin marketplace add ~/.plugin-forge/marketplaces/claude/forge-local` and install with `claude plugin install <name>@forge-local`.
- Upgrade: Claude Code now reads that copy, not your repo, so run `forge install --provider claude` again after editing a forge plugin.
- Upgrade: other forge-managed plugins get the new hook command on their next `forge compile`. Until then their `hooks/hooks.json` keeps the old form, and `forge sync` reports no drift for it, because it does not compare hooks files. On Windows the new command needs Git for Windows, because Claude Code runs hooks through Git Bash.

## [0.2.14] - 2026-10-14

- Lock patched versions of three transitive dependencies of `mcp[crypto]` (pyjwt 2.15.1, anyio 4.15.1, cryptography 50.0.2), clearing 19 known advisories. Direct dependency ranges are unchanged.
- Keep the test suite out of the real home directory: install tests no longer add a `demo` entry and `.forge-backup.*` copies to the forge-local Claude marketplace under `~/.plugin-forge`.

## [0.2.13] - 2026-09-09

- Discover versioned Claude and Codex marketplace cache copies during installed-plugin audits, and exclude provider infrastructure directories from orphan findings.
- Read Codex MCP registration from `config.toml` and recognize Claude's standard automatic hook discovery.
- Label cached versions explicitly; cache presence does not establish the active version or enabled state.

## [0.2.12] - 2026-08-05

- Pending release notes.

## [0.2.11] - 2026-08-05

- Preserve an existing Kimi plugin's enabled or disabled state when refreshing its managed copy.

## [0.2.10] - 2026-08-05

- Refresh `uv.lock` after version bump so locked CI environments resolve the released package metadata.

## [0.2.9] - 2026-08-05

- Honor `KIMI_CODE_HOME` for Kimi install targets, install registry updates, uninstall, and installed-plugin audits.
- Point this repository's marketplace checks at sibling `0langas-plugin-marketplace` catalogs instead of the parent source directory.

## [0.2.8] - 2026-08-05

- Aligned runtime version metadata with generated provider manifests.
- Hardened local sibling-plugin round-trip discovery and version regression coverage.

## [0.2.7] - 2026-07-28

- Synchronized `uv.lock` with release metadata so clean cached installs resolve Plugin Forge as `0.2.7`.

## [0.2.6] - 2026-07-28

- Fixed `mcp_dev` to render its local launcher with the Codex-relative provider context instead of raising a missing-argument `TypeError`.
- Added direct regression coverage for the returned MCP launcher shape.

## [0.2.5] - 2026-07-27

- Fixed generated Claude Code MCP launchers to anchor `--project` and `cwd` on `${CLAUDE_PLUGIN_ROOT}`. Claude Code spawns plugin MCP servers with the session working directory rather than the plugin directory, so the previous relative `.` resolved into the user's repo and the server exited with `ModuleNotFoundError`.
- Codex and Kimi MCP output is byte-identical to 0.2.4; both hosts already resolve relative paths against the plugin root.
- Added regression coverage asserting the Claude manifest is root-anchored and the Codex manifest stays relative.

## [0.2.4] - 2026-07-27

- Fixed generated module MCP launchers to use `uv run --project .` instead of editable-installing the host working directory.
- Added regression coverage preventing `--with-editable` from returning to provider MCP manifests.

## [0.2.3] - 2026-07-27

- Removed workstation-specific names and paths from public documentation, source comments, and test fixtures.
- Added regression coverage preventing private Windows identity data from entering tracked files.
- Made hook entrypoints self-bootstrap their source tree when invoked directly by provider runtimes.

## [0.2.2] - 2026-07-13

- Removed duplicate Claude hook declaration and rely on standard `hooks/hooks.json` autodiscovery.
- Added regression coverage for committed Claude manifest shape.

## [0.2.1] - 2026-07-13

- Declared bundled Claude hooks in plugin metadata.
- Removed editable-install flags from generated MCP launch commands so cached installs remain portable.

## [0.2.0] - 2026-07-12

- Added provider-specific hook arguments and matchers to the Forge schema.
- Preserved hook status messages and Windows commands during provider compilation.
- Enabled Usage Pulse manifests to round-trip without losing provider identity.

## [0.1.1] - 2026-07-12

- Prevent hosted MCP status calls from blocking on Git subprocesses.
- Preserve Codex visual metadata and cross-platform hook commands during compilation.
- Accept versionless Kimi marketplace entries during sync checks.

## [0.1.0] - 2026-07-03

Initial alpha.

- Canonical `forge.yaml` spec + Pydantic validator
- Manifest adapters: Claude Code, Codex, Kimi Code
- Transactional settings.json patcher with backup + rollback + install receipts
- MCP server (stdio) with tools: `status`, `compile`, `import`, `sync`, `install`, `uninstall`, `bump`, `audit_installed`, `release`, `register_marketplace`, `mcp_dev`, `hook_test`
- Hooks: SessionStart banner, PostToolUse auto-compile
- Skills: `using-forge`, `release-plugin`, `import-existing`
- Slash command: `/forge`
- Git-hook templates for target plugin repos: pre-commit, pre-push
- Import: reverse-engineer existing plugins into `forge.yaml`
- Install/uninstall scripts for forge itself into all three providers
