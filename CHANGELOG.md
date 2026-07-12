# Changelog

All notable changes to plugin-forge.

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
